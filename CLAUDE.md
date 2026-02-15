# CLAUDE.md - Gorgon Project

## Overview

**Gorgon** is a multi-agent orchestration framework for production AI workflows. It coordinates specialized AI agents (OpenAI, Claude) across enterprise workflows with integrations for GitHub, Notion, and Gmail.

> The Gorgon metaphor: Multiple specialized "heads" (agents) work in coordination - Planner, Builder, Tester, Reviewer, Architect, Documenter, etc.

---

## Tech Stack

- **Language**: Python 3.12+
- **API Framework**: FastAPI 0.128+
- **Dashboard**: Streamlit
- **AI Providers**: OpenAI, Anthropic (Claude)
- **Integrations**: GitHub (PyGithub), Notion, Google APIs
- **Package Manager**: Poetry
- **Testing**: pytest
- **Linting**: ruff

---

## Project Structure

```
gorgon/
├── src/test_ai/           # Main package
│   ├── api.py             # FastAPI endpoints
│   ├── cli.py             # Typer CLI
│   ├── errors.py          # Custom exceptions
│   ├── auth/              # Authentication (token auth)
│   ├── contracts/         # Contract validation
│   ├── dashboard/         # Streamlit dashboard
│   ├── jobs/              # Job management
│   ├── metrics/           # Metrics collection & export
│   ├── analytics/         # Analytics pipeline
│   ├── plugins/           # Plugin system
│   ├── prompts/           # Prompt templates
│   └── scheduler/         # Job scheduling
├── tests/                 # pytest tests
├── workflows/             # Workflow definitions
├── config/                # Configuration files
├── deploy/                # Deployment configs
├── docs/                  # Documentation
├── examples/              # Usage examples
└── assets/                # Static assets
```

---

## Commands

### Setup
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
# or with poetry:
poetry install
```

### Development
```bash
# Run API server
./run_api.sh
# or: uvicorn src.test_ai.api:app --reload

# Run dashboard
./run_dashboard.sh
# or: streamlit run src/test_ai/dashboard/app.py

# Run CLI
./gorgon --help
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/test_ai

# Run specific test file
pytest tests/test_workflow.py -v
```

### Linting
```bash
# Check code
ruff check .

# Format code
ruff format .

# Fix auto-fixable issues
ruff check . --fix
```

---

## Environment Variables

Required in `.env`:
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=ghp_...
NOTION_TOKEN=secret_...
```

See `.env.example` for full list.

---

## Architecture

### Agent Roles
| Agent | Purpose |
|-------|---------|
| Planner | Breaks features into actionable steps |
| Builder | Writes production-ready code |
| Tester | Creates comprehensive test suites |
| Reviewer | Identifies bugs, security issues |
| Architect | Makes architectural decisions |
| Documenter | Creates API docs and guides |
| Analyst | Statistical analysis, patterns |
| Visualizer | Charts, dashboards |
| Reporter | Executive summaries |

### Workflow Pattern
```
Plan → Build → Test → Review → Deploy
```

### Key Modules
- **Orchestrators**: Coordinate multi-agent workflows
- **Contracts**: Define and validate agent behaviors
- **Plugins**: Extend functionality via plugin system
- **Metrics**: Collect and export workflow metrics
- **Scheduler**: Schedule recurring workflows

---

## Coding Conventions

### Python Style
- Type hints required on all functions
- Docstrings for public functions (Google style)
- snake_case for functions/variables
- PascalCase for classes
- UPPER_CASE for constants

### Error Handling
- Use custom exceptions from `errors.py`
- Always provide actionable error messages
- Log errors with context

### Testing
- Test file naming: `test_<module>.py`
- Use pytest fixtures from `conftest.py`
- Mock external APIs (OpenAI, GitHub, etc.)
- Aim for 80%+ coverage on core modules

---

## Key Files

| File | Purpose |
|------|---------|
| `src/test_ai/api.py` | FastAPI application entry |
| `src/test_ai/cli.py` | CLI commands (Typer) |
| `src/test_ai/analytics/` | Analytics pipeline |
| `src/test_ai/contracts/` | Contract definitions |
| `pyproject.toml` | Dependencies and project config |
| `workflows/` | YAML workflow definitions |

---

## Common Tasks

### Adding a New Agent
1. Define agent role in `agents/`
2. Create prompt template in `prompts/`
3. Add contract in `contracts/definitions.py`
4. Register in plugin system if needed
5. Add tests

### Adding an Integration
1. Add client in appropriate module
2. Add credentials to `.env.example`
3. Create wrapper with error handling
4. Add tests with mocked responses

### Creating a Workflow
1. Define in `workflows/*.yaml`
2. Specify agent sequence
3. Define input/output contracts
4. Test end-to-end

---

## Anti-Patterns to Avoid

- Hardcoding API keys (use env vars)
- Synchronous calls to external APIs (use async)
- Missing type hints
- Catching broad exceptions
- Tests that depend on external services
- God functions (> 50 lines)

---

## Skills

Skills imported from: https://github.com/AreteDriver/ai-skills
Path: Set `GORGON_SKILLS_PATH` to local clone of `ai-skills/agents/`

Available agent skills:
- `technical-debt-auditor` — 5 sub-agents, workflow.yaml, repo health scoring
- `release-engineer` — last-mile shipping automation
- `entity-resolver` — fuzzy entity matching and dedup
- `context-mapper` — pre-execution codebase/corpus mapping
- `workflow-debugger` — root-cause analysis for failed workflows
- `document-forensics` — investigative document methodology
- `intent-author` — Convergent intent graph authoring

---

## Related Documentation

- `README.md` - Project overview
- `ARCHITECTURE.md` - Detailed architecture
- `IMPLEMENTATION.md` - Implementation details
- `QUICKSTART.md` - Getting started guide
- `CONTRIBUTING.md` - Contribution guidelines
