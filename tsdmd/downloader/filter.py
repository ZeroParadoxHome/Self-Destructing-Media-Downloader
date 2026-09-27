# -*- coding:utf-8 -*-
"""Recognition of self-destructing (expiring) media messages.

Telegram marks view-once media with a sentinel TTL instead of a small
expiry, so both the sentinel and short time-to-live values are accepted.
"""

from __future__ import annotations

from typing import Any

from telethon.events import NewMessage

VIEW_ONCE_TTL = 0x7FFFFFFF
MIN_TTL_SECONDS = 3


def get_ttl_seconds(event: NewMessage.Event) -> int | None:
    """Return the message time-to-live in seconds, or None when not expiring.

    The TTL lives on the media object, so video documents and photo
    messages are both covered. Values that cannot be read as an integer
    are treated as no TTL rather than failing the event handler.

    Args:
        event: The incoming message event.

    Returns:
        The TTL in seconds, or None when the media carries none.
    """
    media: Any = getattr(event, "media", None)
    raw_ttl = getattr(media, "ttl_seconds", None)
    if raw_ttl is None:
        return None
    try:
        return int(raw_ttl)
    except (TypeError, ValueError):
        return None


def is_expiring_media(event: NewMessage.Event) -> bool:
    """Report whether the event carries self-destructing media worth archiving.

    Only private, incoming messages qualify: echoes of the account's own
    sends are ignored, because they are the copies this downloader
    produces in Saved Messages.

    Args:
        event: The incoming message event.

    Returns:
        True when the message holds media that will disappear in Telegram.
    """
    if not getattr(event, "is_private", False):
        return False
    if getattr(event, "out", False):
        return False
    if not getattr(event, "media", None):
        return False
    ttl_seconds = get_ttl_seconds(event)
    if ttl_seconds is None:
        return False
    return ttl_seconds == VIEW_ONCE_TTL or ttl_seconds >= MIN_TTL_SECONDS
