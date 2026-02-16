"""Feature flags for gradual rollouts and platform-specific behavior.

Supports:
- Boolean, percentage-based, and user-targeted flags
- Platform-specific flag overrides
- Environment-based defaults (dev/staging/prod)
- Runtime flag updates without restart
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FlagStatus(str, Enum):
    """Feature flag status."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    PERCENTAGE = "percentage"


@dataclass
class FeatureFlag:
    """A feature flag definition.

    Args:
        name: Unique flag identifier (e.g., ``new_dashboard``).
        description: Human-readable description of the feature.
        status: Flag status (enabled, disabled, or percentage-based).
        percentage: Rollout percentage (0-100) when status is ``percentage``.
        enabled_platforms: Platforms where this flag is enabled (empty = all).
        disabled_platforms: Platforms where this flag is disabled.
        enabled_users: Specific user IDs that always see this flag.
        disabled_users: Specific user IDs that never see this flag.
        metadata: Additional flag metadata.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    name: str
    description: str = ""
    status: FlagStatus = FlagStatus.DISABLED
    percentage: int = 0
    enabled_platforms: list[str] = field(default_factory=list)
    disabled_platforms: list[str] = field(default_factory=list)
    enabled_users: list[str] = field(default_factory=list)
    disabled_users: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "percentage": self.percentage,
            "enabled_platforms": self.enabled_platforms,
            "disabled_platforms": self.disabled_platforms,
            "enabled_users": self.enabled_users,
            "metadata": self.metadata,
        }


def _hash_percentage(flag_name: str, user_id: str) -> int:
    """Deterministic hash to decide if a user is in the rollout percentage.

    Returns a value 0-99 that is stable for the same (flag, user) pair.

    Args:
        flag_name: Feature flag name.
        user_id: User identifier.

    Returns:
        Integer 0-99.
    """
    combined = f"{flag_name}:{user_id}"
    digest = hashlib.sha256(combined.encode()).hexdigest()
    return int(digest[:8], 16) % 100


class FeatureFlagManager:
    """Manages feature flags with platform and user targeting.

    Thread-safe flag evaluation for concurrent API requests.
    """

    def __init__(self) -> None:
        self._flags: dict[str, FeatureFlag] = {}
        self._lock = threading.Lock()

    def register(self, flag: FeatureFlag) -> None:
        """Register a feature flag.

        Args:
            flag: Feature flag definition.
        """
        with self._lock:
            self._flags[flag.name] = flag
        logger.info("Feature flag registered: %s (%s)", flag.name, flag.status.value)

    def update(
        self,
        name: str,
        status: Optional[FlagStatus] = None,
        percentage: Optional[int] = None,
        enabled_platforms: Optional[list[str]] = None,
        disabled_platforms: Optional[list[str]] = None,
        enabled_users: Optional[list[str]] = None,
        disabled_users: Optional[list[str]] = None,
    ) -> bool:
        """Update a feature flag.

        Args:
            name: Flag name.
            status: New status.
            percentage: New rollout percentage.
            enabled_platforms: New platform allow list.
            disabled_platforms: New platform deny list.
            enabled_users: New user allow list.
            disabled_users: New user deny list.

        Returns:
            True if flag was updated.
        """
        with self._lock:
            flag = self._flags.get(name)
            if not flag:
                return False

            if status is not None:
                flag.status = status
            if percentage is not None:
                flag.percentage = max(0, min(100, percentage))
            if enabled_platforms is not None:
                flag.enabled_platforms = enabled_platforms
            if disabled_platforms is not None:
                flag.disabled_platforms = disabled_platforms
            if enabled_users is not None:
                flag.enabled_users = enabled_users
            if disabled_users is not None:
                flag.disabled_users = disabled_users

            flag.updated_at = time.time()

        logger.info("Feature flag updated: %s", name)
        return True

    def is_enabled(
        self,
        name: str,
        user_id: str = "",
        platform: str = "",
    ) -> bool:
        """Check if a feature flag is enabled for a given context.

        Evaluation order:
        1. User deny list (always wins)
        2. User allow list (always wins)
        3. Platform deny list
        4. Platform allow list (if specified, restricts to those platforms)
        5. Flag status (enabled/disabled/percentage)

        Args:
            name: Flag name.
            user_id: Current user identifier.
            platform: Current platform (e.g., "web", "mobile", "cli").

        Returns:
            True if the feature is enabled for this context.
        """
        with self._lock:
            flag = self._flags.get(name)
            if not flag:
                return False

            # User deny list (highest priority)
            if user_id and user_id in flag.disabled_users:
                return False

            # User allow list
            if user_id and user_id in flag.enabled_users:
                return True

            # Platform deny list
            if platform and platform in flag.disabled_platforms:
                return False

            # Platform allow list (if specified, only those platforms)
            if flag.enabled_platforms and platform:
                if platform not in flag.enabled_platforms:
                    return False

            # Status-based evaluation
            if flag.status == FlagStatus.ENABLED:
                return True
            elif flag.status == FlagStatus.DISABLED:
                return False
            elif flag.status == FlagStatus.PERCENTAGE:
                if not user_id:
                    return False
                return _hash_percentage(name, user_id) < flag.percentage

        return False

    def get_all_flags(
        self,
        user_id: str = "",
        platform: str = "",
    ) -> dict[str, bool]:
        """Evaluate all flags for a given context.

        Args:
            user_id: Current user identifier.
            platform: Current platform.

        Returns:
            Dictionary mapping flag names to their enabled status.
        """
        results = {}
        with self._lock:
            flag_names = list(self._flags.keys())

        for name in flag_names:
            results[name] = self.is_enabled(name, user_id, platform)

        return results

    def list_flags(self) -> list[dict]:
        """List all registered feature flags.

        Returns:
            List of flag definitions as dictionaries.
        """
        with self._lock:
            return [flag.to_dict() for flag in self._flags.values()]

    def delete(self, name: str) -> bool:
        """Delete a feature flag.

        Args:
            name: Flag name.

        Returns:
            True if flag was deleted.
        """
        with self._lock:
            if name in self._flags:
                del self._flags[name]
                logger.info("Feature flag deleted: %s", name)
                return True
            return False


# Global instance
_manager: FeatureFlagManager | None = None


def get_feature_flag_manager() -> FeatureFlagManager:
    """Get or create the global feature flag manager."""
    global _manager
    if _manager is None:
        _manager = FeatureFlagManager()
    return _manager
