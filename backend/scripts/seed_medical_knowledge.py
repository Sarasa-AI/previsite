#!/usr/bin/env python3
"""Seed medical_knowledge table from backend/data/medical_kb.json."""

import asyncio
import json
import logging
import sys
from pathlib import Path

from sqlalchemy import delete

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.database import get_async_session  # noqa: E402
from app.models.medical_knowledge import MedicalKnowledge  # noqa: E402
from app.services.embedding_service import embedding_service  # noqa: E402

logger = logging.getLogger(__name__)

DATA_PATH = BACKEND_ROOT / "data" / "medical_kb.json"


def _load_documents() -> list[dict]:
    with DATA_PATH.open(encoding="utf-8") as f:
        payload = json.load(f)

    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError(f"No documents found in {DATA_PATH}")

    return documents


async def seed_medical_knowledge() -> None:
    documents = _load_documents()
    documents_processed = 0
    chunks_inserted = 0

    async with get_async_session() as db:
        try:
            for doc in documents:
                document_id = doc.get("document_id")
                content = doc.get("content", "").strip()
                if not document_id:
                    raise ValueError("Each document must include a document_id")
                if not content:
                    logger.warning("Skipping document %s: empty content", document_id)
                    continue

                await db.execute(
                    delete(MedicalKnowledge).where(
                        MedicalKnowledge.document_id == document_id
                    )
                )

                chunks = embedding_service.chunk_medical_text(content)
                if not chunks:
                    logger.warning("Skipping document %s: no chunks produced", document_id)
                    continue

                for chunk_index, chunk_text in enumerate(chunks):
                    embedding = await embedding_service.generate_embedding(chunk_text)
                    db.add(
                        MedicalKnowledge(
                            document_id=document_id,
                            chunk_index=chunk_index,
                            content=chunk_text,
                            source=doc.get("source"),
                            document_metadata=doc.get("metadata"),
                            embedding=embedding,
                        )
                    )
                    chunks_inserted += 1

                documents_processed += 1
                logger.info(
                    "Ingested document %s (%s chunk(s))",
                    document_id,
                    len(chunks),
                )

            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("Medical knowledge seed failed")
            raise

    logger.info(
        "Seed complete: %s document(s), %s chunk(s) inserted",
        documents_processed,
        chunks_inserted,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    asyncio.run(seed_medical_knowledge())


if __name__ == "__main__":
    main()
