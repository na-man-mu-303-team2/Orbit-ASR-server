import asyncio
from fractions import Fraction
from typing import Any

import av
import pytest

from app.config import Settings
from app.nim_client import MockNimClient
from app.session import RealtimeSpikeSession


class FakeWebSocket:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def send_json(self, event: dict[str, Any]) -> None:
        self.events.append(event)

    async def close(self) -> None:
        return None


class SilenceAudioTrack:
    kind = "audio"

    def __init__(self) -> None:
        self._timestamp = 0

    async def recv(self) -> av.AudioFrame:
        await asyncio.sleep(0.005)
        samples = 960
        frame = av.AudioFrame(format="s16", layout="mono", samples=samples)
        frame.sample_rate = 48000
        frame.time_base = Fraction(1, 48000)
        frame.pts = self._timestamp
        frame.planes[0].update(b"\x00\x00" * samples)
        self._timestamp += samples
        return frame


@pytest.mark.asyncio
async def test_audio_track_streams_to_mock_transcript_events() -> None:
    websocket = FakeWebSocket()
    session = RealtimeSpikeSession(
        session_id="rt_flow",
        settings=Settings(nim_client="mock"),
        nim_client=MockNimClient(),
    )
    session.events.add(websocket)  # type: ignore[arg-type]

    session.on_audio_track(SilenceAudioTrack())

    for _ in range(100):
        transcript_events = [
            event for event in websocket.events if event.get("kind") == "transcript"
        ]
        if any(event["type"] == "final" for event in transcript_events):
            break
        await asyncio.sleep(0.02)

    await session.stop()

    transcript_events = [event for event in websocket.events if event.get("kind") == "transcript"]
    assert [event["type"] for event in transcript_events] == ["partial", "final"]
    assert transcript_events[0]["text"].startswith("안녕하세요")
    assert transcript_events[0]["latency"]["firstAudioToThisTranscriptMs"] is not None
    assert session.metrics.audioChunksSent >= 6
