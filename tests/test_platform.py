"""Tests for platform detection and feature flags."""

import sys

import pytest

sys.path.insert(0, "src")

from test_ai.platform.device_detection import (
    DevicePlatform,
    DeviceType,
    detect_platform,
)
from test_ai.platform.feature_flags import (
    FeatureFlag,
    FeatureFlagManager,
    FlagStatus,
    _hash_percentage,
)


# ============================================================================
# Device Detection Tests
# ============================================================================


class TestDetectPlatform:
    """Tests for platform detection from User-Agent."""

    def test_chrome_desktop(self):
        """Detects Chrome on desktop."""
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.130 Safari/537.36"
        info = detect_platform(ua)
        assert info.platform == DevicePlatform.WEB
        assert info.device_type == DeviceType.DESKTOP
        assert info.browser == "Chrome"
        assert info.os == "Windows"
        assert info.is_mobile is False

    def test_safari_iphone(self):
        """Detects Safari on iPhone."""
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
        info = detect_platform(ua)
        assert info.platform == DevicePlatform.MOBILE
        assert info.device_type == DeviceType.PHONE
        assert info.os == "iOS"
        assert info.is_mobile is True

    def test_ipad(self):
        """Detects iPad as tablet."""
        ua = "Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
        info = detect_platform(ua)
        assert info.platform == DevicePlatform.TABLET
        assert info.device_type == DeviceType.TABLET
        assert info.is_mobile is True

    def test_android_chrome(self):
        """Detects Chrome on Android."""
        ua = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.210 Mobile Safari/537.36"
        info = detect_platform(ua)
        assert info.platform == DevicePlatform.MOBILE
        assert info.os == "Android"
        assert info.is_mobile is True

    def test_firefox_linux(self):
        """Detects Firefox on Linux."""
        ua = "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"
        info = detect_platform(ua)
        assert info.platform == DevicePlatform.WEB
        assert info.browser == "Firefox"
        assert info.os == "Linux"

    def test_edge_browser(self):
        """Detects Edge browser."""
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.2210.121"
        info = detect_platform(ua)
        assert info.browser == "Edge"

    def test_bot_detection(self):
        """Detects bots."""
        ua = "Googlebot/2.1 (+http://www.google.com/bot.html)"
        info = detect_platform(ua)
        assert info.platform == DevicePlatform.BOT
        assert info.is_bot is True

    def test_curl_as_cli(self):
        """Detects curl as CLI."""
        ua = "curl/8.4.0"
        info = detect_platform(ua)
        assert info.platform == DevicePlatform.CLI

    def test_sdk_detection(self):
        """Detects Gorgon SDK."""
        ua = "gorgon-sdk/1.0 Python/3.12"
        info = detect_platform(ua)
        assert info.platform == DevicePlatform.SDK

    def test_empty_user_agent(self):
        """Empty UA treated as API client."""
        info = detect_platform("")
        assert info.platform == DevicePlatform.API

    def test_client_hints(self):
        """Uses client hints when available."""
        ua = "Mozilla/5.0"
        hints = {
            "sec-ch-ua-platform": '"macOS"',
            "sec-ch-ua-mobile": "?0",
        }
        info = detect_platform(ua, hints)
        assert info.os == "macOS"

    def test_mobile_client_hint(self):
        """Client hint for mobile is respected."""
        ua = "Mozilla/5.0"
        hints = {"sec-ch-ua-mobile": "?1"}
        info = detect_platform(ua, hints)
        assert info.is_mobile is True

    def test_macos_detection(self):
        """Detects macOS."""
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        info = detect_platform(ua)
        assert info.os == "macOS"

    def test_platform_info_serialization(self):
        """PlatformInfo serializes to dict."""
        info = detect_platform("Mozilla/5.0")
        data = info.to_dict()
        assert "platform" in data
        assert "device_type" in data
        assert "os" in data
        assert "is_mobile" in data
        assert "is_bot" in data

    def test_python_requests_as_bot(self):
        """python-requests user agent treated as bot."""
        ua = "python-requests/2.31.0"
        info = detect_platform(ua)
        assert info.is_bot is True


# ============================================================================
# Feature Flags Tests
# ============================================================================


class TestHashPercentage:
    """Tests for deterministic hash percentage."""

    def test_returns_valid_range(self):
        """Hash returns 0-99."""
        for i in range(100):
            result = _hash_percentage("flag", f"user{i}")
            assert 0 <= result <= 99

    def test_deterministic(self):
        """Same inputs produce same output."""
        assert _hash_percentage("flag", "alice") == _hash_percentage("flag", "alice")

    def test_different_users_vary(self):
        """Different users get different percentages (usually)."""
        values = {_hash_percentage("flag", f"user{i}") for i in range(50)}
        assert len(values) > 1  # Should have variety


class TestFeatureFlag:
    """Tests for FeatureFlag dataclass."""

    def test_default_disabled(self):
        """Flags default to disabled."""
        flag = FeatureFlag(name="test")
        assert flag.status == FlagStatus.DISABLED

    def test_to_dict(self):
        """Flag serializes correctly."""
        flag = FeatureFlag(
            name="dark_mode",
            description="Dark mode toggle",
            status=FlagStatus.ENABLED,
            enabled_platforms=["web", "mobile"],
        )
        data = flag.to_dict()
        assert data["name"] == "dark_mode"
        assert data["status"] == "enabled"
        assert "web" in data["enabled_platforms"]


