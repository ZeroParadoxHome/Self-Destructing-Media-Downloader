# -*- coding:utf-8 -*-
"""Download of self-destructing media, with a copy echoed to Saved Messages."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from telethon import TelegramClient
from telethon.events import NewMessage

from ..client.floodwait import with_floodwait_retry
from .filter import is_expiring_media
from .paths import sender_folder

logger = logging.getLogger(__name__)


async def download_and_echo(
    client: TelegramClient, event: NewMessage.Event
) -> Path | None:
    """Save expiring media locally and echo a copy into Saved Messages.

    The event is re-checked here because handlers can be triggered for
    messages that were already expiring when the event was dispatched, and
    downloading a message whose media is gone yields nothing worth keeping.

    Args:
        client: The connected Telethon client.
        event: The incoming message event.

    Returns:
        Path of the saved file, or None when nothing was saved.
    """
    if not is_expiring_media(event):
        return None

    sender_id = getattr(event, "sender_id", None)
    if not isinstance(sender_id, int):
        logger.warning("Event without a sender id; skipping download.")
        return None

    sender: Any = None
    try:
        sender = await event.get_sender()
    except Exception as exc:
        logger.warning("Could not resolve sender object: %s", exc)

    username: str | None = getattr(sender, "username", None)

    try:
        folder = sender_folder(sender_id, username)
    except (OSError, ValueError) as exc:
        logger.error("Cannot prepare sender folder: %s", exc)
        return None

    try:
        saved = await with_floodwait_retry(
            lambda: event.download_media(file=str(folder))
        )
    except Exception as exc:
        logger.error("Failed to download expiring media: %s", exc)
        return None
    if not saved:
        logger.warning("Telegram returned no media for this event; nothing saved.")
        return None

    saved_path = Path(saved)
    handle = username or getattr(sender, "first_name", None) or str(sender_id)
    try:
        await with_floodwait_retry(
            lambda: client.send_file(
                "me", str(saved_path), caption=f"TSDMD saved from {handle}"
            )
        )
    except Exception as exc:
        logger.error("Failed to echo saved media to Saved Messages: %s", exc)

    logger.info("Archived expiring media to %s", saved_path)
    return saved_path


def register_downloader(client: TelegramClient) -> None:
    """Register the expiring-media downloader on the client.

    Only incoming messages are considered, so the copies this downloader
    writes to Saved Messages are never downloaded again.

    Args:
        client: The connected Telethon client.
    """

    async def _handler(event: NewMessage.Event) -> None:
        await download_and_echo(client, event)

    client.add_event_handler(
        _handler,
        NewMessage(incoming=True, func=is_expiring_media),
    )
