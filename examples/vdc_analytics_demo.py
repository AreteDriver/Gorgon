#!/usr/bin/env python3
"""VDC Analytics Pipeline Demo.

Demonstrates the analytics orchestration pipeline using VDC metrics data.
Can run against real VDC databases or with synthetic test data.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# Add analytics module directly to path to avoid main test_ai package deps
analytics_path = Path(__file__).parent.parent / "src" / "test_ai" / "orchestrators"
sys.path.insert(0, str(analytics_path))

# Import directly from analytics modules (after path modification)
from analytics.pipeline import AnalyticsPipeline, PipelineStage  # noqa: E402
from analytics.collectors import VDCCollector, JSONCollector  # noqa: E402
from analytics.analyzers import OperationalAnalyzer  # noqa: E402
from analytics.visualizers import ChartGenerator, DashboardBuilder  # noqa: E402
from analytics.reporters import ReportGenerator, AlertGenerator  # noqa: E402


def create_synthetic_vdc_data() -> dict:
    """Create synthetic VDC operational data for demo."""
    return {
        "operational": {
            "vehicles_by_status": {
                "arrived": 45,
                "in_production": 23,
                "pending_delivery": 12,
                "delivered": 156,
            },
            "work_orders_by_status": {
                "pending": 34,
                "in_progress": 18,
                "complete": 142,
                "failed_qc": 3,
            },
        },
        "bottlenecks": [
            {
                "stage": "Installation",
                "severity_level": "critical",
                "avg_time_minutes": 95,
                "takt_time_minutes": 45,
                "vehicles_affected": 8,
            },
            {
                "stage": "FQA",
                "severity_level": "warning",
                "avg_time_minutes": 38,
                "takt_time_minutes": 30,
                "vehicles_affected": 5,
            },
        ],
        "day_shift": {
            "shift": "day",
            "percent_complete": 67,
            "hours_complete": 84,
            "hours_total": 126,
        },
        "night_shift": {
            "shift": "night",
            "percent_complete": 0,
            "hours_complete": 0,
            "hours_total": 118,
        },
        "app_performance": {
            "timing": {
                "page_load": {"avg_ms": 245, "max_ms": 1200, "count": 150},
                "db_query": {"avg_ms": 12, "max_ms": 89, "count": 890},
                "api_call": {"avg_ms": 340, "max_ms": 2100, "count": 45},
            },
            "counters": {
                "page_views": 523,
                "error_count": 2,
                "scan_events": 234,
            },
        },
    }


def demo_operational_pipeline():
    """Demo: Operational analysis pipeline."""
    print("\n" + "=" * 60)
    print("DEMO: VDC Operational Analysis Pipeline")
    print("=" * 60)

    # Create pipeline with synthetic data
    pipeline = AnalyticsPipeline("vdc_operations_demo", use_agents=False)

    collector = JSONCollector()
    analyzer = OperationalAnalyzer()
    chart_gen = ChartGenerator()
    reporter = ReportGenerator()

    pipeline.add_stage(
        PipelineStage.COLLECT,
        collector.collect,
        {"data": create_synthetic_vdc_data(), "source_name": "synthetic_vdc"},
    )
    pipeline.add_stage(PipelineStage.ANALYZE, analyzer.analyze)
    pipeline.add_stage(PipelineStage.VISUALIZE, chart_gen.generate)
    pipeline.add_stage(
        PipelineStage.REPORT,
        reporter.generate,
        {"title": "VDC Operations Report"},
    )

    # Execute
    result = pipeline.execute()

    print(f"\nPipeline Status: {result.status}")
    print(f"Duration: {sum(s.duration_ms for s in result.stages):.0f}ms")
    print(f"Stages Completed: {len([s for s in result.stages if s.status == 'success'])}/{len(result.stages)}")

    # Show stage results
    for stage in result.stages:
        print(f"\n--- Stage: {stage.stage.value} ({stage.status}) ---")
        if stage.output:
            if hasattr(stage.output, "to_context_string"):
                print(stage.output.to_context_string()[:500] + "...")
            elif hasattr(stage.output, "to_markdown"):
                print(stage.output.to_markdown()[:500] + "...")

    return result


def demo_alert_pipeline():
    """Demo: Alert generation pipeline."""
    print("\n" + "=" * 60)
    print("DEMO: VDC Alert Pipeline")
    print("=" * 60)

    pipeline = AnalyticsPipeline("vdc_alerts_demo", use_agents=False)

    collector = JSONCollector()
    analyzer = OperationalAnalyzer()
    alerter = AlertGenerator()

    pipeline.add_stage(
        PipelineStage.COLLECT,
        collector.collect,
        {"data": create_synthetic_vdc_data()},
    )
    pipeline.add_stage(PipelineStage.ANALYZE, analyzer.analyze)
    pipeline.add_stage(
        PipelineStage.ALERT,
        alerter.generate,
        {"min_severity": "warning", "source": "vdc_demo"},
    )

    result = pipeline.execute()

    print(f"\nPipeline Status: {result.status}")

    if result.final_output:
        alert_batch = result.final_output
        print(f"Alerts Generated: {len(alert_batch.alerts)}")
        print(f"Summary: {alert_batch.summary}")
        print("\nAlerts:")
        for alert in alert_batch.alerts:
            print(f"  [{alert.severity.upper()}] {alert.title}: {alert.message}")

    return result


def demo_dashboard_pipeline():
    """Demo: Dashboard generation pipeline."""
    print("\n" + "=" * 60)
    print("DEMO: VDC Dashboard Pipeline")
    print("=" * 60)

    pipeline = AnalyticsPipeline("vdc_dashboard_demo", use_agents=False)

    collector = JSONCollector()
    analyzer = OperationalAnalyzer()
    dashboard = DashboardBuilder()

    pipeline.add_stage(
        PipelineStage.COLLECT,
        collector.collect,
        {"data": create_synthetic_vdc_data()},
    )
    pipeline.add_stage(PipelineStage.ANALYZE, analyzer.analyze)
    pipeline.add_stage(
        PipelineStage.VISUALIZE,
        dashboard.build,
        {"title": "VDC Operations Dashboard", "layout": "vertical"},
    )

    result = pipeline.execute()

    print(f"\nPipeline Status: {result.status}")

    if result.final_output:
        viz_result = result.final_output
        print(f"Charts Generated: {len(viz_result.charts)}")
        if viz_result.dashboard:
            print(f"Dashboard: {viz_result.dashboard.title}")
            print(f"Layout: {viz_result.dashboard.layout}")

        print("\nGenerated Streamlit Code Preview:")
        print("-" * 40)
        print(viz_result.streamlit_code[:800])
        if len(viz_result.streamlit_code) > 800:
            print("...")

    return result


def demo_with_real_vdc_data():
    """Demo: Pipeline with real VDC metrics (if available)."""
    print("\n" + "=" * 60)
    print("DEMO: Real VDC Metrics Pipeline")
    print("=" * 60)

    # Check for VDC database
    vdc_db = Path("/home/arete/projects/vdc-portfolio/data/logistics.db")
    metrics_db = Path("/home/arete/projects/vdc-portfolio/data/metrics.db")

    if not vdc_db.exists():
        print(f"VDC database not found at {vdc_db}")
        print("Skipping real data demo.")
        return None

    print(f"Found VDC database: {vdc_db}")

    pipeline = AnalyticsPipeline("vdc_real_data", use_agents=False)

    collector = VDCCollector(
        logistics_db_path=str(vdc_db),
        metrics_db_path=str(metrics_db) if metrics_db.exists() else None,
    )
    analyzer = OperationalAnalyzer()
    reporter = ReportGenerator()

    pipeline.add_stage(PipelineStage.COLLECT, collector.collect)
    pipeline.add_stage(PipelineStage.ANALYZE, analyzer.analyze)
    pipeline.add_stage(PipelineStage.REPORT, reporter.generate)

    result = pipeline.execute()

    print(f"\nPipeline Status: {result.status}")
    if result.errors:
        print(f"Errors: {result.errors}")

    if result.final_output:
        print("\nReport Preview:")
        print("-" * 40)
        report = result.final_output
        print(report.to_markdown()[:1000])

    return result


def main():
    """Run all demos."""
    print("VDC Analytics Pipeline Demos")
    print("=" * 60)
    print(f"Started: {datetime.now().isoformat()}")

    # Run demos
    demo_operational_pipeline()
    demo_alert_pipeline()
    demo_dashboard_pipeline()
    demo_with_real_vdc_data()

    print("\n" + "=" * 60)
    print("All demos complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
