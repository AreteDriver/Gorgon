# Gorgon

**Multi-agent orchestration framework for production AI workflows**

> *Like the mythical Gorgon with multiple heads, each specialized agent focuses its gaze on a specific aspect of the workflow - planning, building, testing, and reviewing in coordinated harmony.*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-green.svg)](https://fastapi.tiangolo.com/)

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

Each head works independently yet in perfect coordination, turning complex workflows into solid, repeatable execution.

---

## Features

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
pip install -r requirements.txt
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

---

## Development Workflow Example

Execute a complete Plan → Build → Test → Review pipeline:

```bash
curl -X POST http://localhost:8000/workflows/execute \
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
│   ├── api_clients/
│   │   ├── openai_client.py      # GPT integration
│   │   ├── claude_code_client.py # Claude agents
│   │   ├── github_client.py
│   │   ├── notion_client.py
│   │   └── gmail_client.py
│   ├── orchestrator/
│   │   └── workflow_engine.py    # Core execution engine
│   └── workflows/                # JSON workflow definitions
├── config/
│   └── agent_prompts.json        # Customizable agent prompts
├── docs/
│   └── claude-code-integration.md
└── requirements.txt
```

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

- [x] Multi-agent Claude integration
- [x] Development workflow (Plan → Build → Test → Review)
- [x] Configurable agent prompts
- [ ] Database backend (PostgreSQL)
- [ ] Parallel agent execution
- [ ] Visual workflow builder
- [ ] Agent memory/context persistence

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
pip install -r requirements.txt
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
**Version**: 0.2.0
