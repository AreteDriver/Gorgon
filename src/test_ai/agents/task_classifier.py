"""Lightweight task complexity classifier.

Classifies incoming tasks as simple/medium/complex to avoid
over-orchestrating with unnecessary agents. Uses heuristics
(no LLM call) to keep classification fast and free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class TaskComplexity(str, Enum):
    """Task complexity levels."""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


# Agent recommendations per complexity tier.
# Maps complexity to the max number of agents and which roles are allowed.
COMPLEXITY_TIERS: dict[TaskComplexity, dict] = {
    TaskComplexity.SIMPLE: {
        "max_agents": 1,
        "allowed_roles": {"builder", "reviewer", "documenter", "analyst"},
        "description": "Single-agent task: direct response or one delegation",
    },
    TaskComplexity.MEDIUM: {
        "max_agents": 3,
        "allowed_roles": {
            "planner",
            "builder",
            "tester",
            "reviewer",
            "documenter",
            "analyst",
        },
        "description": "Multi-agent task: 2-3 agents in sequence or parallel",
    },
    TaskComplexity.COMPLEX: {
        "max_agents": 7,
        "allowed_roles": {
            "planner",
            "builder",
            "tester",
            "reviewer",
            "architect",
            "documenter",
            "analyst",
        },
        "description": "Full pipeline: all agents available",
    },
}

# Patterns that suggest higher complexity
_COMPLEX_SIGNALS = [
    r"\b(architect|design|system\s+design|infrastructure)\b",
    r"\b(refactor|rewrite|migrate|overhaul)\b",
    r"\b(security\s+audit|threat\s+model|penetration)\b",
    r"\b(end.to.end|full.stack|across\s+(?:all|multiple)\s+(?:services|modules))\b",
    r"\b(scalab|distributed|microservice|event.driven)\b",
    r"\b(plan\s+and\s+implement|design\s+and\s+build)\b",
]

_MEDIUM_SIGNALS = [
    r"\b(add\s+feature|implement|create|build)\b",
    r"\b(test|write\s+tests|coverage)\b",
    r"\b(review|audit|check)\b",
    r"\b(document|api\s+docs|readme)\b",
    r"\b(fix\s+and\s+test|update\s+and\s+verify)\b",
    r"\b(multiple|several|few)\s+\w+",
]

_SIMPLE_SIGNALS = [
    r"\b(fix\s+(?:a\s+)?(?:typo|bug|error|issue))\b",
    r"\b(rename|move|delete|remove)\b",
    r"\b(explain|describe|what\s+is|how\s+does)\b",
    r"\b(update\s+(?:the\s+)?(?:version|dependency|config))\b",
    r"\b(add\s+(?:a\s+)?comment|add\s+(?:a\s+)?docstring)\b",
    r"\b(format|lint|style)\b",
]


@dataclass
class ClassificationResult:
    """Result of task complexity classification.

    Attributes:
        complexity: The assessed complexity level.
        confidence: How confident the classifier is (0.0-1.0).
        reasoning: Brief explanation of the classification.
        max_agents: Recommended maximum number of agents.
        allowed_roles: Set of agent roles appropriate for this complexity.
    """

    complexity: TaskComplexity
    confidence: float
    reasoning: str
    max_agents: int
    allowed_roles: set[str]


def classify_task(
    content: str,
    message_count: int = 0,
) -> ClassificationResult:
    """Classify a task's complexity using lightweight heuristics.

    No LLM call -- uses pattern matching and message structure to
    quickly determine whether a task needs 1 agent or the full pipeline.

    Args:
        content: The user's task/message text.
        message_count: Number of messages in conversation history.

    Returns:
        ClassificationResult with complexity and recommendations.
    """
    content_lower = content.lower()
    word_count = len(content.split())

    # Score each complexity level
    simple_score = 0.0
    medium_score = 0.0
    complex_score = 0.0

    # --- Signal matching ---
    for pattern in _SIMPLE_SIGNALS:
        if re.search(pattern, content_lower):
            simple_score += 1.0

    for pattern in _MEDIUM_SIGNALS:
        if re.search(pattern, content_lower):
            medium_score += 1.0

    for pattern in _COMPLEX_SIGNALS:
        if re.search(pattern, content_lower):
            complex_score += 1.5  # Complex signals weighted higher

    # --- Length heuristics ---
    if word_count < 15:
        simple_score += 1.0
    elif word_count < 50:
        medium_score += 0.5
    else:
        complex_score += 0.5

    # --- Structure heuristics ---
    # Bullet points or numbered lists suggest multi-part tasks
    list_items = len(re.findall(r"(?:^|\n)\s*[-*\d]+[.)]\s+", content))
    if list_items >= 4:
        complex_score += 1.0
    elif list_items >= 2:
        medium_score += 0.5

    # Multiple questions suggest broader scope
    question_count = content.count("?")
    if question_count >= 3:
        complex_score += 0.5
    elif question_count >= 2:
        medium_score += 0.5

    # Ongoing conversation context suggests accumulated complexity
    if message_count > 10:
        medium_score += 0.5

    # --- Determine winner ---
    scores = {
        TaskComplexity.SIMPLE: simple_score,
        TaskComplexity.MEDIUM: medium_score,
        TaskComplexity.COMPLEX: complex_score,
    }

    # Default to medium if nothing matched strongly
    max_score = max(scores.values())
    if max_score < 0.5:
        complexity = TaskComplexity.MEDIUM
        confidence = 0.3
        reasoning = "No strong signals detected, defaulting to medium"
    else:
        complexity = max(scores, key=scores.get)
        total = sum(scores.values()) or 1.0
        confidence = min(0.95, scores[complexity] / total)
        # Build reasoning from top signals
        matched = []
        if simple_score > 0:
            matched.append(f"simple={simple_score:.1f}")
        if medium_score > 0:
            matched.append(f"medium={medium_score:.1f}")
        if complex_score > 0:
            matched.append(f"complex={complex_score:.1f}")
        reasoning = f"Scores: {', '.join(matched)}. {word_count} words, {list_items} list items."

    tier = COMPLEXITY_TIERS[complexity]
    return ClassificationResult(
        complexity=complexity,
        confidence=confidence,
        reasoning=reasoning,
        max_agents=tier["max_agents"],
        allowed_roles=tier["allowed_roles"],
    )


def filter_delegations(
    delegations: list[dict],
    classification: ClassificationResult,
) -> list[dict]:
    """Filter a delegation list based on task complexity.

    Trims delegations to respect the complexity tier's agent limits
    and role restrictions. Preserves order (first delegations are
    assumed to be highest priority).

    Args:
        delegations: Original delegation list from the LLM.
        classification: Task complexity classification.

    Returns:
        Filtered delegation list.
    """
    if not delegations:
        return delegations

    filtered = []
    for d in delegations:
        role = d.get("agent", "").lower()
        if role in classification.allowed_roles:
            filtered.append(d)
        if len(filtered) >= classification.max_agents:
            break

    return filtered
