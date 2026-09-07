# AGENTS.md

Single-file Python project: `TSDMD.py` is the entire app — a Telegram **userbot** (Telethon client logged into a user account, not a Bot API bot).

## Running

- `pip install -r requirements.txt` then `python TSDMD.py`. Repo root has a `venv/` virtualenv — use it (`venv/Scripts/activate` on Windows) instead of installing globally.
- First run is **interactive**: prompts for `API_ID`, `API_HASH`, `Admin ID`, then Telegram login code. Saves to `settings.json` + `H0lyFanz.session`. Cannot be run headless/CI without pre-existing session and credentials — don't try to automate a full run; syntax-check with `python -m py_compile TSDMD.py` instead.

## Secrets

Running the script creates `settings.json` (API keys, admin ID) and `H0lyFanz.session` (auth). Never commit, print, or move these. `.gitignore` excludes `Media/`, `settings.json`, `*.session`, `*.session-journal`, `*.zip`, `venv/`, `__pycache__/`, and IDE folders — ensure any new runtime artifact is also ignored.

## Code conventions (TSDMD.py)

- All handlers are registered in `main()` via `client.add_event_handler` — a new command needs both a handler function and a registration there. Handlers rely on module globals `client` and `admin_id` set in `main()`.
- Every command handler must start with `if await is_admin(event, admin_id):`.
- Auto-download only triggers on unread private media (`e.photo or e.video and e.media_unread`) and skips self-sent messages; keep that guard when touching `downloader()`.
- Downloads go to `Media/<letter> - @username - <user_id>/`; media folders are matched by the `@username - <id>` substring, so don't rename that format.

## Verification

No tests, lint, or CI config exist. Verified behavior = script actually running against Telegram; treat nontrivial changes as untested without a live session.
