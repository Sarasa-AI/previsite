"""Patient privacy — data export and account erasure requests."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.security import verify_password
from app.auth.session_access import is_patient
from app.core.rate_limiter import privacy_export_rate_limit
from app.db.database import get_db
from app.models.account_deletion_request import AccountDeletionRequest
from app.models.privacy_export_job import PrivacyExportJob, PrivacyExportJobStatus
from app.models.user import User
from app.privacy.erasure_service import (
    cancel_deletion_request,
    create_deletion_request,
)
from app.privacy.export_service import (
    create_export_job,
    get_job_for_user,
    resolve_download_url,
    run_export_job,
)
from app.schemas.privacy import (
    DeletionRequestCreate,
    DeletionRequestResponse,
    PrivacyExportJobResponse,
)
from app.services.audit_service import (
    AUDIT_PRIVACY_DELETION_CANCEL,
    AUDIT_PRIVACY_DELETION_REQUEST,
    AUDIT_PRIVACY_EXPORT_DOWNLOAD,
    AUDIT_PRIVACY_EXPORT_REQUEST,
    record_request_audit,
)
from app.services.storage_service import storage_service

router = APIRouter(prefix="/api/privacy", tags=["privacy"])


def _require_patient(user: User) -> None:
    if not is_patient(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can access privacy self-service",
        )


def _export_response(job: PrivacyExportJob, download_url: str | None) -> PrivacyExportJobResponse:
    return PrivacyExportJobResponse(
        job_id=job.public_id,
        status=job.status,
        created_at=job.created_at,
        completed_at=job.completed_at,
        download_url=download_url,
        download_expires_at=job.download_expires_at,
        error_code=job.error_code,
    )


async def _latest_deletion_request(
    db: AsyncSession, user_id: int
) -> AccountDeletionRequest | None:
    result = await db.execute(
        select(AccountDeletionRequest)
        .where(AccountDeletionRequest.user_id == user_id)
        .order_by(AccountDeletionRequest.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.post("/export", response_model=PrivacyExportJobResponse)
async def request_data_export(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(privacy_export_rate_limit),
):
    _require_patient(current_user)
    job = await create_export_job(db, current_user.id)
    await record_request_audit(
        db,
        action=AUDIT_PRIVACY_EXPORT_REQUEST,
        user_id=current_user.id,
        resource_type="privacy_export_job",
        resource_id=job.public_id,
        request=request,
    )
    background_tasks.add_task(run_export_job, job.id)
    return _export_response(job, None)


@router.get("/export/{job_id}", response_model=PrivacyExportJobResponse)
async def get_export_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_patient(current_user)
    job = await get_job_for_user(db, public_id=job_id, user_id=current_user.id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    download_url = await resolve_download_url(job)
    return _export_response(job, download_url)


@router.get("/export/{job_id}/download")
async def download_export_bundle(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_patient(current_user)
    job = await get_job_for_user(db, public_id=job_id, user_id=current_user.id)
    if job is None or job.status != PrivacyExportJobStatus.READY or not job.storage_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    from datetime import datetime, timezone

    if job.download_expires_at:
        now = datetime.now(timezone.utc)
        expires = job.download_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Export expired")

    try:
        content = await storage_service.download_file(job.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        ) from exc

    await record_request_audit(
        db,
        action=AUDIT_PRIVACY_EXPORT_DOWNLOAD,
        user_id=current_user.id,
        resource_type="privacy_export_job",
        resource_id=job.public_id,
        request=request,
    )
    filename = f"previsit-export-{job.public_id}.json"
    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/deletion-request", response_model=DeletionRequestResponse)
async def request_account_deletion(
    data: DeletionRequestCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_patient(current_user)
    if not current_user.hashed_password or not verify_password(
        data.password, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )
    row = await create_deletion_request(db, current_user.id)
    await record_request_audit(
        db,
        action=AUDIT_PRIVACY_DELETION_REQUEST,
        user_id=current_user.id,
        resource_type="account_deletion_request",
        resource_id=row.id,
        request=request,
    )
    return DeletionRequestResponse.model_validate(row)


@router.post("/deletion-request/cancel", response_model=DeletionRequestResponse)
async def cancel_account_deletion(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_patient(current_user)
    row = await cancel_deletion_request(db, current_user.id)
    await record_request_audit(
        db,
        action=AUDIT_PRIVACY_DELETION_CANCEL,
        user_id=current_user.id,
        resource_type="account_deletion_request",
        resource_id=row.id,
        request=request,
    )
    return DeletionRequestResponse.model_validate(row)


@router.get("/deletion-request", response_model=DeletionRequestResponse | None)
async def get_deletion_request_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_patient(current_user)
    row = await _latest_deletion_request(db, current_user.id)
    if row is None:
        return None
    return DeletionRequestResponse.model_validate(row)
