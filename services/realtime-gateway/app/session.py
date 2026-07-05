from __future__ import annotations

import asyncio
import json
import secrets
from typing import Any

from fastapi import WebSocket

from .audio import AudioFrameConverter, Pcm16Chunker, pcm16_chunk_size_bytes
from .config import Settings
from .metrics import SessionMetrics, now_ms
from .models import ErrorPayload, MetricsPayload, StatusPayload, TranscriptPayload, WebRtcAnswer
from .nim_client import NimClientProtocol, create_nim_client, normalize_transcript
from .webrtc_ports import constrained_webrtc_udp_ports


def _log_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


class RealtimeSpikeSession:
    def __init__(
        self,
        session_id: str,
        settings: Settings,
        nim_client: NimClientProtocol | None = None,
    ) -> None:
        self.session_id = session_id
        self.settings = settings
        self.peer_connection: Any | None = None
        self.events: set[WebSocket] = set()
        self.nim_client = nim_client or create_nim_client(settings)
        self.metrics = SessionMetrics.create()
        self.tasks: set[asyncio.Task[Any]] = set()
        self._stopped = False
        self._last_partial = ""

    async def handle_offer(self, sdp: str, type: str) -> WebRtcAnswer:
        from aiortc import RTCSessionDescription
        from aiortc.rtcpeerconnection import RTCPeerConnection

        pc = RTCPeerConnection()
        self.peer_connection = pc

        @pc.on("connectionstatechange")
        async def on_connectionstatechange() -> None:
            state = pc.connectionState
            timestamp = now_ms()
            if state == "connected":
                self.metrics.webrtcConnectedAt = timestamp
            _log_json(
                {
                    "sessionId": self.session_id,
                    "event": "webrtc_connection_state",
                    "state": state,
                    "timestamp": timestamp,
                }
            )
            await self.broadcast_status(f"webrtc_{state}")

        @pc.on("track")
        def on_track(track: Any) -> None:
            if track.kind == "audio":
                self.on_audio_track(track)

        await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type=type))
        answer = await pc.createAnswer()
        async with constrained_webrtc_udp_ports(
            self.settings.webrtc_udp_port_min,
            self.settings.webrtc_udp_port_max,
        ):
            await pc.setLocalDescription(answer)
            await _wait_for_ice_gathering_complete(pc)
        return WebRtcAnswer(type="answer", sdp=pc.localDescription.sdp)

    async def register_websocket(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.events.add(websocket)
        self.metrics.websocketConnectedAt = now_ms()
        await websocket.send_json(self.status_event("websocket_connected"))
        await websocket.send_json(self.metrics_event())

    async def unregister_websocket(self, websocket: WebSocket) -> None:
        self.events.discard(websocket)

    async def broadcast(self, event: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for websocket in list(self.events):
            try:
                await websocket.send_json(event)
            except RuntimeError:
                dead.append(websocket)
        for websocket in dead:
            self.events.discard(websocket)

    async def broadcast_status(self, state: str) -> None:
        await self.broadcast(self.status_event(state))

    def status_event(self, state: str) -> dict[str, Any]:
        return StatusPayload(
            sessionId=self.session_id,
            state=state,
            receivedAt=now_ms(),
        ).model_dump()

    def metrics_event(self) -> dict[str, Any]:
        return MetricsPayload(
            sessionId=self.session_id,
            receivedAt=now_ms(),
            metrics=self.metrics.snapshot(),
        ).model_dump()

    def on_audio_track(self, track: Any) -> None:
        task = asyncio.create_task(self._audio_loop(track))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _audio_loop(self, track: Any) -> None:
        await self.nim_client.connect()
        nim_task = asyncio.create_task(self._nim_event_loop())
        self.tasks.add(nim_task)
        nim_task.add_done_callback(self.tasks.discard)

        converter = AudioFrameConverter(self.settings.nim_sample_rate)
        chunker = Pcm16Chunker(
            pcm16_chunk_size_bytes(
                self.settings.nim_sample_rate,
                self.settings.nim_num_channels,
                self.settings.nim_audio_chunk_ms,
            )
        )

        await self.broadcast_status("audio_track_started")
        while not self._stopped:
            frame = await track.recv()
            received_at = now_ms()
            self.metrics.record_audio_frame(received_at)
            pcm16 = converter.to_pcm16(frame)
            for chunk in chunker.append(pcm16):
                sent_at = now_ms()
                await self.nim_client.send_audio(chunk, sent_at)
                self.metrics.record_chunk_sent(len(chunk), sent_at)
                _log_json(
                    {
                        "sessionId": self.session_id,
                        "event": "audio_chunk_sent_to_nim",
                        "chunkMs": self.settings.nim_audio_chunk_ms,
                        "bytes": len(chunk),
                        "audioChunksSent": self.metrics.audioChunksSent,
                        "timestamp": sent_at,
                    }
                )
                await self.broadcast(self.metrics_event())

    async def _nim_event_loop(self) -> None:
        try:
            async for event in self.nim_client.events():
                await self._handle_transcript(event.type, event.text, event.source, event.raw)
        except Exception as exc:
            await self.broadcast(
                ErrorPayload(
                    sessionId=self.session_id,
                    message="nim_event_loop_error",
                    receivedAt=now_ms(),
                    raw={"error": str(exc)},
                ).model_dump()
            )

    async def _handle_transcript(
        self,
        transcript_type: str,
        text: str,
        source: str,
        raw: dict[str, Any],
    ) -> None:
        timestamp = now_ms()
        normalized = normalize_transcript(text)
        is_partial = transcript_type == "partial"
        stable_partial = is_partial and normalized == self._last_partial
        if is_partial:
            self._last_partial = normalized

        self.metrics.record_transcript(timestamp, is_partial=is_partial)
        _log_json(
            {
                "sessionId": self.session_id,
                "event": "transcript_received",
                "type": transcript_type,
                "textLength": len(normalized),
                "firstAudioToThisTranscriptMs": self.metrics.transcript_latency(timestamp)[
                    "firstAudioToThisTranscriptMs"
                ],
                "lastChunkSentToThisTranscriptMs": self.metrics.transcript_latency(timestamp)[
                    "lastChunkSentToThisTranscriptMs"
                ],
                "timestamp": timestamp,
            }
        )
        await self.broadcast(
            TranscriptPayload(
                sessionId=self.session_id,
                type=transcript_type,  # type: ignore[arg-type]
                text=normalized,
                receivedAt=timestamp,
                source=source,  # type: ignore[arg-type]
                latency=self.metrics.transcript_latency(timestamp),
                stablePartial=stable_partial,
                raw=raw,
            ).model_dump()
        )
        await self.broadcast(self.metrics_event())

    async def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True

        for task in list(self.tasks):
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()

        if self.peer_connection is not None:
            await self.peer_connection.close()
        await self.nim_client.close()

        for websocket in list(self.events):
            await websocket.close()
        self.events.clear()


class SessionManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.sessions: dict[str, RealtimeSpikeSession] = {}

    def create_session(self) -> RealtimeSpikeSession:
        session_id = f"rt_{secrets.token_urlsafe(12)}"
        session = RealtimeSpikeSession(session_id=session_id, settings=self.settings)
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> RealtimeSpikeSession | None:
        return self.sessions.get(session_id)

    async def stop_session(self, session_id: str) -> bool:
        session = self.sessions.pop(session_id, None)
        if session is None:
            return False
        await session.stop()
        return True


async def _wait_for_ice_gathering_complete(peer_connection: Any, timeout: float = 2.0) -> None:
    if peer_connection.iceGatheringState == "complete":
        return

    event = asyncio.Event()

    @peer_connection.on("icegatheringstatechange")
    def on_icegatheringstatechange() -> None:
        if peer_connection.iceGatheringState == "complete":
            event.set()

    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
    except TimeoutError:
        _log_json(
            {
                "event": "ice_gathering_timeout",
                "state": peer_connection.iceGatheringState,
                "timestamp": now_ms(),
            }
        )
