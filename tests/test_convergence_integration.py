"""Tests for the Convergent ↔ Gorgon integration adapter."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from test_ai.agents.convergence import (
    ConvergenceResult,
    DelegationConvergenceChecker,
    HAS_CONVERGENT,
    create_checker,
    format_convergence_alert,
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


class TestCreateChecker:
    """Test the create_checker factory function."""

    def test_returns_checker(self):
        checker = create_checker()
        assert isinstance(checker, DelegationConvergenceChecker)

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_enabled_when_convergent_available(self):
        checker = create_checker()
        assert checker.enabled is True

    def test_disabled_when_convergent_unavailable(self, monkeypatch):
        import test_ai.agents.convergence as conv_mod

        monkeypatch.setattr(conv_mod, "HAS_CONVERGENT", False)
        checker = create_checker()
        assert checker.enabled is False

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_checker_can_process_delegations(self):
        checker = create_checker()
        result = checker.check_delegations(
            [
                {"agent": "builder", "task": "Build it"},
                {"agent": "tester", "task": "Test it"},
            ]
        )
        assert isinstance(result, ConvergenceResult)


class TestFormatConvergenceAlert:
    """Test the format_convergence_alert formatter."""

    def test_empty_result(self):
        result = ConvergenceResult()
        alert = format_convergence_alert(result)
        assert alert == ""

    def test_conflicts_formatted(self):
        result = ConvergenceResult(
            conflicts=[
                {"agent": "builder", "description": "overlap with tester"},
                {"agent": "planner", "description": "design conflict"},
            ]
        )
        alert = format_convergence_alert(result)
        assert "Conflicts (2):" in alert
        assert "builder: overlap with tester" in alert
        assert "planner: design conflict" in alert

    def test_dropped_agents_formatted(self):
        result = ConvergenceResult(dropped_agents={"builder", "tester"})
        alert = format_convergence_alert(result)
        assert "Dropped agents (2):" in alert
        assert "builder" in alert
        assert "tester" in alert

    def test_adjustments_formatted(self):
        result = ConvergenceResult(
            adjustments=[
                {"agent": "builder", "description": "consume from tester"},
            ]
        )
        alert = format_convergence_alert(result)
        assert "Adjustments (1):" in alert
        assert "builder: consume from tester" in alert

    def test_combined_alert(self):
        result = ConvergenceResult(
            conflicts=[{"agent": "a", "description": "c1"}],
            dropped_agents={"b"},
            adjustments=[{"agent": "c", "description": "a1"}],
        )
        alert = format_convergence_alert(result)
        assert "Conflicts" in alert
        assert "Dropped agents" in alert
        assert "Adjustments" in alert
