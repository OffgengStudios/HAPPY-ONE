import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.db.session import get_db
from app.modules.iam.actors import AuditActor
from app.modules.iam.models import AuthSession, User, now
from app.modules.iam.security import digest
from app.modules.iam.service import SESSION_COOKIE, check_origin, permissions_for

Database = Annotated[Session, Depends(get_db)]


@dataclass
class Principal:
    user: User
    session: AuthSession
    permissions: set[str]

    @property
    def audit_actor(self) -> AuditActor:
        return AuditActor.user(self.user.id)


def authenticated(request: Request, db: Database) -> Principal:
    token = request.cookies.get(SESSION_COOKIE)
    session = (
        db.scalar(select(AuthSession).where(AuthSession.token_hash == digest(token)))
        if token
        else None
    )
    if (
        session is None
        or session.revoked_at
        or session.expires_at <= now()
        or session.last_seen_at + timedelta(minutes=settings.auth_idle_minutes) <= now()
    ):
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "Sign in to continue.")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "Sign in to continue.")
    if user.mfa_enabled and not session.mfa_verified:
        raise ApiError(401, "MFA_REQUIRED", "Sign in again with MFA verification.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_origin(request)
        csrf = request.headers.get("X-CSRF-Token", "")
        if not csrf or not secrets.compare_digest(digest(csrf), session.csrf_hash):
            raise ApiError(403, "CSRF_FAILED", "Refresh this page and try again.")
    session.last_seen_at = now()
    db.commit()
    return Principal(user, session, permissions_for(user))


Current = Annotated[Principal, Depends(authenticated)]


def require(permission: str, *additional: str) -> Callable[..., Principal]:
    def dependency(principal: Current) -> Principal:
        if not {permission, *additional} <= principal.permissions:
            raise ApiError(403, "PERMISSION_DENIED", "You do not have permission for this action.")
        return principal

    return dependency
