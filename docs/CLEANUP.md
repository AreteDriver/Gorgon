# Gorgon Cleanup: Remove Chat/User-Facing Features & Technical Debt

> **Purpose:** Refocus Gorgon as a headless orchestration engine with an ops dashboard.  
> **Rationale:** Animus owns the user-facing layer (chat, memory, identity). Gorgon is the orchestration API underneath — it doesn't need a chat interface, file upload UX, or conversational memory.  
> **Estimated Time:** 3-4 hours across multiple sessions  
> **Approach:** Each section has context, a Claude Code prompt, and a verification step.

---

## Architecture Reminder

```
User ←→ ANIMUS (chat, memory, identity, personality)
              ↓ API calls
         GORGON (orchestration, workflows, budgets, quality gates)
              ↓ coordination protocol
         CONVERGENT (multi-agent consensus, intent graph)
```

Gorgon exposes a **FastAPI REST API** and an **ops dashboard** (React). It does NOT:
- Chat with users directly
- Store conversational memory
- Handle file uploads from end users
- Manage user identity or personality

---

## Phase 1: Audit & Inventory

Before deleting anything, understand what exists.

### Prompt 1: Full Audit

```
Audit the Gorgon project for all chat, conversational, file upload, and 
user-facing features that should be removed. Gorgon is being refocused as 
a headless orchestration engine — Animus (a separate project) will own the 
user-facing chat layer.

Scan for and report:

1. CHAT COMPONENTS
   - Any chat UI components (React or otherwise)
   - Chat-related API routes/endpoints
   - WebSocket handlers for real-time chat
   - Chat message models/schemas
   - Chat history storage

2. CONVERSATIONAL MEMORY
   - Short-term memory (session/conversation context)
   - Long-term memory (persistent user context)
   - Entity memory (user/topic extraction)
   - Memory store implementations
   - Any ChromaDB, vector store, or embedding-related code for chat memory
   (NOTE: Keep workflow execution state/checkpoints — those are orchestration, not chat)

3. FILE UPLOAD UX
   - File upload endpoints designed for end-user document submission
   - File processing pipelines for user-uploaded content
   - Upload UI components
   (NOTE: Keep file operations that agents use internally during workflow execution)

4. USER-FACING IDENTITY
   - User profile/persona management
   - Onboarding flows
   - User preferences storage (beyond ops dashboard settings)

For each item found, report:
- File path
- What it does
- Whether it's safe to remove or has dependencies
- Recommended action (delete, refactor, or keep)

Output as a markdown checklist I can work through.
```

### Verification
- Review the generated checklist
- Confirm nothing in the orchestration core (workflow engine, budget tracker, checkpoint system, agent contracts) is flagged for removal
- Mark any items you want to keep with a note

---

## Phase 2: Remove Chat Interface

### Prompt 2: Strip Chat UI

```
Remove all chat/conversational UI components from Gorgon's React frontend.
The frontend should be an OPS DASHBOARD only — for monitoring workflows, 
viewing execution logs, managing budgets, and observing agent activity.

Specifically:
1. Delete any chat panel/window components
2. Delete chat message rendering components  
3. Delete chat input components (text input, send buttons for chat)
4. Remove chat-related routes from React Router
5. Remove chat-related state from Zustand stores
6. Remove any WebSocket connections used for real-time chat messages
7. Clean up imports — remove unused dependencies

Keep:
- Dashboard layout and navigation
- Workflow builder/viewer
- Execution monitor (this shows agent pipeline progress, NOT chat)
- Budget dashboard
- Checkpoint manager
- Any real-time WebSocket connections used for execution status updates

After removal, verify the dashboard still builds:
  cd frontend && npm run build

If there are TypeScript errors from broken imports, fix them.
```

### Verification
```bash
cd frontend
npm run build        # Should compile clean
npm run dev          # Spot-check — no chat panel visible
```

---

## Phase 3: Remove Chat API Routes

### Prompt 3: Strip Chat Backend

```
Remove all chat-related API routes and handlers from Gorgon's FastAPI backend.

Remove:
1. Any /chat or /conversation endpoints
2. Chat message CRUD operations
3. Chat session management endpoints  
4. Any middleware that handles chat context injection
5. WebSocket endpoints for chat streaming
6. Chat-related Pydantic models/schemas

Keep:
- /workflows/* endpoints (CRUD, trigger, status)
- /executions/* endpoints (monitor, logs, checkpoint/resume)
- /agents/* endpoints (status, capabilities, health)
- /budget/* endpoints (usage, limits, alerts)
- /health and /status endpoints
- WebSocket endpoints for execution progress streaming

After removal:
1. Run: uvicorn gorgon.api.main:app --reload
2. Check /docs (Swagger) — chat endpoints should be gone
3. Verify remaining endpoints still respond correctly
```

### Verification
```bash
uvicorn gorgon.api.main:app --reload
# Visit http://localhost:8000/docs
# Confirm: no chat endpoints listed
# Confirm: workflow/execution/budget endpoints still work
```

---

## Phase 4: Remove Conversational Memory System

