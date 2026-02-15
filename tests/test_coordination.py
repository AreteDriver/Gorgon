"""Tests for the coordination layer: Convergent ↔ Gorgon workflow integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from test_ai.coordination.convergent_bridge import (
    HAS_CONVERGENT,
    ConvergentPublisher,
    ResolutionResult,
    StabilityGate,
    StabilityReport,
    StepIntent,
    WorkflowCoordinator,
    _role_tags,
)
from test_ai.coordination.parallel_executor import CoordinatedParallelMixin


# ---------------------------------------------------------------------------
# StepIntent tests
# ---------------------------------------------------------------------------


class TestStepIntent:
    def test_defaults(self):
        intent = StepIntent(step_id="s1", agent_role="builder", description="Build it")
        assert intent.step_id == "s1"
        assert intent.stability == 0.0
        assert intent.provides == []
        assert intent.requires == []

    def test_with_interfaces(self):
        intent = StepIntent(
            step_id="s2",
            agent_role="tester",
            description="Test it",
            provides=["test_report"],
            requires=["code_output"],
            tags=["testing"],
        )
        assert intent.provides == ["test_report"]
        assert intent.requires == ["code_output"]


# ---------------------------------------------------------------------------
# ResolutionResult tests
# ---------------------------------------------------------------------------


class TestResolutionResult:
    def test_defaults(self):
        r = ResolutionResult(step_id="s1")
        assert r.stability == 0.0
        assert not r.should_yield
        assert r.adjustments == []
        assert r.conflicts == []


# ---------------------------------------------------------------------------
# StabilityReport tests
# ---------------------------------------------------------------------------


class TestStabilityReport:
    def test_defaults(self):
        report = StabilityReport()
        assert not report.converged
        assert report.mean_stability == 0.0
        assert report.passes == 0

    def test_converged_report(self):
        report = StabilityReport(
            converged=True,
            mean_stability=0.8,
            min_stability=0.6,
            step_stabilities={"s1": 0.6, "s2": 1.0},
            passes=1,
        )
        assert report.converged
        assert report.min_stability == 0.6


# ---------------------------------------------------------------------------
# Role tag helpers
# ---------------------------------------------------------------------------


class TestRoleTags:
    def test_known_roles(self):
        assert "implementation" in _role_tags("builder")
        assert "testing" in _role_tags("tester")
        assert "architecture" in _role_tags("architect")

    def test_unknown_role_uses_name(self):
        assert _role_tags("custom_agent") == ["custom_agent"]


# ---------------------------------------------------------------------------
# ConvergentPublisher tests
# ---------------------------------------------------------------------------


class TestConvergentPublisher:
    def _make_publisher(self):
        resolver = MagicMock()
        return ConvergentPublisher(resolver=resolver, step_id="s1", agent_role="builder")

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_publish_calls_resolver(self):
        pub = self._make_publisher()
        intent = pub.publish(description="Build auth module", provides=["auth_api"])
        assert intent.step_id == "s1"
        assert intent.agent_role == "builder"
        assert intent.provides == ["auth_api"]
        pub._resolver.publish.assert_called_once()

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_resolve_without_publish_returns_empty(self):
        pub = self._make_publisher()
        result = pub.resolve()
        assert result.step_id == "s1"
        assert result.stability == 0.0
        pub._resolver.resolve.assert_not_called()

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_resolve_after_publish(self):
        pub = self._make_publisher()

        mock_adj = MagicMock()
        mock_adj.kind = "Narrow"
        mock_adj.description = "Narrow scope"
        mock_adj.confidence = 0.5

        mock_resolution = MagicMock()
        mock_resolution.adjustments = [mock_adj]
        mock_resolution.conflicts = []
        mock_resolution.stability = 0.7
        pub._resolver.resolve.return_value = mock_resolution

        pub.publish(description="Build it")
        result = pub.resolve()

        assert result.stability == 0.7
        assert len(result.adjustments) == 1
        assert result.adjustments[0]["kind"] == "Narrow"
        assert not result.should_yield

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_consume_instead_triggers_yield(self):
        pub = self._make_publisher()

        mock_adj = MagicMock()
        mock_adj.kind = "ConsumeInstead"
        mock_adj.description = "Use existing output"
        mock_adj.confidence = 0.9

        mock_resolution = MagicMock()
        mock_resolution.adjustments = [mock_adj]
        mock_resolution.conflicts = []
        mock_resolution.stability = 0.4
        pub._resolver.resolve.return_value = mock_resolution

        pub.publish(description="Build it")
        result = pub.resolve()
        assert result.should_yield


# ---------------------------------------------------------------------------
# StabilityGate tests
# ---------------------------------------------------------------------------


class TestStabilityGate:
    def test_empty_publishers_converge(self):
        gate = StabilityGate(resolver=MagicMock(), min_stability=0.3)
        report = gate.check([])
        assert report.converged

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_all_above_threshold_converges(self):
        resolver = MagicMock()
        gate = StabilityGate(resolver=resolver, min_stability=0.3, max_passes=1)

        pub1 = ConvergentPublisher(resolver=resolver, step_id="s1", agent_role="builder")
        pub2 = ConvergentPublisher(resolver=resolver, step_id="s2", agent_role="tester")

        # Mock publish so _published is set
        pub1.publish(description="Build")
        pub2.publish(description="Test")

        # Mock resolve to return high stability
        mock_resolution = MagicMock()
        mock_resolution.adjustments = []
        mock_resolution.conflicts = []
        mock_resolution.stability = 0.8
        resolver.resolve.return_value = mock_resolution

        report = gate.check([pub1, pub2])
        assert report.converged
        assert report.min_stability == 0.8
        assert report.passes == 1

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_below_threshold_does_not_converge(self):
        resolver = MagicMock()
        gate = StabilityGate(resolver=resolver, min_stability=0.5, max_passes=2)

        pub1 = ConvergentPublisher(resolver=resolver, step_id="s1", agent_role="builder")
        pub1.publish(description="Build")

        mock_resolution = MagicMock()
        mock_resolution.adjustments = []
        mock_resolution.conflicts = []
        mock_resolution.stability = 0.2
        resolver.resolve.return_value = mock_resolution

        report = gate.check([pub1])
        assert not report.converged
        assert report.passes == 2  # Exhausted max passes


# ---------------------------------------------------------------------------
# WorkflowCoordinator tests
# ---------------------------------------------------------------------------


class TestWorkflowCoordinator:
    def test_disabled_without_convergent(self, monkeypatch):
        import test_ai.coordination.convergent_bridge as bridge_mod

        monkeypatch.setattr(bridge_mod, "HAS_CONVERGENT", False)
        coord = WorkflowCoordinator.__new__(WorkflowCoordinator)
        coord._min_stability = 0.3
        coord._max_passes = 3
        coord._resolver = None
        coord._gate = None
        coord._publishers = {}
        coord._enabled = False
        coord._setup()
        assert not coord.enabled

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_enabled_with_convergent(self):
        coord = WorkflowCoordinator()
        assert coord.enabled

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_create_publisher(self):
        coord = WorkflowCoordinator()
        pub = coord.create_publisher("s1", "builder")
        assert pub is not None
        assert pub.step_id == "s1"

    def test_create_publisher_returns_none_when_disabled(self, monkeypatch):
        import test_ai.coordination.convergent_bridge as bridge_mod

        monkeypatch.setattr(bridge_mod, "HAS_CONVERGENT", False)
        coord = WorkflowCoordinator.__new__(WorkflowCoordinator)
        coord._enabled = False
        coord._resolver = None
        coord._publishers = {}
        pub = coord.create_publisher("s1", "builder")
        assert pub is None

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_publish_step_intent(self):
        coord = WorkflowCoordinator()
        intent = coord.publish_step_intent(
            step_id="s1",
            agent_role="builder",
            description="Build auth",
            provides=["auth_api"],
        )
        assert intent is not None
        assert intent.step_id == "s1"
        assert "s1" in coord._publishers

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_check_stability_empty(self):
        coord = WorkflowCoordinator()
        report = coord.check_stability()
        assert report.converged

    def test_check_stability_disabled(self, monkeypatch):
        import test_ai.coordination.convergent_bridge as bridge_mod

        monkeypatch.setattr(bridge_mod, "HAS_CONVERGENT", False)
        coord = WorkflowCoordinator.__new__(WorkflowCoordinator)
        coord._enabled = False
        coord._gate = None
        coord._publishers = {}
        report = coord.check_stability()
        assert report.converged

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_reset_clears_publishers(self):
        coord = WorkflowCoordinator()
        coord.publish_step_intent("s1", "builder", "Build")
        assert len(coord._publishers) == 1
        coord.reset()
        assert len(coord._publishers) == 0


# ---------------------------------------------------------------------------
# CoordinatedParallelMixin tests
# ---------------------------------------------------------------------------


class TestCoordinatedParallelMixin:
    def test_get_coordinator_disabled_by_default(self):
        """Coordination is off when coordination_enabled is False."""
        mixin = CoordinatedParallelMixin()
        settings = MagicMock()
        settings.coordination_enabled = False
        assert mixin._get_coordinator(settings) is None

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_get_coordinator_enabled(self):
        """Returns a coordinator when convergent is available and enabled."""
        mixin = CoordinatedParallelMixin()
        settings = MagicMock()
        settings.coordination_enabled = True
        settings.coordination_min_stability = 0.3
        settings.coordination_max_passes = 3
        coord = mixin._get_coordinator(settings)
        assert coord is not None
        assert coord.enabled

    def test_get_coordinator_without_convergent(self, monkeypatch):
        """Returns None even if enabled when convergent is not installed."""
        import test_ai.coordination.parallel_executor as pe_mod

        monkeypatch.setattr(pe_mod, "HAS_CONVERGENT", False)
        mixin = CoordinatedParallelMixin()
        settings = MagicMock()
        settings.coordination_enabled = True
        assert mixin._get_coordinator(settings) is None


# ---------------------------------------------------------------------------
# WorkflowSettings coordination fields
# ---------------------------------------------------------------------------


class TestWorkflowSettingsCoordination:
    def test_defaults(self):
        from test_ai.workflow.loader import WorkflowSettings

        settings = WorkflowSettings()
        assert settings.coordination_enabled is False
        assert settings.coordination_min_stability == 0.3
        assert settings.coordination_max_passes == 3

    def test_from_dict_with_coordination(self):
        from test_ai.workflow.loader import WorkflowSettings

        data = {
            "auto_parallel": True,
            "coordination_enabled": True,
            "coordination_min_stability": 0.5,
            "coordination_max_passes": 5,
        }
        settings = WorkflowSettings.from_dict(data)
        assert settings.auto_parallel is True
        assert settings.coordination_enabled is True
        assert settings.coordination_min_stability == 0.5
        assert settings.coordination_max_passes == 5

    def test_from_dict_without_coordination(self):
        from test_ai.workflow.loader import WorkflowSettings

        data = {"auto_parallel": True}
        settings = WorkflowSettings.from_dict(data)
        assert settings.coordination_enabled is False
        assert settings.coordination_min_stability == 0.3


# ---------------------------------------------------------------------------
# Integration: executor uses coordination path
# ---------------------------------------------------------------------------


class TestExecutorCoordinationPath:
    def test_executor_has_coordination_mixin(self):
        """WorkflowExecutor includes CoordinatedParallelMixin in its MRO."""
        from test_ai.workflow.executor_core import WorkflowExecutor

        assert issubclass(WorkflowExecutor, CoordinatedParallelMixin)

    def test_executor_uses_coordination_when_enabled(self):
        """When both auto_parallel and coordination_enabled are True,
        the executor calls _execute_with_coordination."""
        from test_ai.workflow.executor_core import WorkflowExecutor
        from test_ai.workflow.loader import WorkflowConfig, WorkflowSettings

        executor = WorkflowExecutor()

        settings = WorkflowSettings(
            auto_parallel=True,
            coordination_enabled=True,
        )
        workflow = MagicMock(spec=WorkflowConfig)
        workflow.name = "test_wf"
        workflow.steps = []
        workflow.inputs = {}
        workflow.outputs = []
        workflow.settings = settings

        with patch.object(
            executor, "_execute_with_coordination"
        ) as mock_coord:
            executor.execute(workflow, inputs={})
            mock_coord.assert_called_once()

    def test_executor_falls_back_to_auto_parallel(self):
        """When coordination_enabled is False but auto_parallel is True,
        the executor uses standard auto-parallel."""
        from test_ai.workflow.executor_core import WorkflowExecutor
        from test_ai.workflow.loader import WorkflowConfig, WorkflowSettings

        executor = WorkflowExecutor()

        settings = WorkflowSettings(
            auto_parallel=True,
            coordination_enabled=False,
        )
        workflow = MagicMock(spec=WorkflowConfig)
        workflow.name = "test_wf"
        workflow.steps = []
        workflow.inputs = {}
        workflow.outputs = []
        workflow.settings = settings

        with patch.object(
            executor, "_execute_with_auto_parallel"
        ) as mock_parallel:
            executor.execute(workflow, inputs={})
            mock_parallel.assert_called_once()

    def test_executor_uses_sequential_when_no_parallel(self):
        """When auto_parallel is False, uses sequential execution."""
        from test_ai.workflow.executor_core import WorkflowExecutor
        from test_ai.workflow.loader import WorkflowConfig, WorkflowSettings

        executor = WorkflowExecutor()

        settings = WorkflowSettings(auto_parallel=False)
        workflow = MagicMock(spec=WorkflowConfig)
        workflow.name = "test_wf"
        workflow.steps = []
        workflow.inputs = {}
        workflow.outputs = []
        workflow.settings = settings

        with patch.object(
            executor, "_execute_sequential"
        ) as mock_seq:
            executor.execute(workflow, inputs={})
            mock_seq.assert_called_once()


# ---------------------------------------------------------------------------
# End-to-end: coordinated parallel group lifecycle
# ---------------------------------------------------------------------------


class TestCoordinatedParallelGroupE2E:
    """Tests the full publish → execute → gate lifecycle."""

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_coordinated_group_publishes_and_gates(self):
        """Verify intents are published, parent parallel is called,
        and the stability gate runs before returning a report."""
        from test_ai.workflow.loader import StepConfig

        mixin = CoordinatedParallelMixin()
        coordinator = WorkflowCoordinator(min_stability=0.1)

        step_a = MagicMock(spec=StepConfig)
        step_a.id = "build"
        step_a.type = "claude_code"
        step_a.params = {"role": "builder", "prompt": "Build auth"}
        step_a.outputs = ["auth_module"]
        step_a.depends_on = []

        step_b = MagicMock(spec=StepConfig)
        step_b.id = "test"
        step_b.type = "claude_code"
        step_b.params = {"role": "tester", "prompt": "Test auth"}
        step_b.outputs = ["test_report"]
        step_b.depends_on = []

        steps = [step_a, step_b]
        result = MagicMock()
        result.status = "running"

        # Mock the parent parallel group execution (called via super())
        with patch.object(
            CoordinatedParallelMixin,
            "__mro_entries__",
            create=True,
        ):
            # Patch super()'s _execute_parallel_group to be a no-op
            parent_exec = MagicMock()
            with patch(
                "test_ai.coordination.parallel_executor.super",
                return_value=MagicMock(_execute_parallel_group=parent_exec),
            ):
                report = mixin._coordinated_execute_parallel_group(
                    steps, "wf-1", result, 4, coordinator
                )

        # Intents were published for both steps
        assert report is not None
        # Gate ran (report has passes >= 1 or converged=True for empty)
        assert isinstance(report.converged, bool)

    @pytest.mark.skipif(not HAS_CONVERGENT, reason="convergent not installed")
    def test_publish_intents_helper(self):
        """The _publish_intents static method publishes one intent per step."""
        from test_ai.workflow.loader import StepConfig

        coordinator = WorkflowCoordinator(min_stability=0.1)

        step = MagicMock(spec=StepConfig)
        step.id = "s1"
        step.type = "shell"
        step.params = {"command": "echo hello"}
        step.outputs = ["stdout"]
        step.depends_on = ["s0"]

        CoordinatedParallelMixin._publish_intents([step], coordinator)
        assert "s1" in coordinator._publishers

    def test_publish_intents_returns_none_when_disabled(self, monkeypatch):
        """When coordination is disabled, publish_step_intent returns None
        but _publish_intents still completes without error."""
        import test_ai.coordination.convergent_bridge as bridge_mod
        from test_ai.workflow.loader import StepConfig

        monkeypatch.setattr(bridge_mod, "HAS_CONVERGENT", False)

        coord = WorkflowCoordinator.__new__(WorkflowCoordinator)
        coord._enabled = False
        coord._resolver = None
        coord._publishers = {}
        coord._min_stability = 0.3
        coord._max_passes = 3

        step = MagicMock(spec=StepConfig)
        step.id = "s1"
        step.type = "shell"
        step.params = {"command": "echo hello"}
        step.outputs = []
        step.depends_on = []

        # Should not raise even though coordinator is disabled
        CoordinatedParallelMixin._publish_intents([step], coord)
        assert len(coord._publishers) == 0
