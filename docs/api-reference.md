# Gorgon API Reference

Complete API documentation for the Gorgon AI Workflow Orchestrator.

## Overview

- **Base URL**: `http://localhost:8000` (default)
- **API Version**: `v1`
- **Content-Type**: `application/json`

All API endpoints (except health checks and webhook triggers) are prefixed with `/v1`.

---

## Authentication

Gorgon uses token-based authentication with Bearer tokens.

### Obtaining a Token

**POST** `/v1/auth/login`

Authenticate and receive an access token. Rate limited to 5 requests/minute per IP.

**Authentication Methods** (in priority order):
1. Configured credentials via `API_CREDENTIALS` environment variable
2. Demo auth (password='demo') if `ALLOW_DEMO_AUTH=true` (development only)

**Configure Credentials:**
```bash
# Set API_CREDENTIALS as comma-separated user:sha256hash pairs
API_CREDENTIALS='user1:sha256hash1,user2:sha256hash2'

# Generate a password hash:
python -c "from hashlib import sha256; print(sha256(b'your_password').hexdigest())"
```

**Request Body:**
```json
{
  "user_id": "string",
  "password": "string"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Response (401 Unauthorized):**
```json
{
  "error": {
    "error_code": "AUTH_FAILED",
    "message": "Invalid credentials",
    "details": {},
    "request_id": "abc12345"
  }
}
```

### Using the Token

Include the token in the `Authorization` header for all authenticated requests:

```
Authorization: Bearer <access_token>
```

**Token Configuration:**
- Default expiration: 60 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`)

---

## Error Responses

All errors follow a consistent format:

```json
{
  "error": {
    "error_code": "ERROR_CODE",
    "message": "Human-readable description",
    "details": {},
    "request_id": "abc12345"
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `AUTH_FAILED` | 401 | Invalid or missing authentication |
| `UNAUTHORIZED` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION` | 400/422 | Invalid request or validation error |
| `CONFLICT` | 409 | Resource conflict |
| `RATE_LIMITED` | 429 | Rate limit exceeded |
| `INTERNAL_ERROR` | 500 | Server error |
| `API_ERROR` | 502 | External service error |
| `TIMEOUT` | 504 | Request timeout |

### Rate Limit Response

```json
{
  "error": {
    "error_code": "RATE_LIMITED",
    "message": "Rate limit exceeded",
    "details": {"limit": "10/minute"},
    "request_id": "abc12345"
  },
  "retry_after": 45
}
```

The `Retry-After` header is also included in the response.

---

## Rate Limiting

| Endpoint | Limit |
|----------|-------|
| `POST /v1/auth/login` | 5/minute |
| `POST /v1/workflows/execute` | 10/minute |
| `POST /v1/yaml-workflows/execute` | 10/minute |
| `POST /v1/workflows/{id}/execute` | 10/minute |
| `POST /v1/jobs` | 20/minute |
| `POST /hooks/{webhook_id}` | 30/minute |

Rate limits are per-IP address.

---

## Workflows

### List Workflows

**GET** `/v1/workflows`

List all workflow definitions.

**Response (200 OK):**
```json
[
  {
    "id": "my-workflow",
    "name": "My Workflow",
    "description": "Workflow description",
    "version": "1.0.0"
  }
]
```

### Get Workflow

**GET** `/v1/workflows/{workflow_id}`

Get a specific workflow definition.

**Path Parameters:**
- `workflow_id` (string, required): Workflow identifier

**Response (200 OK):**
```json
{
  "id": "my-workflow",
  "name": "My Workflow",
  "description": "Workflow description",
  "version": "1.0.0",
  "steps": [...],
  "variables": {}
}
```

### Create Workflow

**POST** `/v1/workflows`

Create a new workflow.

**Request Body:**
```json
{
  "id": "my-workflow",
  "name": "My Workflow",
  "description": "Workflow description",
  "steps": [
    {
      "id": "step-1",
      "type": "ai-prompt",
      "params": {...}
    }
  ],
  "variables": {}
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "workflow_id": "my-workflow"
}
```

