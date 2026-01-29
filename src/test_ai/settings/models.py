"""User settings models."""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class NotificationSettings(BaseModel):
    """Notification preferences."""

    execution_complete: bool = True
    execution_failed: bool = True
    budget_alert: bool = True


class UserPreferences(BaseModel):
    """User preferences model."""

    user_id: str
    theme: Literal["light", "dark", "system"] = "system"
    compact_view: bool = False
    show_costs: bool = True
    default_page_size: int = Field(default=20, ge=10, le=100)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserPreferencesUpdate(BaseModel):
    """User preferences update request."""

    theme: Optional[Literal["light", "dark", "system"]] = None
    compact_view: Optional[bool] = None
    show_costs: Optional[bool] = None
    default_page_size: Optional[int] = Field(default=None, ge=10, le=100)
    notifications: Optional[NotificationSettings] = None


class APIKeyInfo(BaseModel):
    """API key metadata (no raw key exposed)."""

    id: int
    provider: str
    key_prefix: str  # e.g., "sk-...abc" - first few and last few chars
    created_at: datetime
    updated_at: datetime


class APIKeyCreate(BaseModel):
    """Request to create/update an API key."""

    provider: Literal["openai", "anthropic", "github"]
    key: str = Field(..., min_length=1)


class APIKeyStatus(BaseModel):
    """Status of configured API keys."""

    openai: bool = False
    anthropic: bool = False
    github: bool = False
