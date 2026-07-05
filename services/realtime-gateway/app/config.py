from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    realtime_host: str = "0.0.0.0"
    realtime_port: int = 8080
    nim_client: str = "mock"
    nim_realtime_ws_url: str = "ws://localhost:9000/v1/realtime?intent=transcription"
    nim_language_code: str = "ko-KR"
    nim_model: str = "nemotron-asr-streaming"
    nim_sample_rate: int = 16000
    nim_num_channels: int = 1
    nim_audio_format: str = "pcm16"
    nim_audio_chunk_ms: int = 80
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        chunk_ms = int(os.getenv("NIM_AUDIO_CHUNK_MS", "80"))
        if chunk_ms < 40 or chunk_ms > 100:
            raise ValueError("NIM_AUDIO_CHUNK_MS must be in the spike range 40..100")

        nim_client = os.getenv("NIM_CLIENT", "mock")
        if nim_client not in {"mock", "real"}:
            raise ValueError("NIM_CLIENT must be either 'mock' or 'real'")

        return cls(
            realtime_host=os.getenv("REALTIME_HOST", "0.0.0.0"),
            realtime_port=int(os.getenv("REALTIME_PORT", "8080")),
            nim_client=nim_client,
            nim_realtime_ws_url=os.getenv(
                "NIM_REALTIME_WS_URL",
                "ws://localhost:9000/v1/realtime?intent=transcription",
            ),
            nim_language_code=os.getenv("NIM_LANGUAGE_CODE", "ko-KR"),
            nim_model=os.getenv("NIM_MODEL", "nemotron-asr-streaming"),
            nim_sample_rate=int(os.getenv("NIM_SAMPLE_RATE", "16000")),
            nim_num_channels=int(os.getenv("NIM_NUM_CHANNELS", "1")),
            nim_audio_format=os.getenv("NIM_AUDIO_FORMAT", "pcm16"),
            nim_audio_chunk_ms=chunk_ms,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
