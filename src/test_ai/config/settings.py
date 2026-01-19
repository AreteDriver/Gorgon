"""Settings and configuration management."""

import logging
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
    log_level: str = Field("INFO", description="Logging level")
    log_format: str = Field(
        "text", description="Log format: 'text' or 'json'"
    )
    sanitize_logs: bool = Field(
        True, description="Sanitize sensitive data from logs"
    )

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

    @property
    def has_secure_secret_key(self) -> bool:
        """Check if secret key has been changed from insecure default."""
        return self.secret_key != _INSECURE_SECRET_KEY

    @property
    def has_secure_database(self) -> bool:
        """Check if database URL has been changed from insecure default."""
        return self.database_url != _INSECURE_DATABASE_URL

    @property
    def is_production_safe(self) -> bool:
        """Check if configuration is safe for production use."""
        return self.has_secure_secret_key and self.has_secure_database

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
            msg = (
                "SECRET_KEY is using insecure default value. "
                "Set SECRET_KEY environment variable to a secure random string."
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

        if issues:
            if self.production:
                # In production mode, raise error for insecure config
                raise ValueError(
                    "Production mode enabled with insecure configuration:\n"
                    + "\n".join(f"  - {issue}" for issue in issues)
                )
            else:
                # In dev mode, just warn
                for issue in issues:
                    warnings.warn(f"Security: {issue}", stacklevel=3)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
