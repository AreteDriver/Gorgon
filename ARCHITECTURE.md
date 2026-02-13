# Gorgon Architecture

## Positioning

Gorgon is an **AI Workflow Operating System** — a production-grade platform for orchestrating specialized AI agents across enterprise workflows with first-class operational primitives for governance, observability, cost control, and resilience.

Gorgon coordinates multiple specialized "heads" (agents) — Planner, Builder, Tester, Reviewer, Architect, Documenter, Analyst, and others — through declarative workflow definitions with checkpoint-based state management, contract-driven validation, and multi-provider fault tolerance.

---

## System Architecture

### Layer Model

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Client Layer                                    │
│   Streamlit Dashboard  │  REST API (FastAPI)  │  CLI (Typer)            │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────────┐
│                       Application Layer                                  │
│   Auth (Token/Tenant)  │  CORS  │  Rate Limiting  │  Audit Logging     │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────────┐
│                       Orchestration Layer                                │
│   WorkflowEngine  │  GraphExecutor (DAG)  │  ParallelExecutor          │
│   WorkflowComposer  │  AutoParallel  │  RateLimitedParallelExecutor    │
└──────────┬────────────────────┬─────────────────────┬───────────────────┘
           │                    │                     │
┌──────────▼──────────┐ ┌──────▼───────────┐ ┌───────▼──────────────────┐
│ Contract Validation  │ │  State & Checkpt │ │  Resilience Layer        │
│ AgentContract        │ │  CheckpointMgr   │ │  Circuit Breaker         │
│ ContractEnforcer     │ │  StatePersistence│ │  Bulkhead (Semaphore)    │
│ Input/Output Schema  │ │  SQLite/Postgres │ │  Fallback Chains         │
└──────────────────────┘ └──────────────────┘ │  Retry + Exp. Backoff   │
                                               └──────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────────┐
│                       Integration Layer                                  │
│   OpenAI Client  │  Claude Client  │  GitHub Client  │  Notion Client  │
│   Gmail Client   │  Slack Client   │  Custom Plugins                   │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────────┐
│                      Observability Layer                                 │
│   MetricsCollector  │  CostTracker  │  PrometheusExporter              │
│   Structured Logs   │  Audit Trail  │  Dashboard Monitoring            │
└─────────────────────────────────────────────────────────────────────────┘
```

### Concrete Class Boundaries

| Class | Module | Responsibility | Owns |
|-------|--------|---------------|------|
| `WorkflowEngine` | `orchestrator/workflow_engine.py` | Sequential step execution, variable interpolation | `Workflow`, `WorkflowStep`, `WorkflowResult` |
| `GraphExecutor` | `workflow/graph_executor.py` | DAG-based execution with dependency resolution | Dependency graph, topological ordering |
| `ParallelExecutor` | `workflow/parallel.py` | Fan-out/fan-in/map-reduce patterns | `ParallelTask`, branch results |
| `RateLimitedParallelExecutor` | `workflow/rate_limited_executor.py` | Concurrent execution with per-provider rate limits | Adaptive rate state, distributed limiters |
| `CheckpointManager` | `state/checkpoint.py` | Workflow state capture and resume | `StageContext`, persistence lifecycle |
| `StatePersistence` | `state/persistence.py` | Database read/write for checkpoints | SQLite/Postgres backend abstraction |
| `AgentContract` | `contracts/base.py` | Input/output schema definition per agent role | JSON Schema for validation |
| `ContractEnforcer` | `contracts/base.py` | Runtime validation of agent inputs/outputs | Violation reporting |
| `MetricsCollector` | `metrics/collector.py` | Thread-safe metrics aggregation | Counters, gauges, histograms, callbacks |
| `CostTracker` | `metrics/cost_tracker.py` | Per-call token and USD cost tracking | Budget alerts, provider pricing |
| `Bulkhead` | `resilience/bulkhead.py` | Semaphore-based resource isolation | Active/waiting counts, rejection stats |
| `PluginManager` | `plugins/base.py` | Plugin lifecycle, hook dispatch | Plugin registry, hook mappings |
| `ScheduleManager` | `scheduler/schedule_manager.py` | APScheduler-backed cron/interval triggers | Schedule DB, execution logs |
| `TokenAuth` | `auth/token_auth.py` | Token generation, verification, revocation | Token store with expiry |
| `TenantAuth` | `auth/tenants.py` | Multi-tenant isolation and RBAC | Tenant config, role mappings |

---

## Execution Model

### Sequential Workflow (WorkflowEngine)

```
WorkflowEngine.execute_workflow(workflow)
  │
  ├── validate(workflow)              # Schema + required fields
  ├── initialize(variables)           # Set up runtime context
  │
  ├── for step in workflow.steps:
  │     ├── interpolate(step.params, variables)    # {{var}} substitution
  │     ├── client = get_api_client(step.type)     # Factory dispatch
  │     ├── result = client.execute_action(step.action, params)
  │     ├── variables[step.id + "_output"] = result
  │     └── log_step(step.id, result)
  │
  └── return WorkflowResult(outputs, status, errors)
