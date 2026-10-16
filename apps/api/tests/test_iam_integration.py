import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.main import app
from app.modules.iam.models import AuditEvent, AuthSession, MfaChallenge, Role, User, now
from app.modules.iam.security import digest, get_mfa_verifier, hasher
from app.modules.iam.service import revoke_all

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Requires migrated PostgreSQL."
    ),
]
PASSWORD = "Synthetic integration password 123"
ORIGIN = {"Origin": "http://localhost:3000"}


@pytest.fixture(scope="module")
def test_engine():
    schema, url = create_test_schema()
    engine = create_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()
        drop_test_schema(schema)


@pytest.fixture
def db(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    app.dependency_overrides[get_db] = lambda: session
    original = settings.api_cors_origins
    settings.api_cors_origins = ["http://localhost:3000"]
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        settings.api_cors_origins = original
        session.close()
        transaction.rollback()
        connection.close()


def account(db: Session, role_code: str = "ADMIN") -> User:
    role = db.scalar(select(Role).where(Role.code == role_code))
    assert role
    user = User(
        email=f"staff-{uuid4().hex}@example.org",
        full_name="Synthetic Staff",
        password_hash=hasher.hash(PASSWORD),
        roles=[role],
        primary_role_id=role.id,
    )
    db.add(user)
    db.commit()
    return user


def sign_in(client: TestClient, user: User) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}, headers=ORIGIN
    )
    assert response.status_code == 200, response.text


def headers(client: TestClient) -> dict[str, str]:
    return {**ORIGIN, "X-CSRF-Token": client.cookies.get("happy_csrf", "")}


def test_login_cookie_projection_logout_and_audit(db: Session) -> None:
    user = account(db, "MARKETING")
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email.upper(), "password": PASSWORD},
        headers=ORIGIN,
    )
    assert response.status_code == 200
    assert "HttpOnly" in response.headers.get_list("set-cookie")[0]
    assert "SameSite=lax" in response.headers.get_list("set-cookie")[0]
    result = client.get("/api/v1/auth/me")
    assert result.status_code == 200
    assert result.headers["Cache-Control"] == "no-store"
    assert [item["code"] for item in result.json()["workspaces"]] == ["MARKETING"]
    assert "password_hash" not in result.text
    assert client.get("/api/v1/users").status_code == 403
    assert client.get("/api/v1/audit-events").status_code == 403
    token = client.cookies.get("happy_session")
    assert client.post("/api/v1/auth/logout", headers=headers(client)).status_code == 204
    client.cookies.set("happy_session", token)
    assert client.get("/api/v1/auth/me").status_code == 401
    events = db.scalars(select(AuditEvent).where(AuditEvent.actor_id == str(user.id))).all()
    assert {row.event_code for row in events} == {"auth.login_success", "auth.logout"}
    assert PASSWORD not in str([row.after_json for row in events])


def test_login_throttling_and_generic_failures(db: Session) -> None:
    user = account(db)
    client = TestClient(app)
    for _ in range(settings.auth_login_limit):
        response = client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": "wrong"}, headers=ORIGIN
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}, headers=ORIGIN
        ).status_code
        == 429
    )
    assert client.get("/api/v1/auth/me").status_code == 401


def test_csrf_origin_and_anonymous_admin_access(db: Session) -> None:
    user = account(db)
    client = TestClient(app)
    assert client.get("/api/v1/users").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}
        ).status_code
        == 403
    )
    sign_in(client, user)
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 403
    assert (
        client.post(
            "/api/v1/auth/logout",
            headers={
                "Origin": "https://evil.example",
                "X-CSRF-Token": client.cookies.get("happy_csrf"),
            },
        ).status_code
        == 403
    )
    assert client.get("/api/v1/auth/me").status_code == 200


