import os
import uuid
from pathlib import Path
from fastapi import UploadFile, HTTPException
from app.core.config import settings


class FileService:
    
    def __init__(self):
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(exist_ok=True)
    
    async def save_file(
        self, 
        file: UploadFile, 
        session_id: int
    ) -> dict:
        """ذخیره فایل و برگرداندن اطلاعات آن"""
        
        # بررسی پسوند
        file_ext = file.filename.split(".")[-1].lower()
        if file_ext not in settings.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"فرمت فایل مجاز نیست. فرمت‌های مجاز: {settings.allowed_extensions}"
            )
        
        # بررسی حجم
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > settings.max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"حجم فایل بیش از حد مجاز است (حداکثر {settings.max_file_size / 1024 / 1024}MB)"
            )
        
        # ساخت نام یونیک
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        
        # ساخت پوشه session
        session_dir = self.upload_dir / str(session_id)
        session_dir.mkdir(exist_ok=True)
        
        # ذخیره فایل
        file_path = session_dir / unique_filename
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        return {
            "filename": file.filename,
            "stored_filename": unique_filename,
            "file_path": str(file_path),
            "file_size": file_size,
            "mime_type": file.content_type
        }
    
    def get_file_path(self, session_id: int, filename: str) -> Path:
        """دریافت مسیر فایل"""
        return self.upload_dir / str(session_id) / filename
    
    def delete_file(self, file_path: str):
        """حذف فایل"""
        try:
            Path(file_path).unlink()
        except:
            pass


file_service = FileService()
