# -*- coding:utf-8 -*-
"""Fernet symmetric encryption helpers for local credential storage.

Keys and plaintext are never logged or printed by this module.
"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


def get_or_create_key(key_path: Path) -> bytes:
    """Return the Fernet key stored at key_path, generating it if absent.

    The key file is persisted with 0600 permissions on POSIX systems.
    On platforms that reject permission changes (Windows, some Termux
    filesystems) this is best-effort and never raises.

    Args:
        key_path: Filesystem path of the key file.

    Returns:
        The 32-byte urlsafe-base64 Fernet key as bytes.
    """
    if key_path.exists():
        return key_path.read_bytes().strip()
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return key


def encrypt_to_file(plaintext: str, bin_path: Path, key_path: Path) -> None:
    """Encrypt plaintext with the key at key_path and write it to bin_path.

    Args:
        plaintext: Secret text to encrypt (never logged).
        bin_path: Destination file for the Fernet token.
        key_path: Key file, created automatically when missing.
    """
    token = Fernet(get_or_create_key(key_path)).encrypt(plaintext.encode("utf-8"))
    bin_path.write_bytes(token)


def decrypt_from_file(bin_path: Path, key_path: Path) -> str:
    """Decrypt the Fernet token at bin_path using the key at key_path.

    Args:
        bin_path: File containing the Fernet token.
        key_path: Key file, created automatically when missing.

    Returns:
        The decrypted plaintext.

    Raises:
        RuntimeError: When the file is unreadable, tampered with, or the
            wrong key was used. The error message contains no secret material.
    """
    try:
        token = bin_path.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"Cannot read encrypted secrets file: {bin_path}") from exc
    try:
        return Fernet(get_or_create_key(key_path)).decrypt(token).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError(
            f"Cannot decrypt {bin_path}: wrong key or corrupted data"
        ) from exc
