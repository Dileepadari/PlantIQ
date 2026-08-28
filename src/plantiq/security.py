"""Password hashing.

The original database stored passwords in clear text. Hashes are written for
every new account, and any surviving clear-text row is re-hashed in place the
first time that user signs in successfully.
"""

from werkzeug.security import check_password_hash, generate_password_hash

# Prefixes Werkzeug uses for the digests it produces.
_HASH_PREFIXES = ("pbkdf2:", "scrypt:", "argon2:")


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def is_hashed(stored: str) -> bool:
    return str(stored).startswith(_HASH_PREFIXES)


def verify_password(stored: str, candidate: str) -> bool:
    """True when ``candidate`` matches, for hashed and legacy rows alike."""
    if stored is None:
        return False
    if is_hashed(stored):
        return check_password_hash(stored, candidate)
    return str(stored) == str(candidate)
