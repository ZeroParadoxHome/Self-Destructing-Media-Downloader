# -*- coding:utf-8 -*-
"""Admin command implementations for TSDMD.

Every handler guards sender identity against the configured admin_id and
operates strictly inside the project downloads directory. Traversal
attempts are resolved and rejected before any file operation runs.
"""

from __future__ import annotations

import logging
import shutil
import time
import zipfile
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Awaitable, Callable
from uuid import uuid4

from telethon import TelegramClient
from telethon.events import NewMessage

from ..client.floodwait import with_floodwait_retry
from ..config.loader import Config
from ..downloader.paths import DOWNLOADS_DIR, PROJECT_ROOT
from .router import is_admin

logger = logging.getLogger(__name__)

CommandHandler = Callable[
    [TelegramClient, NewMessage.Event, Config, list[str]],
    Awaitable[None],
]


async def _reply(event: NewMessage.Event, text: str) -> None:
    """Send a reply to the event, retrying through Telegram flood waits."""
    await with_floodwait_retry(lambda: event.reply(text))


def _resolve_inside_downloads(raw: str) -> Path:
    """Resolve a user-supplied path, ensuring it stays strictly inside downloads.

    Resolving follows symlinks on platforms that support them, so a link
    inside the directory that points outside is caught and rejected.

    Args:
        raw: User-supplied relative path string.

    Returns:
        The resolved Path inside the downloads directory.

    Raises:
        ValueError: When the path escapes the downloads directory or tries
            to target the downloads directory root itself.
    """
    root = DOWNLOADS_DIR.resolve()
    candidate = (DOWNLOADS_DIR / raw).resolve()
    if not candidate.is_relative_to(root) or candidate == root:
        raise ValueError(f"Path must be strictly inside the downloads directory: {raw}")
    return candidate


def _iter_files(directory: Path) -> Iterator[Path]:
    """Yield regular files recursively under directory, ignoring broken entries."""
    if not directory.is_dir():
        return
    for item in directory.rglob("*"):
        try:
            if item.is_file():
                yield item
        except OSError:
            continue


def _total_size_mb(files: Iterable[Path]) -> float:
    """Return the total size of files in megabytes, tolerating stat errors."""
    total_bytes = 0
    for file_path in files:
        try:
            total_bytes += file_path.stat().st_size
        except OSError:
            continue
    return total_bytes / (1024 * 1024)


async def handle_help(
    client: TelegramClient,
    event: NewMessage.Event,
    config: Config,
    args: list[str],
) -> None:
    """Display the admin command list."""
    if not is_admin(event, config.admin_id):
        return
    # Deferred import to keep help text DRY with the router.
    from .router import USAGE_HINT

    await _reply(event, USAGE_HINT)


async def handle_ping(
    client: TelegramClient,
    event: NewMessage.Event,
    config: Config,
    args: list[str],
) -> None:
    """Measure Telegram API round-trip time and report bot status."""
    if not is_admin(event, config.admin_id):
        return
    start = time.perf_counter()
    await with_floodwait_retry(client.get_me)
    latency_ms = (time.perf_counter() - start) * 1000
    await _reply(event, f"Pong! Telegram round-trip: {latency_ms:.0f} ms")


async def handle_status(
    client: TelegramClient,
    event: NewMessage.Event,
    config: Config,
    args: list[str],
) -> None:
    """Report file counts and storage consumption under the downloads directory."""
    if not is_admin(event, config.admin_id):
        return
    files = list(_iter_files(DOWNLOADS_DIR))
    total_mb = _total_size_mb(files)
    folders = (
        [p for p in DOWNLOADS_DIR.iterdir() if p.is_dir()]
        if DOWNLOADS_DIR.is_dir()
        else []
    )
    await _reply(
        event,
        f"Storage status:\n"
        f"  Total files:    {len(files)}\n"
        f"  Sender folders: {len(folders)}\n"
        f"  Space used:     {total_mb:.2f} MB / {config.max_storage_mb} MB limit",
    )


async def handle_files(
    client: TelegramClient,
    event: NewMessage.Event,
    config: Config,
    args: list[str],
) -> None:
    """List every sender folder with its archived file count."""
    if not is_admin(event, config.admin_id):
        return
    if not DOWNLOADS_DIR.is_dir():
        await _reply(event, "No downloads directory yet.")
        return
    folders = sorted(p for p in DOWNLOADS_DIR.iterdir() if p.is_dir())
    if not folders:
        await _reply(event, "No sender folders found.")
        return

    lines = ["Archived folders:"]
    for folder in folders:
        count = sum(1 for _ in _iter_files(folder))
        lines.append(f"  {folder.name}: {count} file{'s' if count != 1 else ''}")
    await _reply(event, "\n".join(lines))