### Execute Workflow (Synchronous)

**POST** `/v1/workflows/execute`

Execute a workflow synchronously. Rate limited to 10/minute.

**Request Body:**
```json
{
  "workflow_id": "my-workflow",
  "variables": {
    "input_text": "Hello world"
  }
}
```

**Response (200 OK):**
```json
{
  "status": "completed",
  "workflow_id": "my-workflow",
  "outputs": {...},
  "errors": []
}
```

### Start Workflow Execution (Async)

**POST** `/v1/workflows/{workflow_id}/execute`

Start a new workflow execution asynchronously. Rate limited to 10/minute.

**Path Parameters:**
- `workflow_id` (string, required): Workflow identifier

**Request Body:**
```json
{
  "variables": {
    "input_text": "Hello world"
  }
}
```

**Response (200 OK):**
```json
{
  "execution_id": "exec-abc123",
  "workflow_id": "my-workflow",
  "workflow_name": "My Workflow",
  "status": "running",
  "poll_url": "/v1/executions/exec-abc123"
}
```

---

## YAML Workflows

YAML workflows are loaded from the `workflows/` directory.

### List YAML Workflows

**GET** `/v1/yaml-workflows`

List all YAML workflow definitions.

**Response (200 OK):**
```json
{
  "workflows": [
    {
      "id": "decision-support",
      "name": "Decision Support",
      "description": "AI-powered decision analysis",
      "version": "1.0",
      "path": "/path/to/decision-support.yaml"
    }
  ]
}
```

### Get YAML Workflow

**GET** `/v1/yaml-workflows/{workflow_id}`

Get a specific YAML workflow definition.

**Response (200 OK):**
```json
{
  "id": "decision-support",
  "name": "Decision Support",
  "description": "AI-powered decision analysis",
  "version": "1.0",
  "inputs": {
    "question": {"type": "string", "required": true}
  },
  "outputs": ["recommendation"],
  "steps": [
    {
      "id": "analyze",
      "type": "ai-prompt",
      "params": {...}
    }
  ]
}
```

### Execute YAML Workflow

**POST** `/v1/yaml-workflows/execute`

Execute a YAML workflow. Rate limited to 10/minute.

**Request Body:**
```json
{
  "workflow_id": "decision-support",
  "inputs": {
    "question": "Should I adopt microservices?"
  }
}
```

**Response (200 OK):**
```json
{
  "id": "exec-xyz789",
  "workflow_id": "decision-support",
  "workflow_name": "Decision Support",
  "status": "completed",
  "started_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:30:45Z",
  "total_duration_ms": 45123,
  "total_tokens": 1250,
  "outputs": {
    "recommendation": "Consider these factors..."
  },
  "steps": [
    {
      "step_id": "analyze",
      "status": "completed",
      "duration_ms": 45000,
      "tokens_used": 1250
    }
  ],
  "error": null
}
```

---

## Executions

Track and manage workflow executions.

### List Executions

**GET** `/v1/executions`

List workflow executions with pagination.

**Query Parameters:**
- `page` (int, default: 1): Page number
- `page_size` (int, default: 20): Items per page
- `status` (string, optional): Filter by status (`pending`, `running`, `paused`, `completed`, `failed`, `cancelled`)
- `workflow_id` (string, optional): Filter by workflow ID

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": "exec-abc123",
      "workflow_id": "my-workflow",
      "workflow_name": "My Workflow",
      "status": "completed",
      "started_at": "2024-01-15T10:30:00Z",
      "completed_at": "2024-01-15T10:30:45Z",
      "current_step": null,
      "progress": 100,
      "error": null
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

### Get Execution

**GET** `/v1/executions/{execution_id}`

Get a specific execution with logs and metrics.

