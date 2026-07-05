import base64

import pytest

from app.nim_client import MockNimClient, build_append_payload, normalize_transcript


def test_append_payload_base64_encodes_pcm16_audio() -> None:
    payload = build_append_payload(b"\x01\x02\x03\x04")

    assert payload == {
        "type": "input_audio_buffer.append",
        "audio": base64.b64encode(b"\x01\x02\x03\x04").decode("ascii"),
    }


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
