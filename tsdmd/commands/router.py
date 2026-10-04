# -*- coding:utf-8 -*-
"""Command routing and dispatch for TSDMD admin interactions.

Commands are matched against a leading slash, parsed into a canonical
lowercased name plus arguments, and guarded by sender ID verification
before dispatch.
"""

from __future__ import annotations

import logging
from html import escape

from telethon import TelegramClient
from telethon.events import NewMessage

from ..config.loader import Config

logger = logging.getLogger(__name__)

USAGE_HINT = (
    "<b>TSDMD admin commands:</b>\n"
    "<blockquote expandable>"
    "/help — show this usage hint\n"
    "/ping — measure bot round-trip time\n"
    "/status — report downloads count and storage used\n"
    "/files — list sender folders and file counts\n"
    "/all — send recent downloads to this chat\n"
    "/check &lt;relative&gt; — check whether a file exists in downloads\n"
    "/download &lt;relative&gt; — send a downloaded file to this chat\n"
    "/delete &lt;relative&gt; — remove a file or folder inside downloads\n"
    "/zip — export the downloads directory as a zip"
    "</blockquote>"
)


def is_admin(event: NewMessage.Event, admin_id: int) -> bool:
    """Return True only when the event originated from the configured admin.

    Args:
        event: The incoming message event.
        admin_id: Telegram user ID authorized to administer this bot.

    Returns:
        True when the sender matches admin_id; False otherwise.
    """
    sender_id = getattr(event, "sender_id", None)
    return sender_id == admin_id


def parse_command(text: str) -> tuple[str, list[str]]:
    """Parse a message into a canonical command name and argument list.

    The leading slash is stripped, and the command name is lowercased.
    Telegram allows command mentions (e.g. ``/help@bot``); the mention
    is dropped so matching is uniform.

    Args:
        text: The message body to parse.

    Returns:
        A tuple of ``(command_name, args)``. When no slash command is
        present, ``("", [])`` is returned.
    """
    stripped = text.strip()
    if not stripped.startswith("/"):
        return "", []
    body = stripped[1:]
    parts = body.split()
    if not parts:
        return "", []
    raw_command = parts[0].split("@", 1)[0]
    return raw_command.lower(), parts[1:]


async def _dispatch(
    client: TelegramClient,
    event: NewMessage.Event,
    config: Config,
    command: str,
    args: list[str],
) -> None:
    """Look up and execute the handler for a command, or reply with usage."""
    # Deferred import: handlers import is_admin from this module.
    from .handlers import COMMANDS, _respond

    handler = COMMANDS.get(command)
    if handler is None:
        await _respond(
            event,
            f"<b>Unknown command:</b> <code>/{escape(command)}</code>\n\n{USAGE_HINT}",
        )
        return
    try:
        await handler(client, event, config, args)
    except Exception as exc:
        logger.exception("Error executing command /%s: %s", command, exc)
        await _respond(
            event,
            f"<b>Command failed:</b> <code>/{escape(command)}</code>\n"
            f"<i>{escape(str(exc))}</i>",
        )


def register_commands(client: TelegramClient, config: Config) -> None:
    """Register the slash-command handler on the client.

    Only messages from the configured admin ID are processed. No
    incoming/outgoing filter is applied: admin commands are typically sent
    from the account itself (own messages), which an incoming-only filter
    would silently drop.

    Args:
        client: The connected Telethon client.
        config: Resolved runtime configuration carrying admin_id.
    """

    async def _handler(event: NewMessage.Event) -> None:
        if not is_admin(event, config.admin_id):
            return
        command, args = parse_command(getattr(event, "text", "") or "")
        if not command:
            return
        await _dispatch(client, event, config, command, args)

    client.add_event_handler(
        _handler,
        NewMessage(pattern=r"^/"),
    )
