from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import UserRole
from app.utils.national_id import validate_iranian_national_id


class UserRegister(BaseModel):
    national_id: str = Field(..., min_length=10, max_length=10)
    password: str = Field(..., min_length=8)
    role: UserRole = Field(default=UserRole.PATIENT)
    display_name: Optional[str] = Field(default=None, min_length=2)

    @field_validator("national_id")
    @classmethod
    def validate_national_id(cls, value: str) -> str:
        normalized = value.strip()
        if not validate_iranian_national_id(normalized):
            raise ValueError("INVALID_NATIONAL_ID")
        return normalized


class UserLogin(BaseModel):
    national_id: str = Field(..., min_length=1)
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    national_id: Optional[str] = None
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
