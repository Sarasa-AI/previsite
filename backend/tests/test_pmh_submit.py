from fastapi.testclient import TestClient

from app.schemas.pmh import PMHAnswer
from app.services.pmh_service import format_pmh_for_prompt, get_patient_pmh
from tests.conftest import setup_async_test_db, teardown_test_db
from tests.test_mvp_flow import _create_client, _national_id_from_seed


def _sample_submission(patient_id: int) -> dict:
    return {
        "patient_id": patient_id,
        "answers": [
            {
                "category_id": "cat_cardio",
                "is_selected": True,
                "question_responses": {
                    "pmh_cardio_cad_001": True,
                    "pmh_cardio_cad_001_followup_stent": "2020",
                },
            },
            {
                "category_id": "cat_pulm",
                "is_selected": False,
                "question_responses": {},
            },
        ],
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
        json=_sample_submission(patient_id),
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["patient_id"] == patient_id
    assert body["answer_count"] == 2
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
        json=_sample_submission(patient_id=1),
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
        json=_sample_submission(other_patient_id),
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
        json=_sample_submission(patient_id),
        headers=headers,
    )
    assert first.status_code == 200, first.text

    updated_payload = _sample_submission(patient_id)
    updated_payload["answers"] = updated_payload["answers"][:1]

    second = client.post(
        "/api/pmh/submit",
        json=updated_payload,
        headers=headers,
    )
    assert second.status_code == 200, second.text
    assert second.json()["answer_count"] == 1
    assert second.json()["last_updated"] >= first.json()["last_updated"]
    client._async_cleanup()


async def test_get_patient_pmh_returns_none_when_missing(tmp_path, monkeypatch) -> None:
    engine = await setup_async_test_db(tmp_path, monkeypatch)
    from app.db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await get_patient_pmh(db, patient_id=99999)
        assert result is None

    teardown_test_db()
    await engine.dispose()


def test_format_pmh_for_prompt_includes_selected_only() -> None:
    answers = [
        PMHAnswer(
            category_id="cat_cardio",
            is_selected=True,
            question_responses={"pmh_cardio_cad_001": True, "followup": "2020"},
        ),
        PMHAnswer(
            category_id="cat_pulm",
            is_selected=False,
            question_responses={"pmh_pulm_asthma_001": True},
        ),
    ]

    text = format_pmh_for_prompt(answers)

    assert "cat_cardio" in text
    assert "pmh_cardio_cad_001" in text
    assert "2020" in text
    assert "cat_pulm" not in text
