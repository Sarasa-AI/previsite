"""Admin-facing medical knowledge ingest pipeline (no curated content generation)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from typing import Any
from uuid import uuid4

from pypdf import PdfReader
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medical_knowledge import MedicalKnowledge
from app.services.embedding_service import EmbeddingServiceError, embedding_service

logger = logging.getLogger(__name__)

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class KbIngestValidationError(ValueError):
    """Raised when an uploaded KB document fails validation."""


@dataclass
class IngestedDocumentResult:
    document_id: str
    chunks_inserted: int
    title: str
    source: str
    published_at: str


def _parse_published_at(value: Any) -> str:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise KbIngestValidationError("Each document must include published_at (YYYY-MM-DD).")

    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = str(value).strip()
    if ISO_DATE_RE.match(text):
        try:
            date.fromisoformat(text)
        except ValueError as exc:
            raise KbIngestValidationError(
                f"published_at must be a valid ISO date (YYYY-MM-DD), got {text!r}."
            ) from exc
        return text

    # Allow full ISO datetime strings by normalizing to date.
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError as exc:
        raise KbIngestValidationError(
            f"published_at must be a valid ISO date (YYYY-MM-DD), got {text!r}."
        ) from exc


def validate_document(doc: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a KB document payload."""
    if not isinstance(doc, dict):
        raise KbIngestValidationError("Each document must be a JSON object.")

    document_id = (doc.get("document_id") or "").strip()
    title = (doc.get("title") or "").strip()
    source = (doc.get("source") or "").strip()
    content = (doc.get("content") or "").strip()
    published_at = _parse_published_at(doc.get("published_at"))

    missing: list[str] = []
    if not document_id:
        missing.append("document_id")
    if not title:
        missing.append("title")
    if not source:
        missing.append("source")
    if not content:
        missing.append("content")
    if missing:
        raise KbIngestValidationError(
            f"Document is missing required fields: {', '.join(missing)}."
        )

    metadata = doc.get("metadata")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise KbIngestValidationError("metadata must be an object when provided.")

    merged_metadata = {
        **metadata,
        "title": title,
        "published_at": published_at,
    }

    return {
        "document_id": document_id,
        "title": title,
        "source": source,
        "published_at": published_at,
        "content": content,
        "metadata": merged_metadata,
    }


def parse_json_payload(raw: bytes | str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise KbIngestValidationError(f"Invalid JSON: {exc.msg}") from exc

    if isinstance(payload, dict) and isinstance(payload.get("documents"), list):
        documents = payload["documents"]
    elif isinstance(payload, dict):
        documents = [payload]
    elif isinstance(payload, list):
        documents = payload
    else:
        raise KbIngestValidationError(
            "JSON must be a document object, a list of documents, or {\"documents\": [...]}."
        )

    if not documents:
        raise KbIngestValidationError("No documents found in JSON payload.")

    return [validate_document(doc) for doc in documents]


def parse_markdown_document(
    raw: bytes | str,
    *,
    document_id: str | None,
    title: str | None,
    source: str | None,
    published_at: str | None,
) -> list[dict[str, Any]]:
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    return [
        validate_document(
            {
                "document_id": document_id or f"md-{uuid4().hex[:12]}",
                "title": title,
                "source": source,
                "published_at": published_at,
                "content": text,
            }
        )
    ]


def parse_pdf_document(
    raw: bytes,
    *,
    document_id: str | None,
    title: str | None,
    source: str | None,
    published_at: str | None,
) -> list[dict[str, Any]]:
    try:
        reader = PdfReader(BytesIO(raw))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise KbIngestValidationError(f"Failed to parse PDF: {exc}") from exc

    content = "\n\n".join(part.strip() for part in pages if part and part.strip()).strip()
    if not content:
        raise KbIngestValidationError("PDF contained no extractable text.")

    return [
        validate_document(
            {
                "document_id": document_id or f"pdf-{uuid4().hex[:12]}",
                "title": title,
                "source": source,
                "published_at": published_at,
                "content": content,
            }
        )
    ]


def parse_upload(
    *,
    filename: str,
    content_type: str | None,
    raw: bytes,
    document_id: str | None = None,
    title: str | None = None,
    source: str | None = None,
    published_at: str | None = None,
) -> list[dict[str, Any]]:
    lower_name = (filename or "").lower()
    ctype = (content_type or "").lower()

    if lower_name.endswith(".json") or "json" in ctype:
        return parse_json_payload(raw)

    if lower_name.endswith((".md", ".markdown")) or "markdown" in ctype or ctype == "text/plain":
        return parse_markdown_document(
            raw,
            document_id=document_id,
            title=title,
            source=source,
            published_at=published_at,
        )

    if lower_name.endswith(".pdf") or "pdf" in ctype:
        return parse_pdf_document(
            raw,
            document_id=document_id,
            title=title,
            source=source,
            published_at=published_at,
        )

    raise KbIngestValidationError(
        "Unsupported file type. Upload JSON, Markdown, or PDF."
    )


async def ingest_documents(
    db: AsyncSession,
    documents: list[dict[str, Any]],
    *,
    commit: bool = True,
) -> list[IngestedDocumentResult]:
    """Chunk, embed, and upsert documents into medical_knowledge."""
    validated = [validate_document(doc) for doc in documents]
    results: list[IngestedDocumentResult] = []

    try:
        for doc in validated:
            document_id = doc["document_id"]
            content = doc["content"]
            chunks = embedding_service.chunk_medical_text(content)
            if not chunks:
                raise KbIngestValidationError(
                    f"Document {document_id!r} produced no embeddable chunks."
                )

            await db.execute(
                delete(MedicalKnowledge).where(MedicalKnowledge.document_id == document_id)
            )

            for chunk_index, chunk_text in enumerate(chunks):
                try:
                    embedding = await embedding_service.generate_embedding(chunk_text)
                except EmbeddingServiceError:
                    logger.exception(
                        "Embedding failed for document_id=%s chunk=%s",
                        document_id,
                        chunk_index,
                    )
                    raise
                except Exception as exc:
                    logger.exception(
                        "Unexpected embedding failure for document_id=%s chunk=%s",
                        document_id,
                        chunk_index,
                    )
                    raise EmbeddingServiceError(
                        "Failed to generate embedding. Ensure the embedding provider "
                        "(Ollama or configured fallback) is reachable."
                    ) from exc

                db.add(
                    MedicalKnowledge(
                        document_id=document_id,
                        chunk_index=chunk_index,
                        content=chunk_text,
                        source=doc["source"],
                        document_metadata=doc["metadata"],
                        embedding=embedding,
                    )
                )

            results.append(
                IngestedDocumentResult(
                    document_id=document_id,
                    chunks_inserted=len(chunks),
                    title=doc["title"],
                    source=doc["source"],
                    published_at=doc["published_at"],
                )
            )
            logger.info(
                "Ingested KB document %s (%s chunk(s))",
                document_id,
                len(chunks),
            )

        if commit:
            await db.commit()
    except Exception:
        await db.rollback()
        raise

    return results