@pytest.mark.parametrize("state", ["expired", "idle", "inactive", "mfa"])
def test_stale_session_is_rejected(db: Session, state: str) -> None:
    user = account(db)
    client = TestClient(app)
    sign_in(client, user)
    session = db.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
    assert session
    if state == "expired":
        session.expires_at = now() - timedelta(seconds=1)
    elif state == "idle":
        session.last_seen_at = now() - timedelta(minutes=settings.auth_idle_minutes + 1)
    elif state == "inactive":
        user.is_active = False
    else:
        user.mfa_enabled = True
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_admin_user_changes_concurrency_revocation_and_mass_assignment(db: Session) -> None:
    admin = account(db)
    client = TestClient(app)
    sign_in(client, admin)
    supply = db.scalar(select(Role).where(Role.code == "SUPPLY"))
    assert supply
    payload = {
        "email": f"new-{uuid4().hex}@example.org",
        "full_name": "New Staff",
        "password": PASSWORD,
        "role_ids": [str(supply.id)],
        "primary_role_id": str(supply.id),
    }
    created = client.post("/api/v1/users", json=payload, headers=headers(client))
    assert created.status_code == 201, created.text
    row = created.json()
    assert "password_hash" not in row
    staff = db.get(User, row["id"])
    assert staff
    staff_client = TestClient(app)
    sign_in(staff_client, staff)
    denied = staff_client.patch(
        f"/api/v1/users/{admin.id}",
        json={"version": 1, "role_ids": [str(supply.id)]},
        headers=headers(staff_client),
    )
    assert denied.status_code == 403
    updated = client.patch(
        f"/api/v1/users/{staff.id}",
        json={"version": 1, "is_active": False},
        headers=headers(client),
    )
    assert updated.status_code == 200, updated.text
    assert staff_client.get("/api/v1/auth/me").status_code == 401
    stale = client.patch(
        f"/api/v1/users/{staff.id}",
        json={"version": 1, "full_name": "Stale"},
        headers=headers(client),
    )
    assert stale.status_code == 409
    assert (
        client.post(
            "/api/v1/users", json={**payload, "mfa_enabled": False}, headers=headers(client)
        ).status_code
        == 422
    )
    assert PASSWORD not in stale.text
    assert client.post("/api/v1/users", json=payload, headers=headers(client)).status_code == 409


def test_override_revokes_permissions_on_existing_session_and_last_admin_guard(db: Session) -> None:
    admin = account(db)
    client = TestClient(app)
    sign_in(client, admin)
    response = client.patch(
        f"/api/v1/users/{admin.id}",
        json={"version": 1, "overrides": [{"code": "user:manage", "effect": "DENY"}]},
        headers=headers(client),
    )
    assert response.status_code == 409
    db.rollback()
    staff = account(db, "SUPPLY")
    staff_client = TestClient(app)
    sign_in(staff_client, staff)
    changed = client.patch(
        f"/api/v1/users/{staff.id}",
        json={"version": 1, "overrides": [{"code": "workspace_supply:view", "effect": "DENY"}]},
        headers=headers(client),
    )
    assert changed.status_code == 200, changed.text
    assert staff_client.get("/api/v1/auth/me").json()["workspaces"] == []


def test_session_revocation_cannot_target_other_user(db: Session) -> None:
    first, second = account(db), account(db, "SUPPLY")
    client, other = TestClient(app), TestClient(app)
    sign_in(client, first)
    sign_in(other, second)
    other_session = other.get("/api/v1/auth/sessions").json()[0]
    assert (
        client.post(
            f"/api/v1/auth/sessions/{other_session['id']}/revoke", headers=headers(client)
        ).status_code
        == 404
    )
    own = client.get("/api/v1/auth/sessions").json()[0]
    assert (
        client.post(
            f"/api/v1/auth/sessions/{own['id']}/revoke", headers=headers(client)
        ).status_code
        == 204
    )
    assert client.get("/api/v1/auth/me").status_code == 401
    assert other.get("/api/v1/auth/me").status_code == 200


def test_mfa_challenge_fails_closed_and_is_consumed(db: Session) -> None:
    user = account(db)
    user.mfa_enabled = True
    db.commit()
    client = TestClient(app)
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}, headers=ORIGIN
        ).status_code
        == 503
    )
    assert client.get("/api/v1/auth/me").status_code == 401

    class TestFactor:
        available = True

        def verify(self, user: User, code: str) -> bool:
            return code == "123456"

    app.dependency_overrides[get_mfa_verifier] = TestFactor
    result = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}, headers=ORIGIN
    )
    assert result.json() == {"mfa_required": True}
    challenge = client.cookies.get("happy_mfa_challenge")
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.post("/api/v1/auth/mfa/verify", json={"code": "wrong"}, headers=ORIGIN).status_code
        == 401
    )
    assert (
        client.post("/api/v1/auth/mfa/verify", json={"code": "123456"}, headers=ORIGIN).status_code
        == 200
    )
    assert client.get("/api/v1/auth/me").status_code == 200
    client.cookies.set("happy_mfa_challenge", challenge)
    assert (
        client.post("/api/v1/auth/mfa/verify", json={"code": "123456"}, headers=ORIGIN).status_code
        == 401
    )


