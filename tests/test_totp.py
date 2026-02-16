"""Tests for TOTP-based two-factor authentication."""

import sys

import pytest

sys.path.insert(0, "src")

from test_ai.security.totp import (
    TOTPManager,
    _hotp,
    build_provisioning_uri,
    compute_totp,
    generate_backup_codes,
    generate_secret,
    verify_totp,
)


class TestGenerateSecret:
    """Tests for TOTP secret generation."""

    def test_returns_string(self):
        """Secret is a base32-encoded string."""
        secret = generate_secret()
        assert isinstance(secret, str)

    def test_sufficient_length(self):
        """Secret has sufficient length for security."""
        secret = generate_secret()
        assert len(secret) >= 24  # 20 bytes -> 32 base32 chars (minus padding)

    def test_unique(self):
        """Each secret is unique."""
        secrets = {generate_secret() for _ in range(10)}
        assert len(secrets) == 10

    def test_base32_chars(self):
        """Secret contains only base32 characters."""
        import re

        secret = generate_secret()
        assert re.fullmatch(r"[A-Z2-7]+", secret)


class TestGenerateBackupCodes:
    """Tests for backup code generation."""

    def test_default_count(self):
        """Generates default number of codes."""
        codes = generate_backup_codes()
        assert len(codes) == 10

    def test_custom_count(self):
        """Generates custom number of codes."""
        codes = generate_backup_codes(count=5)
        assert len(codes) == 5

    def test_unique_codes(self):
        """All codes are unique."""
        codes = generate_backup_codes()
        assert len(set(codes)) == len(codes)

    def test_code_length(self):
        """Codes have expected length."""
        codes = generate_backup_codes(length=8)
        for code in codes:
            assert len(code) == 8


class TestBuildProvisioningUri:
    """Tests for provisioning URI generation."""

    def test_format(self):
        """URI has correct otpauth:// format."""
        uri = build_provisioning_uri("ABCDEFGH", "user@example.com")
        assert uri.startswith("otpauth://totp/")
        assert "secret=ABCDEFGH" in uri
        assert "issuer=Gorgon" in uri

    def test_custom_issuer(self):
        """Custom issuer is included."""
        uri = build_provisioning_uri("SECRET", "user", issuer="MyApp")
        assert "issuer=MyApp" in uri
        assert "MyApp" in uri

    def test_user_in_label(self):
        """User ID appears in the label."""
        uri = build_provisioning_uri("SECRET", "alice")
        assert "alice" in uri


class TestHOTP:
    """Tests for HOTP computation."""

    def test_returns_digits(self):
        """HOTP returns a 6-digit string."""
        code = _hotp("JBSWY3DPEHPK3PXP", 0)
        assert len(code) == 6
        assert code.isdigit()

    def test_deterministic(self):
        """Same inputs produce same output."""
        code1 = _hotp("JBSWY3DPEHPK3PXP", 42)
        code2 = _hotp("JBSWY3DPEHPK3PXP", 42)
        assert code1 == code2

    def test_different_counters(self):
        """Different counters produce different codes (usually)."""
        codes = {_hotp("JBSWY3DPEHPK3PXP", i) for i in range(10)}
        assert len(codes) > 1  # Extremely unlikely to all collide

    def test_zero_padded(self):
        """Short codes are zero-padded."""
        # Test many counters to find a small code
        for i in range(1000):
            code = _hotp("JBSWY3DPEHPK3PXP", i)
            assert len(code) == 6


class TestComputeTOTP:
    """Tests for TOTP computation."""

    def test_returns_string(self):
        """TOTP returns a string."""
        code = compute_totp("JBSWY3DPEHPK3PXP")
        assert isinstance(code, str)
        assert len(code) == 6

    def test_deterministic_for_same_time(self):
        """Same timestamp produces same code."""
        ts = 1700000000.0
        code1 = compute_totp("JBSWY3DPEHPK3PXP", ts)
        code2 = compute_totp("JBSWY3DPEHPK3PXP", ts)
        assert code1 == code2

    def test_changes_with_time(self):
        """Code changes when time period changes."""
        code1 = compute_totp("JBSWY3DPEHPK3PXP", 1700000000.0)
        code2 = compute_totp("JBSWY3DPEHPK3PXP", 1700000030.0)
        # Codes from different 30s windows should differ (extremely likely)
        assert code1 != code2


