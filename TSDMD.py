# -*- coding:utf-8 -*-

import asyncio
import json
import logging
import os
import random
import string
import time
import zipfile
import aiofiles
import aiohttp
from rich.console import Console
from rich.progress import Progress
from telethon import TelegramClient, events


# Define and create necessary directories
all_media_dir = "Media"
if not os.path.exists(all_media_dir):
    os.makedirs(all_media_dir)

# Configure logging to display logs in the terminal
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# Create a StreamHandler for terminal output
log_handler = logging.StreamHandler()
log_handler.setFormatter(formatter)
log_handler.setLevel(logging.INFO)

# Configure the logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

# Create a console instance for rich.
console = Console()

SETTINGS_FILE = "settings.json"


# Load API configuration from settings file or prompt user input if file doesn't exist.
async def load_config():
    if os.path.exists(SETTINGS_FILE):
        async with aiofiles.open(SETTINGS_FILE, mode="r") as file:
            settings = json.loads(await file.read())
        api_id = settings.get("api_id")
        api_hash = settings.get("api_hash")
        admin_id = settings.get("admin_id")

        if not admin_id:
            admin_id = input("Enter the Admin ID: ")
            settings["admin_id"] = admin_id
            async with aiofiles.open(SETTINGS_FILE, mode="w") as file:
                await file.write(json.dumps(settings))

        return api_id, api_hash, int(admin_id)

    else:
        api_id = input("Enter your API_ID: ")
        api_hash = input("Enter your API_HASH: ")
        admin_id = input("Enter the Admin ID: ")
        async with aiofiles.open(SETTINGS_FILE, mode="w") as file:
            await file.write(
                json.dumps(
                    {"api_id": api_id, "api_hash": api_hash, "admin_id": admin_id}
                )
            )
        return api_id, api_hash, int(admin_id)


# Check if the sender is the admin
async def is_admin(event, admin_id):
    return event.sender_id == admin_id


# Reconnect the Telegram client if disconnected.
async def reconnect_client(client):
    try:
        await client.disconnect()
        await client.connect()
        if not await client.is_user_authorized():
            raise Exception("Client not authorized")
    except Exception as e:
        logger.critical(f"Failed to reconnect client: {e}")
        await asyncio.sleep(random.uniform(5, 15))
        await reconnect_client(client)


# Custom progress bar for showing download progress using rich.
class RichProgressBar:
    def __init__(self, total):
        self.progress = Progress()
        self.task = self.progress.add_task("[cyan]Downloading...", total=total)

    def __call__(self, current, total):
        self.progress.update(self.task, completed=current)

    def close(self):
        self.progress.stop()


# Display a welcome message and instructions.
async def show_welcome(event):
    if await is_admin(event, admin_id):
        welcome_message = (
            "Welcome to the Self-Destructing-Media-Downloader Bot Helper Menu!\n\n"
            "Here are the commands you can use:\n\n"
            "/ping - Check if the bot is alive and measure ping time.\n"
            "/status - Get the number of downloaded files (Photos/Videos) in the media folder.\n"
            "/files - List all files in the script folder.\n"
            "/check - Perform a check for new files in the media folder.\n"
            "/download [file_path] - Download a specific file from the script folder.\n"
            "/delete [file_path] - Delete a specific file from the script folder.\n"
            "/all - Download all available media files from the media folder.\n"
            "/zip - Create and send a zip file containing files from the project folder.\n\n"
            "Make sure to replace [file_path] with the actual path to the file you want to access.\n"
            "Enjoy Using Bot..."
        )
        await event.respond(welcome_message)


# Check if the bot is alive and measure ping time.
async def handle_ping(event):
    if await is_admin(event, admin_id):
        url = "https://www.google.com"
        try:
            start_time = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    end_time = time.time()
                    ping_time = round((end_time - start_time) * 1000)
                    await event.respond(
                        f"The bot is alive and running, Ping: {ping_time} ms!"
                    )
        except Exception as e:
            logger.error(f"Error in pinging Google: {str(e)}")
            await event.respond(f"Failed to measure ping time, Error: {str(e)}")


# Show the number of downloaded files in the media folder.
async def handle_status(event):
    if await is_admin(event, admin_id):

        def count_files_in_directory(directory):
            count_photos = 0
            count_videos = 0
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith((".jpg", ".jpeg", ".png")):
                        count_photos += 1
                    elif file.lower().endswith((".mp4", ".avi", ".mkv")):
                        count_videos += 1
            return count_photos, count_videos

        photos_count, videos_count = count_files_in_directory(all_media_dir)
        await event.respond(
            f"The Bot Status:\nTotal Photos: {photos_count}\nTotal Videos: {videos_count}"
        )


