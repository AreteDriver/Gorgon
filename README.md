# Gorgon

**Multi-agent orchestration framework for production AI workflows**

> *Like the mythical Gorgon with multiple heads, each specialized agent focuses its gaze on a specific aspect of the workflow - planning, building, testing, and reviewing in coordinated harmony.*

[![CI](https://github.com/AreteDriver/Gorgon/actions/workflows/ci.yml/badge.svg)](https://github.com/AreteDriver/Gorgon/actions/workflows/ci.yml)
[![CodeQL](https://github.com/AreteDriver/Gorgon/actions/workflows/codeql.yml/badge.svg)](https://github.com/AreteDriver/Gorgon/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-green.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-3358-brightgreen.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-83%25-brightgreen.svg)]()

---

## What's New in v1.0.0

**Budgeted multi-agent workflows with checkpoint/resume and cost observability.**

Define a workflow, set a token/dollar budget, and let specialized agents execute it step-by-step. If a run is interrupted or exceeds its budget, it checkpoints automatically and resumes where it left off. Every step emits cost and latency metrics you can query from the dashboard or the `/v1/jobs` API.

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

### Optional Modules

These ship with v1.0.0 but are **not required** for the core workflow engine:

| Module | What it adds |
|--------|-------------|
| Visual Workflow Builder | Drag-and-drop canvas with YAML export |
| Plugin Marketplace | Discover and install community workflow plugins |
| Agent Eval Framework | Benchmark and compare agent performance |
| Messaging Bots | Trigger workflows from Telegram, Discord, Slack |
| Chat Interface | Conversational AI with session persistence |
| Supervisor Agent | Auto-delegate tasks to specialized sub-agents |
| Self-Improvement | Autonomous codebase improvement with safety guards |

---

## Screenshots

### Dashboard
Monitor active workflows, token usage, costs, and recent executions.
![Dashboard](docs/screenshot-dashboard.png)

### Workflows
Create and manage multi-agent workflow pipelines.
![Workflows](docs/screenshot-workflows.png)

### Executions
Track running, completed, paused, and failed workflow executions with cost tracking.
![Executions](docs/screenshot-executions.png)

---

## Overview

Gorgon is a production-grade framework for coordinating specialized AI agents across enterprise workflows. It provides a unified interface for chaining OpenAI, Claude, GitHub, Notion, and Gmail into declarative automation pipelines with full observability.

### The Gorgon Metaphor

In Greek mythology, the Gorgon had multiple heads, each with a specific purpose. Similarly, Gorgon orchestrates multiple AI agents:

| Head | Role | Purpose |
|------|------|---------|
| **Planner** | Strategic vision | Breaks features into actionable steps |
| **Builder** | Implementation | Writes production-ready code |
| **Tester** | Quality assurance | Creates comprehensive test suites |
| **Reviewer** | Analysis | Identifies bugs, security issues, improvements |
| **Architect** | System design | Makes architectural decisions |
| **Documenter** | Technical writing | Creates API docs and guides |
| **Data Engineer** | Data pipelines | Collection, cleaning, transformation |
| **Analyst** | Data analysis | Statistical analysis, pattern finding |
| **Visualizer** | Visualization | Charts, dashboards, visual insights |
| **Reporter** | Reporting | Executive summaries, stakeholder docs |

Each head works independently yet in perfect coordination, turning complex workflows into solid, repeatable execution.

---

## Features

### Chat Interface
Conversational AI with persistent sessions, streaming responses, and agent attribution.
```bash
# Start chatting with Gorgon
curl -X POST http://localhost:8000/v1/chat/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "New Feature Discussion"}'
```

### Self-Improvement System
Gorgon can analyze and improve its own codebase under strict safety controls:
- **Protected files**: Auth, security, and credentials cannot be modified
- **Change limits**: Max 10 files / 500 lines per PR
- **Human approval gates**: Required at plan, apply, and merge stages
- **Auto-rollback**: Reverts on test failures

### Multi-Agent Development Workflows
```
Plan → Build → Test → Review
```
Coordinate specialized Claude agents for software development with a single API call.

### Unified Integration Layer
- **OpenAI**: GPT-4 completions, summarization, SOP generation
- **Claude**: Multi-agent orchestration with role-based prompts
- **GitHub**: Issues, commits, repository management
- **Notion**: Pages, databases, content management
- **Gmail**: Email reading, OAuth authentication
- **Slack**: Channel messaging, notifications

### Production Instrumentation
- Phase-by-phase timing and metrics
- Success rate tracking
- Complete execution audit trails
- JSON workflow logging

### Dual Interface
- **REST API**: Programmatic access via FastAPI
- **Dashboard**: Interactive Streamlit UI

---

## Quick Start

### Prerequisites
- Python 3.12+
- API keys: OpenAI (required), Anthropic (for Claude agents)
- Optional: GitHub, Notion, Gmail credentials

### Installation

```bash
git clone https://github.com/AreteDriver/Gorgon.git
cd Gorgon
poetry install
cp .env.example .env
# Add your API keys to .env
```

### Configuration

```bash
# .env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...  # For Claude agents
CLAUDE_MODE=api               # 'api' or 'cli'
```

### Run

```bash
# Dashboard
./run_dashboard.sh
# Open http://localhost:8501

# API server
./run_api.sh
# API at http://localhost:8000
```

### Docker (with PostgreSQL)

```bash
# Start all services
docker compose up -d

# Services:
# - API: http://localhost:8001
# - Dashboard: http://localhost:8501
# - PostgreSQL: localhost:5432

# View logs
docker compose logs -f api

# Stop services
docker compose down
```

---

## Workflow Examples

### Development: Plan → Build → Test → Review

```bash
curl -X POST http://localhost:8000/v1/workflows/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "dev_workflow_plan_build_test_review",
    "variables": {
      "feature_request": "Build a REST API for user authentication"
    }
  }'
```

Or via Python:

```python
from test_ai.orchestrator import WorkflowEngine

engine = WorkflowEngine()
workflow = engine.load_workflow("dev_workflow_plan_build_test_review")
workflow.variables["feature_request"] = "Build user authentication"

result = engine.execute_workflow(workflow)

for step_id, output in result.outputs.items():
    print(f"[{step_id}]: {output['output'][:200]}...")
```

### Analytics: Ingest → Analyze → Visualize → Report

```bash
curl -X POST http://localhost:8000/v1/workflows/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "analytics_pipeline",
    "variables": {
      "data_task": "Analyze Q4 sales data and identify top performing regions"
    }
  }'
```

Pipeline stages:
1. **Data Engineer** - Designs ingestion and cleaning pipeline
2. **Analyst** - Performs statistical analysis, finds patterns
3. **Visualizer** - Creates charts and dashboard code
4. **Reporter** - Generates executive summary with recommendations

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Layer                            │
│  ┌──────────────────┐         ┌──────────────────────┐     │
│  │  Streamlit UI    │         │   REST API Clients   │     │
│  └──────────────────┘         └──────────────────────┘     │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                   Workflow Engine                            │
│         JSON Definitions │ Variable Interpolation            │
│              Step Execution │ Error Handling                 │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                   Integration Layer                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ OpenAI  │ │ GitHub  │ │ Notion  │ │  Gmail  │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
│                    ┌─────────────┐                          │
│                    │ Claude Code │                          │
│                    │  (Agents)   │                          │
│                    └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

### Project Structure

```
Gorgon/
├── src/test_ai/
│   ├── api.py                    # FastAPI backend
│   ├── agents/                   # Supervisor & provider wrapper
│   ├── chat/                     # Chat sessions & messages
│   ├── self_improve/             # Self-improvement system
│   │   ├── orchestrator.py       # 10-stage workflow
│   │   ├── safety.py             # Protected files, limits
│   │   ├── sandbox.py            # Isolated execution
│   │   └── rollback.py           # Snapshot/restore
│   ├── api_clients/
│   │   ├── openai_client.py      # GPT integration
│   │   ├── claude_code_client.py # Claude agents
│   │   ├── github_client.py
│   │   ├── notion_client.py
│   │   ├── gmail_client.py
│   │   ├── slack_client.py       # Slack messaging
│   │   └── resilience.py         # Retry, circuit breaker, fallbacks
│   ├── orchestrator/
│   │   └── workflow_engine.py    # Core execution engine
│   ├── skills/                   # Skill context injection
│   └── workflows/                # JSON workflow definitions
├── frontend/                     # React + TypeScript frontend
├── config/
│   ├── agent_prompts.json        # Customizable agent prompts
│   └── self_improve_safety.yaml  # Self-improvement constraints
├── docs/
│   └── claude-code-integration.md
└── requirements.txt
```

---

## Database Configuration

Gorgon supports both SQLite (default) and PostgreSQL backends.

### SQLite (Default)

No configuration needed. The database file (`gorgon-state.db`) is created automatically on first run. Do not commit it to version control.

### PostgreSQL

Set the `DATABASE_URL` environment variable:

```bash
# .env
DATABASE_URL=postgresql://user:password@localhost:5432/gorgon
```

Or use Docker Compose which configures PostgreSQL automatically.

---

## API Endpoints

All versioned endpoints use the `/v1` prefix. Health and webhook trigger endpoints remain unversioned for compatibility.

### Health & Monitoring (Unversioned)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Basic health check |
| `/health/db` | GET | Database connectivity and migration status |

### Authentication

| Endpoint | Method | Rate Limit | Description |
|----------|--------|------------|-------------|
| `/v1/auth/login` | POST | 5/min | Get access token |

### Jobs (Async Workflow Execution)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/jobs` | GET | List jobs (filter by status, workflow_id) |
| `/v1/jobs` | POST | Submit workflow for async execution |
| `/v1/jobs/stats` | GET | Job statistics |
| `/v1/jobs/{id}` | GET | Get job status and result |
| `/v1/jobs/{id}/cancel` | POST | Cancel pending/running job |

### Schedules (Cron/Interval)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/schedules` | GET | List all schedules |
| `/v1/schedules` | POST | Create schedule (cron or interval) |
| `/v1/schedules/{id}` | GET | Get schedule details |
| `/v1/schedules/{id}/pause` | POST | Pause schedule |
| `/v1/schedules/{id}/resume` | POST | Resume schedule |

### Webhooks (Event-Driven)

| Endpoint | Method | Rate Limit | Description |
|----------|--------|------------|-------------|
| `/v1/webhooks` | GET | - | List webhooks |
| `/v1/webhooks` | POST | - | Create webhook |
| `/v1/webhooks/{id}` | GET | - | Get webhook (includes secret) |
| `/hooks/{id}` | POST | 30/min | Trigger webhook (public, unversioned) |

### Rate Limiting

Public endpoints are rate-limited per IP:
- **Login**: 5 requests/minute
- **Webhook triggers**: 30 requests/minute

Rate-limited responses return `429` with `Retry-After` header.

---

## Claude Agent Roles

Customize agent behavior via `config/agent_prompts.json`:

```json
{
  "planner": {
    "name": "Strategic Planning Agent",
    "system_prompt": "You are a strategic planning agent..."
  },
  "builder": {
    "name": "Code Implementation Agent",
    "system_prompt": "You are a code implementation agent..."
  }
}
```

### Using Agents Directly

```python
from test_ai.api_clients import ClaudeCodeClient

client = ClaudeCodeClient()

# Execute specialized agent
result = client.execute_agent(
    role="planner",
    task="Design a microservices architecture",
    context="Using Python, FastAPI, and PostgreSQL"
)

print(result["output"])
```

---

## Workflow Definition

Define workflows as JSON:

```json
{
  "id": "dev_workflow_plan_build_test_review",
  "name": "Development Workflow",
  "steps": [
    {
      "id": "plan",
      "type": "claude_code",
      "action": "execute_agent",
      "params": { "role": "planner", "task": "{{feature_request}}" },
      "next_step": "build"
    },
    {
      "id": "build",
      "type": "claude_code",
      "action": "execute_agent",
      "params": { "role": "builder", "context": "{{plan_output}}" },
      "next_step": "test"
    }
  ],
  "variables": { "feature_request": "" }
}
```

---

## Roadmap

### Core (shipped in v1.0.0)

- [x] Multi-agent Claude integration
- [x] Development workflow (Plan → Build → Test → Review)
- [x] Analytics workflow (Ingest → Analyze → Visualize → Report)
- [x] Configurable agent prompts (10 roles)
- [x] Database backend (SQLite + PostgreSQL)
- [x] Job queue with async execution
- [x] Scheduled workflows (cron/interval)
- [x] Webhook triggers
- [x] Checkpoint/resume for long-running workflows
- [x] Budget enforcement and cost observability
- [x] Request logging with tracing
- [x] Rate limiting
- [x] CI/CD pipeline
- [x] Parallel agent execution
- [x] API resilience (retry, circuit breaker, fallbacks)

### Optional modules (shipped, opt-in)

- [x] Visual workflow builder
- [x] Plugin marketplace
- [x] Chat interface with session persistence
- [x] Supervisor agent for task delegation
- [x] Self-improvement system with safety guards
- [x] Messaging bots (Telegram, Discord, Slack)
- [x] Agent memory/context persistence
- [x] Skill context injection
- [x] Multi-tenant support
- [x] Workflow version control

### Planned

- [ ] Streaming execution logs via SSE/WebSocket
- [ ] Per-agent cost attribution in dashboard
- [ ] Workflow marketplace (share across orgs)

---

## Why "Gorgon"?

- **Multiple specialized heads** working in coordination
- **Focused power** - each agent excels at its specific task
- **Petrifying complexity** - turning chaotic workflows into solid processes
- **Mythological reliability** - battle-tested patterns from production

---

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
# Development setup
poetry install
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"
```

---

## License

MIT License — see [LICENSE](LICENSE)

---

## Support

- **Issues**: [GitHub Issues](https://github.com/AreteDriver/Gorgon/issues)
- **Docs**: [QUICKSTART.md](QUICKSTART.md) | [docs/](docs/)
- **API Docs**: http://localhost:8000/docs (when running)

---

**Author**: ARETE
**Status**: Active Development
**Version**: 1.0.0
