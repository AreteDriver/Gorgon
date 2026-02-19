# Gorgon: OpenClaw Harvest — Patterns Worth Stealing

> **Purpose:** Extract proven patterns from OpenClaw's ecosystem and translate them into Gorgon's Python/FastAPI architecture.  
> **Source repos:** `openclaw/lobster`, `openclaw/skills`, `zscole/model-hierarchy-skill`, `openclaw/openclaw`  
> **Target:** Gorgon multi-agent orchestration framework  
> **License note:** All source repos are MIT. Patterns/concepts are not copyrightable. Implementations below are original.

---

## Harvest 1: Resume Tokens (from Lobster)

### What Lobster Does
When a workflow hits an approval gate, it serializes workflow state to disk and returns a compact token key. The caller (OpenClaw) stores the token and can resume later with `{ "action": "resume", "token": "<key>", "approve": true }`. The workflow picks up exactly where it stopped — no re-execution of prior steps.

### Why This Matters for Gorgon
Your current checkpoint system uses SQLite to persist full workflow state. Lobster's approach is lighter — the resume token is just a key that maps to persisted state. This is better for the API surface because Animus (or any external caller) doesn't need to understand Gorgon's internal state model — it just holds a token.

### Gorgon Implementation

**Data model:**
```python
# src/gorgon/state/resume.py
import json
import uuid
import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Any, Optional
from pathlib import Path


@dataclass
class WorkflowCheckpoint:
    token: str
    workflow_id: str
    execution_id: str
    paused_at_step: str
    step_outputs: dict[str, Any]      # outputs from completed steps
    pending_approval: dict[str, Any]   # what needs approval
    context: dict[str, Any]            # workflow-level context
    created_at: str
    expires_at: str

    def to_api_response(self) -> dict:
        """What the API returns to the caller (Animus)."""
        return {
            "status": "needs_approval",
            "resume_token": self.token,
            "paused_at": self.paused_at_step,
            "approval_prompt": self.pending_approval.get("prompt", ""),
            "preview": self.pending_approval.get("preview", []),
            "expires_at": self.expires_at,
        }


class ResumeTokenStore:
    """SQLite-backed resume token storage. Lightweight, no ORM."""

    def __init__(self, db_path: Path = Path("~/.gorgon/state/resume.db")):
        self.db_path = db_path.expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    token TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    execution_id TEXT NOT NULL,
                    paused_at_step TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_execution 
                ON checkpoints(execution_id)
            """)

    def save(self, checkpoint: WorkflowCheckpoint) -> str:
        """Persist checkpoint, return token."""
        state = {
            "step_outputs": checkpoint.step_outputs,
            "pending_approval": checkpoint.pending_approval,
            "context": checkpoint.context,
        }
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO checkpoints 
                   (token, workflow_id, execution_id, paused_at_step, 
                    state_json, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    checkpoint.token,
                    checkpoint.workflow_id,
                    checkpoint.execution_id,
                    checkpoint.paused_at_step,
                    json.dumps(state),
                    checkpoint.created_at,
                    checkpoint.expires_at,
                ),
            )
        return checkpoint.token

    def load(self, token: str) -> Optional[WorkflowCheckpoint]:
        """Load checkpoint by token. Returns None if expired or missing."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM checkpoints WHERE token = ?", (token,)
            ).fetchone()
        if not row:
            return None
        
        state = json.loads(row[4])
        checkpoint = WorkflowCheckpoint(
            token=row[0],
            workflow_id=row[1],
            execution_id=row[2],
            paused_at_step=row[3],
            step_outputs=state["step_outputs"],
            pending_approval=state["pending_approval"],
            context=state["context"],
            created_at=row[5],
            expires_at=row[6],
        )
        
        # Check expiration
        if datetime.fromisoformat(checkpoint.expires_at) < datetime.utcnow():
            self.delete(token)
            return None
        return checkpoint

    def delete(self, token: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM checkpoints WHERE token = ?", (token,))

    def cleanup_expired(self):
        """Prune expired tokens. Call periodically."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM checkpoints WHERE expires_at < ?",
                (datetime.utcnow().isoformat(),),
            )


def generate_token() -> str:
    """Short, URL-safe token."""
    return uuid.uuid4().hex[:16]
```

