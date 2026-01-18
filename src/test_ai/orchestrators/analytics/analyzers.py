"""Data Analyzers for Analytics Pipelines.

Provides modular analysis components for processing collected data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AnalysisResult:
    """Container for analysis results."""

    analyzer: str
    analyzed_at: datetime
    findings: list[dict[str, Any]]
    metrics: dict[str, Any]
    recommendations: list[str]
    severity: str  # "info", "warning", "critical"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_context_string(self) -> str:
        """Convert to string format for AI agent context."""
        lines = [
            f"# Analysis Results: {self.analyzer}",
            f"Analyzed: {self.analyzed_at.isoformat()}",
            f"Overall Severity: {self.severity.upper()}",
            "",
            "## Key Findings",
        ]

        for finding in self.findings:
            severity = finding.get("severity", "info")
            message = finding.get("message", "")
            lines.append(f"- [{severity.upper()}] {message}")

        lines.append("")
        lines.append("## Metrics")
        for key, value in self.metrics.items():
            lines.append(f"- {key}: {value}")

        if self.recommendations:
            lines.append("")
            lines.append("## Recommendations")
            for rec in self.recommendations:
                lines.append(f"- {rec}")

        return "\n".join(lines)


class DataAnalyzer(ABC):
    """Abstract base class for data analyzers."""

    @abstractmethod
    def analyze(self, data: Any, config: dict) -> AnalysisResult:
        """Analyze the collected data.

        Args:
            data: CollectedData or previous stage output
            config: Analyzer configuration

        Returns:
            AnalysisResult with findings and recommendations
        """
        pass


class OperationalAnalyzer(DataAnalyzer):
    """Analyzer for VDC operational data."""

    def analyze(self, data: Any, config: dict) -> AnalysisResult:
        """Analyze VDC operational metrics.

        Config options:
            takt_threshold: float - Multiplier for takt time alerts (default: 1.5)
            shift_warning_pct: int - Shift progress warning threshold (default: 40)
        """
        _takt_threshold = config.get("takt_threshold", 1.5)  # noqa: F841
        shift_warning_pct = config.get("shift_warning_pct", 40)

        findings = []
        metrics = {}
        recommendations = []
        max_severity = "info"

        # Handle different input types
        if hasattr(data, "data"):
            source_data = data.data
        elif isinstance(data, dict):
            source_data = data
        else:
            source_data = {}

        # Analyze bottlenecks
        bottlenecks = source_data.get("bottlenecks", [])
        if bottlenecks:
            metrics["bottleneck_count"] = len(bottlenecks)

            for bn in bottlenecks:
                severity = bn.get("severity_level", "minor")
                stage = bn.get("stage", "unknown")
                avg_time = bn.get("avg_time_minutes", 0)
                takt_time = bn.get("takt_time_minutes", 1)

                if severity == "critical":
                    max_severity = "critical"
                    findings.append(
                        {
                            "severity": "critical",
                            "category": "bottleneck",
                            "message": f"Critical bottleneck at {stage}: {avg_time:.0f}min avg vs {takt_time}min takt",
                            "data": bn,
                        }
                    )
                    recommendations.append(
                        f"URGENT: Add resources to {stage} or investigate process issues"
                    )
                elif severity == "warning":
                    if max_severity != "critical":
                        max_severity = "warning"
                    findings.append(
                        {
                            "severity": "warning",
                            "category": "bottleneck",
                            "message": f"Bottleneck forming at {stage}: {avg_time:.0f}min avg vs {takt_time}min takt",
                            "data": bn,
                        }
                    )

        # Analyze shift progress
        for shift_key in ["day_shift", "night_shift"]:
            shift_data = source_data.get(shift_key, {})
            if shift_data and isinstance(shift_data, dict):
                pct = shift_data.get("percent_complete", 0)
                shift_name = shift_data.get("shift", shift_key)

                metrics[f"{shift_name}_progress"] = pct

                if pct < shift_warning_pct:
                    if max_severity == "info":
                        max_severity = "warning"
                    findings.append(
                        {
                            "severity": "warning",
                            "category": "shift_progress",
                            "message": f"{shift_name.title()} shift at {pct}% - below target",
                            "data": shift_data,
                        }
                    )
                    recommendations.append(
                        f"Review {shift_name} shift resource allocation"
                    )

        # Analyze operational summary
        ops = source_data.get("operational", {})
        if ops:
            vehicles_by_status = ops.get("vehicles_by_status", {})
            total_vehicles = sum(vehicles_by_status.values())
            metrics["total_vehicles"] = total_vehicles

            in_production = vehicles_by_status.get("in_production", 0)
            metrics["vehicles_in_production"] = in_production

            # Check for work order issues
            wo_status = ops.get("work_orders_by_status", {})
            failed_qc = wo_status.get("failed_qc", 0)
            if failed_qc > 0:
                findings.append(
                    {
                        "severity": "warning",
                        "category": "quality",
                        "message": f"{failed_qc} work orders failed QC",
                        "data": {"failed_qc_count": failed_qc},
                    }
                )
                recommendations.append("Review QC failures and identify root causes")

        # Add general recommendations based on findings
        if not findings:
            findings.append(
                {
                    "severity": "info",
                    "category": "status",
                    "message": "Operations running normally",
                }
            )

        return AnalysisResult(
            analyzer="operational",
            analyzed_at=datetime.now(timezone.utc),
            findings=findings,
            metrics=metrics,
            recommendations=recommendations,
            severity=max_severity,
        )


class TrendAnalyzer(DataAnalyzer):
    """Analyzer for identifying trends in metrics data."""

    def analyze(self, data: Any, config: dict) -> AnalysisResult:
        """Analyze metrics for trends.

        Config options:
            trend_window: int - Number of data points to consider (default: 10)
            change_threshold: float - Percent change to flag as significant (default: 0.2)
        """
        _change_threshold = config.get("change_threshold", 0.2)  # noqa: F841

        findings = []
        metrics = {}
        recommendations = []
        max_severity = "info"

        # Handle different input types
        if hasattr(data, "data"):
            source_data = data.data
        elif isinstance(data, dict):
            source_data = data
        else:
            source_data = {}

        # Analyze timing metrics for performance trends
        app_metrics = source_data.get("metrics", source_data.get("app_performance", {}))

        if isinstance(app_metrics, dict):
            timing = app_metrics.get("timing", {})

            for metric_name, timing_data in timing.items():
                if isinstance(timing_data, dict):
                    avg_ms = timing_data.get("avg_ms", 0)
                    max_ms = timing_data.get("max_ms", 0)
                    count = timing_data.get("count", 0)

                    metrics[f"{metric_name}_avg"] = avg_ms
                    metrics[f"{metric_name}_count"] = count

                    # Flag slow operations
                    if avg_ms > 1000:  # Over 1 second
                        if max_severity == "info":
                            max_severity = "warning"
                        findings.append(
                            {
                                "severity": "warning",
                                "category": "performance",
                                "message": f"Slow operation: {metric_name} averaging {avg_ms:.0f}ms",
                                "data": timing_data,
                            }
                        )
                        recommendations.append(
                            f"Investigate performance of {metric_name}"
                        )

                    # Flag high variance
                    if max_ms > avg_ms * 3 and count > 5:
                        findings.append(
                            {
                                "severity": "info",
                                "category": "variance",
                                "message": f"High variance in {metric_name}: max {max_ms:.0f}ms vs avg {avg_ms:.0f}ms",
                            }
                        )

            # Analyze counters for error trends
            counters = app_metrics.get("counters", {})
            for counter_name, value in counters.items():
                if "error" in counter_name.lower():
                    if value > 0:
                        findings.append(
                            {
                                "severity": "warning",
                                "category": "errors",
                                "message": f"Error counter {counter_name}: {value}",
                            }
                        )
                        if max_severity == "info":
                            max_severity = "warning"

        if not findings:
            findings.append(
                {
                    "severity": "info",
                    "category": "trends",
                    "message": "No significant trends detected",
                }
            )

        return AnalysisResult(
            analyzer="trends",
            analyzed_at=datetime.now(timezone.utc),
            findings=findings,
            metrics=metrics,
            recommendations=recommendations,
            severity=max_severity,
        )


class CompositeAnalyzer(DataAnalyzer):
    """Analyzer that combines results from multiple analyzers."""

    def __init__(self, analyzers: list[DataAnalyzer]):
        self.analyzers = analyzers

    def analyze(self, data: Any, config: dict) -> AnalysisResult:
        """Run all analyzers and combine results.

        Config options:
            analyzer_configs: dict[int, dict] - Config for each analyzer by index
        """
        analyzer_configs = config.get("analyzer_configs", {})

        all_findings = []
        all_metrics = {}
        all_recommendations = []
        max_severity = "info"

        severity_order = {"info": 0, "warning": 1, "critical": 2}

        for i, analyzer in enumerate(self.analyzers):
            analyzer_config = analyzer_configs.get(i, {})
            result = analyzer.analyze(data, analyzer_config)

            all_findings.extend(result.findings)
            all_metrics.update(result.metrics)
            all_recommendations.extend(result.recommendations)

            if severity_order.get(result.severity, 0) > severity_order.get(
                max_severity, 0
            ):
                max_severity = result.severity

        # Deduplicate recommendations
        unique_recommendations = list(dict.fromkeys(all_recommendations))

        return AnalysisResult(
            analyzer="composite",
            analyzed_at=datetime.now(timezone.utc),
            findings=all_findings,
            metrics=all_metrics,
            recommendations=unique_recommendations,
            severity=max_severity,
            metadata={"analyzer_count": len(self.analyzers)},
        )
