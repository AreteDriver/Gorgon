"""Session management with device tracking.

Provides session lifecycle management including:
- Session creation with device/platform metadata
- Concurrent session limits
- Session revocation (single or all)
- Activity tracking and idle timeout
- Device fingerprinting for multi-device awareness
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_SESSION_ID_BYTES = 32
_DEFAULT_MAX_SESSIONS = 5
_DEFAULT_IDLE_TIMEOUT = 3600  # 1 hour
_DEFAULT_ABSOLUTE_TIMEOUT = 86400  # 24 hours


@dataclass
class DeviceInfo:
    """Information about the device that initiated a session."""

    user_agent: str = ""
    ip_address: str = ""
    platform: str = ""  # e.g., "web", "mobile", "cli", "api"
    device_type: str = ""  # e.g., "desktop", "tablet", "phone"
    os: str = ""
    browser: str = ""

    def fingerprint(self) -> str:
        """Generate a simple device fingerprint.

        Returns:
            String fingerprint combining platform and user agent prefix.
        """
        ua_prefix = self.user_agent[:50] if self.user_agent else "unknown"
        return f"{self.platform}:{self.device_type}:{ua_prefix}"


@dataclass
class Session:
    """An authenticated user session."""

    session_id: str
    user_id: str
    device: DeviceInfo
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    expires_at: float = 0.0
    is_active: bool = True
    metadata: dict = field(default_factory=dict)

    @property
    def created_at_iso(self) -> str:
        """ISO formatted creation time."""
        return datetime.fromtimestamp(self.created_at, tz=timezone.utc).isoformat()

    @property
    def last_activity_iso(self) -> str:
        """ISO formatted last activity time."""
        return datetime.fromtimestamp(self.last_activity, tz=timezone.utc).isoformat()

    def to_dict(self) -> dict:
        """Serialize session info (safe for API responses)."""
        return {
            "session_id": self.session_id[:8] + "...",  # Truncated for display
            "user_id": self.user_id,
            "device": {
                "platform": self.device.platform,
                "device_type": self.device.device_type,
                "os": self.device.os,
                "browser": self.device.browser,
                "ip_address": self.device.ip_address,
            },
            "created_at": self.created_at_iso,
            "last_activity": self.last_activity_iso,
            "is_active": self.is_active,
        }


class SessionManager:
    """Manages user sessions with device tracking and security controls.

    Thread-safe session management that enforces concurrent session limits,
    idle timeouts, and provides session visibility for users.
    """

    def __init__(
        self,
        max_sessions_per_user: int = _DEFAULT_MAX_SESSIONS,
        idle_timeout: float = _DEFAULT_IDLE_TIMEOUT,
        absolute_timeout: float = _DEFAULT_ABSOLUTE_TIMEOUT,
    ) -> None:
        """Initialize session manager.

        Args:
            max_sessions_per_user: Maximum concurrent sessions per user.
            idle_timeout: Seconds of inactivity before session expires.
            absolute_timeout: Maximum session duration regardless of activity.
        """
        self.max_sessions_per_user = max_sessions_per_user
        self.idle_timeout = idle_timeout
        self.absolute_timeout = absolute_timeout

        # session_id -> Session
        self._sessions: dict[str, Session] = {}
        # user_id -> set of session_ids
        self._user_sessions: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def create_session(
        self,
        user_id: str,
        device: DeviceInfo | None = None,
        metadata: dict | None = None,
    ) -> Session:
        """Create a new session for a user.

        If the user exceeds the maximum session limit, the oldest session
        is automatically revoked.

        Args:
            user_id: User identifier.
            device: Device information for the session.
            metadata: Additional session metadata.

        Returns:
            The newly created session.
        """
        session_id = secrets.token_urlsafe(_SESSION_ID_BYTES)
        now = time.time()

        session = Session(
            session_id=session_id,
            user_id=user_id,
            device=device or DeviceInfo(),
            created_at=now,
            last_activity=now,
            expires_at=now + self.absolute_timeout,
            metadata=metadata or {},
        )

        with self._lock:
            # Evict oldest session if at limit
            user_sids = self._user_sessions.get(user_id, set())
            if len(user_sids) >= self.max_sessions_per_user:
                self._evict_oldest_session(user_id)

            self._sessions[session_id] = session
            if user_id not in self._user_sessions:
                self._user_sessions[user_id] = set()
            self._user_sessions[user_id].add(session_id)

        logger.info(
            "Session created for user %s from %s (%s)",
            user_id,
            session.device.ip_address,
            session.device.platform,
        )
        return session

    def validate_session(self, session_id: str) -> Optional[Session]:
        """Validate and refresh a session.

        Checks that the session exists, is active, and has not timed out.
        Updates last_activity on success.

        Args:
            session_id: Session identifier.

        Returns:
            Active session, or None if invalid/expired.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or not session.is_active:
                return None

            now = time.time()

            # Check absolute timeout
            if now > session.expires_at:
                self._deactivate_session(session)
                logger.info(
                    "Session expired (absolute timeout) for user %s",
                    session.user_id,
                )
                return None

            # Check idle timeout
            if now - session.last_activity > self.idle_timeout:
                self._deactivate_session(session)
                logger.info(
                    "Session expired (idle timeout) for user %s",
                    session.user_id,
                )
                return None

            # Refresh activity
            session.last_activity = now
            return session

    def revoke_session(self, session_id: str) -> bool:
        """Revoke a specific session.

        Args:
            session_id: Session identifier.

        Returns:
            True if session was revoked.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False

            self._deactivate_session(session)
            logger.info("Session revoked for user %s", session.user_id)
            return True

    def revoke_all_sessions(self, user_id: str, except_session: str = "") -> int:
        """Revoke all sessions for a user.

        Args:
            user_id: User identifier.
            except_session: Session ID to keep active (current session).

        Returns:
            Number of sessions revoked.
        """
        revoked = 0
        with self._lock:
            session_ids = list(self._user_sessions.get(user_id, set()))
            for sid in session_ids:
                if sid == except_session:
                    continue
                session = self._sessions.get(sid)
                if session and session.is_active:
                    self._deactivate_session(session)
                    revoked += 1

        if revoked:
            logger.info("Revoked %d sessions for user %s", revoked, user_id)
        return revoked

    def get_user_sessions(self, user_id: str) -> list[dict]:
        """Get all active sessions for a user.

        Args:
            user_id: User identifier.

        Returns:
            List of session info dictionaries.
        """
        with self._lock:
            session_ids = self._user_sessions.get(user_id, set())
            sessions = []
            for sid in session_ids:
                session = self._sessions.get(sid)
                if session and session.is_active:
                    sessions.append(session.to_dict())
            return sorted(sessions, key=lambda s: s["created_at"], reverse=True)

    def get_active_session_count(self, user_id: str) -> int:
        """Get number of active sessions for a user.

        Args:
            user_id: User identifier.

        Returns:
            Count of active sessions.
        """
        with self._lock:
            session_ids = self._user_sessions.get(user_id, set())
            return sum(
                1
                for sid in session_ids
                if sid in self._sessions and self._sessions[sid].is_active
            )

    def cleanup_expired(self) -> int:
        """Remove expired sessions from memory.

        Returns:
            Number of sessions cleaned up.
        """
        cleaned = 0
        now = time.time()

        with self._lock:
            expired_ids = []
            for sid, session in self._sessions.items():
                if not session.is_active:
                    expired_ids.append(sid)
                elif now > session.expires_at:
                    session.is_active = False
                    expired_ids.append(sid)
                elif now - session.last_activity > self.idle_timeout:
                    session.is_active = False
                    expired_ids.append(sid)

            for sid in expired_ids:
                session = self._sessions.pop(sid, None)
                if session:
                    user_sids = self._user_sessions.get(session.user_id)
                    if user_sids:
                        user_sids.discard(sid)
                    cleaned += 1

        if cleaned:
            logger.debug("Cleaned up %d expired sessions", cleaned)
        return cleaned

    def _evict_oldest_session(self, user_id: str) -> None:
        """Evict the oldest session for a user (must be called under lock)."""
        session_ids = self._user_sessions.get(user_id, set())
        oldest_sid = None
        oldest_time = float("inf")

        for sid in session_ids:
            session = self._sessions.get(sid)
            if session and session.created_at < oldest_time:
                oldest_time = session.created_at
                oldest_sid = sid

        if oldest_sid:
            session = self._sessions.get(oldest_sid)
            if session:
                self._deactivate_session(session)
                logger.info(
                    "Evicted oldest session for user %s (max sessions reached)",
                    user_id,
                )

    def _deactivate_session(self, session: Session) -> None:
        """Deactivate a session (must be called under lock)."""
        session.is_active = False
        self._sessions.pop(session.session_id, None)
        user_sids = self._user_sessions.get(session.user_id)
        if user_sids:
            user_sids.discard(session.session_id)


# Global instance
_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Get or create the global session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
