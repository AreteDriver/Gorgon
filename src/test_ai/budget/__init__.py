"""Cost and Token Budget Management.

Track, allocate, and enforce token budgets across workflow executions.
"""

from .manager import BudgetManager, BudgetConfig, UsageRecord, BudgetStatus
from .strategies import (
    AllocationStrategy,
    EqualAllocation,
    PriorityAllocation,
    AdaptiveAllocation,
)
from .preflight import (
    PreflightValidator,
    ValidationResult,
    ValidationStatus,
    WorkflowEstimate,
    StepEstimate,
    validate_workflow_budget,
)
from .models import (
    Budget,
    BudgetCreate,
    BudgetUpdate,
    BudgetPeriod,
    BudgetSummary,
)
from .persistence import PersistentBudgetManager

# Singleton budget tracker instance (in-memory)
_budget_tracker: BudgetManager | None = None

# Singleton persistent budget manager (database-backed)
_persistent_budget_manager: PersistentBudgetManager | None = None


def get_budget_tracker(
    backend=None,
    session_id: str | None = None,
) -> BudgetManager:
    """Get the global budget tracker instance.

    Args:
        backend: Optional DatabaseBackend for persistence
        session_id: Session identifier (required if backend is provided)

    Returns:
        BudgetManager singleton instance
    """
    global _budget_tracker
    if _budget_tracker is None:
        _budget_tracker = BudgetManager(backend=backend, session_id=session_id)
    return _budget_tracker


def reset_budget_tracker() -> None:
    """Reset the global budget tracker singleton (for testing)."""
    global _budget_tracker
    _budget_tracker = None


__all__ = [
    # In-memory budget tracking
    "BudgetManager",
    "BudgetConfig",
    "BudgetStatus",
    "UsageRecord",
    "AllocationStrategy",
    "EqualAllocation",
    "PriorityAllocation",
    "AdaptiveAllocation",
    "PreflightValidator",
    "ValidationResult",
    "ValidationStatus",
    "WorkflowEstimate",
    "StepEstimate",
    "validate_workflow_budget",
    "get_budget_tracker",
    "reset_budget_tracker",
    # Persistent budget management
    "Budget",
    "BudgetCreate",
    "BudgetUpdate",
    "BudgetPeriod",
    "BudgetSummary",
    "PersistentBudgetManager",
]
