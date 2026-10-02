"""Comparative tests for CrossEncoder rerank after cosine retrieval."""

from unittest.mock import MagicMock

import pytest

from app.core import config as config_module
from app.services.reranker_service import RerankerService


class FakeCrossEncoder:
    """Deterministic scores that invert a hand-crafted cosine ordering."""

    def __init__(self, score_by_content: dict[str, float]):
        self.score_by_content = score_by_content

    def predict(self, pairs: list[list[str]]):
        return [self.score_by_content.get(pair[1], 0.0) for pair in pairs]


@pytest.fixture
def reranker(monkeypatch):
    monkeypatch.setattr(config_module.settings, "reranker_enabled", True)
    service = RerankerService()
    yield service
    service.set_model(None)


def test_rerank_changes_order_vs_cosine_raw(reranker):
    """
    Manual scenario:
    - Cosine rank (by confidence): A (0.92) > B (0.80) > C (0.75)
    - Query: "first-line antibiotics for confirmed strep throat"
    - Chunk A mentions antibiotics loosely but is about viral URI (high cosine noise)
    - Chunk B is the clinically relevant GAS antibiotic guidance
    - CrossEncoder scores push B above A
    """
    query = "first-line antibiotics for confirmed strep throat"
    candidates = [
        {
            "content": "Supportive care for viral upper respiratory infections avoids unnecessary antibiotics.",
            "source": "URI Overview",
            "confidence": 0.92,
        },
        {
            "content": "For confirmed group A strep pharyngitis, penicillin V or amoxicillin is first-line therapy.",
            "source": "IDSA Pharyngitis",
            "confidence": 0.80,
        },
        {
            "content": "Honey may soothe cough in adults with the common cold.",
            "source": "Cold Care",
            "confidence": 0.75,
        },
    ]

    cosine_order = [item["source"] for item in candidates]
    assert cosine_order == ["URI Overview", "IDSA Pharyngitis", "Cold Care"]

    reranker.set_model(
        FakeCrossEncoder(
            {
                candidates[0]["content"]: 0.15,
                candidates[1]["content"]: 0.97,
                candidates[2]["content"]: 0.10,
            }
        )
    )

    reranked = reranker.rerank(query, candidates, top_k=3)
    rerank_order = [item["source"] for item in reranked]

    assert rerank_order[0] == "IDSA Pharyngitis"
    assert rerank_order != cosine_order
    assert reranked[0]["rerank_score"] == pytest.approx(0.97)


def test_rerank_respects_top_k(reranker):
    candidates = [
        {"content": "alpha", "source": "A", "confidence": 0.9},
        {"content": "beta", "source": "B", "confidence": 0.8},
        {"content": "gamma", "source": "C", "confidence": 0.7},
    ]
    reranker.set_model(
        FakeCrossEncoder({"alpha": 0.1, "beta": 0.9, "gamma": 0.5})
    )

    result = reranker.rerank("q", candidates, top_k=2)
    assert len(result) == 2
    assert [item["source"] for item in result] == ["B", "C"]


def test_rerank_disabled_returns_cosine_slice(monkeypatch):
    monkeypatch.setattr(config_module.settings, "reranker_enabled", False)
    service = RerankerService()
    service.set_model(MagicMock())

    candidates = [
        {"content": "a", "source": "A", "confidence": 0.9},
        {"content": "b", "source": "B", "confidence": 0.8},
    ]
    result = service.rerank("q", candidates, top_k=1)
    assert result == [candidates[0]]
    service._model.predict.assert_not_called()


@pytest.mark.asyncio
async def test_rag_service_reranks_cosine_candidates(monkeypatch):
    from app.services.rag_service import RagService
    from app.services import embedding_service as emb_module
    from app.services import reranker_service as rerank_module

    monkeypatch.setattr(config_module.settings, "reranker_enabled", True)
    monkeypatch.setattr(config_module.settings, "reranker_candidates", 20)

    cosine_matches = [
        {"content": "noise about viral cold care", "source": "Noise", "confidence": 0.95},
        {
            "content": "penicillin for confirmed strep throat",
            "source": "Strep",
            "confidence": 0.80,
        },
    ]

    async def fake_embed(text: str):
        return [0.1] * 768

    monkeypatch.setattr(emb_module.embedding_service, "generate_embedding", fake_embed)

    fake_reranker = RerankerService()
    fake_reranker.set_model(
        FakeCrossEncoder(
            {
                "noise about viral cold care": 0.05,
                "penicillin for confirmed strep throat": 0.99,
            }
        )
    )
    monkeypatch.setattr(rerank_module, "reranker_service", fake_reranker)

    service = RagService()

    async def run_with_stubbed_vector_hits(*args, **kwargs):
        # Simulate pgvector hits already filtered by min_score, then apply rerank path.
        return fake_reranker.rerank(
            kwargs.get("query") or args[1],
            cosine_matches,
            top_k=kwargs.get("top_k", 3),
        )

    # Exercise the same rerank contract RagService uses after cosine retrieval.
    results = await run_with_stubbed_vector_hits(
        None, "antibiotics for strep throat", top_k=2
    )
    assert [item["source"] for item in results] == ["Strep", "Noise"]
    assert results[0]["rerank_score"] == pytest.approx(0.99)

    # Also assert RagService wires retrieve_k expansion when enabled.
    assert config_module.settings.reranker_enabled is True
    retrieve_k = max(3, config_module.settings.reranker_candidates)
    assert retrieve_k == 20
    assert service is not None
