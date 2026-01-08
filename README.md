# AI-Orchestra

**Enterprise-grade AI workflow orchestration platform** — Chain GPT-4, GitHub, Notion, and Gmail into declarative automation pipelines with full observability.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)

---

## What It Is

AI-Orchestra is a Python-based workflow orchestration platform that provides a unified interface for integrating multiple AI services and productivity tools. It enables teams to define complex multi-step automations in simple JSON configurations, with built-in authentication, error handling, and execution logging.

The platform bridges the gap between AI capabilities and practical business automation by providing a declarative workflow system that chains unlimited operations while maintaining complete audit trails.

---

## Problem / Solution / Impact

**Problem**: Organizations using AI tools face fragmented integrations, no observability into LLM calls, and difficulty scaling from ad-hoc scripts to reliable automation.

**Solution**: AI-Orchestra provides:
- Unified API layer across OpenAI, GitHub, Notion, and Gmail
- Declarative JSON workflow definitions with variable interpolation
- Reusable prompt template management
- Dual interface (REST API + Streamlit dashboard)
- Complete execution logging and error tracking

**Impact** (Intended Outcomes):
- Reduce integration development time from weeks to hours
- Enable non-developers to create and modify workflows via dashboard
- Provide audit trails for compliance-sensitive AI operations
- Support scaling from prototype to production without rewrites

---

## Quick Start

### Prerequisites
- Python 3.12+
- OpenAI API key ([get one here](https://platform.openai.com/api-keys))
- Optional: GitHub, Notion, Gmail credentials for full functionality

### Install

```bash
git clone https://github.com/AreteDriver/AI-Orchestra.git
cd AI-Orchestra
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
./init.sh
```

### Run

```bash
# Dashboard (recommended)
./run_dashboard.sh
# Open http://localhost:8501

# Or API server
./run_api.sh
# API at http://localhost:8000, docs at http://localhost:8000/docs
```

### First Workflow

```bash
# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "demo", "password": "demo"}'

# Execute
curl -X POST http://localhost:8000/workflows/execute \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"workflow_id": "simple_ai_completion", "variables": {"prompt": "Write a haiku about AI"}}'
```

---

## Architecture

```
                     +-----------------------+
                     |    User Interfaces    |
                     |  Streamlit | REST API |
                     +-----------+-----------+
                                 |
                     +-----------v-----------+
                     |     Core Engine       |
                     | Workflow | Prompts | Auth
                     +-----------+-----------+
                                 |
         +----------+------------+------------+----------+
         |          |            |            |          |
    +----v----+ +---v----+ +----v----+ +-----v----+
    | OpenAI  | | GitHub | | Notion  | |  Gmail   |
    +---------+ +--------+ +---------+ +----------+
```

For detailed component diagrams, see [docs/architecture.md](docs/architecture.md).

### Project Structure

```
AI-Orchestra/
├── src/test_ai/              # Main package
│   ├── api.py                # FastAPI backend
│   ├── api_clients/          # OpenAI, GitHub, Notion, Gmail
│   ├── orchestrator/         # Workflow engine
│   ├── prompts/              # Template management
│   └── dashboard/            # Streamlit UI
├── docs/                     # Documentation
├── config/                   # Settings files
└── requirements.txt
```

---

## AI Operating Model

| Layer | Implementation |
|-------|----------------|
| **Structured Outputs** | Pydantic models for all API responses. JSON workflow definitions with schema validation. Typed step parameters. |
| **Validation / Safety Rails** | JWT authentication on all endpoints. Input validation via Pydantic. Workflow variable type checking before execution. |
| **Retry / Fallback** | Robust error tracking per workflow step. Execution logging for debugging. Step-level error isolation (one step failure doesn't crash workflow). |
| **Telemetry** | Complete execution audit trails. Step timing and status tracking. API health endpoints. Comprehensive logging throughout. |

---

## Key Decisions

See [docs/adr/0001-initial-architecture.md](docs/adr/0001-initial-architecture.md) for the initial architecture decision record.

**Summary of Key Decisions**:
1. **JSON Workflow Definitions** — Declarative over imperative for non-developer accessibility
2. **Dual Interface (API + Dashboard)** — Serve both programmatic and interactive use cases
3. **Pluggable Client Architecture** — Each integration is independent for easy extension
4. **In-Memory Workflow Store** — Simplicity for v1; database persistence planned

---

## Usage Examples

### Simple AI Completion

```python
from test_ai import WorkflowEngine, Workflow, WorkflowStep, StepType

engine = WorkflowEngine()
workflow = Workflow(
    id="my_workflow",
    name="Simple Text Generation",
    steps=[
        WorkflowStep(
            id="generate",
            type=StepType.OPENAI,
            action="generate_completion",
            params={"prompt": "{{user_prompt}}", "model": "gpt-4o-mini"}
        )
    ],
    variables={"user_prompt": "Explain quantum computing"}
)
result = engine.execute_workflow(workflow)
```

### Email to Notion Pipeline

```json
{
  "id": "email_to_notion",
  "name": "Email Summary to Notion",
  "steps": [
    {"id": "fetch", "type": "gmail", "action": "get_messages", "params": {"max_results": 1}},
    {"id": "summarize", "type": "openai", "action": "generate_completion",
     "params": {"prompt": "Summarize: {{fetch.body}}"}},
    {"id": "save", "type": "notion", "action": "create_page",
     "params": {"title": "Email Summary", "content": "{{summarize.response}}"}}
  ]
}
```

---

## Roadmap

- [ ] Database backend (PostgreSQL) for workflow persistence
- [x] Scheduled workflow execution (cron-style) - APScheduler integration
- [x] Webhook triggers for event-driven automation - HMAC-SHA256 signed
- [x] Async workflow execution with status polling - ThreadPoolExecutor
- [ ] Additional integrations (Slack, Discord, Jira)
- [ ] Visual workflow builder in dashboard

---

## Demo

<!-- TODO: Add demo GIF showing workflow creation and execution -->
*Demo placeholder: Record creating a workflow in the dashboard and executing it*

---

## Contributing

Contributions welcome. See areas for enhancement in the roadmap above.

```bash
# Development setup
poetry install  # or pip install -r requirements.txt
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"
```

---

## License

MIT License — see [LICENSE](LICENSE)

---

## Support

- **Issues**: [GitHub Issues](https://github.com/AreteDriver/AI-Orchestra/issues)
- **Docs**: [QUICKSTART.md](QUICKSTART.md) | [IMPLEMENTATION.md](IMPLEMENTATION.md)
- **API Docs**: http://localhost:8000/docs (when running)
