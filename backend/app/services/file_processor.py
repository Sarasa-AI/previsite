import base64
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import TYPE_CHECKING

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader

from app.core.config import settings

if TYPE_CHECKING:
    from app.services.storage_service import StorageService


class FileProcessor:
    def __init__(self, storage: "StorageService") -> None:
        self._storage = storage
        self.supported_image_formats = ["jpg", "jpeg", "png"]
        self.supported_doc_formats = ["pdf"]

    def get_file_type(self, filename: str) -> str:
        ext = filename.split(".")[-1].lower()

        if ext in self.supported_image_formats:
            return "image"
        if ext in self.supported_doc_formats:
            return "document"
        return "unknown"

    def extract_text_from_pdf(self, data: bytes) -> str:
        try:
            reader = PdfReader(BytesIO(data))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as exc:
            return f"خطا در خواندن PDF: {str(exc)}"

    def encode_image_to_base64(self, data: bytes) -> str:
        try:
            return base64.b64encode(data).decode("utf-8")
        except Exception as exc:
            raise Exception(f"خطا در خواندن عکس: {str(exc)}") from exc

    async def process_file(self, s3_key: str, filename: str) -> dict:
        data = await self._storage.download_file(s3_key)
        file_type = self.get_file_type(filename)

        if file_type == "image":
            return {
                "type": "image",
                "content": self.encode_image_to_base64(data),
                "mime_type": f"image/{filename.split('.')[-1].lower()}",
            }

        if file_type == "document":
            return {
                "type": "text",
                "content": self.extract_text_from_pdf(data),
            }

        return {"type": "unknown", "content": None}

    def _sanitize_filename(self, filename: str) -> str:
        basename = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        sanitized = re.sub(r"[^\w.\-]", "_", basename)
        return sanitized or "upload"

    def _build_s3_key(self, session_id: int, filename: str) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        safe_name = self._sanitize_filename(filename)
        return f"{session_id}/{timestamp}_{safe_name}"

    async def save_file(self, file: UploadFile, session_id: int) -> dict:
        if not file.filename or "." not in file.filename:
            raise HTTPException(status_code=400, detail="فرمت فایل مجاز نیست.")

        file_ext = file.filename.rsplit(".", 1)[-1].lower()
        if file_ext not in settings.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"فرمت فایل مجاز نیست. فرمت‌های مجاز: {settings.allowed_extensions}",
            )

        content = await file.read()
        file_size = len(content)

        if file_size > settings.max_file_size:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"حجم فایل بیش از حد مجاز است "
                    f"(حداکثر {settings.max_file_size / 1024 / 1024}MB)"
                ),
            )

        content_type = file.content_type or "application/octet-stream"
        s3_key = self._build_s3_key(session_id, file.filename)
        await self._storage.upload_file(s3_key, content, content_type)

        return {
            "filename": file.filename,
            "s3_key": s3_key,
            "file_size": file_size,
            "mime_type": content_type,
            "file_path": s3_key,
            "content": content,
        }

    async def delete_file(self, s3_key: str) -> None:
        await self._storage.delete_file(s3_key)


from app.services.storage_service import storage_service

file_processor = FileProcessor(storage_service)
