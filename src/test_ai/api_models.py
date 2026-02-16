"""Pydantic request/response models for API endpoints."""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """Login request."""

    user_id: str = Field(..., max_length=128, pattern=r"^[\w@.\-]+$")
    password: str


class LoginResponse(BaseModel):
    """Login response."""

    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Workflow execution
# ---------------------------------------------------------------------------


class WorkflowExecuteRequest(BaseModel):
    """Request to execute a workflow."""

    workflow_id: str
    variables: Optional[Dict] = None


class ExecutionStartRequest(BaseModel):
    """Request to start a workflow execution."""

    variables: Optional[Dict] = None


class YAMLWorkflowExecuteRequest(BaseModel):
    """Request to execute a YAML workflow."""

    workflow_id: str = Field(..., pattern=r"^[\w\-]+$")
    inputs: Optional[Dict] = None


# ---------------------------------------------------------------------------
# Workflow versioning
# ---------------------------------------------------------------------------


class WorkflowVersionRequest(BaseModel):
    """Request to save a workflow version."""

    content: str
    version: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    activate: bool = True


class VersionCompareRequest(BaseModel):
    """Request to compare two versions."""

    from_version: str
    to_version: str


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class PreferencesUpdateRequest(BaseModel):
    """Request to update user preferences."""

    theme: Optional[str] = None
    compact_view: Optional[bool] = None
    show_costs: Optional[bool] = None
    default_page_size: Optional[int] = None
    notifications: Optional[Dict] = None


class APIKeyCreateRequest(BaseModel):
    """Request to create/update an API key."""

    provider: str
    key: str


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------


class BudgetCreateRequest(BaseModel):
    """Request to create a budget."""

    name: str
    total_amount: float
    period: str = "monthly"
    agent_id: Optional[str] = None


class BudgetUpdateRequest(BaseModel):
    """Request to update a budget."""

    name: Optional[str] = None
    total_amount: Optional[float] = None
    used_amount: Optional[float] = None
    period: Optional[str] = None
    agent_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class DashboardStats(BaseModel):
    """Dashboard statistics response."""

    totalWorkflows: int
    activeExecutions: int
    completedToday: int
    failedToday: int
    totalTokensToday: int
    totalCostToday: float


class RecentExecution(BaseModel):
    """Recent execution summary for dashboard."""

    id: str
    name: str
    status: str
    time: str


class DailyUsage(BaseModel):
    """Daily usage data point."""

    date: str
    tokens: int
    cost: float


class AgentUsage(BaseModel):
    """Per-agent usage data point."""

    agent: str
    tokens: int


class BudgetStatus(BaseModel):
    """Budget status for an agent."""

    agent: str
    used: float
    limit: float


class DashboardBudget(BaseModel):
    """Dashboard budget summary."""

    totalBudget: float
    totalUsed: float
    percentUsed: float
    byAgent: list[BudgetStatus]
    alert: Optional[str] = None


class AgentDefinitionResponse(BaseModel):
    """Response model for agent definition."""

    id: str
    name: str
    description: str
    capabilities: list[str]
    icon: str
    color: str


# ---------------------------------------------------------------------------
# Two-Factor Authentication
# ---------------------------------------------------------------------------


class TOTPSetupResponse(BaseModel):
    """Response after initiating 2FA setup."""

    secret: str
    provisioning_uri: str
    backup_codes: list[str]


class TOTPVerifyRequest(BaseModel):
    """Request to verify a TOTP code."""

    code: str = Field(..., min_length=6, max_length=8, pattern=r"^[0-9a-f]+$")


class TOTPStatusResponse(BaseModel):
    """2FA status for a user."""

    enabled: bool
    backup_codes_remaining: int


class LoginWithTOTPRequest(BaseModel):
    """Login request with optional 2FA code."""

    user_id: str = Field(..., max_length=128, pattern=r"^[\w@.\-]+$")
    password: str
    totp_code: Optional[str] = Field(
        None, min_length=6, max_length=8, description="TOTP code if 2FA is enabled"
    )


class LoginWithTOTPResponse(BaseModel):
    """Login response that may require 2FA."""

    access_token: Optional[str] = None
    token_type: str = "bearer"
    requires_2fa: bool = False
    session_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Session Management
# ---------------------------------------------------------------------------


class SessionInfoResponse(BaseModel):
    """Information about an active session."""

    session_id: str
    user_id: str
    device: Dict
    created_at: str
    last_activity: str
    is_active: bool


class SessionListResponse(BaseModel):
    """List of active sessions."""

    sessions: list[SessionInfoResponse]
    total: int


class RevokeSessionRequest(BaseModel):
    """Request to revoke a specific session."""

    session_id: str


# ---------------------------------------------------------------------------
# API Key Management
# ---------------------------------------------------------------------------


class APIKeyCreateFullRequest(BaseModel):
    """Request to create a new managed API key."""

    name: str = Field(..., max_length=100)
    scopes: list[str] = Field(default=["read"])
    expires_days: int = Field(default=90, ge=0, le=365)
    ip_whitelist: list[str] = Field(default=[])
    rate_limit_rpm: int = Field(default=60, ge=1, le=10000)


class APIKeyCreateResponse(BaseModel):
    """Response with the newly created API key (shown only once)."""

    raw_key: str
    key_id: str
    name: str
    scopes: list[str]
    expires_at: Optional[str] = None


class APIKeyRotateResponse(BaseModel):
    """Response after rotating an API key."""

    new_raw_key: str
    key_id: str
    grace_period_seconds: int


class APIKeyListResponse(BaseModel):
    """List of API keys for a user."""

    keys: list[Dict]


# ---------------------------------------------------------------------------
# Password Policy
# ---------------------------------------------------------------------------


class PasswordValidateRequest(BaseModel):
    """Request to validate password strength."""

    password: str
    username: Optional[str] = None


class PasswordValidateResponse(BaseModel):
    """Password validation result."""

    valid: bool
    errors: list[str]
    strength_score: float
    entropy_bits: float


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------


class FeatureFlagResponse(BaseModel):
    """Feature flag evaluation result."""

    flags: Dict[str, bool]


class FeatureFlagCreateRequest(BaseModel):
    """Request to create/update a feature flag."""

    name: str = Field(..., max_length=100, pattern=r"^[\w\-\.]+$")
    description: str = ""
    status: str = Field(default="disabled", pattern=r"^(enabled|disabled|percentage)$")
    percentage: int = Field(default=0, ge=0, le=100)
    enabled_platforms: list[str] = Field(default=[])
    disabled_platforms: list[str] = Field(default=[])
    enabled_users: list[str] = Field(default=[])
    disabled_users: list[str] = Field(default=[])


# ---------------------------------------------------------------------------
# Platform Detection
# ---------------------------------------------------------------------------


class PlatformInfoResponse(BaseModel):
    """Detected platform information."""

    platform: str
    device_type: str
    os: str
    os_version: str
    browser: str
    browser_version: str
    is_mobile: bool
    is_bot: bool


# ---------------------------------------------------------------------------
# Threat Detection
# ---------------------------------------------------------------------------


class ThreatEventsResponse(BaseModel):
    """Recent threat events."""

    events: list[Dict]
    total: int


class ThreatStatsResponse(BaseModel):
    """Threat detection statistics."""

    total_events: int
    tracked_ips: int
    by_category: Dict[str, int]
    by_severity: Dict[str, int]
