# -*- coding:utf-8 -*-
"""Admin command implementations for TSDMD.

Every handler guards sender identity against the configured admin_id and
operates strictly inside the project downloads directory. Traversal
attempts are resolved and rejected before any file operation runs.
All replies use HTML parse mode, which is set on the client at startup.
"""

from __future__ import annotations

import logging
import shutil
import time
import zipfile
from collections.abc import Iterable, Iterator
from html import escape
from pathlib import Path
from typing import Awaitable, Callable
from uuid import uuid4

from telethon import TelegramClient
from telethon.errors import MessageAuthorRequiredError, MessageNotModifiedError
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

_MAX_FOLDERS_LISTED = 50
_MAX_FILES_SENT = 30


async def _respond(event: NewMessage.Event, text: str) -> None:
    """Edit the triggering message when possible, else send a reply.

    Editing keeps the admin chat tidy. Messages the account cannot edit
    fall back to a plain reply. Identical content is left as-is. Both paths
    retry through flood waits.
    File deliveries always stay separate new messages via send_file.
    """
    try:
        await with_floodwait_retry(lambda: event.edit(text))
    except MessageNotModifiedError:
        return
    except MessageAuthorRequiredError:
        await with_floodwait_retry(lambda: event.reply(text))


def _is_real_file(path: Path) -> bool:
    """Return True for regular files only, excluding symlinks.

    Zipping or counting a symlink would leak the link target's bytes from
    outside the archive scope, so links are skipped quietly.

    Args:
        path: Filesystem path to test.

    Returns:
        True when path is a file and not a symlink; False otherwise.
    """
    try:
        return path.is_file() and not path.is_symlink()
    except OSError:
        return False


