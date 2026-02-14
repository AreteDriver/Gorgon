# Gorgon

Production runtime for AI agent workflows. Budget controls, checkpoints, resilience, and cost observability — built in, not bolted on.

[![CI](https://github.com/AreteDriver/Gorgon/actions/workflows/ci.yml/badge.svg)](https://github.com/AreteDriver/Gorgon/actions/workflows/ci.yml)
[![CodeQL](https://github.com/AreteDriver/Gorgon/actions/workflows/codeql.yml/badge.svg)](https://github.com/AreteDriver/Gorgon/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-5231-brightgreen.svg)]()

## Why This Exists

- **Problem:** AI agent workflows fail silently, costs spiral without warning, and interrupted runs lose all progress. Teams paste prompts into notebooks and hope for the best.
- **Audience:** Engineers running multi-step AI pipelines in production — anyone who needs their agent workflows to be reproducible, observable, and cost-controlled.
- **Outcome:** Define a workflow once. Gorgon handles execution order, budget enforcement, failure recovery, and cost tracking. Every run is checkpointed, auditable, and resumable.

## What It Does

- **Declarative workflows** — Define multi-agent pipelines as YAML/JSON with variable interpolation, conditional branching, and error handling
- **Budget enforcement** — Set per-workflow token/USD limits. Gorgon tracks costs per step and halts before overspend
- **Checkpoint & resume** — Automatic state snapshots after each step. Resume from last checkpoint on failure or interruption
- **Circuit breakers & bulkheads** — Per-provider resilience with exponential backoff, fallback chains, and concurrency isolation
- **Cost observability** — Per-call token tracking, cost attribution by workflow/agent/provider, Prometheus metrics export
- **10 specialized agents** — Planner, Builder, Tester, Reviewer, Architect, Documenter, Analyst, Visualizer, Reporter, Data Engineer
- **Parallel execution** — DAG-based scheduling with fan-out, fan-in, and map-reduce patterns
- **Job queue & scheduling** — Async execution, cron/interval triggers, webhook-driven workflows
- **Multi-tenant isolation** — Per-tenant namespaces, quotas, and RBAC
- **Triple interface** — REST API (FastAPI), dashboard (Streamlit), CLI (Typer), and TUI (Textual)

## Quickstart

### Prerequisites

- Python 3.12+
- At least one AI provider key (OpenAI or Anthropic)

### Install

```bash
git clone https://github.com/AreteDriver/Gorgon.git
cd Gorgon
poetry install
cp .env.example .env
# Edit .env — add OPENAI_API_KEY and/or ANTHROPIC_API_KEY
```

### Run

```bash
# API server (http://localhost:8000, docs at /docs)
./run_api.sh

# Dashboard (http://localhost:8501)
./run_dashboard.sh

# CLI
gorgon workflow list
gorgon workflow run dev_workflow_plan_build_test_review \
  --var feature_request="Build user authentication"
```

### Docker

```bash
docker compose up -d
# API: http://localhost:8001 | Dashboard: http://localhost:8501 | PostgreSQL: :5432
```

## Usage Examples

### Example 1: Execute a budgeted workflow

```bash
curl -X POST http://localhost:8000/v1/workflows/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "dev_workflow_plan_build_test_review",
    "variables": { "feature_request": "Build user auth" },
    "budget": { "max_cost_usd": 2.00 }
  }'
```

What happens:
1. **Planner** breaks the request into implementation steps
2. **Builder** writes production code with type hints and error handling
3. **Tester** generates a test suite covering edge cases
4. **Reviewer** audits for security issues, bugs, and improvements
5. Each step is checkpointed. If the budget limit is hit at step 3, resume later from step 3 — steps 1-2 are not re-executed

### Example 2: Define a custom workflow

```yaml
# workflows/my-pipeline.yaml
name: Security Audit Pipeline
token_budget: 100000
timeout_seconds: 1800

steps:
  - id: scan
    type: claude_code
    params:
      role: reviewer
      prompt: "Audit this codebase for OWASP Top 10 vulnerabilities"
    on_failure: abort

  - id: report
    depends_on: [scan]
    type: claude_code
    params:
      role: reporter
      prompt: "Write an executive summary of the security findings"
    on_failure: retry
    max_retries: 2
```

```bash
gorgon workflow run my-pipeline
```

### Example 3: Check budget and cost status

```bash
# Current spend across all workflows
curl http://localhost:8000/v1/budgets/summary \
  -H "Authorization: Bearer $TOKEN"

# Per-workflow execution history with cost breakdown
curl http://localhost:8000/v1/dashboard/usage/daily \
  -H "Authorization: Bearer $TOKEN"
```

## Architecture

```text
Client Layer        Streamlit | FastAPI | CLI | TUI
                         │
Application Layer   Auth, CORS, Rate Limiting, Audit Logging
                         │
Orchestration       WorkflowEngine ─── GraphExecutor ─── ParallelExecutor
                    │                │                │
                    Contracts        Checkpoints      Resilience
                    (schema valid.)  (SQLite/PG)      (circuit breaker,
                                                       bulkhead, retry)
                         │
Integration Layer   Claude | OpenAI | GitHub | Notion | Gmail | Slack
                         │
Observability       MetricsCollector | CostTracker | PrometheusExporter
```

**Key components:**

| Component | Responsibility |
|-----------|---------------|
| `WorkflowEngine` | Sequential step execution, variable interpolation, error routing |
| `GraphExecutor` | DAG-based parallel execution with dependency resolution |
| `CheckpointManager` | State persistence after each step, resume from failure |
| `CostTracker` | Per-call token counting, USD attribution, budget alerts |
| `CircuitBreaker` | Per-provider failure tracking, automatic fallback routing |
| `ContractEnforcer` | Input/output schema validation per agent role |
| `SupervisorAgent` | Intelligent task delegation to specialized sub-agents |

## Testing

```bash
# Full suite (5231 tests)
pytest

# With coverage
pytest --cov=src/test_ai

# Specific module
pytest tests/test_workflow.py -v

# Lint
ruff check . && ruff format --check .
```

## Roadmap

- **v0.4.0** (current): Core engine, parallel execution, budget controls, CLI, plugin system, metrics
- **v0.5.0** (next): Streaming execution logs via SSE, per-agent cost attribution in dashboard
- **v1.0.0**: Stable API contract, workflow marketplace, production deployment guides

## License

[MIT](LICENSE) — use it however you want.
