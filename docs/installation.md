# Installation Guide

Complete installation guide for Gorgon - a multi-agent orchestration framework for production AI workflows.

---

## Prerequisites

### System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.12+ | 3.12.x |
| RAM | 2 GB | 4 GB+ |
| Disk Space | 500 MB | 1 GB |

### Supported Operating Systems

- **Linux**: Ubuntu 20.04+, Debian 11+, RHEL 8+, Fedora 36+
- **macOS**: 12 (Monterey) or later
- **Windows**: Windows 10/11 with WSL2 recommended

### Required API Keys

| Service | Required | Purpose |
|---------|----------|---------|
| OpenAI | Yes | GPT-4 completions, summarization |
| Anthropic | No | Claude agents (multi-agent workflows) |
| GitHub | No | Repository management, issues |
| Notion | No | Content management integration |
| Gmail | No | Email reading via OAuth |

---

## Installation Methods

### Method 1: Poetry (Recommended)

Poetry is the recommended installation method for development.

```bash
# Clone the repository
git clone https://github.com/AreteDriver/Gorgon.git
cd Gorgon

# Install Poetry (if not installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Install with optional PostgreSQL support
poetry install -E postgres
```

### Method 2: pip (From Source)

```bash
# Clone the repository
git clone https://github.com/AreteDriver/Gorgon.git
cd Gorgon

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install the package
pip install -e .

# Install with PostgreSQL support
pip install -e ".[postgres]"

# Install development dependencies
pip install -e ".[dev]"
```

### Method 3: Docker (Production)

Docker deployment includes PostgreSQL and is recommended for production.

```bash
# Clone the repository
git clone https://github.com/AreteDriver/Gorgon.git
cd Gorgon

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys and credentials (see Environment Setup below)

# Generate a secure SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"
# Add the generated key to .env

# Set required PostgreSQL password in .env
# POSTGRES_PASSWORD=your-secure-password-here

# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

**Docker Services:**

| Service | Container | Port | Description |
|---------|-----------|------|-------------|
| API | gorgon-api | 8001 | FastAPI backend |
| Dashboard | gorgon-dashboard | 8501 | Streamlit UI |
| Database | gorgon-db | 5432 | PostgreSQL 16 |

---

## Environment Setup

### 1. Create Configuration File

```bash
cp .env.example .env
```

### 2. Configure Required Variables

Edit `.env` and set the following:

```bash
# Required: OpenAI API Key
OPENAI_API_KEY=sk-your-openai-api-key

# Required for production: Secret key for JWT tokens
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(48))"
SECRET_KEY=your-generated-secret-key
```

### 3. Configure Optional Variables

```bash
# Claude agents (for multi-agent workflows)
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
CLAUDE_MODE=api  # 'api' or 'cli'

# GitHub integration
GITHUB_TOKEN=ghp_your-github-token

# Notion integration
NOTION_TOKEN=secret_your-notion-token

# Gmail OAuth (path to credentials.json from Google Cloud Console)
GMAIL_CREDENTIALS_PATH=path/to/credentials.json
```

### 4. Configure Database

```bash
# SQLite (default, for development)
DATABASE_URL=sqlite:///gorgon-state.db

# PostgreSQL (for production)
DATABASE_URL=postgresql://user:password@localhost:5432/gorgon
```

### 5. Production Security Settings

For production deployments, set:

```bash
PRODUCTION=true
ALLOW_DEMO_AUTH=false
REQUIRE_SECURE_CONFIG=true
DEBUG=false
LOG_FORMAT=json
SANITIZE_LOGS=true
```

---

## Verification

### Verify Installation

```bash
# Check CLI is available
gorgon --help

# Or using poetry
poetry run gorgon --help
```

### Start the API Server

```bash
# Using the run script
./run_api.sh

# Or manually
uvicorn test_ai.api:app --host 0.0.0.0 --port 8000

# Or with poetry
poetry run uvicorn test_ai.api:app --host 0.0.0.0 --port 8000
```

### Start the Dashboard

```bash
# Using the run script
./run_dashboard.sh

# Or manually
streamlit run src/test_ai/dashboard/app.py

# Or with poetry
poetry run streamlit run src/test_ai/dashboard/app.py
```

### Verify Services

```bash
# Check API health
curl http://localhost:8000/health

# Check database connectivity
curl http://localhost:8000/health/db

# Access Dashboard
open http://localhost:8501  # macOS
xdg-open http://localhost:8501  # Linux
```

Expected health check response:

```json
{"status": "healthy"}
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/test_ai

# Run specific test
pytest tests/test_workflow.py -v
```

---

## Troubleshooting

### Python Version Issues

**Error:** `Python version 3.11 is not supported`

**Solution:** Gorgon requires Python 3.12+. Install Python 3.12:

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.12 python3.12-venv

# macOS (with Homebrew)
brew install python@3.12

# Use pyenv
pyenv install 3.12
pyenv local 3.12
```

### Poetry Not Found

**Error:** `poetry: command not found`

**Solution:** Install Poetry and add to PATH:

```bash
curl -sSL https://install.python-poetry.org | python3 -

# Add to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.local/bin:$PATH"
```

### Missing API Keys

**Error:** `OPENAI_API_KEY environment variable not set`

**Solution:** Ensure `.env` file exists and contains valid API keys:

```bash
# Verify .env exists
ls -la .env

# Check key is set
grep OPENAI_API_KEY .env
```

### Docker: POSTGRES_PASSWORD Required

**Error:** `POSTGRES_PASSWORD is required`

**Solution:** Set POSTGRES_PASSWORD in your `.env` file:

```bash
POSTGRES_PASSWORD=your-secure-password-here
```

### Docker: SECRET_KEY Required

**Error:** `SECRET_KEY is required`

**Solution:** Generate and set a secure secret key:

```bash
# Generate key
python -c "import secrets; print(secrets.token_urlsafe(48))"

# Add to .env
SECRET_KEY=generated-key-here
```

### Port Already in Use

**Error:** `Address already in use: 8000`

**Solution:** Find and stop the conflicting process:

```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use a different port
uvicorn test_ai.api:app --port 8080
```

### Database Connection Failed

**Error:** `could not connect to server: Connection refused`

**Solution for PostgreSQL:**

```bash
# Check PostgreSQL is running
docker compose ps

# Restart the database
docker compose restart db

# Check database logs
docker compose logs db
```

**Solution for SQLite:**

```bash
# Ensure database file is writable
ls -la gorgon-state.db

# Check permissions
chmod 644 gorgon-state.db
```

### Import Errors

**Error:** `ModuleNotFoundError: No module named 'test_ai'`

**Solution:** Set PYTHONPATH or install in editable mode:

```bash
# Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"

# Or reinstall in editable mode
pip install -e .
```

### SSL Certificate Errors (macOS)

**Error:** `SSL: CERTIFICATE_VERIFY_FAILED`

**Solution:** Install certificates:

```bash
# For Python installed via Homebrew
/Applications/Python\ 3.12/Install\ Certificates.command

# Or install certifi
pip install certifi
```

---

## Next Steps

After installation:

1. **Read the Quick Start**: See [QUICKSTART.md](../QUICKSTART.md) for usage examples
2. **Explore the API**: Visit http://localhost:8000/docs for interactive API documentation
3. **Configure Agents**: Edit `config/agent_prompts.json` to customize agent behavior
4. **Create Workflows**: Define workflows in `workflows/` directory

---

## Related Documentation

- [README.md](../README.md) - Project overview
- [QUICKSTART.md](../QUICKSTART.md) - Getting started guide
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Production deployment
- [architecture.md](architecture.md) - System architecture
