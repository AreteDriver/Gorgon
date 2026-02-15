"""Agent Evaluation Framework.

Provides tools for systematically evaluating agent performance
across various dimensions like accuracy, relevance, safety, and helpfulness.
"""

from .base import (
    EvalCase,
    EvalResult,
    EvalMetric,
    EvalSuite,
    Evaluator,
)
from .metrics import (
    ExactMatchMetric,
    ContainsMetric,
    LLMJudgeMetric,
    CodeExecutionMetric,
    SimilarityMetric,
    FactualityMetric,
)
from .runner import EvalRunner
from .reporters import (
    ConsoleReporter,
    JSONReporter,
    HTMLReporter,
)
from .loader import SuiteLoader
from .store import EvalStore, get_eval_store, reset_eval_store

__all__ = [
    # Base classes
    "EvalCase",
    "EvalResult",
    "EvalMetric",
    "EvalSuite",
    "Evaluator",
    # Metrics
    "ExactMatchMetric",
    "ContainsMetric",
    "LLMJudgeMetric",
    "CodeExecutionMetric",
    "SimilarityMetric",
    "FactualityMetric",
    # Runner
    "EvalRunner",
    # Reporters
    "ConsoleReporter",
    "JSONReporter",
    "HTMLReporter",
    # Loader
    "SuiteLoader",
    # Store
    "EvalStore",
    "get_eval_store",
    "reset_eval_store",
]