**Response (200 OK):**
```json
{
  "id": "exec-abc123",
  "workflow_id": "my-workflow",
  "workflow_name": "My Workflow",
  "status": "completed",
  "started_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:30:45Z",
  "current_step": null,
  "progress": 100,
  "checkpoint_id": null,
  "variables": {"input": "test"},
  "error": null,
  "logs": [
    {
      "id": 1,
      "execution_id": "exec-abc123",
      "timestamp": "2024-01-15T10:30:00Z",
      "level": "info",
      "message": "Starting workflow",
      "step_id": null,
      "metadata": null
    }
  ],
  "metrics": {
    "execution_id": "exec-abc123",
    "total_tokens": 1250,
    "total_cost_cents": 5,
    "duration_ms": 45123,
    "steps_completed": 3,
    "steps_failed": 0
  }
}
```

### Get Execution Logs

**GET** `/v1/executions/{execution_id}/logs`

Get logs for an execution.

**Query Parameters:**
- `limit` (int, default: 100): Maximum logs to return
- `level` (string, optional): Filter by log level (`debug`, `info`, `warning`, `error`)

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "execution_id": "exec-abc123",
    "timestamp": "2024-01-15T10:30:00Z",
    "level": "info",
    "message": "Starting workflow",
    "step_id": null,
    "metadata": null
  }
]
```

### Pause Execution

**POST** `/v1/executions/{execution_id}/pause`

Pause a running execution.

**Response (200 OK):**
```json
{
  "status": "success",
  "execution_id": "exec-abc123",
  "execution_status": "paused"
}
```

### Resume Execution

**POST** `/v1/executions/{execution_id}/resume`

Resume a paused execution.

**Response (200 OK):**
```json
{
  "status": "success",
  "execution_id": "exec-abc123",
  "execution_status": "running"
}
```

### Cancel Execution

**POST** `/v1/executions/{execution_id}/cancel`

Cancel a running or paused execution.

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Execution cancelled"
}
```

### Delete Execution

**DELETE** `/v1/executions/{execution_id}`

Delete a completed/failed/cancelled execution.

**Response (200 OK):**
```json
{
  "status": "success"
}
```

### Cleanup Executions

**POST** `/v1/executions/cleanup`

Remove old completed/failed/cancelled executions.

**Query Parameters:**
- `max_age_hours` (int, default: 168): Delete executions older than this (7 days)

**Response (200 OK):**
```json
{
  "status": "success",
  "deleted": 15
}
```

---

## Schedules

Schedule workflows for automated execution.

### List Schedules

**GET** `/v1/schedules`

List all schedules.

**Response (200 OK):**
```json
[
  {
    "id": "daily-report",
    "name": "Daily Report",
    "workflow_id": "report-workflow",
    "schedule_type": "cron",
    "status": "active",
    "last_run": "2024-01-15T06:00:00Z",
    "next_run": "2024-01-16T06:00:00Z",
    "run_count": 42
  }
]
```

### Get Schedule

**GET** `/v1/schedules/{schedule_id}`

Get a specific schedule.

**Response (200 OK):**
```json
{
  "id": "daily-report",
  "workflow_id": "report-workflow",
  "name": "Daily Report",
  "description": "Generate daily analytics report",
  "schedule_type": "cron",
  "cron_config": {
    "minute": "0",
    "hour": "6",
    "day": "*",
    "month": "*",
    "day_of_week": "*"
  },
  "interval_config": null,
  "variables": {"format": "pdf"},
  "status": "active",
  "created_at": "2024-01-01T00:00:00Z",
  "last_run": "2024-01-15T06:00:00Z",
  "next_run": "2024-01-16T06:00:00Z",
  "run_count": 42
}
```

### Create Schedule

**POST** `/v1/schedules`

Create a new schedule.

**Request Body (Cron):**
```json
{
  "id": "daily-report",
  "workflow_id": "report-workflow",
  "name": "Daily Report",
  "description": "Generate daily analytics report",
  "schedule_type": "cron",
  "cron_config": {
    "minute": "0",
    "hour": "6",
    "day": "*",
    "month": "*",
    "day_of_week": "*"
  },
  "variables": {"format": "pdf"},
  "status": "active"
}
```

