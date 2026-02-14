"""Helpers to run async operations from sync or async contexts."""

from __future__ import annotations

import asyncio
import threading
from queue import Queue
from typing import TYPE_CHECKING, Any

from extractforms.exceptions import AsyncExecutionError

if TYPE_CHECKING:
    from collections.abc import Coroutine


def _run_in_background_thread[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine in a dedicated thread with its own event loop.

    Args:
        coro: The coroutine to run.

    Raises:
        AsyncExecutionError: If the coroutine raises an exception.

    Returns:
        The result of the coroutine.
    """
    output: Queue[T | BaseException] = Queue(maxsize=1)

    def _runner() -> None:
        try:
            output.put(asyncio.run(coro))
        except BaseException as exc:
            output.put(exc)

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()

    result = output.get()
    if isinstance(result, BaseException):
        raise AsyncExecutionError(result=result) from result
    return result


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine from both sync and async contexts.

    If called from a sync context, the coroutine will be run in a dedicated thread
    with its own event loop. If called from an async context, the coroutine will
    be awaited directly.

    Args:
        coro: The coroutine to run.

    Returns:
        The result of the coroutine.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    return _run_in_background_thread(coro)
