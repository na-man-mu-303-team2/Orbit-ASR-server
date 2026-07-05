from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

_ice_gather_lock = asyncio.Lock()


@asynccontextmanager
async def constrained_webrtc_udp_ports(
    min_port: int,
    max_port: int,
) -> AsyncIterator[None]:
    """Constrain aioice's port-0 UDP binds during aiortc ICE gathering."""
    loop = asyncio.get_running_loop()
    original_create_datagram_endpoint = loop.create_datagram_endpoint

    async with _ice_gather_lock:
        async def create_datagram_endpoint(
            protocol_factory: Callable[[], asyncio.DatagramProtocol],
            local_addr: tuple[str, int] | None = None,
            remote_addr: tuple[str, int] | None = None,
            **kwargs: Any,
        ) -> tuple[asyncio.BaseTransport, asyncio.DatagramProtocol]:
            if local_addr is None or local_addr[1] != 0:
                return await original_create_datagram_endpoint(
                    protocol_factory,
                    local_addr=local_addr,
                    remote_addr=remote_addr,
                    **kwargs,
                )

            host = local_addr[0]
            ports = list(range(min_port, max_port + 1))
            random.shuffle(ports)
            last_error: OSError | None = None

            for port in ports:
                try:
                    return await original_create_datagram_endpoint(
                        protocol_factory,
                        local_addr=(host, port),
                        remote_addr=remote_addr,
                        **kwargs,
                    )
                except OSError as exc:
                    last_error = exc

            raise OSError(
                f"no available UDP ports in configured WebRTC range {min_port}-{max_port}"
            ) from last_error

        loop.create_datagram_endpoint = create_datagram_endpoint  # type: ignore[method-assign]
        try:
            yield
        finally:
            loop.create_datagram_endpoint = original_create_datagram_endpoint  # type: ignore[method-assign]
