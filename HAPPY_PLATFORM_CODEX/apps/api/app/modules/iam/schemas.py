from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

Password = Annotated[SecretStr, Field(min_length=12, max_length=128)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Input):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)


class MfaVerify(Input):
    code: SecretStr = Field(min_length=1, max_length=128)


class MfaConfirm(MfaVerify):
    password: SecretStr = Field(min_length=1, max_length=128)


class PasswordConfirm(Input):
    password: SecretStr = Field(min_length=1, max_length=128)


class OverrideInput(Input):
    code: str
    effect: Literal["ALLOW", "DENY"]


class UserCreate(Input):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=150)
    password: Password
    role_ids: list[UUID] = Field(default_factory=list, max_length=20)
    primary_role_id: UUID | None = None


class UserPatch(Input):
    version: int = Field(ge=1)
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    is_active: bool | None = None
    password: Password | None = None
    role_ids: list[UUID] | None = Field(default=None, max_length=20)
    primary_role_id: UUID | None = None
    overrides: list[OverrideInput] | None = Field(default=None, max_length=100)


class RoleCreate(Input):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,39}$")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    permission_codes: list[str] = Field(default_factory=list, max_length=200)


class RolePatch(Input):
    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    permission_codes: list[str] | None = Field(default=None, max_length=200)


class RoleView(BaseModel):
    id: UUID
    code: str
    name: str
    description: str
    is_system_role: bool
    version: int
    permission_codes: list[str]


class UserView(BaseModel):
    id: UUID
    email: str
    full_name: str
    is_active: bool
    mfa_enabled: bool
    primary_role_id: UUID | None
    roles: list[RoleView]
    version: int
    last_login_at: datetime | None
    overrides: list[OverrideInput]


class WorkspaceView(BaseModel):
    code: str
    name: str


class MeView(UserView):
    permissions: list[str]
    workspaces: list[WorkspaceView]


class SessionView(BaseModel):
    id: UUID
    device_label: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    current: bool
