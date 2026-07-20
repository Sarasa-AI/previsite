import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app as fastapi_app
from app.models.drug import BrandDrug, GenericDrug
from app.services.drug_matcher import drug_matcher
from tests.test_api_integration import _auth_headers, _national_id_from_seed


async def _register_and_login(
    client: AsyncClient,
    *,
    role: str,
    seed: str,
    password: str = "VeryStrongPassword123!",
) -> str:
    national_id = _national_id_from_seed(seed)
    register = await client.post(
        "/api/auth/register",
        json={
            "national_id": national_id,
            "password": password,
            "role": role,
        },
    )
    assert register.status_code == 200, register.text

    login = await client.post(
        "/api/auth/login",
        json={"national_id": national_id, "password": password},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


async def _seed_metfortex(db) -> None:
    generic = GenericDrug(generic_name="Metformin", category="Diabet's Drug")
    db.add(generic)
    await db.flush()
    db.add(BrandDrug(brand_name="Metfortex", generic_id=generic.id))
    await db.commit()


@pytest.mark.asyncio
async def test_admin_refresh_drug_cache_reloads_singleton(db, test_db_engine) -> None:
    drug_matcher._entries = []
    await _seed_metfortex(db)

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await _register_and_login(
            client,
            role="admin",
            seed="AdminCacheRefresh",
        )
        patient_token = await _register_and_login(
            client,
            role="patient",
            seed="PatientCacheRefresh",
        )

        assert drug_matcher.match_drug("Metfortex") is None

        refresh = await client.post(
            "/api/admin/refresh-drug-cache",
            headers=_auth_headers(admin_token),
        )
        assert refresh.status_code == 200, refresh.text
        body = refresh.json()
        assert body["status"] == "ok"
        assert body["entry_count"] > 0

        result = drug_matcher.match_drug("Metfortex")
        assert result is not None
        assert result["generic_name"] == "Metformin"

        forbidden = await client.post(
            "/api/admin/refresh-drug-cache",
            headers=_auth_headers(patient_token),
        )
        assert forbidden.status_code == 403
