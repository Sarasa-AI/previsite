import asyncio
import base64
import hashlib
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

import aiofiles
import httpx
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, field_validator
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings

# تنظیم logging با ماسک کردن اطلاعات حساس
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------
# مدل‌های داده‌ای و تایپ‌ها
# -----------------------------


class LabResult(BaseModel):
    test_name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    flag: Optional[str] = None


class Medication(BaseModel):
    name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None


class VitalSigns(BaseModel):
    blood_pressure: Optional[str] = None
    heart_rate: Optional[str] = None
    temperature: Optional[str] = None
    respiratory_rate: Optional[str] = None
    oxygen_saturation: Optional[str] = None


class MedicalExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True, arbitrary_types_allowed=False)

    document_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    lab_results: List[LabResult] = Field(default_factory=list)
    medications: List[Medication] = Field(default_factory=list)
    diagnoses: List[str] = Field(default_factory=list)
    imaging_findings: Optional[str] = None
    clinical_notes: Optional[str] = None
    vital_signs: Optional[VitalSigns] = None
    allergies: List[str] = Field(default_factory=list)
    date: Optional[str] = None
    doctor_name: Optional[str] = None
    summary: Optional[str] = None

    @field_validator("confidence", mode="after")
    def round_confidence(cls, value: float) -> float:
        return round(value, 3)

    @field_validator("date", mode="before")
    def validate_date(cls, value: Optional[Union[str, datetime]]) -> Optional[str]:
        if value in (None, "", "null"):
            return None

        if isinstance(value, datetime):
            return value.date().isoformat()

        cleaned = str(value).strip()
        if not cleaned:
            return None

        try:
            parsed = datetime.fromisoformat(cleaned)
            return parsed.date().isoformat()
        except ValueError:
            logger.warning("Invalid date format received from model: %s", value)
            return cleaned


class ProcessedText(TypedDict):
    type: Literal["text"]
    data: str


class ProcessedImage(TypedDict):
    type: Literal["image"]
    data: str
    mime_type: str


ProcessedFile = Union[ProcessedText, ProcessedImage]


class RetryableAPIError(Exception):
    """خطاهای قابل تکرار (network / rate-limit)."""
    pass


class PermanentAPIError(Exception):
    """خطاهای غیرقابل تکرار (Authentication/Invalid Request)."""
    pass


MEDICAL_EXTRACTION_PROMPT = """You are a medical data extraction system. Extract structured information...
(Output prompt متن کامل قبلی بدون تغییر، ترجیحاً در یک متغیر ثابت نگه دارید)"""


