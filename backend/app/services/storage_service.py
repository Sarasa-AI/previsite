import asyncio
import logging
from pathlib import Path
from typing import Any, Protocol

import aioboto3

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageBackend(Protocol):
    is_local: bool

    async def upload_file(self, key: str, content: bytes, content_type: str) -> None: ...

    async def download_file(self, key: str) -> bytes: ...

    async def delete_file(self, key: str) -> None: ...

    async def get_presigned_url(self, key: str, expires_in: int = 3600) -> str: ...


class LocalStorageService:
    """Filesystem storage for local development (UPLOAD_DIR)."""

    is_local = True

    def __init__(self, base_dir: str) -> None:
        self._base_dir = Path(base_dir).resolve()
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._base_dir / key

    async def upload_file(self, key: str, content: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, content)

    async def download_file(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return await asyncio.to_thread(path.read_bytes)

    async def delete_file(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            await asyncio.to_thread(path.unlink)

    async def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        raise NotImplementedError("Local storage serves files via the download API route")


class S3StorageService:
    is_local = False

    def __init__(self) -> None:
        self._session = aioboto3.Session()

    def _client_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "service_name": "s3",
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
            "use_ssl": settings.s3_use_ssl,
        }
        if settings.s3_endpoint:
            kwargs["endpoint_url"] = settings.s3_endpoint
        return kwargs

    async def upload_file(self, key: str, content: bytes, content_type: str) -> None:
        async with self._session.client(**self._client_kwargs()) as client:
            await client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=key,
                Body=content,
                ContentType=content_type,
            )

    async def download_file(self, key: str) -> bytes:
        async with self._session.client(**self._client_kwargs()) as client:
            response = await client.get_object(
                Bucket=settings.s3_bucket_name,
                Key=key,
            )
            async with response["Body"] as stream:
                return await stream.read()

    async def delete_file(self, key: str) -> None:
        async with self._session.client(**self._client_kwargs()) as client:
            await client.delete_object(
                Bucket=settings.s3_bucket_name,
                Key=key,
            )

    async def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        async with self._session.client(**self._client_kwargs()) as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.s3_bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )


def create_storage_service() -> StorageBackend:
    if settings.upload_dir:
        resolved = Path(settings.upload_dir).resolve()
        logger.info("Using local file storage at %s", resolved)
        return LocalStorageService(settings.upload_dir)
    logger.info("Using S3 storage at %s", settings.s3_endpoint)
    return S3StorageService()


storage_service = create_storage_service()
