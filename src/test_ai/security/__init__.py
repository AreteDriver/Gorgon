"""Security patterns for API protection.

Provides middleware and utilities for:
- Request size limits
- Brute force protection
- Rate limiting for sensitive endpoints
- Audit logging for compliance
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
]