**API integration:**
```python
# In src/gorgon/api/routes/executions.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from gorgon.state.resume import ResumeTokenStore, generate_token

router = APIRouter(prefix="/executions", tags=["executions"])
store = ResumeTokenStore()


class ResumeRequest(BaseModel):
    token: str
    approve: bool


@router.post("/{execution_id}/resume")
async def resume_execution(execution_id: str, req: ResumeRequest):
    """Resume a paused workflow execution."""
    checkpoint = store.load(req.token)
    if not checkpoint:
        raise HTTPException(404, "Token expired or not found")
    if checkpoint.execution_id != execution_id:
        raise HTTPException(400, "Token doesn't match execution")
    
    if not req.approve:
        store.delete(req.token)
        return {"status": "cancelled", "execution_id": execution_id}
    
    # Resume workflow from checkpoint
    # ... hand off to workflow engine with checkpoint.step_outputs
    store.delete(req.token)
    return {"status": "resumed", "execution_id": execution_id}
```

**Claude Code prompt to implement:**
```
Implement a resume token system for Gorgon's workflow engine.

When a workflow step has `approval: required` in the YAML definition, the 
execution engine should:
1. Serialize all completed step outputs to SQLite via ResumeTokenStore
2. Generate a compact token (16-char hex)
3. Return an API response with status "needs_approval", the token, 
   and a preview of what's pending approval
4. The execution STOPS — no further steps run

When POST /executions/{id}/resume is called with approve=true:
1. Load the checkpoint from SQLite
2. Resume the workflow engine from the paused step
3. Delete the token after use

Use the ResumeTokenStore class from src/gorgon/state/resume.py.
The token expires after 24 hours by default (configurable in workflow YAML).
```

---

## Harvest 2: Approval Gates in YAML Workflows (from Lobster)

### What Lobster Does
Steps can declare `approval: required`. When hit, execution halts and returns a structured approval request with a prompt, preview data, and resume token.

### Gorgon Implementation

**YAML workflow syntax addition:**
```yaml
# workflows/code-review.yaml
name: code-review
description: Multi-agent code review pipeline
agents:
  - role: analyzer
    model: cheap
  - role: reviewer  
    model: mid
  - role: architect
    model: premium

steps:
  - id: analyze
    agent: analyzer
    action: static_analysis
    inputs:
      repo: $input.repo_path
    budget: 5000  # max tokens

  - id: review
    agent: reviewer
    action: code_review
    inputs:
      code: $analyze.output
      analysis: $analyze.findings
    budget: 15000

  - id: approval_gate
    type: approval
    prompt: "Review complete. Apply suggested changes?"
    preview: $review.suggestions
    timeout: 86400  # 24hr expiration

  - id: apply
    agent: architect
    action: apply_changes
    inputs:
      suggestions: $review.suggestions
    condition: $approval_gate.approved
    budget: 20000
```

**Step reference syntax:**
- `$input.field` — workflow input parameters
- `$step_id.output` — previous step's primary output
- `$step_id.field` — specific field from a step's output
- `$approval_gate.approved` — boolean from approval step

**Claude Code prompt to implement:**
```
Add approval gate support to Gorgon's YAML workflow parser and execution engine.

A step with `type: approval` should:
1. Halt execution
2. Collect the `preview` field (resolving any $step_id references)
3. Create a WorkflowCheckpoint with all completed step outputs
4. Save to ResumeTokenStore
5. Return the approval API response

The workflow YAML parser should validate:
- Steps after an approval gate must have `condition: $gate_id.approved`
- Preview fields must reference completed steps only
- Timeout is optional (default 86400 seconds)

Add this to the existing YAML workflow schema in src/gorgon/workflows/schema.py.
Integrate with the execution engine in src/gorgon/engine/runner.py.
```

---

## Harvest 3: Model Hierarchy / Budget Routing (from model-hierarchy-skill)

### What It Does
Classifies every task as ROUTINE/MODERATE/COMPLEX and routes to the cheapest model that can handle it. Claims ~10x cost reduction with 80/15/5 distribution.

