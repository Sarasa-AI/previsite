import pytest

from app.schemas.pmh import PMHAnswer, PMHAssertion
from app.services.clinical_conflict import (
    split_conflict_footer,
    validate_and_format_conflicts,
)
from app.services.pmh_service import build_pmh_assertion_registry


def test_split_conflict_footer_returns_body_and_items() -> None:
    output = (
        "# SOAP\nS: ...\n\n"
        "<<<CLINICAL_CONFLICTS>>>[{\"pmh_assertion_id\":\"x\",\"chat_polarity\":\"deny\",\"chat_quote\":\"no\",\"concept\":\"X\",\"confidence\":\"high\"}]"
        "<<<END_CLINICAL_CONFLICTS>>>"
    )
    parsed = split_conflict_footer(output)
    assert parsed.soap_body.startswith("# SOAP")
    assert len(parsed.raw_items) == 1
    assert parsed.raw_items[0]["pmh_assertion_id"] == "x"


def test_validate_and_format_conflicts_filters_low_confidence_and_missing_quote() -> None:
    pmh_registry = [
        PMHAssertion(
            assertion_id="pmh_cardio_cad_001",
            concept="CAD",
            subcategory="Ischemic Heart Disease",
            category_id="cat_cardio",
            polarity="present",
        )
    ]
    llm = (
        "# SOAP\nS: ...\n\n"
        "<<<CLINICAL_CONFLICTS>>>"
        "["
        "{\"pmh_assertion_id\":\"pmh_cardio_cad_001\",\"chat_polarity\":\"deny\",\"chat_quote\":\"I never had heart disease\",\"concept\":\"CAD\",\"confidence\":\"low\"},"
        "{\"pmh_assertion_id\":\"pmh_cardio_cad_001\",\"chat_polarity\":\"deny\",\"chat_quote\":\"I never had heart disease\",\"concept\":\"CAD\",\"confidence\":\"high\"}"
        "]"
        "<<<END_CLINICAL_CONFLICTS>>>"
    )
    body, conflicts = validate_and_format_conflicts(
        llm_output=llm,
        pmh_registry=pmh_registry,
        chat_history=[{"role": "patient", "content": "No issues today."}],
    )
    assert body.startswith("# SOAP")
    assert conflicts == []


def test_validate_and_format_conflicts_keeps_true_contradiction() -> None:
    pmh_registry = [
        PMHAssertion(
            assertion_id="pmh_cardio_cad_001",
            concept="CAD",
            subcategory="Ischemic Heart Disease",
            category_id="cat_cardio",
            polarity="present",
        )
    ]
    llm = (
        "# SOAP\nS: ...\n\n"
        "<<<CLINICAL_CONFLICTS>>>"
        "[{\"pmh_assertion_id\":\"pmh_cardio_cad_001\",\"chat_polarity\":\"deny\",\"chat_quote\":\"I never had heart disease\",\"concept\":\"CAD\",\"confidence\":\"high\"}]"
        "<<<END_CLINICAL_CONFLICTS>>>"
    )
    _body, conflicts = validate_and_format_conflicts(
        llm_output=llm,
        pmh_registry=pmh_registry,
        chat_history=[{"role": "patient", "content": "I never had heart disease."}],
    )
    assert len(conflicts) == 1
    assert conflicts[0].pmh_assertion_id == "pmh_cardio_cad_001"


@pytest.mark.parametrize(
    "is_selected,expected_polarity",
    [
        (True, "present"),
        (False, "category_denied"),
    ],
)
def test_build_pmh_assertion_registry_basic(is_selected: bool, expected_polarity: str) -> None:
    answers = [
        PMHAnswer(
            category_id="cat_cardio",
            is_selected=is_selected,
            question_responses={"pmh_cardio_cad_001": True} if is_selected else {},
        )
    ]
    registry = build_pmh_assertion_registry(answers)
    assert registry
    assert registry[0].polarity == expected_polarity

