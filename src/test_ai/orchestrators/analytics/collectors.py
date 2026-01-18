"""Data Collectors for Analytics Pipelines.

Provides modular data collection components that can be used in analytics pipelines.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class CollectedData:
    """Container for collected data."""

    source: str
    collected_at: datetime
    data: dict[str, Any]
    metadata: dict[str, Any]

    def to_context_string(self) -> str:
        """Convert to string format for AI agent context."""
        lines = [
            f"# Data Collection: {self.source}",
            f"Collected: {self.collected_at.isoformat()}",
            "",
        ]

        for key, value in self.data.items():
            lines.append(f"## {key}")
            if isinstance(value, dict):
                for k, v in value.items():
                    lines.append(f"- {k}: {v}")
            elif isinstance(value, list):
                for item in value[:10]:  # Limit to 10 items
                    lines.append(f"- {item}")
                if len(value) > 10:
                    lines.append(f"- ... and {len(value) - 10} more")
            else:
                lines.append(str(value))
            lines.append("")

        return "\n".join(lines)


class DataCollector(ABC):
    """Abstract base class for data collectors."""

    @abstractmethod
    def collect(self, context: Any, config: dict) -> CollectedData:
        """Collect data from the source.

        Args:
            context: Previous stage output or initial context
            config: Collector configuration

        Returns:
            CollectedData with collected information
        """
        pass


class VDCCollector(DataCollector):
    """Collector for VDC operational data."""

    def __init__(self, metrics_db_path: str = None, logistics_db_path: str = None):
        from test_ai.integrations.vdc_metrics import VDCMetricsClient

        self.client = VDCMetricsClient(
            metrics_db_path=metrics_db_path,
            logistics_db_path=logistics_db_path,
        )

    def collect(self, context: Any, config: dict) -> CollectedData:
        """Collect VDC operational metrics.

        Config options:
            include_performance: bool - Include app performance metrics
            include_bottlenecks: bool - Include bottleneck detection
            include_shifts: bool - Include shift progress data
            performance_minutes: int - Time window for performance metrics
        """
        include_performance = config.get("include_performance", True)
        include_bottlenecks = config.get("include_bottlenecks", True)
        include_shifts = config.get("include_shifts", True)
        performance_minutes = config.get("performance_minutes", 60)

        data = {}

        # Operational summary
        data["operational"] = self.client.get_operational_summary()

        # App performance metrics
        if include_performance:
            data["app_performance"] = self.client.get_app_performance(
                performance_minutes
            )

        # Bottleneck detection
        if include_bottlenecks:
            data["bottlenecks"] = self.client.get_bottlenecks()

        # Shift progress
        if include_shifts:
            data["day_shift"] = self.client.get_shift_progress("day")
            data["night_shift"] = self.client.get_shift_progress("night")

        return CollectedData(
            source="vdc_operations",
            collected_at=datetime.now(timezone.utc),
            data=data,
            metadata={
                "include_performance": include_performance,
                "include_bottlenecks": include_bottlenecks,
                "include_shifts": include_shifts,
            },
        )


class MetricsCollector(DataCollector):
    """Collector for application metrics from metrics database."""

    def __init__(self, metrics_db_path: str = None):
        from test_ai.integrations.vdc_metrics import VDCMetricsClient

        self.client = VDCMetricsClient(metrics_db_path=metrics_db_path)

    def collect(self, context: Any, config: dict) -> CollectedData:
        """Collect application metrics.

        Config options:
            minutes: int - Time window for metrics (default: 60)
            app_filter: str - Filter by app name (optional)
        """
        minutes = config.get("minutes", 60)

        data = self.client.get_app_performance(minutes)

        return CollectedData(
            source="app_metrics",
            collected_at=datetime.now(timezone.utc),
            data={"metrics": data},
            metadata={"minutes": minutes},
        )


class JSONCollector(DataCollector):
    """Collector that accepts JSON data directly (for testing/manual input)."""

    def collect(self, context: Any, config: dict) -> CollectedData:
        """Pass through JSON data.

        Config options:
            data: dict - The data to pass through
            source_name: str - Name for the data source
        """
        data = config.get("data", context if isinstance(context, dict) else {})
        source_name = config.get("source_name", "json_input")

        return CollectedData(
            source=source_name,
            collected_at=datetime.now(timezone.utc),
            data=data,
            metadata={"type": "json_passthrough"},
        )


class AggregateCollector(DataCollector):
    """Collector that aggregates data from multiple collectors."""

    def __init__(self, collectors: list[DataCollector]):
        self.collectors = collectors

    def collect(self, context: Any, config: dict) -> CollectedData:
        """Collect and aggregate data from all child collectors.

        Config options:
            collector_configs: dict[int, dict] - Config for each collector by index
        """
        collector_configs = config.get("collector_configs", {})

        aggregated_data = {}

        for i, collector in enumerate(self.collectors):
            collector_config = collector_configs.get(i, {})
            result = collector.collect(context, collector_config)
            aggregated_data[result.source] = result.data

        return CollectedData(
            source="aggregate",
            collected_at=datetime.now(timezone.utc),
            data=aggregated_data,
            metadata={"collector_count": len(self.collectors)},
        )
