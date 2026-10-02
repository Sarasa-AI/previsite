from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PrivacyExportJobResponse(BaseModel):
    job_id: str
    status: str
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    download_url: Optional[str] = None
    download_expires_at: Optional[datetime] = None
    error_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DeletionRequestCreate(BaseModel):
    password: str = Field(min_length=1)


class DeletionRequestResponse(BaseModel):
    id: int
    status: str
    requested_at: Optional[datetime] = None
    cool_off_until: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