async def handle_check(
    client: TelegramClient,
    event: NewMessage.Event,
    config: Config,
    args: list[str],
) -> None:
    """Check whether a user-supplied relative path exists inside downloads."""
    if not is_admin(event, config.admin_id):
        return
    if not args:
        await _reply(event, "Usage: /check <relative-path>")
        return
    raw = " ".join(args)
    try:
        target = _resolve_inside_downloads(raw)
    except ValueError as exc:
        await _reply(event, f"Refusal: {exc}")
        return

    if not target.exists():
        await _reply(event, f"Does not exist: {raw}")
        return
    kind = "directory" if target.is_dir() else "file"
    size_str = ""
    if target.is_file():
        try:
            size_mb = target.stat().st_size / (1024 * 1024)
            size_str = f" ({size_mb:.2f} MB)"
        except OSError:
            pass
    await _reply(event, f"Found {kind}: {raw}{size_str}")


async def handle_download(
    client: TelegramClient,
    event: NewMessage.Event,
    config: Config,
    args: list[str],
) -> None:
    """Send the requested file inside the downloads directory to the chat."""
    if not is_admin(event, config.admin_id):
        return
    if not args:
        await _reply(event, "Usage: /download <relative-path>")
        return
    raw = " ".join(args)
    try:
        target = _resolve_inside_downloads(raw)
    except ValueError as exc:
        await _reply(event, f"Refusal: {exc}")
        return

    if not target.is_file():
        await _reply(event, f"File not found: {raw}")
        return

    sender_id = getattr(event, "sender_id", config.admin_id)
    await _reply(event, f"Sending {target.name}...")
    try:
        await with_floodwait_retry(
            lambda: client.send_file(
                sender_id,
                str(target),
                caption=f"TSDMD: {target.name}",
            )
        )
    except Exception as exc:
        logger.error("Failed to send file %s: %s", target, exc)
        await _reply(event, f"Send failed: {exc}")


async def handle_delete(
    client: TelegramClient,
    event: NewMessage.Event,
    config: Config,
    args: list[str],
) -> None:
    """Delete a file or folder strictly inside the downloads directory."""
    if not is_admin(event, config.admin_id):
        return
    if not args:
        await _reply(event, "Usage: /delete <relative-path>")
        return
    raw = " ".join(args)
    try:
        target = _resolve_inside_downloads(raw)
    except ValueError as exc:
        await _reply(event, f"Refusal: {exc}")
        return

    if not target.exists():
        await _reply(event, f"Does not exist: {raw}")
        return

    try:
        if target.is_file():
            target.unlink()
            await _reply(event, f"Deleted file: {raw}")
        elif target.is_dir():
            shutil.rmtree(target)
            await _reply(event, f"Deleted folder: {raw}")
    except OSError as exc:
        logger.error("Failed to delete %s: %s", target, exc)
        await _reply(event, f"Deletion failed: {exc}")


async def handle_zip(
    client: TelegramClient,
    event: NewMessage.Event,
    config: Config,
    args: list[str],
) -> None:
    """Create a zip archive of the downloads directory and send it."""
    if not is_admin(event, config.admin_id):
        return
    if not DOWNLOADS_DIR.is_dir() or not any(_iter_files(DOWNLOADS_DIR)):
        await _reply(event, "Downloads directory is empty; nothing to zip.")
        return

    archive = PROJECT_ROOT / f"tsdmd-export-{uuid4().hex[:8]}.zip"
    await _reply(event, "Creating archive, please wait...")
    try:
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in _iter_files(DOWNLOADS_DIR):
                zf.write(file_path, file_path.relative_to(DOWNLOADS_DIR))

        sender_id = getattr(event, "sender_id", config.admin_id)
        await with_floodwait_retry(
            lambda: client.send_file(
                sender_id,
                str(archive),
                caption="TSDMD downloads archive",
            )
        )
        await _reply(event, "Archive sent successfully.")
    except Exception as exc:
        logger.error("Failed to build or send zip archive: %s", exc)
        await _reply(event, f"Archive failed: {exc}")
    finally:
        try:
            archive.unlink(missing_ok=True)
        except OSError:
            pass


COMMANDS: dict[str, CommandHandler] = {
    "help": handle_help,
    "ping": handle_ping,
    "status": handle_status,
    "files": handle_files,
    "check": handle_check,
    "download": handle_download,
    "delete": handle_delete,
    "zip": handle_zip,
}
