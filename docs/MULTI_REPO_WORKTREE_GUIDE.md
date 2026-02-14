# Gorgon Multi-Repo Development Guide
## Git Worktrees + Parallel AI Agent Workflows

---

## 1. Directory Structure — How Everything Connects

```
~/projects/
├── gorgon/                          # MAIN REPO - Orchestration framework
│   ├── gorgon/
│   │   ├── __init__.py
│   │   ├── core.py                  # Main entry point
│   │   ├── errors.py                # Exception hierarchy
│   │   ├── contracts/               # Agent input/output contracts
│   │   │   ├── base.py
│   │   │   ├── definitions.py
│   │   │   └── validator.py
│   │   ├── state/                   # SQLite checkpoint/resume
│   │   │   ├── store.py
│   │   │   └── models.py
│   │   ├── workflow/                # YAML workflow engine
│   │   │   ├── loader.py
│   │   │   ├── executor.py
│   │   │   └── patterns/            # Orchestration patterns
│   │   │       ├── pipeline.py      # Linear (current)
│   │   │       ├── parallel.py      # Phase 3
│   │   │       ├── branching.py     # Phase 3
│   │   │       └── hierarchical.py  # Phase 3
│   │   ├── agents/                  # Agent implementations
│   │   │   ├── base.py
│   │   │   ├── planner.py
│   │   │   ├── builder.py
│   │   │   ├── tester.py
│   │   │   ├── reviewer.py
│   │   │   └── context_mapper.py    # NEW: Blitzy-inspired
│   │   ├── skills/                  # Skill loader (Phase 1)
│   │   │   ├── loader.py            # SkillLibrary class
│   │   │   ├── registry.py          # Registry parser
│   │   │   ├── validator.py         # Skill validation
│   │   │   └── mcp.py               # MCP bridge (Phase 4)
│   │   ├── memory/                  # Memory system (Phase 2)
│   │   │   ├── store.py
│   │   │   ├── short_term.py
│   │   │   ├── long_term.py
│   │   │   └── entity.py
│   │   ├── budget/                  # Token budget management
│   │   │   ├── tracker.py
│   │   │   └── policies.py
│   │   ├── logging/                 # Structured JSON logging
│   │   │   └── logger.py
│   │   └── cli/                     # CLI interface
│   │       └── main.py
│   ├── api/                         # FastAPI backend (Phase 5)
│   │   ├── main.py
│   │   ├── routes/
│   │   └── websocket.py
│   ├── dashboard/                   # React frontend (Phase 5)
│   │   ├── src/
│   │   └── package.json
│   ├── workflows/                   # Example YAML workflows
│   │   ├── feature-build.yaml
│   │   ├── code-review.yaml
│   │   └── vdc-analytics.yaml
│   ├── tests/
│   ├── docker/
│   ├── .github/workflows/
│   ├── pyproject.toml
│   ├── QUICKSTART.md
│   ├── CLAUDE.md                    # Project context for Claude Code
│   └── README.md
│
├── ai-skills/                       # SKILLS REPO - Agent capabilities
│   ├── personas/                    # Claude Code user skills
│   │   ├── senior-software-engineer/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   ├── senior-software-analyst/
│   │   │   └── SKILL.md
│   │   └── mentor-linux/
│   │       └── SKILL.md
│   ├── agents/                      # Gorgon agent skills
│   │   ├── system/
│   │   │   ├── file_operations/
│   │   │   │   ├── SKILL.md
│   │   │   │   ├── schema.yaml
│   │   │   │   ├── examples/
│   │   │   │   └── tools.py
│   │   │   └── process_management/
│   │   ├── browser/
│   │   │   ├── web_search/
│   │   │   └── web_scrape/
│   │   ├── email/
│   │   │   └── compose/
│   │   ├── integrations/
│   │   │   ├── github/
│   │   │   ├── slack/
│   │   │   └── gmail/
│   │   └── meta/                    # NEW: Meta-skills
│   │       └── context_mapper/      # Blitzy-inspired mapping
│   │           ├── SKILL.md
│   │           └── schema.yaml
│   ├── workflows/                   # YAML workflow templates
│   │   ├── context-mapping.yaml     # WHY/WHAT/HOW template
│   │   ├── code-generation.yaml
│   │   └── data-pipeline.yaml
│   ├── registry.yaml                # Master skill index
│   ├── skill-template.md            # Template for new skills
│   ├── CLAUDE.md                    # Project context for Claude Code
│   └── README.md
│
├── prompt-library/                  # PROMPTS REPO - Standalone
│   ├── patterns/
│   │   ├── extraction/
│   │   ├── transformation/
│   │   ├── reasoning/
│   │   ├── orchestration/
│   │   └── generation/
│   ├── domains/
│   │   ├── enterprise/
│   │   ├── development/
│   │   └── operations/
│   ├── templates/
│   │   └── PROMPT_TEMPLATE.md
│   └── README.md
│
└── .trees/                          # GIT WORKTREES (ephemeral)
    ├── gorgon-skills/               # Worktree: skill loader work
    ├── gorgon-memory/               # Worktree: memory system
    ├── gorgon-dashboard/            # Worktree: React frontend
    └── gorgon-patterns/             # Worktree: orchestration patterns
```