```

### DAG Workflow (GraphExecutor)

```
GraphExecutor.execute(steps)
  │
  ├── build_dependency_graph(steps)        # Parse depends_on edges
  ├── validate_dag(graph)                  # Cycle detection
  ├── groups = topological_sort(graph)     # Parallel groups
  │
  ├── for group in groups:
  │     └── asyncio.gather(*[execute_step(s) for s in group])
  │           ├── Per step: checkpoint on success
  │           └── Per step: checkpoint on failure → decide continue/abort
  │
  └── aggregate_results()
```

### DAG Validation Rules

1. **Cycle detection** — Topological sort fails on cycles; workflow rejected at load time.
2. **Missing dependency** — If `depends_on` references a non-existent step ID, validation raises `ValidationError`.
3. **Orphan detection** — Steps with no path from root are flagged as warnings (still execute).
4. **Type compatibility** — Contract enforcer validates that upstream output schemas match downstream input schemas when contracts are defined.

### Sequence Diagram: Plan → Build → Test → Review

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  Client   │   │ Workflow  │   │ Planner  │   │ Builder  │   │ Reviewer │
│          │   │  Engine   │   │  Agent   │   │  Agent   │   │  Agent   │
└────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘
     │              │              │              │              │
     │──execute────▶│              │              │              │
     │              │──checkpoint──│              │              │
     │              │  (start)     │              │              │
     │              │──plan───────▶│              │              │
     │              │              │──plan_output─│              │
     │              │◀─────────────│              │              │
     │              │──checkpoint──│              │              │
     │              │  (plan:ok)   │              │              │
     │              │──build──────────────────────▶│              │
     │              │              │              │──code_output─│
     │              │◀─────────────────────────────│              │
     │              │──checkpoint──│              │              │
     │              │  (build:ok)  │              │              │
     │              │──test────────────────────────▶│  (tester)  │
     │              │◀─────────────────────────────│              │
     │              │──checkpoint──│              │              │
     │              │  (test:ok)   │              │              │
     │              │──review────────────────────────────────────▶│
     │              │◀───────────────────────────────────────────│
     │              │──checkpoint──│              │              │
     │              │  (review:ok) │              │              │
     │◀─result──────│              │              │              │
```

Each checkpoint persists to the database. On failure at any stage, execution can resume from the last successful checkpoint.

---

## State Management

### Checkpoint Object (Serialized)

```json
{
  "checkpoint_id": 47,
  "workflow_id": "wf-a3b8c1d2e4f5",
  "stage": "build",
  "status": "success",
  "input_data": {
    "plan": "1. Create FastAPI router\n2. Add JWT middleware\n3. ...",
    "task_id": "auth-feature-001"
  },
  "output_data": {
    "code": "...",
    "files_created": ["src/auth/router.py", "src/auth/jwt.py"],
    "status": "complete"
  },
  "tokens_used": 4230,
  "duration_ms": 12847,
  "created_at": "2025-01-18T10:30:47.123Z"
}
```

### Database Schema (State Layer)

```sql
-- Workflow execution tracking
CREATE TABLE workflows (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    config TEXT,             -- JSON
    status TEXT DEFAULT 'pending',  -- pending | running | completed | failed
    current_stage TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Per-stage checkpoints
CREATE TABLE checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT REFERENCES workflows(id),
    stage TEXT NOT NULL,
    status TEXT NOT NULL,     -- running | success | failed
    input_data TEXT,          -- JSON
    output_data TEXT,         -- JSON
    tokens_used INTEGER DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Scheduled workflow definitions
CREATE TABLE schedules (
    id TEXT PRIMARY KEY,
    workflow_id TEXT,
    name TEXT,
    schedule_type TEXT,       -- CRON | INTERVAL
    cron_config TEXT,
    interval_config TEXT,
    variables TEXT,
    status TEXT,              -- ACTIVE | PAUSED | DISABLED
    created_at TIMESTAMP,
    last_run TIMESTAMP,
    next_run TIMESTAMP,
    run_count INTEGER DEFAULT 0
);
```

