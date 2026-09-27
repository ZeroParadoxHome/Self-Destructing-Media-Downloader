# -*- coding:utf-8 -*-
"""Dual-mode credential loading: .env first, encrypted store second, prompt last."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from .security import decrypt_from_file, encrypt_to_file

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
SECRETS_PATH = PROJECT_ROOT / ".secrets.bin"
KEY_PATH = PROJECT_ROOT / ".secrets.key"


@dataclass(frozen=True)
class Config:
    """Runtime configuration resolved from .env, encrypted secrets, or a prompt."""

    api_id: int
    api_hash: str
    admin_id: int
    retention_days: int = 30
    max_storage_mb: int = 1024


def _as_int(name: str, value: str) -> int:
    """Convert a configuration string to int with a clear error message.

    Args:
        name: Variable name used in the error message.
        value: Raw string value.

    Returns:
        The parsed integer.

    Raises:
        ValueError: When value is not an integer.
    """
    try:
        return int(value.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc


def _from_env(env_path: Path) -> Config | None:
    """Build a Config from a .env file, or return None if absent/incomplete.

    Args:
        env_path: Path to the .env file.

    Returns:
        A Config when API_ID, API_HASH and ADMIN_ID are all set; None otherwise.
    """
    if not env_path.is_file():
        return None
    values = dotenv_values(env_path)
    api_id_raw = values.get("API_ID")
    api_hash_raw = values.get("API_HASH")
    admin_id_raw = values.get("ADMIN_ID")
    if not (api_id_raw and api_hash_raw and admin_id_raw):
        return None
    return Config(
        api_id=_as_int("API_ID", api_id_raw),
        api_hash=api_hash_raw.strip(),
        admin_id=_as_int("ADMIN_ID", admin_id_raw),
        retention_days=_as_int("RETENTION_DAYS", values.get("RETENTION_DAYS") or "30"),
        max_storage_mb=_as_int(
            "MAX_STORAGE_MB", values.get("MAX_STORAGE_MB") or "1024"
        ),
    )


def _from_secrets(bin_path: Path, key_path: Path) -> Config | None:
    """Build a Config from the encrypted secrets file, or None if absent.

    Args:
        bin_path: Path to the encrypted JSON payload.
        key_path: Path to the Fernet key file.

    Returns:
        A Config when the file exists and decrypts; None otherwise.

    Raises:
        RuntimeError: When the file exists but cannot be decrypted.
    """
    if not bin_path.is_file():
        return None
    data: dict[str, Any] = json.loads(decrypt_from_file(bin_path, key_path))
    retention = data.get("RETENTION_DAYS", data.get("retention_days", 30))
    storage = data.get("MAX_STORAGE_MB", data.get("max_storage_mb", 1024))
    return Config(
        api_id=_as_int("API_ID", str(data.get("API_ID", data.get("api_id", "")))),
        api_hash=str(data.get("API_HASH", data.get("api_hash", ""))),
        admin_id=_as_int(
            "ADMIN_ID", str(data.get("ADMIN_ID", data.get("admin_id", "")))
        ),
        retention_days=_as_int("RETENTION_DAYS", str(retention)),
        max_storage_mb=_as_int("MAX_STORAGE_MB", str(storage)),
    )


def _prompt_and_store(bin_path: Path, key_path: Path) -> Config:
    """Prompt in the terminal for credentials and persist them encrypted.

    Args:
        bin_path: Destination file for the encrypted JSON payload.
        key_path: Key file, created automatically when missing.

    Returns:
        The Config built from the entered values.
    """
    api_id = _as_int("API_ID", input("Enter your API_ID: "))
    api_hash = input("Enter your API_HASH: ").strip()
    admin_id = _as_int("ADMIN_ID", input("Enter the Admin ID: "))
    payload = json.dumps({"api_id": api_id, "api_hash": api_hash, "admin_id": admin_id})
    encrypt_to_file(payload, bin_path, key_path)
    return Config(api_id=api_id, api_hash=api_hash, admin_id=admin_id)


def load_config() -> Config:
    """Resolve configuration in priority order: .env, then .secrets.bin, then prompt.

    Reads the three required credentials from .env when present and complete
    (no prompts, loaded silently via python-dotenv). Otherwise decrypts the
    local .secrets.bin store if it exists. Otherwise prompts interactively
    and encrypts the entered values to .secrets.bin — no plaintext
    settings.json is ever written.

    Returns:
        The resolved runtime configuration.
    """
    config = _from_env(ENV_PATH)
    if config is None:
        config = _from_secrets(SECRETS_PATH, KEY_PATH)
    if config is None:
        config = _prompt_and_store(SECRETS_PATH, KEY_PATH)
    return config
