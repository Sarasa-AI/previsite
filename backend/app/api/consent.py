"""Patient consent API — grant/withdraw/list + clinician read (audited)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.session_access import (
    doctor_may_access_patient,
    is_admin,
    is_doctor,
    is_patient,
)
from app.core.config import settings
from app.db.database import get_db
from app.models.user import User
from app.privacy.consent_keys import ENFORCEMENT_REQUIRED_KEYS
from app.privacy.consent_service import (
    get_consent_status,
    grant_consent,
    list_consent_records,
    withdraw_consent,
)
from app.schemas.consent import (
    ConsentGrantRequest,
    ConsentRecordResponse,
    ConsentStatusItem,
    ConsentStatusResponse,
    ConsentWithdrawRequest,
)
from app.services.audit_service import (
    AUDIT_CONSENT_GRANT,
    AUDIT_CONSENT_PATIENT_READ,
    AUDIT_CONSENT_WITHDRAW,
    client_ip_from_request,
    record_request_audit,
)

router = APIRouter(prefix="/api/consent", tags=["consent"])


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _require_patient(user: User) -> None:
    if not is_patient(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can manage their own consents",
        )


def _status_response(statuses: list[dict]) -> ConsentStatusResponse:
    return ConsentStatusResponse(
        enforcement_enabled=bool(settings.consent_enforcement_enabled),
        required_for_processing=list(ENFORCEMENT_REQUIRED_KEYS),
        consents=[ConsentStatusItem.model_validate(s) for s in statuses],
    )


@router.get("/me", response_model=ConsentStatusResponse)
async def list_my_consents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Current consent status for the authenticated patient."""
    _require_patient(current_user)
    statuses = await get_consent_status(db, current_user.id)
    return _status_response(statuses)


@router.get("/me/history", response_model=list[ConsentRecordResponse])
async def list_my_consent_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Append-only consent ledger for the authenticated patient."""
    _require_patient(current_user)
    rows = await list_consent_records(db, current_user.id)
    return [ConsentRecordResponse.model_validate(r) for r in rows]


@router.post("/grant", response_model=ConsentRecordResponse)
async def grant_my_consent(
    data: ConsentGrantRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_patient(current_user)
    row = await grant_consent(
        db,
        user_id=current_user.id,
        consent_key=data.consent_key,
        policy_version=data.policy_version,
        ip=client_ip_from_request(request),
        user_agent=_user_agent(request),
    )
    await record_request_audit(
        db,
        action=AUDIT_CONSENT_GRANT,
        user_id=current_user.id,
        resource_type="consent",
        resource_id=row.id,
        request=request,
        previous_value=data.consent_key,
    )
    return ConsentRecordResponse.model_validate(row)


@router.post("/withdraw", response_model=ConsentRecordResponse)
async def withdraw_my_consent(
    data: ConsentWithdrawRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_patient(current_user)
    row = await withdraw_consent(
        db,
        user_id=current_user.id,
        consent_key=data.consent_key,
        ip=client_ip_from_request(request),
        user_agent=_user_agent(request),
    )
    await record_request_audit(
        db,
        action=AUDIT_CONSENT_WITHDRAW,
        user_id=current_user.id,
        resource_type="consent",
        resource_id=row.id,
        request=request,
        previous_value=data.consent_key,
    )
    return ConsentRecordResponse.model_validate(row)


@router.get("/patient/{patient_id}", response_model=ConsentStatusResponse)
async def read_patient_consents(
    patient_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Doctors/admins may read consent status for patients they are authorized on."""
    if is_patient(current_user):
        if patient_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
        statuses = await get_consent_status(db, patient_id)
        return _status_response(statuses)

    if not (is_doctor(current_user) or is_admin(current_user)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    if is_doctor(current_user) and not await doctor_may_access_patient(
        db, patient_id, current_user
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    await record_request_audit(
        db,
        action=AUDIT_CONSENT_PATIENT_READ,
        user_id=current_user.id,
        resource_type="patient",
        resource_id=patient_id,
        request=request,
    )
    statuses = await get_consent_status(db, patient_id)
    return _status_response(statuses)