**Request Body (Interval):**
```json
{
  "id": "health-check",
  "workflow_id": "health-workflow",
  "name": "Health Check",
  "description": "Run health check every 30 minutes",
  "schedule_type": "interval",
  "interval_config": {
    "seconds": 0,
    "minutes": 30,
    "hours": 0,
    "days": 0
  },
  "variables": {},
  "status": "active"
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "schedule_id": "daily-report"
}
```

### Update Schedule

**PUT** `/v1/schedules/{schedule_id}`

Update an existing schedule.

**Request Body:** Same as create

**Response (200 OK):**
```json
{
  "status": "success",
  "schedule_id": "daily-report"
}
```

### Delete Schedule

**DELETE** `/v1/schedules/{schedule_id}`

Delete a schedule.

**Response (200 OK):**
```json
{
  "status": "success"
}
```

### Pause Schedule

**POST** `/v1/schedules/{schedule_id}/pause`

Pause a schedule.

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Schedule paused"
}
```

### Resume Schedule

**POST** `/v1/schedules/{schedule_id}/resume`

Resume a paused schedule.

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Schedule resumed"
}
```

### Trigger Schedule

**POST** `/v1/schedules/{schedule_id}/trigger`

Manually trigger a scheduled workflow immediately.

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Workflow triggered"
}
```

### Get Schedule History

**GET** `/v1/schedules/{schedule_id}/history`

Get execution history for a schedule.

**Query Parameters:**
- `limit` (int, default: 10): Maximum entries to return

**Response (200 OK):**
```json
[
  {
    "schedule_id": "daily-report",
    "workflow_id": "report-workflow",
    "executed_at": "2024-01-15T06:00:00Z",
    "status": "completed",
    "duration_seconds": 45.5,
    "error": null
  }
]
```

---

## Webhooks

Event-driven workflow triggers.

### List Webhooks

**GET** `/v1/webhooks`

List all webhooks (secrets redacted).

**Response (200 OK):**
```json
[
  {
    "id": "github-push",
    "name": "GitHub Push Handler",
    "workflow_id": "ci-workflow",
    "status": "active",
    "last_triggered": "2024-01-15T14:30:00Z",
    "trigger_count": 156
  }
]
```

### Get Webhook

**GET** `/v1/webhooks/{webhook_id}`

Get a specific webhook (secret redacted).

**Response (200 OK):**
```json
{
  "id": "github-push",
  "name": "GitHub Push Handler",
  "description": "Trigger CI on push events",
  "workflow_id": "ci-workflow",
  "secret": "***REDACTED***",
  "payload_mappings": [
    {
      "source_path": "repository.full_name",
      "target_variable": "repo_name",
      "default": null
    }
  ],
  "static_variables": {"notify": true},
  "status": "active",
  "created_at": "2024-01-01T00:00:00Z",
  "last_triggered": "2024-01-15T14:30:00Z",
  "trigger_count": 156
}
```

### Create Webhook

**POST** `/v1/webhooks`

Create a new webhook. Returns the secret (only shown at creation time).

**Request Body:**
```json
{
  "id": "github-push",
  "name": "GitHub Push Handler",
  "description": "Trigger CI on push events",
  "workflow_id": "ci-workflow",
  "payload_mappings": [
    {
      "source_path": "repository.full_name",
      "target_variable": "repo_name",
      "default": "unknown"
    },
    {
      "source_path": "pusher.name",
      "target_variable": "author",
      "default": null
    }
  ],
  "static_variables": {"notify": true},
  "status": "active"
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "webhook_id": "github-push",
  "secret": "xK9mN2pQ_rS3tU4vW5xY6zA7bC8dE9fG0hI1jK2lM3n",
  "trigger_url": "/hooks/github-push"
}
```

### Update Webhook

**PUT** `/v1/webhooks/{webhook_id}`

Update an existing webhook.

**Request Body:** Same as create (secret is preserved if empty)

**Response (200 OK):**
```json
{
  "status": "success",
  "webhook_id": "github-push"
}
```

### Delete Webhook

**DELETE** `/v1/webhooks/{webhook_id}`

Delete a webhook.

**Response (200 OK):**
```json
{
  "status": "success"
}
```

### Regenerate Webhook Secret

**POST** `/v1/webhooks/{webhook_id}/regenerate-secret`

Regenerate the secret for a webhook.

**Response (200 OK):**
```json
{
  "status": "success",
  "secret": "newSecretHere_xK9mN2pQ_rS3tU4vW5xY6zA7b"
}
```

### Get Webhook History

**GET** `/v1/webhooks/{webhook_id}/history`

Get trigger history for a webhook.

**Query Parameters:**
- `limit` (int, default: 10): Maximum entries to return

**Response (200 OK):**
```json
[
  {
    "webhook_id": "github-push",
    "workflow_id": "ci-workflow",
    "triggered_at": "2024-01-15T14:30:00Z",
    "source_ip": "140.82.112.10",
    "payload_size": 2048,
    "status": "success",
    "duration_seconds": 12.5,
    "error": null
  }
]
```

### Trigger Webhook (Public)

**POST** `/hooks/{webhook_id}`

Public endpoint to trigger a webhook. Rate limited to 30/minute per IP.

**Authentication:** HMAC-SHA256 signature in `X-Webhook-Signature` header (not Bearer token).

**Generate Signature:**
```python
import hmac
import hashlib
import json

