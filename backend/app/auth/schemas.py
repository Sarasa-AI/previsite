from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.user import UserRole
from app.utils.national_id import validate_iranian_national_id


class UserRegister(BaseModel):
    """Legacy password registration — disabled at the route layer (use OTP)."""

    national_id: str = Field(..., min_length=10, max_length=10)
    password: str = Field(..., min_length=8)
    display_name: Optional[str] = Field(default=None, min_length=2)

    model_config = ConfigDict(extra="ignore")

    @field_validator("national_id")
    @classmethod
    def validate_national_id(cls, value: str) -> str:
        normalized = value.strip()
        if not validate_iranian_national_id(normalized):
            raise ValueError("INVALID_NATIONAL_ID")
        return normalized


class UserLogin(BaseModel):
    """Privileged login uses email; legacy patient login uses national_id.

    Accepts either ``email`` or ``national_id`` (legacy field name). Full-name
    login is not supported.
    """

    email: Optional[str] = Field(default=None, min_length=1)
    national_id: Optional[str] = Field(default=None, min_length=1)
    password: str

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def require_identity(self) -> "UserLogin":
        if not (self.email or "").strip() and not (self.national_id or "").strip():
            raise ValueError("email or national_id required")
        return self


class OtpRequestBody(BaseModel):
    phone: str = Field(..., min_length=8, max_length=20)
    link_token: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class OtpVerifyBody(BaseModel):
    phone: str = Field(..., min_length=8, max_length=20)
    code: str = Field(..., min_length=6, max_length=6)
    link_token: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class OtpRequestResponse(BaseModel):
    success: bool = True
    cooldown_seconds: int
    expires_in: int


class Token(BaseModel):
    access_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    # Opaque refresh token for BFF httpOnly cookie only — never expose to JS.
    refresh_token: Optional[str] = None
    refresh_expires_in: Optional[int] = None
    mfa_required: bool = False
    mfa_setup_required: bool = False
    mfa_token: Optional[str] = None
    setup_token: Optional[str] = None
    otpauth_uri: Optional[str] = None
    # Legacy patient must attach a verified mobile via OTP before session issue.
    phone_link_required: bool = False
    link_token: Optional[str] = None
    code: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=16)


class MfaSetupVerifyRequest(BaseModel):
    setup_token: str
    code: str = Field(..., min_length=6, max_length=8)


class MfaVerifyRequest(BaseModel):
    mfa_token: str
    code: str = Field(..., min_length=6, max_length=16)


class MfaSetupVerifyResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    refresh_expires_in: int
    backup_codes: list[str]


class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    national_id: Optional[str] = None
    phone: Optional[str] = None
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CurrentUserResponse(BaseModel):
    """Minimal non-sensitive identity for authenticated clients."""

    id: int
    role: UserRole
    display_name: str

    model_config = ConfigDict(from_attributes=True)
