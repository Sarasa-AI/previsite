from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.medications import get_medication_resolver
from app.auth.dependencies import get_current_user
from app.main import app
from app.modules.medications.application.resolver import MedicationResolver
from app.modules.medications.domain.models import CatalogMedication
from app.modules.medications.infrastructure.catalog import CatalogUnavailableError
from app.schemas.intake import CurrentMedication, MedicalOverview
from app.services.medical_overview_service import overview_for_storage


class QueryCatalog:
    def search(self, query: str, limit: int = 20) -> tuple[CatalogMedication, ...]:
        medication = CatalogMedication(
            id=101,
            brand_name_fa="گلوکوفاژ",
            brand_name_en="Glucophage",
            generic_name_en="Metformin",
            form="TAB",
            strength="500 mg",
            manufacturer="Merck",
        )
        return (medication,)[:limit]


class UnavailableCatalog:
    def search(self, query: str, limit: int = 20) -> tuple[CatalogMedication, ...]:
        raise CatalogUnavailableError("Real Darooyab catalog is unavailable")


def _override_dependencies(resolver: MedicationResolver) -> None:
    app.dependency_overrides[get_current_user] = lambda: object()
    app.dependency_overrides[get_medication_resolver] = lambda: resolver


def teardown_function() -> None:
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_manual_search_uses_resolver_for_english_and_persian_results() -> None:
    _override_dependencies(MedicationResolver(QueryCatalog()))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        english = await client.get("/api/medications/search", params={"query": "Metformin"})
        persian = await client.get("/api/medications/search", params={"query": "متفورمین"})

        assert english.status_code == 200
        assert english.json()["results"][0] == {
            "id": 101,
            "catalog_id": 101,
            "display_name": "Glucophage",
            "brand_name": "Glucophage",
            "brand_name_fa": "گلوکوفاژ",
            "brand_name_en": "Glucophage",
            "generic_name": "Metformin",
            "generic_name_en": "Metformin",
            "generic_slug": None,
            "brand_slug": None,
            "form": "TAB",
            "strength": "500 mg",
            "manufacturer": "Merck",
            "company_name": None,
            "company_slug": None,
            "dose_unit": "قرص",
        }
        assert persian.status_code == 200
        assert persian.json()["results"][0]["display_name"] == "گلوکوفاژ"


@pytest.mark.asyncio
async def test_manual_search_fails_explicitly_when_real_catalog_is_unavailable() -> None:
    _override_dependencies(MedicationResolver(UnavailableCatalog()))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/medications/search", params={"query": "metformin"})

        assert response.status_code == 503
        assert response.json()["detail"] == (
            "MEDICATION_CATALOG_UNAVAILABLE: Real Darooyab catalog is unavailable"
        )


def test_canonical_catalog_identity_and_dose_unit_survive_medication_storage() -> None:
    overview = MedicalOverview(
        current_medications=[
            CurrentMedication(
                id="med-101",
                catalog_id=101,
                name="Glucophage",
                amount="۱ قرص",
                frequency="روزی ۱ بار",
                dose_unit="قرص",
            )
        ]
    )

    stored = overview_for_storage(overview)

    assert stored["current_medications"] == [
        {
            "id": "med-101",
            "catalog_id": 101,
            "name": "Glucophage",
            "amount": "۱ قرص",
            "frequency": "روزی ۱ بار",
            "dose_unit": "قرص",
        }
    ]