### Resume Semantics

When `CheckpointManager.resume(workflow_id)` is called:

1. Load workflow record and verify status is `failed` or `running`.
2. Query checkpoints ordered by `created_at DESC`.
3. Find the last checkpoint with `status = 'success'`.
4. Return the stage name and its output data.
5. Caller skips all stages up to and including the resumed stage.
6. Execution continues from the next stage using the checkpointed output as input context.

Idempotency guarantee: each stage writes its checkpoint in a `finally` block. If a stage partially completes but crashes before checkpoint write, the stage re-executes from its input data on resume. Stages must be designed to tolerate re-execution (idempotent with respect to their input data).

---

## Concurrency Model

### Threading Architecture

- **API Layer**: FastAPI runs on uvicorn with async event loop. Each request is an async coroutine.
- **MetricsCollector**: Protected by `threading.Lock` for thread-safe counter/gauge/histogram updates.
- **Bulkhead**: Per-provider semaphores (`asyncio.Semaphore` for async, `threading.Semaphore` for sync). Limits concurrent requests to each external API independently.
- **Parallel Execution**: `asyncio.gather()` for concurrent step execution within a DAG group. `ThreadPoolExecutor` fallback for sync operations.
- **Distributed Rate Limiting**: Redis-backed (production) or SQLite-backed (single-node) sliding window counters for cross-process coordination.

### Bulkhead Isolation

```python
# Each provider gets an isolated concurrency pool
bulkheads = {
    "anthropic": Bulkhead(max_concurrent=5, max_waiting=20, timeout=30.0),
    "openai":    Bulkhead(max_concurrent=8, max_waiting=30, timeout=30.0),
    "github":    Bulkhead(max_concurrent=10, max_waiting=50, timeout=15.0),
}

# If anthropic bulkhead is full, openai/github calls proceed unaffected
```

When `max_concurrent` slots are occupied and `max_waiting` queue slots are full, new requests receive `BulkheadFull` immediately. This prevents cascading backpressure from one slow provider blocking the entire system.

### Rate Limiting Stack

| Layer | Mechanism | Scope |
|-------|-----------|-------|
| API ingress | `slowapi` per-IP limits | Per client IP |
| Provider concurrency | `Bulkhead` semaphores | Per provider, per process |
| Adaptive throttle | Automatic limit reduction on 429 | Per provider, per process |
| Distributed RPM | Redis/SQLite sliding window | Per provider, cross-process |

---

## Failure Modes and Recovery

### Error Classification

| Error Type | Response | Example |
|-----------|----------|---------|
| Validation Error | Fail fast, no retry | Invalid workflow schema |
| API Transient Error | Retry with exponential backoff + jitter | HTTP 429, 503, timeout |
| API Permanent Error | Fail step, checkpoint failure state | HTTP 401, 403 |
| Provider Outage | Circuit breaker opens → fallback provider | 5+ consecutive failures |
| Resource Exhaustion | Bulkhead rejection → immediate error | Max concurrent reached |
| Checkpoint Write Failure | Log error, workflow marked failed | Database unavailable |

### Retry Semantics

```python
# Exponential backoff with jitter (from resilience layer)
retry_config = RetryConfig(
    max_retries=3,
    base_delay=1.0,        # 1s initial
    max_delay=30.0,        # Cap at 30s
    exponential_base=2.0,  # 1s → 2s → 4s
    jitter=True,           # ±random to prevent thundering herd
)

# Per-step override in workflow YAML:
# steps:
#   - id: call_claude
#     retry_policy:
#       max_retries: 5
#       base_delay: 2.0
```

### Circuit Breaker States

```
CLOSED ──[failure_threshold exceeded]──▶ OPEN
                                            │
                                     [recovery_timeout]
                                            │
                                            ▼
                                        HALF_OPEN
                                       /         \
                           [success_threshold]  [any failure]
                                  │                  │
                                  ▼                  ▼
                               CLOSED              OPEN
```

