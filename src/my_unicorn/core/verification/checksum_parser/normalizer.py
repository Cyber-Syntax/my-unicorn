"""Hash normalization and encoding detection utilities."""

from __future__ import annotations

import base64

from my_unicorn.constants import (
    DEFAULT_HASH_TYPE,
    HASH_PREFERENCE_ORDER,
    HashType,
)
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


def convert_base64_to_hex(base64_hash: str) -> str:
    """Convert base64 encoded hash to hexadecimal string."""

    try:
        return base64.b64decode(base64_hash).hex()
    except Exception as exc:  # pragma: no cover - kept for safety
        logger.exception("❌ Failed to convert base64 to hex")
        msg = f"Invalid base64 hash: {base64_hash}"
        raise ValueError(msg) from exc


def _is_likely_hex(hash_value: str) -> bool:
    """Detect if a hash value is likely hexadecimal encoding.

    Checks if the hash matches common hash algorithm lengths (MD5, SHA1,
    SHA256, SHA512) and contains only valid hexadecimal characters.

    Args:
        hash_value: The hash value to check.

    Returns:
        True if the hash appears to be hexadecimal, False otherwise.

    Examples:
        >>> _is_likely_hex("abc123def4567890abcdef1234567890")  # MD5
        True
        >>> _is_likely_hex("deadbeef" * 8)  # SHA256
        True
        >>> _is_likely_hex("DEADBEEF" * 16)  # SHA512 uppercase
        True
        >>> _is_likely_hex("JNmYBTG9lqXt")  # Base64 - wrong length
        False
        >>> _is_likely_hex("ghijklmn" * 8)  # Invalid hex characters
        False
    """
    hash_value = hash_value.strip()
    hash_length = len(hash_value)

    # Check if length matches known hash algorithms
    # MD5: 32, SHA1: 40, SHA256: 64, SHA512: 128
    if hash_length not in (32, 40, 64, 128):
        return False

    # Check if all characters are valid hexadecimal
    return all(c in "0123456789abcdefABCDEF" for c in hash_value)


def _is_likely_base64(hash_value: str) -> bool:
    """Detect if a hash value is likely base64 encoding.

    Checks if the hash has valid base64 characteristics: length is multiple
    of 4, contains only valid base64 characters, and padding (=) only at end.

    Args:
        hash_value: The hash value to check.

    Returns:
        True if the hash appears to be base64-encoded, False otherwise.

    Examples:
        >>> _is_likely_base64("JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8=")
        True
        >>> _is_likely_base64("JNmYBTG9")  # Valid, no padding needed (8 chars)
        True
        >>> _is_likely_base64("abc123")  # Not multiple of 4 (6 chars)
        False
        >>> _is_likely_base64("JN=mYBTG")  # Padding in middle
        False
        >>> _is_likely_base64("")  # Empty string
        False
    """
    hash_value = hash_value.strip()
    hash_length = len(hash_value)

    # Base64 strings must be multiples of 4
    if hash_length == 0 or hash_length % 4 != 0:
        return False

    # Valid base64 alphabet (uppercase + lowercase + digits + special chars)
    base64_chars = (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
    )

    # Find first padding character
    padding_index = hash_value.find("=")

    # If padding exists, it must be at the end (last 2 positions)
    if padding_index != -1 and padding_index < hash_length - 2:
        return False

    # All characters must be valid base64
    return all(c in base64_chars for c in hash_value)


def _normalize_hash_value(hash_value: str) -> str:
    """Normalize a hash value to hexadecimal representation.

    Detects encoding (hex vs base64) and converts to hexadecimal.
    Handles algorithm prefixes (e.g., "sha256:abc123...").

    This function prevents corruption of hexadecimal hashes that contain only
    valid base64 characters (e.g., "deadbeef12345678..."). Without proper
    detection, such hashes would be incorrectly decoded as base64, producing
    garbage output. The fix ensures hex detection runs BEFORE base64 decode.

    The function applies the following priority:
        1. If hex → return unchanged (lowercased)
        2. If base64 → convert to hex
        3. Otherwise → return unchanged

    Args:
        hash_value: The hash value to normalize.

    Returns:
        The normalized hash value as hexadecimal string (lowercase).

    Examples:
        >>> # Hex hash preserved (not corrupted)
        >>> _normalize_hash_value("deadbeef12345678" * 4)  # SHA256
        'deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678'
        >>> # Base64 converted to hex
        >>> b64 = "JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8="
        >>> _normalize_hash_value(b64)
        '24d9980531bd96a5edfd55e67acdf6a6eddb9f3fd868a3337e31552fed09f92f'
        >>> # Algorithm prefix stripped
        >>> _normalize_hash_value("sha256:deadbeef12345678" * 4)
        'deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678'
    """
    # Type coercion: convert non-string input to string
    hash_value = str(hash_value)

    # Strip algorithm prefix (e.g., "sha256:")
    if ":" in hash_value:
        _, _, hash_value = hash_value.partition(":")

    # CRITICAL FIX: Detect hex BEFORE attempting base64 decode
    if _is_likely_hex(hash_value):
        return hash_value.lower()

    # If not hex, check if base64
    if _is_likely_base64(hash_value):
        try:
            return convert_base64_to_hex(hash_value)
        except ValueError:
            # If base64 decode fails, return unchanged
            return hash_value

    # Unknown format - return unchanged
    return hash_value


def _extract_hash_from_dict(data: dict) -> tuple[str, HashType] | None:
    """Extract hash value and algorithm from a dictionary.

    Args:
        data: Dictionary containing hash information keyed by algorithm.

    Returns:
        A tuple of (normalized_hash_value, algorithm) or None if no hash found.
    """
    for algo in HASH_PREFERENCE_ORDER:
        if algo in data:
            return _normalize_hash_value(data[algo]), algo

    if data:
        first_key, first_value = next(iter(data.items()))
        return (
            _normalize_hash_value(first_value),
            first_key if isinstance(first_key, str) else DEFAULT_HASH_TYPE,
        )

    return None