# List all files in the script folder.
async def handle_files(event):
    if await is_admin(event, admin_id):
        if event.sender_id == (await client.get_me()).id:

            def list_files_and_folders(directory):
                if not os.path.isdir(directory):
                    return f"The directory {directory} does not exist."
                files_list = ""
                for root, dirs, files in os.walk(directory):
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                    files_list += f"Directory: {root}\n"
                    # if dirs:
                    #     for dir_name in dirs:
                    #         files_list += (
                    #             f"  Subdirectory: {os.path.join(root, dir_name)}\n"
                    #         )
                    if files:
                        for file_name in files:
                            if not file_name.startswith("."):
                                files_list += (
                                    f"    File: {os.path.join(root, file_name)}\n"
                                )
                return files_list

            files_list = list_files_and_folders(".")
            await event.respond(files_list)


# Perform a check for new files in the media folder.
async def handle_check(event):
    if await is_admin(event, admin_id):

        def get_current_files(directory):
            if not os.path.isdir(directory):
                return []
            current_files = []
            for root, dirs, files in os.walk(directory):
                for file in files:
                    current_files.append(os.path.join(root, file))
            return current_files

        current_files = get_current_files(all_media_dir)
        if current_files:
            await event.respond("Current files:\n" + "\n".join(current_files))
        else:
            await event.respond("No new files found in the media folder.")


# Download a specific file from the script folder.
async def handle_download(event):
    if await is_admin(event, admin_id):
        try:
            file_path = event.pattern_match.group(1).strip()
            if os.path.exists(file_path):
                await client.send_file(event.sender_id, file_path)
                await event.respond(f"File {file_path} sent successfully!")
            else:
                await event.respond(f"File {file_path} does not exist.")
        except FileNotFoundError:
            logger.error(f"File {file_path} not found during download.")
            await event.respond(f"Error: File {file_path} not found.")
        except PermissionError:
            logger.error(f"Permission denied for file {file_path}.")
            await event.respond(f"Error: Permission denied for {file_path}.")
        except Exception as e:
            logger.error(f"Error in /download command: {str(e)}")
            await event.respond(f"Error in downloading file: {str(e)}")


# Delete a specific file from the script folder.
async def handle_delete(event):
    if await is_admin(event, admin_id):
        try:
            file_path = event.pattern_match.group(1).strip()
            if os.path.exists(file_path):
                os.remove(file_path)
                await event.respond(f"File {file_path} deleted successfully!")
            else:
                await event.respond(f"File {file_path} does not exist.")
        except FileNotFoundError:
            logger.error(f"File {file_path} not found during deletion.")
            await event.respond(f"Error: File {file_path} not found.")
        except PermissionError:
            logger.error(f"Permission denied for file {file_path}.")
            await event.respond(f"Error: Permission denied for {file_path}.")
        except Exception as e:
            logger.error(f"Error in /delete command: {str(e)}")
            await event.respond(f"Error in deleting file: {str(e)}")


# Download all available media files from the media folder.
async def handle_all(event):
    if await is_admin(event, admin_id):
        try:

            def get_media_files(directory):
                media_files = []
                for root, dirs, files in os.walk(directory):
                    for file in files:
                        if file.lower().endswith(
                            (".jpg", ".jpeg", ".png", ".mp4", ".avi", ".mkv")
                        ):
                            media_files.append(os.path.join(root, file))
                return media_files

            media_files = get_media_files(all_media_dir)
            if media_files:
                for media_file in media_files:
                    await client.send_file(event.sender_id, media_file)
                await event.respond("All media files sent successfully!")
            else:
                await event.respond("No media files found in the media folder.")
        except FileNotFoundError as e:
            logger.error(f"File not found during download: {e}")
            await event.respond("Error: File not found.")
        except PermissionError as e:
            logger.error(f"Permission denied: {e}")
            await event.respond("Error: Permission denied.")
        except Exception as e:
            logger.error(f"Error in /all command: {str(e)}")
            await event.respond(f"Error in downloading all media files: {str(e)}")


# Create zip file containing files from project folder.
async def handle_zip(event):
    if await is_admin(event, admin_id):
        try:
            folder_paths = ["."]  # Add your desired folder paths here
            zip_filename = "media_files.zip"
            with zipfile.ZipFile(zip_filename, "w") as zipf:
                for folder_path in folder_paths:
                    for file_name in os.listdir(folder_path):
                        full_path = os.path.join(folder_path, file_name)
                        if os.path.isfile(full_path):
                            zipf.write(
                                full_path, os.path.relpath(full_path, folder_path)
                            )
            await client.send_file(event.sender_id, zip_filename)
            await event.respond("Zip file created and sent successfully!")
            os.remove(zip_filename)
        except FileNotFoundError as e:
            logger.error(f"File not found during zipping: {e}")
            await event.respond("Error: File not found.")
        except PermissionError as e:
            logger.error(f"Permission denied during zipping: {e}")
            await event.respond("Error: Permission denied.")
        except Exception as e:
            logger.error(f"Error in /zip command: {str(e)}")
            await event.respond(f"Error in creating zip file: {str(e)}")


