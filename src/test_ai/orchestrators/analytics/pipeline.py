"""Analytics Pipeline Orchestration.

Provides a flexible pipeline framework for chaining data collection,
analysis, visualization, and reporting stages.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from test_ai.api_clients import ClaudeCodeClient


class PipelineStage(str, Enum):
    """Pipeline stage types."""

    COLLECT = "collect"
    CLEAN = "clean"
    ANALYZE = "analyze"
    VISUALIZE = "visualize"
    REPORT = "report"
    ALERT = "alert"


@dataclass
class StageResult:
    """Result from a pipeline stage."""

    stage: PipelineStage
    status: str  # "success", "failed", "skipped"
    output: Any
    duration_ms: float
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Complete pipeline execution result."""

    pipeline_id: str
    status: str  # "completed", "failed", "partial"
    started_at: datetime
    completed_at: Optional[datetime] = None
    stages: list[StageResult] = field(default_factory=list)
    final_output: Any = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "pipeline_id": self.pipeline_id,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "stages": [
                {
                    "stage": s.stage.value,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "error": s.error,
                }
                for s in self.stages
            ],
            "errors": self.errors,
        }


class AnalyticsPipeline:
    """Orchestrates analytics workflows through modular stages.

    Example usage:
        pipeline = AnalyticsPipeline("vdc_daily_analysis")
        pipeline.add_stage(PipelineStage.COLLECT, vdc_collector.collect)
        pipeline.add_stage(PipelineStage.ANALYZE, operational_analyzer.analyze)
        pipeline.add_stage(PipelineStage.VISUALIZE, chart_generator.generate)
        pipeline.add_stage(PipelineStage.REPORT, report_generator.generate)

        result = pipeline.execute({"date": "2025-01-18"})
    """

    def __init__(self, pipeline_id: str, use_agents: bool = True):
        """Initialize analytics pipeline.

        Args:
            pipeline_id: Unique identifier for this pipeline
            use_agents: Whether to use Claude agents for AI-powered stages
        """
        self.pipeline_id = pipeline_id
        self.use_agents = use_agents
        self._stages: list[tuple[PipelineStage, Callable, dict]] = []
        self._claude_client = None
        if use_agents:
            from test_ai.api_clients import ClaudeCodeClient
            self._claude_client = ClaudeCodeClient()

    def add_stage(
        self,
        stage_type: PipelineStage,
        handler: Callable[[Any, dict], Any],
        config: dict = None,
    ) -> "AnalyticsPipeline":
        """Add a stage to the pipeline.

        Args:
            stage_type: Type of pipeline stage
            handler: Function to execute for this stage
            config: Optional configuration for the stage

        Returns:
            Self for method chaining
        """
        self._stages.append((stage_type, handler, config or {}))
        return self

    def add_agent_stage(
        self,
        stage_type: PipelineStage,
        agent_role: str,
        task_template: str,
        config: dict = None,
    ) -> "AnalyticsPipeline":
        """Add an AI agent-powered stage.

        Args:
            stage_type: Type of pipeline stage
            agent_role: Role for the Claude agent (e.g., "analyst", "visualizer")
            task_template: Task template with {{context}} placeholder
            config: Optional configuration

        Returns:
            Self for method chaining
        """
        if not self._claude_client:
            raise ValueError("Pipeline not configured for agent usage")

        def agent_handler(context: Any, cfg: dict) -> Any:
            task = task_template.replace("{{context}}", str(context))
            result = self._claude_client.execute_agent(
                role=agent_role,
                task=task,
                context=str(context),
            )
            return result.get("output", result)

        self._stages.append((stage_type, agent_handler, config or {}))
        return self

    def execute(self, initial_context: dict = None) -> PipelineResult:
        """Execute the pipeline.

        Args:
            initial_context: Initial context/parameters for the pipeline

        Returns:
            PipelineResult with all stage outputs
        """
        import time

        result = PipelineResult(
            pipeline_id=self.pipeline_id,
            status="running",
            started_at=datetime.utcnow(),
        )

        context = initial_context or {}
        current_output = context

        for stage_type, handler, config in self._stages:
            stage_start = time.time()

            try:
                # Merge config into context
                stage_context = {**context, **config}

                # Execute stage
                output = handler(current_output, stage_context)

                duration_ms = (time.time() - stage_start) * 1000

                stage_result = StageResult(
                    stage=stage_type,
                    status="success",
                    output=output,
                    duration_ms=duration_ms,
                    metadata={"config": config},
                )

                result.stages.append(stage_result)
                current_output = output

                # Update context with stage output
                context[f"{stage_type.value}_output"] = output

            except Exception as e:
                duration_ms = (time.time() - stage_start) * 1000

                stage_result = StageResult(
                    stage=stage_type,
                    status="failed",
                    output=None,
                    duration_ms=duration_ms,
                    error=str(e),
                )

                result.stages.append(stage_result)
                result.errors.append(f"Stage {stage_type.value} failed: {e}")
                result.status = "failed"
                break

        if result.status != "failed":
            result.status = "completed"
            result.final_output = current_output

        result.completed_at = datetime.utcnow()
        return result


class PipelineBuilder:
    """Fluent builder for creating common pipeline configurations."""

    @staticmethod
    def vdc_operations_pipeline() -> AnalyticsPipeline:
        """Create a pre-configured VDC operations analysis pipeline."""
        from .collectors import VDCCollector
        from .analyzers import OperationalAnalyzer
        from .reporters import ReportGenerator

        pipeline = AnalyticsPipeline("vdc_operations")

        collector = VDCCollector()
        analyzer = OperationalAnalyzer()
        reporter = ReportGenerator()

        return (
            pipeline
            .add_stage(PipelineStage.COLLECT, collector.collect)
            .add_stage(PipelineStage.ANALYZE, analyzer.analyze)
            .add_agent_stage(
                PipelineStage.VISUALIZE,
                "visualizer",
                "Create visualization recommendations for VDC operational data:\n\n{{context}}",
            )
            .add_stage(PipelineStage.REPORT, reporter.generate)
        )

    @staticmethod
    def metrics_trend_pipeline() -> AnalyticsPipeline:
        """Create a pipeline for analyzing metrics trends."""
        from .collectors import MetricsCollector
        from .analyzers import TrendAnalyzer

        pipeline = AnalyticsPipeline("metrics_trends")

        collector = MetricsCollector()
        analyzer = TrendAnalyzer()

        return (
            pipeline
            .add_stage(PipelineStage.COLLECT, collector.collect)
            .add_stage(PipelineStage.ANALYZE, analyzer.analyze)
            .add_agent_stage(
                PipelineStage.REPORT,
                "reporter",
                "Generate trend analysis report:\n\n{{context}}",
            )
        )

    @staticmethod
    def alert_pipeline() -> AnalyticsPipeline:
        """Create a pipeline for generating operational alerts."""
        from .collectors import VDCCollector
        from .analyzers import OperationalAnalyzer
        from .reporters import AlertGenerator

        pipeline = AnalyticsPipeline("alerts")

        collector = VDCCollector()
        analyzer = OperationalAnalyzer()
        alerter = AlertGenerator()

        return (
            pipeline
            .add_stage(PipelineStage.COLLECT, collector.collect)
            .add_stage(PipelineStage.ANALYZE, analyzer.analyze)
            .add_stage(PipelineStage.ALERT, alerter.generate)
        )
