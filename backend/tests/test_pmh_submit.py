from fastapi.testclient import TestClient

from app.schemas.pmh import PMHAnswer
from app.services.pmh_service import (
    format_pmh_for_prompt,
    get_patient_overview,
    get_patient_pmh,
)
from tests.test_mvp_flow import _create_client, _national_id_from_seed


def _sample_overview_submission(patient_id: int) -> dict:
    return {
        "patient_id": patient_id,
        "overview": {
            "allergies": "پنی‌سیلین",
            "surgical_history": "آپاندکتومی ۱۳۹۵",
            "family_history": "فشار خون (پدر)",
            "chronic_conditions": [
                {"id": "cond-diabetes", "name": "دیابت نوع ۲", "duration": "۵ سال"},
                {"id": "cond-htn", "name": "فشار خون", "duration": "۱۰ سال"},
            ],
            "current_medications": ["متفورمین ۵۰۰mg"],
        },
    }


def _register_patient(client: TestClient, *, seed: str) -> tuple[str, int]:
    national_id = _national_id_from_seed(seed)
    password = "VeryStrongPassword123!"
    register_response = client.post(
        "/api/auth/register",
        json={
            "national_id": national_id,
            "password": password,
            "role": "patient",
        },
    )
    assert register_response.status_code == 200, register_response.text
    patient_id = register_response.json()["id"]

    login_response = client.post(
        "/api/auth/login",
        json={"national_id": national_id, "password": password},
    )
    assert login_response.status_code == 200, login_response.text
    token = login_response.json()["access_token"]
    return token, patient_id


def test_patient_can_submit_pmh(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    token, patient_id = _register_patient(client, seed="pmh-submit-patient")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/pmh/submit",
        json=_sample_overview_submission(patient_id),
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["patient_id"] == patient_id
    assert body["overview"]["chronic_conditions"][0]["name"] == "دیابت نوع ۲"
    assert body["last_updated"] is not None
    client._async_cleanup()


def test_doctor_cannot_submit_pmh(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)

    login_response = client.post(
        "/api/auth/login",
        json={"national_id": "bagherzade", "password": "0808"},
    )
    assert login_response.status_code == 200, login_response.text
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/pmh/submit",
        json=_sample_overview_submission(patient_id=1),
        headers=headers,
    )

    assert response.status_code == 403
    client._async_cleanup()


def test_patient_cannot_submit_for_other_patient(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    token, _patient_id = _register_patient(client, seed="pmh-owner")
    _, other_patient_id = _register_patient(client, seed="pmh-other")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/pmh/submit",
        json=_sample_overview_submission(other_patient_id),
        headers=headers,
    )

    assert response.status_code == 403
    client._async_cleanup()


def test_pmh_submit_upserts_existing_row(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    token, patient_id = _register_patient(client, seed="pmh-upsert")
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post(
        "/api/pmh/submit",
        json=_sample_overview_submission(patient_id),
        headers=headers,
    )
    assert first.status_code == 200, first.text

    updated_payload = _sample_overview_submission(patient_id)
    updated_payload["overview"]["chronic_conditions"] = updated_payload["overview"]["chronic_conditions"][:1]

    second = client.post(
        "/api/pmh/submit",
        json=updated_payload,
        headers=headers,
    )
    assert second.status_code == 200, second.text
    assert len(second.json()["overview"]["chronic_conditions"]) == 1
    assert second.json()["last_updated"] >= first.json()["last_updated"]
    client._async_cleanup()


def test_patient_can_get_own_overview(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    token, patient_id = _register_patient(client, seed="pmh-get-overview")
    headers = {"Authorization": f"Bearer {token}"}

    submit = client.post(
        "/api/pmh/submit",
        json=_sample_overview_submission(patient_id),
        headers=headers,
    )
    assert submit.status_code == 200, submit.text

    response = client.get(f"/api/pmh/overview/{patient_id}", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["overview"]["allergies"] == "پنی‌سیلین"
    client._async_cleanup()


def test_pmh_schema_is_deprecated(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    response = client.get("/api/pmh/schema")
    assert response.status_code == 410
    client._async_cleanup()


async def test_get_patient_pmh_returns_none_when_missing(db) -> None:
    result = await get_patient_pmh(db, patient_id=99999)
    assert result is None


async def test_get_patient_overview_returns_none_when_missing(db) -> None:
    result = await get_patient_overview(db, patient_id=99999)
    assert result is None


def test_format_pmh_for_prompt_includes_selected_only() -> None:
    answers = [
        PMHAnswer(
            category_id="cat_cardio",
            is_selected=True,
            question_responses={
                "pmh_cardio_cad_001": True,
                "pmh_cardio_cad_001_date": "1398",
            },
        ),
        PMHAnswer(
            category_id="cat_pulm",
            is_selected=False,
            question_responses={"pmh_pulm_asthma_001": True},
        ),
    ]

    text = format_pmh_for_prompt(answers)

    assert "[cat_cardio]" in text
    assert "History of Myocardial Infarction / Coronary Artery Disease" in text
    assert "Date of Event: 1398" in text
    assert "cat_pulm" not in text
    assert "pmh_cardio_cad_001" not in text


def test_format_pmh_for_prompt_falls_back_to_id_for_unknown_questions() -> None:
    answers = [
        PMHAnswer(
            category_id="cat_cardio",
            is_selected=True,
            question_responses={"unknown_question_id": True, "unknown_followup": "2020"},
        ),
    ]

    text = format_pmh_for_prompt(answers)

    assert "- unknown_question_id: positive" in text
    assert "- unknown_followup: 2020" in text