### How the repos connect

```
┌──────────────────────────────────────────────────────────────┐
│                        GORGON                                │
│                                                              │
│   gorgon/skills/loader.py ─── imports from ──┐               │
│                                              │               │
│   pyproject.toml:                            │               │
│     [tool.gorgon]                            │               │
│     skills_path = "~/.gorgon/skills"    ◄────┘               │
│     skills_repo = "github.com/AreteDriver/ai-skills"         │
│     skills_version = "v0.2.0"          # PINNED TAG          │
│     prompts_path = "~/.gorgon/prompts" # prompt-library sync │
│                                                              │
│   CLI:                                                       │
│     gorgon skills sync   # git checkout pinned tag           │
│     gorgon skills list   # show installed skills             │
│     gorgon skills validate  # check all skills valid         │
│     gorgon skills upgrade   # bump to latest tag             │
│                                                              │
│   YAML workflow prompt_ref:                                  │
│     stages:                                                  │
│       - name: analyze                                        │
│         prompt_ref: "reasoning/chain-of-thought"   ◄─────┐   │
│         agent: planner                                   │   │
│                                                          │   │
└──────────────────────────────────────────────────────────┼───┘
          │                                                │
          │ git checkout tag                               │ prompt_ref resolves
          ▼                                                ▼
┌────────────────────┐    ┌──────────────────────────────────┐
│     AI-SKILLS      │    │    PROMPT-LIBRARY                 │
│                    │    │                                  │
│ ~/.gorgon/skills/  │    │ ~/.gorgon/prompts/ (local cache) │
│ (pinned to tag)    │    │ Synced via gorgon prompts sync   │
│                    │    │                                  │
│ Breaking change?   │    │ Workflow YAML references patterns │
│ → bump tag in      │    │ by path: "reasoning/chain-of-    │
│   pyproject.toml   │    │ thought" → loads PROMPT.md        │
└────────────────────┘    └──────────────────────────────────┘
```

### Prompt-Library Integration

Gorgon workflows can reference prompt patterns from the prompt-library repo via the `prompt_ref` field in YAML workflow definitions. This resolves to a `PROMPT.md` file in the local cache:

```yaml
# Example: workflows/code-review.yaml
metadata:
  why: "Ensure code quality before merge"
  what: "Review PR for bugs, style, and architecture issues"
  how: "Multi-agent review with structured feedback"

stages:
  - name: analyze
    agent: planner
    prompt_ref: "reasoning/chain-of-thought"    # → ~/.gorgon/prompts/patterns/reasoning/chain-of-thought/PROMPT.md
  - name: review
    agent: reviewer
    prompt_ref: "extraction/structured-output"   # → ~/.gorgon/prompts/patterns/extraction/structured-output/PROMPT.md
```

The prompt-library is synced separately from skills and pinned independently. This keeps prompt engineering evolution decoupled from skill/tool changes.

---

## 2. Git Worktree Setup — Multi-Agent Parallel Development

Git worktrees let you check out **multiple branches** of the same repo into **separate directories**, sharing the same `.git` history. This is the key to running multiple Claude Code agents on the same repo without conflicts.

### Initial Setup

```bash
# Clone all repos
cd ~/projects
git clone git@github.com:AreteDriver/Gorgon.git gorgon
git clone git@github.com:AreteDriver/ai-skills.git ai-skills
git clone git@github.com:AreteDriver/prompt-library.git prompt-library

# Create worktree directory
mkdir -p ~/projects/.trees
```

### Creating Worktrees for Parallel Agent Work

```bash
cd ~/projects/gorgon

# Create worktrees for each major work stream
git worktree add -b feature/skill-loader   ~/projects/.trees/gorgon-skills
git worktree add -b feature/memory-system  ~/projects/.trees/gorgon-memory
git worktree add -b feature/dashboard      ~/projects/.trees/gorgon-dashboard
git worktree add -b feature/patterns       ~/projects/.trees/gorgon-patterns

# Verify
git worktree list
```

