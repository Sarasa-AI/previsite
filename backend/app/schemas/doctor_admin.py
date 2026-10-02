from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.user import DoctorVerificationStatus


class DoctorAdminItem(BaseModel):
    id: int
    email: str
    full_name: str
    medical_council_license: Optional[str] = None
    specialty: Optional[str] = None
    verification_status: Optional[DoctorVerificationStatus] = None
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None
    mfa_enabled: bool = False
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class MfaRegenerateResponse(BaseModel):
    backup_codes: list[str]
