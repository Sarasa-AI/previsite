#!/usr/bin/env python3
"""Seed medical_knowledge table from backend/data/medical_kb.json via kb_ingest_service."""

import asyncio
import json
import logging
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.database import get_async_session  # noqa: E402
from app.services.kb_ingest_service import (  # noqa: E402
    KbIngestValidationError,
    ingest_documents,
)

logger = logging.getLogger(__name__)

DATA_PATH = BACKEND_ROOT / "data" / "medical_kb.json"


def _load_seed_documents() -> list[dict]:
    with DATA_PATH.open(encoding="utf-8") as f:
        payload = json.load(f)

    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError(f"No documents found in {DATA_PATH}")

    # Seed JSON historically omitted title/published_at; derive safe defaults
    # for local CLI seeding only (admin HTTP ingest still requires them).
    normalized: list[dict] = []
    for doc in documents:
        metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
        title = doc.get("title") or doc.get("source") or doc.get("document_id")
        published_at = doc.get("published_at") or metadata.get("published_at") or "1970-01-01"
        normalized.append(
            {
                **doc,
                "title": title,
                "published_at": published_at,
                "metadata": metadata,
            }
        )
    return normalized


async def seed_medical_knowledge() -> None:
    documents = _load_seed_documents()

    async with get_async_session() as db:
        try:
            results = await ingest_documents(db, documents, commit=True)
        except KbIngestValidationError:
            logger.exception("Medical knowledge seed validation failed")
            raise
        except Exception:
            logger.exception("Medical knowledge seed failed")
            raise

    logger.info(
        "Seed complete: %s document(s), %s chunk(s) inserted",
        len(results),
        sum(item.chunks_inserted for item in results),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    asyncio.run(seed_medical_knowledge())


if __name__ == "__main__":
    main()
