"""Consent API request/response schemas — structure only, no legal copy."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ConsentGrantRequest(BaseModel):
    consent_key: str = Field(..., min_length=1, max_length=64)
    # Optional override for tests / migration tooling; defaults to current version.
    policy_version: Optional[str] = Field(default=None, max_length=32)

    model_config = ConfigDict(extra="ignore")


class ConsentWithdrawRequest(BaseModel):
    consent_key: str = Field(..., min_length=1, max_length=64)

    model_config = ConfigDict(extra="ignore")


class ConsentRecordResponse(BaseModel):
    id: int
    user_id: int
    consent_key: str
    policy_version: str
    granted: bool
    granted_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ConsentStatusItem(BaseModel):
    consent_key: str
    policy_version: str
    copy_text_key: str
    granted: bool
    granted_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None
    latest_record_id: Optional[int] = None
    latest_policy_version: Optional[str] = None


class ConsentStatusResponse(BaseModel):
    enforcement_enabled: bool
    required_for_processing: list[str]
    consents: list[ConsentStatusItem]