- **Failure threshold**: 5 consecutive failures opens the circuit.
- **Recovery timeout**: 60s before testing with a single probe request.
- **Success threshold**: 3 consecutive successes in half-open state closes the circuit.
- **Scope**: One breaker per provider (Anthropic, OpenAI, GitHub, etc.).

### Fallback Chain

When a provider's circuit breaker is open:

1. Route to configured fallback provider (e.g., OpenAI → Claude, Claude → OpenAI).
2. If fallback also unavailable, return cached result if available.
3. If no cache, fail with actionable error including which providers were attempted.

---

## Contract System

### Contract Structure

```python
@dataclass
class AgentContract:
    role: AgentRole              # PLANNER, BUILDER, TESTER, etc.
    input_schema: dict           # JSON Schema for inputs
    output_schema: dict          # JSON Schema for outputs
    description: str
    required_context: list[str]  # Context keys that must be present
```

### Enforcement Flow

```
Workflow step begins
  │
  ├── ContractEnforcer.validate_input(contract, input_data)
  │     └── jsonschema.validate(input_data, contract.input_schema)
  │           ├── Pass → proceed to execution
  │           └── Fail → ContractViolation raised, step skipped
  │
  ├── Agent executes
  │
  └── ContractEnforcer.validate_output(contract, output_data)
        └── jsonschema.validate(output_data, contract.output_schema)
              ├── Pass → checkpoint output, proceed
              └── Fail → ContractViolation raised, step marked failed
```

### Predefined Contracts

| Agent | Required Input | Expected Output |
|-------|---------------|-----------------|
| Planner | `request`, `context` | `tasks`, `architecture`, `success_criteria` |
| Builder | `plan`, `task_id` | `code`, `files_created`, `status` |
| Tester | `code`, `success_criteria` | `tests`, `test_results`, `coverage` |
| Reviewer | `code` | `issues`, `recommendations`, `risk_level` |
| Analyst | `data`, `analysis_request` | `findings`, `statistics`, `confidence` |

---

## Observability and Metrics

### Metrics Collection Architecture

The `MetricsCollector` is a thread-safe singleton that tracks all workflow execution in real time:

```python
class MetricsCollector:
    _active: dict[str, WorkflowMetrics]     # Currently running workflows
    _history: list[WorkflowMetrics]          # Completed (ring buffer, max 1000)
    _counters: dict[str, int]               # Monotonic event counters
    _gauges: dict[str, float]               # Point-in-time values
    _histograms: dict[str, list[float]]     # Distribution tracking
```

**Counters tracked**: `workflows_started`, `workflows_completed`, `workflows_failed`, `steps_started`, `steps_completed`, `steps_failed`, `steps_started_{type}`.

**Histograms tracked**: `workflow_duration_ms`, `workflow_tokens`, `step_duration_ms`, `step_tokens`.

**Computed statistics**: min, max, avg, p50, p95 for all histograms.

### Prometheus Integration

The `PrometheusExporter` (`metrics/exporters.py`) exposes metrics in Prometheus text exposition format, compatible with standard Prometheus scraping:

```
# HELP gorgon_workflows_total Total workflow executions
# TYPE gorgon_workflows_total counter
gorgon_workflows_total{status="completed"} 1247
gorgon_workflows_total{status="failed"} 83

# HELP gorgon_workflow_duration_seconds Workflow execution duration
# TYPE gorgon_workflow_duration_seconds histogram
gorgon_workflow_duration_seconds_bucket{le="1.0"} 120
gorgon_workflow_duration_seconds_bucket{le="5.0"} 890
gorgon_workflow_duration_seconds_bucket{le="30.0"} 1200

# HELP gorgon_tokens_used_total Total tokens consumed
# TYPE gorgon_tokens_used_total counter
gorgon_tokens_used_total{provider="anthropic"} 2847000
gorgon_tokens_used_total{provider="openai"} 1523000
```

A `prometheus_server.py` module provides a standalone HTTP endpoint for Prometheus scraping.

### Cost Tracking

The `CostTracker` (`metrics/cost_tracker.py`) provides granular cost attribution:

- **Per-call tracking**: Provider, model, input/output tokens, computed USD cost.
- **Attribution dimensions**: workflow_id, step_id, agent_role, provider, model.
- **Budget management**: Configurable budget limits with threshold alerts.
- **Aggregation**: By provider, by model, by workflow, by time period (daily/monthly).
- **Export**: JSON persistence, CSV export for finance/reporting.

