"""Shared async test database fixtures (SQLite local, Postgres in CI)."""

from __future__ import annotations

import os

# Override .env proxy so httpx.AsyncClient init succeeds in tests (httpx 0.28+ uses `proxy`).
os.environ["HTTP_PROXY"] = ""
os.environ["http_proxy"] = ""
# Ensure startup health check skips OpenRouter during tests.
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["GAPGPT_API_KEY"] = ""
# Required for fail-fast SECRET_KEY validation and doctor seed used by legacy tests.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("SEED_DOCTOR_PASSWORD", "0808")
os.environ.setdefault("SEED_DOCTOR_USERNAME", "bagherzade")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_HEALTH_CHECK", "true")
os.environ.setdefault("MFA_ENABLED", "false")
os.environ.setdefault("RERANKER_ENABLED", "false")

from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.api.files as files_api_module
import app.db.database as database_module
import app.db.init_db as init_db_module
import app.services.file_processor as file_processor_module
import app.services.storage_service as storage_service_module
from app.core import config as config_module
from app.db.database import Base, get_db
from app.main import app as fastapi_app
from app.models import *  # noqa: F401,F403

# Ensure fail-fast / seed settings match the env we set above (pydantic may
# also read a local .env; keep tests deterministic).
config_module.settings.secret_key = os.environ["SECRET_KEY"]
config_module.settings.seed_doctor_password = os.environ["SEED_DOCTOR_PASSWORD"]
config_module.settings.seed_doctor_username = os.environ["SEED_DOCTOR_USERNAME"]
config_module.settings.app_env = os.environ.get("APP_ENV", "test")
config_module.settings.skip_health_check = True
config_module.settings.single_doctor_mode = False
if hasattr(config_module.settings, "mfa_enabled"):
    config_module.settings.mfa_enabled = False
if hasattr(config_module.settings, "reranker_enabled"):
    config_module.settings.reranker_enabled = False


def _test_database_url() -> str | None:
    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    return url or None


class FakeStorageService:
    """In-memory S3 stand-in for tests."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def upload_file(self, key: str, content: bytes, content_type: str) -> None:
        self._store[key] = content

    async def download_file(self, key: str) -> bytes:
        if key not in self._store:
            raise KeyError(key)
        return self._store[key]

    async def delete_file(self, key: str) -> None:
        self._store.pop(key, None)

    async def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return f"https://fake-storage.example/{key}?expires={expires_in}"


def patch_fake_storage(monkeypatch) -> FakeStorageService:
    fake = FakeStorageService()
    monkeypatch.setattr(storage_service_module, "storage_service", fake)
    monkeypatch.setattr(file_processor_module, "storage_service", fake)
    monkeypatch.setattr(files_api_module, "storage_service", fake)
    file_processor_module.file_processor._storage = fake
    return fake


async def _truncate_all_tables(engine) -> None:
    table_names = [t.name for t in Base.metadata.sorted_tables]
    if not table_names:
        return
    quoted = ", ".join(f'"{name}"' for name in table_names)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE"))


async def setup_async_test_db(tmp_path, monkeypatch) -> create_async_engine:
    test_url = _test_database_url()
    if test_url:
        engine = create_async_engine(test_url, pool_pre_ping=True)
        await _truncate_all_tables(engine)
    else:
        db_path = tmp_path / "test.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(init_db_module, "engine", engine)
    patch_fake_storage(monkeypatch)

    # Seed default doctor so login tests that use SEED_DOCTOR_* still work
    # without the removed hardcoded auto-provision path.
    await init_db_module._seed_default_doctor()

    from app.core.rate_limiter import rate_limiter
    from app.services.llm_circuit_breaker import tier1_circuit_breaker

    rate_limiter.reset()
    tier1_circuit_breaker.reset()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    return engine


def teardown_test_db() -> None:
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def client(tmp_path, monkeypatch):
    import asyncio

    async def _setup():
        return await setup_async_test_db(tmp_path, monkeypatch)

    engine = asyncio.run(_setup())
    with TestClient(fastapi_app) as c:
        yield c
    teardown_test_db()
    asyncio.run(engine.dispose())


@pytest.fixture
async def test_db_engine(tmp_path, monkeypatch):
    engine = await setup_async_test_db(tmp_path, monkeypatch)
    yield engine
    teardown_test_db()
    await engine.dispose()


@pytest.fixture
async def async_client(test_db_engine):
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db(test_db_engine):
    from app.db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()