payload = json.dumps({"event": "push", "data": {...}}).encode()
signature = "sha256=" + hmac.new(
    secret.encode(),
    payload,
    hashlib.sha256
).hexdigest()
```

**Headers:**
```
Content-Type: application/json
X-Webhook-Signature: sha256=<hex_digest>
```

**Request Body:**
```json
{
  "event": "push",
  "repository": {
    "full_name": "user/repo"
  },
  "pusher": {
    "name": "johndoe"
  }
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "webhook_id": "github-push",
  "workflow_id": "ci-workflow",
  "duration_seconds": 12.5,
  "result": {...},
  "error": null
}
```

---

## Jobs

Async workflow execution with status polling.

### Submit Job

**POST** `/v1/jobs`

Submit a workflow for async execution. Rate limited to 20/minute.

**Request Body:**
```json
{
  "workflow_id": "my-workflow",
  "variables": {"input": "test"}
}
```

**Response (200 OK):**
```json
{
  "status": "submitted",
  "job_id": "job-abc123",
  "workflow_id": "my-workflow",
  "poll_url": "/jobs/job-abc123"
}
```

### List Jobs

**GET** `/v1/jobs`

List jobs with optional filtering.

**Query Parameters:**
- `status` (string, optional): Filter by status (`pending`, `running`, `completed`, `failed`, `cancelled`)
- `workflow_id` (string, optional): Filter by workflow ID
- `limit` (int, default: 50): Maximum jobs to return

**Response (200 OK):**
```json
[
  {
    "id": "job-abc123",
    "workflow_id": "my-workflow",
    "status": "completed",
    "created_at": "2024-01-15T10:30:00Z",
    "started_at": "2024-01-15T10:30:01Z",
    "completed_at": "2024-01-15T10:30:45Z",
    "variables": {"input": "test"},
    "result": {...},
    "error": null,
    "progress": null
  }
]
```

### Get Job

**GET** `/v1/jobs/{job_id}`

Get job status and result.

**Response (200 OK):**
```json
{
  "id": "job-abc123",
  "workflow_id": "my-workflow",
  "status": "completed",
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:01Z",
  "completed_at": "2024-01-15T10:30:45Z",
  "variables": {"input": "test"},
  "result": {
    "status": "completed",
    "outputs": {...}
  },
  "error": null,
  "progress": null
}
```

### Get Job Stats

**GET** `/v1/jobs/stats`

Get job statistics.

**Response (200 OK):**
```json
{
  "total": 150,
  "pending": 2,
  "running": 1,
  "completed": 140,
  "failed": 5,
  "cancelled": 2
}
```

### Cancel Job

**POST** `/v1/jobs/{job_id}/cancel`

Cancel a pending or running job.

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Job cancelled"
}
```

