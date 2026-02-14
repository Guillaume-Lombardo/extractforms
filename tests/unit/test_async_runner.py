from __future__ import annotations

import asyncio

from extractforms.async_runner import run_async


async def _identity(value: int) -> int:
    await asyncio.sleep(0)
    return value


def test_run_async_from_sync_context() -> None:
    assert run_async(_identity(7)) == 7


def test_run_async_with_running_loop() -> None:
    async def _nested() -> int:
        await asyncio.sleep(0)
        return run_async(_identity(11))

    assert asyncio.run(_nested()) == 11
