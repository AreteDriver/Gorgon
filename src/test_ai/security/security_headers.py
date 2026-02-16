"""Security headers middleware.

Adds standard security headers to all HTTP responses:
- Strict-Transport-Security (HSTS)
- Content-Security-Policy (CSP)
- X-Content-Type-Options
- X-Frame-Options
- X-XSS-Protection
- Referrer-Policy
- Permissions-Policy
- Cache-Control for sensitive endpoints
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Paths containing sensitive data that should not be cached
_SENSITIVE_PATH_PREFIXES = (
    "/v1/auth/",
    "/auth/",
    "/v1/settings/",
)


@dataclass
class SecurityHeadersConfig:
    """Configuration for security headers.

    Args:
        hsts_enabled: Enable HSTS header (set True in production behind TLS).
        hsts_max_age: HSTS max-age in seconds (default: 1 year).
        hsts_include_subdomains: Include subdomains in HSTS.
        hsts_preload: Add preload directive to HSTS.
        csp_policy: Content-Security-Policy value.
        frame_options: X-Frame-Options value.
        content_type_nosniff: Enable X-Content-Type-Options: nosniff.
        xss_protection: X-XSS-Protection value.
        referrer_policy: Referrer-Policy value.
        permissions_policy: Permissions-Policy value.
        cache_sensitive_endpoints: Add no-cache headers to auth endpoints.
        custom_headers: Additional custom headers to add.
    """

    hsts_enabled: bool = False
    hsts_max_age: int = 31_536_000  # 1 year
    hsts_include_subdomains: bool = True
    hsts_preload: bool = False
    csp_policy: str = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    frame_options: str = "DENY"
    content_type_nosniff: bool = True
    xss_protection: str = "1; mode=block"
    referrer_policy: str = "strict-origin-when-cross-origin"
    permissions_policy: str = "camera=(), microphone=(), geolocation=(), payment=()"
    cache_sensitive_endpoints: bool = True
    custom_headers: dict[str, str] = field(default_factory=dict)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to every response.

    Follows OWASP recommendations for HTTP security headers.
    """

    def __init__(self, app, config: SecurityHeadersConfig | None = None) -> None:
        """Initialize middleware.

        Args:
            app: ASGI application.
            config: Security headers configuration.
        """
        super().__init__(app)
        self.config = config or SecurityHeadersConfig()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        # HSTS (only when enabled, typically behind TLS termination)
        if self.config.hsts_enabled:
            hsts_value = f"max-age={self.config.hsts_max_age}"
            if self.config.hsts_include_subdomains:
                hsts_value += "; includeSubDomains"
            if self.config.hsts_preload:
                hsts_value += "; preload"
            response.headers["Strict-Transport-Security"] = hsts_value

        # Content-Security-Policy
        if self.config.csp_policy:
            response.headers["Content-Security-Policy"] = self.config.csp_policy

        # X-Content-Type-Options
        if self.config.content_type_nosniff:
            response.headers["X-Content-Type-Options"] = "nosniff"

        # X-Frame-Options
        if self.config.frame_options:
            response.headers["X-Frame-Options"] = self.config.frame_options

        # X-XSS-Protection
        if self.config.xss_protection:
            response.headers["X-XSS-Protection"] = self.config.xss_protection

        # Referrer-Policy
        if self.config.referrer_policy:
            response.headers["Referrer-Policy"] = self.config.referrer_policy

        # Permissions-Policy
        if self.config.permissions_policy:
            response.headers["Permissions-Policy"] = self.config.permissions_policy

        # Cache-Control for sensitive endpoints
        if self.config.cache_sensitive_endpoints:
            path = request.url.path
            if any(path.startswith(prefix) for prefix in _SENSITIVE_PATH_PREFIXES):
                response.headers["Cache-Control"] = (
                    "no-store, no-cache, must-revalidate, max-age=0"
                )
                response.headers["Pragma"] = "no-cache"

        # Custom headers
        for header_name, header_value in self.config.custom_headers.items():
            response.headers[header_name] = header_value

        return response
