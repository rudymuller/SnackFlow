"""Authentication utilities (password hashing + verification).

This module centralizes password hashing and verification so other modules
(e.g., Usuario, AuthService) can reuse the same implementation and configuration
(salt size, iterations, algorithm).
"""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Tuple

# Configurable parameters
SALT_SIZE = 16  # bytes
HASH_ITERS = 100_000
ALGO = 'sha256'


def hash_password(password: str) -> str:
    """Return a string containing salt:hash, both hex-encoded.

    Example format: <salt_hex>:<key_hex>
    """
    if not isinstance(password, str):
        raise TypeError('password must be a string')
    salt = os.urandom(SALT_SIZE)
    key = hashlib.pbkdf2_hmac(ALGO, password.encode('utf-8'), salt, HASH_ITERS)
    return salt.hex() + ':' + key.hex()


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored salt:hash string.

    Returns True when the password is correct, False otherwise.
    """
    if not isinstance(password, str) or not isinstance(stored, str):
        return False
    try:
        salt_hex, key_hex = stored.split(':')
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(key_hex)
        got = hashlib.pbkdf2_hmac(ALGO, password.encode('utf-8'), salt, HASH_ITERS)
        # Use compare_digest for timing-attack-safe comparison
        # use hmac.compare_digest which is available and intended for
        # timing-safe bytes comparisons
        return hmac.compare_digest(got, expected)
    except Exception:
        return False


def split_storage(stored: str) -> Tuple[str, str]:
    """Split stored value into (salt_hex, key_hex) or raise ValueError."""
    s, k = stored.split(':')
    return s, k