### Delete Job

**DELETE** `/v1/jobs/{job_id}`

Delete a completed/failed/cancelled job.

**Response (200 OK):**
```json
{
  "status": "success"
}
```

### Cleanup Jobs

**POST** `/v1/jobs/cleanup`

Remove old completed/failed/cancelled jobs.

**Query Parameters:**
- `max_age_hours` (int, default: 24): Delete jobs older than this

**Response (200 OK):**
```json
{
  "status": "success",
  "deleted": 25
}
```

---

## Workflow Versions

Version control for workflow definitions.

### List Workflow Versions

**GET** `/v1/workflows/{workflow_name}/versions`

List all versions of a workflow.

**Query Parameters:**
- `limit` (int, default: 50): Maximum versions to return
- `offset` (int, default: 0): Number of versions to skip

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "workflow_name": "my-workflow",
    "version": "1.2.0",
    "version_major": 1,
    "version_minor": 2,
    "version_patch": 0,
    "content": "name: My Workflow\n...",
    "content_hash": "abc123...",
    "description": "Added new feature",
    "author": "johndoe",
    "created_at": "2024-01-15T10:30:00Z",
    "is_active": true,
    "metadata": {}
  }
]
```

### Get Workflow Version

**GET** `/v1/workflows/{workflow_name}/versions/{version}`

Get a specific workflow version.

**Response (200 OK):**
```json
{
  "id": 1,
  "workflow_name": "my-workflow",
  "version": "1.2.0",
  "version_major": 1,
  "version_minor": 2,
  "version_patch": 0,
  "content": "name: My Workflow\n...",
  "content_hash": "abc123...",
  "description": "Added new feature",
  "author": "johndoe",
  "created_at": "2024-01-15T10:30:00Z",
  "is_active": true,
  "metadata": {}
}
```

### Save Workflow Version

**POST** `/v1/workflows/{workflow_name}/versions`

Save a new workflow version.

**Request Body:**
```json
{
  "content": "name: My Workflow\nversion: 1.3.0\n...",
  "version": "1.3.0",
  "description": "Added validation step",
  "author": "johndoe",
  "activate": true
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "workflow_name": "my-workflow",
  "version": "1.3.0",
  "is_active": true
}
```

### Compare Workflow Versions

**GET** `/v1/workflows/{workflow_name}/versions/compare`

Compare two workflow versions.

**Query Parameters:**
- `from_version` (string, required): Base version for comparison
- `to_version` (string, required): Target version for comparison

**Response (200 OK):**
```json
{
  "workflow_name": "my-workflow",
  "from_version": "1.2.0",
  "to_version": "1.3.0",
  "has_changes": true,
  "added_lines": 15,
  "removed_lines": 3,
  "changed_sections": ["steps", "outputs"],
  "unified_diff": "--- old\n+++ new\n@@ -1,5 +1,8 @@\n..."
}
```

### Activate Workflow Version

**POST** `/v1/workflows/{workflow_name}/versions/{version}/activate`

Activate a specific workflow version.

**Response (200 OK):**
```json
{
  "status": "success",
  "workflow_name": "my-workflow",
  "active_version": "1.2.0"
}
```

### Rollback Workflow

**POST** `/v1/workflows/{workflow_name}/rollback`

Rollback to the previous workflow version.

**Response (200 OK):**
```json
{
  "status": "success",
  "workflow_name": "my-workflow",
  "rolled_back_to": "1.1.0"
}
```

### Delete Workflow Version

**DELETE** `/v1/workflows/{workflow_name}/versions/{version}`

Delete a workflow version (cannot delete active version).

**Response (200 OK):**
```json
{
  "status": "success"
}
```

### List Versioned Workflows

**GET** `/v1/workflow-versions`

List all workflows with version information.

**Response (200 OK):**
```json
[
  {
    "workflow_name": "my-workflow",
    "latest_version": "1.3.0",
    "active_version": "1.2.0",
    "total_versions": 5
  }
]
```

---

## Prompt Templates

### List Prompts

**GET** `/v1/prompts`

List all prompt templates.

**Response (200 OK):**
```json
[
  {
    "id": "code-review",
    "name": "Code Review",
    "description": "Review code for quality and security"
  }
]
```

### Get Prompt

**GET** `/v1/prompts/{template_id}`

Get a specific prompt template.

**Response (200 OK):**
```json
{
  "id": "code-review",
  "name": "Code Review",
  "description": "Review code for quality and security",
  "template": "Review the following code:\n{{code}}\n..."
}
```

### Create Prompt

**POST** `/v1/prompts`

Create a new prompt template.

**Request Body:**
```json
{
  "id": "code-review",
  "name": "Code Review",
  "description": "Review code for quality and security",
  "template": "Review the following code:\n{{code}}\n..."
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "template_id": "code-review"
}
```

### Delete Prompt

**DELETE** `/v1/prompts/{template_id}`

Delete a prompt template.

**Response (200 OK):**
```json
{
  "status": "success"
}
```

---

## Health Endpoints

Health check endpoints do not require authentication.

### Basic Health Check

**GET** `/health`

Basic liveness check. Returns 200 if the process is running.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Liveness Probe

**GET** `/health/live`

Kubernetes liveness probe endpoint.

**Response (200 OK):**
```json
{
  "status": "alive"
}
```

### Readiness Probe

**GET** `/health/ready`

Kubernetes readiness probe. Returns 503 if not ready or shutting down.

**Response (200 OK):**
```json
{
  "status": "ready"
}
```

**Response (503 Service Unavailable):**
```json
{
  "status": "not_ready",
  "reason": "Application not initialized"
}
```

### Database Health Check

**GET** `/health/db`

Check database connectivity and migration status.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "database": "connected",
  "backend": "postgresql",
  "migrations": {
    "applied": ["001_initial", "002_add_versions"],
    "pending": []
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Full Health Check

**GET** `/health/full`

Comprehensive health check with all subsystem statuses.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "uptime_seconds": 86400,
  "application": {
    "ready": true,
    "shutting_down": false,
    "active_requests": 5
  },
  "database": {
    "status": "connected",
    "backend": "postgresql"
  },
  "circuit_breakers": {
    "openai": {
      "state": "closed",
      "failure_count": 0
    },
    "anthropic": {
      "state": "closed",
      "failure_count": 0
    }
  },
  "api_clients": {...},
  "security": {
    "brute_force": {
      "blocked_ips": 0,
      "recent_blocks": []
    }
  }
}
```

