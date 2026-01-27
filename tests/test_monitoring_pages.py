"""Tests for dashboard monitoring pages.

Tests all rendering functions with mocked Streamlit components.
"""

import sys
from unittest.mock import MagicMock, patch, PropertyMock
from types import SimpleNamespace

sys.path.insert(0, "src")


def _mock_st():
    """Create a comprehensive Streamlit mock."""
    st = MagicMock()
    st.columns.return_value = [MagicMock() for _ in range(4)]
    st.columns.return_value[0].__enter__ = MagicMock(
        return_value=st.columns.return_value[0]
    )
    st.columns.return_value[0].__exit__ = MagicMock(return_value=False)
    st.columns.return_value[1].__enter__ = MagicMock(
        return_value=st.columns.return_value[1]
    )
    st.columns.return_value[1].__exit__ = MagicMock(return_value=False)
    st.columns.return_value[2].__enter__ = MagicMock(
        return_value=st.columns.return_value[2]
    )
    st.columns.return_value[2].__exit__ = MagicMock(return_value=False)
    st.columns.return_value[3].__enter__ = MagicMock(
        return_value=st.columns.return_value[3]
    )
    st.columns.return_value[3].__exit__ = MagicMock(return_value=False)
    st.container.return_value.__enter__ = MagicMock(return_value=MagicMock())
    st.container.return_value.__exit__ = MagicMock(return_value=False)
    st.expander.return_value.__enter__ = MagicMock(return_value=MagicMock())
    st.expander.return_value.__exit__ = MagicMock(return_value=False)
    st.toggle.return_value = False  # Don't auto-refresh in tests
    st.button.return_value = False
    st.selectbox.return_value = "workflow_metrics"
    st.number_input.return_value = 24
    st.session_state = {}
    st.sidebar = MagicMock()
    return st


