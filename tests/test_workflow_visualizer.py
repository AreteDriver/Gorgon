"""Tests for workflow visualizer component."""

import sys
from unittest.mock import MagicMock, patch

import pytest


def _create_context_manager():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_cm)
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


def _create_columns(n):
    count = n if isinstance(n, int) else len(n)
    return [_create_context_manager() for _ in range(count)]


def _create_tabs(labels):
    return [_create_context_manager() for _ in labels]


def _create_expander(label, **kwargs):
    return _create_context_manager()


@pytest.fixture(autouse=True)
def mock_streamlit():
    mock_st = MagicMock()

    class SessionState(dict):
        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError:
                raise AttributeError(name)

        def __setattr__(self, name, value):
            self[name] = value

        def __delattr__(self, name):
            try:
                del self[name]
            except KeyError:
                raise AttributeError(name)

    mock_st.session_state = SessionState()
    mock_st.cache_resource = lambda f: f
    mock_st.columns.side_effect = _create_columns
    mock_st.tabs.side_effect = _create_tabs
    mock_st.expander.side_effect = _create_expander

    # Remove cached module so re-import picks up mock streamlit
    mod_key = "test_ai.dashboard.workflow_visualizer"
    cached = sys.modules.pop(mod_key, None)

    with patch.dict(sys.modules, {"streamlit": mock_st}):
        yield mock_st

    # Remove again so other tests aren't affected
    sys.modules.pop(mod_key, None)
    if cached is not None:
        sys.modules[mod_key] = cached