def _resolve_inside_downloads(raw: str) -> Path:
    """Resolve a user-supplied path strictly inside the downloads directory.

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
    """Yield regular (non-symlink) files recursively, ignoring broken entries."""
    if not directory.is_dir():
        return
    for item in directory.rglob("*"):
        if _is_real_file(item):
            yield item


def join_lines(lines: list[str]) -> str:
    """Join message lines with plain newlines.

    Telegram HTML has no line-break tag: unknown tags such as ``<br>``
    are stripped by the parser and lines would run together, so messages
    use literal newlines which Telegram preserves as line breaks.
    """
    return "\n".join(lines)


def _mtime_or_zero(path: Path) -> float:
    """Return a file's mtime, or 0.0 when it vanished mid-scan.

    Args:
        path: Filesystem path to stat.

    Returns:
        Modification time in seconds, or 0.0 on stat failure so the
        entry sorts last instead of breaking newest-first ordering.
    """
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _total_size_mb(files: Iterable[Path]) -> float:
    """Return the total size of regular files in MB, tolerating stat errors."""
    total_bytes = 0
    for file_path in files:
        if not _is_real_file(file_path):
            continue
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
    await _respond(
        event,
        "<b>TSDMD — Admin Commands</b>\n"
        "<blockquote expandable>"
        "/help — this command list\n"
        "/ping — measure Telegram round-trip\n"
        "/status — file counts and storage used\n"
        "/files — sender folders and file counts\n"
        "/all — send recent downloads to this chat\n"
        "<code>/check</code> &lt;path&gt; — check a file exists\n"
        "<code>/download</code> &lt;path&gt; — send one file here\n"
        "<code>/delete</code> &lt;path&gt; — remove a file or folder\n"
        "/zip — export downloads as a zip"
        "</blockquote>\n"
        "<i>All paths are relative to downloads/.</i>",
    )


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
    verdict = (
        "Excellent" if latency_ms < 200 else "Good" if latency_ms <= 800 else "Degraded"
    )
    logger.info("Ping for admin %s: %.0f ms (%s)", config.admin_id, latency_ms, verdict)
    await _respond(
        event, f"<b>Pong</b> <code>{latency_ms:.0f} ms</code> <i>{verdict}</i>"
    )


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
    pct = (
        round(total_mb / config.max_storage_mb * 100, 1)
        if config.max_storage_mb
        else 0.0
    )
    logger.info(
        "Status for admin %s: %d files in %d folders, %.2f MB",
        config.admin_id,
        len(files),
        len(folders),
        total_mb,
    )
    await _respond(
        event,
        "<b>Storage Status</b>\n"
        "<blockquote>"
        f"Total files: <code>{len(files)}</code>\n"
        f"Sender folders: <code>{len(folders)}</code>\n"
        f"Space used: <code>{total_mb:.2f} MB / {config.max_storage_mb} MB</code> ({pct}%)"
        "</blockquote>",
    )


async def handle_files(
    client: TelegramClient,
    event: NewMessage.Event,
    config: Config,
    args: list[str],
) -> None:
    """List sender folders with file counts and copyable file paths."""
    if not is_admin(event, config.admin_id):
        return
    if not DOWNLOADS_DIR.is_dir():
        await _respond(event, "<b>No downloads yet.</b>")
        return
    folders = sorted(p for p in DOWNLOADS_DIR.iterdir() if p.is_dir())
    if not folders:
        await _respond(event, "<b>No sender folders found.</b>")
        return

    shown = folders[:_MAX_FOLDERS_LISTED]
    lines = []
    for folder in shown:
        folder_files = sorted(_iter_files(folder))
        lines.append(
            f"<b>{escape(folder.name)}</b> — <code>{len(folder_files)}</code> file(s)"
        )
        for file_path in folder_files:
            try:
                relative = file_path.relative_to(DOWNLOADS_DIR).as_posix()
            except ValueError:
                continue
            lines.append(f"<code>{escape(relative)}</code>")
    remaining = len(folders) - len(shown)
    footer = f"<i>…and {remaining} more folder(s).</i>" if remaining else ""
    logger.info(
        "Files listing for admin %s: %d folders shown of %d",
        config.admin_id,
        len(shown),
        len(folders),
    )
    await _respond(
        event,
        f"<b>Archived Senders</b> (<code>{len(folders)}</code>)\n"
        f"<blockquote expandable>{join_lines(lines)}</blockquote>\n{footer}"
        "<i>Copy a path to use with /download, /delete, or /check.</i>",
    )


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
        await _respond(event, "<b>Usage:</b> <code>/check &lt;relative-path&gt;</code>")
        return
    raw = " ".join(args)
    try:
        target = _resolve_inside_downloads(raw)
    except ValueError as exc:
        logger.warning(
            "Access denied for admin %s on /check with target %s", config.admin_id, raw
        )
        await _respond(event, f"<b><u>Access Denied</u></b>\n<i>{escape(str(exc))}</i>")
        return

    if not target.exists():
        await _respond(event, f"<b><u>Not found</u></b>: <code>{escape(raw)}</code>")
        return
    kind = "directory" if target.is_dir() else "file"
    size_str = ""
    if _is_real_file(target):
        try:
            size_mb = target.stat().st_size / (1024 * 1024)
            size_str = f" (<code>{size_mb:.2f} MB</code>)"
        except OSError:
            pass
    logger.info("Check for admin %s: %s exists as %s", config.admin_id, raw, kind)
    await _respond(event, f"<b>Found {kind}:</b> <code>{escape(raw)}</code>{size_str}")


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
        await _respond(
            event, "<b>Usage:</b> <code>/download &lt;relative-path&gt;</code>"
        )
        return
    raw = " ".join(args)
    try:
        target = _resolve_inside_downloads(raw)
    except ValueError as exc:
        logger.warning(
            "Access denied for admin %s on /download with target %s",
            config.admin_id,
            raw,
        )
        await _respond(event, f"<b><u>Access Denied</u></b>\n<i>{escape(str(exc))}</i>")
        return

    if not _is_real_file(target):
        await _respond(event, f"<b><u>Not found</u></b>: <code>{escape(raw)}</code>")
        return

    sender_id = getattr(event, "sender_id", config.admin_id)
    await _respond(event, f"<i>Sending <code>{escape(target.name)}</code>…</i>")
    try:
        await with_floodwait_retry(
            lambda: client.send_file(
                sender_id,
                str(target),
                caption=f"TSDMD: {escape(target.name)}",
            )
        )
        logger.info("Sent file %s to admin %s", raw, config.admin_id)
    except Exception as exc:
        logger.error(
            "Failed to send file %s for admin %s: %s", raw, config.admin_id, exc
        )
        await _respond(event, f"<b><u>Send failed</u></b>: <i>{escape(str(exc))}</i>")


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
        await _respond(
            event, "<b>Usage:</b> <code>/delete &lt;relative-path&gt;</code>"
        )
        return
    raw = " ".join(args)
    try:
        target = _resolve_inside_downloads(raw)
    except ValueError as exc:
        logger.warning(
            "Access denied for admin %s on /delete with target %s",
            config.admin_id,
            raw,
        )
        await _respond(event, f"<b><u>Access Denied</u></b>\n<i>{escape(str(exc))}</i>")
        return

    if not target.exists():
        await _respond(
            event, f"<b><u>Does not exist</u></b>: <code>{escape(raw)}</code>"
        )
        return

    try:
        if _is_real_file(target):
            target.unlink()
            logger.info("Deleted file %s for admin %s", raw, config.admin_id)
            await _respond(event, f"<b>Deleted file:</b> <code>{escape(raw)}</code>")
        elif target.is_dir():
            shutil.rmtree(target)
            logger.info("Deleted folder %s for admin %s", raw, config.admin_id)
            await _respond(event, f"<b>Deleted folder:</b> <code>{escape(raw)}</code>")
        else:
            await _respond(
                event, f"<b><u>Cannot delete</u></b>: <code>{escape(raw)}</code>"
            )
    except OSError as exc:
        logger.error("Failed to delete %s for admin %s: %s", raw, config.admin_id, exc)
        await _respond(
            event, f"<b><u>Deletion failed</u></b>: <i>{escape(str(exc))}</i>"
        )


async def handle_all(
    client: TelegramClient,
    event: NewMessage.Event,
    config: Config,
    args: list[str],
) -> None:
    """Send up to 30 archived files, newest first, to the admin chat."""
    if not is_admin(event, config.admin_id):
        return
    files = sorted(_iter_files(DOWNLOADS_DIR), key=_mtime_or_zero, reverse=True)
    if not files:
        await _respond(event, "<b>Nothing archived yet.</b>")
        return

    sender_id = getattr(event, "sender_id", config.admin_id)
    await _respond(
        event,
        f"<i>Sending <code>{min(len(files), _MAX_FILES_SENT)}</code> newest files…</i>",
    )
    sent = 0
    for file_path in files[:_MAX_FILES_SENT]:
        try:
            await with_floodwait_retry(
                lambda fp=file_path: client.send_file(
                    sender_id,
                    str(fp),
                    caption=f"TSDMD: {escape(fp.name)}",
                )
            )
            sent += 1
        except Exception as exc:
            logger.error(
                "Failed to send file %s for admin %s: %s",
                file_path.name,
                config.admin_id,
                exc,
            )
    remaining = len(files) - sent
    logger.info(
        "Bulk send for admin %s: %d sent, %d remaining",
        config.admin_id,
        sent,
        remaining,
    )
    if remaining:
        await _respond(
            event,
            f"<b>Sent <code>{sent}</code> of <code>{len(files)}</code> files.</b>\n"
            f"<i>{remaining} more remain — use /zip for the full archive.</i>",
        )
    else:
        await _respond(event, f"<b>Sent all <code>{sent}</code> files.</b>")


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
        await _respond(event, "<b>Downloads are empty</b> — <i>nothing to zip.</i>")
        return

    archive = PROJECT_ROOT / f"tsdmd-export-{uuid4().hex[:8]}.zip"
    await _respond(event, "<i>Creating archive, please wait…</i>")
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
        logger.info("Zip archive sent for admin %s", config.admin_id)
        await _respond(event, "<b>Archive sent successfully.</b>")
    except Exception as exc:
        logger.error(
            "Failed to build or send zip for admin %s: %s", config.admin_id, exc
        )
        await _respond(
            event, f"<b><u>Archive failed</u></b>: <i>{escape(str(exc))}</i>"
        )
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
    "all": handle_all,
    "check": handle_check,
    "download": handle_download,
    "delete": handle_delete,
    "zip": handle_zip,
}