Output:
```
~/projects/gorgon                         abc1234 [main]
~/projects/.trees/gorgon-skills           abc1234 [feature/skill-loader]
~/projects/.trees/gorgon-memory           abc1234 [feature/memory-system]
~/projects/.trees/gorgon-dashboard        abc1234 [feature/dashboard]
~/projects/.trees/gorgon-patterns         abc1234 [feature/patterns]
```

### Running Multiple Claude Code Agents in Parallel

```bash
# Terminal 1 — Agent working on skill loader
cd ~/projects/.trees/gorgon-skills
claude  # or: claude-code "implement SkillLibrary loader class"

# Terminal 2 — Agent working on memory system
cd ~/projects/.trees/gorgon-memory
claude  # or: claude-code "implement cross-run memory store"

# Terminal 3 — Agent working on dashboard
cd ~/projects/.trees/gorgon-dashboard
claude  # or: claude-code "build workflow status React component"

# Terminal 4 — You reviewing/merging on main
cd ~/projects/gorgon
git log --all --oneline --graph
```

Each agent gets **complete isolation**: separate files, separate branch, zero conflicts. They all share the same git history so merging is clean.

### Scope Rules for Each Agent

Create a `.claude/rules.md` in each worktree to constrain the agent:

```bash
# In gorgon-skills worktree
cat > ~/projects/.trees/gorgon-skills/.claude/rules.md << 'EOF'
# Scope: Skill Loader System
- Work ONLY on files in gorgon/skills/ and tests/test_skills/
- Do not modify gorgon/agents/, gorgon/memory/, or dashboard/
- Branch: feature/skill-loader
- Safe to commit and push to origin/feature/skill-loader
EOF

# In gorgon-memory worktree
cat > ~/projects/.trees/gorgon-memory/.claude/rules.md << 'EOF'
# Scope: Memory System
- Work ONLY on files in gorgon/memory/ and tests/test_memory/
- Do not modify gorgon/skills/, gorgon/agents/, or dashboard/
- Branch: feature/memory-system
- Safe to commit and push to origin/feature/memory-system
EOF

# In gorgon-dashboard worktree
cat > ~/projects/.trees/gorgon-dashboard/.claude/rules.md << 'EOF'
# Scope: React Dashboard
- Work ONLY on files in dashboard/ and api/routes/
- Do not modify gorgon/ core Python code
- Branch: feature/dashboard
- Safe to commit and push to origin/feature/dashboard
EOF
```

### Merge Strategy

```bash
# When an agent finishes a feature:
cd ~/projects/gorgon  # main worktree

# Integration branch for testing combinations
git checkout -b integration

# Merge features one at a time, test between each
git merge feature/skill-loader
pytest tests/ -v
# If tests pass:
git merge feature/memory-system
pytest tests/ -v
# Continue...

# When integration is stable:
git checkout main
git merge integration
git push origin main

# Clean up worktrees
git worktree remove ~/projects/.trees/gorgon-skills
git worktree remove ~/projects/.trees/gorgon-memory
git branch -d feature/skill-loader
git branch -d feature/memory-system
```

---

## 3. Task Dependency Tree — What Work Happens Where

