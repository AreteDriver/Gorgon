"""API key management with scopes and rotation.

Provides API key lifecycle management including:
- Key generation with configurable scopes
- Key rotation with grace period for old keys
- Expiration enforcement
- Per-key rate limiting metadata
- Key revocation
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

_KEY_PREFIX = "gorgon_"
_KEY_BYTES = 32  # 256-bit keys
_DEFAULT_EXPIRY_DAYS = 90
_ROTATION_GRACE_PERIOD = 86400  # 24 hours


class APIKeyScope(str, Enum):
    """Scopes that control what an API key can access."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"
    WORKFLOWS = "workflows"
    EXECUTIONS = "executions"
    SETTINGS = "settings"
    WEBHOOKS = "webhooks"


# Scope hierarchy: higher scopes include lower ones
_SCOPE_HIERARCHY: dict[APIKeyScope, set[APIKeyScope]] = {
    APIKeyScope.ADMIN: {
        APIKeyScope.READ,
        APIKeyScope.WRITE,
        APIKeyScope.EXECUTE,
        APIKeyScope.WORKFLOWS,
        APIKeyScope.EXECUTIONS,
        APIKeyScope.SETTINGS,
        APIKeyScope.WEBHOOKS,
    },
    APIKeyScope.WRITE: {APIKeyScope.READ},
    APIKeyScope.EXECUTE: {APIKeyScope.READ},
}


@dataclass
class APIKey:
    """An API key with metadata."""

    key_id: str
    key_hash: str  # SHA-256 hash of the full key (never store plaintext)
    user_id: str
    name: str
    scopes: set[APIKeyScope]
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    last_used: Optional[float] = None
    revoked: bool = False
    revoked_at: Optional[float] = None
    ip_whitelist: list[str] = field(default_factory=list)
    rate_limit_rpm: int = 60  # requests per minute
    metadata: dict = field(default_factory=dict)

    # For rotation: the previous key hash that's still valid during grace period
    previous_key_hash: Optional[str] = None
    previous_key_expires: Optional[float] = None

    @property
    def is_expired(self) -> bool:
        """Check if key has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if key is valid (not revoked or expired)."""
        return not self.revoked and not self.is_expired

    def has_scope(self, required: APIKeyScope) -> bool:
        """Check if key has the required scope.

        Args:
            required: The scope to check for.

        Returns:
            True if the key has the required scope (directly or via hierarchy).
        """
        if required in self.scopes:
            return True

        # Check hierarchy
        for scope in self.scopes:
            inherited = _SCOPE_HIERARCHY.get(scope, set())
            if required in inherited:
                return True

        return False

    def to_dict(self) -> dict:
        """Serialize for API responses (no sensitive data)."""
        return {
            "key_id": self.key_id,
            "name": self.name,
            "scopes": sorted(s.value for s in self.scopes),
            "created_at": datetime.fromtimestamp(
                self.created_at, tz=timezone.utc
            ).isoformat(),
            "expires_at": (
                datetime.fromtimestamp(self.expires_at, tz=timezone.utc).isoformat()
                if self.expires_at
                else None
            ),
            "last_used": (
                datetime.fromtimestamp(self.last_used, tz=timezone.utc).isoformat()
                if self.last_used
                else None
            ),
            "revoked": self.revoked,
            "ip_whitelist": self.ip_whitelist,
            "rate_limit_rpm": self.rate_limit_rpm,
        }


def _hash_key(raw_key: str) -> str:
    """Hash a raw API key using SHA-256.

    Args:
        raw_key: The plaintext API key.

    Returns:
        Hex-encoded SHA-256 hash.
    """
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _generate_raw_key() -> str:
    """Generate a new raw API key.

    Returns:
        A prefixed, URL-safe API key string.
    """
    return f"{_KEY_PREFIX}{secrets.token_urlsafe(_KEY_BYTES)}"