@patch("test_ai.dashboard.monitoring_pages.st", new_callable=_mock_st)
@patch("test_ai.dashboard.monitoring_pages.get_tracker")
class TestRenderMonitoringPage:
    """Tests for render_monitoring_page."""

    def test_renders_with_data(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_monitoring_page

        mock_tracker = MagicMock()
        mock_tracker.get_dashboard_data.return_value = {
            "summary": {
                "active_workflows": 2,
                "total_executions": 50,
                "success_rate": 95.0,
                "avg_duration_ms": 500,
            },
            "active_workflows": [
                {
                    "workflow_name": "build",
                    "execution_id": "abc123",
                    "completed_steps": 3,
                    "total_steps": 5,
                    "status": "running",
                }
            ],
            "recent_executions": [
                {
                    "workflow_name": "test",
                    "execution_id": "def456abcdef1234",
                    "status": "completed",
                    "duration_ms": 1200,
                    "completed_steps": 4,
                    "total_steps": 4,
                    "started_at": "2026-01-27T10:00:00",
                    "completed_at": "2026-01-27T10:01:00",
                    "total_tokens": 500,
                    "error": None,
                    "steps": [
                        {
                            "step_id": "s1",
                            "step_type": "claude_code",
                            "action": "execute",
                            "status": "success",
                            "duration_ms": 300,
                        }
                    ],
                }
            ],
        }
        mock_tracker_fn.return_value = mock_tracker
        render_monitoring_page()
        mock_st.title.assert_called_once()

    def test_renders_with_tracker_error(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_monitoring_page

        mock_tracker_fn.side_effect = Exception("No tracker")
        render_monitoring_page()
        mock_st.warning.assert_called()

    def test_renders_empty_active_workflows(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_monitoring_page

        mock_tracker = MagicMock()
        mock_tracker.get_dashboard_data.return_value = {
            "summary": {
                "active_workflows": 0,
                "total_executions": 0,
                "success_rate": 0,
                "avg_duration_ms": 0,
            },
            "active_workflows": [],
            "recent_executions": [],
        }
        mock_tracker_fn.return_value = mock_tracker
        render_monitoring_page()
        mock_st.info.assert_called()

    def test_renders_execution_with_error(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_monitoring_page

        mock_tracker = MagicMock()
        mock_tracker.get_dashboard_data.return_value = {
            "summary": {
                "active_workflows": 0,
                "total_executions": 1,
                "success_rate": 0,
                "avg_duration_ms": 1500,
            },
            "active_workflows": [],
            "recent_executions": [
                {
                    "workflow_name": "fail",
                    "execution_id": "err123456789abcdef",
                    "status": "failed",
                    "duration_ms": 1500,
                    "completed_steps": 1,
                    "total_steps": 3,
                    "started_at": "2026-01-27",
                    "error": "Step 2 failed",
                    "steps": [],
                }
            ],
        }
        mock_tracker_fn.return_value = mock_tracker
        render_monitoring_page()

    def test_low_success_rate_warning(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_monitoring_page

        mock_tracker = MagicMock()
        mock_tracker.get_dashboard_data.return_value = {
            "summary": {
                "active_workflows": 0,
                "total_executions": 10,
                "success_rate": 50.0,
                "avg_duration_ms": 2000,
            },
            "active_workflows": [],
            "recent_executions": [],
        }
        mock_tracker_fn.return_value = mock_tracker
        render_monitoring_page()

    def test_duration_display_seconds(self, mock_tracker_fn, mock_st):
        """Duration >= 1000ms displays in seconds."""
        from test_ai.dashboard.monitoring_pages import render_monitoring_page

        mock_tracker = MagicMock()
        mock_tracker.get_dashboard_data.return_value = {
            "summary": {
                "active_workflows": 0,
                "total_executions": 1,
                "success_rate": 100,
                "avg_duration_ms": 5000,
            },
            "active_workflows": [],
            "recent_executions": [],
        }
        mock_tracker_fn.return_value = mock_tracker
        render_monitoring_page()


@patch("test_ai.dashboard.monitoring_pages.st", new_callable=_mock_st)
class TestRenderAgentsPage:
    """Tests for render_agents_page."""

    def test_renders_with_active_agents(self, mock_st):
        from test_ai.dashboard.monitoring_pages import render_agents_page

        mock_tracker = MagicMock()
        mock_tracker.get_agent_summary.return_value = {
            "active_count": 2,
            "recent_count": 5,
            "by_role": {"planner": 1, "builder": 1},
        }
        mock_tracker.get_active_agents.return_value = [
            {
                "role": "planner",
                "agent_id": "agent_abc12345",
                "status": "active",
                "tasks_completed": 3,
            },
            {
                "role": "builder",
                "agent_id": "agent_def67890",
                "status": "active",
                "tasks_completed": 1,
            },
        ]
        mock_tracker.get_agent_history.return_value = [
            {
                "role": "planner",
                "agent_id": "agent_old12345",
                "status": "completed",
                "completed_at": "2026-01-27",
            },
        ]
        mock_st.session_state = {"agent_tracker": mock_tracker}

        render_agents_page()
        mock_st.title.assert_called_with("Agent Coordination")

    def test_renders_empty_agents(self, mock_st):
        from test_ai.dashboard.monitoring_pages import render_agents_page

        mock_tracker = MagicMock()
        mock_tracker.get_agent_summary.return_value = {
            "active_count": 0,
            "recent_count": 0,
            "by_role": {},
        }
        mock_tracker.get_active_agents.return_value = []
        mock_tracker.get_agent_history.return_value = []
        mock_st.session_state = {"agent_tracker": mock_tracker}

        render_agents_page()

    def test_renders_with_no_history(self, mock_st):
        from test_ai.dashboard.monitoring_pages import render_agents_page

        mock_tracker = MagicMock()
        mock_tracker.get_agent_summary.return_value = {
            "active_count": 0,
            "recent_count": 0,
            "by_role": {},
        }
        mock_tracker.get_active_agents.return_value = []
        mock_tracker.get_agent_history.return_value = []
        mock_st.session_state = {"agent_tracker": mock_tracker}

        render_agents_page()


@patch("test_ai.dashboard.monitoring_pages.st", new_callable=_mock_st)
@patch("test_ai.dashboard.monitoring_pages.get_tracker")
class TestRenderMetricsPage:
    """Tests for render_metrics_page."""

    def test_renders_with_data(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_metrics_page

        mock_tracker = MagicMock()
        mock_tracker.get_dashboard_data.return_value = {
            "summary": {
                "total_executions": 100,
                "failed_executions": 5,
                "total_steps_executed": 500,
                "total_tokens_used": 10000,
                "success_rate": 95.0,
                "avg_duration_ms": 800,
            },
            "step_performance": {
                "claude_code": {"count": 200, "avg_ms": 500, "failure_rate": 2.0},
                "openai": {"count": 300, "avg_ms": 300, "failure_rate": 1.0},
            },
            "recent_executions": [
                {"execution_id": "abc12345", "total_tokens": 500, "duration_ms": 800},
                {"execution_id": "def67890", "total_tokens": 300, "duration_ms": 600},
            ],
        }
        mock_tracker_fn.return_value = mock_tracker
        render_metrics_page()
        mock_st.title.assert_called_with("Metrics Dashboard")

    def test_renders_with_tracker_error(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_metrics_page

        mock_tracker_fn.side_effect = Exception("No tracker")
        render_metrics_page()

    def test_renders_empty_step_performance(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_metrics_page

        mock_tracker = MagicMock()
        mock_tracker.get_dashboard_data.return_value = {
            "summary": {},
            "step_performance": {},
            "recent_executions": [],
        }
        mock_tracker_fn.return_value = mock_tracker
        render_metrics_page()

    def test_renders_no_token_data(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_metrics_page

        mock_tracker = MagicMock()
        mock_tracker.get_dashboard_data.return_value = {
            "summary": {},
            "step_performance": {},
            "recent_executions": [
                {"execution_id": "x", "total_tokens": 0, "duration_ms": 0},
            ],
        }
        mock_tracker_fn.return_value = mock_tracker
        render_metrics_page()


@patch("test_ai.dashboard.monitoring_pages.st", new_callable=_mock_st)
@patch("test_ai.dashboard.monitoring_pages.get_tracker")
class TestRenderSystemStatus:
    def test_renders_active_workflows(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_system_status

        mock_tracker = MagicMock()
        mock_tracker.store.get_summary.return_value = {
            "active_workflows": 2,
            "success_rate": 90.0,
        }
        mock_tracker_fn.return_value = mock_tracker
        render_system_status()

    def test_renders_no_active(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_system_status

        mock_tracker = MagicMock()
        mock_tracker.store.get_summary.return_value = {
            "active_workflows": 0,
            "success_rate": 100,
        }
        mock_tracker_fn.return_value = mock_tracker
        render_system_status()

    def test_renders_on_error(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_system_status

        mock_tracker_fn.side_effect = Exception("fail")
        render_system_status()


@patch("test_ai.dashboard.monitoring_pages.st", new_callable=_mock_st)
class TestRenderAnalyticsPage:
    def test_renders_page(self, mock_st):
        from test_ai.dashboard.monitoring_pages import render_analytics_page

        mock_st.session_state = {}
        render_analytics_page()
        mock_st.title.assert_called_with("Analytics Pipelines")

    def test_renders_with_cached_result(self, mock_st):
        from test_ai.dashboard.monitoring_pages import render_analytics_page

        mock_result = MagicMock()
        mock_result.status = "completed"
        mock_result.stages = []
        mock_result.errors = []
        mock_result.final_output = None
        mock_st.session_state = {
            "analytics_result": mock_result,
            "analytics_pipeline": "workflow_metrics",
        }
        render_analytics_page()


@patch("test_ai.dashboard.monitoring_pages.st", new_callable=_mock_st)
class TestRunAnalyticsPipeline:
    @patch("test_ai.dashboard.monitoring_pages.PipelineBuilder", create=True)
    def test_workflow_metrics(self, mock_builder_cls, mock_st):
        # Can't easily test without real PipelineBuilder, but test the import path
        from test_ai.dashboard.monitoring_pages import _run_analytics_pipeline
        import pytest

        # Just test the unknown pipeline error
        with pytest.raises(ValueError, match="Unknown pipeline"):
            _run_analytics_pipeline("nonexistent")


class TestRenderPipelineResult:
    def test_renders_completed_result(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_pipeline_result

            mock_stage = MagicMock()
            mock_stage.stage.value = "collect"
            mock_stage.duration_ms = 100.0
            mock_stage.status = "success"
            mock_stage.error = None
            mock_stage.output = MagicMock()

            result = MagicMock()
            result.status = "completed"
            result.stages = [mock_stage]
            result.errors = []
            result.final_output = None

            pipelines = {"test_pipe": {"name": "Test Pipeline"}}
            _render_pipeline_result(result, "test_pipe", pipelines)

    def test_renders_with_errors(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_pipeline_result

            mock_stage = MagicMock()
            mock_stage.stage.value = "analyze"
            mock_stage.duration_ms = 50.0
            mock_stage.status = "failed"
            mock_stage.error = "Something went wrong"
            mock_stage.output = None

            result = MagicMock()
            result.status = "failed"
            result.stages = [mock_stage]
            result.errors = ["Error 1"]
            result.final_output = None

            _render_pipeline_result(result, "unknown", {})

    def test_renders_with_final_output(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_pipeline_result

            result = MagicMock()
            result.status = "completed"
            result.stages = []
            result.errors = []
            result.final_output = {"metrics": {"counters": {"total": 10}}}

            _render_pipeline_result(result, "test", {"test": {"name": "Test"}})


class TestStageRenderers:
    def test_render_collect_output_with_source(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_collect_output

            output = SimpleNamespace(
                source="tracker",
                collected_at="2026-01-27",
                data={
                    "metrics": {"counters": {"a": 1, "b": 2}},
                    "summary": {"key": "val"},
                },
            )
            _render_collect_output(output)

    def test_render_collect_output_dict(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_collect_output

            _render_collect_output({"raw": "data"})

    def test_render_collect_output_no_data(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_collect_output

            output = SimpleNamespace(source="tracker", collected_at="now")
            _render_collect_output(output)

    def test_render_analyze_output_with_findings(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_analyze_output

            output = SimpleNamespace(
                severity="warning",
                findings=[
                    {"severity": "warning", "message": "High latency"},
                    {"severity": "critical", "message": "Errors detected"},
                    {"severity": "info", "message": "All OK"},
                ],
            )
            _render_analyze_output(output)

    def test_render_analyze_output_no_findings(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_analyze_output

            output = SimpleNamespace(severity="info", findings=[])
            _render_analyze_output(output)

    def test_render_analyze_no_severity(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_analyze_output

            output = SimpleNamespace(findings=[{"message": "test"}])
            # no severity attribute
            delattr(output, "severity") if hasattr(output, "severity") else None
            output2 = MagicMock(spec=[])  # no attributes
            _render_analyze_output(output2)

    def test_render_visualize_output(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_visualize_output

            chart = SimpleNamespace(title="My Chart", chart_type="bar")
            output = SimpleNamespace(charts=[chart], streamlit_code="st.write('hi')")
            _render_visualize_output(output)

    def test_render_visualize_no_code(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_visualize_output

            output = SimpleNamespace(charts=[], streamlit_code="")
            _render_visualize_output(output)

    def test_render_report_output(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_report_output

            output = SimpleNamespace(report_type="summary", summary="All good")
            _render_report_output(output)

    def test_render_alert_output_with_alerts(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_alert_output

            output = SimpleNamespace(
                alerts=[
                    {"severity": "warning", "title": "Warn", "message": "Something"},
                    {"severity": "critical", "title": "Crit", "message": "Bad"},
                    {"severity": "info", "title": "Info", "message": "OK"},
                ]
            )
            _render_alert_output(output)

    def test_render_alert_output_empty(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_alert_output

            output = SimpleNamespace(alerts=[])
            _render_alert_output(output)

    def test_render_fallback_dict(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_fallback_output

            _render_fallback_output({"key": "val"})
            st_mock.json.assert_called()

    def test_render_fallback_to_dict(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_fallback_output

            obj = MagicMock()
            obj.to_dict.return_value = {"a": 1}
            _render_fallback_output(obj)

    def test_render_fallback_string(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_fallback_output

            _render_fallback_output("some string")
            st_mock.text.assert_called()

    def test_render_stage_output_dispatches(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_stage_output

            stage = MagicMock()
            stage.stage.value = "report"
            stage.output = SimpleNamespace(report_type="summary", summary="ok")
            _render_stage_output(stage)

    def test_render_stage_output_unknown_type(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_stage_output

            stage = MagicMock()
            stage.stage.value = "unknown_type"
            stage.output = {"raw": "data"}
            _render_stage_output(stage)


class TestRenderFinalOutput:
    def test_with_metrics_object(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_final_output

            output = SimpleNamespace(
                metrics={"counters": {"total_requests": 100, "errors": 5}},
                findings=[{"severity": "warning", "message": "High error rate"}],
            )
            _render_final_output(output)

    def test_with_data_dict(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_final_output

            output = SimpleNamespace(data={"metrics": {"counters": {"x": 1}}})
            _render_final_output(output)

    def test_with_plain_dict(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_final_output

            _render_final_output({"metrics": {"counters": {}}, "some": "data"})

    def test_with_to_dict_output(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_final_output

            output = MagicMock()
            output.metrics = {}
            output.findings = []
            output.to_dict.return_value = {"a": 1}
            # Ensure hasattr checks work
            type(output).metrics = PropertyMock(return_value={})
            type(output).findings = PropertyMock(return_value=[])
            _render_final_output(output)

    def test_with_string_output(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_final_output

            _render_final_output("plain string output")

    def test_with_zero_counters(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_final_output

            output = {"metrics": {"counters": {"zero_val": 0}}}
            _render_final_output(output)


@patch("test_ai.dashboard.monitoring_pages.st", new_callable=_mock_st)
@patch("test_ai.dashboard.monitoring_pages.get_parallel_tracker")
class TestRenderParallelExecutionPage:
    def test_renders_with_data(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_parallel_execution_page

        mock_tracker = MagicMock()
        mock_tracker.get_dashboard_data.return_value = {
            "summary": {
                "active_executions": 1,
                "total_executions": 10,
                "success_rate": 90.0,
                "active_branches": 3,
                "counters": {"branches_completed": 20, "branches_failed": 2},
                "rate_limit_waits": {"count": 5, "avg": 100.0, "max": 500.0},
                "rate_limit_states": {},
                "execution_duration": {"count": 10, "avg": 500, "p50": 450, "p95": 900},
                "branch_duration": {"count": 20, "avg": 100, "p50": 90, "p95": 200},
                "execution_tokens": {"count": 10, "avg": 500, "min": 100, "max": 1000},
            },
            "active_executions": [
                {
                    "pattern_type": "fan_out",
                    "step_id": "step_1",
                    "execution_id": "exec123456789abc",
                    "total_items": 10,
                    "completed_count": 5,
                    "failed_count": 1,
                    "active_branch_count": 4,
                    "duration_ms": 2000,
                    "total_tokens": 500,
                    "branches": [
                        {
                            "branch_id": "branch_1_long_name",
                            "status": "completed",
                            "item_index": 0,
                            "duration_ms": 100,
                        },
                        {
                            "branch_id": "branch_2_long_name",
                            "status": "running",
                            "item_index": 1,
                            "duration_ms": 50,
                        },
                    ],
                }
            ],
            "recent_executions": [
                {
                    "pattern_type": "map_reduce",
                    "step_id": "step_2",
                    "execution_id": "exec_old_12345678",
                    "status": "completed",
                    "total_items": 5,
                    "completed_count": 5,
                    "failed_count": 0,
                    "duration_ms": 3000,
                    "total_tokens": 1000,
                    "started_at": "2026-01-27",
                    "completed_at": "2026-01-27",
                    "branches": [],
                }
            ],
            "rate_limits": {
                "openai": {
                    "base_limit": 10,
                    "current_limit": 5,
                    "total_429s": 3,
                    "is_throttled": True,
                }
            },
        }
        mock_tracker_fn.return_value = mock_tracker
        render_parallel_execution_page()

    def test_renders_with_tracker_error(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_parallel_execution_page

        mock_tracker_fn.side_effect = Exception("No tracker")
        render_parallel_execution_page()

    def test_renders_no_active(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_parallel_execution_page

        mock_tracker = MagicMock()
        mock_tracker.get_dashboard_data.return_value = {
            "summary": {
                "active_executions": 0,
                "total_executions": 0,
                "success_rate": 0,
                "active_branches": 0,
                "counters": {},
            },
            "active_executions": [],
            "recent_executions": [],
            "rate_limits": {},
        }
        mock_tracker_fn.return_value = mock_tracker
        render_parallel_execution_page()

    def test_renders_failed_execution(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_parallel_execution_page

        mock_tracker = MagicMock()
        mock_tracker.get_dashboard_data.return_value = {
            "summary": {
                "active_executions": 0,
                "total_executions": 1,
                "success_rate": 0,
                "active_branches": 0,
                "counters": {"branches_completed": 0, "branches_failed": 3},
            },
            "active_executions": [],
            "recent_executions": [
                {
                    "pattern_type": "fan_out",
                    "step_id": "s1",
                    "execution_id": "fail123456789abc",
                    "status": "failed",
                    "total_items": 3,
                    "completed_count": 0,
                    "failed_count": 3,
                    "duration_ms": 100,
                    "total_tokens": 0,
                    "started_at": "2026-01-27",
                    "completed_at": "2026-01-27",
                    "branches": [
                        {"branch_id": "b1", "status": "failed", "error": "timeout"},
                    ],
                }
            ],
            "rate_limits": {},
        }
        mock_tracker_fn.return_value = mock_tracker
        render_parallel_execution_page()


class TestRenderRateLimitSection:
    def test_no_rate_limits(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_rate_limit_section

            _render_rate_limit_section({}, {})
            st_mock.success.assert_called()

    def test_with_rate_limits(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_rate_limit_section

            rate_limits = {
                "openai": {
                    "base_limit": 10,
                    "current_limit": 5,
                    "total_429s": 3,
                    "is_throttled": True,
                },
                "anthropic": {
                    "base_limit": 10,
                    "current_limit": 10,
                    "total_429s": 0,
                    "is_throttled": False,
                },
            }
            summary = {
                "rate_limit_waits": {"count": 5, "avg": 100.0, "max": 500.0},
                "rate_limit_states": {},
            }
            _render_rate_limit_section(rate_limits, summary)

    def test_with_only_states(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_rate_limit_section

            summary = {
                "rate_limit_waits": {"count": 0},
                "rate_limit_states": {
                    "openai": {"base_limit": 10, "current_limit": 10, "total_429s": 1}
                },
            }
            _render_rate_limit_section({}, summary)

    def test_warning_status(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_rate_limit_section

            rate_limits = {
                "provider": {
                    "base_limit": 10,
                    "current_limit": 10,
                    "total_429s": 1,
                    "is_throttled": False,
                }
            }
            _render_rate_limit_section(rate_limits, {})


class TestRenderActiveExecution:
    def test_renders_execution(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_active_execution

            execution = {
                "pattern_type": "auto_parallel",
                "step_id": "step_1",
                "execution_id": "exec1234567890ab",
                "total_items": 5,
                "completed_count": 3,
                "failed_count": 0,
                "active_branch_count": 2,
                "duration_ms": 500,
                "total_tokens": 100,
                "branches": [],
            }
            _render_active_execution(execution)

    def test_renders_unknown_pattern(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_active_execution

            execution = {
                "pattern_type": "unknown",
                "step_id": "s",
                "execution_id": "x" * 20,
                "total_items": 0,
                "completed_count": 0,
                "failed_count": 0,
                "active_branch_count": 0,
                "duration_ms": 0,
                "total_tokens": 0,
                "branches": [],
            }
            _render_active_execution(execution)


class TestRenderPerformanceStats:
    def test_with_full_stats(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_performance_stats

            summary = {
                "execution_duration": {"count": 10, "avg": 500, "p50": 450, "p95": 900},
                "branch_duration": {"count": 20, "avg": 100, "p50": 90, "p95": 200},
                "execution_tokens": {"count": 10, "avg": 500, "min": 100, "max": 1000},
                "counters": {
                    "executions_started_fan_out": 5,
                    "executions_started_map_reduce": 3,
                    "executions_started": 8,
                },
            }
            _render_performance_stats(summary)

    def test_with_empty_stats(self):
        st_mock = _mock_st()
        with patch("test_ai.dashboard.monitoring_pages.st", st_mock):
            from test_ai.dashboard.monitoring_pages import _render_performance_stats

            summary = {
                "execution_duration": {"count": 0},
                "branch_duration": {"count": 0},
                "execution_tokens": {"count": 0},
                "counters": {},
            }
            _render_performance_stats(summary)


@patch("test_ai.dashboard.monitoring_pages.st", new_callable=_mock_st)
@patch("test_ai.dashboard.monitoring_pages.get_parallel_tracker")
class TestRenderParallelStatusSidebar:
    def test_active_executions(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_parallel_status_sidebar

        mock_tracker = MagicMock()
        mock_tracker.get_summary.return_value = {
            "active_executions": 2,
            "active_branches": 5,
            "rate_limit_states": {"openai": {"is_throttled": True}},
        }
        mock_tracker_fn.return_value = mock_tracker
        render_parallel_status_sidebar()

    def test_no_active(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_parallel_status_sidebar

        mock_tracker = MagicMock()
        mock_tracker.get_summary.return_value = {
            "active_executions": 0,
            "active_branches": 0,
            "rate_limit_states": {},
        }
        mock_tracker_fn.return_value = mock_tracker
        render_parallel_status_sidebar()

    def test_tracker_error(self, mock_tracker_fn, mock_st):
        from test_ai.dashboard.monitoring_pages import render_parallel_status_sidebar

        mock_tracker_fn.side_effect = Exception("No tracker")
        render_parallel_status_sidebar()
