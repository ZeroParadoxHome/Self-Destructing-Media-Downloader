# -*- coding:utf-8 -*-
"""Filesystem layout for archived media.

Layout is ``<sender id>-<handle>`` under the project downloads directory so
it stays stable regardless of case folding or renames on the filesystem.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOWNLOADS_DIR = PROJECT_ROOT / "downloads"


def sanitize_username(username: str | None) -> str:
    """Return a filesystem-safe handle for a Telegram username.

    Path separators are the only platform-specific character here, so they
    are replaced on every platform to keep one code path.

    Args:
        username: Telegram username, or None when the sender has none.

    Returns:
        The stripped username, or ``unknown`` when there is none.
    """
    if not username:
        return "unknown"
    cleaned = username.strip().replace("/", "_").replace("\\", "_")
    return cleaned or "unknown"


def sender_folder(sender_id: int, username: str | None = None) -> Path:
    """Return the archive folder for a sender, creating it if needed.

    The returned path is verified to stay inside the downloads directory so
    a crafted identifier cannot write media anywhere else.

    Args:
        sender_id: Telegram user ID of the sender.
        username: Optional Telegram username, used as the readable handle.

    Returns:
        The existing sender folder inside the downloads directory.

    Raises:
        ValueError: When the resolved folder escapes the downloads directory.
    """
    folder = DOWNLOADS_DIR / f"{sender_id}-{sanitize_username(username)}"
    folder.mkdir(parents=True, exist_ok=True)
    resolved = folder.resolve()
    if not resolved.is_relative_to(DOWNLOADS_DIR.resolve()):
        raise ValueError(f"Refusing to write outside the downloads directory: {folder}")
    return folder