```
PHASE 0: Foundation Audit
│
├─ [gorgon repo]      Audit current code state
├─ [ai-skills repo]   Audit current code state
├─ [gorgon repo]      Run 8 Claude Code prompts if needed
└─ [both repos]       Push clean to GitHub
     │
     ├─────────────────────────────────────────┐
     │                                         │
PHASE 1: Skill System                   PHASE 2: Memory System
│ (can run in parallel)                  │ (can run in parallel)
│                                        │
├─ [gorgon]                              ├─ [gorgon]
│   worktree: gorgon-skills              │   worktree: gorgon-memory
│   ├─ SkillLibrary loader.py            │   ├─ Memory store (SQLite)
│   ├─ Skill validation CLI              │   ├─ Short-term memory
│   ├─ WHY/WHAT/HOW YAML schema          │   ├─ Long-term memory
│   └─ Skill install/sync CLI            │   ├─ Entity memory
│                                        │   └─ Memory injection
├─ [ai-skills]                           │
│   ├─ ContextMapper skill               └─── depends on Phase 0
│   ├─ 3 complete working skills         
│   ├─ registry.yaml finalized           
│   └─ skill-template.md                 
│                                        
└─── depends on Phase 0                  
     │
     │
     ├─────────────────────────────────────────┐
     │                                         │
PHASE 3: Orchestration Patterns          PHASE 4: Integrations & MCP
│ (can run in parallel)                  │ (depends on Phase 1)
│                                        │
├─ [gorgon]                              ├─ [gorgon]
│   worktree: gorgon-patterns            │   worktree: gorgon-integrations
│   ├─ Parallel execution                │   ├─ MCP server support
│   ├─ Conditional branching             │   ├─ MCP client support
│   ├─ Hierarchical delegation           │   └─ Webhook triggers
│   └─ Event-driven Flows                │
│                                        ├─ [ai-skills]
└─── depends on Phase 0                  │   ├─ GitHub integration skill
                                         │   ├─ Slack integration skill
                                         │   └─ Gmail integration skill
                                         │
                                         └─── depends on Phase 1
     │
     │
PHASE 5: Observability Dashboard
│ (depends on Phase 2)
│
├─ [gorgon]
│   worktree: gorgon-dashboard
│   ├─ Workflow status view
│   ├─ Agent reasoning trace
│   ├─ Budget consumption chart
│   ├─ Memory inspector
│   ├─ Skill registry browser
│   └─ WebSocket real-time updates
│
└─── depends on Phase 2 (memory) + Phase 0
     │
     │
PHASE 6: Polish & Launch
│ (depends on all phases)
│
├─ [gorgon]      QUICKSTART.md, architecture docs, CI
├─ [ai-skills]   README, contributing guide
├─ [all repos]   Final push, launch posts
│
└─── depends on Phases 1-5
```

### Parallel Execution Map

```
Week 1-2:
  Agent A (gorgon-skills):     ████████████████ Phase 1: Skill loader
  Agent B (gorgon-memory):     ████████████████ Phase 2: Memory system
  You (main):                  ██ Phase 0 audit → review/merge

Week 3-4:
  Agent A (gorgon-patterns):   ████████████████ Phase 3: Orchestration
  Agent B (gorgon-integrations):████████████████ Phase 4: MCP + integrations
  You (ai-skills repo):        ████████ Skills content + ContextMapper

Week 5-6:
  Agent A (gorgon-dashboard):  ████████████████ Phase 5: Dashboard
  You (main):                  ████████████████ Integration testing + merge

Week 7-8:
  You (all repos):             ████████████████ Phase 6: Polish + launch
```

**By using worktrees + parallel agents, you compress 10 weeks of serial work into ~6 weeks.**

---

## 4. Helper Scripts

### `worktree-new.sh` — Create a new agent workspace

```bash
#!/bin/bash
# Usage: ./worktree-new.sh <feature-name> <scope-description>
#
# Creates a worktree, branch, and .claude/rules.md in one command

FEATURE=$1
SCOPE=$2
REPO_ROOT=~/projects/gorgon
TREE_DIR=~/projects/.trees/gorgon-$FEATURE

if [ -z "$FEATURE" ] || [ -z "$SCOPE" ]; then
  echo "Usage: ./worktree-new.sh <feature-name> <scope-description>"
  echo "Example: ./worktree-new.sh skills 'gorgon/skills/ and tests/test_skills/'"
  exit 1
fi

cd $REPO_ROOT

# Create worktree + branch
git worktree add -b feature/$FEATURE $TREE_DIR
echo "Created worktree: $TREE_DIR on branch feature/$FEATURE"

# Create scope rules for Claude Code
mkdir -p $TREE_DIR/.claude
cat > $TREE_DIR/.claude/rules.md << EOF
# Scope: $FEATURE
- Read CLAUDE.md in the repo root for full project context
- Work ONLY on files in: $SCOPE
- Branch: feature/$FEATURE
- Safe to commit and push to origin/feature/$FEATURE
- Run tests before committing: pytest tests/ -v
- Do not modify files outside your scope
- Do NOT modify pyproject.toml or requirements.txt
- Document any new dependencies in DEPS_NEEDED.md at worktree root
  Format: - package_name >= version  # reason
EOF

# Create DEPS_NEEDED.md for dependency tracking
cat > $TREE_DIR/DEPS_NEEDED.md << EOF
# Dependencies Needed for feature/$FEATURE
# Agent: add entries here. Human merges to pyproject.toml on main.
# Format: - package_name >= version  # reason
EOF

echo "Agent rules written to $TREE_DIR/.claude/rules.md"
echo ""
echo "To start an agent:"
echo "  cd $TREE_DIR && claude"
```

### `worktree-status.sh` — Monitor all active agents

