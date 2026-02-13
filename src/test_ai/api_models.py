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
