"""Shared async test database fixtures using sqlite+aiosqlite."""

from __future__ import annotations

import os

# Override .env proxy so httpx.AsyncClient init succeeds in tests (httpx 0.28+ uses `proxy`).
os.environ["HTTP_PROXY"] = ""
os.environ["http_proxy"] = ""
# Ensure startup health check skips OpenRouter during tests.
os.environ["OPENROUTER_API_KEY"] = ""

from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.db.database as database_module
import app.db.init_db as init_db_module
import app.api.files as files_api_module
import app.services.file_processor as file_processor_module
import app.services.storage_service as storage_service_module
from app.db.database import Base, get_db
from app.main import app as fastapi_app


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


async def setup_async_test_db(tmp_path, monkeypatch) -> create_async_engine:
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

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

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

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
