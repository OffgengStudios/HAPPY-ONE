import base64
import binascii
import secrets
from datetime import timedelta
from typing import Any, Literal, cast
from uuid import UUID

from fastapi import Request, Response
from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.modules.iam.actors import AuditActor
from app.modules.iam.catalog import WORKSPACES, effective_permissions
from app.modules.iam.models import (
    AuditEvent,
    AuthSession,
    LoginThrottle,
    MfaChallenge,
    Permission,
    Role,
    User,
    now,
)
from app.modules.iam.schemas import MeView, OverrideInput, RoleView, UserView, WorkspaceView
from app.modules.iam.security import digest

SESSION_COOKIE = "happy_session"
CSRF_COOKIE = "happy_csrf"
CHALLENGE_COOKIE = "happy_mfa_challenge"


def permissions_for(user: User) -> set[str]:
    return effective_permissions(
        {permission.code for role in user.roles for permission in role.permissions},
        {override.permission.code: override.effect for override in user.overrides},
    )


def role_view(role: Role) -> RoleView:
    return RoleView(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_system_role=role.is_system_role,
        version=role.version,
        permission_codes=sorted(p.code for p in role.permissions),
    )


def user_view(user: User) -> UserView:
    return UserView(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        mfa_enabled=user.mfa_enabled,
        primary_role_id=user.primary_role_id,
        roles=[role_view(role) for role in user.roles],
        version=user.version,
        last_login_at=user.last_login_at,
        overrides=[
            OverrideInput(
                code=item.permission.code,
                effect=cast(Literal["ALLOW", "DENY"], item.effect),
            )
            for item in user.overrides
        ],
    )


def me_view(user: User) -> MeView:
    permissions = permissions_for(user)
    workspaces = [
        WorkspaceView(code=code, name=name)
        for code, name in WORKSPACES.items()
        if f"workspace_{code.lower()}:view" in permissions
    ]
    primary = next((role.code for role in user.roles if role.id == user.primary_role_id), None)
    workspaces.sort(key=lambda workspace: workspace.code != primary)
    return MeView(
        **user_view(user).model_dump(), permissions=sorted(permissions), workspaces=workspaces
    )


def audit(
    db: Session,
    code: str,
    actor: UUID | AuditActor | None,
    entity_type: str = "user",
    entity_id: UUID | None = None,
    request: Request | None = None,
    result: str = "SUCCESS",
    changes: dict[str, Any] | None = None,
) -> None:
    identity = (
        actor
        if isinstance(actor, AuditActor)
        else AuditActor.user(actor)
        if actor
        else AuditActor("SYSTEM")
    )
    db.add(
        AuditEvent(
            event_code=code,
            action=code,
            actor_id=identity.actor_id,
            actor_type=identity.actor_type,
            entity_type=entity_type,
            entity_id=entity_id,
            result=result,
            after_json=changes,
            metadata_json={"request_id": getattr(request.state, "request_id", None)}
            if request
            else {},
            ip_address=request.client.host if request and request.client else None,
        )
    )


def check_origin(request: Request) -> None:
    if request.headers.get("origin") not in settings.api_cors_origins:
        raise ApiError(403, "ORIGIN_FORBIDDEN", "This request origin is not permitted.")


def set_cookie(response: Response, name: str, value: str, max_age: int, httponly: bool) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=httponly,
        secure=settings.app_env in {"staging", "production"},
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def clear_cookies(response: Response) -> None:
    for name in (SESSION_COOKIE, CSRF_COOKIE, CHALLENGE_COOKIE):
        response.delete_cookie(
            name,
            path="/",
            secure=settings.app_env in {"staging", "production"},
            httponly=name != CSRF_COOKIE,
            samesite="lax",
        )
    response.headers["Cache-Control"] = "no-store"


