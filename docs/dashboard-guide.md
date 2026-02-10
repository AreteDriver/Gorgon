# Using the Dashboard

Gorgon's Streamlit dashboard provides a web interface for workflow management, monitoring, and execution.

## Launch

```bash
./run_dashboard.sh
# or: streamlit run src/test_ai/dashboard/app.py
```

## Pages

### Dashboard (Home)
Overview metrics: workflow count, prompt count, system status. Quick-action buttons for creating workflows and launching the visual builder.

### Builder
Visual drag-and-drop workflow creation with 10 node types and 6 pre-built templates. Tabs for Canvas, Visual Graph, YAML Preview, and Execute Preview.

**Node Types**: claude_code, openai, shell, parallel, fan_out, fan_in, map_reduce, branch, loop, checkpoint

**Templates**: Feature Development, Code Review, Documentation Generator, Data Analysis Pipeline, Bug Fix, Shell Command Pipeline

### Workflows
Browse, create, and manage workflow definitions. Each workflow defines a sequence of steps with agent roles, parameters, and dependencies.

### Execute
Select a saved workflow, fill in variables, and run it. Results display inline with execution status.

### Prompts
Create and manage prompt templates. Configure model, temperature, system prompts, and variable placeholders.

### Monitoring
Real-time execution tracking: active workflows, success rates, average duration, and step-by-step progress.

### Agents
Agent coordination visualization showing active agents by role, delegation flow (Planner -> Builder -> Tester -> Reviewer), and activity history.

### Metrics
Step-level performance: execution counts, failure rates, token usage trends, and duration histograms.

### Costs
Cost tracking by provider, model, and agent role. Daily trends, budget alerts (75%/90% thresholds), and CSV export.

### Analytics
Pipeline analysis with 4 built-in pipelines: workflow_metrics, historical_trends, api_health, operations_dashboard. Configurable time ranges.

### Parallel
Fan-out/map-reduce monitoring: branch progress, rate limit status per provider, and parallel execution history.

### Plugins
Plugin marketplace for discovering, installing, and managing workflow extensions across 10 categories.

### Logs
Browse the last 20 workflow execution logs with expandable JSON detail views.

## System Status

The sidebar shows a live system status widget with active workflow count, success rate, agent count, and rate limit status.
