from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_admin
from app.db.database import get_db
from app.models import User
from app.services.drug_matcher import drug_matcher

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/refresh-drug-cache")
async def refresh_drug_cache(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_admin),
) -> dict:
    await drug_matcher.refresh_cache(db)
    return {"status": "ok", "entry_count": len(drug_matcher._entries)}
