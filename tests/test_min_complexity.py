"""Tests for the min_complexity workflow step feature.

Tests both the _meets_min_complexity helper function and the
StepConfig.min_complexity field integration in the executor.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from unittest.mock import MagicMock

from test_ai.workflow.executor_step import _meets_min_complexity
from test_ai.workflow.executor_results import StepResult, StepStatus
from test_ai.workflow.loader import StepConfig


# ---------------------------------------------------------------------------
# _meets_min_complexity helper
# ---------------------------------------------------------------------------


class TestMeetsMinComplexity:
    """Unit tests for the _meets_min_complexity function."""

    def test_none_complexity_always_passes(self):
        """When no classification exists, always allow execution."""
        assert _meets_min_complexity(None, "simple") is True
        assert _meets_min_complexity(None, "medium") is True
        assert _meets_min_complexity(None, "complex") is True

    def test_simple_meets_simple(self):
        assert _meets_min_complexity("simple", "simple") is True

    def test_medium_meets_simple(self):
        assert _meets_min_complexity("medium", "simple") is True

    def test_medium_meets_medium(self):
        assert _meets_min_complexity("medium", "medium") is True

    def test_complex_meets_all(self):
        assert _meets_min_complexity("complex", "simple") is True
        assert _meets_min_complexity("complex", "medium") is True
        assert _meets_min_complexity("complex", "complex") is True

    def test_simple_does_not_meet_medium(self):
        assert _meets_min_complexity("simple", "medium") is False

    def test_simple_does_not_meet_complex(self):
        assert _meets_min_complexity("simple", "complex") is False

    def test_medium_does_not_meet_complex(self):
        assert _meets_min_complexity("medium", "complex") is False

    def test_unknown_complexity_defaults_to_medium(self):
        """Unknown values default to order index 1 (medium)."""
        assert _meets_min_complexity("unknown", "simple") is True
        assert _meets_min_complexity("unknown", "medium") is True
        assert _meets_min_complexity("unknown", "complex") is False


# ---------------------------------------------------------------------------
# StepConfig.min_complexity parsing
# ---------------------------------------------------------------------------


class TestStepConfigMinComplexity:
    """Tests for StepConfig.min_complexity field."""

    def test_from_dict_with_min_complexity(self):
        data = {
            "id": "review_step",
            "type": "claude_code",
            "min_complexity": "complex",
        }
        step = StepConfig.from_dict(data)
        assert step.min_complexity == "complex"

    def test_from_dict_without_min_complexity(self):
        data = {
            "id": "build_step",
            "type": "claude_code",
        }
        step = StepConfig.from_dict(data)
        assert step.min_complexity is None

    def test_from_dict_medium_complexity(self):
        data = {
            "id": "test_step",
            "type": "claude_code",
            "min_complexity": "medium",
        }
        step = StepConfig.from_dict(data)
        assert step.min_complexity == "medium"


# ---------------------------------------------------------------------------
# Step precondition check integration
# ---------------------------------------------------------------------------


def _bare_executor(**overrides):
    """Create a minimal executor-like object for mixin testing."""
    from test_ai.workflow.executor_core import WorkflowExecutor

    exe = WorkflowExecutor.__new__(WorkflowExecutor)
    exe.checkpoint_manager = None
    exe.contract_validator = None
    exe.budget_manager = None
    exe.dry_run = False
    exe.error_callback = None
    exe.fallback_callbacks = {}
    exe.memory_manager = None
    exe.memory_config = None
    exe.feedback_engine = None
    exe.execution_manager = None
    exe._execution_id = None
    exe._handlers = {"claude_code": MagicMock(return_value={"output": "ok"})}
    exe._context = {}
    exe._current_workflow_id = None
    for k, v in overrides.items():
        setattr(exe, k, v)
    return exe


def _make_step(step_id="s1", step_type="claude_code", **kwargs) -> StepConfig:
    return StepConfig(id=step_id, type=step_type, params={}, **kwargs)


class TestStepPreconditionComplexity:
    """Integration tests for min_complexity in step preconditions."""

    def test_step_skipped_when_below_min_complexity(self):
        exe = _bare_executor(_context={"_task_complexity": "simple"})
        step = _make_step(min_complexity="complex")
        result = StepResult(step_id=step.id, status=StepStatus.PENDING)

        handler, cb, error = exe._check_step_preconditions(step, result)

        assert result.status == StepStatus.SKIPPED
        assert handler is None
        assert error is None

    def test_step_runs_when_meeting_min_complexity(self):
        exe = _bare_executor(_context={"_task_complexity": "complex"})
        step = _make_step(min_complexity="complex")
        result = StepResult(step_id=step.id, status=StepStatus.PENDING)

        handler, cb, error = exe._check_step_preconditions(step, result)

        assert result.status != StepStatus.SKIPPED
        assert handler is not None

    def test_step_runs_when_no_classification(self):
        """Steps run normally when _task_complexity is not set."""
        exe = _bare_executor(_context={})
        step = _make_step(min_complexity="complex")
        result = StepResult(step_id=step.id, status=StepStatus.PENDING)

        handler, cb, error = exe._check_step_preconditions(step, result)

        assert result.status != StepStatus.SKIPPED
        assert handler is not None

    def test_step_runs_when_no_min_complexity(self):
        """Steps without min_complexity always run."""
        exe = _bare_executor(_context={"_task_complexity": "simple"})
        step = _make_step()  # No min_complexity
        result = StepResult(step_id=step.id, status=StepStatus.PENDING)

        handler, cb, error = exe._check_step_preconditions(step, result)

        assert result.status != StepStatus.SKIPPED
        assert handler is not None

    def test_medium_task_skips_complex_step(self):
        exe = _bare_executor(_context={"_task_complexity": "medium"})
        step = _make_step(min_complexity="complex")
        result = StepResult(step_id=step.id, status=StepStatus.PENDING)

        handler, cb, error = exe._check_step_preconditions(step, result)

        assert result.status == StepStatus.SKIPPED

    def test_medium_task_runs_medium_step(self):
        exe = _bare_executor(_context={"_task_complexity": "medium"})
        step = _make_step(min_complexity="medium")
        result = StepResult(step_id=step.id, status=StepStatus.PENDING)

        handler, cb, error = exe._check_step_preconditions(step, result)

        assert result.status != StepStatus.SKIPPED
        assert handler is not None
