"""Manual medication search API backed by the shared resolver."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_user
from app.core.rate_limiter import medications_search_rate_limit
from app.models.user import User
from app.modules.medications.application.resolver import MedicationResolver
from app.modules.medications.infrastructure.catalog import CatalogUnavailableError
from app.modules.medications.interface.dto import (
    MedicationSearchResponseDTO,
    MedicationSearchResultDTO,
)

router = APIRouter(prefix="/api/medications", tags=["medications"])


def get_medication_resolver() -> MedicationResolver:
    try:
        return MedicationResolver()
    except CatalogUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"MEDICATION_CATALOG_UNAVAILABLE: {exc}",
        ) from exc


@router.get("/search", response_model=MedicationSearchResponseDTO)
def search_medications(
    query: str = Query(min_length=1, max_length=120),
    limit: int = Query(default=20, ge=1, le=20),
    _current_user: User = Depends(get_current_user),
    _: None = Depends(medications_search_rate_limit),
    resolver: MedicationResolver = Depends(get_medication_resolver),
) -> MedicationSearchResponseDTO:
    try:
        resolution = resolver.resolve_manual(query, limit=limit)
    except CatalogUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"MEDICATION_CATALOG_UNAVAILABLE: {exc}",
        ) from exc

    return MedicationSearchResponseDTO(
        query=resolution.normalized_query,
        results=[
            MedicationSearchResultDTO.from_resolved(medication)
            for medication in resolution.medications
        ],
    )