```python
tracker.track(
    provider=Provider.ANTHROPIC,
    model="claude-sonnet-4-20250514",
    input_tokens=1500,
    output_tokens=2000,
    workflow_id="feature-123",
    agent_role="builder",
)
summary = tracker.get_summary(days=30)
# { "total_cost_usd": 47.82, "by_provider": {...}, "by_workflow": {...} }
```

### Structured Logging

All workflow execution produces structured JSON logs with correlation IDs:

```json
{
  "timestamp": "2025-01-18T10:30:00Z",
  "level": "INFO",
  "event": "step_completed",
  "workflow_id": "wf-a3b8c1d2e4f5",
  "execution_id": "exec-7890abcd",
  "step_id": "build",
  "step_type": "claude_code",
  "duration_ms": 12847,
  "tokens_used": 4230,
  "status": "success",
  "trace_id": "req-1234-5678-abcd"
}
```

When `SANITIZE_LOGS=true`, sensitive data (API keys, tokens, passwords) is automatically redacted.

### Alerting Rules (Prometheus)

```yaml
groups:
  - name: gorgon
    rules:
      - alert: HighFailureRate
        expr: >
          rate(gorgon_workflows_total{status="failed"}[5m])
          / rate(gorgon_workflows_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning

      - alert: TokenBudgetExceeded
        expr: gorgon_tokens_used_daily > gorgon_token_budget_daily * 0.9
        for: 1m
        labels:
          severity: critical

      - alert: ProviderCircuitOpen
        expr: gorgon_circuit_breaker_state{state="open"} == 1
        for: 0m
        labels:
          severity: warning
```

### Dashboard Monitoring

The Streamlit dashboard provides real-time visibility into:

- **Active workflows**: Progress, current stage, elapsed time.
- **Execution history**: Success/failure rates, duration trends.
- **Cost breakdown**: Per-provider, per-workflow, per-agent spend.
- **Rate limit status**: Per-provider throttling gauges and 429 counts.
- **Parallel execution**: Fan-out branch progress, map-reduce status.

---

## Security and Governance

### Authentication

- **Token-based auth**: Cryptographically secure tokens via `secrets.token_urlsafe(32)`.
- **Token lifecycle**: Configurable expiration, revocation support.
- **Brute force protection**: Per-IP rate limiting with exponential backoff — 5 attempts/min, 20/hour, 24-hour lockout after 10+ failures.

### Multi-Tenant Isolation

- **TenantAuth**: Separate tenant contexts with per-tenant configuration.
- **Namespace isolation**: Each tenant's workflows, schedules, and execution history are isolated.
- **Per-tenant quotas**: Token budgets and resource limits enforced per tenant.

### Secrets Management

- **Environment-based**: All API keys and secrets loaded from environment variables, never hardcoded.
- **Field-level encryption**: Sensitive data (API keys, tokens, PII) encrypted at rest using Fernet symmetric encryption with PBKDF2-HMAC-SHA256 key derivation (480,000 iterations). Encrypted values prefixed with `enc:`.
- **Log sanitization**: When `SANITIZE_LOGS=true`, API keys, tokens, and passwords are redacted from all log output.
- **Gmail tokens**: Stored with 600 permissions (user-read only).

### Execution Sandboxing

- **Shell step constraints**: Configurable timeout (default 300s), output limit (10MB), optional command whitelist.
- **Self-improvement safety**: Protected files list (auth, security, credentials cannot be modified). Max 10 files / 500 lines per PR. Human approval gates at plan, apply, and merge stages. Auto-rollback on test failure.
- **Request size limits**: JSON 1MB, form data 50MB, general 10MB.

### Workflow Approval Gates

The self-improvement system enforces human-in-the-loop checkpoints:

1. **Plan gate**: AI proposes changes → human reviews plan before any code is written.
2. **Apply gate**: Generated code is reviewed before being applied to the codebase.
3. **Merge gate**: Final human approval before PR is merged.
4. **Auto-rollback**: If tests fail after apply, changes are reverted automatically.

### Production Safety Checklist

| Setting | Requirement |
|---------|------------|
| `SECRET_KEY` | ≥32 characters, not default |
| `DATABASE_URL` | PostgreSQL (not SQLite) |
| `ALLOW_DEMO_AUTH` | `false` |
| `PRODUCTION` | `true` |
| `DEBUG` | `false` |
| `LOG_FORMAT` | `json` |
| `SANITIZE_LOGS` | `true` |

