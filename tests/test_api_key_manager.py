"""Tests for API key management with scopes and rotation."""

import sys
import time

import pytest

sys.path.insert(0, "src")

from test_ai.security.api_key_manager import (
    APIKey,
    APIKeyManager,
    APIKeyScope,
)


class TestAPIKeyScope:
    """Tests for API key scopes."""

    def test_scope_values(self):
        """All scopes have string values."""
        assert APIKeyScope.READ.value == "read"
        assert APIKeyScope.WRITE.value == "write"
        assert APIKeyScope.ADMIN.value == "admin"

    def test_scope_hierarchy(self):
        """Admin scope includes all other scopes."""
        key = APIKey(
            key_id="test",
            key_hash="hash",
            user_id="alice",
            name="test",
            scopes={APIKeyScope.ADMIN},
        )
        assert key.has_scope(APIKeyScope.READ) is True
        assert key.has_scope(APIKeyScope.WRITE) is True
        assert key.has_scope(APIKeyScope.EXECUTE) is True

    def test_write_includes_read(self):
        """Write scope includes read."""
        key = APIKey(
            key_id="test",
            key_hash="hash",
            user_id="alice",
            name="test",
            scopes={APIKeyScope.WRITE},
        )
        assert key.has_scope(APIKeyScope.READ) is True
        assert key.has_scope(APIKeyScope.ADMIN) is False

    def test_read_only(self):
        """Read scope does not include write."""
        key = APIKey(
            key_id="test",
            key_hash="hash",
            user_id="alice",
            name="test",
            scopes={APIKeyScope.READ},
        )
        assert key.has_scope(APIKeyScope.READ) is True
        assert key.has_scope(APIKeyScope.WRITE) is False
        assert key.has_scope(APIKeyScope.ADMIN) is False


class TestAPIKeyManager:
    """Tests for APIKeyManager."""

    @pytest.fixture
    def manager(self):
        return APIKeyManager()

    def test_create_key(self, manager):
        """Creates a key and returns raw key."""
        raw_key, api_key = manager.create_key(
            user_id="alice",
            name="test-key",
            scopes={APIKeyScope.READ, APIKeyScope.WRITE},
        )

        assert raw_key.startswith("gorgon_")
        assert api_key.name == "test-key"
        assert api_key.user_id == "alice"
        assert APIKeyScope.READ in api_key.scopes

    def test_validate_key(self, manager):
        """Validates a correct API key."""
        raw_key, api_key = manager.create_key(
            user_id="alice",
            name="test-key",
        )

        result = manager.validate_key(raw_key)
        assert result is not None
        assert result.key_id == api_key.key_id

    def test_validate_invalid_key(self, manager):
        """Rejects an invalid key."""
        result = manager.validate_key("gorgon_invalid_key")
        assert result is None

    def test_validate_with_scope(self, manager):
        """Validates key with scope check."""
        raw_key, _ = manager.create_key(
            user_id="alice",
            name="read-only",
            scopes={APIKeyScope.READ},
        )

        # Read scope should pass
        assert (
            manager.validate_key(raw_key, required_scope=APIKeyScope.READ) is not None
        )

        # Write scope should fail
        assert manager.validate_key(raw_key, required_scope=APIKeyScope.WRITE) is None

    def test_validate_with_ip_whitelist(self, manager):
        """Validates key with IP whitelist check."""
        raw_key, _ = manager.create_key(
            user_id="alice",
            name="restricted",
            ip_whitelist=["192.168.1.1"],
        )

        # Allowed IP
        assert manager.validate_key(raw_key, source_ip="192.168.1.1") is not None

        # Blocked IP
        assert manager.validate_key(raw_key, source_ip="10.0.0.1") is None

    def test_revoke_key(self, manager):
        """Revokes a key."""
        raw_key, api_key = manager.create_key(
            user_id="alice",
            name="to-revoke",
        )

        assert manager.revoke_key(api_key.key_id) is True
        assert manager.validate_key(raw_key) is None

    def test_revoke_nonexistent(self, manager):
        """Revoking nonexistent key returns False."""
        assert manager.revoke_key("nonexistent") is False

    def test_rotate_key(self, manager):
        """Rotates a key, generating new key."""
        raw_key, api_key = manager.create_key(
            user_id="alice",
            name="to-rotate",
        )

        result = manager.rotate_key(api_key.key_id)
        assert result is not None

        new_raw, _ = result
        assert new_raw != raw_key
        assert new_raw.startswith("gorgon_")

        # New key works
        assert manager.validate_key(new_raw) is not None

    def test_rotate_keeps_old_key_during_grace(self, manager):
        """Old key remains valid during grace period after rotation."""
        raw_key, api_key = manager.create_key(
            user_id="alice",
            name="grace-test",
        )

        manager.rotate_key(api_key.key_id)

        # Old key should still work during grace period
        assert manager.validate_key(raw_key) is not None

    def test_list_keys(self, manager):
        """Lists all keys for a user."""
        manager.create_key(user_id="alice", name="key1")
        manager.create_key(user_id="alice", name="key2")
        manager.create_key(user_id="bob", name="key3")

        alice_keys = manager.list_keys("alice")
        assert len(alice_keys) == 2

        bob_keys = manager.list_keys("bob")
        assert len(bob_keys) == 1

    def test_get_key_info(self, manager):
        """Gets metadata for a specific key."""
        _, api_key = manager.create_key(
            user_id="alice",
            name="info-test",
        )

        info = manager.get_key_info(api_key.key_id)
        assert info is not None
        assert info["name"] == "info-test"
        assert "key_hash" not in info  # Should not expose hash

    def test_key_expiry(self, manager):
        """Expired keys are rejected."""
        raw_key, api_key = manager.create_key(
            user_id="alice",
            name="expiring",
            expires_days=0,  # No expiry
        )

        # Manually set expiry to the past
        api_key.expires_at = time.time() - 1

        assert manager.validate_key(raw_key) is None

    def test_key_updates_last_used(self, manager):
        """Validation updates last_used timestamp."""
        raw_key, api_key = manager.create_key(
            user_id="alice",
            name="usage-test",
        )
        assert api_key.last_used is None

        manager.validate_key(raw_key)
        assert api_key.last_used is not None

    def test_key_to_dict(self, manager):
        """Key serialization excludes sensitive data."""
        _, api_key = manager.create_key(
            user_id="alice",
            name="serial-test",
            scopes={APIKeyScope.READ},
        )

        data = api_key.to_dict()
        assert "key_hash" not in data
        assert data["name"] == "serial-test"
        assert "read" in data["scopes"]
        assert data["revoked"] is False
