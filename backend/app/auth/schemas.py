from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole

class UserRegister(BaseModel):
    name: str = Field(..., min_length=2)
    password: str = Field(..., min_length=8)
    role: UserRole = Field(default=UserRole.PATIENT)

class UserLogin(BaseModel):
    name: str = Field(..., min_length=1)
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
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
