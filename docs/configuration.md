# Configuration Guide

This document provides comprehensive documentation for configuring Gorgon, covering environment variables, settings files, integration-specific configuration, security settings, database options, and logging.

## Table of Contents

1. [Configuration Overview](#configuration-overview)
2. [Environment Variables](#environment-variables)
3. [Settings File Options](#settings-file-options)
4. [Integration Configuration](#integration-configuration)
5. [Security Settings](#security-settings)
6. [Database Configuration](#database-configuration)
7. [Logging Configuration](#logging-configuration)
8. [Example Configurations](#example-configurations)

---

## Configuration Overview

Gorgon uses a layered configuration system based on Pydantic Settings:

1. **Environment Variables** - Primary configuration method, loaded from `.env` file or system environment
2. **Settings Files** - YAML-based configuration for workflows and integrations (`config/settings.example.yaml`)
3. **Defaults** - Sensible defaults built into the application

### Configuration Precedence

1. Environment variables (highest priority)
2. `.env` file values
3. Application defaults (lowest priority)

### Quick Start

```bash
# Copy example configuration
cp .env.example .env

# Edit with your API keys and settings
nano .env

# For production, generate a secure secret key
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## Environment Variables

### API Keys

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key for GPT models | `""` | Yes (for OpenAI workflows) |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude models | `None` | Yes (for Claude workflows) |
| `GITHUB_TOKEN` | GitHub personal access token for repository operations | `None` | No |
| `NOTION_TOKEN` | Notion integration token for database/page operations | `None` | No |
| `GMAIL_CREDENTIALS_PATH` | Path to Gmail OAuth credentials JSON file | `None` | No |

### Claude/Anthropic Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ANTHROPIC_API_KEY` | API key for Claude/Anthropic | `None` | Yes (for Claude) |
| `CLAUDE_CLI_PATH` | Path to Claude CLI executable | `claude` | No |
| `CLAUDE_MODE` | Claude invocation mode: `api` or `cli` | `api` | No |

### Application Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `APP_NAME` | Application name | `Gorgon` | No |
| `DEBUG` | Enable debug mode (verbose logging, dev features) | `false` | No |
| `PRODUCTION` | Production mode - enforces strict security validation | `false` | No |
| `REQUIRE_SECURE_CONFIG` | Require secure SECRET_KEY and DATABASE_URL even in dev | `false` | No |
| `LOG_LEVEL` | Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL | `INFO` | No |
| `LOG_FORMAT` | Log format: `text` or `json` | `text` | No |
| `SANITIZE_LOGS` | Remove sensitive data (API keys, tokens) from logs | `true` | No |

### Security Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SECRET_KEY` | Secret key for JWT token generation (min 32 chars) | `change-me-in-production` | Yes (production) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token expiration in minutes | `60` | No |
| `API_CREDENTIALS` | Comma-separated `user:password_hash` pairs | `None` | No |
| `ALLOW_DEMO_AUTH` | Allow demo authentication (password='demo') | `false` | No |

### Database Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | Database connection URL | `sqlite:///gorgon-state.db` | No |
| `POSTGRES_USER` | PostgreSQL username (for Docker Compose) | `gorgon` | No |
| `POSTGRES_PASSWORD` | PostgreSQL password (for Docker Compose) | - | Yes (PostgreSQL) |
| `POSTGRES_DB` | PostgreSQL database name | `gorgon` | No |

### Shell Execution Limits

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SHELL_TIMEOUT_SECONDS` | Maximum shell command execution time | `300` (5 min) | No |
| `SHELL_MAX_OUTPUT_BYTES` | Maximum output size for shell commands | `10485760` (10MB) | No |
| `SHELL_ALLOWED_COMMANDS` | Comma-separated list of allowed commands (empty = all) | `None` | No |

### Rate Limiting

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `RATELIMIT_OPENAI_RPM` | OpenAI requests per minute | `60` | No |
| `RATELIMIT_OPENAI_TPM` | OpenAI tokens per minute | `90000` | No |
| `RATELIMIT_ANTHROPIC_RPM` | Anthropic requests per minute | `60` | No |
| `RATELIMIT_GITHUB_RPM` | GitHub requests per minute | `30` | No |
| `RATELIMIT_NOTION_RPM` | Notion requests per minute | `30` | No |
| `RATELIMIT_GMAIL_RPM` | Gmail requests per minute | `30` | No |

### Bulkhead/Concurrency Limits

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `BULKHEAD_OPENAI_CONCURRENT` | OpenAI max concurrent requests | `10` | No |
| `BULKHEAD_ANTHROPIC_CONCURRENT` | Anthropic max concurrent requests | `10` | No |
| `BULKHEAD_GITHUB_CONCURRENT` | GitHub max concurrent requests | `5` | No |
| `BULKHEAD_NOTION_CONCURRENT` | Notion max concurrent requests | `3` | No |
| `BULKHEAD_GMAIL_CONCURRENT` | Gmail max concurrent requests | `5` | No |
| `BULKHEAD_DEFAULT_TIMEOUT` | Default bulkhead timeout in seconds | `30.0` | No |

### Request Size Limits

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `REQUEST_MAX_BODY_SIZE` | Maximum request body size | `10485760` (10MB) | No |
| `REQUEST_MAX_JSON_SIZE` | Maximum JSON body size | `1048576` (1MB) | No |
| `REQUEST_MAX_FORM_SIZE` | Maximum form body size | `52428800` (50MB) | No |

### Brute Force Protection

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `BRUTE_FORCE_MAX_ATTEMPTS_PER_MINUTE` | Max requests/min per IP | `60` | No |
| `BRUTE_FORCE_MAX_ATTEMPTS_PER_HOUR` | Max requests/hour per IP | `300` | No |
| `BRUTE_FORCE_MAX_AUTH_ATTEMPTS_PER_MINUTE` | Max auth attempts/min per IP | `5` | No |
| `BRUTE_FORCE_MAX_AUTH_ATTEMPTS_PER_HOUR` | Max auth attempts/hour per IP | `20` | No |
| `BRUTE_FORCE_INITIAL_BLOCK_SECONDS` | Initial block duration | `60.0` | No |
| `BRUTE_FORCE_MAX_BLOCK_SECONDS` | Maximum block duration | `3600.0` (1 hour) | No |

### Distributed Tracing

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `TRACING_ENABLED` | Enable distributed tracing | `true` | No |
| `TRACING_SERVICE_NAME` | Service name for tracing | `gorgon-api` | No |
| `TRACING_SAMPLE_RATE` | Trace sampling rate (0.0-1.0) | `1.0` | No |

---

## Settings File Options

### config/settings.example.yaml

The YAML settings file provides configuration for application behavior, integrations, and default workflows:

```yaml
app:
  name: AI Workflow Orchestrator
  host: 127.0.0.1
  port: 8000
  log_dir: logs

integrations:
  openai:
    api_key: "${OPENAI_API_KEY}"    # Reference environment variable
    model: "gpt-4o-mini"             # Default model
  notion:
    api_key: "${NOTION_API_KEY}"
    database_id: "REPLACE_WITH_DB_ID"
  gmail:
    user_id: "me"                    # Gmail API uses 'me' for authenticated user
  github:
    token: "${GITHUB_TOKEN}"
    repo: "username/repository"

workflows:
  default: "email_to_notion_to_git"
```

### Directory Configuration

The application uses several directories for different purposes. All paths are relative to the application base directory:

| Path | Description |
|------|-------------|
| `logs/` | Application log files |
| `prompts/` | Prompt templates |
| `workflows/` | Workflow definitions |
| `schedules/` | Schedule configurations |
| `webhooks/` | Webhook configurations |
| `jobs/` | Job definitions |
| `plugins/custom/` | Custom plugin modules |
| `skills/` | Skill definitions (schema.yaml + SKILL.md) |

---

## Integration Configuration

### OpenAI

OpenAI integration enables GPT-based text generation, summarization, and SOP generation.

**Required Environment Variables:**
```bash
OPENAI_API_KEY=sk-your-openai-api-key
```

**Rate Limiting:**
```bash
RATELIMIT_OPENAI_RPM=60    # Requests per minute
RATELIMIT_OPENAI_TPM=90000 # Tokens per minute
BULKHEAD_OPENAI_CONCURRENT=10
```

**Default Model:** `gpt-4o-mini`

**Usage Example:**
```python
from test_ai.api_clients.openai_client import OpenAIClient

client = OpenAIClient()
response = client.generate_completion(
    prompt="Summarize this document",
    model="gpt-4o-mini",
    temperature=0.7
)
```

### Anthropic (Claude)

Anthropic integration supports both API mode (direct API calls) and CLI mode (subprocess).

**Required Environment Variables:**
```bash
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
CLAUDE_MODE=api           # 'api' or 'cli'
CLAUDE_CLI_PATH=claude    # Path to CLI (only for cli mode)
```

**Rate Limiting:**
```bash
RATELIMIT_ANTHROPIC_RPM=60
BULKHEAD_ANTHROPIC_CONCURRENT=10
```

**Default Model:** `claude-sonnet-4-20250514`

**Agent Roles:** The Claude client supports specialized agent roles:
- `planner` - Strategic planning and task breakdown
- `builder` - Code implementation
- `tester` - Test creation
- `reviewer` - Code review
- `data_analyst` - SQL, pandas, visualizations
- `devops` - Docker, K8s, CI/CD, IaC
- `security_auditor` - Security review, OWASP, compliance
- `migrator` - Framework/language migrations
- `model_builder` - 3D modeling, game dev

**Custom Role Prompts:**
Create `config/agent_prompts.json` to override default prompts:
```json
{
  "builder": {
    "system_prompt": "You are a code implementation agent..."
  }
}
```

### GitHub

GitHub integration enables issue creation, file commits, and repository operations.

**Required Environment Variables:**
```bash
GITHUB_TOKEN=ghp_your-github-token
```

**Required Token Scopes:**
- `repo` - Full repository access
- `workflow` - GitHub Actions access (optional)

**Rate Limiting:**
```bash
RATELIMIT_GITHUB_RPM=30
BULKHEAD_GITHUB_CONCURRENT=5
```

**Caching:** Repository metadata is cached for 5 minutes.

### Notion

Notion integration enables database queries, page creation, and content management.

**Required Environment Variables:**
```bash
NOTION_TOKEN=secret_your-notion-token
```

**Setup Steps:**
1. Create a Notion integration at https://www.notion.so/my-integrations
2. Copy the "Internal Integration Token"
3. Share databases/pages with your integration

**Rate Limiting:**
```bash
RATELIMIT_NOTION_RPM=30
BULKHEAD_NOTION_CONCURRENT=3
```

**Caching:** Database schemas are cached for 1 hour.

### Gmail

Gmail integration enables email reading via OAuth2.

**Required Environment Variables:**
```bash
GMAIL_CREDENTIALS_PATH=path/to/credentials.json
```

**Setup Steps:**
1. Create a Google Cloud project
2. Enable Gmail API
3. Create OAuth 2.0 credentials (Desktop application)
4. Download `credentials.json` and set path

**OAuth Scopes Required:**
- `https://www.googleapis.com/auth/gmail.readonly`

**Rate Limiting:**
```bash
RATELIMIT_GMAIL_RPM=30
BULKHEAD_GMAIL_CONCURRENT=5
```

### Slack

Slack integration enables notifications, workflow updates, and approval requests.

**Setup:**
```python
from test_ai.api_clients.slack_client import SlackClient

client = SlackClient(token="xoxb-your-slack-bot-token")
client.send_message(
    channel="#workflows",
    text="Workflow completed!",
    message_type=MessageType.SUCCESS
)
```

**Features:**
- Message types: INFO, SUCCESS, WARNING, ERROR, APPROVAL_REQUEST
- Color-coded attachments
- Block Kit support
- Interactive approval buttons
- Thread replies

---

## Security Settings

### Authentication

Gorgon uses token-based authentication with configurable credentials.

**Secure Secret Key:**
```bash
# Generate a secure key (minimum 32 characters, 384 bits recommended)
python -c "import secrets; print(secrets.token_urlsafe(48))"

# Set in .env
SECRET_KEY=your-generated-secure-key-here
```

**API Credentials:**
```bash
# Generate password hash
python -c "from hashlib import sha256; print(sha256(b'your_password').hexdigest())"

# Set credentials (comma-separated user:hash pairs)
API_CREDENTIALS=admin:5e884898da28047d9...,user1:abc123...
```

**Demo Authentication (Development Only):**
```bash
ALLOW_DEMO_AUTH=true  # Allows any username with password 'demo'
```

### Production Mode

When `PRODUCTION=true`, the following are enforced:

1. **SECRET_KEY** must be:
   - Not the default value (`change-me-in-production`)
   - At least 32 characters long

2. **DATABASE_URL** must be changed from the default SQLite path

3. **DEBUG** must be `false`

4. **ALLOW_DEMO_AUTH** must be `false`

### Brute Force Protection

The brute force protection system includes:

- **IP-based rate limiting** with configurable limits
- **Exponential backoff** on repeated blocks
- **Extended blocks** for repeated failed attempts
- **Automatic cleanup** of expired records

**Auth Paths Protected:**
- `/auth/`
- `/login`
- `/token`
- `/api/token`

**Configuration:**
```bash
BRUTE_FORCE_MAX_ATTEMPTS_PER_MINUTE=60
BRUTE_FORCE_MAX_ATTEMPTS_PER_HOUR=300
BRUTE_FORCE_MAX_AUTH_ATTEMPTS_PER_MINUTE=5
BRUTE_FORCE_MAX_AUTH_ATTEMPTS_PER_HOUR=20
BRUTE_FORCE_INITIAL_BLOCK_SECONDS=60
BRUTE_FORCE_MAX_BLOCK_SECONDS=3600
```

### Request Size Limits

Protect against large payload attacks:

```bash
REQUEST_MAX_BODY_SIZE=10485760    # 10MB
REQUEST_MAX_JSON_SIZE=1048576     # 1MB
REQUEST_MAX_FORM_SIZE=52428800    # 50MB
```

### Shell Execution Security

Control shell command execution:

```bash
SHELL_TIMEOUT_SECONDS=300
SHELL_MAX_OUTPUT_BYTES=10485760

# Restrict to specific commands (empty = all allowed)
SHELL_ALLOWED_COMMANDS=ls,cat,grep,find,git
```

---

## Database Configuration

### SQLite (Development)

Default configuration for local development:

```bash
DATABASE_URL=sqlite:///gorgon-state.db
```

### PostgreSQL (Production)

For production deployments:

```bash
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Docker Compose variables
POSTGRES_USER=gorgon
POSTGRES_PASSWORD=secure-password-here
POSTGRES_DB=gorgon
POSTGRES_PORT=5432
```

### Connection String Formats

| Database | Format |
|----------|--------|
| SQLite | `sqlite:///relative/path.db` or `sqlite:////absolute/path.db` |
| PostgreSQL | `postgresql://user:pass@host:port/dbname` |
| PostgreSQL (async) | `postgresql+asyncpg://user:pass@host:port/dbname` |

---

## Logging Configuration

### Log Levels

| Level | Description |
|-------|-------------|
| `DEBUG` | Detailed diagnostic information |
| `INFO` | General operational information |
| `WARNING` | Potential issues or deprecation notices |
| `ERROR` | Errors that don't halt execution |
| `CRITICAL` | Severe errors requiring immediate attention |

### Log Formats

**Text Format (Default):**
```
2024-01-15 10:30:45 - test_ai.api - INFO - Request processed
```

**JSON Format (Production):**
```json
{
  "timestamp": "2024-01-15T10:30:45.123456+00:00",
  "level": "INFO",
  "logger": "test_ai.api",
  "message": "Request processed",
  "trace_id": "abc123...",
  "span_id": "def456...",
  "duration_ms": 45.2
}
```

### Log Sanitization

When `SANITIZE_LOGS=true`, the following are redacted:
- API keys
- Tokens
- Passwords
- Secrets

### Distributed Tracing

Gorgon supports W3C Trace Context compatible tracing:

```bash
TRACING_ENABLED=true
TRACING_SERVICE_NAME=gorgon-api
TRACING_SAMPLE_RATE=1.0  # Sample all requests (reduce for high traffic)
```

**Trace Context Propagation:**
- Generates 128-bit trace IDs (W3C compliant)
- Generates 64-bit span IDs
- Supports `traceparent` header propagation

---

## Example Configurations

### Development Environment

`.env`:
```bash
# Development - minimal config
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=sk-ant-your-key

DEBUG=true
LOG_LEVEL=DEBUG
LOG_FORMAT=text
ALLOW_DEMO_AUTH=true

DATABASE_URL=sqlite:///gorgon-state.db
```

### Small Team (deploy/templates/small-team/.env.example)

```bash
# Small Team Configuration
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=

DASHBOARD_PORT=8501
LOG_LEVEL=INFO
GORGON_ENV=development
```

### Medium Team (deploy/templates/medium-team/.env.example)

```bash
# Medium Team Configuration
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=

# PostgreSQL
POSTGRES_USER=gorgon
POSTGRES_PASSWORD=CHANGE_ME_SECURE_PASSWORD
POSTGRES_DB=gorgon
POSTGRES_PORT=5432

# Redis
REDIS_PORT=6379

# Dashboard
DASHBOARD_PORT=8501

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
GRAFANA_PASSWORD=CHANGE_ME_ADMIN_PASSWORD

LOG_LEVEL=INFO
GORGON_ENV=production
```

### Enterprise/Kubernetes (deploy/templates/enterprise/configmap.yaml)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: gorgon-config
  namespace: gorgon
  labels:
    app.kubernetes.io/name: gorgon
data:
  GORGON_ENV: "production"
  LOG_LEVEL: "INFO"
  METRICS_ENABLED: "true"
  AUDIT_LOGGING: "true"
```

### Production Environment

`.env`:
```bash
# Production - secure config
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=sk-ant-your-key
GITHUB_TOKEN=ghp_your-token
NOTION_TOKEN=secret_your-token

# Security (REQUIRED - generate with: python -c "import secrets; print(secrets.token_urlsafe(48))")
SECRET_KEY=your-64-char-cryptographically-secure-key-here
PRODUCTION=true
DEBUG=false
ALLOW_DEMO_AUTH=false

# API Credentials (generate hash with: python -c "from hashlib import sha256; print(sha256(b'password').hexdigest())")
API_CREDENTIALS=admin:5e884898da28047d...

# Database
DATABASE_URL=postgresql://gorgon:secure-password@db.example.com:5432/gorgon

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
SANITIZE_LOGS=true

# Tracing
TRACING_ENABLED=true
TRACING_SERVICE_NAME=gorgon-api
TRACING_SAMPLE_RATE=0.1  # Sample 10% of requests

# Rate Limiting (adjust based on your API limits)
RATELIMIT_OPENAI_RPM=60
RATELIMIT_ANTHROPIC_RPM=60

# Brute Force Protection
BRUTE_FORCE_MAX_AUTH_ATTEMPTS_PER_MINUTE=5
BRUTE_FORCE_MAX_AUTH_ATTEMPTS_PER_HOUR=20
```

### High-Volume Production

```bash
# High-volume settings
RATELIMIT_OPENAI_RPM=100
RATELIMIT_OPENAI_TPM=150000
BULKHEAD_OPENAI_CONCURRENT=20
BULKHEAD_ANTHROPIC_CONCURRENT=20

BRUTE_FORCE_MAX_ATTEMPTS_PER_MINUTE=100
BRUTE_FORCE_MAX_ATTEMPTS_PER_HOUR=500

TRACING_SAMPLE_RATE=0.01  # Sample 1% to reduce overhead
```

---

## Configuration Validation

### Security Validation

When `PRODUCTION=true` or `REQUIRE_SECURE_CONFIG=true`, the application validates:

1. SECRET_KEY is not the insecure default
2. SECRET_KEY is at least 32 characters
3. DATABASE_URL is not the default SQLite path
4. DEBUG is disabled in production
5. ALLOW_DEMO_AUTH is disabled in production

### Validation Errors

If validation fails in production mode, the application will not start and will display:

```
ValueError: Insecure configuration not allowed (production mode enabled):
  - SECRET_KEY is using insecure default value. Set SECRET_KEY environment variable...
  - DATABASE_URL is using default SQLite path. Set DATABASE_URL environment variable...
```

### Development Warnings

In development mode, insecure configurations generate warnings:

```
Security: SECRET_KEY is using insecure default value...
```

---

## Troubleshooting

### Common Issues

**"Claude Code client not configured"**
- Ensure `ANTHROPIC_API_KEY` is set
- If using CLI mode, verify `claude` command is in PATH

**"Notion client not configured"**
- Ensure `NOTION_TOKEN` is set
- Verify the integration has access to target databases/pages

**"Rate limit exceeded"**
- Reduce request frequency
- Increase `RATELIMIT_*_RPM` values
- Check API provider rate limits

**"Bulkhead full"**
- Too many concurrent requests
- Increase `BULKHEAD_*_CONCURRENT` values
- Implement request queuing

**"Insecure configuration not allowed"**
- In production mode, all security requirements must be met
- Generate a proper SECRET_KEY
- Configure DATABASE_URL for production database