```bash
#!/bin/bash
# Show status of all active worktrees

REPO_ROOT=~/projects/gorgon

echo "=== Active Gorgon Worktrees ==="
echo ""

cd $REPO_ROOT
git worktree list --porcelain | while IFS= read -r line; do
  case "$line" in
    worktree\ *)
      path="${line#worktree }"
      echo "📂 $path"
      ;;
    branch\ *)
      branch="${line#branch refs/heads/}"
      echo "   🌿 Branch: $branch"
      # Show uncommitted changes count
      changes=$(cd "$path" 2>/dev/null && git status --porcelain | wc -l)
      if [ "$changes" -gt 0 ]; then
        echo "   ⚠️  Uncommitted changes: $changes files"
      else
        echo "   ✅ Clean"
      fi
      # Show commit count ahead of main
      ahead=$(cd "$path" 2>/dev/null && git rev-list main..$branch --count 2>/dev/null || echo "0")
      echo "   📊 Commits ahead of main: $ahead"
      echo ""
      ;;
  esac
done
```

### `worktree-merge.sh` — Merge a completed feature

```bash
#!/bin/bash
# Usage: ./worktree-merge.sh <feature-name>
#
# Merges a feature branch, runs tests, cleans up worktree

FEATURE=$1
REPO_ROOT=~/projects/gorgon
TREE_DIR=~/projects/.trees/gorgon-$FEATURE

if [ -z "$FEATURE" ]; then
  echo "Usage: ./worktree-merge.sh <feature-name>"
  exit 1
fi

cd $REPO_ROOT

echo "=== Merging feature/$FEATURE into main ==="

# Check for dependency requirements first
DEPS_FILE=$TREE_DIR/DEPS_NEEDED.md
if [ -f "$DEPS_FILE" ]; then
  DEPS_COUNT=$(grep -c "^- " $DEPS_FILE 2>/dev/null || echo "0")
  if [ "$DEPS_COUNT" -gt 0 ]; then
    echo ""
    echo "⚠️  This feature requires new dependencies:"
    grep "^- " $DEPS_FILE
    echo ""
    read -p "Have you added these to pyproject.toml on main? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      echo "Add dependencies to pyproject.toml first, then re-run merge."
      exit 1
    fi
  fi
fi

# Ensure main is up to date
git checkout main
git pull origin main

# Merge
git merge feature/$FEATURE --no-ff -m "Merge feature/$FEATURE: completed"

# Run tests
echo ""
echo "Running tests..."
pytest tests/ -v
TEST_EXIT=$?

if [ $TEST_EXIT -ne 0 ]; then
  echo ""
  echo "❌ Tests failed! Aborting merge."
  git merge --abort
  exit 1
fi

echo ""
echo "✅ Tests passed. Pushing..."
git push origin main

# Clean up
echo "Cleaning up worktree and branch..."
git worktree remove $TREE_DIR
git branch -d feature/$FEATURE

echo ""
echo "✅ feature/$FEATURE merged and cleaned up."
```

### `sync-skills.sh` — Sync ai-skills repo to local Gorgon cache (versioned)

```bash
#!/bin/bash
# Syncs ai-skills repo to ~/.gorgon/skills/ at a pinned version tag
# Prevents breaking changes from landing in a running Gorgon instance

SKILLS_REPO=~/projects/ai-skills
GORGON_SKILLS=~/.gorgon/skills
GORGON_PROMPTS=~/.gorgon/prompts
PROMPTS_REPO=~/projects/prompt-library

# Read pinned version from pyproject.toml (or default to latest tag)
PINNED_VERSION=$(grep 'skills_version' ~/projects/gorgon/pyproject.toml \
  | head -1 | sed 's/.*= *"\(.*\)"/\1/' 2>/dev/null)

echo "=== Syncing ai-skills to Gorgon ==="

# Pull latest refs
cd $SKILLS_REPO
git fetch --tags origin

if [ -n "$PINNED_VERSION" ]; then
  echo "Pinned version: $PINNED_VERSION"
  git checkout $PINNED_VERSION 2>/dev/null
  if [ $? -ne 0 ]; then
    echo "⚠️  Tag $PINNED_VERSION not found. Available tags:"
    git tag -l | tail -5
    echo "Falling back to main"
    git checkout main
    git pull origin main
  fi
else
  echo "No pinned version found, using main"
  git checkout main
  git pull origin main
fi

# Sync agent skills (not personas — those are Claude Code only)
mkdir -p $GORGON_SKILLS
rsync -av --delete $SKILLS_REPO/agents/ $GORGON_SKILLS/
cp $SKILLS_REPO/registry.yaml $GORGON_SKILLS/

echo "✅ Skills synced to $GORGON_SKILLS"
echo ""

# Sync prompt-library
if [ -d "$PROMPTS_REPO" ]; then
  echo "=== Syncing prompt-library ==="
  cd $PROMPTS_REPO
  git pull origin main
  mkdir -p $GORGON_PROMPTS
  rsync -av --delete $PROMPTS_REPO/patterns/ $GORGON_PROMPTS/patterns/
  rsync -av --delete $PROMPTS_REPO/templates/ $GORGON_PROMPTS/templates/
  echo "✅ Prompts synced to $GORGON_PROMPTS"
fi

echo ""

# Validate if Gorgon CLI is available
if command -v gorgon &> /dev/null; then
  echo "Running skill validation..."
  gorgon skills validate
else
  echo "Gorgon CLI not installed — skipping validation"
fi
```

