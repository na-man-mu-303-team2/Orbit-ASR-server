from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_returns_gateway_status() -> None:
    client = TestClient(create_app(Settings(nim_client="mock")))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "realtime-gateway",
        "nimClient": "mock",
    }


def test_create_session_returns_session_id_and_events_url() -> None:
    client = TestClient(create_app(Settings(nim_client="mock")))

    response = client.post("/api/realtime/sessions")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "created"
    assert body["sessionId"].startswith("rt_")
    assert body["eventsUrl"] == f"/api/realtime/sessions/{body['sessionId']}/events"
