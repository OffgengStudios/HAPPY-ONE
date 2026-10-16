import secrets
from datetime import timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select

from app.core.errors import ApiError
from app.modules.iam.dependencies import Current, Database, Principal, require
from app.modules.iam.models import (
    AuditEvent,
    AuthSession,
    MfaChallenge,
    Permission,
    PermissionOverride,
    Role,
    User,
    now,
)
from app.modules.iam.schemas import (
    Login,
    MeView,
    MfaConfirm,
    MfaVerify,
    PasswordConfirm,
    RoleCreate,
    RolePatch,
    RoleView,
    SessionView,
    UserCreate,
    UserPatch,
    UserView,
)
from app.modules.iam.security import (
    MfaVerifier,
    decrypt_mfa_secret,
    digest,
    encrypt_mfa_secret,
    generate_totp_secret,
    get_mfa_verifier,
    hasher,
    recovery_hash,
    verify_password,
    verify_totp,
)
from app.modules.iam.service import (
    CHALLENGE_COOKIE,
    audit,
    check_origin,
    check_primary,
    clear_cookies,
    guard_last_admin,
    issue_session,
    me_view,
    mutation_lock,
    page_query,
    permissions_by_codes,
    revoke_all,
    role_view,
    roles_by_ids,
    set_cookie,
    user_view,
)

