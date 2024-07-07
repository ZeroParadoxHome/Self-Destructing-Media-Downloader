# -*- coding:utf-8 -*-

from telethon import TelegramClient, events, sync
import asyncio
import logging
import json
import os
import coloredlogs
from tqdm import tqdm
import traceback

# Enhanced logging with coloredlogs
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler = logging.StreamHandler()
handler.setFormatter(formatter)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)

coloredlogs.install(
    fmt="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO, logger=logger
)

SETTINGS_FILE = "settings.json"


def load_config():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as file:
            settings = json.load(file)
        return settings.get("api_id"), settings.get("api_hash")
    else:
        api_id = input("Enter your API_ID: ")
        api_hash = input("Enter your API_HASH: ")
        with open(SETTINGS_FILE, "w") as file:
            json.dump({"api_id": api_id, "api_hash": api_hash}, file)
        return api_id, api_hash


api_id, api_hash = load_config()

client = TelegramClient("H0lyFanz", api_id, api_hash).start()


class TqdmProgressBar:
    def __init__(self, total):
        self.progress_bar = tqdm(
            total=total, unit="B", unit_scale=True, desc="Downloading"
        )

    def __call__(self, current, total):
        self.progress_bar.total = total
        self.progress_bar.n = current
        self.progress_bar.refresh()

    def close(self):
        self.progress_bar.close()


@client.on(
    events.NewMessage(
        func=lambda e: e.is_private and (e.photo or e.video) and e.media_unread
    )
)
async def downloader(event):
    me = await client.get_me()
    if event.sender_id != me.id:
        sender = await event.get_sender()
        logger.info(
            f"Received media from {sender.username} (ID: {sender.id}). Starting download..."
        )
        try:
            total_size = event.file.size
            progress_bar = TqdmProgressBar(total_size)
            result = await event.download_media(progress_callback=progress_bar)
            progress_bar.close()
            media_type = "photo" if event.photo else "video"
            logger.info(
                f"{media_type.capitalize()} downloaded successfully from {sender.username} (ID: {sender.id})"
            )
            await client.send_file(
                "me", result, caption=f"Downloaded by @H0lyFanz from {sender.username}"
            )
        except Exception as e:
            logger.error(
                f"Failed to download media from {sender.username} (ID: {sender.id}): {str(e)}"
            )
            logger.debug(traceback.format_exc())


@client.on(
    events.NewMessage(pattern=r"بصبر دانلود (بشه|شه)", func=lambda e: e.is_reply)
)
async def get_image(event):
    me = await client.get_me()
    if event.sender_id == me.id:
        try:
            message = await event.get_reply_message()
            logger.info("Reply detected. Starting download of replied media...")
            total_size = message.file.size
            progress_bar = TqdmProgressBar(total_size)
            result = await client.download_media(
                message, progress_callback=progress_bar
            )
            progress_bar.close()
            logger.info("Media downloaded successfully from reply")
            await client.send_message("me", f"Downloaded by @H0lyFanz", file=result)
        except Exception as e:
            logger.error(f"Error in downloading media from reply: {str(e)}")
            logger.debug(traceback.format_exc())
            await client.send_message("me", f"Error:\n\n{e}")


async def main():
    logger.info("Starting bot...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