@pytest.mark.parametrize("change", ["password", "deactivation"])
def test_account_security_changes_invalidate_pending_mfa(db: Session, change: str) -> None:
    admin, staff, other = account(db), account(db, "SUPPLY"), account(db, "SUPPLY")
    staff.mfa_enabled = other.mfa_enabled = True
    db.commit()

    class TestFactor:
        available = True

        def verify(self, user: User, code: str) -> bool:
            return code == "123456"

    app.dependency_overrides[get_mfa_verifier] = TestFactor
    manager, pending, unaffected = TestClient(app), TestClient(app), TestClient(app)
    sign_in(manager, admin)
    sign_in(pending, staff)
    sign_in(unaffected, other)
    token = pending.cookies.get("happy_mfa_challenge")
    assert token
    assert pending.get("/api/v1/auth/me").status_code == 401
    payload = (
        {"password": "Synthetic replacement password 456"}
        if change == "password"
        else {"is_active": False}
    )
    changed = manager.patch(
        f"/api/v1/users/{staff.id}",
        json={"version": 1, **payload},
        headers=headers(manager),
    )
    assert changed.status_code == 200, changed.text
    if change == "deactivation":
        # Reactivation must not resurrect a previously password-validated challenge.
        assert (
            manager.patch(
                f"/api/v1/users/{staff.id}",
                json={"version": 2, "is_active": True},
                headers=headers(manager),
            ).status_code
            == 200
        )
    denied = pending.post("/api/v1/auth/mfa/verify", json={"code": "123456"}, headers=ORIGIN)
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "MFA_CHALLENGE_EXPIRED"
    challenge = db.get(MfaChallenge, digest(token))
    assert challenge and challenge.consumed
    assert pending.get("/api/v1/auth/me").status_code == 401
    assert not db.scalar(select(AuthSession.id).where(AuthSession.user_id == staff.id))
    assert (
        unaffected.post(
            "/api/v1/auth/mfa/verify", json={"code": "123456"}, headers=ORIGIN
        ).status_code
        == 200
    )
    assert unaffected.get("/api/v1/auth/me").status_code == 200
    fresh_password = payload.get("password", PASSWORD)
    assert pending.post(
        "/api/v1/auth/login",
        json={"email": staff.email, "password": fresh_password},
        headers=ORIGIN,
    ).json() == {"mfa_required": True}
    assert (
        pending.post("/api/v1/auth/mfa/verify", json={"code": "123456"}, headers=ORIGIN).status_code
        == 200
    )


def test_pending_mfa_cannot_race_account_revocation() -> None:
    schema, url = create_test_schema()
    engine = create_engine(url)
    original_overrides = app.dependency_overrides.copy()
    original_origins = settings.api_cors_origins
    verification_waiting = Event()

    def request_db():
        with Session(engine.execution_options(iam_verify_test=True)) as session:
            yield session

    class TestFactor:
        available = True

        def verify(self, user: User, code: str) -> bool:
            return code == "123456"

    def observe_lock(connection, cursor, statement, parameters, context, executemany):
        if (
            context.execution_options.get("iam_verify_test")
            and "FROM users" in statement
            and "FOR UPDATE" in statement
        ):
            verification_waiting.set()

    try:
        settings.api_cors_origins = ["http://localhost:3000"]
        app.dependency_overrides[get_db] = request_db
        app.dependency_overrides[get_mfa_verifier] = TestFactor
        with Session(engine, expire_on_commit=False) as seed:
            staff = account(seed, "SUPPLY")
            staff.mfa_enabled = True
            seed.commit()
        client = TestClient(app)
        sign_in(client, staff)
        event.listen(engine, "before_cursor_execute", observe_lock)
        # Two real PostgreSQL transactions reproduce verification waiting on an account change.
        with ThreadPoolExecutor(max_workers=1) as pool:
            with Session(engine) as reset:
                target = reset.scalar(select(User).where(User.id == staff.id).with_for_update())
                assert target
                reset.execute(text("SET LOCAL lock_timeout = '5s'"))
                result = pool.submit(
                    client.post,
                    "/api/v1/auth/mfa/verify",
                    json={"code": "123456"},
                    headers=ORIGIN,
                )
                assert verification_waiting.wait(5), "Verification did not reach the user lock."
                target.password_hash = hasher.hash("Synthetic replacement password 456")
                revoke_all(reset, target)
                reset.commit()
            response = result.result(timeout=10)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "MFA_CHALLENGE_EXPIRED"
        assert client.get("/api/v1/auth/me").status_code == 401
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        settings.api_cors_origins = original_origins
        engine.dispose()
        drop_test_schema(schema)


def test_audit_is_append_only_in_postgresql(db: Session) -> None:
    user = account(db)
    sign_in(TestClient(app), user)
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(
            text("UPDATE audit_events SET result='TAMPERED' WHERE actor_id=:id"),
            {"id": str(user.id)},
        )


