"""Intelligence layer — application-layer dominance for Gorgon.

Provides feedback loops, outcome tracking, cross-workflow learning,
and intelligent provider routing that make Gorgon's orchestration
irreplaceable.

Modules:
    outcome_tracker: Records whether agent outputs actually worked
    cross_workflow_memory: Persistent learning across workflow executions
    provider_router: Intelligent provider+model selection
    feedback_engine: Closes the loop between outcomes and future behavior
"""

from test_ai.intelligence.outcome_tracker import (
    OutcomeRecord,
    OutcomeTracker,
    ProviderStats,
)
from test_ai.intelligence.cross_workflow_memory import (
    AgentProfile,
    CrossWorkflowMemory,
    Pattern,
)
from test_ai.intelligence.provider_router import (
    ProviderCapability,
    ProviderRouter,
    ProviderSelection,
    RoutingStrategy,
)
from test_ai.intelligence.feedback_engine import (
    AgentTrajectory,
    FeedbackEngine,
    FeedbackResult,
    Suggestion,
    WorkflowFeedback,
)

__all__ = [
    # Outcome tracking
    "OutcomeRecord",
    "OutcomeTracker",
    "ProviderStats",
    # Cross-workflow memory
    "AgentProfile",
    "CrossWorkflowMemory",
    "Pattern",
    # Provider routing
    "ProviderCapability",
    "ProviderRouter",
    "ProviderSelection",
    "RoutingStrategy",
    # Feedback engine
    "AgentTrajectory",
    "FeedbackEngine",
    "FeedbackResult",
    "Suggestion",
    "WorkflowFeedback",
]