class TestDataClasses:
    def test_step_status_enum_values(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import StepStatus

        assert StepStatus.PENDING.value == "pending"
        assert StepStatus.RUNNING.value == "running"
        assert StepStatus.COMPLETED.value == "completed"
        assert StepStatus.FAILED.value == "failed"
        assert StepStatus.SKIPPED.value == "skipped"

    def test_visual_step_defaults(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import StepStatus, VisualStep

        step = VisualStep(id="s1", name="Test", type="shell")

        assert step.id == "s1"
        assert step.name == "Test"
        assert step.type == "shell"
        assert step.status == StepStatus.PENDING
        assert step.duration_ms is None
        assert step.error is None
        assert step.output_preview is None

    def test_visual_step_all_fields(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import StepStatus, VisualStep

        step = VisualStep(
            id="s1",
            name="Build",
            type="claude_code",
            status=StepStatus.COMPLETED,
            duration_ms=1500,
            error=None,
            output_preview="success",
        )

        assert step.status == StepStatus.COMPLETED
        assert step.duration_ms == 1500
        assert step.output_preview == "success"


class TestRenderWorkflowVisualizer:
    def _make_steps(self):
        return [
            {"id": "plan", "type": "claude_code", "params": {"role": "planner"}},
            {"id": "build", "type": "openai", "params": {"role": "builder"}},
            {"id": "test", "type": "shell", "params": {}},
        ]

    def test_renders_with_steps(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import render_workflow_visualizer

        render_workflow_visualizer(self._make_steps())

        mock_streamlit.markdown.assert_called()
        mock_streamlit.progress.assert_called()

    def test_compact_mode(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import render_workflow_visualizer

        render_workflow_visualizer(self._make_steps(), compact=True)

        mock_streamlit.progress.assert_called()
        # Compact mode creates columns for steps
        mock_streamlit.columns.assert_called()

    def test_empty_steps(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import render_workflow_visualizer

        render_workflow_visualizer([])

        mock_streamlit.progress.assert_called_once()

    def test_current_step_highlight(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import render_workflow_visualizer

        render_workflow_visualizer(self._make_steps(), current_step="build")

        # Should render without error; the running step gets highlighted via markdown
        mock_streamlit.markdown.assert_called()

    def test_with_step_results(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import render_workflow_visualizer

        results = {
            "plan": {"status": "completed", "duration_ms": 500},
            "build": {"status": "completed", "duration_ms": 1200},
        }

        render_workflow_visualizer(self._make_steps(), step_results=results)

        # Progress should reflect 2/3 completed
        progress_call = mock_streamlit.progress.call_args
        assert progress_call[0][0] == pytest.approx(2 / 3, abs=0.01)


class TestRenderWorkflowSummary:
    def test_renders_metric_columns(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import render_workflow_summary

        render_workflow_summary(
            workflow_name="Test WF",
            total_steps=5,
            completed_steps=4,
            failed_steps=1,
            total_duration_ms=3000,
            total_cost_usd=0.05,
        )

        assert mock_streamlit.metric.call_count == 4
        mock_streamlit.columns.assert_called_with(4)

    def test_zero_values(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import render_workflow_summary

        render_workflow_summary(
            workflow_name="Empty",
            total_steps=0,
            completed_steps=0,
            failed_steps=0,
        )

        mock_streamlit.metric.assert_called()

    def test_optional_duration_and_cost(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import render_workflow_summary

        render_workflow_summary(
            workflow_name="Basic",
            total_steps=3,
            completed_steps=3,
            failed_steps=0,
        )

        # Duration and cost should show "N/A"
        metric_calls = mock_streamlit.metric.call_args_list
        na_calls = [c for c in metric_calls if "N/A" in str(c)]
        assert len(na_calls) >= 1

    def test_failed_steps_shows_error(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import render_workflow_summary

        render_workflow_summary(
            workflow_name="Fail",
            total_steps=3,
            completed_steps=2,
            failed_steps=1,
        )

        mock_streamlit.error.assert_called()

    def test_all_completed_shows_success(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import render_workflow_summary

        render_workflow_summary(
            workflow_name="Done",
            total_steps=3,
            completed_steps=3,
            failed_steps=0,
        )

        mock_streamlit.success.assert_called()

    def test_in_progress_shows_info(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import render_workflow_summary

        render_workflow_summary(
            workflow_name="Running",
            total_steps=5,
            completed_steps=2,
            failed_steps=0,
        )

        mock_streamlit.info.assert_called()


class TestRenderStepTimeline:
    def test_renders_timeline(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import render_step_timeline

        steps = [
            {"id": "plan", "type": "claude_code"},
            {"id": "build", "type": "openai"},
        ]
        results = {
            "plan": {"status": "completed", "duration_ms": 500},
            "build": {"status": "completed", "duration_ms": 1200},
        }

        render_step_timeline(steps, results)

        mock_streamlit.markdown.assert_called()

    def test_empty_results(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import render_step_timeline

        steps = [{"id": "plan", "type": "claude_code"}]

        render_step_timeline(steps, {})

        mock_streamlit.markdown.assert_called()


class TestRenderAgentActivity:
    def test_renders_activities(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import render_agent_activity

        agents = [
            {
                "role": "planner",
                "action": "planning",
                "timestamp": "10:00",
                "status": "completed",
            },
            {
                "role": "builder",
                "action": "coding",
                "timestamp": "10:05",
                "status": "running",
            },
        ]

        render_agent_activity(agents)

        mock_streamlit.markdown.assert_called()

    def test_empty_list(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import render_agent_activity

        render_agent_activity([])

        mock_streamlit.info.assert_called()

    def test_show_live_flag(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import render_agent_activity

        render_agent_activity([], show_live=True)

        # Live indicator rendered via markdown
        calls = [str(c) for c in mock_streamlit.markdown.call_args_list]
        assert any("Live" in c for c in calls)

    def test_show_live_false(self, mock_streamlit):
        from test_ai.dashboard.workflow_visualizer import render_agent_activity

        render_agent_activity([], show_live=False)

        # No live indicator — only the title markdown and info
        calls = [str(c) for c in mock_streamlit.markdown.call_args_list]
        live_calls = [c for c in calls if "pulse" in c]
        assert len(live_calls) == 0