### `upgrade-skills.sh` — Bump to latest ai-skills tag

```bash
#!/bin/bash
# Upgrades the pinned ai-skills version to the latest tag

SKILLS_REPO=~/projects/ai-skills

cd $SKILLS_REPO
git fetch --tags origin
LATEST=$(git tag -l 'v*' --sort=-v:refname | head -1)

if [ -z "$LATEST" ]; then
  echo "No version tags found in ai-skills repo"
  exit 1
fi

echo "Latest ai-skills tag: $LATEST"
echo ""

# Show what changed since current pin
CURRENT=$(grep 'skills_version' ~/projects/gorgon/pyproject.toml \
  | head -1 | sed 's/.*= *"\(.*\)"/\1/' 2>/dev/null)

if [ -n "$CURRENT" ]; then
  echo "Current pin: $CURRENT"
  echo "Changes since $CURRENT:"
  git log $CURRENT..$LATEST --oneline
  echo ""
fi

read -p "Upgrade to $LATEST? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
  sed -i "s/skills_version = \".*\"/skills_version = \"$LATEST\"/" \
    ~/projects/gorgon/pyproject.toml
  echo "✅ Updated pyproject.toml to $LATEST"
  echo "Run ./sync-skills.sh to apply"
fi
```

---

## 5. Multi-Agent Safety Rules

### The Integration Branch Pattern

Never merge feature branches directly to main. Always go through integration first:

```
feature/skill-loader ──┐
                       ├──► integration ──► main
feature/memory-system ─┘       │
                             tests
                             pass?
```

### File Scope Isolation

The key to parallel agents not breaking each other:

```
Agent A (skills):    gorgon/skills/*     tests/test_skills/*
Agent B (memory):    gorgon/memory/*     tests/test_memory/*
Agent C (dashboard): dashboard/*         api/routes/*
Agent D (patterns):  gorgon/workflow/patterns/*  tests/test_patterns/*
```

**Shared files that NO agent should touch:**
- `gorgon/__init__.py` (you wire this up manually after merge)
- `pyproject.toml` (dependency additions go through main)
- `README.md` (you write this)
- `.github/workflows/*` (CI changes go through main)

### Dependency Management Across Worktrees

Agents cannot modify `pyproject.toml` directly — it's a shared file that guarantees merge conflicts when two agents both add packages. Instead:

```bash
# Each worktree gets a DEPS_NEEDED.md that agents write to
cat > ~/projects/.trees/gorgon-skills/DEPS_NEEDED.md << 'EOF'
# Dependencies Needed for feature/skill-loader
# Agent: add entries here. Human merges to pyproject.toml on main.

- pyyaml >= 6.0       # YAML parsing for skill schemas
- jsonschema >= 4.0    # Skill schema validation
EOF
```

**Workflow:**
1. Agent documents needed deps in `DEPS_NEEDED.md` in its worktree
2. Agent writes code with the imports (assumes deps will be available)
3. Before merging, you read `DEPS_NEEDED.md` and add deps to `pyproject.toml` on main
4. Install deps, then merge the feature branch

Add this to the `.claude/rules.md` for every worktree:
```
- Do NOT modify pyproject.toml or requirements.txt
- Document any new dependencies in DEPS_NEEDED.md in the worktree root
- Format: `- package_name >= version  # reason`
```

### Test Isolation Across Worktrees

If two agents run `pytest` simultaneously and both use SQLite, they'll collide on the database file. Each worktree needs its own test database.

**`conftest.py` (in repo root, shared by all worktrees):**

```python
import os
import tempfile
from pathlib import Path

import pytest


