"""Tests for security headers middleware."""

import sys

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

sys.path.insert(0, "src")

from test_ai.security.security_headers import (
    SecurityHeadersConfig,
    SecurityHeadersMiddleware,
)


class TestSecurityHeadersConfig:
    """Tests for SecurityHeadersConfig defaults."""

    def test_default_values(self):
        """Config has sensible defaults."""
        config = SecurityHeadersConfig()
        assert config.hsts_enabled is False
        assert config.content_type_nosniff is True
        assert config.frame_options == "DENY"
        assert config.referrer_policy == "strict-origin-when-cross-origin"

    def test_custom_values(self):
        """Config accepts custom values."""
        config = SecurityHeadersConfig(
            hsts_enabled=True,
            hsts_max_age=600,
            frame_options="SAMEORIGIN",
        )
        assert config.hsts_enabled is True
        assert config.hsts_max_age == 600
        assert config.frame_options == "SAMEORIGIN"


class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware."""

    @pytest.fixture
    def app_default(self):
        """App with default security headers."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        @app.get("/v1/auth/token")
        async def auth_endpoint():
            return {"token": "secret"}

        return app

    @pytest.fixture
    def app_hsts(self):
        """App with HSTS enabled."""
        config = SecurityHeadersConfig(
            hsts_enabled=True,
            hsts_max_age=86400,
            hsts_include_subdomains=True,
            hsts_preload=True,
        )
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, config=config)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        return app

    def test_x_content_type_options(self, app_default):
        """X-Content-Type-Options header is set."""
        client = TestClient(app_default)
        response = client.get("/test")
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options(self, app_default):
        """X-Frame-Options header is set."""
        client = TestClient(app_default)
        response = client.get("/test")
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_x_xss_protection(self, app_default):
        """X-XSS-Protection header is set."""
        client = TestClient(app_default)
        response = client.get("/test")
        assert response.headers["X-XSS-Protection"] == "1; mode=block"

    def test_referrer_policy(self, app_default):
        """Referrer-Policy header is set."""
        client = TestClient(app_default)
        response = client.get("/test")
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_csp_header(self, app_default):
        """Content-Security-Policy header is set."""
        client = TestClient(app_default)
        response = client.get("/test")
        assert "Content-Security-Policy" in response.headers
        assert "default-src 'self'" in response.headers["Content-Security-Policy"]

    def test_permissions_policy(self, app_default):
        """Permissions-Policy header is set."""
        client = TestClient(app_default)
        response = client.get("/test")
        assert "Permissions-Policy" in response.headers
        assert "camera=()" in response.headers["Permissions-Policy"]

    def test_no_hsts_by_default(self, app_default):
        """HSTS is not set when disabled."""
        client = TestClient(app_default)
        response = client.get("/test")
        assert "Strict-Transport-Security" not in response.headers

    def test_hsts_enabled(self, app_hsts):
        """HSTS header when enabled."""
        client = TestClient(app_hsts)
        response = client.get("/test")
        hsts = response.headers["Strict-Transport-Security"]
        assert "max-age=86400" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" in hsts

    def test_cache_control_on_auth_paths(self, app_default):
        """Sensitive endpoints get no-cache headers."""
        client = TestClient(app_default)
        response = client.get("/v1/auth/token")
        assert (
            response.headers.get("Cache-Control")
            == "no-store, no-cache, must-revalidate, max-age=0"
        )
        assert response.headers.get("Pragma") == "no-cache"

    def test_no_cache_control_on_normal_paths(self, app_default):
        """Normal endpoints don't get no-cache headers."""
        client = TestClient(app_default)
        response = client.get("/test")
        # Cache-Control may be absent or not set to no-store
        cache = response.headers.get("Cache-Control", "")
        assert "no-store" not in cache

    def test_custom_headers(self):
        """Custom headers are added."""
        config = SecurityHeadersConfig(custom_headers={"X-Custom": "test-value"})
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, config=config)

        @app.get("/test")
        async def test():
            return {}

        client = TestClient(app)
        response = client.get("/test")
        assert response.headers["X-Custom"] == "test-value"
