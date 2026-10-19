import secrets
from typing import Annotated

from fastapi import Depends, Request

from app.core.config import settings
from app.core.errors import ApiError
from app.modules.iam.actors import AuditActor
from app.modules.iam.security import digest


class EmployerPortalIdentity:
    permissions = {"employer_submission:create"}
    audit_actor = AuditActor("INTEGRATION", "EMPLOYER_PORTAL")


def authenticated(request: Request) -> EmployerPortalIdentity:
    configured = settings.employer_portal_integration_token.get_secret_value()
    header = request.headers.get("Authorization", "")
    supplied = header[7:] if header.startswith("Bearer ") else ""
    if (
        not configured
        or not supplied
        or not secrets.compare_digest(digest(supplied), digest(configured))
    ):
        raise ApiError(
            401,
            "INTEGRATION_AUTHENTICATION_REQUIRED",
            "Valid integration credentials are required.",
        )
    return EmployerPortalIdentity()


EmployerPortalActor = Annotated[EmployerPortalIdentity, Depends(authenticated)]