This is the most nuanced step. Gorgon has memory concepts that serve TWO purposes — you need to keep orchestration state and remove conversational memory.

### Prompt 4: Separate Orchestration State from Chat Memory

```
Gorgon's memory system needs to be trimmed. Remove conversational memory 
while preserving orchestration state.

REMOVE (these belong in Animus):
- src/gorgon/memory/short_term.py — session/conversation context
- src/gorgon/memory/long_term.py — persistent user context across sessions
- src/gorgon/memory/entity.py — entity extraction from conversations
- src/gorgon/memory/store.py — IF it's primarily a memory store for chat 
  context (inspect first)
- Any vector database integrations (ChromaDB, FAISS, etc.) used for 
  semantic search over conversation history
- Any embedding generation code used for conversation memory

KEEP (these are orchestration, not chat):
- SQLite checkpoint/resume system (workflow state persistence)
- Workflow execution history/logs
- Agent output caching within a workflow run
- Budget tracking state
- Any context that passes between agents WITHIN a workflow execution

If store.py or any memory module serves dual purposes (both chat and 
orchestration), refactor it:
- Extract the orchestration-relevant parts into a new module 
  (e.g., src/gorgon/state/execution_context.py)
- Delete the chat-relevant parts

Update all imports throughout the codebase after removal.
Run tests to identify any breakage: pytest tests/
```

### Verification
```bash
pytest tests/                    # All orchestration tests should pass
grep -r "short_term\|long_term\|entity_memory\|chat_memory" src/  # Should return nothing
```

---

## Phase 5: Remove File Upload UX

### Prompt 5: Strip User File Upload

```
Remove end-user file upload features from Gorgon. File uploads are an 
Animus concern — users upload documents to Animus, which may then pass 
them to Gorgon workflows via API.

Remove:
1. File upload API endpoints designed for user document submission
2. File upload UI components (drag-drop zones, upload buttons, progress bars)
3. File type validation for user uploads
4. Temporary file storage/cleanup for user uploads

Keep:
- Internal file operations that agents use during workflow execution 
  (reading/writing files as part of a task)
- Workflow artifact storage (outputs from completed workflows)
- Any file handling in the agent tool system (agents reading codebases, 
  writing output files, etc.)

The distinction: Gorgon agents can work with files. Gorgon does NOT 
accept file uploads from end users through its own interface.
```

### Verification
```bash
# Frontend: no upload components visible
# API: no /upload endpoints in Swagger docs
# Agent file operations still work in workflow execution
```

---

## Phase 6: Technical Debt Cleanup

Now that the chat/upload/memory cruft is removed, clean up what's left.

### Prompt 6: Dependency Cleanup

```
Clean up Gorgon's dependencies after removing chat, memory, and upload features.

1. PYTHON (pyproject.toml / requirements.txt):
   - Remove any packages only used by deleted features:
     - chromadb, faiss-cpu, or similar vector stores (if only for chat memory)
     - sentence-transformers or embedding libraries (if only for chat memory)
     - python-multipart (if only for file uploads, check FastAPI still needs it)
     - websockets libraries only used for chat streaming
   - Run: pip install -e . && pytest tests/
   - Run: pip-audit (if available) to check for security issues

2. JAVASCRIPT (frontend/package.json):
   - Remove packages only used by deleted components
   - Common candidates: file upload libraries, chat UI kits, markdown 
     renderers for chat messages, emoji pickers
   - Run: cd frontend && npm prune && npm run build

3. DOCKER:
   - Update Dockerfile if it installed dependencies for removed features
   - Update docker-compose.yml if it mounted volumes for chat storage 
     or vector databases
   - Remove any docker services for vector DBs (chromadb container, etc.)

4. ENVIRONMENT VARIABLES:
   - Remove env vars for chat/memory features from .env.example
   - Clean up config files that reference removed features

List everything removed and verify the project still builds and tests pass.
```

### Prompt 7: Dead Code & Import Cleanup

```
Scan Gorgon for dead code, unused imports, and orphaned files after the 
chat/memory/upload removal.

1. Run a dead code analysis:
   - Check for Python files with no imports pointing to them
   - Check for React components not referenced in any route or parent
   - Check for API routes not connected to the FastAPI app
   - Check for test files testing deleted features

2. Clean up:
   - Remove orphaned test files
   - Remove empty __init__.py files for deleted packages
   - Remove any migration files for deleted database tables
   - Remove stale configuration entries

3. Verify project structure is clean:
   - No empty directories (except intentional ones like /workflows)
   - No circular import issues
   - All remaining imports resolve

4. Run full test suite and fix any remaining failures:
   pytest tests/ -v --tb=short
```

### Prompt 8: API Contract Hardening