The `settings.is_production_safe` property validates all of the above. Violations raise errors when `PRODUCTION=true`.

---

## Plugin System

### Lifecycle Hooks

```python
class PluginHook(Enum):
    WORKFLOW_START  = "workflow_start"
    WORKFLOW_END    = "workflow_end"
    WORKFLOW_ERROR  = "workflow_error"
    STEP_START      = "step_start"
    STEP_END        = "step_end"
    STEP_ERROR      = "step_error"
    STEP_RETRY      = "step_retry"
    PRE_EXECUTE     = "pre_execute"
    POST_EXECUTE    = "post_execute"
    CUSTOM          = "custom"
```

Plugins receive a `PluginContext` with workflow ID, step ID, inputs, outputs, metadata, and error state. Plugins can also transform inputs and outputs via `transform_input()` / `transform_output()` pipelines.

### Plugin Marketplace

Plugins are categorized (INTEGRATION, MONITORING, SECURITY, AI_PROVIDER, etc.) and can be sourced from MARKETPLACE, LOCAL, GITHUB, PYPI, or URL. Each plugin listing includes version history, ratings, verification status, and download counts.

---

## Parallel Execution Patterns

| Pattern | Mechanism | Use Case |
|---------|-----------|----------|
| **Fan-Out** | Execute step template per item in a list | Review N files concurrently |
| **Fan-In** | Aggregate parallel results (concat, AI summary) | Combine review findings |
| **Map-Reduce** | Combined scatter-gather | Analyze + summarize in one step |
| **Auto-Parallel** | Build dependency graph, parallelize independent groups | Any DAG workflow |

Auto-parallel works by:
1. Parsing `depends_on` edges to build a dependency graph.
2. Grouping steps with no mutual dependencies.
3. Executing each group concurrently via `asyncio.gather()`.
4. Proceeding to the next group only when the current group completes.

Rate-limited parallel execution adds per-provider semaphores with adaptive backoff (halve limit on 429, recover after 10 consecutive successes) and optional distributed rate limiting via Redis sliding windows.

---

## Budget Tracking State

The `CostTracker` maintains a persistent cost ledger:

```python
@dataclass
class CostEntry:
    timestamp: datetime
    provider: Provider         # OPENAI | ANTHROPIC | GITHUB | NOTION | SLACK
    model: str                 # "gpt-4", "claude-sonnet-4-20250514", etc.
    tokens: TokenUsage         # input_tokens, output_tokens, total_tokens
    cost_usd: float            # Computed from per-model pricing table
    workflow_id: str | None    # Attribution
    step_id: str | None
    agent_role: str | None
```

**Pricing is maintained per-model** with separate input/output rates. Budget alerts fire when spend crosses configurable thresholds (default: 80% of limit). Daily and monthly limits are enforced independently.

---

## Competitive Positioning

Gorgon's differentiator is **first-class operational primitives** — capabilities that are native to the framework rather than requiring custom implementation on top of a general-purpose library.

| Capability | Gorgon | LangGraph | AutoGen | CrewAI |
|-----------|--------|-----------|---------|--------|
| Declarative workflow definitions | Native (JSON/YAML) | Custom code | Custom code | Custom code |
| Per-step checkpointing and resume | Native (`CheckpointManager`) | Requires custom state | Not built-in | Not built-in |
| Per-provider circuit breakers | Native (`Bulkhead` + breaker) | Requires custom impl | Not built-in | Not built-in |
| Contract-driven agent validation | Native (`AgentContract`) | Not built-in | Not built-in | Not built-in |
| Budget tracking with alerts | Native (`CostTracker`) | Requires custom impl | Requires custom impl | Token limits only |
| Prometheus metrics export | Native (`PrometheusExporter`) | Requires custom impl | Requires custom impl | Not built-in |
| Multi-tenant isolation | Native (`TenantAuth`) | Not built-in | Not built-in | Not built-in |
| Cron/interval scheduling | Native (`ScheduleManager`) | Not built-in | Not built-in | Not built-in |
| Plugin marketplace | Native | Not built-in | Extensions | Tools only |
| Webhook triggers | Native | Not built-in | Not built-in | Not built-in |

These capabilities can be implemented in other frameworks with additional code. The difference is that Gorgon provides them as default operational structure — production-ready governance, observability, and resilience without assembly required.