---

## Metrics

### Prometheus Metrics

**GET** `/metrics`

Prometheus metrics endpoint for scraping.

**Response (200 OK, text/plain):**
```
# TYPE gorgon_app_ready gauge
gorgon_app_ready 1
# TYPE gorgon_app_shutting_down gauge
gorgon_app_shutting_down 0
# TYPE gorgon_active_requests gauge
gorgon_active_requests 5
# TYPE gorgon_uptime_seconds counter
gorgon_uptime_seconds 86400.00
# TYPE gorgon_circuit_breaker_openai_state gauge
gorgon_circuit_breaker_openai_state 0
# TYPE gorgon_circuit_breaker_openai_failures gauge
gorgon_circuit_breaker_openai_failures 0
...
```

---

## WebSocket

Real-time execution updates via WebSocket.

### Connect

**WebSocket** `ws://host/ws/executions?token=<jwt>`

Authenticate via query parameter.

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/executions?token=eyJ...');
```

### Protocol

**Client Messages:**
- `subscribe`: Subscribe to execution updates
- `unsubscribe`: Unsubscribe from execution updates
- `ping`: Keep-alive ping

```json
{"type": "subscribe", "execution_ids": ["exec-abc123"]}
{"type": "unsubscribe", "execution_ids": ["exec-abc123"]}
{"type": "ping"}
```

**Server Messages:**
- `connected`: Connection established
- `execution_status`: Status update
- `execution_log`: New log entry
- `execution_metrics`: Metrics update
- `pong`: Ping response
- `error`: Error message

```json
{"type": "connected", "message": "Connected to execution updates"}
{"type": "execution_status", "execution_id": "exec-abc123", "status": "running", "progress": 50}
{"type": "execution_log", "execution_id": "exec-abc123", "level": "info", "message": "Step completed"}
{"type": "pong"}
```

**Error Codes:**
- `4001`: Missing or invalid token

---

## Root Endpoint

**GET** `/`

Root endpoint showing API info.

**Response (200 OK):**
```json
{
  "app": "AI Workflow Orchestrator",
  "version": "0.1.0",
  "status": "running"
}
```

---

## Request Headers

All authenticated requests should include:

| Header | Value | Required |
|--------|-------|----------|
| `Authorization` | `Bearer <token>` | Yes (for protected endpoints) |
| `Content-Type` | `application/json` | Yes (for POST/PUT requests) |

Responses include:

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Unique request identifier for tracing |
| `Retry-After` | Seconds until rate limit resets (on 429) |

---

## Environment Configuration

Key environment variables for the API:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (insecure default) | Secret for token generation (min 32 chars) |
| `DATABASE_URL` | `sqlite:///gorgon-state.db` | Database connection URL |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token expiration time |
| `API_CREDENTIALS` | None | Comma-separated user:hash pairs |
| `ALLOW_DEMO_AUTH` | `false` | Enable demo authentication |
| `PRODUCTION` | `false` | Enable production mode (strict validation) |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FORMAT` | `text` | Log format (`text` or `json`) |

---

## Code Examples

### Python (requests)

```python
import requests

