from typing import Any

import aioboto3

from app.core.config import settings


class StorageService:
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


storage_service = StorageService()
