from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.medical_knowledge import MedicalKnowledge
from app.services.embedding_service import embedding_service
from app.services.reranker_service import reranker_service


class RagService:
    async def search_similar_knowledge(
        self,
        db: AsyncSession,
        query: str,
        top_k: int = 3,
        min_score: float = 0.3,
    ) -> list[dict]:
        query_vector = await embedding_service.generate_embedding(query)

        retrieve_k = top_k
        if settings.reranker_enabled:
            retrieve_k = max(top_k, settings.reranker_candidates)

        distance = MedicalKnowledge.embedding.cosine_distance(query_vector)
        stmt = (
            select(MedicalKnowledge, distance.label("distance"))
            .where(MedicalKnowledge.embedding.is_not(None))
            .order_by(distance)
            .limit(retrieve_k)
        )

        result = await db.execute(stmt)
        rows = result.all()

        matches: list[dict] = []
        for row in rows:
            knowledge, dist = row[0], float(row[1])
            confidence = 1.0 - dist
            if confidence < min_score:
                continue
            matches.append(
                {
                    "content": knowledge.content,
                    "source": knowledge.source,
                    "confidence": confidence,
                }
            )

        if settings.reranker_enabled and matches:
            return reranker_service.rerank(query, matches, top_k=top_k)

        return matches[:top_k]


rag_service = RagService()
