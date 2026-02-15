# Changelog

All notable changes to Gorgon will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-02-14

### Added
- **SQLite Task History** (TODO 2) — Migration 010 with `task_history`, `agent_scores`, `budget_log` tables. `TaskStore` class with record/query/stats. JobManager history hook. Bot `/history` and CLI `gorgon history` commands
- **Session Budget Passthrough** (TODO 3) — `BudgetManager` with `get_budget_context()` prompt injection. Daily token limits via `budget_log`. Budget gate in supervisor (`MIN_DELEGATION_TOKENS`). CLI `budget daily` and bot `/budget` commands
- **Consensus Voting** — `_run_consensus_vote()` in supervisor, GorgonBridge request/vote/evaluate integration
- **Ollama Fallback Chain** (TODO 4) — Configurable provider order with output validation
- **Git Conflict Detection** (TODO 5) — `ConflictResult` dataclass + `check_conflicts()` dry-run merge in PRManager
- **PersistentBudgetManager** — `BudgetManager` optionally backed by SQLite (`budget_session_usage` table). Survives session restarts. Migration 011
- **Coverage enforcement** — 75% `fail_under` threshold in pyproject.toml and CI
- **Integration tests** — Budget persistence round-trips, daily limit enforcement, supervisor prompt injection, budget gate, bot command e2e

### Changed
- God objects decomposed: 5/6 complete (cli/main, api, executor, renderers, state/memory)
- Convergent v0.5.0 integration (GorgonBridge, stigmergy/flocking/phi enrichment)
- v2 skill schema wiring (routing, consensus, verification)
- Version consistency: pyproject.toml and `__init__.__version__` now both `1.1.0`
- 5,450+ tests

### Fixed
- MCP test pollution (shared `shutting_down` state reset in fixture)
- Version mismatch between pyproject.toml (was 1.0.0) and `__init__.py` (was 0.1.0)

## [0.2.0] - 2026-02-01

### Added
- **Chat Interface** - Conversational AI interface with session persistence
  - `ChatSessionManager`: Session lifecycle and message storage
  - `ChatMessage`, `ChatSession`, `ChatMode` models
  - FastAPI routes for chat CRUD and streaming responses
  - Full React frontend with markdown/code rendering
  - Agent attribution on messages (shows which agent authored each response)
  - Session history and archival
- **Supervisor Agent** - Intelligent task delegation system
  - `SupervisorAgent`: Analyzes requests and delegates to specialized sub-agents
  - `AgentProvider`: Abstraction layer for AI providers (OpenAI, Anthropic)
  - `AgentDelegation`: Tracks delegation decisions and results
  - Routes tasks to Planner, Builder, Tester, Reviewer, etc. based on intent
- **Self-Improvement System** - Autonomous codebase improvement with safety guards
  - 10-stage workflow: analyze → plan → approve → implement → test → approve → snapshot → apply → PR → approve
  - `SafetyChecker`: Protected files (auth, security, credentials), change limits (10 files, 500 lines max)
  - `ApprovalGate`: Human approval required at plan, apply, and merge stages
  - `RollbackManager`: Snapshot/restore capability for safe rollback
  - `Sandbox`: Isolated execution environment for testing changes
  - `PRManager`: Automatic branch and PR creation
  - Auto-rollback on test failures
  - Cannot modify its own safety module (no recursive self-modification)
- **Parallel Agent Execution** with rate-limited parallel execution for AI workflows
  - `RateLimitedParallelExecutor`: Per-provider concurrency control with semaphores
  - `AdaptiveRateLimitConfig/State`: Dynamic rate limit adjustment based on 429 responses
  - `DistributedRateLimiter`: Cross-process rate limiting (SQLite/Redis backends)
  - Automatic provider detection from task metadata
  - `create_rate_limited_executor()` factory with sensible defaults
- **Async Provider Support**: Native async methods for AI providers
  - `Provider.complete_async()` and `Provider.generate_async()`
  - `ProviderManager.complete_async()` with fallback support
  - `ClaudeCodeClient.execute_agent_async()` for async agent execution
- **Documentation**
  - `docs/PARALLEL_EXECUTION.md` with usage guide
  - Comprehensive README, CONTRIBUTING.md, ARCHITECTURE.md
  - Structured docs/ directory with documentation index
  - examples/ directory with sample workflows

### Changed
- Improved repository structure with proper organization
- Updated documentation to be more comprehensive
- `WorkflowEngineAdapter` now the recommended way to interact with workflows
- Deprecated `WorkflowEngine` class (use `WorkflowEngineAdapter` instead)
- 3,200+ tests with 83% coverage

## [0.1.0] - 2024-12-08

### Added
- Initial project setup
- Core workflow orchestration engine
- OpenAI, GitHub, Notion, and Gmail integrations
- FastAPI REST API with authentication
- Streamlit dashboard UI
- Prompt template management system
- Token-based authentication
- Configuration management with Pydantic
- Example workflows (simple AI completion, email to Notion, SOP to GitHub)
- Logging system for workflow execution
- Quick start guide (QUICKSTART.md)
- Implementation documentation (IMPLEMENTATION.md)
- Environment configuration (.env.example)
- Convenience scripts (init.sh, run_api.sh, run_dashboard.sh)
- Poetry and pip dependency management

### Features
- Multi-step workflow execution
- Variable interpolation between steps
- Error handling and recovery
- JSON-based workflow definitions
- Reusable prompt templates
- OAuth 2.0 support for Gmail
- Auto-generated API documentation (OpenAPI/Swagger)
- Interactive web dashboard
- Health check endpoints

[Unreleased]: https://github.com/AreteDriver/Gorgon/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/AreteDriver/Gorgon/compare/v0.2.0...v1.1.0
[0.2.0]: https://github.com/AreteDriver/Gorgon/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/AreteDriver/Gorgon/releases/tag/v0.1.0
