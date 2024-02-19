# -*- coding:utf-8 -*-
from telethon import TelegramClient, events, sync
import asyncio
import logging
import json
import os

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

SETTINGS_FILE = "settings.json"
if os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, "r") as file:
        settings = json.load(file)
    api_id = settings.get("api_id")
    api_hash = settings.get("api_hash")
else:
    api_id = input("Enter your API_ID: ")
    api_hash = input("Enter your API_HASH: ")
    with open(SETTINGS_FILE, "w") as file:
        json.dump({"api_id": api_id, "api_hash": api_hash}, file)

client = TelegramClient("H0lyFanz", api_id, api_hash).start()


@client.on(
    events.NewMessage(
        func=lambda e: e.is_private and (e.photo or e.video) and e.media_unread
    )
)
async def downloader(event):
    me = await client.get_me()
    if event.sender_id != me.id:
        result = await event.download_media()
        await client.send_file("me", result, caption="Downloaded by @H0lyFanz")


@client.on(events.NewMessage(pattern=r"بصبر دان (بشه|شه)", func=lambda e: e.is_reply))
async def get_image(event):
    me = await client.get_me()
    if event.sender_id == me.id:
        try:
            message = await event.get_reply_message()
            download = await client.download_media(message)
            await client.send_message("me", f"Downloaded by @H0lyFanz", file=download)
        except Exception as e:
            await client.send_message("me", f"Error:\n\n{e}")


async def main():
    await client.run_until_disconnected()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
