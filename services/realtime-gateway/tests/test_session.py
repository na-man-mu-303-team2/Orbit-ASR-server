import pytest

from app.config import Settings
from app.nim_client import MockNimClient
from app.session import RealtimeSpikeSession


@pytest.mark.asyncio
async def test_session_stop_is_idempotent() -> None:
    session = RealtimeSpikeSession(
        session_id="rt_test",
        settings=Settings(nim_client="mock"),
        nim_client=MockNimClient(),
    )

    await session.stop()
    await session.stop()

    assert session.tasks == set()
