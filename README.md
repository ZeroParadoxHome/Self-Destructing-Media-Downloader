# Self-Destructing Media Downloader

A Python script that automatically downloads media (photos and videos) from private messages and replies to your "Saved Messages" in Telegram. This script simplifies the process of archiving and retrieving media content from Telegram conversations.

## Features

- Automatically download photos and videos from private messages
- Organize downloaded media by user
- Admin commands for managing the bot and downloaded files
- Create ZIP archives of downloaded media
- Ping functionality to check bot status
- File management commands (list, download, delete)

## Prerequisites

Before running the script, you need to:

1. Create a Telegram application and obtain the `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org/).
2. Get your Telegram user ID (Admin ID) using the [@userinfobot](https://t.me/userinfobot) on Telegram.

## Installation

1. Clone this repository:

```bash
git clone https://github.com/ZeroParadoxHome/Self-Destructing-Media-Downloader.git
cd Self-Destructing-Media-Downloader
```

2. Install the required packages:

```bash
pip install -r requirements.txt
```

## Configuration

The script will prompt you to enter your `API_ID`, `API_HASH`, and `Admin ID` when you run it for the first time. These values will be saved in a `settings.json` file for future use.

## Usage

To run the script, use the following command:

```bash
python TSDMD.py
```

Once the bot is running, you can use the following commands:

- `/help` - Display the help menu with available commands
- `/ping` - Check if the bot is alive and measure ping time
- `/status` - Get the number of downloaded files (Photos/Videos) in the media folder
- `/files` - List all files in the script folder
- `/check` - Perform a check for new files in the media folder
- `/download [file_path]` - Download a specific file from the script folder
- `/delete [file_path]` - Delete a specific file from the script folder
- `/all` - Download all available media files from the media folder
- `/zip` - Create and send a zip file containing files from the project folder

## How it works

1. The bot automatically downloads media files (photos and videos) sent to it via private messages.
2. Downloaded files are organized in folders named after the sender's username and user ID.
3. The bot can be controlled using various admin commands to manage downloaded files and check the bot's status.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the [MIT License](LICENSE).

## Disclaimer

This tool is for educational purposes only, So Please respect copyright laws and the privacy of others when using this script.

## Support

Please open an issue on the GitHub repository if you encounter any issues or have questions.