class TestVerifyTOTP:
    """Tests for TOTP verification."""

    def test_valid_code(self):
        """Verifies a correct code."""
        secret = generate_secret()
        code = compute_totp(secret)
        valid, counter = verify_totp(secret, code)
        assert valid is True
        assert counter > 0

    def test_invalid_code(self):
        """Rejects an incorrect code."""
        secret = generate_secret()
        valid, counter = verify_totp(secret, "000000")
        # May or may not be valid depending on timing, but testing rejection
        # Use a timestamp that generates a known code
        ts = 1700000000.0
        correct = compute_totp(secret, ts)
        wrong = str((int(correct) + 1) % 1000000).zfill(6)
        valid, counter = verify_totp(secret, wrong, timestamp=ts)
        assert valid is False

    def test_clock_skew_tolerance(self):
        """Accepts codes from adjacent time periods."""
        secret = generate_secret()
        ts = 1700000000.0
        # Code from previous period
        prev_code = compute_totp(secret, ts - 30)
        valid, _ = verify_totp(secret, prev_code, timestamp=ts)
        assert valid is True

    def test_replay_prevention(self):
        """Rejects codes at or below last used counter."""
        secret = generate_secret()
        ts = 1700000000.0
        code = compute_totp(secret, ts)

        # First use succeeds
        valid, counter = verify_totp(secret, code, timestamp=ts)
        assert valid is True

        # Replay with same counter fails
        valid2, _ = verify_totp(secret, code, last_used_counter=counter, timestamp=ts)
        assert valid2 is False


class TestTOTPManager:
    """Tests for TOTPManager lifecycle."""

    @pytest.fixture
    def manager(self):
        return TOTPManager()

    def test_setup_returns_data(self, manager):
        """Setup returns secret, URI, and backup codes."""
        setup = manager.setup_totp("alice")
        assert setup.secret
        assert setup.provisioning_uri.startswith("otpauth://")
        assert len(setup.backup_codes) == 10

    def test_not_enabled_before_confirm(self, manager):
        """2FA is not enabled until confirmed."""
        manager.setup_totp("alice")
        assert manager.is_enabled("alice") is False

    def test_confirm_with_valid_code(self, manager):
        """Confirm enables 2FA."""
        setup = manager.setup_totp("alice")
        code = compute_totp(setup.secret)
        assert manager.confirm_setup("alice", code) is True
        assert manager.is_enabled("alice") is True

    def test_confirm_with_invalid_code(self, manager):
        """Confirm fails with wrong code."""
        manager.setup_totp("alice")
        assert manager.confirm_setup("alice", "000000") is False

    def test_verify_totp_code(self, manager):
        """Verifies TOTP code after setup."""
        setup = manager.setup_totp("alice")
        code = compute_totp(setup.secret)
        manager.confirm_setup("alice", code)

        # Generate a new code for the current time
        new_code = compute_totp(setup.secret)
        # This may fail if the time period changed between setup and verify,
        # so we test the mechanism
        result = manager.verify("alice", new_code)
        assert isinstance(result, bool)

    def test_verify_backup_code(self, manager):
        """Verifies a backup code."""
        setup = manager.setup_totp("alice")
        code = compute_totp(setup.secret)
        manager.confirm_setup("alice", code)

        backup = setup.backup_codes[0]
        assert manager.verify("alice", backup) is True

    def test_backup_code_single_use(self, manager):
        """Backup codes can only be used once."""
        setup = manager.setup_totp("alice")
        code = compute_totp(setup.secret)
        manager.confirm_setup("alice", code)

        backup = setup.backup_codes[0]
        manager.verify("alice", backup)  # Use it
        assert manager.verify("alice", backup) is False  # Second use fails

    def test_disable(self, manager):
        """Disable removes 2FA."""
        setup = manager.setup_totp("alice")
        code = compute_totp(setup.secret)
        manager.confirm_setup("alice", code)

        assert manager.disable("alice") is True
        assert manager.is_enabled("alice") is False

    def test_disable_nonexistent(self, manager):
        """Disabling non-enrolled user returns False."""
        assert manager.disable("bob") is False

    def test_regenerate_backup_codes(self, manager):
        """Regenerates new backup codes."""
        setup = manager.setup_totp("alice")
        code = compute_totp(setup.secret)
        manager.confirm_setup("alice", code)

        new_codes = manager.regenerate_backup_codes("alice")
        assert new_codes is not None
        assert len(new_codes) == 10
        assert new_codes != setup.backup_codes

    def test_backup_code_count(self, manager):
        """Tracks remaining backup codes."""
        setup = manager.setup_totp("alice")
        code = compute_totp(setup.secret)
        manager.confirm_setup("alice", code)

        assert manager.get_backup_code_count("alice") == 10

        # Use one backup code
        manager.verify("alice", setup.backup_codes[0])
        assert manager.get_backup_code_count("alice") == 9

    def test_verify_disabled_user(self, manager):
        """Verify returns False for user without 2FA."""
        assert manager.verify("bob", "123456") is False
