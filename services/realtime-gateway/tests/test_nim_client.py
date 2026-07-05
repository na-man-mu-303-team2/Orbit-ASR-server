import base64

import pytest

from app.config import Settings
from app.nim_client import (
    MockNimClient,
    build_append_payload,
    build_session_update,
    normalize_transcript,
    parse_nim_transcript_event,
)


def test_append_payload_base64_encodes_pcm16_audio() -> None:
    payload = build_append_payload(b"\x01\x02\x03\x04")

    assert payload == {
        "type": "input_audio_buffer.append",
        "audio": base64.b64encode(b"\x01\x02\x03\x04").decode("ascii"),
    }


def test_session_update_uses_korean_nemotron_realtime_settings() -> None:
    payload = build_session_update(Settings())

    assert payload["type"] == "transcription_session.update"
    assert payload["session"]["input_audio_format"] == "pcm16"
    assert payload["session"]["input_audio_transcription"] == {
        "language": "ko-KR",
        "model": "nemotron-asr-streaming",
    }
    assert payload["session"]["input_audio_params"] == {
        "sample_rate_hz": 16000,
        "num_channels": 1,
    }


def test_parse_nim_transcript_event_handles_partial_and_final_shapes() -> None:
    partial = parse_nim_transcript_event(
        {"type": "response.audio_transcript.delta", "delta": " 안녕   하세요 "}
    )
    final = parse_nim_transcript_event(
        {"type": "response.audio_transcript.final", "transcript": "테스트입니다"}
    )

    assert partial is not None
    assert partial.type == "partial"
    assert partial.text == "안녕 하세요"
    assert final is not None
    assert final.type == "final"
    assert final.text == "테스트입니다"


def test_transcript_normalization_collapses_repeated_whitespace() -> None:
    assert normalize_transcript(" 안녕   하세요\n테스트\t입니다 ") == "안녕 하세요 테스트 입니다"


@pytest.mark.asyncio
async def test_mock_nim_emits_partial_and_final_transcripts() -> None:
    client = MockNimClient()
    await client.connect()

    for index in range(6):
        await client.send_audio(bytes([index]) * 2560, sent_at_ms=index)

    events = []
    async for event in client.events():
        events.append(event)
        if len(events) == 2:
            await client.close()

    assert [event.type for event in events] == ["partial", "final"]
    assert events[0].text.startswith("안녕하세요")
