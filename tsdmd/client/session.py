# -*- coding:utf-8 -*-
"""Telethon client construction and clean lifecycle helpers."""

from __future__ import annotations

import getpass

from telethon import TelegramClient, errors

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
    client = TelegramClient(SESSION_NAME, config.api_id, config.api_hash)
    client.parse_mode = "html"
    return client


async def connect(client: TelegramClient) -> None:
    """Connect the client, performing first-run login when needed.

    When a stored, authorized session already exists this only connects.
    On first run (no authorized session) an interactive login runs in the
    terminal: the phone number and login code are read with ``input()``,
    the 2FA password (when set) with ``getpass``, and authentication runs
    through ``send_code_request``/``sign_in``.

    Args:
        client: The Telethon client to connect.

    Raises:
        RuntimeError: When the session is still unauthorized after the
            interactive login attempt.
    """
    await client.connect()
    if await client.is_user_authorized():
        return
    phone = input("Enter your phone number (with country code): ").strip()
    sent = await client.send_code_request(phone)
    code = input("Enter the Telegram login code: ").strip()
    try:
        await client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
    except errors.SessionPasswordNeededError:
        password = getpass.getpass("Enter your 2FA password: ")
        try:
            await client.sign_in(phone, password=password)
        except errors.PasswordHashInvalidError:
            password = getpass.getpass("Wrong password, try once more: ")
            await client.sign_in(phone, password=password)
    if not await client.is_user_authorized():
        raise RuntimeError("Session 'tsdmd' is not authorized; login failed.")


async def disconnect(client: TelegramClient) -> None:
    """Disconnect the client if it is still connected.

    Args:
        client: The Telethon client to disconnect.
    """
    if client.is_connected():
        client.disconnect()