def issue_session(
    db: Session, user: User, request: Request, response: Response, mfa_verified: bool = False
) -> None:
    old = request.cookies.get(SESSION_COOKIE)
    if old:
        db.execute(
            update(AuthSession)
            .where(AuthSession.token_hash == digest(old))
            .values(revoked_at=now())
        )
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=digest(token),
            csrf_hash=digest(csrf),
            expires_at=now() + timedelta(hours=settings.auth_session_hours),
            mfa_verified=mfa_verified,
        )
    )
    user.last_login_at = now()
    bucket = db.get(LoginThrottle, digest("account:" + user.email))
    if bucket:
        bucket.attempts = 0
    audit(db, "auth.login_success", user.id, entity_id=user.id, request=request)
    db.commit()
    seconds = settings.auth_session_hours * 3600
    set_cookie(response, SESSION_COOKIE, token, seconds, True)
    set_cookie(response, CSRF_COOKIE, csrf, seconds, False)
    response.delete_cookie(
        CHALLENGE_COOKIE,
        path="/",
        secure=settings.app_env in {"staging", "production"},
        httponly=True,
        samesite="lax",
    )


def reserve_login(db: Session, email: str, request: Request) -> bool:
    host = request.client.host if request.client else "unknown"
    allowed = True
    for key, limit in (
        (digest("account:" + email), settings.auth_login_limit),
        (digest("ip:" + host), settings.auth_ip_limit),
    ):
        db.execute(
            insert(LoginThrottle)
            .values(
                key=key,
                attempts=0,
                expires_at=now() + timedelta(minutes=settings.auth_window_minutes),
            )
            .on_conflict_do_nothing()
        )
        bucket = db.scalar(select(LoginThrottle).where(LoginThrottle.key == key).with_for_update())
        assert bucket is not None
        if bucket.expires_at <= now():
            bucket.attempts = 0
            bucket.expires_at = now() + timedelta(minutes=settings.auth_window_minutes)
        allowed = allowed and bucket.attempts < limit
        bucket.attempts += 1
    return allowed


def mutation_lock(db: Session) -> None:
    db.execute(text("SELECT pg_advisory_xact_lock(714032001)"))


def guard_last_admin(db: Session) -> None:
    db.flush()
    admins = db.scalars(select(User).where(User.is_active.is_(True))).unique().all()
    if not any({"user:manage", "role:manage"} <= permissions_for(user) for user in admins):
        raise ApiError(
            409, "LAST_ADMIN_REQUIRED", "At least one active IAM administrator must remain."
        )


def roles_by_ids(db: Session, ids: list[UUID]) -> list[Role]:
    roles = list(db.scalars(select(Role).where(Role.id.in_(set(ids)))).all())
    if len(roles) != len(set(ids)):
        raise ApiError(422, "UNKNOWN_ROLE", "One or more roles do not exist.")
    return roles


def permissions_by_codes(db: Session, codes: list[str]) -> list[Permission]:
    permissions = list(db.scalars(select(Permission).where(Permission.code.in_(set(codes)))).all())
    if len(permissions) != len(set(codes)):
        raise ApiError(422, "UNKNOWN_PERMISSION", "One or more permissions do not exist.")
    return permissions


def check_primary(user: User) -> None:
    if user.primary_role_id and user.primary_role_id not in {role.id for role in user.roles}:
        raise ApiError(
            422, "INVALID_PRIMARY_ROLE", "The primary role must be assigned to this user."
        )


def revoke_all(db: Session, user: User) -> None:
    # Account changes and MFA verification lock the user before its challenges.
    db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now())
    )
    db.execute(
        update(MfaChallenge)
        .where(MfaChallenge.user_id == user.id, MfaChallenge.consumed.is_(False))
        .values(consumed=True)
    )


def page_query(
    query: Any, model: Any, db: Session, limit: int, cursor: str | None
) -> dict[str, Any]:
    if cursor:
        try:
            identifier = UUID(bytes=base64.urlsafe_b64decode(cursor.encode()))
        except (ValueError, binascii.Error):
            raise ApiError(422, "INVALID_CURSOR", "The pagination cursor is invalid.") from None
        query = query.where(model.id > identifier)
    rows = list(db.scalars(query.order_by(model.id).limit(limit + 1)).unique().all())
    more = len(rows) > limit
    rows = rows[:limit]
    return {
        "rows": rows,
        "next_cursor": base64.urlsafe_b64encode(rows[-1].id.bytes).decode() if more else None,
    }
