# AGENTS.md

Modular Python project: `tsdmd/` package (config, client, downloader, commands, retention) + `main.py` entrypoint — a Telegram **userbot** (Telethon client logged into a user account, not a Bot API bot). Legacy single-file `TSDMD.py` is retired.

## Running

- Repo root has a `venv/` virtualenv — use it (`venv/Scripts/activate` on Windows) instead of installing globally. `pip install -r requirements.txt` then `python main.py`.
- First run is **interactive**: credentials via `.env` or terminal prompt, then Telegram login code. Saves to `.env`/`.secrets.bin` + `tsdmd.session`. Cannot be run headless/CI without pre-existing session and credentials — don't try to automate a full run; syntax-check with `python -m py_compile main.py` instead.

## Secrets

Never commit, print, or move credentials or sessions. `.gitignore` excludes `.env`, `.secrets.bin`, `.secrets.key`, `tsdmd.session`, `downloads/`, `venv/`, `__pycache__/`, and IDE folders — ensure any new runtime artifact is also ignored.

## Code conventions (tsdmd/)

- New admin commands need a handler in `commands/handlers.py`, a registration in `COMMANDS`, and a line in `router.py` `USAGE_HINT`. Every handler must start with the `is_admin(event, config.admin_id)` guard.
- Text responses go through `_respond()` (edit-first, reply fallback) — never call `event.reply`/`event.edit` directly. File deliveries stay separate new messages via `client.send_file`.
- Auto-download only triggers on expiring media (`filter.is_expiring_media`: private, incoming, TTL present) — keep that guard when touching `downloader/engine.py`.
- Downloads go to `downloads/<user_id>-<handle>/`; sender folders are matched by that format, so don't rename it.
- Keep the six-gate verification green; only pyright has a config file (`pyrightconfig.json`, dev-only, gitignored) — black/isort/flake8 run on defaults with `--extend-ignore=E501` passed on the CLI, so don't add new config files.

## Verification

No tests or CI exist. Run all six gates before finishing: `black --check tsdmd main.py`, `isort --check-only tsdmd main.py`, `flake8 tsdmd main.py --extend-ignore=E501`, `pyright tsdmd main.py` (0 errors), `pylint --errors-only tsdmd main.py`, `py_compile`. Treat nontrivial changes as untested without a live Telegram session.
