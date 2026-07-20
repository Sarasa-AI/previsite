"""
Production-grade API integration & resiliency tests for the 4-layer intake flow.

Uses httpx.AsyncClient (ASGI transport) against the FastAPI app with an isolated
SQLite database per test module invocation.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from app.utils.national_id import validate_iranian_national_id
from httpx import ASGITransport, AsyncClient, Response

import app.api.intake as intake_api
from app.main import app as fastapi_app
from app.schemas.intake import ClinicalSummary, DemographicsInput, HPIQuestionsResponse
from app.services.intake_llm import (
    EXTRACTION_SYSTEM_PROMPT,
    LAYER2_SYSTEM_PROMPT,
    ClinicalSummaryResult,
    Layer2GenerationResult,
    _build_extraction_user_prompt,
    _build_layer2_user_prompt,
    _fallback_questions,
    intake_llm_service,
)
from app.services.json_parser import parse_llm_json
from app.services.openrouter_service import OpenRouterServiceError, openrouter_service


def _layer2_result(
    questions: HPIQuestionsResponse,
    *,
    fallback: bool = False,
    error: str | None = None,
) -> Layer2GenerationResult:
    return Layer2GenerationResult(
        questions=questions,
        llm_fallback_used=fallback,
        llm_error_message=error,
    )


def _clinical_summary_result(summary: ClinicalSummary, *, fallback: bool = False, error: str | None = None) -> ClinicalSummaryResult:
    return ClinicalSummaryResult(
        summary=summary,
        llm_fallback_used=fallback,
        llm_error_message=error,
    )

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

VALID_DEMOGRAPHICS: dict[str, Any] = {
    "first_name": "علی",
    "last_name": "رضایی",
    "national_id": "0499370899",
    "insurance_provider": "تأمین اجتماعی",
    "age": 34,
    "sex": "male",
    "weight": 75.0,
    "height": 175.0,
    "chief_complaint": "دل درد",
}


from tests.conftest import setup_async_test_db, teardown_test_db

_test_engine = None


async def _setup_test_db(tmp_path, monkeypatch) -> None:
    global _test_engine
    _test_engine = await setup_async_test_db(tmp_path, monkeypatch)


def _teardown() -> None:
    import asyncio

    global _test_engine
    teardown_test_db()
    if _test_engine is not None:
        asyncio.run(_test_engine.dispose())
        _test_engine = None


async def _async_client() -> AsyncClient:
    transport = ASGITransport(app=fastapi_app)
    return AsyncClient(transport=transport, base_url="http://test")


async def _register_and_login_async(
    client: AsyncClient,
    *,
    national_id: str | None = None,
    password: str = "VeryStrongPassword123!",
    seed: str = "default-patient",
) -> str:
    resolved_national_id = national_id or _national_id_from_seed(seed)
    register = await client.post(
        "/api/auth/register",
        json={
            "national_id": resolved_national_id,
            "password": password,
            "role": "patient",
        },
    )
    assert register.status_code == 200, register.text

    login = await client.post(
        "/api/auth/login",
        json={"national_id": resolved_national_id, "password": password},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _national_id_from_seed(seed: str) -> str:
    candidate = 1_000_000_000 + (abs(hash(seed)) % 900_000_000)
    while candidate < 9_999_999_999:
        national_id = str(candidate).zfill(10)
        if validate_iranian_national_id(national_id):
            return national_id
        candidate += 1
    return "0499370899"


async def _create_session(
    client: AsyncClient,
    headers: dict[str, str],
    complaint: str = "دل درد",
) -> int:
    response = await client.post(
        "/api/chat/session",
        json={"initial_complaint": complaint},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


async def _save_layer1(
    client: AsyncClient,
    session_id: int,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
) -> Response:
    return await client.post(
        f"/api/intake/{session_id}/layer1",
        json=payload or VALID_DEMOGRAPHICS,
        headers=headers,
    )


async def _bootstrap_intake_through_layer2(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    complaint: str = "دل درد",
) -> tuple[int, HPIQuestionsResponse]:
    session_id = await _create_session(client, headers, complaint)
    layer1 = await _save_layer1(client, session_id, headers)
    assert layer1.status_code == 200, layer1.text

    layer2 = await client.post(
        f"/api/intake/{session_id}/layer2/generate",
        headers=headers,
    )
    assert layer2.status_code == 200, layer2.text
    questions = HPIQuestionsResponse.model_validate(layer2.json()["hpi_questions"])
    return session_id, questions


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Phase 1 — API contract testing
# ---------------------------------------------------------------------------


class TestLayer1DemographicsContract:
    """DemographicsInput must align with planned frontend Zod (age 0–150, weight/height > 0)."""

    @pytest.mark.parametrize(
        "field_name,invalid_value,expected_status",
        [
            ("age", -1, 422),
            ("age", 151, 422),
            ("weight", 0, 422),
            ("weight", -5, 422),
            ("height", 0, 422),
        ],
    )
    def test_boundary_validation_rejects_invalid_numeric_fields(
        self, tmp_path, monkeypatch, field_name, invalid_value, expected_status
    ) -> None:
        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed=f"Boundary Patient boundary-{field_name}-{abs(invalid_value)}",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)

                payload = {**VALID_DEMOGRAPHICS, field_name: invalid_value}
                response = await client.post(
                    f"/api/intake/{session_id}/layer1",
                    json=payload,
                    headers=headers,
                )
                assert response.status_code == expected_status
                detail = response.json()["detail"]
                assert isinstance(detail, list)
                loc_fields = {err["loc"][-1] for err in detail}
                assert field_name in loc_fields

        asyncio.run(_run())
        _teardown()

    def test_missing_required_fields_returns_422(self, tmp_path, monkeypatch) -> None:
        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="Missing Fields",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)

                for missing_key in ("national_id", "first_name", "chief_complaint"):
                    payload = {k: v for k, v in VALID_DEMOGRAPHICS.items() if k != missing_key}
                    response = await client.post(
                        f"/api/intake/{session_id}/layer1",
                        json=payload,
                        headers=headers,
                    )
                    assert response.status_code == 422, f"expected 422 when {missing_key} omitted"

        asyncio.run(_run())
        _teardown()

    def test_valid_demographics_persists_and_advances_layer(self, tmp_path, monkeypatch) -> None:
        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="Valid Demo",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)

                response = await _save_layer1(client, session_id, headers)
                assert response.status_code == 200
                body = response.json()
                assert body["current_layer"] == 2

                demo = DemographicsInput.model_validate(body["demographics"])
                assert demo.national_id == VALID_DEMOGRAPHICS["national_id"]
                assert demo.age == VALID_DEMOGRAPHICS["age"]

                get_resp = await client.get(f"/api/intake/{session_id}", headers=headers)
                assert get_resp.status_code == 200
                assert get_resp.json()["demographics"]["chief_complaint"] == "دل درد"

        asyncio.run(_run())
        _teardown()

    def test_age_zero_is_accepted_by_backend(self, tmp_path, monkeypatch) -> None:
        """Frontend Zod should allow ge=0 to match Pydantic Field(ge=0)."""
        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="Age Zero",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)

                response = await _save_layer1(
                    client,
                    session_id,
                    headers,
                    {**VALID_DEMOGRAPHICS, "age": 0},
                )
                assert response.status_code == 200
                assert response.json()["demographics"]["age"] == 0

        asyncio.run(_run())
        _teardown()


class TestLayer2HPIContract:
    def test_layer2_generate_builds_expected_llm_prompt(self, tmp_path, monkeypatch) -> None:
        captured: dict[str, str] = {}

        async def spy_generate_json(*, system_prompt: str, user_prompt: str, **kwargs) -> dict:
            captured["system_prompt"] = system_prompt
            captured["user_prompt"] = user_prompt
            return {
                "question_strategy": "Acute symptom workflow",
                "questions": [
                    {
                        "id": "onset",
                        "question": "از چه زمانی؟",
                        "priority": 1,
                        "red_flag_related": False,
                    }
                ],
            }

        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            monkeypatch.setattr(openrouter_service, "generate_json", spy_generate_json)

            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="Prompt Spy",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)
                await _save_layer1(client, session_id, headers)

                demographics = DemographicsInput.model_validate(VALID_DEMOGRAPHICS)
                expected_user = _build_layer2_user_prompt(demographics)

                response = await client.post(
                    f"/api/intake/{session_id}/layer2/generate",
                    headers=headers,
                )
                assert response.status_code == 200

                assert LAYER2_SYSTEM_PROMPT.splitlines()[0] in captured["system_prompt"]
                assert captured["user_prompt"] == expected_user
                assert "Age: 34" in captured["user_prompt"]
                assert "Chief Complaint: دل درد" in captured["user_prompt"]

                hpi = response.json()["hpi_questions"]
                assert hpi["question_strategy"] == "Acute symptom workflow"
                assert hpi["questions"][0]["id"] == "onset"

        asyncio.run(_run())
        _teardown()

    def test_rapid_answer_submission_persists_all_answers(self, tmp_path, monkeypatch) -> None:
        async def fake_generate_hpi_questions(demographics, **kwargs):
            return _layer2_result(
                HPIQuestionsResponse(
                question_strategy="Acute",
                questions=[
                    {"id": "onset", "question": "Q1", "priority": 1, "red_flag_related": False},
                    {"id": "severity", "question": "Q2", "priority": 2, "red_flag_related": False},
                    {"id": "fever", "question": "Q3", "priority": 3, "red_flag_related": True},
                ],
                )
            )

        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            monkeypatch.setattr(
                intake_api.intake_llm_service,
                "generate_hpi_questions",
                fake_generate_hpi_questions,
            )

            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="Rapid HPI",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id, questions = await _bootstrap_intake_through_layer2(client, headers)

                answers = {
                    "onset": "۲ روز پیش",
                    "severity": "۸ از ۱۰",
                    "fever": "خیر",
                }

                last_response: Response | None = None
                for qid, ans in answers.items():
                    last_response = await client.post(
                        f"/api/intake/{session_id}/layer2/answer",
                        json={"question_id": qid, "answer": ans},
                        headers=headers,
                    )
                    assert last_response.status_code == 200, last_response.text

                final = last_response.json()  # type: ignore[union-attr]
                assert final["current_layer"] == 3
                assert final["hpi_answers"] == answers

        asyncio.run(_run())
        _teardown()

    def test_re_answer_overwrites_same_question_id(self, tmp_path, monkeypatch) -> None:
        async def fake_generate_hpi_questions(_demographics, **kwargs):
            return _layer2_result(
                HPIQuestionsResponse(
                question_strategy="Acute",
                questions=[
                    {"id": "onset", "question": "Q1", "priority": 1, "red_flag_related": False},
                    {"id": "severity", "question": "Q2", "priority": 2, "red_flag_related": False},
                ],
                )
            )

        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            monkeypatch.setattr(
                intake_api.intake_llm_service,
                "generate_hpi_questions",
                fake_generate_hpi_questions,
            )

            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="Reanswer",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id, _ = await _bootstrap_intake_through_layer2(client, headers)

                await client.post(
                    f"/api/intake/{session_id}/layer2/answer",
                    json={"question_id": "onset", "answer": "اولیه"},
                    headers=headers,
                )
                second = await client.post(
                    f"/api/intake/{session_id}/layer2/answer",
                    json={"question_id": "onset", "answer": "اصلاح‌شده"},
                    headers=headers,
                )
                assert second.status_code == 200
                assert second.json()["hpi_answers"]["onset"] == "اصلاح‌شده"
                assert len(second.json()["hpi_answers"]) == 1

        asyncio.run(_run())
        _teardown()

    def test_layer2_generate_without_layer1_returns_400(self, tmp_path, monkeypatch) -> None:
        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="No Layer1",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)

                response = await client.post(
                    f"/api/intake/{session_id}/layer2/generate",
                    headers=headers,
                )
                assert response.status_code == 400
                assert "Layer 1" in response.json()["detail"]

        asyncio.run(_run())
        _teardown()


class TestLayer3ClinicalSummaryContract:
    def test_clinical_summary_schema_with_categorized_flags(self, tmp_path, monkeypatch) -> None:
        llm_payload = ClinicalSummary(
            chief_complaint="درد قفسه سینه",
            hpi_summary="بیمار با درد قفسه سینه و تنگی نفس مراجعه کرده است.",
            pertinent_positives=["درد قفسه سینه", "تنگی نفس"],
            pertinent_negatives=["تب", "سرفه"],
            red_flags=["درد منتشر به بازو"],
            patient_questions=[
                "آیا درد با فعالیت بدتر می‌شود؟",
                "آیا سابقه بیماری قلبی در خانواده دارید؟",
            ],
        )
        captured: dict[str, str] = {}

        async def spy_generate_json(*, system_prompt: str, user_prompt: str, **kwargs) -> dict:
            if "Extract structured clinical data" in user_prompt:
                captured["extraction_system_prompt"] = system_prompt
                captured["extraction_user_prompt"] = user_prompt
                return {
                    "chief_complaint": "درد قفسه سینه",
                    "pertinent_positives": ["درد قفسه سینه", "تنگی نفس"],
                    "pertinent_negatives": ["تب", "سرفه"],
                    "red_flags": ["درد منتشر به بازو"],
                }
            if "Write a fluent Persian hpi_summary narrative" in user_prompt:
                captured["narration_system_prompt"] = system_prompt
                captured["narration_user_prompt"] = user_prompt
                return {"hpi_summary": "بیمار با درد قفسه سینه و تنگی نفس مراجعه کرده است."}
            if "Generate 2-3 targeted Persian follow-up questions" in user_prompt:
                captured["followup_system_prompt"] = system_prompt
                captured["followup_user_prompt"] = user_prompt
                return {
                    "patient_questions": [
                        "آیا درد با فعالیت بدتر می‌شود؟",
                        "آیا سابقه بیماری قلبی در خانواده دارید؟",
                    ]
                }
            raise AssertionError(f"Unexpected user prompt: {user_prompt[:120]}")

        async def fake_generate_hpi_questions(_demographics, **kwargs):
            return _layer2_result(
                HPIQuestionsResponse(
                question_strategy="Acute",
                questions=[
                    {"id": "onset", "question": "Q1", "priority": 1, "red_flag_related": False},
                    {"id": "severity", "question": "Q2", "priority": 2, "red_flag_related": False},
                ],
                )
            )

        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            monkeypatch.setattr(openrouter_service, "generate_json_primary", spy_generate_json)
            monkeypatch.setattr(
                intake_api.intake_llm_service,
                "generate_hpi_questions",
                fake_generate_hpi_questions,
            )

            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="Layer3",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id, questions = await _bootstrap_intake_through_layer2(client, headers)

                hpi_answers: dict[str, str] = {}
                for q in questions.questions:
                    hpi_answers[q.id] = "پاسخ تست"
                    await client.post(
                        f"/api/intake/{session_id}/layer2/answer",
                        json={"question_id": q.id, "answer": hpi_answers[q.id]},
                        headers=headers,
                    )

                demographics = DemographicsInput.model_validate(VALID_DEMOGRAPHICS)
                expected_user = _build_extraction_user_prompt(demographics, hpi_answers)

                response = await client.post(
                    f"/api/intake/{session_id}/layer3/generate",
                    headers=headers,
                )
                assert response.status_code == 200, response.text

                assert EXTRACTION_SYSTEM_PROMPT.splitlines()[0] in captured["extraction_system_prompt"]
                assert captured["extraction_user_prompt"] == expected_user

                summary = ClinicalSummary.model_validate(response.json()["clinical_summary"])
                assert summary.chief_complaint == "درد قفسه سینه"
                assert "درد قفسه سینه" in summary.pertinent_positives
                assert "تب" in summary.pertinent_negatives
                assert "درد منتشر به بازو" in summary.red_flags
                assert summary.patient_questions == [
                    "آیا درد با فعالیت بدتر می‌شود؟",
                    "آیا سابقه بیماری قلبی در خانواده دارید؟",
                ]
                assert response.json()["current_layer"] == 4

        asyncio.run(_run())
        _teardown()


class TestLayer4MedicalHistoryContract:
    def test_nested_medical_history_arrays_persist(self, tmp_path, monkeypatch) -> None:
        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="Layer4",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)
                await _save_layer1(client, session_id, headers)

                monkeypatch.setattr(
                    intake_api.intake_llm_service,
                    "generate_hpi_questions",
                    AsyncMock(
                        return_value=_layer2_result(
                            HPIQuestionsResponse(
                            question_strategy="Acute",
                            questions=[
                                {
                                    "id": "onset",
                                    "question": "Q",
                                    "priority": 1,
                                    "red_flag_related": False,
                                }
                            ],
                            )
                        )
                    ),
                )
                monkeypatch.setattr(
                    intake_api.intake_llm_service,
                    "generate_clinical_summary",
                    AsyncMock(
                        return_value=_clinical_summary_result(
                            ClinicalSummary(
                            chief_complaint="دل درد",
                            hpi_summary="خلاصه",
                            pertinent_positives=[],
                            pertinent_negatives=[],
                            red_flags=[],
                            )
                        )
                    ),
                )

                await client.post(f"/api/intake/{session_id}/layer2/generate", headers=headers)
                await client.post(
                    f"/api/intake/{session_id}/layer2/answer",
                    json={"question_id": "onset", "answer": "دیروز"},
                    headers=headers,
                )
                await client.post(f"/api/intake/{session_id}/layer3/generate", headers=headers)

                overview_payload = {
                    "allergies": "پنی‌سیلین، آسپرین",
                    "surgical_history": "آپاندکتومی ۱۳۹۵",
                    "family_history": "سرطان پستان (مادر)، فشار خون (پدر)",
                    "chronic_conditions": [
                        {"id": "cond-dm", "name": "دیابت نوع ۲", "duration": "۵ سال"},
                        {"id": "cond-htn", "name": "فشار خون", "duration": "۱۰ سال"},
                    ],
                    "current_medications": ["لوزارتان"],
                }

                response = await client.post(
                    f"/api/intake/{session_id}/layer4",
                    json=overview_payload,
                    headers=headers,
                )
                assert response.status_code == 200, response.text
                body = response.json()
                assert body["current_layer"] == 5
                assert body["medical_overview"]["allergies"] == overview_payload["allergies"]
                assert len(body["medical_overview"]["chronic_conditions"]) == 2

        asyncio.run(_run())
        _teardown()

    def test_medical_overview_rejects_duplicate_condition_ids(self, tmp_path, monkeypatch) -> None:
        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="Layer4 Invalid",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)
                await _save_layer1(client, session_id, headers)

                response = await client.post(
                    f"/api/intake/{session_id}/layer4",
                    json={
                        "allergies": "پنی‌سیلین",
                        "chronic_conditions": [
                            {"id": "dup", "name": "دیابت", "duration": ""},
                            {"id": "dup", "name": "فشار خون", "duration": ""},
                        ],
                    },
                    headers=headers,
                )
                assert response.status_code == 422

        asyncio.run(_run())
        _teardown()

    def test_empty_medical_overview_defaults_ok(self, tmp_path, monkeypatch) -> None:
        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="Layer4 Empty",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)
                await _save_layer1(client, session_id, headers)

                response = await client.post(
                    f"/api/intake/{session_id}/layer4",
                    json={},
                    headers=headers,
                )
                assert response.status_code == 200
                overview = response.json()["medical_overview"]
                assert overview["allergies"] == ""
                assert overview["chronic_conditions"] == []

        asyncio.run(_run())
        _teardown()


# ---------------------------------------------------------------------------
# Fallback question categories
# ---------------------------------------------------------------------------


class TestFallbackQuestionCategories:
    @pytest.mark.parametrize(
        ("complaint", "expected_strategy_fragment", "expected_question_id"),
        [
            ("درد قفسه سینه", "Chest pain", "chest_location"),
            ("دل درد", "Abdominal pain", "abd_location"),
            ("سردرد شدید", "Headache", "headache_onset"),
            ("کاهش وزن شدید", "Weight change", "weight_amount"),
            ("سرفه و تب", "Respiratory", "onset_duration"),
            ("دیابت - پیگیری", "Chronic disease", "followup_reason"),
            ("نتیجه آزمایش خون", "Laboratory result", "reason_for_testing"),
            ("درد مفصل", "Acute symptom", "location"),
        ],
    )
    def test_fallback_questions_match_complaint_category(
        self,
        complaint: str,
        expected_strategy_fragment: str,
        expected_question_id: str,
    ) -> None:
        demographics = DemographicsInput.model_validate(
            {**VALID_DEMOGRAPHICS, "chief_complaint": complaint}
        )
        result = _fallback_questions(demographics)
        assert expected_strategy_fragment in result.question_strategy
        assert any(q.id == expected_question_id for q in result.questions)
        assert len(result.questions) >= 5


# ---------------------------------------------------------------------------
# Phase 2 — LLM resiliency & timeout simulation
# ---------------------------------------------------------------------------


class TestLLMResiliency:
    def test_timeout_triggers_deterministic_fallback_not_500(self, tmp_path, monkeypatch) -> None:
        async def noop_sleep(_seconds: float) -> None:
            return None

        async def slow_then_fail(*, system_prompt: str, user_prompt: str, **kwargs) -> dict:
            await asyncio.sleep(16)  # patched to no-op; simulates >15s LLM latency
            raise OpenRouterServiceError("Simulated timeout after 16s")

        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            monkeypatch.setattr(asyncio, "sleep", noop_sleep)
            monkeypatch.setattr(openrouter_service, "generate_json", slow_then_fail)

            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="Timeout",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)
                await _save_layer1(client, session_id, headers)

                response = await client.post(
                    f"/api/intake/{session_id}/layer2/generate",
                    headers=headers,
                    timeout=30.0,
                )
                assert response.status_code == 200, response.text
                assert response.status_code != 500

                demographics = DemographicsInput.model_validate(VALID_DEMOGRAPHICS)
                expected = _fallback_questions(demographics)
                body = response.json()
                assert body["hpi_questions"]["question_strategy"] == expected.question_strategy
                assert len(body["hpi_questions"]["questions"]) == len(expected.questions)
                assert body["llm_fallback_used"] is True
                assert body["llm_error_message"]

        asyncio.run(_run())
        _teardown()

    def test_malformed_json_from_llm_triggers_layer2_fallback(self, tmp_path, monkeypatch) -> None:
        async def return_unparseable(*, system_prompt: str, user_prompt: str, **kwargs) -> dict:
            raise OpenRouterServiceError("Failed to parse JSON from OpenRouter response.")

        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            monkeypatch.setattr(openrouter_service, "generate_json", return_unparseable)

            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="Malformed",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)
                await _save_layer1(client, session_id, headers)

                response = await client.post(
                    f"/api/intake/{session_id}/layer2/generate",
                    headers=headers,
                )
                assert response.status_code == 200
                assert len(response.json()["hpi_questions"]["questions"]) >= 5

        asyncio.run(_run())
        _teardown()

    def test_markdown_wrapped_json_is_recovered_by_json_parser(self) -> None:
        wrapped = """Here is the JSON:
```json
{"question_strategy": "test", "questions": [{"id": "a", "question": "q", "priority": 1}]}
```
"""
        parsed = parse_llm_json(wrapped)
        assert parsed["question_strategy"] == "test"
        assert parsed["questions"][0]["id"] == "a"

    def test_invalid_json_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_llm_json("{not valid json}")

    def test_layer3_malformed_llm_triggers_clinical_summary_fallback(self, tmp_path, monkeypatch) -> None:
        async def fail_generate(*, system_prompt: str, user_prompt: str, **kwargs) -> dict:
            raise OpenRouterServiceError("Failed to parse JSON from OpenRouter response.")

        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            monkeypatch.setattr(openrouter_service, "generate_json", fail_generate)

            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="Layer3 Fallback",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id, questions = await _bootstrap_intake_through_layer2(client, headers)

                for q in questions.questions:
                    await client.post(
                        f"/api/intake/{session_id}/layer2/answer",
                        json={"question_id": q.id, "answer": "پاسخ بیمار"},
                        headers=headers,
                    )

                response = await client.post(
                    f"/api/intake/{session_id}/layer3/generate",
                    headers=headers,
                )
                assert response.status_code == 200, response.text
                summary = response.json()["clinical_summary"]
                assert summary["chief_complaint"] == VALID_DEMOGRAPHICS["chief_complaint"]
                assert summary["pertinent_positives"]
                assert summary["red_flags"] == []
                assert len(summary["patient_questions"]) >= 2
                assert response.json()["llm_fallback_used"] is True

        asyncio.run(_run())
        _teardown()

    def test_intake_llm_service_direct_timeout_fallback(self, monkeypatch) -> None:
        async def slow_fail(*, system_prompt: str, user_prompt: str, **kwargs) -> dict:
            await asyncio.sleep(0.05)
            raise OpenRouterServiceError("timeout")

        monkeypatch.setattr(openrouter_service, "generate_json", slow_fail)
        demographics = DemographicsInput.model_validate(VALID_DEMOGRAPHICS)

        async def _run() -> Layer2GenerationResult:
            return await intake_llm_service.generate_hpi_questions(demographics)

        result = asyncio.run(_run())
        assert result.questions.question_strategy
        assert len(result.questions.questions) >= 5
        assert result.llm_fallback_used is True


# ---------------------------------------------------------------------------
# Phase 4 — Security & session isolation
# ---------------------------------------------------------------------------


class TestSessionIsolation:
    INTAKE_WRITE_PATHS = [
        ("POST", "/layer1"),
        ("POST", "/layer2/generate"),
        ("POST", "/layer2/answer"),
        ("POST", "/layer3/generate"),
        ("POST", "/layer4"),
        ("POST", "/submit"),
    ]

    async def _owner_bootstrap(self, client: AsyncClient) -> tuple[int, dict[str, str], dict[str, str]]:
        owner_token = await _register_and_login_async(
            client,
            seed="Owner",
            password="VeryStrongPassword123!",
        )
        owner_headers = _auth_headers(owner_token)
        session_id = await _create_session(client, owner_headers)
        await _save_layer1(client, session_id, owner_headers)
        return session_id, owner_headers, owner_token

    def test_patient_cannot_read_other_patients_intake(self, tmp_path, monkeypatch) -> None:
        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                session_id, owner_headers, _ = await self._owner_bootstrap(client)

                intruder_token = await _register_and_login_async(
                    client,
                    seed="Intruder read",
                    password="VeryStrongPassword123!",
                )
                intruder_headers = _auth_headers(intruder_token)

                response = await client.get(
                    f"/api/intake/{session_id}",
                    headers=intruder_headers,
                )
                assert response.status_code == 403
                assert response.json()["detail"] == "Access denied to this session"

                owner_get = await client.get(
                    f"/api/intake/{session_id}",
                    headers=owner_headers,
                )
                assert owner_get.status_code == 200

        asyncio.run(_run())
        _teardown()

    @pytest.mark.parametrize("method,suffix", INTAKE_WRITE_PATHS)
    def test_patient_cannot_write_other_patients_intake(
        self, tmp_path, monkeypatch, method, suffix
    ) -> None:
        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                session_id, _, _ = await self._owner_bootstrap(client)

                intruder_token = await _register_and_login_async(
                    client,
                    seed=f"Intruder intruder-{suffix.replace('/', '-')}",
                    password="VeryStrongPassword123!",
                )
                intruder_headers = _auth_headers(intruder_token)

                path = f"/api/intake/{session_id}{suffix}"
                json_body: dict[str, Any] | None = None
                if suffix == "/layer1":
                    json_body = VALID_DEMOGRAPHICS
                elif suffix == "/layer2/answer":
                    json_body = {"question_id": "onset", "answer": "هک"}
                elif suffix == "/layer4":
                    json_body = {"allergies": "هک"}

                if method == "POST":
                    response = await client.post(path, json=json_body, headers=intruder_headers)
                else:
                    response = await client.request(method, path, json=json_body, headers=intruder_headers)

                assert response.status_code == 403, f"{suffix} should be forbidden"

        asyncio.run(_run())
        _teardown()

    def test_intruder_cannot_overwrite_owner_demographics(self, tmp_path, monkeypatch) -> None:
        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                session_id, owner_headers, _ = await self._owner_bootstrap(client)

                intruder_token = await _register_and_login_async(
                    client,
                    seed="Intruder overwrite",
                    password="VeryStrongPassword123!",
                )
                intruder_headers = _auth_headers(intruder_token)

                attack = await client.post(
                    f"/api/intake/{session_id}/layer1",
                    json={**VALID_DEMOGRAPHICS, "first_name": "مهاجم"},
                    headers=intruder_headers,
                )
                assert attack.status_code == 403

                owner_view = await client.get(f"/api/intake/{session_id}", headers=owner_headers)
                assert owner_view.status_code == 200
                assert owner_view.json()["demographics"]["first_name"] == "علی"

        asyncio.run(_run())
        _teardown()
