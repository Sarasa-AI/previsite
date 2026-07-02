import app.api.intake as intake_api
from app.schemas.intake import ClinicalSummary, HPIQuestionsResponse
from app.services.intake_llm import ClinicalSummaryResult, Layer2GenerationResult
from tests.test_mvp_flow import _create_client, _register_and_login


def test_intake_four_layer_flow(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)

    async def fake_generate_hpi_questions(demographics, **kwargs):
        return Layer2GenerationResult(
            questions=HPIQuestionsResponse(
            question_strategy="Acute symptom workflow",
            questions=[
                {"id": "onset", "question": "از چه زمانی شروع شده؟", "priority": 1, "red_flag_related": False},
                {"id": "severity", "question": "شدت را از ۰ تا ۱۰ چقدر می‌دانید؟", "priority": 2, "red_flag_related": False},
            ],
            )
        )

    async def fake_generate_clinical_summary(demographics, hpi_answers, **kwargs):
        return ClinicalSummaryResult(
            summary=ClinicalSummary(
            chief_complaint="درد شکم",
            hpi_summary="بیمار با درد شکم مراجعه کرده است.",
            pertinent_positives=["درد شکم"],
            pertinent_negatives=[],
            red_flags=[],
            )
        )

    monkeypatch.setattr(intake_api.intake_llm_service, "generate_hpi_questions", fake_generate_hpi_questions)
    monkeypatch.setattr(intake_api.intake_llm_service, "generate_clinical_summary", fake_generate_clinical_summary)

    token = _register_and_login(
        client,
        seed="Intake Patient",
        password="VeryStrongPassword123!",
    )
    headers = {"Authorization": f"Bearer {token}"}

    session_response = client.post(
        "/api/chat/session",
        json={"initial_complaint": "دل درد"},
        headers=headers,
    )
    session_id = session_response.json()["id"]

    layer1 = client.post(
        f"/api/intake/{session_id}/layer1",
        json={
            "first_name": "علی",
            "last_name": "رضایی",
            "national_id": "0499370899",
            "insurance_provider": "تأمین اجتماعی",
            "age": 34,
            "sex": "male",
            "weight": 75,
            "height": 175,
            "chief_complaint": "دل درد",
        },
        headers=headers,
    )
    assert layer1.status_code == 200
    assert layer1.json()["current_layer"] == 2

    layer2 = client.post(f"/api/intake/{session_id}/layer2/generate", headers=headers)
    assert layer2.status_code == 200
    assert len(layer2.json()["hpi_questions"]["questions"]) == 2

    answer1 = client.post(
        f"/api/intake/{session_id}/layer2/answer",
        json={"question_id": "onset", "answer": "۲ روز پیش"},
        headers=headers,
    )
    assert answer1.status_code == 200

    answer2 = client.post(
        f"/api/intake/{session_id}/layer2/answer",
        json={"question_id": "severity", "answer": "۷ از ۱۰"},
        headers=headers,
    )
    assert answer2.status_code == 200
    assert answer2.json()["current_layer"] == 3

    layer3 = client.post(f"/api/intake/{session_id}/layer3/generate", headers=headers)
    assert layer3.status_code == 200
    assert layer3.json()["clinical_summary"]["chief_complaint"] == "درد شکم"

    layer4 = client.post(
        f"/api/intake/{session_id}/layer4",
        json={
            "allergies": "پنی‌سیلین",
            "chronic_conditions": [
                {"id": "cond-1", "name": "دیابت", "duration": "۳ سال"},
            ],
            "surgical_history": "هیچ‌کدام",
            "family_history": "فشار خون",
            "current_medications": ["متفورمین"],
        },
        headers=headers,
    )
    assert layer4.status_code == 200

    submit = client.post(f"/api/intake/{session_id}/submit", headers=headers)
    assert submit.status_code == 200

    summary = client.get(f"/api/summary/{session_id}", headers=headers)
    assert summary.status_code == 200
    body = summary.json()
    assert body["intake"] is not None
    assert body["medical_data"]["chief_complaint"] == "درد شکم"

    from app.main import app as fastapi_app
    fastapi_app.dependency_overrides.clear()
    client.close()