class MedicalFileAnalyzer:
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_TEXT_FORMATS = {".txt", ".pdf", ".docx", ".doc"}
    ALLOWED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        openrouter_base_url: Optional[str] = None,
        cache_dir: Optional[Union[str, Path]] = None,
        timeout: int = 30,
    ) -> None:
        http_client = httpx.AsyncClient(proxies=settings.HTTP_PROXY, timeout=timeout)

        resolved_openrouter_key = openrouter_api_key or settings.openrouter_api_key
        resolved_openrouter_base_url = openrouter_base_url or settings.openrouter_base_url

        self.openai_client = (
            AsyncOpenAI(api_key=openai_api_key, timeout=timeout, http_client=http_client) if openai_api_key else None
        )
        self.openrouter_client = (
            AsyncOpenAI(
                api_key=resolved_openrouter_key,
                base_url=resolved_openrouter_base_url,
                timeout=timeout,
                http_client=http_client,
                default_headers={
                    "HTTP-Referer": settings.openrouter_http_referer,
                    "X-Title": settings.openrouter_app_title,
                },
            )
            if resolved_openrouter_key
            else None
        )
        self.anthropic_client = (
            AsyncAnthropic(api_key=anthropic_api_key, timeout=timeout) if anthropic_api_key else None
        )
        self.timeout = timeout

        if not self.openai_client and not self.anthropic_client and not self.openrouter_client:
            raise ValueError("حداقل یکی از کلیدهای OpenAI، OpenRouter یا Anthropic باید ارائه شود.")

        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".medical_analyzer_cache"
        self.cache_dir.mkdir(exist_ok=True)
        logger.info("MedicalFileAnalyzer initialized successfully.")

    # -----------------------------
    # توابع کمکی فایل و کش
    # -----------------------------

    def _get_file_hash(self, file_path: str) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    async def _get_cached_result(self, file_hash: str) -> Optional[Dict[str, Any]]:
        cache_file = self.cache_dir / f"{file_hash}.json"
        if cache_file.exists():
            try:
                async with aiofiles.open(cache_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                logger.info("Cache hit for file hash: %s", file_hash[:8])
                return json.loads(content)
            except Exception as exc:
                logger.warning("Unable to read cache (%s): %s", cache_file.name, exc)
        return None

    async def _save_to_cache(self, file_hash: str, result: Dict[str, Any]) -> None:
        cache_file = self.cache_dir / f"{file_hash}.json"
        try:
            async with aiofiles.open(cache_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(result, ensure_ascii=False, indent=2))
            logger.info("Result cached under hash: %s", file_hash[:8])
        except Exception as exc:
            logger.warning("Unable to write cache (%s): %s", cache_file.name, exc)

    def _validate_file(self, file_path: str) -> Path:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"فایل یافت نشد: {file_path}")
        if not path.is_file():
            raise ValueError(f"مسیر باید یک فایل باشد: {file_path}")

        file_size = path.stat().st_size
        if file_size > self.MAX_FILE_SIZE:
            raise ValueError(
                f"حجم فایل ({file_size / 1024 / 1024:.2f}MB) از سقف مجاز ({self.MAX_FILE_SIZE / 1024 / 1024}MB) بیشتر است."
            )

        suffix = path.suffix.lower()
        if suffix not in self.ALLOWED_TEXT_FORMATS | self.ALLOWED_IMAGE_FORMATS:
            raise ValueError(
                f"فرمت فایل پشتیبانی نمی‌شود: {suffix}."
                f" فرمت‌های مجاز: {self.ALLOWED_TEXT_FORMATS | self.ALLOWED_IMAGE_FORMATS}"
            )

        return path

    # -----------------------------
    # تبدیل فایل به متن/تصویر
    # -----------------------------

    async def _extract_pdf_text(self, file_path: Path) -> str:
        try:
            import PyPDF2  # type: ignore
        except ImportError as exc:
            raise ImportError("برای پردازش PDF باید PyPDF2 نصب شود: pip install PyPDF2") from exc

        def read_pdf() -> str:
            text_chunks: List[str] = []
            with file_path.open("rb") as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    extracted = page.extract_text() or ""
                    text_chunks.append(extracted.strip())
            return "\n".join(filter(None, text_chunks))

        return await asyncio.to_thread(read_pdf)

    async def _extract_docx_text(self, file_path: Path) -> str:
        try:
            import docx  # type: ignore
        except ImportError as exc:
            raise ImportError("برای پردازش Word باید python-docx نصب شود: pip install python-docx") from exc

        def read_docx() -> str:
            document = docx.Document(file_path)
            return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())

        return await asyncio.to_thread(read_docx)

    async def _process_file(self, file_path: Path) -> ProcessedFile:
        suffix = file_path.suffix.lower()

        if suffix in self.ALLOWED_IMAGE_FORMATS:
            async with aiofiles.open(file_path, "rb") as f:
                content = await f.read()
            base64_image = base64.b64encode(content).decode("utf-8")
            mime_type = f"image/{suffix[1:]}" if suffix != ".jpg" else "image/jpeg"
            return {"type": "image", "data": base64_image, "mime_type": mime_type}

        if suffix == ".txt":
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                text = await f.read()
            return {"type": "text", "data": text}

        if suffix == ".pdf":
            text = await self._extract_pdf_text(file_path)
            return {"type": "text", "data": text}

        if suffix in {".docx", ".doc"}:
            if suffix == ".doc":
                logger.warning(".doc legacy support relies on python-docx; تبدیل ممکن است کامل نباشد.")
            text = await self._extract_docx_text(file_path)
            return {"type": "text", "data": text}

        raise ValueError(f"فرمت فایل پشتیبانی نمی‌شود: {suffix}")

    # -----------------------------
    # پردازش خروجی LLM
    # -----------------------------

    def _safe_json_load(self, raw_text: str) -> Dict[str, Any]:
        stripped = raw_text.strip()
        if not stripped:
            raise ValueError("خروجی مدل خالی بود.")

        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

                # حذف code block
        pattern = r"""^
        ```(?:json)?\s*|\s*
        ```$"""
        sanitized = re.sub(pattern, "", stripped, flags=re.MULTILINE).strip()

        if sanitized != stripped:
            try:
                return json.loads(sanitized)
            except json.JSONDecodeError:
                pass

        # یافتن اولین آبجکت JSON کامل
        match = re.search(r"\{(?:[^{}]|\{[^{}]*\})*\}", sanitized, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # تلاش نهایی برای استخراج متعادل
        stack: List[int] = []
        start = -1
        for idx, char in enumerate(sanitized):
            if char == "{":
                if not stack:
                    start = idx
                stack.append(idx)
            elif char == "}":
                if stack:
                    stack.pop()
                    if not stack and start >= 0:
                        candidate = sanitized[start : idx + 1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            continue

        raise ValueError("JSON معتبر در خروجی مدل یافت نشد.")

    # -----------------------------
    # تماس با API‌ها
    # -----------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(RetryableAPIError),
        reraise=True,
    )
    async def _analyze_with_openai(self, processed_file: ProcessedFile, model: str = "gpt-4o") -> Dict[str, Any]:
        if not self.openai_client:
            raise RuntimeError("OpenAI client is not configured.")

        try:
            messages: List[Dict[str, Any]] = [{"role": "system", "content": MEDICAL_EXTRACTION_PROMPT}]

            if processed_file["type"] == "text":
                messages.append(
                    {
                        "role": "user",
                        "content": f"Extract medical information from this document:\n\n{processed_file['data']}",
                    }
                )
            else:
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract medical information from this image:"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{processed_file['mime_type']};base64,{processed_file['data']}"
                                },
                            },
                        ],
                    }
                )

            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if isinstance(content, list):
                content = "".join(chunk["text"] for chunk in content if chunk.get("type") == "text")

            logger.info("OpenAI response received (model: %s).", model)
            return self._safe_json_load(content)

        except Exception as exc:
            error_msg = str(exc).lower()
            if any(keyword in error_msg for keyword in ("timeout", "connection", "network", "rate limit")):
                logger.warning("Retryable error from OpenAI: %s", exc)
                raise RetryableAPIError(f"OpenAI API error: {exc}") from exc

            logger.error("Permanent error from OpenAI: %s", exc)
            raise PermanentAPIError(f"OpenAI API error: {exc}") from exc

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(RetryableAPIError),
        reraise=True,
    )
    async def _analyze_with_openrouter(
        self,
        processed_file: ProcessedFile,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.openrouter_client:
            raise RuntimeError("OpenRouter client is not configured.")

        model = model or settings.openrouter_default_model

        try:
            messages: List[Dict[str, Any]] = [{"role": "system", "content": MEDICAL_EXTRACTION_PROMPT}]

            if processed_file["type"] == "text":
                messages.append(
                    {
                        "role": "user",
                        "content": f"Extract medical information from this document:\n\n{processed_file['data']}",
                    }
                )
            else:
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract medical information from this image:"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{processed_file['mime_type']};base64,{processed_file['data']}"
                                },
                            },
                        ],
                    }
                )

            response = await self.openrouter_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if isinstance(content, list):
                content = "".join(chunk["text"] for chunk in content if chunk.get("type") == "text")

            logger.info("OpenRouter response received (model: %s).", model)
            return self._safe_json_load(content)

        except Exception as exc:
            error_msg = str(exc).lower()
            if any(keyword in error_msg for keyword in ("timeout", "connection", "network", "rate limit")):
                logger.warning("Retryable error from OpenRouter: %s", exc)
                raise RetryableAPIError(f"OpenRouter API error: {exc}") from exc

            logger.error("Permanent error from OpenRouter: %s", exc)
            raise PermanentAPIError(f"OpenRouter API error: {exc}") from exc

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(RetryableAPIError),
        reraise=True,
    )
    async def _analyze_with_anthropic(
        self,
        processed_file: ProcessedFile,
        model: str = "claude-3-5-sonnet-20241022",
    ) -> Dict[str, Any]:
        if not self.anthropic_client:
            raise RuntimeError("Anthropic client is not configured.")

        try:
            if processed_file["type"] == "text":
                content = [{"type": "text", "text": f"Extract medical information from this document:\n\n{processed_file['data']}"}]
            else:
                content = [
                    {"type": "image", "source": {"type": "base64", "media_type": processed_file["mime_type"], "data": processed_file["data"]}},
                    {"type": "text", "text": "Extract medical information from this image:"},
                ]

            response = await self.anthropic_client.messages.create(
                model=model,
                max_tokens=2000,
                temperature=0.0,
                system=MEDICAL_EXTRACTION_PROMPT,
                messages=[{"role": "user", "content": content}],
            )

            # Anthropic پاسخ را به صورت لیست segment باز می‌گرداند
            content_text = " ".join(segment.text for segment in response.content if hasattr(segment, "text"))
            logger.info("Anthropic response received (model: %s).", model)
            return self._safe_json_load(content_text)

        except Exception as exc:
            error_msg = str(exc).lower()
            if any(keyword in error_msg for keyword in ("timeout", "connection", "network", "rate limit", "overloaded")):
                logger.warning("Retryable error from Anthropic: %s", exc)
                raise RetryableAPIError(f"Anthropic API error: {exc}") from exc

            logger.error("Permanent error from Anthropic: %s", exc)
            raise PermanentAPIError(f"Anthropic API error: {exc}") from exc

    # -----------------------------
    # رابط عمومی تحلیل
    # -----------------------------

    async def analyze_file(
        self,
        file_path: str,
        *,
        use_cache: bool = True,
        prefer_provider: Optional[Literal["openai", "anthropic", "openrouter"]] = None,
    ) -> MedicalExtraction:
        validated_path = self._validate_file(file_path)
        logger.info("Processing file: %s", validated_path.name)

        file_hash: Optional[str] = None
        if use_cache:
            file_hash = self._get_file_hash(str(validated_path))
            cached = await self._get_cached_result(file_hash)
            if cached:
                return MedicalExtraction(**cached)

        processed_file = await self._process_file(validated_path)

        providers_order: List[str] = []
        if prefer_provider == "openai" and self.openai_client:
            providers_order = ["openai", "openrouter", "anthropic"]
        elif prefer_provider == "openrouter" and self.openrouter_client:
            providers_order = ["openrouter", "openai", "anthropic"]
        elif prefer_provider == "anthropic" and self.anthropic_client:
            providers_order = ["anthropic", "openai", "openrouter"]
        else:
            if self.openrouter_client:
                providers_order.append("openrouter")
            if self.openai_client:
                providers_order.append("openai")
            if self.anthropic_client:
                providers_order.append("anthropic")

        if not providers_order:
            raise RuntimeError("هیچ ارائه‌دهنده‌ای برای تحلیل قابل استفاده نیست.")

        last_exception: Optional[Exception] = None
        for provider in providers_order:
            try:
                if provider == "openai":
                    raw_result = await self._analyze_with_openai(processed_file)
                elif provider == "openrouter":
                    raw_result = await self._analyze_with_openrouter(processed_file)
                else:
                    raw_result = await self._analyze_with_anthropic(processed_file)

                extraction = MedicalExtraction(**raw_result)

                if use_cache and file_hash:
                    await self._save_to_cache(file_hash, extraction.model_dump())
                logger.info("Analysis completed successfully using provider: %s.", provider)
                return extraction

            except PermanentAPIError as exc:
                logger.error("Permanent error with %s, switching provider.", provider)
                last_exception = exc
                continue
            except RetryableAPIError as exc:
                logger.error("Retries exhausted for %s, switching provider.", provider)
                last_exception = exc
                continue
            except Exception as exc:
                logger.exception("Unexpected error with %s: %s", provider, exc)
                last_exception = exc
                continue

        raise RuntimeError(f"تحلیل فایل با تمام ارائه‌دهندگان شکست خورد. آخرین خطا: {last_exception}")

    async def batch_analyze(self, file_paths: List[str], *, use_cache: bool = True) -> List[MedicalExtraction]:
        tasks = [self.analyze_file(path, use_cache=use_cache) for path in file_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful: List[MedicalExtraction] = []
        for file_path, result in zip(file_paths, results):
            if isinstance(result, Exception):
                logger.error("Failed to analyze %s: %s", file_path, result)
            else:
                successful.append(result)

        return successful


async def main() -> None:
    analyzer = MedicalFileAnalyzer(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        timeout=30,
    )

    try:
        result = await analyzer.analyze_file(
            "path/to/medical/file.pdf",
            prefer_provider="openai",
        )
        print(f"نوع سند: {result.document_type}")
        print(f"اطمینان: {result.confidence}")
        print(f"تعداد نتایج آزمایش: {len(result.lab_results)}")
        print(f"تعداد داروها: {len(result.medications)}")
        print(f"\nخلاصه: {result.summary}")
    except Exception as exc:
        logger.error("خطا در تحلیل: %s", exc)


if __name__ == "__main__":
    asyncio.run(main())