router = APIRouter(tags=["auth", "iam"])
UsersAdmin = Annotated[Principal, Depends(require("user:manage"))]
RolesAdmin = Annotated[Principal, Depends(require("role:manage"))]
Auditor = Annotated[Principal, Depends(require("audit:view"))]
Factor = Annotated[MfaVerifier, Depends(get_mfa_verifier)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.post("/auth/login")
def login(
    data: Login, request: Request, response: Response, db: Database, factor: Factor
) -> dict[str, bool]:
    from app.modules.iam.service import reserve_login

    check_origin(request)
    email = str(data.email).lower()
    allowed = reserve_login(db, email, request)
    user = db.scalar(select(User).where(User.email == email).with_for_update())
    valid = (
        verify_password(user.password_hash if user else None, data.password.get_secret_value())
        if allowed
        else False
    )
    if not allowed or not valid or not user or not user.is_active:
        audit(
            db,
            "auth.login_failed",
            None,
            request=request,
            result="THROTTLED" if not allowed else "DENIED",
        )
        db.commit()
        raise ApiError(
            429 if not allowed else 401,
            "LOGIN_THROTTLED" if not allowed else "INVALID_CREDENTIALS",
            "Too many attempts. Try again later."
            if not allowed
            else "Email or password is incorrect.",
        )
    if hasher.check_needs_rehash(user.password_hash or ""):
        user.password_hash = hasher.hash(data.password.get_secret_value())
    if user.mfa_enabled:
        if not factor.available:
            audit(db, "auth.login_failed", user.id, request=request, result="MFA_UNAVAILABLE")
            db.commit()
            raise ApiError(
                503, "MFA_NOT_CONFIGURED", "Contact your administrator to restore MFA verification."
            )
        token = secrets.token_urlsafe(32)
        db.add(
            MfaChallenge(
                token_hash=digest(token), user_id=user.id, expires_at=now() + timedelta(minutes=5)
            )
        )
        db.commit()
        set_cookie(response, CHALLENGE_COOKIE, token, 300, True)
        return {"mfa_required": True}
    issue_session(db, user, request, response)
    return {"mfa_required": False}


@router.post("/auth/mfa/verify")
def mfa_verify(
    data: MfaVerify, request: Request, response: Response, db: Database, factor: Factor
) -> dict[str, bool]:
    check_origin(request)
    token = request.cookies.get(CHALLENGE_COOKIE, "")
    challenge = db.scalar(select(MfaChallenge).where(MfaChallenge.token_hash == digest(token)))
    if not challenge:
        raise ApiError(401, "MFA_CHALLENGE_EXPIRED", "Sign in again to request a new verification.")
    # Match account-change lock order, then re-read the challenge under lock.
    user = db.scalar(
        select(User)
        .where(User.id == challenge.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    challenge = db.scalar(
        select(MfaChallenge)
        .where(MfaChallenge.token_hash == digest(token))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        not challenge
        or challenge.consumed
        or challenge.expires_at <= now()
        or challenge.attempts >= 5
    ):
        raise ApiError(401, "MFA_CHALLENGE_EXPIRED", "Sign in again to request a new verification.")
    if not user or not user.is_active or not user.mfa_enabled:
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "Sign in again.")
    if not factor.available:
        raise ApiError(503, "MFA_NOT_CONFIGURED", "MFA verification is unavailable.")
    challenge.attempts += 1
    if not factor.verify(user, data.code.get_secret_value()):
        audit(db, "auth.login_failed", user.id, request=request, result="MFA_DENIED")
        db.commit()
        raise ApiError(401, "MFA_INVALID", "The verification code is invalid.")
    challenge.consumed = True
    issue_session(db, user, request, response, mfa_verified=True)
    return {"mfa_required": False}


@router.get("/auth/me", response_model=MeView)
def me(principal: Current, response: Response) -> MeView:
    response.headers["Cache-Control"] = "no-store"
    return me_view(principal.user)


@router.post("/auth/logout", status_code=204)
def logout(principal: Current, db: Database, request: Request, response: Response) -> None:
    principal.session.revoked_at = now()
    audit(db, "auth.logout", principal.user.id, entity_id=principal.user.id, request=request)
    db.commit()
    clear_cookies(response)


@router.get("/auth/sessions", response_model=list[SessionView])
def sessions(principal: Current, db: Database, response: Response) -> list[SessionView]:
    response.headers["Cache-Control"] = "no-store"
    rows = db.scalars(
        select(AuthSession)
        .where(
            AuthSession.user_id == principal.user.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now(),
        )
        .order_by(AuthSession.created_at.desc())
    ).all()
    return [
        SessionView(
            id=row.id,
            device_label=row.device_label,
            created_at=row.created_at,
            last_seen_at=row.last_seen_at,
            expires_at=row.expires_at,
            current=row.id == principal.session.id,
        )
        for row in rows
    ]


@router.post("/auth/mfa/enrol")
def enrol_mfa(
    data: PasswordConfirm, principal: Current, db: Database, request: Request
) -> dict[str, str]:
    if principal.user.mfa_enabled:
        raise ApiError(409, "MFA_ALREADY_ENABLED", "MFA is already enabled.")
    if not verify_password(principal.user.password_hash, data.password.get_secret_value()):
        raise ApiError(401, "INVALID_CREDENTIALS", "Password is incorrect.")
    secret = generate_totp_secret()
    principal.user.mfa_pending_secret_ciphertext = encrypt_mfa_secret(secret)
    db.commit()
    label = principal.user.email.replace(" ", "%20")
    return {
        "secret": secret,
        "otpauth_uri": f"otpauth://totp/HAPPY:{label}?secret={secret}&issuer=HAPPY&digits=6&period=30",
    }


@router.post("/auth/mfa/confirm")
def confirm_mfa(
    data: MfaConfirm, principal: Current, db: Database, request: Request
) -> dict[str, list[str]]:
    if not verify_password(principal.user.password_hash, data.password.get_secret_value()):
        raise ApiError(401, "INVALID_CREDENTIALS", "Password is incorrect.")
    pending = principal.user.mfa_pending_secret_ciphertext
    if not pending or not verify_totp(decrypt_mfa_secret(pending), data.code.get_secret_value()):
        raise ApiError(422, "MFA_INVALID", "The verification code is invalid.")
    recovery = [secrets.token_hex(5).upper() for _ in range(8)]
    principal.user.mfa_secret_ciphertext = pending
    principal.user.mfa_pending_secret_ciphertext = None
    principal.user.mfa_recovery_hashes = [recovery_hash(code) for code in recovery]
    principal.user.mfa_enabled = True
    principal.user.version += 1
    audit(db, "auth.mfa_enabled", principal.user.id, "user", principal.user.id, request)
    db.commit()
    return {"recovery_codes": recovery}


@router.post("/auth/mfa/disable", status_code=204)
def disable_mfa(data: MfaConfirm, principal: Current, db: Database, request: Request) -> None:
    if not verify_password(principal.user.password_hash, data.password.get_secret_value()):
        raise ApiError(401, "INVALID_CREDENTIALS", "Password is incorrect.")
    factor = get_mfa_verifier()
    if not principal.user.mfa_enabled or not factor.verify(
        principal.user, data.code.get_secret_value()
    ):
        raise ApiError(422, "MFA_INVALID", "The verification code is invalid.")
    principal.user.mfa_enabled = False
    principal.user.mfa_secret_ciphertext = None
    principal.user.mfa_pending_secret_ciphertext = None
    principal.user.mfa_recovery_hashes = []
    principal.user.version += 1
    audit(db, "auth.mfa_disabled", principal.user.id, "user", principal.user.id, request)
    db.commit()


@router.post("/auth/sessions/{session_id}/revoke", status_code=204)
def revoke_session(
    session_id: UUID, principal: Current, db: Database, request: Request, response: Response
) -> None:
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.id == session_id, AuthSession.user_id == principal.user.id
        )
    )
    if session is None:
        raise ApiError(404, "SESSION_NOT_FOUND", "The session does not exist.")
    session.revoked_at = now()
    audit(db, "auth.session_revoked", principal.user.id, "session", session.id, request)
    db.commit()
    if session.id == principal.session.id:
        clear_cookies(response)


