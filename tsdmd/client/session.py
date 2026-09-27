# -*- coding:utf-8 -*-
"""Telethon client construction and clean lifecycle helpers."""

from __future__ import annotations

from telethon import TelegramClient

from ..config.loader import Config

SESSION_NAME = "tsdmd"


def build_telethon_client(config: Config) -> TelegramClient:
    """Create the Telethon client for the TSDMD session.

    Uses the session name 'tsdmd' — a clean break from the legacy
    'H0lyFanz' session used by the old single-file TSDMD.py.

    Args:
        config: Resolved runtime configuration.

    Returns:
        An unconnected TelegramClient bound to the TSDMD session.
    """
    return TelegramClient(SESSION_NAME, config.api_id, config.api_hash)


async def connect(client: TelegramClient) -> None:
    """Connect the client and verify the stored session is authorized.

    Args:
        client: The Telethon client to connect.

    Raises:
        RuntimeError: When the client connects but the session is not
            authorized (no stored login for this Telegram account).
    """
    await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError("Session 'tsdmd' is not authorized; log in first.")


async def disconnect(client: TelegramClient) -> None:
    """Disconnect the client if it is still connected.

    Args:
        client: The Telethon client to disconnect.
    """
    if client.is_connected():
        client.disconnect()
