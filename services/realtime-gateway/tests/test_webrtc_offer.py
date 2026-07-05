import asyncio

import pytest
from aiortc import RTCPeerConnection
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.mark.asyncio
async def test_offer_endpoint_returns_webrtc_answer() -> None:
    client = TestClient(create_app(Settings(nim_client="mock")))
    session_id = client.post("/api/realtime/sessions").json()["sessionId"]
    peer_connection = RTCPeerConnection()
    peer_connection.addTransceiver("audio", direction="sendonly")

    offer = await peer_connection.createOffer()
    await peer_connection.setLocalDescription(offer)
    await wait_for_ice_gathering_complete(peer_connection)
    response = client.post(
        f"/api/realtime/sessions/{session_id}/offer",
        json={
            "type": peer_connection.localDescription.type,
            "sdp": peer_connection.localDescription.sdp,
        },
    )
    await peer_connection.close()

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "answer"
    assert body["sdp"].startswith("v=0")


async def wait_for_ice_gathering_complete(
    peer_connection: RTCPeerConnection,
    timeout: float = 2.0,
) -> None:
    if peer_connection.iceGatheringState == "complete":
        return

    event = asyncio.Event()

    @peer_connection.on("icegatheringstatechange")
    def on_icegatheringstatechange() -> None:
        if peer_connection.iceGatheringState == "complete":
            event.set()

    await asyncio.wait_for(event.wait(), timeout=timeout)
