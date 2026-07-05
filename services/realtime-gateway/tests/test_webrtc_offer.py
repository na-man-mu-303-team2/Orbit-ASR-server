import asyncio

import pytest
from aiortc import RTCPeerConnection
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.webrtc_ports import constrained_webrtc_udp_ports


@pytest.mark.asyncio
async def test_offer_endpoint_returns_webrtc_answer() -> None:
    settings = Settings(nim_client="mock", webrtc_udp_port_min=40000, webrtc_udp_port_max=40099)
    client = TestClient(create_app(settings))
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


@pytest.mark.asyncio
async def test_constrained_webrtc_udp_ports_binds_inside_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loop = asyncio.get_running_loop()
    requested_ports: list[int] = []

    class FakeTransport(asyncio.DatagramTransport):
        def get_extra_info(self, name: str, default: object = None) -> object:
            if name == "sockname":
                return ("127.0.0.1", requested_ports[-1])
            return default

    async def fake_create_datagram_endpoint(
        protocol_factory: object,
        local_addr: tuple[str, int] | None = None,
        remote_addr: tuple[str, int] | None = None,
        **kwargs: object,
    ) -> tuple[asyncio.DatagramTransport, asyncio.DatagramProtocol]:
        assert local_addr is not None
        requested_ports.append(local_addr[1])
        return FakeTransport(), asyncio.DatagramProtocol()

    monkeypatch.setattr(loop, "create_datagram_endpoint", fake_create_datagram_endpoint)

    async with constrained_webrtc_udp_ports(40100, 40110):
        transport, _ = await loop.create_datagram_endpoint(
            asyncio.DatagramProtocol,
            local_addr=("127.0.0.1", 0),
        )

    port = transport.get_extra_info("sockname")[1]
    assert 40100 <= port <= 40110
    assert requested_ports == [port]


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