class TestFeatureFlagManager:
    """Tests for FeatureFlagManager."""

    @pytest.fixture
    def manager(self):
        return FeatureFlagManager()

    def test_register_and_check(self, manager):
        """Registers a flag and checks it."""
        manager.register(FeatureFlag(name="dark_mode", status=FlagStatus.ENABLED))
        assert manager.is_enabled("dark_mode") is True

    def test_disabled_flag(self, manager):
        """Disabled flag returns False."""
        manager.register(FeatureFlag(name="beta", status=FlagStatus.DISABLED))
        assert manager.is_enabled("beta") is False

    def test_nonexistent_flag(self, manager):
        """Non-registered flag returns False."""
        assert manager.is_enabled("nonexistent") is False

    def test_percentage_rollout(self, manager):
        """Percentage rollout works deterministically."""
        manager.register(
            FeatureFlag(name="new_ui", status=FlagStatus.PERCENTAGE, percentage=50)
        )

        # Should be deterministic for same user
        result1 = manager.is_enabled("new_ui", user_id="alice")
        result2 = manager.is_enabled("new_ui", user_id="alice")
        assert result1 == result2

    def test_percentage_no_user(self, manager):
        """Percentage flag without user_id returns False."""
        manager.register(
            FeatureFlag(name="new_ui", status=FlagStatus.PERCENTAGE, percentage=50)
        )
        assert manager.is_enabled("new_ui") is False

    def test_user_allow_list(self, manager):
        """User allow list overrides status."""
        manager.register(
            FeatureFlag(
                name="beta",
                status=FlagStatus.DISABLED,
                enabled_users=["alice"],
            )
        )
        assert manager.is_enabled("beta", user_id="alice") is True
        assert manager.is_enabled("beta", user_id="bob") is False

    def test_user_deny_list(self, manager):
        """User deny list overrides everything."""
        manager.register(
            FeatureFlag(
                name="feature",
                status=FlagStatus.ENABLED,
                disabled_users=["alice"],
            )
        )
        assert manager.is_enabled("feature", user_id="alice") is False
        assert manager.is_enabled("feature", user_id="bob") is True

    def test_platform_allow_list(self, manager):
        """Platform allow list restricts access."""
        manager.register(
            FeatureFlag(
                name="mobile_only",
                status=FlagStatus.ENABLED,
                enabled_platforms=["mobile"],
            )
        )
        assert manager.is_enabled("mobile_only", platform="mobile") is True
        assert manager.is_enabled("mobile_only", platform="web") is False

    def test_platform_deny_list(self, manager):
        """Platform deny list blocks access."""
        manager.register(
            FeatureFlag(
                name="no_bots",
                status=FlagStatus.ENABLED,
                disabled_platforms=["bot"],
            )
        )
        assert manager.is_enabled("no_bots", platform="bot") is False
        assert manager.is_enabled("no_bots", platform="web") is True

    def test_update_flag(self, manager):
        """Updates a flag dynamically."""
        manager.register(FeatureFlag(name="test", status=FlagStatus.DISABLED))
        assert manager.is_enabled("test") is False

        manager.update("test", status=FlagStatus.ENABLED)
        assert manager.is_enabled("test") is True

    def test_update_percentage(self, manager):
        """Updates rollout percentage."""
        manager.register(
            FeatureFlag(name="test", status=FlagStatus.PERCENTAGE, percentage=0)
        )
        manager.update("test", percentage=100)
        assert manager.is_enabled("test", user_id="anyone") is True

    def test_update_nonexistent(self, manager):
        """Updating nonexistent flag returns False."""
        assert manager.update("fake", status=FlagStatus.ENABLED) is False

    def test_get_all_flags(self, manager):
        """Evaluates all flags for a context."""
        manager.register(FeatureFlag(name="a", status=FlagStatus.ENABLED))
        manager.register(FeatureFlag(name="b", status=FlagStatus.DISABLED))

        flags = manager.get_all_flags(user_id="alice", platform="web")
        assert flags["a"] is True
        assert flags["b"] is False

    def test_list_flags(self, manager):
        """Lists all registered flags."""
        manager.register(FeatureFlag(name="flag1"))
        manager.register(FeatureFlag(name="flag2"))

        flags = manager.list_flags()
        assert len(flags) == 2
        names = {f["name"] for f in flags}
        assert "flag1" in names
        assert "flag2" in names

    def test_delete_flag(self, manager):
        """Deletes a flag."""
        manager.register(FeatureFlag(name="temp", status=FlagStatus.ENABLED))
        assert manager.delete("temp") is True
        assert manager.is_enabled("temp") is False

    def test_delete_nonexistent(self, manager):
        """Deleting nonexistent flag returns False."""
        assert manager.delete("fake") is False

    def test_percentage_100(self, manager):
        """100% rollout enables for all users."""
        manager.register(
            FeatureFlag(name="full", status=FlagStatus.PERCENTAGE, percentage=100)
        )
        # Every user should get it
        for i in range(20):
            assert manager.is_enabled("full", user_id=f"user{i}") is True

    def test_percentage_0(self, manager):
        """0% rollout disables for all users."""
        manager.register(
            FeatureFlag(name="none", status=FlagStatus.PERCENTAGE, percentage=0)
        )
        for i in range(20):
            assert manager.is_enabled("none", user_id=f"user{i}") is False
