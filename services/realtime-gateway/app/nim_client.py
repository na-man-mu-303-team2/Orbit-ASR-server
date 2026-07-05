from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

import websockets

from .config import Settings


@dataclass(frozen=True)
class TranscriptEvent:
    type: str
    text: str
    raw: dict[str, Any] = field(default_factory=dict)
    source: str = "nim"


class NimClientProtocol(Protocol):
    async def connect(self) -> None: ...

    async def send_audio(self, pcm16: bytes, sent_at_ms: int) -> None: ...

    async def events(self) -> AsyncIterator[TranscriptEvent]: ...

    async def close(self) -> None: ...


def build_session_update(settings: Settings) -> dict[str, Any]:
    return {
        "type": "transcription_session.update",
        "session": {
            "modalities": ["text"],
            "input_audio_format": settings.nim_audio_format,
            "input_audio_transcription": {
                "language": settings.nim_language_code,
                "model": settings.nim_model,
            },
            "input_audio_params": {
                "sample_rate_hz": settings.nim_sample_rate,
                "num_channels": settings.nim_num_channels,
            },
            "recognition_config": {
                "enable_automatic_punctuation": True,
                "enable_verbatim_transcripts": True,
            },
            "word_boosting": {
                "enabled": False,
                "terms": [],
            },
        },
    }


def build_append_payload(pcm16: bytes) -> dict[str, str]:
    return {
        "type": "input_audio_buffer.append",
        "audio": base64.b64encode(pcm16).decode("ascii"),
    }


def normalize_transcript(text: str) -> str:
    return " ".join(text.split())


def parse_nim_transcript_event(payload: dict[str, Any]) -> TranscriptEvent | None:
    event_type = str(payload.get("type", ""))
    text = _extract_text(payload)
    if not text:
        return None

    transcript_type = "final" if "final" in event_type or payload.get("is_final") else "partial"
    return TranscriptEvent(
        type=transcript_type,
        text=normalize_transcript(text),
        raw=payload,
        source="nim",
    )


def _extract_text(payload: dict[str, Any]) -> str:
    for key in ("text", "transcript"):
        value = payload.get(key)
        if isinstance(value, str):
            return value

    delta = payload.get("delta")
    if isinstance(delta, str):
        return delta
    if isinstance(delta, dict):
        for key in ("text", "transcript"):
            value = delta.get(key)
            if isinstance(value, str):
                return value

    item = payload.get("item")
    if isinstance(item, dict):
        for key in ("text", "transcript"):
            value = item.get(key)
            if isinstance(value, str):
                return value

    return ""


class RealNimClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._ws: Any | None = None
        self._closed = False

    async def connect(self) -> None:
        self._ws = await websockets.connect(self._settings.nim_realtime_ws_url)
        await self._ws.send(json.dumps(build_session_update(self._settings)))

    async def send_audio(self, pcm16: bytes, sent_at_ms: int) -> None:
        if self._ws is None:
            raise RuntimeError("NIM client is not connected")
        await self._ws.send(json.dumps(build_append_payload(pcm16)))

    async def events(self) -> AsyncIterator[TranscriptEvent]:
        if self._ws is None:
            return
        async for raw_message in self._ws:
            try:
                payload = json.loads(raw_message)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            event = parse_nim_transcript_event(payload)
            if event is not None:
                yield event

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._ws is not None:
            await self._ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
            await self._ws.close()


class MockNimClient:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue()
        self._chunk_count = 0
        self._connected = False
        self._closed = False

    async def connect(self) -> None:
        self._connected = True

    async def send_audio(self, pcm16: bytes, sent_at_ms: int) -> None:
        if not self._connected:
            raise RuntimeError("mock NIM client is not connected")
        if self._closed:
            return

        self._chunk_count += 1
        await asyncio.sleep(0.02)
        if self._chunk_count == 3:
            await self._queue.put(
                TranscriptEvent(
                    type="partial",
                    text="안녕하세요 실시간 전사 테스트",
                    raw={"mockChunkCount": self._chunk_count},
                    source="mock",
                )
            )
        elif self._chunk_count == 6:
            await self._queue.put(
                TranscriptEvent(
                    type="final",
                    text="안녕하세요 실시간 전사 테스트입니다.",
                    raw={"mockChunkCount": self._chunk_count},
                    source="mock",
                )
            )

    async def events(self) -> AsyncIterator[TranscriptEvent]:
        while True:
            event = await self._queue.get()
            if event is None:
                break
            yield event

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._queue.put(None)


def create_nim_client(settings: Settings) -> NimClientProtocol:
    if settings.nim_client == "real":
        return RealNimClient(settings)
    return MockNimClient()