@router.get("/users")
def users(
    principal: UsersAdmin,
    db: Database,
    response: Response,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    page = page_query(select(User), User, db, limit, cursor)
    return {"items": [user_view(user) for user in page["rows"]], "next_cursor": page["next_cursor"]}


@router.get("/users/{user_id}", response_model=UserView)
def user_detail(user_id: UUID, principal: UsersAdmin, db: Database, response: Response) -> UserView:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "USER_NOT_FOUND", "The account does not exist.")
    response.headers["Cache-Control"] = "no-store"
    return user_view(user)


@router.post("/users", status_code=201, response_model=UserView)
def create_user(
    data: UserCreate, principal: UsersAdmin, db: Database, request: Request
) -> UserView:
    if data.role_ids and "role:manage" not in principal.permissions:
        raise ApiError(
            403, "PERMISSION_DENIED", "Role assignments require role management permission."
        )
    mutation_lock(db)
    user = User(
        email=str(data.email).lower(),
        full_name=data.full_name,
        password_hash=hasher.hash(data.password.get_secret_value()),
        roles=roles_by_ids(db, data.role_ids),
        primary_role_id=data.primary_role_id,
        created_by=principal.user.id,
    )
    check_primary(user)
    db.add(user)
    db.flush()
    audit(db, "user.created", principal.user.id, entity_id=user.id, request=request)
    for role in user.roles:
        audit(
            db,
            "role.assigned",
            principal.user.id,
            entity_id=user.id,
            request=request,
            changes={"role_id": str(role.id)},
        )
    db.commit()
    return user_view(user)


@router.patch("/users/{user_id}", response_model=UserView)
def update_user(
    user_id: UUID, data: UserPatch, principal: UsersAdmin, db: Database, request: Request
) -> UserView:
    if (
        data.role_ids is not None or data.overrides is not None
    ) and "role:manage" not in principal.permissions:
        raise ApiError(
            403,
            "PERMISSION_DENIED",
            "Role and permission changes require role management permission.",
        )
    mutation_lock(db)
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise ApiError(404, "USER_NOT_FOUND", "The account does not exist.")
    if user.version != data.version:
        raise ApiError(409, "RECORD_VERSION_CONFLICT", "The account changed. Reload before saving.")
    if data.is_active is False and user.id == principal.user.id:
        raise ApiError(
            409, "SELF_DEACTIVATION_FORBIDDEN", "You cannot deactivate your own account."
        )
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.role_ids is not None:
        old_ids = {role.id for role in user.roles}
        user.roles = roles_by_ids(db, data.role_ids)
        new_ids = {role.id for role in user.roles}
        for role_id in old_ids ^ new_ids:
            audit(
                db,
                "role.assigned" if role_id in new_ids else "role.removed",
                principal.user.id,
                entity_id=user.id,
                request=request,
                changes={"role_id": str(role_id)},
            )
    if "primary_role_id" in data.model_fields_set:
        user.primary_role_id = data.primary_role_id
    check_primary(user)
    if data.overrides is not None:
        codes = [override.code for override in data.overrides]
        if len(set(codes)) != len(codes):
            raise ApiError(422, "DUPLICATE_OVERRIDE", "Each permission can have only one override.")
        permissions = {
            permission.code: permission for permission in permissions_by_codes(db, codes)
        }
        user.overrides = [
            PermissionOverride(permission=permissions[override.code], effect=override.effect)
            for override in data.overrides
        ]
        audit(
            db,
            "permission.override_changed",
            principal.user.id,
            entity_id=user.id,
            request=request,
            changes={"overrides": [override.model_dump() for override in data.overrides]},
        )
    if data.is_active is not None and data.is_active != user.is_active:
        user.is_active = data.is_active
        audit(
            db,
            "user.activated" if user.is_active else "user.deactivated",
            principal.user.id,
            entity_id=user.id,
            request=request,
        )
    if data.password is not None:
        user.password_hash = hasher.hash(data.password.get_secret_value())
        audit(db, "auth.password_changed", principal.user.id, entity_id=user.id, request=request)
    user.version += 1
    user.updated_by = principal.user.id
    if not user.is_active or data.password is not None:
        revoke_all(db, user)
    guard_last_admin(db)
    audit(db, "user.updated", principal.user.id, entity_id=user.id, request=request)
    db.commit()
    return user_view(user)