### Why This Matters for Gorgon
Your budget management system already tracks token spend per agent. This adds the intelligence to *route* tasks to different model tiers automatically, which is the missing piece between "tracking cost" and "optimizing cost."

### Gorgon Implementation

**Model routing config:**
```yaml
# config/model_routing.yaml
tiers:
  cheap:
    provider: ollama
    model: llama3.2:3b
    cost_per_1k_tokens: 0.0  # local
    max_context: 8192
    capabilities: [file_ops, formatting, status_checks, simple_qa]
    
  mid:
    provider: anthropic
    model: claude-sonnet-4-20250514
    cost_per_1k_tokens: 0.003
    max_context: 200000
    capabilities: [code_generation, summarization, analysis, drafting]
    
  premium:
    provider: anthropic
    model: claude-opus-4-20250514
    cost_per_1k_tokens: 0.015
    max_context: 200000
    capabilities: [debugging, architecture, novel_problems, complex_reasoning]

classification_rules:
  routine:
    keywords: [read, list, format, status, check, lookup, echo, copy, move]
    max_input_tokens: 2000
    tier: cheap
    
  moderate:
    keywords: [generate, write, summarize, analyze, draft, review, compare]
    max_input_tokens: 50000
    tier: mid
    
  complex:
    keywords: [debug, architect, design, investigate, diagnose, optimize]
    # Also triggered by: error recovery, multi-step reasoning, novel problems
    tier: premium

  # Fallback: if classification is uncertain, use mid tier
  default_tier: mid
```

**Router implementation:**
```python
# src/gorgon/budget/router.py
from dataclasses import dataclass
from typing import Optional
import yaml
from pathlib import Path


@dataclass
class ModelRoute:
    tier: str
    provider: str
    model: str
    cost_per_1k: float
    reason: str


class ModelRouter:
    """Route agent tasks to appropriate model tiers based on complexity."""
    
    def __init__(self, config_path: Path = Path("config/model_routing.yaml")):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        self.tiers = self.config["tiers"]
        self.rules = self.config["classification_rules"]
    
    def classify(
        self, 
        task_description: str, 
        input_tokens: int = 0,
        agent_role: Optional[str] = None,
        step_type: Optional[str] = None,
    ) -> ModelRoute:
        """Classify a task and return the optimal model route."""
        
        desc_lower = task_description.lower()
        
        # Check explicit agent role overrides (architect always gets premium)
        if agent_role in ("architect", "debugger"):
            return self._route("premium", f"agent_role={agent_role}")
        
        # Check complex indicators first (they override everything)
        complex_keywords = self.rules.get("complex", {}).get("keywords", [])
        if any(kw in desc_lower for kw in complex_keywords):
            return self._route("premium", "complex_keyword_match")
        
        # Check if input size forces upgrade
        routine_max = self.rules.get("routine", {}).get("max_input_tokens", 2000)
        moderate_max = self.rules.get("moderate", {}).get("max_input_tokens", 50000)
        
        if input_tokens > moderate_max:
            return self._route("premium", f"input_tokens={input_tokens}")
        
        # Check routine
        routine_keywords = self.rules.get("routine", {}).get("keywords", [])
        if any(kw in desc_lower for kw in routine_keywords) and input_tokens <= routine_max:
            return self._route("cheap", "routine_keyword_match")
        
        # Check moderate
        moderate_keywords = self.rules.get("moderate", {}).get("keywords", [])
        if any(kw in desc_lower for kw in moderate_keywords):
            return self._route("mid", "moderate_keyword_match")
        
        # Default
        default = self.rules.get("default_tier", "mid")
        return self._route(default, "default_fallback")
    
    def _route(self, tier: str, reason: str) -> ModelRoute:
        t = self.tiers[tier]
        return ModelRoute(
            tier=tier,
            provider=t["provider"],
            model=t["model"],
            cost_per_1k=t["cost_per_1k_tokens"],
            reason=reason,
        )
    
    def estimate_cost(self, tier: str, tokens: int) -> float:
        """Estimate cost for a given tier and token count."""
        return (tokens / 1000) * self.tiers[tier]["cost_per_1k_tokens"]
```

