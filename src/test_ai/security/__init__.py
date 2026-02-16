"""Security patterns for API protection.

Provides middleware and utilities for:
- Request size limits
- Brute force protection
- Rate limiting for sensitive endpoints
- Audit logging for compliance
- Security headers (CSP, HSTS, etc.)
- Two-factor authentication (TOTP)
- Threat detection and monitoring
- Session management with device tracking
- API key management with scopes
- Password policy enforcement
"""

from test_ai.security.request_limits import (
    RequestLimitConfig,
    RequestSizeLimitMiddleware,
    RequestTooLarge,
    create_size_limit_middleware,
)
from test_ai.security.brute_force import (
    BruteForceBlocked,
    BruteForceConfig,
    BruteForceMiddleware,
    BruteForceProtection,
    get_brute_force_protection,
)
from test_ai.security.audit_log import AuditLogMiddleware
from test_ai.security.field_encryption import FieldEncryptor, get_field_encryptor
from test_ai.security.security_headers import (
    SecurityHeadersConfig,
    SecurityHeadersMiddleware,
)
from test_ai.security.totp import (
    TOTPManager,
    TOTPSetup,
    get_totp_manager,
)
from test_ai.security.threat_detection import (
    ThreatCategory,
    ThreatDetector,
    ThreatEvent,
    ThreatSeverity,
    get_threat_detector,
)
from test_ai.security.session_manager import (
    DeviceInfo,
    Session,
    SessionManager,
    get_session_manager,
)
from test_ai.security.api_key_manager import (
    APIKey,
    APIKeyManager,
    APIKeyScope,
    get_api_key_manager,
)
from test_ai.security.password_policy import (
    PasswordPolicyConfig,
    PasswordValidationResult,
    validate_password,
)

__all__ = [
    # Request limits
    "RequestLimitConfig",
    "RequestSizeLimitMiddleware",
    "RequestTooLarge",
    "create_size_limit_middleware",
    # Brute force
    "BruteForceBlocked",
    "BruteForceConfig",
    "BruteForceMiddleware",
    "BruteForceProtection",
    "get_brute_force_protection",
    # Audit logging
    "AuditLogMiddleware",
    # Field encryption
    "FieldEncryptor",
    "get_field_encryptor",
    # Security headers
    "SecurityHeadersConfig",
    "SecurityHeadersMiddleware",
    # TOTP / 2FA
    "TOTPManager",
    "TOTPSetup",
    "get_totp_manager",
    # Threat detection
    "ThreatCategory",
    "ThreatDetector",
    "ThreatEvent",
    "ThreatSeverity",
    "get_threat_detector",
    # Session management
    "DeviceInfo",
    "Session",
    "SessionManager",
    "get_session_manager",
    # API key management
    "APIKey",
    "APIKeyManager",
    "APIKeyScope",
    "get_api_key_manager",
    # Password policy
    "PasswordPolicyConfig",
    "PasswordValidationResult",
    "validate_password",
]
