from __future__ import annotations

import time
from dataclasses import dataclass


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class SessionMetrics:
    sessionCreatedAt: int
    websocketConnectedAt: int | None = None
    webrtcConnectedAt: int | None = None
    firstAudioFrameAt: int | None = None
    firstChunkSentToNimAt: int | None = None
    lastChunkSentToNimAt: int | None = None
    firstTranscriptAt: int | None = None
    latestTranscriptAt: int | None = None
    firstPartialLatencyMs: int | None = None
    latestPartialLatencyMs: int | None = None
    audioChunksSent: int = 0
    audioBytesSent: int = 0
    audioChunkDropCount: int = 0
    nimReconnectCount: int = 0

    @classmethod
    def create(cls) -> "SessionMetrics":
        return cls(sessionCreatedAt=now_ms())

    def record_audio_frame(self, timestamp_ms: int) -> None:
        if self.firstAudioFrameAt is None:
            self.firstAudioFrameAt = timestamp_ms

    def record_chunk_sent(self, byte_count: int, timestamp_ms: int) -> None:
        if self.firstChunkSentToNimAt is None:
            self.firstChunkSentToNimAt = timestamp_ms
        self.lastChunkSentToNimAt = timestamp_ms
        self.audioChunksSent += 1
        self.audioBytesSent += byte_count

    def record_transcript(self, timestamp_ms: int, is_partial: bool) -> None:
        if self.firstTranscriptAt is None:
            self.firstTranscriptAt = timestamp_ms
        self.latestTranscriptAt = timestamp_ms
        if is_partial and self.firstAudioFrameAt is not None:
            first_latency = timestamp_ms - self.firstAudioFrameAt
            if self.firstPartialLatencyMs is None:
                self.firstPartialLatencyMs = first_latency
        if is_partial and self.lastChunkSentToNimAt is not None:
            self.latestPartialLatencyMs = timestamp_ms - self.lastChunkSentToNimAt

    def transcript_latency(self, timestamp_ms: int) -> dict[str, int | None]:
        return {
            "firstAudioToThisTranscriptMs": (
                timestamp_ms - self.firstAudioFrameAt
                if self.firstAudioFrameAt is not None
                else None
            ),
            "lastChunkSentToThisTranscriptMs": (
                timestamp_ms - self.lastChunkSentToNimAt
                if self.lastChunkSentToNimAt is not None
                else None
            ),
            "serverReceivedToBrowserSentMs": 0,
        }

    def snapshot(self) -> dict[str, int | None]:
        return {
            "sessionCreatedAt": self.sessionCreatedAt,
            "websocketConnectedAt": self.websocketConnectedAt,
            "webrtcConnectedAt": self.webrtcConnectedAt,
            "firstAudioFrameAt": self.firstAudioFrameAt,
            "firstChunkSentToNimAt": self.firstChunkSentToNimAt,
            "lastChunkSentToNimAt": self.lastChunkSentToNimAt,
            "firstTranscriptAt": self.firstTranscriptAt,
            "latestTranscriptAt": self.latestTranscriptAt,
            "firstPartialLatencyMs": self.firstPartialLatencyMs,
            "latestPartialLatencyMs": self.latestPartialLatencyMs,
            "audioChunksSent": self.audioChunksSent,
            "audioBytesSent": self.audioBytesSent,
            "audioChunkDropCount": self.audioChunkDropCount,
            "nimReconnectCount": self.nimReconnectCount,
        }
