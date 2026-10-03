# -*- coding:utf-8 -*-
"""Retention enforcement: age-based expiry and storage quota management.

Files older than the configured retention window are removed first, then
any remaining storage over the quota is reclaimed oldest-first. Symlinks
are never touched, and every path is verified to stay inside the
downloads directory before deletion.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from ..config.loader import Config
from ..downloader.paths import DOWNLOADS_DIR

logger = logging.getLogger(__name__)

CLEANER_INTERVAL_SECONDS = 6 * 3600

_MB = 1024 * 1024
_SECONDS_PER_DAY = 86_400


def _is_real_file(path: Path) -> bool:
    """Return True for regular files only, excluding symlinks.

    Args:
        path: Filesystem path to test.

    Returns:
        True when path is a file and not a symlink; False otherwise.
    """
    try:
        return path.is_file() and not path.is_symlink()
    except OSError:
        return False


def _scan() -> list[tuple[float, int, Path]]:
    """Collect real files under the downloads directory with mtime and size.

    Symlinks are skipped, and any path that resolves outside the downloads
    directory is rejected so a link can never move deletion elsewhere.

    Returns:
        Tuples of ``(mtime, size_bytes, path)`` for each eligible file.
    """
    if not DOWNLOADS_DIR.is_dir():
        return []
    root = DOWNLOADS_DIR.resolve()
    entries: list[tuple[float, int, Path]] = []
    for path in DOWNLOADS_DIR.rglob("*"):
        if not _is_real_file(path):
            continue
        try:
            resolved = path.resolve()
            stat = path.stat()
        except OSError as exc:
            logger.debug("Skipping unreadable path %s: %s", path, exc)
            continue
        if not resolved.is_relative_to(root):
            logger.warning("Skipping path outside downloads directory: %s", path)
            continue
        entries.append((stat.st_mtime, stat.st_size, path))
    return entries


def enforce_retention(config: Config) -> dict[str, float | int]:
    """Apply retention policy: delete by age, then reclaim storage over quota.

    Order matters: age-based expiry runs first, then the total is
    recomputed from disk, and only files still pushing the store over
    ``max_storage_mb`` are deleted oldest-first. Empty sender folders are
    cleaned up afterwards.

    Args:
        config: Runtime configuration with retention_days and max_storage_mb.

    Returns:
        Summary dict with keys ``deleted_files`` (int), ``freed_mb`` (float),
        ``remaining_files`` (int) and ``remaining_mb`` (float).
    """
    if not DOWNLOADS_DIR.is_dir():
        return {
            "deleted_files": 0,
            "freed_mb": 0.0,
            "remaining_files": 0,
            "remaining_mb": 0.0,
        }

    deleted_files = 0
    freed_bytes = 0

    def _remove(path: Path, size: int) -> bool:
        """Unlink one file, counting it on success; log but never raise.

        Args:
            path: File to delete (already verified inside downloads).
            size: Known size used for freed-space accounting.

        Returns:
            True when the file was removed; False when deletion failed.
        """
        nonlocal deleted_files, freed_bytes
        try:
            path.unlink()
        except OSError as exc:
            logger.warning("Could not remove %s: %s", path, exc)
            return False
        deleted_files += 1
        freed_bytes += size
        logger.info("Retention removed %s (%d bytes)", path, size)
        return True

    # Age pass: expire anything past the retention window.
    cutoff = time.time() - config.retention_days * _SECONDS_PER_DAY
    for mtime, size, path in _scan():
        if mtime < cutoff:
            _remove(path, size)

    # Quota pass: recompute from disk, then free oldest-first if over quota.
    entries = _scan()
    total_bytes = sum(size for _, size, _ in entries)
    if total_bytes / _MB > config.max_storage_mb:
        for _, size, path in sorted(entries, key=lambda item: item[0]):
            if total_bytes / _MB <= config.max_storage_mb:
                break
            if _remove(path, size):
                total_bytes -= size

    # Cleanup pass: drop sender folders that no longer hold anything.
    for folder in DOWNLOADS_DIR.iterdir():
        if folder.is_symlink() or not folder.is_dir():
            continue
        try:
            if not any(folder.iterdir()):
                folder.rmdir()
                logger.info("Retention removed empty folder %s", folder)
        except OSError as exc:
            logger.warning("Could not remove empty folder %s: %s", folder, exc)

    remaining = _scan()
    remaining_bytes = sum(size for _, size, _ in remaining)
    summary: dict[str, float | int] = {
        "deleted_files": deleted_files,
        "freed_mb": freed_bytes / _MB,
        "remaining_files": len(remaining),
        "remaining_mb": remaining_bytes / _MB,
    }
    logger.info("Retention pass: %s", summary)
    return summary


async def start_cleaner_task(
    config: Config, interval: int = CLEANER_INTERVAL_SECONDS
) -> asyncio.Task[None]:
    """Run an immediate retention pass, then schedule recurring passes.

    The first pass is awaited so callers can rely on retention having run
    once startup completes. The returned task sleeps between passes and
    exits cleanly when cancelled, logging and continuing on pass errors so
    one bad cycle never kills the scheduler.

    Args:
        config: Runtime configuration forwarded to each retention pass.
        interval: Seconds between retention passes.

    Returns:
        The background task running the recurring retention loop.
    """
    enforce_retention(config)

    async def _cleaner_loop() -> None:
        """Sleep, enforce retention, repeat until cancelled."""
        while True:
            try:
                await asyncio.sleep(interval)
                enforce_retention(config)
            except asyncio.CancelledError:
                logger.info("Retention cleaner task cancelled.")
                return
            except Exception:
                logger.exception("Retention pass failed; retrying next cycle.")

    task = asyncio.create_task(_cleaner_loop())
    logger.info("Retention cleaner scheduled every %d seconds", interval)
    return task
