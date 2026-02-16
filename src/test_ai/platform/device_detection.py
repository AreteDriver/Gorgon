"""Device and platform detection from HTTP requests.

Parses User-Agent headers and client hints to determine:
- Device type (desktop, tablet, phone, bot)
- Operating system
- Browser family
- Platform category (web, mobile, cli, api, sdk)

Used for platform-adaptive API responses and analytics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DevicePlatform(str, Enum):
    """High-level platform category."""

    WEB = "web"
    MOBILE = "mobile"
    TABLET = "tablet"
    DESKTOP = "desktop"
    CLI = "cli"
    API = "api"
    SDK = "sdk"
    BOT = "bot"
    UNKNOWN = "unknown"


class DeviceType(str, Enum):
    """Physical device type."""

    DESKTOP = "desktop"
    TABLET = "tablet"
    PHONE = "phone"
    BOT = "bot"
    UNKNOWN = "unknown"


@dataclass
class PlatformInfo:
    """Detected platform and device information."""

    platform: DevicePlatform
    device_type: DeviceType
    os: str
    os_version: str
    browser: str
    browser_version: str
    is_mobile: bool
    is_bot: bool
    raw_user_agent: str

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "platform": self.platform.value,
            "device_type": self.device_type.value,
            "os": self.os,
            "os_version": self.os_version,
            "browser": self.browser,
            "browser_version": self.browser_version,
            "is_mobile": self.is_mobile,
            "is_bot": self.is_bot,
        }


# OS detection patterns
_OS_PATTERNS = [
    (re.compile(r"Windows NT (\d+\.\d+)"), "Windows", None),
    (re.compile(r"Mac OS X (\d+[._]\d+[._]?\d*)"), "macOS", None),
    (re.compile(r"iPhone OS (\d+[._]\d+)"), "iOS", None),
    (re.compile(r"iPad.*OS (\d+[._]\d+)"), "iPadOS", None),
    (re.compile(r"Android (\d+\.?\d*)"), "Android", None),
    (re.compile(r"Linux"), "Linux", ""),
    (re.compile(r"CrOS"), "ChromeOS", ""),
]

# Browser detection patterns (order matters — check specific before generic)
_BROWSER_PATTERNS = [
    (re.compile(r"Edg/(\d+\.\d+)"), "Edge"),
    (re.compile(r"OPR/(\d+\.\d+)"), "Opera"),
    (re.compile(r"Vivaldi/(\d+\.\d+)"), "Vivaldi"),
    (re.compile(r"Firefox/(\d+\.\d+)"), "Firefox"),
    (re.compile(r"Chrome/(\d+\.\d+)"), "Chrome"),
    (re.compile(r"Safari/(\d+\.\d+)"), "Safari"),
    (re.compile(r"MSIE (\d+\.\d+)"), "IE"),
    (re.compile(r"Trident/.*rv:(\d+\.\d+)"), "IE"),
]

# Bot detection patterns
_BOT_PATTERNS = re.compile(
    r"(?i)(bot|crawl|spider|scrape|fetch|curl|wget|httpx|python-requests|"
    r"go-http-client|java/|axios|node-fetch|postman|insomnia|"
    r"googlebot|bingbot|slurp|duckduckbot|baiduspider|yandexbot)"
)

# Mobile indicators
_MOBILE_PATTERN = re.compile(
    r"(?i)(mobile|android|iphone|ipod|opera mini|opera mobi|windows phone)"
)
_TABLET_PATTERN = re.compile(r"(?i)(ipad|tablet|kindle|silk|playbook)")

# CLI/SDK indicators (custom user agents set by Gorgon clients)
_CLI_PATTERN = re.compile(r"(?i)(gorgon-cli|gorgon-sdk|curl|httpie|wget)")
_SDK_PATTERN = re.compile(r"(?i)(gorgon-sdk|gorgon-python|gorgon-node|gorgon-go)")


def detect_platform(
    user_agent: str,
    client_hints: Optional[dict[str, str]] = None,
) -> PlatformInfo:
    """Detect platform and device from User-Agent and optional client hints.

    Args:
        user_agent: User-Agent header string.
        client_hints: Optional Sec-CH-UA client hints headers.

    Returns:
        Detected platform information.
    """
    ua = user_agent or ""

    # Detect OS
    os_name = "Unknown"
    os_version = ""
    for pattern, name, default_ver in _OS_PATTERNS:
        match = pattern.search(ua)
        if match:
            os_name = name
            os_version = (
                match.group(1).replace("_", ".")
                if match.lastindex
                else (default_ver or "")
            )
            break

    # Use client hints if available
    if client_hints:
        if "sec-ch-ua-platform" in client_hints:
            hint_platform = client_hints["sec-ch-ua-platform"].strip('"')
            if hint_platform:
                os_name = hint_platform
        if "sec-ch-ua-platform-version" in client_hints:
            os_version = client_hints["sec-ch-ua-platform-version"].strip('"')

    # Detect browser
    browser = "Unknown"
    browser_version = ""
    for pattern, name in _BROWSER_PATTERNS:
        match = pattern.search(ua)
        if match:
            browser = name
            browser_version = match.group(1)
            break

    # Detect device type and platform
    is_bot = bool(_BOT_PATTERNS.search(ua))
    is_mobile = bool(_MOBILE_PATTERN.search(ua))
    is_tablet = bool(_TABLET_PATTERN.search(ua))
    is_cli = bool(_CLI_PATTERN.search(ua))
    is_sdk = bool(_SDK_PATTERN.search(ua))

    # Check client hints for mobile
    if client_hints and client_hints.get("sec-ch-ua-mobile") == "?1":
        is_mobile = True

    if is_sdk:
        device_type = DeviceType.UNKNOWN
        platform = DevicePlatform.SDK
    elif is_cli:
        device_type = DeviceType.UNKNOWN
        platform = DevicePlatform.CLI
    elif is_bot:
        device_type = DeviceType.BOT
        platform = DevicePlatform.BOT
    elif is_tablet:
        device_type = DeviceType.TABLET
        platform = DevicePlatform.TABLET
    elif is_mobile:
        device_type = DeviceType.PHONE
        platform = DevicePlatform.MOBILE
    elif browser != "Unknown":
        device_type = DeviceType.DESKTOP
        platform = DevicePlatform.WEB
    elif not ua:
        device_type = DeviceType.UNKNOWN
        platform = DevicePlatform.API
    else:
        device_type = DeviceType.UNKNOWN
        platform = DevicePlatform.UNKNOWN

    return PlatformInfo(
        platform=platform,
        device_type=device_type,
        os=os_name,
        os_version=os_version,
        browser=browser,
        browser_version=browser_version,
        is_mobile=is_mobile or is_tablet,
        is_bot=is_bot,
        raw_user_agent=ua,
    )
