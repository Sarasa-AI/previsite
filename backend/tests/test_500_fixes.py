import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.database import Base, get_db
import app.db.database as database_module
import app.db.init_db as init_db_module

# Create a test database
@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test_fixes.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(init_db_module, "engine", engine)

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_chat_message_and_summary_flow(client, monkeypatch):
    # 1. Register
    reg_res = client.post("/api/auth/register", json={
        "name": "Test Fix",
        "password": "password123",
        "role": "patient"
    })
    assert reg_res.status_code == 200

    # 2. Login
    login_res = client.post("/api/auth/login", json={
        "name": "Test Fix",
        "password": "password123"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create Session
    session_res = client.post("/api/chat/session", json={
        "initial_complaint": "I have a headache"
    }, headers=headers)
    assert session_res.status_code == 200
    session_id = session_res.json()["id"]

    # 4. Mock LLM services to avoid real API calls
    async def mock_chat(*args, **kwargs):
        return "چطور می‌توانم کمک کنم؟"
    
    async def mock_build_summary(*args, **kwargs):
        return {
            "chief_complaint": "سردرد",
            "history_present_illness": "از دیروز شروع شده",
            "past_medical_history": "نامشخص",
            "medications": "نامشخص",
            "allergies": "نامشخص",
            "assessment": "بررسی اولیه انجام شد"
        }

    from app.services.llm_service import llm_service
    from app.services.summary_builder import summary_builder
    monkeypatch.setattr(llm_service, "chat", mock_chat)
    monkeypatch.setattr(summary_builder, "build_summary", mock_build_summary)

    # 5. Send Message (This previously caused 500)
    msg_res = client.post(f"/api/chat/{session_id}", json={
        "content": "سلام"
    }, headers=headers)
    assert msg_res.status_code == 200
    assert msg_res.json()["role"] == "assistant"

    # 6. Verify Summary exists (This also uses the Summary model)
    summary_res = client.get(f"/api/summary/{session_id}", headers=headers)
    assert summary_res.status_code == 200
    assert summary_res.json()["medical_data"]["chief_complaint"] == "سردرد"
