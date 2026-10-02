"""Best-effort audit logging helpers."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

# Fixed action names — never put clinical free text in any audit field.
AUDIT_SESSION_ACCESS_DENIED = "session_access_denied"
AUDIT_INTAKE_READ = "intake_read"
AUDIT_INTAKE_WRITE = "intake_write"
AUDIT_FILE_UPLOAD = "file_upload"
AUDIT_FILE_DOWNLOAD = "file_download"
AUDIT_FILE_LIST = "file_list"
AUDIT_OCR_READ = "ocr_read"
AUDIT_PDF_EXPORT = "pdf_export"
AUDIT_PMH_OVERVIEW_READ = "pmh_overview_read"
AUDIT_PMH_WRITE = "pmh_write"
AUDIT_PROFILE_READ_OTHER = "profile_read_other"
AUDIT_ADMIN_CLINICAL_READ = "admin_clinical_read"
AUDIT_CONSENT_GRANT = "consent_grant"
AUDIT_CONSENT_WITHDRAW = "consent_withdraw"
AUDIT_CONSENT_PATIENT_READ = "consent_patient_read"
AUDIT_PRIVACY_EXPORT_REQUEST = "privacy_export_request"
AUDIT_PRIVACY_EXPORT_DOWNLOAD = "privacy_export_download"
AUDIT_PRIVACY_DELETION_REQUEST = "privacy_deletion_request"
AUDIT_PRIVACY_DELETION_CANCEL = "privacy_deletion_cancel"
AUDIT_PRIVACY_DELETION_APPROVE = "privacy_deletion_approve"
AUDIT_PRIVACY_DELETION_EXECUTE = "privacy_deletion_execute"
AUDIT_DOCTOR_VERIFIED = "doctor_verified"
AUDIT_DOCTOR_SUSPENDED = "doctor_suspended"
AUDIT_DOCTOR_REINSTATED = "doctor_reinstated"
AUDIT_MFA_RESET_BY_ADMIN = "mfa_reset_by_admin"
AUDIT_MFA_BACKUP_CODES_REGENERATED = "mfa_backup_codes_regenerated"


async def record_audit(
    db: AsyncSession,
    *,
    action: str,
    user_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str | int] = None,
    ip_address: Optional[str] = None,
    previous_value: Optional[str] = None,
) -> None:
    """Persist an audit row; never raise to the caller (fail-soft)."""
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            ip_address=ip_address,
            previous_value=previous_value,
        )
        db.add(entry)
        await db.commit()
    except Exception:
        logger.exception("Failed to write audit log action=%s", action)
        try:
            await db.rollback()
        except Exception:
            logger.exception("Failed to rollback after audit log error")


def client_ip_from_request(request) -> str | None:
    """Extract client IP without capturing request body or clinical content."""
    if request is None:
        return None
    client = getattr(request, "client", None)
    return client.host if client else None


async def record_request_audit(
    db: AsyncSession,
    *,
    action: str,
    user_id: Optional[int],
    resource_type: Optional[str],
    resource_id: Optional[str | int],
    request=None,
    previous_value: Optional[str] = None,
) -> None:
    """Shared helper for route-level audit events (no clinical free text)."""
    await record_audit(
        db,
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=client_ip_from_request(request),
        previous_value=previous_value,
    )
