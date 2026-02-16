"""Platform compatibility and feature management.

Provides:
- Device and platform detection from HTTP requests
- Feature flags for gradual rollouts and platform-specific behavior
- Cross-platform response adaptation
"""

from test_ai.platform.device_detection import (
    DevicePlatform,
    PlatformInfo,
    detect_platform,
)
from test_ai.platform.feature_flags import (
    FeatureFlag,
    FeatureFlagManager,
    get_feature_flag_manager,
)

__all__ = [
    "DevicePlatform",
    "PlatformInfo",
    "detect_platform",
    "FeatureFlag",
    "FeatureFlagManager",
    "get_feature_flag_manager",
]
