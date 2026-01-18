"""VDC Metrics Integration for Gorgon.

Reads operational metrics from VDC portfolio applications and
provides them to Gorgon analytics workflows.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class VDCMetricsSummary:
    """Summary of VDC operational metrics."""

    timestamp: datetime
    app_metrics: dict[str, Any]
    operational_metrics: dict[str, Any]
    performance_metrics: dict[str, Any]
    alerts: list[dict[str, Any]]


class VDCMetricsClient:
    """Client for reading VDC application metrics."""

    def __init__(
        self,
        metrics_db_path: str | None = None,
        logistics_db_path: str | None = None,
    ):
        """Initialize VDC metrics client.

        Args:
            metrics_db_path: Path to VDC metrics database (observability data)
            logistics_db_path: Path to VDC logistics database (operational data)
        """
        self.metrics_db_path = Path(
            metrics_db_path
            or os.environ.get(
                "VDC_METRICS_DB", "/home/arete/projects/vdc-Production/data/metrics.db"
            )
        )
        self.logistics_db_path = Path(
            logistics_db_path
            or os.environ.get(
                "VDC_LOGISTICS_DB", "/home/arete/projects/vdc-Production/logistics.db"
            )
        )

    def _get_connection(self, db_path: Path) -> sqlite3.Connection:
        """Get database connection."""
        if not db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # Application Performance Metrics
    # =========================================================================

    def get_app_performance(self, minutes: int = 60) -> dict[str, Any]:
        """Get application performance metrics.

        Returns timing metrics for page loads, DB queries, etc.
        """
        if not self.metrics_db_path.exists():
            return {
                "error": "Metrics database not found",
                "path": str(self.metrics_db_path),
            }

        conn = self._get_connection(self.metrics_db_path)
        try:
            # Get histogram metrics (timing data)
            cursor = conn.execute(
                """
                SELECT name, AVG(value) as avg_ms, MIN(value) as min_ms,
                       MAX(value) as max_ms, COUNT(*) as count
                FROM metrics
                WHERE metric_type = 'histogram'
                AND timestamp >= datetime('now', ? || ' minutes')
                GROUP BY name
                ORDER BY avg_ms DESC
                """,
                (-minutes,),
            )

            performance = {}
            for row in cursor.fetchall():
                performance[row["name"]] = {
                    "avg_ms": round(row["avg_ms"], 2),
                    "min_ms": round(row["min_ms"], 2),
                    "max_ms": round(row["max_ms"], 2),
                    "count": row["count"],
                }

            # Get counter metrics (call counts, errors)
            cursor = conn.execute(
                """
                SELECT name, labels, MAX(value) as total
                FROM metrics
                WHERE metric_type = 'counter'
                AND timestamp >= datetime('now', ? || ' minutes')
                GROUP BY name, labels
                """,
                (-minutes,),
            )

            counters = {}
            for row in cursor.fetchall():
                labels = json.loads(row["labels"]) if row["labels"] else {}
                key = f"{row['name']}:{labels.get('status', 'unknown')}"
                counters[key] = row["total"]

            return {
                "timing": performance,
                "counters": counters,
                "period_minutes": minutes,
            }
        finally:
            conn.close()

    # =========================================================================
    # Operational Metrics (from logistics.db)
    # =========================================================================

    def get_operational_summary(self) -> dict[str, Any]:
        """Get current VDC operational summary.

        Returns vehicle counts, stage distribution, bottlenecks, etc.
        """
        if not self.logistics_db_path.exists():
            return {
                "error": "Logistics database not found",
                "path": str(self.logistics_db_path),
            }

        conn = self._get_connection(self.logistics_db_path)
        try:
            summary = {}

            # Vehicle counts by status
            cursor = conn.execute(
                """
                SELECT status, COUNT(*) as count
                FROM vehicles
                GROUP BY status
                """
            )
            summary["vehicles_by_status"] = {
                row["status"]: row["count"] for row in cursor.fetchall()
            }

            # Vehicle counts by stage
            cursor = conn.execute(
                """
                SELECT ps.stage_name, COUNT(v.id) as count
                FROM vehicles v
                LEFT JOIN production_stages ps ON v.current_stage_id = ps.id
                WHERE v.status IN ('arrived', 'in_production')
                GROUP BY ps.stage_name
                ORDER BY ps.stage_order
                """
            )
            summary["vehicles_by_stage"] = {
                row["stage_name"] or "Unknown": row["count"]
                for row in cursor.fetchall()
            }

            # Work order status
            cursor = conn.execute(
                """
                SELECT status, COUNT(*) as count
                FROM work_orders
                GROUP BY status
                """
            )
            summary["work_orders_by_status"] = {
                row["status"]: row["count"] for row in cursor.fetchall()
            }

            # Today's movements
            cursor = conn.execute(
                """
                SELECT movement_type, COUNT(*) as count
                FROM vehicle_movements
                WHERE DATE(timestamp) = DATE('now')
                GROUP BY movement_type
                """
            )
            summary["todays_movements"] = {
                row["movement_type"]: row["count"] for row in cursor.fetchall()
            }

            # Calculate total labor hours
            cursor = conn.execute(
                """
                SELECT
                    SUM(estimated_labor_hours) as total_estimated,
                    SUM(CASE WHEN status = 'complete' THEN actual_hours ELSE 0 END) as completed
                FROM work_orders
                WHERE DATE(created_at) = DATE('now')
                """
            )
            row = cursor.fetchone()
            summary["labor_hours"] = {
                "estimated": row["total_estimated"] or 0,
                "completed": row["completed"] or 0,
            }

            return summary
        finally:
            conn.close()

    def get_bottlenecks(self) -> list[dict[str, Any]]:
        """Detect production bottlenecks.

        Returns stages with vehicles exceeding takt time.
        """
        if not self.logistics_db_path.exists():
            return []

        conn = self._get_connection(self.logistics_db_path)
        try:
            cursor = conn.execute(
                """
                SELECT
                    ps.stage_name,
                    ps.takt_time_minutes,
                    COUNT(v.id) as vehicle_count,
                    AVG(
                        CAST((julianday('now') - julianday(v.stage_entry_time)) * 24 * 60 AS INTEGER)
                    ) as avg_time_minutes
                FROM vehicles v
                JOIN production_stages ps ON v.current_stage_id = ps.id
                WHERE v.status = 'in_production'
                AND v.stage_entry_time IS NOT NULL
                GROUP BY ps.id, ps.stage_name, ps.takt_time_minutes
                HAVING avg_time_minutes > ps.takt_time_minutes
                ORDER BY (avg_time_minutes / ps.takt_time_minutes) DESC
                """
            )

            bottlenecks = []
            for row in cursor.fetchall():
                severity = row["avg_time_minutes"] / row["takt_time_minutes"]
                bottlenecks.append(
                    {
                        "stage": row["stage_name"],
                        "takt_time_minutes": row["takt_time_minutes"],
                        "avg_time_minutes": round(row["avg_time_minutes"], 1),
                        "vehicle_count": row["vehicle_count"],
                        "severity": round(severity, 2),
                        "severity_level": "critical"
                        if severity > 2
                        else "warning"
                        if severity > 1.5
                        else "minor",
                    }
                )

            return bottlenecks
        finally:
            conn.close()

    def get_shift_progress(self, shift: str = "day") -> dict[str, Any]:
        """Get current shift progress.

        Args:
            shift: 'day' or 'night'
        """
        if not self.logistics_db_path.exists():
            return {"error": "Logistics database not found"}

        conn = self._get_connection(self.logistics_db_path)
        try:
            cursor = conn.execute(
                """
                SELECT
                    SUM(wo.estimated_hours) as total_hours,
                    SUM(CASE WHEN wo.status = 'complete' THEN wo.actual_hours ELSE 0 END) as completed_hours,
                    COUNT(DISTINCT wo.vehicle_id) as total_vehicles,
                    COUNT(DISTINCT CASE WHEN wo.status = 'complete' THEN wo.vehicle_id END) as completed_vehicles
                FROM work_orders wo
                JOIN vehicles v ON wo.vehicle_id = v.id
                WHERE v.shift_assigned = ?
                AND DATE(wo.created_at) = DATE('now')
                """,
                (shift,),
            )

            row = cursor.fetchone()
            total_hours = row["total_hours"] or 0
            completed_hours = row["completed_hours"] or 0

            return {
                "shift": shift,
                "total_labor_hours": round(total_hours, 1),
                "completed_labor_hours": round(completed_hours, 1),
                "percent_complete": round(
                    (completed_hours / total_hours * 100) if total_hours > 0 else 0, 1
                ),
                "total_vehicles": row["total_vehicles"] or 0,
                "completed_vehicles": row["completed_vehicles"] or 0,
            }
        finally:
            conn.close()

    # =========================================================================
    # Aggregated Summary for Gorgon Workflows
    # =========================================================================

    def get_full_summary(self, performance_minutes: int = 60) -> VDCMetricsSummary:
        """Get complete metrics summary for Gorgon analysis.

        Returns all metrics in a format suitable for AI analysis.
        """
        return VDCMetricsSummary(
            timestamp=datetime.now(timezone.utc),
            app_metrics=self.get_app_performance(performance_minutes),
            operational_metrics=self.get_operational_summary(),
            performance_metrics={
                "bottlenecks": self.get_bottlenecks(),
                "day_shift": self.get_shift_progress("day"),
                "night_shift": self.get_shift_progress("night"),
            },
            alerts=self._generate_alerts(),
        )

    def _generate_alerts(self) -> list[dict[str, Any]]:
        """Generate alerts based on current metrics."""
        alerts = []

        # Check bottlenecks
        bottlenecks = self.get_bottlenecks()
        for bn in bottlenecks:
            if bn["severity_level"] == "critical":
                alerts.append(
                    {
                        "type": "bottleneck",
                        "severity": "critical",
                        "message": f"Critical bottleneck at {bn['stage']}: {bn['avg_time_minutes']}min avg vs {bn['takt_time_minutes']}min takt",
                        "stage": bn["stage"],
                    }
                )

        # Check shift progress
        for shift in ["day", "night"]:
            progress = self.get_shift_progress(shift)
            if isinstance(progress, dict) and "percent_complete" in progress:
                # Alert if behind schedule (assuming linear progress)
                # This is a simplified check
                if (
                    progress["percent_complete"] < 50
                    and progress["total_labor_hours"] > 0
                ):
                    alerts.append(
                        {
                            "type": "shift_progress",
                            "severity": "warning",
                            "message": f"{shift.title()} shift at {progress['percent_complete']}% complete",
                            "shift": shift,
                        }
                    )

        return alerts

    def format_for_analysis(self) -> str:
        """Format metrics as text for AI analysis.

        Returns a structured text summary suitable for Claude agents.
        """
        summary = self.get_full_summary()

        lines = [
            "# VDC Operations Metrics Summary",
            f"Generated: {summary.timestamp.isoformat()}",
            "",
            "## Operational Status",
        ]

        # Vehicle counts
        ops = summary.operational_metrics
        if "vehicles_by_status" in ops:
            lines.append("\n### Vehicles by Status")
            for status, count in ops["vehicles_by_status"].items():
                lines.append(f"- {status}: {count}")

        if "vehicles_by_stage" in ops:
            lines.append("\n### Vehicles by Stage")
            for stage, count in ops["vehicles_by_stage"].items():
                lines.append(f"- {stage}: {count}")

        # Bottlenecks
        perf = summary.performance_metrics
        if perf.get("bottlenecks"):
            lines.append("\n## Bottlenecks Detected")
            for bn in perf["bottlenecks"]:
                lines.append(
                    f"- **{bn['stage']}** [{bn['severity_level'].upper()}]: "
                    f"{bn['avg_time_minutes']}min avg vs {bn['takt_time_minutes']}min takt "
                    f"({bn['vehicle_count']} vehicles)"
                )

        # Shift progress
        for shift_key in ["day_shift", "night_shift"]:
            shift_data = perf.get(shift_key, {})
            if shift_data and "percent_complete" in shift_data:
                lines.append(f"\n### {shift_data['shift'].title()} Shift Progress")
                lines.append(
                    f"- Completed: {shift_data['completed_labor_hours']}/{shift_data['total_labor_hours']} hours ({shift_data['percent_complete']}%)"
                )
                lines.append(
                    f"- Vehicles: {shift_data['completed_vehicles']}/{shift_data['total_vehicles']}"
                )

        # Alerts
        if summary.alerts:
            lines.append("\n## Active Alerts")
            for alert in summary.alerts:
                lines.append(f"- [{alert['severity'].upper()}] {alert['message']}")

        # App performance
        app = summary.app_metrics
        if app.get("timing"):
            lines.append("\n## Application Performance (Last Hour)")
            for name, timing in list(app["timing"].items())[:5]:  # Top 5 slowest
                lines.append(
                    f"- {name}: avg {timing['avg_ms']}ms (min: {timing['min_ms']}ms, max: {timing['max_ms']}ms)"
                )

        return "\n".join(lines)


# Convenience function for Gorgon workflows
def get_vdc_metrics_text() -> str:
    """Get VDC metrics formatted for AI analysis.

    This is the primary function called by Gorgon workflows.
    """
    client = VDCMetricsClient()
    return client.format_for_analysis()


def get_vdc_metrics_json() -> dict:
    """Get VDC metrics as JSON for programmatic access."""
    client = VDCMetricsClient()
    summary = client.get_full_summary()
    return {
        "timestamp": summary.timestamp.isoformat(),
        "app_metrics": summary.app_metrics,
        "operational_metrics": summary.operational_metrics,
        "performance_metrics": summary.performance_metrics,
        "alerts": summary.alerts,
    }
