"""Monitoring and Metrics Dashboard Pages for Gorgon.

Provides real-time monitoring UI for orchestrator status,
agent coordination visualization, and metrics dashboards.
"""

from __future__ import annotations

import time
from datetime import datetime

import streamlit as st

# Import monitoring components - lazy load to avoid dep issues
def get_tracker():
    from test_ai.monitoring import get_tracker as _get_tracker
    return _get_tracker()


def get_agent_tracker():
    from test_ai.monitoring.tracker import AgentTracker
    if "agent_tracker" not in st.session_state:
        st.session_state.agent_tracker = AgentTracker()
    return st.session_state.agent_tracker


def render_monitoring_page():
    """Render real-time monitoring page."""
    st.title("Real-Time Monitoring")

    # Auto-refresh toggle
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
    with col2:
        auto_refresh = st.toggle("Auto-refresh", value=True)

    if auto_refresh:
        time.sleep(0.1)  # Small delay for smoother updates
        st.rerun()

    try:
        tracker = get_tracker()
        data = tracker.get_dashboard_data()
    except Exception as e:
        st.warning(f"Monitoring data not available: {e}")
        data = {
            "summary": {
                "active_workflows": 0,
                "total_executions": 0,
                "success_rate": 0,
                "avg_duration_ms": 0,
            },
            "active_workflows": [],
            "recent_executions": [],
        }

    # Summary metrics
    summary = data["summary"]
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Active Workflows",
            summary.get("active_workflows", 0),
            delta=None,
        )
    with col2:
        st.metric(
            "Total Executions",
            summary.get("total_executions", 0),
        )
    with col3:
        success_rate = summary.get("success_rate", 0)
        st.metric(
            "Success Rate",
            f"{success_rate:.1f}%",
            delta="Good" if success_rate >= 90 else ("Warning" if success_rate >= 70 else "Critical"),
            delta_color="normal" if success_rate >= 90 else ("off" if success_rate >= 70 else "inverse"),
        )
    with col4:
        avg_duration = summary.get("avg_duration_ms", 0)
        st.metric(
            "Avg Duration",
            f"{avg_duration:.0f}ms" if avg_duration < 1000 else f"{avg_duration/1000:.1f}s",
        )

    st.divider()

    # Active workflows
    st.subheader("Active Workflows")
    active = data.get("active_workflows", [])

    if active:
        for wf in active:
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.markdown(f"**{wf['workflow_name']}**")
                    st.caption(f"ID: {wf['execution_id']}")
                with col2:
                    progress = (
                        wf["completed_steps"] / wf["total_steps"]
                        if wf["total_steps"] > 0
                        else 0
                    )
                    st.progress(progress, f"{wf['completed_steps']}/{wf['total_steps']} steps")
                with col3:
                    st.markdown(f"Status: **{wf['status']}**")
                st.divider()
    else:
        st.info("No active workflows")

    # Recent executions
    st.subheader("Recent Executions")
    recent = data.get("recent_executions", [])

    if recent:
        for execution in recent[:10]:
            with st.expander(
                f"{'✅' if execution['status'] == 'completed' else '❌'} "
                f"{execution['workflow_name']} - {execution['execution_id'][:16]}..."
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Status:** {execution['status']}")
                    st.write(f"**Duration:** {execution['duration_ms']:.0f}ms")
                    st.write(f"**Steps:** {execution['completed_steps']}/{execution['total_steps']}")
                with col2:
                    st.write(f"**Started:** {execution['started_at']}")
                    st.write(f"**Completed:** {execution.get('completed_at', 'N/A')}")
                    st.write(f"**Tokens:** {execution.get('total_tokens', 0)}")

                if execution.get("error"):
                    st.error(f"Error: {execution['error']}")

                # Show steps
                if execution.get("steps"):
                    st.markdown("**Steps:**")
                    for step in execution["steps"]:
                        step_status = "✅" if step["status"] == "success" else "❌"
                        st.text(
                            f"  {step_status} {step['step_id']} ({step['step_type']}:{step['action']}) "
                            f"- {step['duration_ms']:.0f}ms"
                        )
    else:
        st.info("No recent executions")


def render_agents_page():
    """Render agent coordination visualization page."""
    st.title("Agent Coordination")

    agent_tracker = get_agent_tracker()

    # Summary
    summary = agent_tracker.get_agent_summary()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Active Agents", summary["active_count"])
    with col2:
        st.metric("Recent Completions", summary["recent_count"])
    with col3:
        roles_str = ", ".join(f"{k}: {v}" for k, v in summary.get("by_role", {}).items())
        st.metric("By Role", roles_str or "None")

    st.divider()

    # Active agents visualization
    st.subheader("Active Agents")

    active_agents = agent_tracker.get_active_agents()

    if active_agents:
        # Create a visual grid for agents
        cols = st.columns(min(len(active_agents), 4))
        for i, agent in enumerate(active_agents):
            with cols[i % 4]:
                st.markdown(
                    f"""
                    <div style="
                        border: 2px solid #00d4ff;
                        border-radius: 10px;
                        padding: 15px;
                        margin: 5px;
                        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                    ">
                        <h4 style="color: #00d4ff; margin: 0;">🤖 {agent['role'].title()}</h4>
                        <p style="color: #888; font-size: 12px; margin: 5px 0;">
                            ID: {agent['agent_id'][:12]}...
                        </p>
                        <p style="color: #4caf50; font-size: 14px;">
                            ● {agent['status'].upper()}
                        </p>
                        <p style="color: #888; font-size: 11px;">
                            Tasks: {agent.get('tasks_completed', 0)}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("No active agents")

        # Demo button to simulate agents
        if st.button("Simulate Agent Activity"):
            import uuid
            for role in ["planner", "builder", "tester"]:
                agent_tracker.register_agent(
                    f"agent_{uuid.uuid4().hex[:8]}",
                    role,
                    "demo_workflow",
                )
            st.rerun()

    st.divider()

    # Agent coordination diagram
    st.subheader("Coordination Flow")

    st.markdown("""
    ```
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │   PLANNER   │────▶│   BUILDER   │────▶│   TESTER    │
    │  (analyze)  │     │  (implement)│     │  (validate) │
    └─────────────┘     └─────────────┘     └─────────────┘
           │                   │                   │
           ▼                   ▼                   ▼
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │  Workflow   │     │   Context   │     │   Results   │
    │   Context   │     │   Updates   │     │   & Logs    │
    └─────────────┘     └─────────────┘     └─────────────┘
    ```
    """)

    st.divider()

    # Agent history
    st.subheader("Recent Agent Activity")

    history = agent_tracker.get_agent_history(20)

    if history:
        for agent in history:
            status_icon = "✅" if agent["status"] == "completed" else "❌"
            st.text(
                f"{status_icon} {agent['role'].title()} "
                f"({agent['agent_id'][:12]}...) - "
                f"{agent.get('completed_at', 'N/A')}"
            )
    else:
        st.info("No agent history")


def render_metrics_page():
    """Render metrics and analytics page."""
    st.title("Metrics Dashboard")

    try:
        tracker = get_tracker()
        data = tracker.get_dashboard_data()
    except Exception:
        data = {
            "summary": {},
            "step_performance": {},
            "recent_executions": [],
        }

    # Summary cards
    summary = data.get("summary", {})

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Execution Metrics")

        st.metric("Total Workflows", summary.get("total_executions", 0))
        st.metric("Failed Workflows", summary.get("failed_executions", 0))
        st.metric("Total Steps", summary.get("total_steps_executed", 0))
        st.metric("Total Tokens", summary.get("total_tokens_used", 0))

    with col2:
        st.subheader("Performance")

        success_rate = summary.get("success_rate", 0)
        avg_duration = summary.get("avg_duration_ms", 0)

        # Success rate gauge
        st.markdown(f"### Success Rate: {success_rate:.1f}%")
        st.progress(success_rate / 100 if success_rate <= 100 else 1.0)

        st.markdown(f"### Avg Duration: {avg_duration:.0f}ms")

    st.divider()

    # Step performance breakdown
    st.subheader("Step Performance by Type")

    step_perf = data.get("step_performance", {})

    if step_perf:
        # Create a table
        rows = []
        for step_type, stats in step_perf.items():
            rows.append({
                "Step Type": step_type,
                "Count": stats["count"],
                "Avg Duration (ms)": f"{stats['avg_ms']:.1f}",
                "Failure Rate": f"{stats['failure_rate']:.1f}%",
            })

        st.table(rows)
    else:
        st.info("No step performance data available")

    st.divider()

    # Token usage over time (simulated for now)
    st.subheader("Token Usage Trend")

    recent = data.get("recent_executions", [])

    if recent:
        # Extract token data
        import pandas as pd

        token_data = [
            {
                "execution": ex["execution_id"][:8],
                "tokens": ex.get("total_tokens", 0),
            }
            for ex in recent[:20]
        ]

        if token_data and any(d["tokens"] > 0 for d in token_data):
            df = pd.DataFrame(token_data)
            st.bar_chart(df.set_index("execution")["tokens"])
        else:
            st.info("No token usage data recorded")
    else:
        st.info("Execute workflows to see token usage trends")

    st.divider()

    # Duration histogram
    st.subheader("Execution Duration Distribution")

    if recent:
        durations = [ex["duration_ms"] for ex in recent if ex.get("duration_ms")]
        if durations:
            import pandas as pd

            df = pd.DataFrame({"duration_ms": durations})
            st.bar_chart(df["duration_ms"])
        else:
            st.info("No duration data available")
    else:
        st.info("Execute workflows to see duration distribution")


def render_system_status():
    """Render system status component (for sidebar)."""
    st.sidebar.divider()
    st.sidebar.subheader("System Status")

    try:
        tracker = get_tracker()
        summary = tracker.store.get_summary()

        active = summary.get("active_workflows", 0)
        status_color = "🟢" if active == 0 else "🟡"

        st.sidebar.markdown(f"{status_color} **{active}** active workflows")
        st.sidebar.caption(f"Success rate: {summary.get('success_rate', 0):.0f}%")

    except Exception:
        st.sidebar.markdown("⚪ Monitoring unavailable")