def _worktree_id() -> str:
    """Derive a unique ID from the current git branch / worktree."""
    try:
        head_file = Path(".git")
        # Worktrees have .git as a file pointing to the real .git dir
        if head_file.is_file():
            # Extract worktree name from gitdir path
            gitdir = head_file.read_text().strip().split(": ")[1]
            return Path(gitdir).parent.name
        else:
            # Main worktree — use branch name
            ref = (head_file / "HEAD").read_text().strip()
            return ref.split("/")[-1].replace("/", "-")
    except Exception:
        return "default"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Give each worktree its own test database to prevent collisions."""
    wt = _worktree_id()
    db_path = tmp_path / f"gorgon-test-{wt}.db"
    monkeypatch.setenv("GORGON_DB_PATH", str(db_path))
    monkeypatch.setenv("GORGON_TEST_MODE", "1")
    return db_path


@pytest.fixture(autouse=True)
def isolated_skills(tmp_path, monkeypatch):
    """Each worktree gets its own skills cache for testing."""
    wt = _worktree_id()
    skills_path = tmp_path / f"skills-{wt}"
    skills_path.mkdir(exist_ok=True)
    monkeypatch.setenv("GORGON_SKILLS_PATH", str(skills_path))
    return skills_path
```

This means Agent A and Agent B can both run `pytest` at the same time with zero database collisions. The `tmp_path` fixture ensures complete isolation.

### CLAUDE.md Per Repo

Every repo needs a root-level `CLAUDE.md` that gives any Claude Code session full project context on cold start. Without this, every new agent session wastes tokens rediscovering architecture.

**`~/projects/gorgon/CLAUDE.md`:**

```markdown
# Gorgon — Claude Code Context

## What This Is
Multi-agent AI orchestration framework. Python 3.10+, FastAPI backend, React/TS frontend.

## Architecture
- gorgon/contracts/ — Agent input/output validation (jsonschema)
- gorgon/state/ — SQLite checkpoint/resume for workflow recovery
- gorgon/workflow/ — YAML workflow engine with orchestration patterns
- gorgon/agents/ — Planner, Builder, Tester, Reviewer, ContextMapper
- gorgon/skills/ — Skill loader (imports from external ai-skills repo)
- gorgon/memory/ — Cross-run memory (short-term, long-term, entity)
- gorgon/budget/ — Token budget management per-agent and per-workflow
- api/ — FastAPI backend with WebSocket real-time updates
- dashboard/ — React/TypeScript monitoring UI

## Coding Standards
- Type hints on all function signatures
- Docstrings on public methods
- Tests in tests/ mirroring source structure
- Run: pytest tests/ -v --cov=gorgon
- Format: black . && ruff check .

## What NOT To Modify
- pyproject.toml (add deps to DEPS_NEEDED.md instead)
- gorgon/__init__.py (wired up manually on main)
- .github/workflows/* (CI changes go through main branch only)

## Key Design Principles
- Budget controls are first-class, not bolted on
- Checkpoint/resume at every stage boundary
- Feedback loops: agents can reject work back to previous stages
- Skills are external and composable (ai-skills repo)
- WHY/WHAT/HOW metadata required on all workflow definitions
```

**`~/projects/ai-skills/CLAUDE.md`:**

```markdown
# AI Skills — Claude Code Context

## What This Is
Skill library for Gorgon multi-agent orchestration framework.
Two categories: personas (Claude Code behavior) and agents (Gorgon capabilities).

## Structure
- personas/ — Claude Code user skills (SKILL.md files that change Claude behavior)
- agents/ — Gorgon agent capabilities with SKILL.md + schema.yaml + tools.py
- workflows/ — YAML workflow templates with WHY/WHAT/HOW metadata
- registry.yaml — Master index of all agent skills

## Skill Anatomy
Every agent skill needs:
1. SKILL.md — Human + LLM readable instructions, safety rules, examples
2. schema.yaml — Input/output contracts, risk levels, consensus requirements
3. examples/ — Few-shot examples for the agent (optional)
4. tools.py — Python helper functions (optional)

## Consensus Levels (Triumvirate)
- any: 1 of 3 approval (low-risk reads)
- majority: 2 of 3 (medium-risk, recoverable)
- unanimous: 3 of 3 (high-risk, irreversible)
- unanimous + user: 3 of 3 + human confirm (critical ops)

## Adding New Skills
1. mkdir agents/category/skill_name/
2. Create SKILL.md from skill-template.md
3. Create schema.yaml with capability definitions
4. Add entry to registry.yaml
5. Tag a new version: git tag vX.Y.Z
```

### Rate Limits and Cost Control

Running 3-4 Claude Code agents in parallel means 3-4x the API spend. Apply Gorgon's own budget philosophy to your development process:

**Before spinning up parallel agents, set a session budget:**

```bash
# In your .bashrc or session startup
export ANTHROPIC_MAX_TOKENS_PER_SESSION=50000  # Per agent session cap

# Or use Claude Code's built-in cost tracking
# Check after each session:
claude --usage
```

**Cost guidelines per parallel session type:**

```
Scaffolding new module:     ~10-20K tokens  (predictable, bounded)
Implementing full feature:  ~30-50K tokens  (moderate, watch for loops)
Exploratory/debugging:      ~50-100K tokens (unpredictable, set hard cap)
```

**Rule of thumb:** If you're running 3 agents in parallel on implementation work, budget ~150K tokens for the session. That's roughly $3-5 depending on model. The same work sequentially would cost the same in tokens but 3x the wall-clock time.

**When to go parallel vs. serial:**
- Parallel: Agents working on fully isolated modules (skills, memory, dashboard)
- Serial: Work that touches shared interfaces or requires decisions from a previous step
- Never parallel: Two agents working on the same module or closely coupled code

### Conflict Resolution Protocol

If two agents need to modify the same file (rare with proper scoping):
1. One agent finishes first → merge to integration
2. Second agent rebases off integration: `git rebase integration`
3. Resolve conflicts manually
4. Continue

---

## 6. Quick Reference Commands

```bash
# === WORKTREE MANAGEMENT ===
git worktree add -b feature/X ~/projects/.trees/gorgon-X    # Create
git worktree list                                             # List all
git worktree remove ~/projects/.trees/gorgon-X               # Remove

# === PARALLEL AGENTS ===
cd ~/projects/.trees/gorgon-skills && claude                  # Start agent
cd ~/projects/.trees/gorgon-memory && claude                  # Start agent

# === SYNC & MERGE ===
cd ~/projects/gorgon && git merge feature/skill-loader        # Merge
./sync-skills.sh                                              # Sync skills

# === MONITORING ===
./worktree-status.sh                                          # All worktree status
git log --all --oneline --graph                               # Visual branch history

# === CLEANUP ===
git worktree prune                                            # Clean stale refs
git branch -d feature/X                                       # Delete merged branch
```

---

## 7. Recommended Workflow Per Session

```
Morning block (before shift):

1. Check worktree status + cost from previous session
   ./worktree-status.sh
   claude --usage  # review API spend from overnight agents

2. If agent work completed overnight, review + merge
   cd ~/projects/gorgon
   git diff main..feature/skill-loader
   # Check DEPS_NEEDED.md — add any new deps to pyproject.toml first
   cat ~/projects/.trees/gorgon-skills/DEPS_NEEDED.md
   pip install new-package-if-needed
   # Then merge
   ./worktree-merge.sh skill-loader

3. Spin up new agent(s) for next tasks
   ./worktree-new.sh memory "gorgon/memory/ and tests/test_memory/"
   cd ~/projects/.trees/gorgon-memory && claude

4. While agent runs, work on ai-skills content
   cd ~/projects/ai-skills
   # Write SKILL.md files, schema.yaml, examples
   # Tag when stable: git tag v0.2.0 && git push --tags

5. Sync before wrapping up
   ./sync-skills.sh
   git add . && git commit -m "session: added X skill"

6. Quick cost check
   claude --usage  # verify session stayed within budget
```

---

## 8. Version Lifecycle — When Things Change

### ai-skills Breaking Changes

When a skill schema changes in a way that could break running Gorgon workflows:

```
1. Make the change in ai-skills repo
2. Tag a new version:  git tag v0.3.0
3. Push:               git push --tags
4. In Gorgon repo, bump the pin:
   sed -i 's/skills_version = "v0.2.0"/skills_version = "v0.3.0"/' pyproject.toml
5. Run sync:           ./sync-skills.sh
6. Run tests:          pytest tests/ -v
7. If tests pass, commit the version bump
```

**Never sync to `main` without a version pin.** This is the same mistake OpenClaw made with their skill registry — untested community skills could break running instances.

### prompt-library Changes

Prompt patterns are lower risk than skill schemas (they're text, not contracts), but still version-aware:

```
1. Edit patterns in prompt-library repo
2. Test in a Gorgon workflow manually
3. Push to main
4. Sync:  ./sync-skills.sh  (handles both skills and prompts)
```

Prompt-library doesn't need version pinning yet — patterns are consumed as text, not as validated schemas. Add pinning later if the library grows large enough to warrant it.
