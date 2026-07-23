from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_admin
from app.db.database import get_db
from app.models import User
from app.models.audit_log import AuditLog
from app.services.audit_service import record_audit
from app.services.drug_matcher import drug_matcher
from app.services.embedding_service import EmbeddingServiceError
from app.services.kb_ingest_service import (
    KbIngestValidationError,
    ingest_documents,
    parse_upload,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AuditLogItem(BaseModel):
    id: int
    user_id: Optional[int] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    timestamp: Optional[str] = None
    ip_address: Optional[str] = None
    previous_value: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


@router.post("/refresh-drug-cache")
async def refresh_drug_cache(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_admin),
) -> dict:
    await drug_matcher.refresh_cache(db)
    return {"status": "ok", "entry_count": len(drug_matcher._entries)}


@router.post("/kb/ingest")
async def ingest_kb_document(
    request: Request,
    file: UploadFile = File(...),
    document_id: Optional[str] = Form(default=None),
    title: Optional[str] = Form(default=None),
    source: Optional[str] = Form(default=None),
    published_at: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
) -> dict:
    """Ingest a curated KB document (JSON / Markdown / PDF). Admin only."""
    raw = await file.read()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    try:
        documents = parse_upload(
            filename=file.filename or "",
            content_type=file.content_type,
            raw=raw,
            document_id=document_id,
            title=title,
            source=source,
            published_at=published_at,
        )
        results = await ingest_documents(db, documents, commit=True)
    except KbIngestValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except EmbeddingServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    for item in results:
        await record_audit(
            db,
            action="kb_document_ingested",
            user_id=current_user.id,
            resource_type="medical_knowledge",
            resource_id=item.document_id,
            ip_address=request.client.host if request.client else None,
            previous_value=(
                f"title={item.title}; source={item.source}; "
                f"published_at={item.published_at}; chunks={item.chunks_inserted}"
            ),
        )

    return {
        "status": "ok",
        "documents": [
            {
                "document_id": item.document_id,
                "chunks_inserted": item.chunks_inserted,
                "title": item.title,
                "source": item.source,
                "published_at": item.published_at,
            }
            for item in results
        ],
        "documents_processed": len(results),
        "chunks_inserted": sum(item.chunks_inserted for item in results),
    }


@router.get("/audit-logs", response_model=list[AuditLogItem])
async def list_audit_logs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_admin),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AuditLogItem]:
    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        AuditLogItem(
            id=row.id,
            user_id=row.user_id,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            timestamp=row.timestamp.isoformat() if row.timestamp else None,
            ip_address=row.ip_address,
            previous_value=row.previous_value,
        )
        for row in rows
    ]