The closer competitive frame is not other agent frameworks but **enterprise workflow engines**: Temporal.io for AI agents, Airflow for AI pipelines, Zapier for AI automation. Gorgon is positioned as the **AI Workflow Operating System** — the operational layer between AI providers and enterprise production requirements.

---

## Deployment Tiers

| | Tier 1: Team | Tier 2: Department | Tier 3: Enterprise |
|---|---|---|---|
| **Users** | 1–5 developers | 5–20 developers | 20+ developers |
| **Compute** | 1 CPU, 2GB RAM | 2–4 CPU, 4–8GB RAM | Kubernetes cluster |
| **Database** | SQLite | PostgreSQL | Managed PostgreSQL + Redis |
| **State** | Local file | PostgreSQL backend | Distributed with replicas |
| **Multi-tenant** | No | Yes | Yes + SSO (SAML/OIDC) |
| **Audit** | Basic logging | Full structured logs | Full + compliance export |
| **SLA** | Best effort | 99.5% | 99.9% |

---

## Design Patterns

| Pattern | Where Used | Purpose |
|---------|-----------|---------|
| Factory | `get_api_client()` | Dynamic API client instantiation by step type |
| Strategy | `WorkflowEngine.execute_step()` | Dispatch to different execution strategies |
| Template Method | `execute_workflow()` | Common flow (validate → setup → execute → cleanup → log) |
| Circuit Breaker | `resilience/` | Prevent cascading failures from provider outages |
| Bulkhead | `resilience/bulkhead.py` | Resource isolation per provider |
| Observer | `MetricsCollector` callbacks | Decouple metrics events from handling |
| Context Manager | `CheckpointManager.workflow()` / `.stage()` | Automatic state capture with cleanup |
| Singleton | `get_collector()`, `get_settings()` | Global instances for metrics and config |
| Registry | `PluginManager`, `ContractRegistry` | Dynamic registration and lookup |

---

## Error Hierarchy

```
GorgonError (base)
├── ValidationError          # Invalid workflow schema or parameters
├── ExecutionError           # Step execution failure
├── ConfigurationError       # Missing config or env vars
├── AuthenticationError      # Invalid credentials or expired token
├── ContractViolation        # Agent input/output schema mismatch
└── BulkheadFull             # Provider concurrency limit exceeded
```

---

## Key File Reference

| File | Purpose |
|------|---------|
| `src/test_ai/api.py` | FastAPI application, all REST endpoints, middleware stack |
| `src/test_ai/orchestrator/workflow_engine.py` | Core sequential workflow execution |
| `src/test_ai/workflow/graph_executor.py` | DAG-based parallel workflow execution |
| `src/test_ai/workflow/parallel.py` | Fan-out/fan-in/map-reduce patterns |
| `src/test_ai/workflow/rate_limited_executor.py` | Rate-limited parallel execution |
| `src/test_ai/contracts/base.py` | Agent contract definitions and enforcement |
| `src/test_ai/contracts/definitions.py` | Predefined contracts per agent role |
| `src/test_ai/state/checkpoint.py` | Checkpoint manager for workflow state |
| `src/test_ai/state/persistence.py` | Database persistence layer |
| `src/test_ai/metrics/collector.py` | Thread-safe metrics collection |
| `src/test_ai/metrics/cost_tracker.py` | API cost tracking and budget management |
| `src/test_ai/metrics/exporters.py` | Prometheus and CSV metrics export |
| `src/test_ai/resilience/bulkhead.py` | Bulkhead pattern for resource isolation |
| `src/test_ai/plugins/base.py` | Plugin system base classes and registry |
| `src/test_ai/scheduler/schedule_manager.py` | APScheduler-backed workflow scheduling |
| `src/test_ai/auth/token_auth.py` | Token authentication |
| `src/test_ai/auth/tenants.py` | Multi-tenant isolation |

---

## Related Documentation

| Document | Focus |
|----------|-------|
| `docs/ENTERPRISE_PATTERNS.md` | Deployment patterns, HA, disaster recovery |
| `docs/PARALLEL_EXECUTION.md` | Parallel execution API reference |
| `docs/security.md` | Security configuration checklist |
| `docs/performance.md` | Performance tuning guide |
| `docs/architecture.md` | Mermaid visual diagrams |
| `QUICKSTART.md` | Getting started guide |
