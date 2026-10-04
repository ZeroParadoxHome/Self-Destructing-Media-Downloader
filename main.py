# -*- coding:utf-8 -*-
"""TSDMD entrypoint: archive self-destructing Telegram media.

Loads credentials, connects the Telethon client, registers the media
downloader and admin commands, starts background retention, and serves
until disconnected or interrupted.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from rich.console import Console

from tsdmd.client.session import build_telethon_client, connect, disconnect
from tsdmd.commands.router import register_commands
from tsdmd.config.loader import load_config
from tsdmd.downloader.engine import register_downloader
from tsdmd.retention.cleaner import start_cleaner_task

logger = logging.getLogger(__name__)
console = Console()


async def amain() -> int:
    """Run TSDMD: connect, register handlers, serve until disconnected.

    Starts retention before the serve loop so the first pass completes
    during startup. On exit the cleaner task is cancelled, then the
    client is disconnected.

    Returns:
        Process exit code: 0 on clean disconnect.
    """
    config = load_config()
    client = build_telethon_client(config)
    register_downloader(client)  # sync: attaches handler, returns None
    register_commands(client, config)

    await connect(client)
    cleaner_task = await start_cleaner_task(config)
    console.print(
        f"[bold green]TSDMD running[/bold green] — admin: "
        f"[cyan]{config.admin_id}[/cyan]"
    )
    try:
        # Dual sync/async API: returns a coroutine when the loop is
        # already running (our case inside asyncio.run), so awaiting is
        # correct here; the ignore silences the sync-signature complaint.
        await client.run_until_disconnected()  # type: ignore[misc]
    finally:
        cleaner_task.cancel()
        try:
            await cleaner_task
        except asyncio.CancelledError:
            pass
        await disconnect(client)
    return 0


def main() -> int:
    """Wrap the async entrypoint with terminal-friendly exit codes.

    Returns:
        0 on clean disconnect, 130 on Ctrl+C, 1 on unexpected errors.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    try:
        return asyncio.run(amain())
    except KeyboardInterrupt:
        console.print("[yellow]Interrupted by user.[/yellow]")
        return 130
    except Exception:
        logger.exception("TSDMD crashed with an unexpected error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