BASE_URL = "http://localhost:8000"

# Login
response = requests.post(f"{BASE_URL}/v1/auth/login", json={
    "user_id": "admin",
    "password": "demo"
})
token = response.json()["access_token"]

headers = {"Authorization": f"Bearer {token}"}

# List workflows
workflows = requests.get(f"{BASE_URL}/v1/workflows", headers=headers).json()

# Execute workflow
result = requests.post(
    f"{BASE_URL}/v1/workflows/execute",
    headers=headers,
    json={
        "workflow_id": "my-workflow",
        "variables": {"input": "test"}
    }
).json()
```

### curl

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "admin", "password": "demo"}' | jq -r '.access_token')

# List workflows
curl -s -X GET http://localhost:8000/v1/workflows \
  -H "Authorization: Bearer $TOKEN"

# Execute workflow
curl -s -X POST http://localhost:8000/v1/workflows/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"workflow_id": "my-workflow", "variables": {"input": "test"}}'
```

### JavaScript (fetch)

```javascript
const BASE_URL = 'http://localhost:8000';

// Login
const loginResponse = await fetch(`${BASE_URL}/v1/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ user_id: 'admin', password: 'demo' })
});
const { access_token } = await loginResponse.json();

// List workflows
const workflows = await fetch(`${BASE_URL}/v1/workflows`, {
  headers: { 'Authorization': `Bearer ${access_token}` }
}).then(r => r.json());

// Execute workflow
const result = await fetch(`${BASE_URL}/v1/workflows/execute`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${access_token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    workflow_id: 'my-workflow',
    variables: { input: 'test' }
  })
}).then(r => r.json());
```

### Webhook Trigger Example

```python
import hmac
import hashlib
import json
import requests

WEBHOOK_SECRET = "your-webhook-secret"
WEBHOOK_URL = "http://localhost:8000/hooks/my-webhook"

payload = {
    "event": "deployment",
    "environment": "production",
    "commit": "abc123"
}

payload_bytes = json.dumps(payload).encode()
signature = "sha256=" + hmac.new(
    WEBHOOK_SECRET.encode(),
    payload_bytes,
    hashlib.sha256
).hexdigest()

response = requests.post(
    WEBHOOK_URL,
    headers={
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature
    },
    data=payload_bytes
)
```