**Integration with workflow engine:**
```python
# In the workflow executor, before calling an agent:

route = router.classify(
    task_description=step.action,
    input_tokens=len(step_input_text) // 4,  # rough estimate
    agent_role=step.agent_role,
)

# Override the agent's default model with the routed model
agent_config.model = route.model
agent_config.provider = route.provider

# Log the routing decision for the budget dashboard
budget_tracker.log_routing(
    execution_id=execution.id,
    step_id=step.id,
    tier=route.tier,
    reason=route.reason,
    estimated_cost=router.estimate_cost(route.tier, estimated_tokens),
)
```

**Claude Code prompt to implement:**
```
Add model routing to Gorgon's workflow execution engine.

1. Create src/gorgon/budget/router.py with the ModelRouter class
2. Create config/model_routing.yaml with tier definitions
3. Integrate into the workflow executor:
   - Before each agent step, classify the task
   - Override the agent's model with the routed model
   - Log the routing decision to the budget tracker
4. Add a /budget/routing-stats endpoint that shows:
   - Distribution of tasks across tiers (should trend toward 80/15/5)
   - Actual vs estimated costs per tier
   - Routing reasons breakdown

The YAML workflow should support per-step model overrides:
  - `model: premium` forces a specific tier
  - `model: auto` (default) uses the router
  - Agent role definitions can set a minimum tier

Test with: pytest tests/test_router.py
```

---

## Harvest 4: Skill Format Standardization (from ClawHub)

### What OpenClaw Does
Skills are SKILL.md files with YAML frontmatter declaring name, description, required env vars, required binaries, and runtime metadata. The registry validates these declarations against actual behavior.

### Gorgon Implementation

Standardize your existing skill format to match — this makes Gorgon skills potentially publishable to ClawHub and compatible with the broader ecosystem.

**Gorgon skill template:**
```markdown
---
name: code-review-agent
description: Reviews code changes for quality, security, and style issues.
version: 1.0.0
metadata:
  gorgon:
    agent_role: reviewer
    default_tier: mid
    min_tier: mid
    requires:
      env:
        - ANTHROPIC_API_KEY
      bins:
        - git
    capabilities:
      - code_review
      - security_analysis
      - style_checking
    inputs:
      - name: diff
        type: string
        required: true
        description: Git diff or file contents to review
      - name: language
        type: string
        required: false
        default: auto
    outputs:
      - name: findings
        type: array
        description: List of review findings
      - name: severity
        type: string
        enum: [pass, warn, fail]
    budget:
      max_tokens: 15000
      typical_tokens: 8000
---

# Code Review Agent

You are a code reviewer focused on quality, security, and maintainability.

## Behavior

1. Analyze the provided diff for issues
2. Classify each finding by severity (critical, warning, info)
3. Provide actionable fix suggestions
4. Return structured JSON output

## Output Format

Return JSON:
```json
{
  "findings": [
    {
      "file": "path/to/file",
      "line": 42,
      "severity": "warning",
      "category": "security",
      "message": "SQL injection risk",
      "suggestion": "Use parameterized queries"
    }
  ],
  "severity": "warn",
  "summary": "2 warnings, 1 info"
}
```

## Constraints

- Never modify files directly
- Always explain reasoning
- Flag uncertainty explicitly
```

