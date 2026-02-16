"""Tests for session management with device tracking."""

import sys
import time

import pytest

sys.path.insert(0, "src")

from test_ai.security.session_manager import (
    DeviceInfo,
    SessionManager,
)


class TestDeviceInfo:
    """Tests for DeviceInfo."""

    def test_default_values(self):
        """DeviceInfo has empty defaults."""
        device = DeviceInfo()
        assert device.user_agent == ""
        assert device.platform == ""

    def test_fingerprint(self):
        """Generates a consistent fingerprint."""
        device = DeviceInfo(
            user_agent="Mozilla/5.0",
            platform="web",
            device_type="desktop",
        )
        fp = device.fingerprint()
        assert "web" in fp
        assert "desktop" in fp

    def test_fingerprint_truncates_ua(self):
        """Fingerprint truncates long user agents."""
        device = DeviceInfo(user_agent="x" * 100, platform="web", device_type="desktop")
        fp = device.fingerprint()
        assert len(fp) < 100


class TestSessionManager:
    """Tests for SessionManager."""

    @pytest.fixture
    def manager(self):
        return SessionManager(
            max_sessions_per_user=3,
            idle_timeout=60,
            absolute_timeout=300,
        )

    def test_create_session(self, manager):
        """Creates a session with device info."""
        device = DeviceInfo(
            user_agent="Mozilla/5.0",
            ip_address="192.168.1.1",
            platform="web",
        )
        session = manager.create_session("alice", device)
        assert session.user_id == "alice"
        assert session.is_active is True
        assert session.device.platform == "web"

    def test_validate_active_session(self, manager):
        """Validates an active session."""
        session = manager.create_session("alice")
        result = manager.validate_session(session.session_id)
        assert result is not None
        assert result.user_id == "alice"

    def test_validate_nonexistent_session(self, manager):
        """Returns None for invalid session."""
        result = manager.validate_session("invalid-session-id")
        assert result is None

    def test_session_updates_last_activity(self, manager):
        """Validation updates last activity timestamp."""
        session = manager.create_session("alice")
        original_activity = session.last_activity

        time.sleep(0.01)
        manager.validate_session(session.session_id)
        assert session.last_activity > original_activity

    def test_idle_timeout(self, manager):
        """Session expires after idle timeout."""
        short_manager = SessionManager(idle_timeout=0.01, absolute_timeout=300)
        session = short_manager.create_session("alice")

        time.sleep(0.02)
        result = short_manager.validate_session(session.session_id)
        assert result is None

    def test_absolute_timeout(self, manager):
        """Session expires after absolute timeout."""
        short_manager = SessionManager(idle_timeout=300, absolute_timeout=0.01)
        session = short_manager.create_session("alice")

        time.sleep(0.02)
        result = short_manager.validate_session(session.session_id)
        assert result is None

    def test_revoke_session(self, manager):
        """Revokes a specific session."""
        session = manager.create_session("alice")
        assert manager.revoke_session(session.session_id) is True
        assert manager.validate_session(session.session_id) is None

    def test_revoke_nonexistent(self, manager):
        """Revoking nonexistent session returns False."""
        assert manager.revoke_session("fake-id") is False

    def test_revoke_all_sessions(self, manager):
        """Revokes all sessions for a user."""
        manager.create_session("alice")
        manager.create_session("alice")
        manager.create_session("alice")

        count = manager.revoke_all_sessions("alice")
        assert count == 3
        assert manager.get_active_session_count("alice") == 0

    def test_revoke_all_except_current(self, manager):
        """Revokes all sessions except one."""
        s1 = manager.create_session("alice")
        manager.create_session("alice")
        manager.create_session("alice")

        count = manager.revoke_all_sessions("alice", except_session=s1.session_id)
        assert count == 2
        assert manager.get_active_session_count("alice") == 1

    def test_max_sessions_eviction(self, manager):
        """Oldest session is evicted when limit is reached."""
        s1 = manager.create_session("alice")
        time.sleep(0.01)
        manager.create_session("alice")
        time.sleep(0.01)
        manager.create_session("alice")

        # At limit (3), creating 4th should evict oldest
        time.sleep(0.01)
        manager.create_session("alice")

        assert manager.get_active_session_count("alice") == 3
        assert manager.validate_session(s1.session_id) is None

    def test_get_user_sessions(self, manager):
        """Lists active sessions for a user."""
        manager.create_session("alice", DeviceInfo(platform="web"))
        manager.create_session("alice", DeviceInfo(platform="mobile"))

        sessions = manager.get_user_sessions("alice")
        assert len(sessions) == 2
        platforms = {s["device"]["platform"] for s in sessions}
        assert "web" in platforms
        assert "mobile" in platforms

    def test_session_count(self, manager):
        """Counts active sessions correctly."""
        manager.create_session("alice")
        manager.create_session("alice")
        assert manager.get_active_session_count("alice") == 2

    def test_cleanup_expired(self, manager):
        """Cleanup removes expired sessions."""
        short_manager = SessionManager(idle_timeout=0.01, absolute_timeout=0.01)
        short_manager.create_session("alice")
        short_manager.create_session("bob")

        time.sleep(0.02)
        cleaned = short_manager.cleanup_expired()
        assert cleaned == 2

    def test_session_to_dict(self, manager):
        """Session serializes correctly."""
        device = DeviceInfo(
            platform="web",
            device_type="desktop",
            os="Linux",
            browser="Chrome",
            ip_address="192.168.1.1",
        )
        session = manager.create_session("alice", device)
        data = session.to_dict()

        assert data["user_id"] == "alice"
        assert data["device"]["platform"] == "web"
        assert data["is_active"] is True
        assert "created_at" in data
        assert "last_activity" in data

    def test_different_users_independent(self, manager):
        """Sessions for different users are independent."""
        manager.create_session("alice")
        manager.create_session("bob")

        manager.revoke_all_sessions("alice")
        assert manager.get_active_session_count("alice") == 0
        assert manager.get_active_session_count("bob") == 1
