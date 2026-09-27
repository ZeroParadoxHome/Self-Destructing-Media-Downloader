# -*- coding:utf-8 -*-
"""Bounded, non-recursive retry wrapper for Telegram flood waits."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, TypeVar

from rich.console import Console
from telethon.errors import FloodWaitError

T = TypeVar("T")

console = Console()


async def with_floodwait_retry(
    coro_factory: Callable[[], Awaitable[T]], max_retries: int = 5
) -> T:
    """Await coro_factory(), sleeping through FloodWaitError and retrying.

    The wrapper is non-recursive: retries run in a flat loop with a hard
    upper bound of ``max_retries`` sleep-and-retry cycles.

    Args:
        coro_factory: Zero-argument callable returning a fresh awaitable,
            so every retry performs the request again instead of reusing
            an already-consumed coroutine object.
        max_retries: Maximum number of retries after the first attempt.

    Returns:
        The result of the first successful attempt.

    Raises:
        ValueError: When max_retries is negative.
        FloodWaitError: When the final attempt is still throttled.
    """
    if max_retries < 0:
        raise ValueError(f"max_retries must be >= 0, got {max_retries}")
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except FloodWaitError as exc:
            if attempt == max_retries:
                raise
            wait_seconds = int(exc.seconds) + 1
            console.print(
                f"[yellow]Flood wait: sleeping {wait_seconds}s "
                f"(attempt {attempt + 1}/{max_retries})[/yellow]"
            )
            await asyncio.sleep(wait_seconds)
    raise AssertionError("unreachable: retry loop exited without result")
