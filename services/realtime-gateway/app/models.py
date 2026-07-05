from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["realtime-gateway"]
    nimClient: Literal["mock", "real"]


class CreateSessionResponse(BaseModel):
    sessionId: str
    status: Literal["created"]
    eventsUrl: str


class WebRtcOffer(BaseModel):
    type: Literal["offer"]
    sdp: str = Field(min_length=1)


class WebRtcAnswer(BaseModel):
    type: Literal["answer"]
    sdp: str


class LatencyPayload(BaseModel):
    firstAudioToThisTranscriptMs: int | None = None
    lastChunkSentToThisTranscriptMs: int | None = None
    serverReceivedToBrowserSentMs: int | None = None


class TranscriptPayload(BaseModel):
    sessionId: str
    kind: Literal["transcript"] = "transcript"
    type: Literal["partial", "final"]
    text: str
    receivedAt: int
    source: Literal["nim", "mock"] = "nim"
    latency: LatencyPayload
    stablePartial: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)


class StatusPayload(BaseModel):
    sessionId: str
    kind: Literal["status"] = "status"
    state: str
    receivedAt: int


class MetricsPayload(BaseModel):
    sessionId: str
    kind: Literal["metrics"] = "metrics"
    receivedAt: int
    metrics: dict[str, int | None]


class ErrorPayload(BaseModel):
    sessionId: str
    kind: Literal["error"] = "error"
    message: str
    receivedAt: int
    raw: dict[str, Any] = Field(default_factory=dict)