@pytest.mark.parametrize(
    "code", ["DEMAND", "SUPPLY", "MATCHING", "MERL", "MARKETING", "MANAGEMENT", "ADMIN"]
)
def test_seeded_roles_produce_server_side_workspaces(db: Session, code: str) -> None:
    user = account(db, code)
    client = TestClient(app)
    sign_in(client, user)
    result = client.get("/api/v1/auth/me").json()
    assert [row["code"] for row in result["workspaces"]] == (
        ["DEMAND", "SUPPLY", "MATCHING", "MERL", "MARKETING", "MANAGEMENT"]
        if code == "ADMIN"
        else [code]
    )
    for endpoint in ("/users", "/roles", "/permissions", "/audit-events"):
        assert client.get("/api/v1" + endpoint).status_code == (200 if code == "ADMIN" else 403)


def test_ip_throttle_limits_password_spraying(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_ip_limit", 2)
    client = TestClient(app)
    for index in range(2):
        result = client.post(
            "/api/v1/auth/login",
            json={"email": f"unknown-{index}@example.org", "password": "wrong"},
            headers=ORIGIN,
        )
        assert result.status_code == 401
    user = account(db)
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}, headers=ORIGIN
        ).status_code
        == 429
    )


def test_cookie_rotation_and_csrf_binding(db: Session) -> None:
    user = account(db)
    client = TestClient(app)
    sign_in(client, user)
    old_token, old_csrf = client.cookies.get("happy_session"), client.cookies.get("happy_csrf")
    sign_in(client, user)
    assert client.cookies.get("happy_session") != old_token
    assert (
        client.post("/api/v1/auth/logout", headers={**ORIGIN, "X-CSRF-Token": old_csrf}).status_code
        == 403
    )
    old = TestClient(app)
    old.cookies.set("happy_session", old_token)
    assert old.get("/api/v1/auth/me").status_code == 401


def test_admin_permissions_overrides_can_change_effect(db: Session) -> None:
    admin, staff = account(db), account(db, "SUPPLY")
    client = TestClient(app)
    sign_in(client, admin)
    for version, effect in ((1, "ALLOW"), (2, "DENY"), (3, "ALLOW")):
        result = client.patch(
            f"/api/v1/users/{staff.id}",
            json={
                "version": version,
                "overrides": [{"code": "workspace_marketing:view", "effect": effect}],
            },
            headers=headers(client),
        )
        assert result.status_code == 200, result.text
        assert result.json()["overrides"] == [
            {"code": "workspace_marketing:view", "effect": effect}
        ]


def test_role_management_pagination_and_protected_admin(db: Session) -> None:
    user = account(db)
    client = TestClient(app)
    sign_in(client, user)
    role = client.post(
        "/api/v1/roles",
        json={
            "code": "CUSTOM_" + uuid4().hex[:12].upper(),
            "name": "Synthetic Reviewer",
            "permission_codes": ["workspace_management:view"],
        },
        headers=headers(client),
    )
    assert role.status_code == 201
    row = role.json()
    updated = client.patch(
        "/api/v1/roles/" + row["id"],
        json={"version": 1, "permission_codes": ["workspace_marketing:view"]},
        headers=headers(client),
    )
    assert updated.status_code == 200
    assert (
        client.patch(
            "/api/v1/roles/" + row["id"],
            json={"version": 1, "name": "Stale"},
            headers=headers(client),
        ).status_code
        == 409
    )
    admin_role = db.scalar(select(Role).where(Role.code == "ADMIN"))
    assert admin_role
    assert (
        client.patch(
            f"/api/v1/roles/{admin_role.id}",
            json={"version": 1, "permission_codes": []},
            headers=headers(client),
        ).status_code
        == 409
    )
    first = client.get("/api/v1/permissions?limit=1").json()
    second = client.get(
        "/api/v1/permissions", params={"limit": 1, "cursor": first["next_cursor"]}
    ).json()
    assert len(first["items"]) == len(second["items"]) == 1
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert client.get("/api/v1/roles?cursor=invalid").status_code == 422


def test_staging_session_cookies_are_secure(db: Session, monkeypatch) -> None:
    user = account(db)
    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "api_cors_origins", ["https://happy-staging.example.org"])
    client = TestClient(app, base_url="https://happy-staging.example.org")
    result = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": PASSWORD},
        headers={"Origin": "https://happy-staging.example.org"},
    )
    assert result.status_code == 200
    assert all(
        "Secure" in cookie
        for cookie in result.headers.get_list("set-cookie")
        if "Max-Age" in cookie
    )
    assert client.get("/api/v1/auth/me").status_code == 200
