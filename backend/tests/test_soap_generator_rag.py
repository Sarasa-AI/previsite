from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.medical import MedicalSummary
from app.services.soap_generator import SOAPNoteGenerator


def _sample_summary(**overrides) -> MedicalSummary:
    base = {
        "chief_complaint": "Chest pain",
        "symptoms": ["chest pain", "shortness of breath"],
        "symptom_duration": "2 days",
        "symptom_severity": "moderate",
        "additional_notes": "Patient reports substernal chest pain radiating to left arm.",
    }
    base.update(overrides)
    return MedicalSummary(**base)


def _rag_results() -> list[dict]:
    return [
        {
            "content": "Acute coronary syndrome may present with substernal chest pain.",
            "source": "Harrison's Internal Medicine",
            "confidence": 0.91,
        },
        {
            "content": "ECG and troponin are first-line diagnostics for chest pain.",
            "source": "ACC Guidelines 2024",
            "confidence": 0.84,
        },
        {
            "content": "Aspirin 325 mg is recommended unless contraindicated.",
            "source": "AHA Chest Pain Protocol",
            "confidence": 0.79,
        },
    ]


class TestPatientHpiExtraction:
    def test_prefers_additional_notes(self):
        generator = SOAPNoteGenerator(rag_service=MagicMock())
        summary = _sample_summary(additional_notes="Detailed HPI narrative.")

        assert generator._extract_patient_hpi(summary) == "Detailed HPI narrative."

    def test_falls_back_to_structured_fields(self):
        generator = SOAPNoteGenerator(rag_service=MagicMock())
        summary = _sample_summary(additional_notes=None)

        hpi = generator._extract_patient_hpi(summary)

        assert "Chest pain" in hpi
        assert "chest pain, shortness of breath" in hpi
        assert "2 days" in hpi

    def test_falls_back_to_chief_complaint(self):
        generator = SOAPNoteGenerator(rag_service=MagicMock())
        summary = MedicalSummary(chief_complaint="Headache")

        assert generator._extract_patient_hpi(summary) == "Headache"

    def test_uses_general_presentation_when_empty(self):
        generator = SOAPNoteGenerator(rag_service=MagicMock())
        summary = MedicalSummary()

        assert generator._extract_patient_hpi(summary) == "general clinical presentation"


class TestMedicalEvidenceFormatting:
    def test_formats_numbered_evidence_block(self):
        generator = SOAPNoteGenerator(rag_service=MagicMock())
        block = generator._format_medical_evidence(_rag_results())

        assert block.startswith("### Medical Evidence:")
        assert "[1] Harrison's Internal Medicine:" in block
        assert "[2] ACC Guidelines 2024:" in block
        assert "[3] AHA Chest Pain Protocol:" in block

    def test_uses_unknown_source_when_missing(self):
        generator = SOAPNoteGenerator(rag_service=MagicMock())
        block = generator._format_medical_evidence([{"content": "Some evidence", "source": None}])

        assert "[1] Unknown source: Some evidence" in block

    def test_returns_empty_string_for_no_results(self):
        generator = SOAPNoteGenerator(rag_service=MagicMock())

        assert generator._format_medical_evidence([]) == ""


class TestCitationMapping:
    def test_builds_one_indexed_citations(self):
        generator = SOAPNoteGenerator(rag_service=MagicMock())
        citations = generator._build_citations(_rag_results())

        assert len(citations) == 3
        assert citations[0]["index"] == 1
        assert citations[0]["source"] == "Harrison's Internal Medicine"
        assert citations[0]["content"].startswith("Acute coronary syndrome")
        assert citations[0]["confidence"] == 0.91


@pytest.mark.asyncio
async def test_generate_soap_note_includes_evidence_and_citations():
    mock_rag = MagicMock()
    mock_rag.search_similar_knowledge = AsyncMock(return_value=_rag_results())

    generator = SOAPNoteGenerator(rag_service=mock_rag)
    generator.openrouter_client = MagicMock()

    captured_messages = {}

    async def fake_create(**kwargs):
        captured_messages["messages"] = kwargs["messages"]
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="# SOAP\n\nA: ACS suspected [1]"))]
        return response

    generator.openrouter_client.chat.completions.create = AsyncMock(side_effect=fake_create)

    summary = _sample_summary()
    db = MagicMock()

    result = await generator.generate_soap_note(summary=summary, db=db)

    assert result["status"] == "success"
    assert result["soap_note"].startswith("# SOAP")
    assert len(result["citations"]) == 3
    assert result["citations"][0]["index"] == 1

    user_content = captured_messages["messages"][1]["content"]
    assert "### Medical Evidence:" in user_content
    assert "[1] Harrison's Internal Medicine:" in user_content

    mock_rag.search_similar_knowledge.assert_awaited_once()
    call_kwargs = mock_rag.search_similar_knowledge.await_args.kwargs
    assert call_kwargs["query"] == summary.additional_notes


@pytest.mark.asyncio
async def test_generate_soap_note_gracefully_degrades_when_rag_fails():
    mock_rag = MagicMock()
    mock_rag.search_similar_knowledge = AsyncMock(side_effect=RuntimeError("embedding unavailable"))

    generator = SOAPNoteGenerator(rag_service=mock_rag)
    generator.openrouter_client = MagicMock()

    captured_messages = {}

    async def fake_create(**kwargs):
        captured_messages["messages"] = kwargs["messages"]
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="# SOAP\n\nA: Clinical impression"))]
        return response

    generator.openrouter_client.chat.completions.create = AsyncMock(side_effect=fake_create)

    result = await generator.generate_soap_note(summary=_sample_summary(), db=MagicMock())

    assert result["status"] == "success"
    assert result["citations"] == []
    assert "### Medical Evidence:" not in captured_messages["messages"][1]["content"]