```
Now that Gorgon is a clean orchestration engine, harden its API contract.
This API is what Animus will call.

1. Review and document all remaining FastAPI endpoints:
   - Method, path, request/response schemas
   - Authentication requirements  
   - Rate limiting considerations

2. Ensure all endpoints have:
   - Proper Pydantic request/response models (no raw dicts)
   - Consistent error response format
   - OpenAPI documentation (descriptions, examples)

3. Create or update: docs/API.md with the full endpoint reference

4. Verify the API is Animus-ready:
   - Can an external service trigger a workflow? (POST /workflows/{id}/execute)
   - Can an external service check execution status? (GET /executions/{id})
   - Can an external service retrieve results? (GET /executions/{id}/results)
   - Is there a webhook/callback mechanism for completion notifications?

If any of these are missing, stub them out with TODO comments and proper 
route signatures.
```

---

## Phase 7: Frontend Refocus

### Prompt 9: Dashboard Polish

```
Refocus Gorgon's React frontend as a pure ops dashboard. Now that chat 
and upload features are removed, ensure the remaining pages are clean 
and functional.

The dashboard should have these views:

1. DASHBOARD (home)
   - Active workflow count
   - Running/queued/completed execution stats
   - Token budget usage summary
   - Recent execution timeline

2. WORKFLOWS
   - List/grid of defined workflows
   - Workflow detail view (YAML definition, agent roles, dependencies)
   - Trigger workflow button

3. EXECUTIONS  
   - Live execution monitor (real-time status via WebSocket)
   - Execution detail view (step progress, agent outputs, logs)
   - Checkpoint/resume controls
   - Error details with retry option

4. BUDGET
   - Token usage by agent, by workflow, by time period
   - Budget limits and alerts
   - Cost projections

5. AGENTS
   - Registered agent list with capabilities
   - Health/availability status
   - Performance metrics (avg completion time, error rate)

Remove or update:
- Navigation items pointing to deleted pages
- Any "chat" or "upload" entries in sidebar/nav
- Empty/broken pages
- Placeholder components that reference removed features

Ensure the layout is clean and all remaining pages render without errors.
```

---

## Phase 8: Verification & Documentation

### Prompt 10: Final Verification

```
Run a final verification pass on the cleaned-up Gorgon project:

1. BUILD VERIFICATION
   - Backend: pip install -e . (no errors)
   - Frontend: cd frontend && npm run build (no errors)  
   - Docker: docker-compose build (no errors)
   - Tests: pytest tests/ -v (all pass)

2. RUNTIME VERIFICATION
   - Start backend: uvicorn gorgon.api.main:app
   - Start frontend: cd frontend && npm run dev
   - Verify Swagger docs at /docs show only orchestration endpoints
   - Verify dashboard loads with all 5 views functional

3. DOCUMENTATION UPDATE
   - Update README.md:
     - Remove any references to chat features
     - Remove any references to file upload
     - Remove any references to conversational memory
     - Update architecture diagram to show Gorgon as headless orchestration
     - Add note: "User-facing interface provided by Animus"
     - Update installation instructions if dependencies changed
   - Update QUICKSTART.md if it references removed features
   - Update any architecture docs

4. GIT CLEANUP
   - Stage all changes
   - Create a single clean commit: 
     "refactor: remove user-facing features, refocus as headless orchestration engine
     
     Gorgon is now a pure orchestration API + ops dashboard.
     Chat interface, conversational memory, and file upload UX 
     have been removed — these responsibilities belong to Animus.
     
     - Removed: chat UI, chat API routes, memory system (short/long/entity)
     - Removed: file upload endpoints and UI components  
     - Cleaned: dependencies, dead code, orphaned files
     - Hardened: API contract for external consumption (Animus integration)
     - Updated: documentation and architecture diagrams"
```

---

## Quick Reference: What Stays vs. What Goes

| Component | Keep? | Reason |
|-----------|-------|--------|
| Workflow engine (YAML pipelines) | ✅ | Core orchestration |
| Agent contracts & roles | ✅ | Core orchestration |
| Token budget management | ✅ | Core orchestration |
| SQLite checkpoints | ✅ | Workflow state persistence |
| Structured logging | ✅ | Observability |
| FastAPI REST API | ✅ | Gorgon's interface to Animus |
| Execution WebSocket | ✅ | Real-time ops monitoring |
| React ops dashboard | ✅ | Admin monitoring tool |
| CLI interface | ✅ | Developer/admin tool |
| Chat UI components | ❌ | → Animus |
| Chat API routes | ❌ | → Animus |
| Chat WebSocket | ❌ | → Animus |
| Short-term memory | ❌ | → Animus |
| Long-term memory | ❌ | → Animus |
| Entity memory | ❌ | → Animus |
| Vector store (for chat) | ❌ | → Animus |
| File upload UX | ❌ | → Animus |
| User profiles/personas | ❌ | → Animus |

---

## Notes

- **Don't delete the memory module concepts entirely from your brain** — they'll resurface in Animus's architecture. The patterns are good, they just live in the wrong project.
- **The Triumvirate (Utrennyaya, Vechernyaya, Polunochnaya)** stays — that's agent consensus within Gorgon, not user-facing.
- **Skills system stays** — skills are agent capabilities, not user features.
- **After this cleanup**, Gorgon should be deployable as a standalone service that any client (Animus, CLI, CI/CD pipeline, webhook) can call via REST API.
