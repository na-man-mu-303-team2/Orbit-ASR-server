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


def test_websocket_receives_initial_status_and_metrics() -> None:
    client = TestClient(create_app(Settings(nim_client="mock")))
    session = client.post("/api/realtime/sessions").json()

    with client.websocket_connect(session["eventsUrl"]) as websocket:
        status = websocket.receive_json()
        metrics = websocket.receive_json()

    assert status["kind"] == "status"
    assert status["state"] == "websocket_connected"
    assert metrics["kind"] == "metrics"
    assert metrics["metrics"]["websocketConnectedAt"] is not None


def test_stop_session_endpoint_cleans_up_session() -> None:
    client = TestClient(create_app(Settings(nim_client="mock")))
    session_id = client.post("/api/realtime/sessions").json()["sessionId"]

    response = client.post(f"/api/realtime/sessions/{session_id}/stop")
    missing = client.post(f"/api/realtime/sessions/{session_id}/stop")

    assert response.status_code == 200
    assert response.json() == {"sessionId": session_id, "status": "stopped"}
    assert missing.status_code == 404
