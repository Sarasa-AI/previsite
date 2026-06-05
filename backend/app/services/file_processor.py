import base64
from pathlib import Path
from typing import Optional
from pypdf import PdfReader
from PIL import Image
import io

from app.core.config import settings


class FileProcessor:
    
    def __init__(self):
        self.supported_image_formats = ["jpg", "jpeg", "png"]
        self.supported_doc_formats = ["pdf"]
    
    def get_file_type(self, filename: str) -> str:
        """تشخیص نوع فایل"""
        ext = filename.split(".")[-1].lower()
        
        if ext in self.supported_image_formats:
            return "image"
        elif ext in self.supported_doc_formats:
            return "document"
        else:
            return "unknown"
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        """استخراج متن از PDF"""
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            return f"خطا در خواندن PDF: {str(e)}"
    
    def encode_image_to_base64(self, file_path: str) -> str:
        """تبدیل عکس به base64 برای ارسال به LLM"""
        try:
            with open(file_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            raise Exception(f"خطا در خواندن عکس: {str(e)}")
    
    def process_file(self, file_path: str, filename: str) -> dict:
        """پردازش فایل و آماده‌سازی برای LLM"""
        
        file_type = self.get_file_type(filename)
        
        if file_type == "image":
            return {
                "type": "image",
                "content": self.encode_image_to_base64(file_path),
                "mime_type": f"image/{filename.split('.')[-1].lower()}"
            }
        
        elif file_type == "document":
            return {
                "type": "text",
                "content": self.extract_text_from_pdf(file_path)
            }
        
        else:
            return {
                "type": "unknown",
                "content": None
            }


file_processor = FileProcessor()
