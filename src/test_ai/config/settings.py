"""Settings and configuration management."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    log_level: str = Field("INFO", description="Logging level")
    log_format: str = Field(
        "text", description="Log format: 'text' or 'json'"
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

    # Database
    database_url: str = Field(
        default="sqlite:///gorgon-state.db",
        description="Database URL (sqlite:///path.db or postgresql://user:pass@host/db)",
    )

    # Auth
    secret_key: str = Field(
        default="change-me-in-production", description="Secret key for token generation"
    )
    access_token_expire_minutes: int = Field(
        60, description="Access token expiration in minutes"
    )

    def model_post_init(self, __context) -> None:
        """Ensure directories exist."""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self.schedules_dir.mkdir(parents=True, exist_ok=True)
        self.webhooks_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
