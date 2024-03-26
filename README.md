# Self-Destructing Media Downloader

A Python script that automatically downloads media (photos and videos) from privates and replied messages to your "Saved Messages". This script simplifies the process of archiving and retrieving media content from Telegram conversations.

## Prerequisites

Before running the script, you need to:

1. Create a Telegram application and obtain the `API_ID` and `API_HASH`.
2. Set the `API_ID` and `API_HASH` environment variables with the correct values, or be prepared to enter them when prompted by the script.

## Installation

1. First, clone this repository from GitHub:

```bash
git clone https://github.com/ZeroParadoxHome/Self-Destructing-Media-Downloader.git
```

2. Then, navigate to the project directory and install the required packages using the "requirements.txt" file:

```bash
cd Self-Destructing-Media-Downloader
pip install -r requirements.txt
```

3. Set the API_ID and API_HASH environment variables with the correct values for your Telegram application.

## Running

To run the script, use the following command:

```bash
python SDMD.py
```

The script will prompt you to enter your API_ID and API_HASH. After entering these values, the script will start running.
