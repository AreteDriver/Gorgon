"""AI Agents for autonomous task orchestration.

This module provides intelligent agents that can analyze user requests,
delegate to specialized sub-agents, and synthesize results.
"""

from .supervisor import SupervisorAgent, AgentDelegation
from .provider_wrapper import AgentProvider, create_agent_provider
from .convergence import ConvergenceResult, DelegationConvergenceChecker, HAS_CONVERGENT
from .task_classifier import (
    ClassificationResult,
    TaskComplexity,
    classify_task,
    filter_delegations,
)

__all__ = [
    "SupervisorAgent",
    "AgentDelegation",
    "AgentProvider",
    "create_agent_provider",
    "ConvergenceResult",
    "DelegationConvergenceChecker",
    "HAS_CONVERGENT",
    "ClassificationResult",
    "TaskComplexity",
    "classify_task",
    "filter_delegations",
]
