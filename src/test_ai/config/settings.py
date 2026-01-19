"""Settings and configuration management."""

import logging
import secrets
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Insecure default values that should not be used in production
_INSECURE_SECRET_KEY = "change-me-in-production"
_INSECURE_DATABASE_URL = "sqlite:///gorgon-state.db"

# Minimum requirements for secure configuration
_MIN_SECRET_KEY_LENGTH = 32
_MIN_SECRET_KEY_ENTROPY_BITS = 128


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # API Keys
    openai_api_key: str = Field(..., description="OpenAI API key")
    github_token: Optional[str] = Field(
        None, description="GitHub personal access token"
    )
    notion_token: Optional[str] = Field(None, description="Notion integration token")
    gmail_credentials_path: Optional[str] = Field(
        None, description="Path to Gmail OAuth credentials"
    )

    # Claude/Anthropic Settings
    anthropic_api_key: Optional[str] = Field(
        None, description="Anthropic API key for Claude"
    )
    claude_cli_path: str = Field("claude", description="Path to Claude CLI executable")
    claude_mode: str = Field(
        "api", description="Claude invocation mode: 'api' or 'cli'"
    )

    # Application Settings
    app_name: str = Field("Gorgon", description="Application name")
    debug: bool = Field(False, description="Debug mode")
    production: bool = Field(
        False,
        description="Production mode - enables strict security validation",
    )
    require_secure_config: bool = Field(
        False,
        description="Require secure SECRET_KEY and DATABASE_URL even in dev mode",
    )
    log_level: str = Field("INFO", description="Logging level")
    log_format: str = Field("text", description="Log format: 'text' or 'json'")
    sanitize_logs: bool = Field(True, description="Sanitize sensitive data from logs")

    # Paths
    base_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent.parent
    )
    logs_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent / "logs"
    )
    prompts_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent / "prompts"
    )
    workflows_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent / "workflows"
    )
    schedules_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent / "schedules"
    )
    webhooks_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent / "webhooks"
    )
    jobs_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent / "jobs"
    )
    plugins_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent / "plugins" / "custom"
    )

    # Database
    database_url: str = Field(
        default=_INSECURE_DATABASE_URL,
        description="Database URL (sqlite:///path.db or postgresql://user:pass@host/db)",
    )

    # Auth
    secret_key: str = Field(
        default=_INSECURE_SECRET_KEY, description="Secret key for token generation"
    )
    access_token_expire_minutes: int = Field(
        60, description="Access token expiration in minutes"
    )
    # API credentials (comma-separated user:password_hash pairs)
    # Generate hash with: python -c "from hashlib import sha256; print(sha256(b'your_password').hexdigest())"
    api_credentials: Optional[str] = Field(
        None,
        description="API credentials as 'user1:hash1,user2:hash2'. Hash passwords with SHA-256.",
    )
    allow_demo_auth: bool = Field(
        True,
        description="Allow demo authentication (user: any, password: 'demo'). Disable in production.",
    )

    # Shell execution limits
    shell_timeout_seconds: int = Field(
        300,
        description="Maximum execution time for shell commands in seconds (default: 5 minutes)",
    )
    shell_max_output_bytes: int = Field(
        10 * 1024 * 1024,
        description="Maximum output size for shell commands in bytes (default: 10MB)",
    )
    shell_allowed_commands: Optional[str] = Field(
        None,
        description="Comma-separated list of allowed shell commands (empty = all allowed)",
    )

    @property
    def has_secure_secret_key(self) -> bool:
        """Check if secret key meets security requirements.

        Requirements:
        - Not the insecure default value
        - At least 32 characters long
        """
        if self.secret_key == _INSECURE_SECRET_KEY:
            return False
        if len(self.secret_key) < _MIN_SECRET_KEY_LENGTH:
            return False
        return True

    @property
    def has_secure_database(self) -> bool:
        """Check if database URL has been changed from insecure default."""
        return self.database_url != _INSECURE_DATABASE_URL

    @property
    def is_production_safe(self) -> bool:
        """Check if configuration is safe for production use."""
        return self.has_secure_secret_key and self.has_secure_database

    @staticmethod
    def generate_secret_key() -> str:
        """Generate a cryptographically secure secret key."""
        return secrets.token_urlsafe(48)  # 64 characters, 384 bits of entropy

    def get_credentials_map(self) -> dict[str, str]:
        """Parse API credentials into a username -> password_hash map."""
        if not self.api_credentials:
            return {}

        credentials = {}
        for pair in self.api_credentials.split(","):
            pair = pair.strip()
            if ":" in pair:
                username, password_hash = pair.split(":", 1)
                credentials[username.strip()] = password_hash.strip()
        return credentials

    def verify_credentials(self, username: str, password: str) -> bool:
        """Verify username and password against configured credentials.

        Args:
            username: The username to verify
            password: The plaintext password to verify

        Returns:
            True if credentials are valid, False otherwise
        """
        from hashlib import sha256

        # Check configured credentials first
        credentials = self.get_credentials_map()
        if username in credentials:
            password_hash = sha256(password.encode()).hexdigest()
            return secrets.compare_digest(credentials[username], password_hash)

        # Fall back to demo auth if allowed
        if self.allow_demo_auth and password == "demo":
            return True

        return False

    def model_post_init(self, __context) -> None:
        """Ensure directories exist and validate production config."""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self.schedules_dir.mkdir(parents=True, exist_ok=True)
        self.webhooks_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

        # Production mode validation
        self._validate_production_config()

    def _validate_production_config(self) -> None:
        """Validate configuration for production safety."""
        issues = []

        if not self.has_secure_secret_key:
            if self.secret_key == _INSECURE_SECRET_KEY:
                msg = (
                    "SECRET_KEY is using insecure default value. "
                    f"Set SECRET_KEY environment variable to a secure random string "
                    f"(minimum {_MIN_SECRET_KEY_LENGTH} characters). "
                    f'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
                )
            else:
                msg = (
                    f"SECRET_KEY is too short ({len(self.secret_key)} chars). "
                    f"Minimum length is {_MIN_SECRET_KEY_LENGTH} characters. "
                    f'Generate a secure key with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
                )
            issues.append(msg)

        if not self.has_secure_database:
            msg = (
                "DATABASE_URL is using default SQLite path. "
                "Set DATABASE_URL environment variable for production "
                "(e.g., postgresql://user:pass@host/db or sqlite:///absolute/path.db)."
            )
            issues.append(msg)

        if self.debug and self.production:
            msg = "DEBUG mode is enabled in production. Set DEBUG=false."
            issues.append(msg)

        if self.allow_demo_auth and self.production:
            msg = (
                "Demo authentication is enabled in production. "
                "Set ALLOW_DEMO_AUTH=false and configure API_CREDENTIALS."
            )
            issues.append(msg)

        # Determine if we should enforce or warn
        enforce_security = self.production or self.require_secure_config

        if issues:
            if enforce_security:
                # In production or when require_secure_config is set, raise error
                mode = "production" if self.production else "secure config"
                raise ValueError(
                    f"Insecure configuration not allowed ({mode} mode enabled):\n"
                    + "\n".join(f"  - {issue}" for issue in issues)
                )
            else:
                # In dev mode, warn loudly
                for issue in issues:
                    warnings.warn(f"Security: {issue}", stacklevel=3)
                    logger.warning("SECURITY WARNING: %s", issue)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
