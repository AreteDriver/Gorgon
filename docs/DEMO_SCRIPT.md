# Gorgon Demo Script

**Duration:** 3-5 minutes
**Target Audience:** AI Engineering / Solutions Engineering hiring managers

---

## Setup (Before Recording)

```bash
# Terminal 1: Start API
./run_api.sh

# Terminal 2: Start Dashboard
./run_dashboard.sh

# Browser: Open http://localhost:8501
```

Ensure `.env` has valid API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY).

---

## Demo Flow

### 1. Hook (15 seconds)

> "Gorgon is a multi-agent orchestration framework. It coordinates specialized AI agents - planners, builders, testers, reviewers - into production workflows with a single API call."

**Show:** Dashboard overview with metrics

---

### 2. The Problem (20 seconds)

> "Building with LLMs today means managing prompts, chaining outputs, handling failures, and tracking costs across multiple providers. Most teams end up with fragile scripts that break in production."

---

### 3. The Solution (30 seconds)

> "Gorgon provides declarative workflows. Define your pipeline as JSON, and Gorgon handles orchestration, error recovery, and observability."

**Show:** Workflow definition JSON

```json
{
  "id": "dev_workflow",
  "steps": [
    { "id": "plan", "type": "claude_code", "params": { "role": "planner" } },
    { "id": "build", "type": "claude_code", "params": { "role": "builder" } },
    { "id": "test", "type": "claude_code", "params": { "role": "tester" } },
    { "id": "review", "type": "claude_code", "params": { "role": "reviewer" } }
  ]
}
```

---

### 4. Live Demo: Dev Workflow (90 seconds)

**Action:** Execute a development workflow

> "Let's build a feature. I'll ask Gorgon to create a REST API for user authentication."

**Dashboard Steps:**
1. Navigate to **Workflows** tab
2. Select `dev_workflow_plan_build_test_review`
3. Enter variable: `"Build a REST API for user authentication with JWT tokens"`
4. Click **Execute**

> "Watch the agents coordinate. The Planner breaks this into steps. The Builder implements. The Tester writes tests. The Reviewer catches issues."

**Show:** Execution progress with phase timing

> "Each step shows token usage and timing. Full audit trail for debugging and cost tracking."

---

### 5. Architecture Highlight (30 seconds)

**Show:** Architecture diagram in README

> "Under the hood: FastAPI backend, PostgreSQL for state, integrations with OpenAI, Claude, GitHub, Notion, Slack. Everything's containerized with Docker."

---

### 6. API Demo (30 seconds)

**Show:** Swagger docs at `/docs`

> "The same workflow is available via REST API. Submit jobs, check status, cancel - all programmatic."

```bash
curl -X POST http://localhost:8000/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"workflow_id": "dev_workflow", "variables": {"feature": "auth API"}}'
```

---

### 7. Production Features (20 seconds)

> "Production-ready: job queues, scheduled workflows, webhook triggers, rate limiting, request tracing. 2300+ tests, full CI/CD."

**Show:** CI badge, test count badge

---

### 8. Close (15 seconds)

> "Gorgon turns complex AI workflows into reliable, observable pipelines. Check out the repo at github.com/AreteDriver/Gorgon."

**Show:** GitHub repo URL

---

## Key Talking Points

- **10 specialized agent roles** (Planner, Builder, Tester, Reviewer, Architect, Documenter, Data Engineer, Analyst, Visualizer, Reporter)
- **6 integrations** (OpenAI, Claude, GitHub, Notion, Gmail, Slack)
- **2,300+ tests** with CI/CD
- **Docker-ready** with PostgreSQL support
- **Declarative workflows** as JSON

---

## Backup Demos (if time permits)

### Analytics Pipeline
> "Not just for code. Here's an analytics workflow: Data Engineer → Analyst → Visualizer → Reporter."

### Webhook Trigger
> "Trigger workflows from external events - GitHub webhooks, Slack commands, custom integrations."

---

## Recording Tips

1. **Clean terminal** - use `clear` between commands
2. **Zoom browser** to 125% for readability
3. **Pre-populate** the feature request to avoid typing on camera
4. **Pause** on key screens (dashboard, execution, results)
5. **Keep energy up** - this is a pitch, not a tutorial
