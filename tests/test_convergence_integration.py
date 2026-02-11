"""Tests for the Convergent ↔ Gorgon integration adapter."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from test_ai.agents.convergence import (
    ConvergenceResult,
    DelegationConvergenceChecker,
    HAS_CONVERGENT,
)


class TestConvergenceResult:
    """Test the ConvergenceResult dataclass."""

    def test_clean_result(self):
        result = ConvergenceResult()
        assert not result.has_conflicts
        assert result.adjustments == []
        assert result.conflicts == []
        assert result.dropped_agents == set()

    def test_result_with_conflicts(self):
        result = ConvergenceResult(
            conflicts=[{"agent": "builder", "description": "overlap with tester"}],
        )
        assert result.has_conflicts


class TestDelegationConvergenceChecker:
    """Test the adapter between Gorgon delegations and Convergent."""

    def test_disabled_without_resolver(self):
        checker = DelegationConvergenceChecker(resolver=None)
        assert not checker.enabled
        result = checker.check_delegations([{"agent": "builder", "task": "Build it"}])
        assert not result.has_conflicts
        assert result.dropped_agents == set()

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_enabled_with_convergent(self):
        from convergent import IntentResolver

        resolver = IntentResolver(min_stability=0.0)
        checker = DelegationConvergenceChecker(resolver=resolver)
        assert checker.enabled

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_independent_agents_no_conflicts(self):
        from convergent import IntentResolver

        resolver = IntentResolver(min_stability=0.0)
        checker = DelegationConvergenceChecker(resolver=resolver)

        delegations = [
            {"agent": "builder", "task": "Build the auth module"},
            {"agent": "tester", "task": "Write tests for the API"},
            {"agent": "documenter", "task": "Document the endpoints"},
        ]
        result = checker.check_delegations(delegations)
        # Independent roles with different tags should not conflict
        assert result.dropped_agents == set()

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_overlapping_delegations_detected(self):
        from convergent import IntentResolver

        resolver = IntentResolver(min_stability=0.0)
        checker = DelegationConvergenceChecker(resolver=resolver)

        # planner and architect share "architecture" and "design" tags (2+ overlap)
        delegations = [
            {"agent": "planner", "task": "Design the auth architecture"},
            {"agent": "architect", "task": "Design the system architecture"},
        ]
        result = checker.check_delegations(delegations)
        # Overlapping tags should produce adjustments or conflicts
        assert len(result.adjustments) > 0 or len(result.conflicts) > 0

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_delegation_to_intent_structure(self):
        checker = DelegationConvergenceChecker(resolver=MagicMock())
        intent = checker._delegation_to_intent(
            {"agent": "builder", "task": "Build auth"}
        )
        assert intent.agent_id == "builder"
        assert intent.intent == "Build auth"
        assert len(intent.provides) == 1
        assert "implementation" in intent.provides[0].tags
