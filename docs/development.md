# Development Setup

## Prerequisites

- Python 3.12+
- Poetry (recommended) or pip

## Installation

```bash
git clone https://github.com/AreteDriver/Gorgon.git
cd Gorgon

# With Poetry
poetry install

# With pip
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Optional Extras

```bash
poetry install --extras postgres    # PostgreSQL support
poetry install --extras messaging   # Telegram/Discord bots
poetry install --extras browser     # Playwright browser automation
poetry install --extras all         # Everything
```

## Running

```bash
# Dashboard
./run_dashboard.sh

# API server
./run_api.sh

# CLI
python -m test_ai.cli --help
```

## Code Quality

```bash
# Lint
ruff check .
ruff check . --fix    # Auto-fix

# Format
ruff format .

# Tests
pytest
pytest --cov=src/test_ai --cov-report=html

# Single test
pytest tests/test_workflow.py -v
```

## Project Structure

```
src/test_ai/
├── api.py              # FastAPI endpoints
├── cli.py              # Typer CLI
├── errors.py           # Custom exceptions
├── auth/               # Token-based auth
├── cache/              # Memory + Redis caching
├── config/             # Settings (Pydantic)
├── dashboard/          # Streamlit UI (13 pages)
├── api_clients/        # OpenAI, GitHub, Notion, Gmail
├── orchestrators/      # Agent orchestration
├── plugins/            # Plugin system
├── prompts/            # Prompt template manager
├── ratelimit/          # Token bucket + sliding window
├── scheduler/          # Job scheduling
├── security/           # Encryption, brute force, audit
└── workflow/           # Workflow engine + loader
```

## Conventions

- **Type hints** on all public functions
- **Google-style docstrings** for public APIs
- **Custom exceptions** from `errors.py` (never bare `Exception`)
- **snake_case** functions/variables, **PascalCase** classes
- **Coverage target**: 80%+ overall, 90%+ core logic