class APIKeyManager:
    """Manages API key lifecycle: creation, validation, rotation, and revocation.

    Keys are stored as SHA-256 hashes. The plaintext key is only returned
    once at creation time and during rotation.
    """

    def __init__(self) -> None:
        # key_hash -> APIKey
        self._keys_by_hash: dict[str, APIKey] = {}
        # key_id -> APIKey
        self._keys_by_id: dict[str, APIKey] = {}
        # user_id -> list of key_ids
        self._user_keys: dict[str, list[str]] = {}
        self._lock = threading.Lock()

    def create_key(
        self,
        user_id: str,
        name: str,
        scopes: set[APIKeyScope] | None = None,
        expires_days: int = _DEFAULT_EXPIRY_DAYS,
        ip_whitelist: list[str] | None = None,
        rate_limit_rpm: int = 60,
    ) -> tuple[str, APIKey]:
        """Create a new API key.

        Args:
            user_id: Owner user ID.
            name: Human-readable key name.
            scopes: Set of scopes for this key.
            expires_days: Days until expiration (0 for no expiry).
            ip_whitelist: Optional list of allowed IP addresses.
            rate_limit_rpm: Per-key rate limit (requests per minute).

        Returns:
            Tuple of (raw_key, api_key_metadata). The raw_key is only
            returned here — it cannot be recovered later.
        """
        raw_key = _generate_raw_key()
        key_hash = _hash_key(raw_key)
        key_id = secrets.token_hex(8)

        now = time.time()
        expires_at = now + (expires_days * 86400) if expires_days > 0 else None

        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            user_id=user_id,
            name=name,
            scopes=scopes or {APIKeyScope.READ},
            created_at=now,
            expires_at=expires_at,
            ip_whitelist=ip_whitelist or [],
            rate_limit_rpm=rate_limit_rpm,
        )

        with self._lock:
            self._keys_by_hash[key_hash] = api_key
            self._keys_by_id[key_id] = api_key
            if user_id not in self._user_keys:
                self._user_keys[user_id] = []
            self._user_keys[user_id].append(key_id)

        logger.info("API key '%s' created for user %s (id: %s)", name, user_id, key_id)
        return raw_key, api_key

    def validate_key(
        self,
        raw_key: str,
        required_scope: APIKeyScope | None = None,
        source_ip: str = "",
    ) -> Optional[APIKey]:
        """Validate an API key and check scope/IP restrictions.

        Args:
            raw_key: The plaintext API key.
            required_scope: Scope required for this request.
            source_ip: Client IP for whitelist check.

        Returns:
            APIKey metadata if valid, None otherwise.
        """
        key_hash = _hash_key(raw_key)

        with self._lock:
            api_key = self._keys_by_hash.get(key_hash)

            # Check previous key during rotation grace period
            if not api_key:
                for k in self._keys_by_id.values():
                    if (
                        k.previous_key_hash == key_hash
                        and k.previous_key_expires
                        and time.time() < k.previous_key_expires
                    ):
                        api_key = k
                        break

            if not api_key:
                return None

            if not api_key.is_valid:
                return None

            # Check scope
            if required_scope and not api_key.has_scope(required_scope):
                logger.warning(
                    "API key %s lacks scope %s", api_key.key_id, required_scope.value
                )
                return None

            # Check IP whitelist
            if api_key.ip_whitelist and source_ip:
                if source_ip not in api_key.ip_whitelist:
                    logger.warning(
                        "API key %s used from non-whitelisted IP %s",
                        api_key.key_id,
                        source_ip,
                    )
                    return None

            # Update last used
            api_key.last_used = time.time()

        return api_key

    def rotate_key(self, key_id: str) -> tuple[str, APIKey] | None:
        """Rotate an API key, generating a new key while keeping the old one valid temporarily.

        Args:
            key_id: ID of the key to rotate.

        Returns:
            Tuple of (new_raw_key, api_key) or None if key not found.
        """
        with self._lock:
            api_key = self._keys_by_id.get(key_id)
            if not api_key or api_key.revoked:
                return None

            # Store old hash with grace period
            old_hash = api_key.key_hash
            api_key.previous_key_hash = old_hash
            api_key.previous_key_expires = time.time() + _ROTATION_GRACE_PERIOD

            # Generate new key
            new_raw = _generate_raw_key()
            new_hash = _hash_key(new_raw)

            # Update hash mappings
            del self._keys_by_hash[old_hash]
            self._keys_by_hash[new_hash] = api_key
            api_key.key_hash = new_hash

        logger.info(
            "API key %s rotated (grace period: %ds)", key_id, _ROTATION_GRACE_PERIOD
        )
        return new_raw, api_key

    def revoke_key(self, key_id: str) -> bool:
        """Revoke an API key.

        Args:
            key_id: ID of the key to revoke.

        Returns:
            True if key was revoked.
        """
        with self._lock:
            api_key = self._keys_by_id.get(key_id)
            if not api_key:
                return False

            api_key.revoked = True
            api_key.revoked_at = time.time()
            self._keys_by_hash.pop(api_key.key_hash, None)

        logger.info("API key %s revoked", key_id)
        return True

    def list_keys(self, user_id: str) -> list[dict]:
        """List all API keys for a user.

        Args:
            user_id: User identifier.

        Returns:
            List of key metadata dictionaries.
        """
        with self._lock:
            key_ids = self._user_keys.get(user_id, [])
            keys = []
            for kid in key_ids:
                api_key = self._keys_by_id.get(kid)
                if api_key:
                    keys.append(api_key.to_dict())
            return keys

    def get_key_info(self, key_id: str) -> dict | None:
        """Get metadata for a specific key.

        Args:
            key_id: Key identifier.

        Returns:
            Key metadata or None.
        """
        with self._lock:
            api_key = self._keys_by_id.get(key_id)
            return api_key.to_dict() if api_key else None


# Global instance
_manager: APIKeyManager | None = None


def get_api_key_manager() -> APIKeyManager:
    """Get or create the global API key manager."""
    global _manager
    if _manager is None:
        _manager = APIKeyManager()
    return _manager
