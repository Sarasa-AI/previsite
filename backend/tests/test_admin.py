import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.security import create_access_token, get_password_hash
from app.main import app as fastapi_app
from app.models.drug import BrandDrug, GenericDrug
from app.models.user import User, UserRole
from app.services.drug_matcher import drug_matcher
from tests.test_api_integration import _auth_headers, _national_id_from_seed


async def _login_patient(
    client: AsyncClient,
    *,
    seed: str,
    password: str = "VeryStrongPassword123!",
) -> str:
    from tests.auth_helpers import register_and_login_async

    return await register_and_login_async(client, password=password, seed=seed)


async def _create_admin(db, *, email: str, full_name: str, password: str) -> User:
    admin = User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=full_name,
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin


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

    admin = await _create_admin(
        db,
        email="admin-cache@test.com",
        full_name="admin_cache",
        password="VeryStrongPassword123!",
    )
    admin_token = create_access_token(
        data={"sub": str(admin.id), "email": admin.email}
    )

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        patient_token = await _login_patient(
            client,
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
