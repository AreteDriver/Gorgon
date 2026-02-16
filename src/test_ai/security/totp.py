"""TOTP-based two-factor authentication.

Implements RFC 6238 Time-Based One-Time Password using HMAC-SHA1.
Provides TOTP secret generation, QR URI creation, code verification
with clock-skew tolerance, and backup code management.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import struct
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# TOTP defaults per RFC 6238
_TOTP_PERIOD = 30  # seconds
_TOTP_DIGITS = 6
_TOTP_SKEW_STEPS = 1  # Allow +/- 1 period for clock drift
_SECRET_BYTES = 20  # 160-bit secret (standard for TOTP)
_BACKUP_CODE_COUNT = 10
_BACKUP_CODE_LENGTH = 8


@dataclass
class TOTPSetup:
    """Data returned when a user enrolls in 2FA."""

    secret: str
    provisioning_uri: str
    backup_codes: list[str]


@dataclass
class TOTPState:
    """Persistent 2FA state for a user."""

    user_id: str
    secret: str
    enabled: bool = False
    backup_codes: list[str] = field(default_factory=list)
    last_used_counter: int = 0
    created_at: float = field(default_factory=time.time)


def generate_secret() -> str:
    """Generate a random TOTP secret encoded as base32.

    Returns:
        Base32-encoded secret string (no padding).
    """
    raw = secrets.token_bytes(_SECRET_BYTES)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def generate_backup_codes(
    count: int = _BACKUP_CODE_COUNT,
    length: int = _BACKUP_CODE_LENGTH,
) -> list[str]:
    """Generate a set of single-use backup codes.

    Args:
        count: Number of codes to generate.
        length: Length of each code in hex characters.

    Returns:
        List of backup code strings.
    """
    return [secrets.token_hex(length // 2) for _ in range(count)]


def build_provisioning_uri(
    secret: str,
    user_id: str,
    issuer: str = "Gorgon",
) -> str:
    """Build an otpauth:// URI for QR code generation.

    Args:
        secret: Base32-encoded TOTP secret.
        user_id: User identifier (typically email).
        issuer: Service name displayed in authenticator apps.

    Returns:
        otpauth:// URI string.
    """
    # URL-encode components
    from urllib.parse import quote

    label = f"{quote(issuer)}:{quote(user_id)}"
    params = f"secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits={_TOTP_DIGITS}&period={_TOTP_PERIOD}"
    return f"otpauth://totp/{label}?{params}"


def _hotp(secret_b32: str, counter: int) -> str:
    """Compute HOTP value per RFC 4226.

    Args:
        secret_b32: Base32-encoded secret (padding optional).
        counter: 8-byte counter value.

    Returns:
        Zero-padded OTP string.
    """
    # Decode base32 secret (add padding if needed)
    padded = secret_b32 + "=" * (-len(secret_b32) % 8)
    key = base64.b32decode(padded, casefold=True)

    # HMAC-SHA1 of counter
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()

    # Dynamic truncation
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    code = code_int % (10**_TOTP_DIGITS)
    return str(code).zfill(_TOTP_DIGITS)


def compute_totp(secret: str, timestamp: Optional[float] = None) -> str:
    """Compute current TOTP value.

    Args:
        secret: Base32-encoded secret.
        timestamp: Unix timestamp (defaults to now).

    Returns:
        TOTP code string.
    """
    if timestamp is None:
        timestamp = time.time()
    counter = int(timestamp) // _TOTP_PERIOD
    return _hotp(secret, counter)


def verify_totp(
    secret: str,
    code: str,
    last_used_counter: int = 0,
    timestamp: Optional[float] = None,
) -> tuple[bool, int]:
    """Verify a TOTP code with clock-skew tolerance.

    Checks the code against the current time step and +/- ``_TOTP_SKEW_STEPS``
    adjacent steps. Rejects codes whose counter is at or below
    ``last_used_counter`` to prevent replay attacks.

    Args:
        secret: Base32-encoded secret.
        code: User-provided OTP code.
        last_used_counter: Counter from last successful verification.
        timestamp: Unix timestamp (defaults to now).

    Returns:
        Tuple of (valid, counter_used). ``counter_used`` should be persisted
        as the new ``last_used_counter`` on success.
    """
    if timestamp is None:
        timestamp = time.time()

    current_counter = int(timestamp) // _TOTP_PERIOD

    for offset in range(-_TOTP_SKEW_STEPS, _TOTP_SKEW_STEPS + 1):
        check_counter = current_counter + offset
        if check_counter <= last_used_counter:
            continue  # Prevent replay

        expected = _hotp(secret, check_counter)
        if hmac.compare_digest(expected, code):
            return True, check_counter

    return False, 0


class TOTPManager:
    """Manages TOTP enrollment, verification, and backup codes.

    Stores 2FA state in-memory. In production, state should be persisted
    to the database backend.
    """

    def __init__(self) -> None:
        self._users: dict[str, TOTPState] = {}

    def setup_totp(self, user_id: str, issuer: str = "Gorgon") -> TOTPSetup:
        """Begin 2FA enrollment for a user.

        Generates a new secret and backup codes. The user must verify a code
        via :meth:`confirm_setup` before 2FA is enforced.

        Args:
            user_id: User identifier.
            issuer: Service name for authenticator apps.

        Returns:
            Setup data including secret, provisioning URI, and backup codes.
        """
        secret = generate_secret()
        backup_codes = generate_backup_codes()
        uri = build_provisioning_uri(secret, user_id, issuer)

        # Store pending state (not yet enabled)
        self._users[user_id] = TOTPState(
            user_id=user_id,
            secret=secret,
            enabled=False,
            backup_codes=backup_codes,
        )

        logger.info("TOTP setup initiated for user %s", user_id)
        return TOTPSetup(secret=secret, provisioning_uri=uri, backup_codes=backup_codes)

    def confirm_setup(self, user_id: str, code: str) -> bool:
        """Confirm 2FA setup by verifying a code from the authenticator.

        Args:
            user_id: User identifier.
            code: TOTP code from authenticator app.

        Returns:
            True if code is valid and 2FA is now enabled.
        """
        state = self._users.get(user_id)
        if not state:
            return False

        valid, counter = verify_totp(state.secret, code)
        if valid:
            state.enabled = True
            state.last_used_counter = counter
            logger.info("TOTP confirmed and enabled for user %s", user_id)
            return True

        logger.warning("TOTP confirmation failed for user %s", user_id)
        return False

    def verify(self, user_id: str, code: str) -> bool:
        """Verify a TOTP code or backup code for login.

        Args:
            user_id: User identifier.
            code: TOTP code or backup code.

        Returns:
            True if verification succeeds.
        """
        state = self._users.get(user_id)
        if not state or not state.enabled:
            return False

        # Try TOTP first
        valid, counter = verify_totp(state.secret, code, state.last_used_counter)
        if valid:
            state.last_used_counter = counter
            return True

        # Try backup codes (single-use)
        normalized = code.strip().lower()
        if normalized in state.backup_codes:
            state.backup_codes.remove(normalized)
            logger.info(
                "Backup code used for user %s (%d remaining)",
                user_id,
                len(state.backup_codes),
            )
            return True

        return False

    def is_enabled(self, user_id: str) -> bool:
        """Check if 2FA is enabled for a user.

        Args:
            user_id: User identifier.

        Returns:
            True if 2FA is enabled.
        """
        state = self._users.get(user_id)
        return state is not None and state.enabled

    def disable(self, user_id: str) -> bool:
        """Disable 2FA for a user.

        Args:
            user_id: User identifier.

        Returns:
            True if 2FA was disabled.
        """
        if user_id in self._users:
            del self._users[user_id]
            logger.info("TOTP disabled for user %s", user_id)
            return True
        return False

    def regenerate_backup_codes(self, user_id: str) -> list[str] | None:
        """Regenerate backup codes for a user.

        Args:
            user_id: User identifier.

        Returns:
            New backup codes, or None if 2FA is not enabled.
        """
        state = self._users.get(user_id)
        if not state or not state.enabled:
            return None

        state.backup_codes = generate_backup_codes()
        logger.info("Backup codes regenerated for user %s", user_id)
        return state.backup_codes

    def get_backup_code_count(self, user_id: str) -> int:
        """Get remaining backup code count for a user.

        Args:
            user_id: User identifier.

        Returns:
            Number of remaining backup codes (0 if 2FA not enabled).
        """
        state = self._users.get(user_id)
        if not state:
            return 0
        return len(state.backup_codes)


# Global instance
_totp_manager: TOTPManager | None = None


def get_totp_manager() -> TOTPManager:
    """Get or create the global TOTP manager."""
    global _totp_manager
    if _totp_manager is None:
        _totp_manager = TOTPManager()
    return _totp_manager
