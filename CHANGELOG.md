# Changelog

All notable changes to Gorgon will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive README with project overview and features
- CONTRIBUTING.md with contribution guidelines
- ARCHITECTURE.md with technical architecture details
- LICENSE file (MIT License)
- Structured docs/ directory with documentation index
- examples/ directory with sample workflows
- tests/ directory structure for future test implementation
- Enhanced .gitignore for better repository hygiene
- CHANGELOG.md for tracking project changes
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
- **Documentation**: Added `docs/PARALLEL_EXECUTION.md` with usage guide

### Changed
- Improved repository structure with proper organization
- Updated documentation to be more comprehensive
- `WorkflowEngineAdapter` now the recommended way to interact with workflows
- Deprecated `WorkflowEngine` class (use `WorkflowEngineAdapter` instead)

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

[Unreleased]: https://github.com/AreteDriver/Gorgon/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/AreteDriver/Gorgon/releases/tag/v0.1.0