@router.get("/roles")
def roles(
    principal: RolesAdmin,
    db: Database,
    response: Response,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    page = page_query(select(Role), Role, db, limit, cursor)
    return {"items": [role_view(role) for role in page["rows"]], "next_cursor": page["next_cursor"]}


@router.post("/roles", status_code=201, response_model=RoleView)
def create_role(
    data: RoleCreate, principal: RolesAdmin, db: Database, request: Request
) -> RoleView:
    mutation_lock(db)
    role = Role(
        code=data.code,
        name=data.name,
        description=data.description,
        permissions=permissions_by_codes(db, data.permission_codes),
    )
    db.add(role)
    db.flush()
    audit(db, "role.created", principal.user.id, "role", role.id, request)
    db.commit()
    return role_view(role)


@router.patch("/roles/{role_id}", response_model=RoleView)
def update_role(
    role_id: UUID, data: RolePatch, principal: RolesAdmin, db: Database, request: Request
) -> RoleView:
    mutation_lock(db)
    role = db.scalar(select(Role).where(Role.id == role_id).with_for_update())
    if role is None:
        raise ApiError(404, "ROLE_NOT_FOUND", "The role does not exist.")
    if role.version != data.version:
        raise ApiError(409, "RECORD_VERSION_CONFLICT", "The role changed. Reload before saving.")
    if role.code == "ADMIN" and data.permission_codes is not None:
        raise ApiError(
            409,
            "SYSTEM_ADMIN_PROTECTED",
            "The baseline administrator permissions cannot be changed.",
        )
    if data.name is not None:
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.permission_codes is not None:
        role.permissions = permissions_by_codes(db, data.permission_codes)
    role.version += 1
    guard_last_admin(db)
    audit(
        db,
        "role.updated",
        principal.user.id,
        "role",
        role.id,
        request,
        changes={"permission_codes": sorted(permission.code for permission in role.permissions)},
    )
    db.commit()
    return role_view(role)


@router.get("/permissions")
def permission_catalog(
    principal: RolesAdmin,
    db: Database,
    response: Response,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    page = page_query(select(Permission), Permission, db, limit, cursor)
    return {
        "items": [
            {
                "id": row.id,
                "code": row.code,
                "resource": row.resource,
                "action": row.action,
                "description": row.description,
            }
            for row in page["rows"]
        ],
        "next_cursor": page["next_cursor"],
    }


def audit_view(row: AuditEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "event_code": row.event_code,
        "actor_type": row.actor_type,
        "actor_id": row.actor_id,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "result": row.result,
        "before": row.before_json,
        "after": row.after_json,
        "metadata": row.metadata_json,
        "occurred_at": row.occurred_at,
    }


@router.get("/audit-events")
def audit_events(
    principal: Auditor,
    db: Database,
    response: Response,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    page = page_query(select(AuditEvent), AuditEvent, db, limit, cursor)
    return {"items": [audit_view(row) for row in page["rows"]], "next_cursor": page["next_cursor"]}


@router.get("/audit-events/{event_id}")
def audit_detail(
    event_id: UUID, principal: Auditor, db: Database, response: Response
) -> dict[str, Any]:
    row = db.get(AuditEvent, event_id)
    if row is None:
        raise ApiError(404, "AUDIT_EVENT_NOT_FOUND", "The event does not exist.")
    response.headers["Cache-Control"] = "no-store"
    return audit_view(row)