**Skill registry:**
```python
# src/gorgon/skills/registry.py
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SkillMetadata:
    name: str
    description: str
    version: str
    agent_role: str
    default_tier: str
    min_tier: str
    required_env: list[str] = field(default_factory=list)
    required_bins: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    max_tokens: int = 10000
    typical_tokens: int = 5000


class SkillRegistry:
    """Discover, validate, and load Gorgon skills from SKILL.md files."""
    
    def __init__(self, skills_dir: Path = Path("skills/")):
        self.skills_dir = skills_dir
        self._skills: dict[str, SkillMetadata] = {}
        self._skill_prompts: dict[str, str] = {}
    
    def discover(self) -> dict[str, SkillMetadata]:
        """Scan skills directory and load all valid skills."""
        for skill_dir in self.skills_dir.iterdir():
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                meta, prompt = self._parse_skill(skill_file)
                if meta:
                    self._skills[meta.name] = meta
                    self._skill_prompts[meta.name] = prompt
        return self._skills
    
    def _parse_skill(self, path: Path) -> tuple[Optional[SkillMetadata], str]:
        """Parse SKILL.md frontmatter + body."""
        content = path.read_text()
        
        if not content.startswith("---"):
            return None, ""
        
        _, frontmatter, body = content.split("---", 2)
        meta = yaml.safe_load(frontmatter)
        gorgon = meta.get("metadata", {}).get("gorgon", {})
        
        return SkillMetadata(
            name=meta["name"],
            description=meta["description"],
            version=meta.get("version", "0.0.0"),
            agent_role=gorgon.get("agent_role", "general"),
            default_tier=gorgon.get("default_tier", "mid"),
            min_tier=gorgon.get("min_tier", "cheap"),
            required_env=gorgon.get("requires", {}).get("env", []),
            required_bins=gorgon.get("requires", {}).get("bins", []),
            capabilities=gorgon.get("capabilities", []),
            max_tokens=gorgon.get("budget", {}).get("max_tokens", 10000),
            typical_tokens=gorgon.get("budget", {}).get("typical_tokens", 5000),
        ), body.strip()
    
    def validate(self, name: str) -> list[str]:
        """Check if a skill's requirements are met. Returns list of issues."""
        import shutil
        import os
        
        issues = []
        meta = self._skills.get(name)
        if not meta:
            return [f"Skill '{name}' not found"]
        
        for env_var in meta.required_env:
            if not os.environ.get(env_var):
                issues.append(f"Missing env var: {env_var}")
        
        for binary in meta.required_bins:
            if not shutil.which(binary):
                issues.append(f"Missing binary: {binary}")
        
        return issues
    
    def get_prompt(self, name: str) -> Optional[str]:
        """Get the skill's system prompt (body of SKILL.md)."""
        return self._skill_prompts.get(name)
    
    def get_by_capability(self, capability: str) -> list[SkillMetadata]:
        """Find skills that declare a specific capability."""
        return [
            s for s in self._skills.values() 
            if capability in s.capabilities
        ]
```

**Claude Code prompt to implement:**
```
Standardize Gorgon's skill system using SKILL.md files with YAML frontmatter.

1. Create src/gorgon/skills/registry.py with SkillRegistry class
2. Create skills/ directory with template:
   - skills/code-review/SKILL.md
   - skills/static-analysis/SKILL.md  
   - skills/documentation/SKILL.md
3. Integrate with workflow engine:
   - When a workflow references an agent role, look up matching skill
   - Inject the skill's prompt as the agent's system message
   - Validate requirements before execution
   - Use the skill's budget hints for token allocation
4. Add CLI command: gorgon skills list (show discovered skills + validation)
5. Add CLI command: gorgon skills validate <name> (check requirements)

The frontmatter schema should include gorgon-specific metadata under 
metadata.gorgon (matching ClawHub's metadata.clawdbot pattern for 
ecosystem compatibility).
```

---

## Harvest 5: Cursor/State Persistence for Recurring Workflows (from Lobster)

### What Lobster Does
Workflows can persist state between runs — like "last processed email ID" — so the next run picks up where the previous one left off. This turns one-shot workflows into ongoing automations.

### Gorgon Implementation

```python
# src/gorgon/state/cursor.py
import json
import sqlite3
from pathlib import Path
from typing import Any, Optional
from datetime import datetime


class WorkflowCursor:
    """Persist workflow state between runs for recurring workflows."""
    
    def __init__(self, db_path: Path = Path("~/.gorgon/state/cursors.db")):
        self.db_path = db_path.expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cursors (
                    workflow_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (workflow_id, key)
                )
            """)
    
    def get(self, workflow_id: str, key: str, default: Any = None) -> Any:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value_json FROM cursors WHERE workflow_id = ? AND key = ?",
                (workflow_id, key),
            ).fetchone()
        if row:
            return json.loads(row[0])
        return default
    
    def set(self, workflow_id: str, key: str, value: Any):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO cursors 
                   (workflow_id, key, value_json, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (workflow_id, key, json.dumps(value), datetime.utcnow().isoformat()),
            )
    
    def get_all(self, workflow_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT key, value_json FROM cursors WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchall()
        return {k: json.loads(v) for k, v in rows}
    
    def clear(self, workflow_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM cursors WHERE workflow_id = ?", (workflow_id,)
            )
```