# Initialize an iterator for letters
letters = iter(string.ascii_uppercase)


# Function to get the next letter in the sequence
def get_next_letter():
    global letters
    try:
        return next(letters)
    except StopIteration:
        letters = iter(string.ascii_uppercase)
        return next(letters)


# Automatically download received media files.
async def downloader(event):
    me = await client.get_me()
    if event.sender_id != me.id:
        sender = await event.get_sender()
        username = sender.username if sender.username else "None"
        user_id = sender.id if sender.id else "None"

        existing_folder = None
        for folder in os.listdir(all_media_dir):
            if f"@{username} - {user_id}" in folder:
                existing_folder = folder
                break

        if existing_folder:
            user_folder_name = existing_folder
        else:
            letter = get_next_letter()
            user_folder_name = f"{letter} - @{username} - {user_id}"

        user_folder_path = os.path.join(all_media_dir, user_folder_name)

        if not os.path.exists(user_folder_path):
            try:
                os.makedirs(user_folder_path)
                logger.info(f"Created folder for user: {user_folder_name}")
            except Exception as e:
                logger.error(f"Failed to create folder {user_folder_path}: {e}")
                await event.respond(
                    f"Error creating folder for user: {user_folder_name}"
                )
                return

        logger.info(
            f"Received media from {username} (ID: {user_id}). Starting download..."
        )
        try:
            total_size = event.file.size
            progress_bar = RichProgressBar(total_size)
            result = await event.download_media(
                file=user_folder_path, progress_callback=progress_bar
            )
            progress_bar.close()
            media_type = "photo" if event.photo else "video"
            logger.info(
                f"{media_type.capitalize()} downloaded successfully from {username} (ID: {user_id})"
            )
            await client.send_file(
                "me", result, caption=f"Downloaded by @H0lyFanz from {username}"
            )
        except FileNotFoundError as e:
            logger.error(f"File not found during download: {e}")
            await event.respond("File not found during the download.")
        except PermissionError as e:
            logger.error(f"Permission error during download: {e}")
            await event.respond("Permission error during the download.")
        except Exception as e:
            logger.error(
                f"Failed to download media from {username} (ID: {user_id}): {str(e)}"
            )
            await event.respond(f"Error in downloading media: {str(e)}")


# Main function to start the Telegram client and run it until disconnected.
async def main():
    global client, admin_id
    api_id, api_hash, admin_id = await load_config()
    client = TelegramClient("H0lyFanz", api_id, api_hash)

    # Register event handlers
    client.add_event_handler(
        show_welcome,
        events.NewMessage(func=lambda e: e.is_private and e.text == "/help"),
    )
    client.add_event_handler(
        handle_ping,
        events.NewMessage(func=lambda e: e.is_private and e.text == "/ping"),
    )
    client.add_event_handler(
        handle_status,
        events.NewMessage(func=lambda e: e.is_private and e.text == "/status"),
    )
    client.add_event_handler(
        handle_files,
        events.NewMessage(func=lambda e: e.is_private and e.text == "/files"),
    )
    client.add_event_handler(
        handle_check,
        events.NewMessage(func=lambda e: e.is_private and e.text == "/check"),
    )
    client.add_event_handler(
        handle_download,
        events.NewMessage(pattern=r"/download (.+)", func=lambda e: e.is_private),
    )
    client.add_event_handler(
        handle_delete,
        events.NewMessage(pattern=r"/delete (.+)", func=lambda e: e.is_private),
    )
    client.add_event_handler(
        handle_all, events.NewMessage(func=lambda e: e.is_private and e.text == "/all")
    )
    client.add_event_handler(
        handle_zip, events.NewMessage(func=lambda e: e.is_private and e.text == "/zip")
    )
    client.add_event_handler(
        downloader,
        events.NewMessage(
            func=lambda e: e.is_private and (e.photo or e.video) and e.media_unread
        ),
    )
    try:
        await client.start()
        logger.info("Bot is running...")
        await client.run_until_disconnected()
    except Exception as e:
        logger.critical(f"Unexpected error: {e}")
        await reconnect_client(client)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
