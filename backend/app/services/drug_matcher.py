import logging
import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.drug import GenericDrug

logger = logging.getLogger(__name__)

MATCH_THRESHOLD = 85
_WHITESPACE_RE = re.compile(r"\s+")
_DOSAGE_SUFFIX_RE = re.compile(r"[\d.,\s]+(?:mg|mcg|g|ml)?$", re.IGNORECASE)
_ALPHA_TOKEN_RE = re.compile(r"[a-z\u0600-\u06FF]{4,}", re.IGNORECASE)


@dataclass(frozen=True)
class DrugMatchEntry:
    term: str
    generic_name: str
    match_type: str


class DrugMatcher:
    def __init__(self) -> None:
        self._entries: list[DrugMatchEntry] = []

    async def refresh_cache(self, db: AsyncSession) -> None:
        result = await db.execute(
            select(GenericDrug).options(
                selectinload(GenericDrug.brands),
                selectinload(GenericDrug.aliases),
            )
        )
        generics = result.scalars().all()

        entries: list[DrugMatchEntry] = []
        for generic in generics:
            entries.append(
                DrugMatchEntry(
                    term=generic.generic_name.lower(),
                    generic_name=generic.generic_name,
                    match_type="generic",
                )
            )
            for brand in generic.brands:
                entries.append(
                    DrugMatchEntry(
                        term=brand.brand_name.lower(),
                        generic_name=generic.generic_name,
                        match_type="brand",
                    )
                )
            for alias in generic.aliases:
                entries.append(
                    DrugMatchEntry(
                        term=alias.alias_name.lower(),
                        generic_name=generic.generic_name,
                        match_type="alias",
                    )
                )

        self._entries = entries
        logger.info("DrugMatcher cache loaded with %s searchable terms", len(entries))

    def _ocr_query_variants(self, query: str) -> list[str]:
        variants: list[str] = []
        seen: set[str] = set()

        def _add(candidate: str) -> None:
            normalized = _WHITESPACE_RE.sub(" ", candidate.strip().lower())
            if normalized and normalized not in seen:
                seen.add(normalized)
                variants.append(normalized)

        _add(query)

        stripped = _DOSAGE_SUFFIX_RE.sub("", query).strip()
        if stripped:
            _add(stripped)

        for token in _ALPHA_TOKEN_RE.findall(query):
            _add(token)

        return variants

    def match_drug(self, ocr_text: str) -> dict | None:
        if not self._entries:
            return None

        choices = [entry.term for entry in self._entries]
        best_result: tuple[str, float, int] | None = None

        for query in self._ocr_query_variants(ocr_text):
            result = process.extractOne(
                query,
                choices,
                scorer=fuzz.WRatio,
                score_cutoff=MATCH_THRESHOLD,
            )
            if result is None:
                continue
            if best_result is None or result[1] > best_result[1]:
                best_result = result

        if best_result is None:
            return None

        matched_term, score, index = best_result
        entry = self._entries[index]
        return {
            "generic_name": entry.generic_name,
            "score": score,
            "matched_term": matched_term,
            "match_type": entry.match_type,
        }


drug_matcher = DrugMatcher()
