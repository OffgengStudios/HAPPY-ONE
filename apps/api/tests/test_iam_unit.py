from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.iam.catalog import ROLE_GRANTS, effective_permissions, project_fields
from app.modules.iam.models import Permission, Role, User
from app.modules.iam.schemas import UserCreate
from app.modules.iam.security import hasher, verify_password
from app.modules.iam.service import me_view


@pytest.mark.parametrize("code", ROLE_GRANTS)
def test_baseline_role_workspace_projection(code: str) -> None:
    role = Role(
        id=uuid4(),
        code=code,
        name=code,
        description="",
        is_system_role=True,
        version=1,
        permissions=[Permission(code=item) for item in ROLE_GRANTS[code]],
    )
    user = User(
        id=uuid4(),
        email="staff@example.org",
        full_name="Test Staff",
        is_active=True,
        mfa_enabled=False,
        primary_role_id=role.id,
        version=1,
        last_login_at=None,
        roles=[role],
        overrides=[],
    )
    projection = me_view(user)
    assert len(projection.workspaces) == (6 if code == "ADMIN" else 1)
    if code != "ADMIN":
        assert projection.workspaces[0].code == code
        assert "user:manage" not in projection.permissions
        assert "report:sensitive_export" not in projection.permissions
        assert "participant_sensitive:view" not in projection.permissions


def test_explicit_deny_wins_and_projection_omits_restricted_fields() -> None:
    allowed = effective_permissions(
        {"participant:view", "participant_sensitive:view"},
        {"participant_sensitive:view": "DENY", "vacancy:view": "ALLOW"},
    )
    assert allowed == {"participant:view", "vacancy:view"}
    assert project_fields(
        {"name": "Synthetic", "government_id": "hidden", "income": 1000},
        allowed,
        {"government_id": "participant_sensitive:view", "income": "income:view"},
    ) == {"name": "Synthetic"}


def test_password_hashes_are_salted_and_unknown_external_accounts_fail() -> None:
    password = "Synthetic password 123"
    first, second = hasher.hash(password), hasher.hash(password)
    assert first.startswith("$argon2id$")
    assert first != second
    assert verify_password(first, password)
    assert not verify_password(first, "incorrect")
    assert not verify_password(None, password)
    assert not verify_password("corrupt hash", password)


def test_mass_assignment_and_weak_password_are_rejected() -> None:
    with pytest.raises(ValidationError):
        UserCreate(email="test@example.org", full_name="Test", password="short")
    with pytest.raises(ValidationError):
        UserCreate.model_validate(
            {
                "email": "test@example.org",
                "full_name": "Test",
                "password": "Synthetic password 123",
                "is_system_role": True,
            }
        )
