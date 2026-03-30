"""Secrets vault encryption service using Fernet symmetric encryption.

The vault key is read from the VAULT_KEY environment variable, which must be
a URL-safe base64-encoded 32-byte key (generated with Fernet.generate_key()).

If VAULT_KEY is not set a per-process ephemeral key is used — secrets will
be unreadable after restart.  Set VAULT_KEY in production.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is not None:
        return _fernet
    from cryptography.fernet import Fernet  # noqa: PLC0415

    key = os.getenv("VAULT_KEY", "")
    if not key:
        key = Fernet.generate_key().decode()
        log.warning("VAULT_KEY not set — using ephemeral key. Secrets will not survive restart.")
    _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string and return a base64 ciphertext string."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """Decrypt a ciphertext string and return plaintext."""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def can_access(secret, username: str, is_admin: bool) -> bool:
    """Return True if the given user can access the secret."""
    if is_admin:
        return True
    allowed = [u.strip() for u in (secret.allowed_users or "").split(",") if u.strip()]
    return "*" in allowed or username in allowed


def generate_key() -> str:
    """Generate a new Fernet key suitable for VAULT_KEY."""
    from cryptography.fernet import Fernet  # noqa: PLC0415

    return Fernet.generate_key().decode()
