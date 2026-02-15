"""Analytics Workflow Orchestration.

Provides modular pipeline components for data collection, analysis,
visualization, and reporting workflows.
"""

from .pipeline import AnalyticsPipeline, PipelineStage, PipelineResult
from .collectors import (
    DataCollector,
    JSONCollector,
    AggregateCollector,
    CollectedData,
    ExecutionMetricsCollector,
    HistoricalMetricsCollector,
    APIClientMetricsCollector,
    BudgetMetricsCollector,
)
from .analyzers import (
    DataAnalyzer,
    AnalysisResult,
    TrendAnalyzer,
    ThresholdAnalyzer,
    CompositeAnalyzer,
)
from .visualizers import ChartGenerator, DashboardBuilder
from .reporters import ReportGenerator, AlertGenerator

__all__ = [
    # Pipeline
    "AnalyticsPipeline",
    "PipelineStage",
    "PipelineResult",
    # Collectors
    "DataCollector",
    "CollectedData",
    "JSONCollector",
    "AggregateCollector",
    "ExecutionMetricsCollector",
    "HistoricalMetricsCollector",
    "APIClientMetricsCollector",
    "BudgetMetricsCollector",
    # Analyzers
    "DataAnalyzer",
    "AnalysisResult",
    "TrendAnalyzer",
    "ThresholdAnalyzer",
    "CompositeAnalyzer",
    # Visualizers
    "ChartGenerator",
    "DashboardBuilder",
    # Reporters
    "ReportGenerator",
    "AlertGenerator",
]
