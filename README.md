# TSDMD — The Self-Destructing Media Downloader

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Telethon](https://img.shields.io/badge/Telethon-1.38%2B-green)
![License MIT](https://img.shields.io/badge/License-MIT-yellow)

Archives Telegram view-once media before it disappears.

## Features

- View-once TTL filter — downloads only self-destructing media, ignores the rest
- Per-sender folders (`downloads/<id>-<handle>/`) for stable, reviewable archives
- Saved Messages echo — a copy of every archive lands in your Saved Messages
- 9 admin slash commands for status, browsing, export, and cleanup
- Retention engine — age expiry plus storage quota, oldest-first, on a 6h cycle
- Encrypted credentials — Fernet-encrypted local store, no plaintext secrets
- Systemd user service for always-on Linux servers

## Requirements

- Python 3.10+
- `telethon>=1.38.0`, `python-dotenv>=1.0.0`, `cryptography>=42.0.0`, `aiofiles>=23.2.0`, `rich>=13.7.0` (see `requirements.txt`)

## Quickstart

```bash
git clone https://github.com/ZeroParadoxHome/Self-Destructing-Media-Downloader.git
cd Self-Destructing-Media-Downloader
```

Create and activate a virtualenv:

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux
python3 -m venv venv
source venv/bin/activate
```

Then install and configure:

```bash
pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env   # Linux
```

Fill in `API_ID`, `API_HASH`, and `ADMIN_ID` in `.env` (get the first two at
<https://my.telegram.org>, the third from [@userinfobot](https://t.me/userinfobot)).

## Configuration

| Variable         | Required | Default | Purpose                              |
|------------------|----------|---------|--------------------------------------|
| `API_ID`         | Yes      | —       | Telegram app ID                      |
| `API_HASH`       | Yes      | —       | Telegram app hash                    |
| `ADMIN_ID`       | Yes      | —       | Your Telegram user ID (access gate)  |
| `RETENTION_DAYS` | No       | `30`    | Archive age limit before auto-delete |
| `MAX_STORAGE_MB` | No       | `1024`  | Storage quota for the downloads dir  |

Credential loading is `.env`-first: when `.env` holds all three required
values, they are used silently with no prompts. Otherwise TSDMD prompts
interactively in the terminal once, encrypts the answers into `.secrets.bin`
(Fernet, key in `.secrets.key`), and reuses them on later runs. No plaintext
`settings.json` is ever written.

## Usage

```bash
python main.py
```

On first run with no authorized session, TSDMD performs an interactive
login in the terminal (phone number, login code, 2FA password when set) and
stores the session as `tsdmd.session`. Later runs reuse it with no prompts.
Stop with Ctrl+C.

### Run as a systemd user service (Linux)

```bash
mkdir -p ~/.config/systemd/user
cp systemd/tsdmd.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now tsdmd.service
journalctl --user -u tsdmd.service -f
```

## Commands

Send these as private messages to your own account from the admin ID:

| Command               | Purpose                                  |
|-----------------------|------------------------------------------|
| `/help`               | Show the command list                    |
| `/ping`               | Measure Telegram round-trip latency      |
| `/status`             | File counts and storage used vs. quota   |
| `/files`              | Sender folders with copyable file paths  |
| `/all`                | Send up to 30 archived files to the chat |
| `/check <path>`       | Check a path exists inside downloads     |
| `/download <path>`    | Send one archived file to the chat       |
| `/delete <path>`      | Delete a file or folder inside downloads |
| `/zip`                | Export downloads as a zip archive        |

## Project structure

```text
main.py                  # entrypoint: connect, register, serve
tsdmd/
  client/                # Telethon construction, flood-wait retry
  commands/              # admin slash-command router and handlers
  config/                # .env / encrypted-store loader, Fernet helpers
  downloader/            # TTL filter, sender paths, download-and-echo
  retention/             # age + quota enforcement, 6h scheduler
systemd/tsdmd.service    # user service unit
.env.example             # optional configuration template
```

## Security notes

- Credentials live in `.env` (your file, never committed) or encrypted in
  `.secrets.bin` via Fernet; the key file `.secrets.key` is written with
  restrictive permissions (0600, best-effort on Windows).
- Handlers only answer the configured `ADMIN_ID`; all other senders are ignored.
- `/download`, `/delete`, `/check`, and `/zip` resolve every path and refuse
  anything outside `downloads/` (symlinks included).

## Troubleshooting

- **Login code never arrives** — request it from an already-logged-in Telegram
  app on the same number, then retry; codes take a minute on new devices.
- **`SessionPasswordNeededError` loop** — enter the 2FA *password*, not another
  login code, at the password prompt.
- **`FloodWaitError` sleeps** — normal Telegram rate limiting; TSDMD waits and
  retries automatically, no action needed.
- **Empty archive / no downloads** — only view-once media in private chats is
  saved; regular photos, videos, and group media are ignored by design.

## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/my-change`).
3. Keep changes scoped; match existing style (type hints, docstrings).
4. Verify with `black`, `isort`, `flake8`, and `pyright`.
5. Open a Pull Request describing the change and its testing.

## License

This project is open source and available under the [MIT License](LICENSE).

## Disclaimer

For educational purposes. Respect copyright law and the privacy of others.