**YAML usage:**
```yaml
name: daily-pr-monitor
schedule: "0 9 * * *"  # cron: 9am daily
cursor:
  - last_checked_at    # auto-persisted between runs
  - known_pr_ids

steps:
  - id: fetch_prs
    agent: analyzer
    action: github_pr_list
    inputs:
      repo: $input.repo
      since: $cursor.last_checked_at  # reads from persistent cursor
    
  - id: filter_new
    action: filter
    inputs:
      items: $fetch_prs.output
      exclude: $cursor.known_pr_ids
    
  - id: update_cursor
    type: cursor_update
    set:
      last_checked_at: $now
      known_pr_ids: $fetch_prs.all_ids
```

---

## Harvest 6: Safety Constraints (from Lobster)

### What Lobster Does
- Timeouts per subprocess (default 20s, configurable)
- Max stdout size cap (default 512KB)
- Sandbox awareness (disabled in sandboxed contexts)
- No secret management (delegates to the caller's auth)

### Gorgon Implementation
Add to workflow step schema:

```yaml
# Per-step safety constraints
steps:
  - id: risky_step
    agent: builder
    action: execute_code
    constraints:
      timeout_seconds: 30
      max_output_bytes: 524288    # 512KB
      max_tokens: 20000
      sandbox: true               # run in isolated context
      requires_approval: false    # set true for destructive ops
      retry_on_failure: 2         # max retries
      retry_delay_seconds: 5
```

```python
# src/gorgon/engine/constraints.py
from dataclasses import dataclass
from typing import Optional


@dataclass 
class StepConstraints:
    timeout_seconds: int = 30
    max_output_bytes: int = 524288
    max_tokens: int = 20000
    sandbox: bool = False
    requires_approval: bool = False
    retry_on_failure: int = 0
    retry_delay_seconds: int = 5
    
    @classmethod
    def from_yaml(cls, data: dict) -> "StepConstraints":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def validate_output(self, output: bytes) -> bool:
        return len(output) <= self.max_output_bytes
    
    def validate_tokens(self, token_count: int) -> bool:
        return token_count <= self.max_tokens
```

---

## Implementation Priority

| Harvest | Priority | Effort | Impact |
|---------|----------|--------|--------|
| 1. Resume Tokens | **HIGH** | 2-3 hrs | Core API feature for Animus integration |
| 2. Approval Gates | **HIGH** | 2-3 hrs | Depends on #1, enables safe automation |
| 3. Model Routing | **HIGH** | 2 hrs | Direct cost savings, budget system enhancement |
| 4. Skill Format | **MEDIUM** | 1-2 hrs | Standardization, ecosystem compatibility |
| 5. Cursor State | **MEDIUM** | 1 hr | Enables recurring workflows |
| 6. Safety Constraints | **MEDIUM** | 1 hr | Should be built alongside #2 |

**Recommended order:** 1 → 2 → 6 → 3 → 4 → 5

Resume tokens and approval gates are the foundation — everything else builds on them. Model routing is high impact but independent. Skill format and cursor state are polish.

---

## What NOT to Harvest

- **Lobster's DSL/pipe syntax** — Gorgon uses YAML workflows, not shell pipes. Different paradigm, both valid. Don't bolt on a DSL.
- **OpenClaw's channel system** (WhatsApp/Telegram/etc.) — That's Animus territory.
- **OpenClaw's persona/identity system** — Also Animus.
- **The TypeScript implementation** — Gorgon is Python. Translate patterns, don't port code.
- **ClawHub as a platform** — You don't need a skill marketplace. Just use the SKILL.md format for internal consistency.
