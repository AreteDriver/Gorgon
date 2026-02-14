# Gorgon Implementation Prompts for Claude Code

> Copy each prompt into Claude Code sequentially. Wait for completion before moving to next.
> Test after each prompt: `pytest tests/ -v`
> Commit after each prompt: `git add . && git commit -m "Implement <feature>"`

**Estimated Total: ~4-5 hours focused work**

| Prompt | Feature | Est. Time |
|--------|---------|-----------|
| 1 | Project Setup & Contracts | 30 min |
| 2 | State Persistence | 30 min |
| 3 | YAML Workflows | 45 min |
| 4 | Budget Management | 30 min |
| 5 | Structured Logging | 20 min |
| 6 | CLI Interface | 30 min |
| 7 | Agent Implementation | 45 min |
| 8 | Integration & Final Assembly | 30 min |

---

## Pre-Flight Checklist

Before starting, ensure the repo is properly set up:

```bash
# Verify repo exists and is renamed from AI-Orchestra
cd ~/projects/Gorgon
git remote -v  # Should point to git@github.com:AreteDriver/Gorgon.git

# If not yet renamed:
git remote set-url origin git@github.com:AreteDriver/Gorgon.git
git push -u origin main
```

---

## Prompt 1: Project Setup & Contracts

```
I'm building Gorgon, a multi-agent orchestration framework. Start by setting up the project structure and implementing agent contracts.

Project location: ~/projects/Gorgon

Create this structure:
gorgon/
├── __init__.py
├── errors.py
├── contracts/
│   ├── __init__.py
│   ├── base.py
│   ├── definitions.py
│   └── validator.py

Requirements:

1. errors.py - Define exception hierarchy:
   - GorgonError (base)
   - AgentError (with subclasses: TimeoutError, TokenLimitError, ContractViolationError, APIError, ValidationError)
   - BudgetExceededError
   - WorkflowError (with subclasses: StageFailedError, MaxRetriesError)
   - Each error should have a `code` class attribute

2. contracts/base.py:
   - AgentRole enum (PLANNER, BUILDER, TESTER, REVIEWER)
   - AgentContract dataclass with: role, input_schema (dict), output_schema (dict)
   - validate_input() and validate_output() methods using jsonschema
   - ContractViolation exception

3. contracts/definitions.py - Define contracts for each agent:
   - PLANNER_CONTRACT: input needs request+context, output needs tasks+architecture+success_criteria
   - BUILDER_CONTRACT: input needs plan+task_id, output needs code+files_created+status
   - TESTER_CONTRACT: input needs code+success_criteria, output needs passed+tests_run+results array
   - REVIEWER_CONTRACT: input needs code+plan+test_results, output needs approved+score+findings array

4. contracts/validator.py:
   - ContractValidator class that validates handoffs between agents
   - validate_handoff(from_agent, to_agent, data) method

Add requirements.txt with: jsonschema>=4.0.0

Create tests/test_contracts.py with basic validation tests.
```

---

## Prompt 2: State Persistence

```
Continue building Gorgon. Now implement state persistence for workflow checkpointing and resume.

Add to the project:
gorgon/
├── state/
│   ├── __init__.py
│   ├── persistence.py
│   └── checkpoint.py

Requirements:

1. state/persistence.py - SQLite-backed state storage:
   - WorkflowStatus enum (PENDING, RUNNING, PAUSED, COMPLETED, FAILED)
   - StatePersistence class with db_path parameter (default: gorgon-state.db)
   - Tables: workflows (id, name, status, current_stage, created_at, updated_at, config JSON, error)
   - Table: checkpoints (id, workflow_id, stage, status, input_data JSON, output_data JSON, tokens_used, duration_ms, created_at)
   - Methods:
     - create_workflow(workflow_id, name, config)
     - checkpoint(workflow_id, stage, status, input_data, output_data, tokens_used, duration_ms)
     - get_last_checkpoint(workflow_id) -> dict or None
     - get_resumable_workflows() -> list of workflows with status in (running, paused, failed)
     - resume_from_checkpoint(workflow_id) -> checkpoint dict, updates status to RUNNING
     - mark_complete(workflow_id)
     - mark_failed(workflow_id, error_message)

2. state/checkpoint.py:
   - CheckpointManager class that wraps StatePersistence
   - Context manager for automatic checkpointing: with checkpoint_manager.stage("building"): ...
   - Auto-captures exceptions and marks failed

Create tests/test_state.py:
- Test workflow creation
- Test checkpointing
- Test resume functionality
- Use temporary database for tests
```

---

## Prompt 3: YAML Workflow Definitions

```
Continue building Gorgon. Now implement YAML workflow definitions.

Add to the project:
gorgon/
├── workflow/
│   ├── __init__.py
│   ├── loader.py
│   └── executor.py
workflows/
├── feature-build.yaml
├── bug-fix.yaml
└── refactor.yaml

Requirements:

1. workflow/loader.py:
   - Dataclasses: AgentConfig, StageConfig, WorkflowConfig
   - WorkflowLoader class:
     - __init__(workflows_dir="workflows")
     - load(workflow_name) -> WorkflowConfig
     - validate(config) -> list of error strings
     - list_workflows() -> list of workflow names

2. YAML workflow schema supports:
   - name, version, description
   - settings: max_retries, timeout_minutes, budget_tokens
   - agents: each with budget_tokens, retries, timeout_seconds, feedback_from, can_reject_to
   - flow: list of stages with agent, on_success, on_failure, pass_data
   - hooks: on_start, on_complete, on_failure (list of actions)

3. Create workflows/feature-build.yaml:
   - 4 stages: planning -> building -> testing -> reviewing
   - Tester can reject to builder
   - Reviewer can reject to builder
   - Budget: 50000 total, planner 5000, builder 30000, tester 10000, reviewer 5000

4. Create workflows/bug-fix.yaml:
   - Simplified: planning -> building -> testing
   - Lower budgets, faster timeouts

5. Create workflows/refactor.yaml:
   - Focus on reviewer feedback loops
   - Multiple review cycles allowed

6. workflow/executor.py:
   - WorkflowExecutor class
   - __init__(config: WorkflowConfig, persistence: StatePersistence)
   - execute(request: str) -> runs through all stages
   - Integrates with contracts for validation
   - Integrates with persistence for checkpointing

Create tests/test_workflow.py:
- Test YAML loading
- Test validation catches errors
- Test executor stage transitions
```

---

## Prompt 4: Budget Management

```
Continue building Gorgon. Now implement token budget management.

Add to the project:
gorgon/
├── budget/
│   ├── __init__.py
│   ├── manager.py
│   └── strategies.py

Requirements:

1. budget/manager.py:
   - BudgetStatus enum (OK, WARNING >80%, CRITICAL >95%, EXCEEDED)
   - BudgetAllocation dataclass: total, used, reserved
     - Properties: available, utilization, status
   - BudgetManager class:
     - __init__(workflow_budget, agent_budgets dict)
     - request(agent, tokens) -> bool (can we afford this?)
     - consume(agent, tokens) -> records usage
     - get_allocation(agent) -> BudgetAllocation
     - get_workflow_allocation() -> BudgetAllocation
     - suggest_reduced_scope(agent) -> dict with suggestions when low
     - report() -> full usage report dict

2. budget/strategies.py - Degradation strategies:
   - BudgetStrategy abstract base class
   - ConservativeStrategy: stop early, preserve budget for critical stages
   - AggressiveStrategy: use full budget, fail if exceeded
   - AdaptiveStrategy: reduce scope dynamically based on remaining budget
   - Each has: should_proceed(manager, agent, estimated_tokens) -> bool
   - Each has: adjust_request(manager, agent, original_request) -> modified request

3. Integrate with WorkflowExecutor:
   - Pass BudgetManager to executor
   - Check budget before each agent call
   - Apply degradation strategy when WARNING or CRITICAL
   - Raise BudgetExceededError when EXCEEDED

Create tests/test_budget.py:
- Test allocation tracking
- Test status thresholds
- Test degradation strategies
```

---

## Prompt 5: Structured Logging

```
Continue building Gorgon. Now implement structured JSON logging with trace IDs.

Add to the project:
gorgon/
├── logging.py

Requirements:

1. logging.py:
   - JSONFormatter class (extends logging.Formatter)
     - Outputs JSON with: timestamp, level, message, logger
     - Includes custom fields if present: workflow_id, stage, agent, tokens, trace_id, duration_ms
   
   - GorgonLogger class:
     - __init__(name, workflow_id=None, trace_id=None)
     - Auto-generates trace_id if not provided (uuid4)
     - Methods: info, warning, error, debug
     - Each accepts **kwargs for extra fields
     - stage_context(stage_name) -> context manager that adds stage to all logs
   
   - get_logger(name) -> configured GorgonLogger

2. Log levels and when to use:
   - DEBUG: Contract validation details, checkpoint data
   - INFO: Stage start/complete, workflow start/complete
   - WARNING: Budget warning threshold, retry attempts
   - ERROR: Stage failures, contract violations, budget exceeded

3. Integrate throughout:
   - WorkflowExecutor logs stage transitions
   - BudgetManager logs warnings and consumption
   - StatePersistence logs checkpoints
   - ContractValidator logs validation results

4. Add log output configuration:
   - GORGON_LOG_LEVEL env var
   - GORGON_LOG_FILE env var (optional file output)
   - GORGON_LOG_FORMAT env var (json or text)

Example output:
{"timestamp": "2024-01-15T10:30:00Z", "level": "INFO", "message": "Stage complete", "workflow_id": "wf-123", "stage": "building", "tokens": 1500, "trace_id": "abc-123", "duration_ms": 4500}

Create tests/test_logging.py
```

---

## Prompt 6: CLI Interface

```
Continue building Gorgon. Now implement the CLI interface.

Add to the project:
gorgon/
├── cli.py

Requirements:

1. Use argparse (no external dependencies)

2. Commands:

   gorgon run <workflow> "<request>"
   - Load workflow YAML
   - Execute with full instrumentation
   - Options: --budget, --timeout, --dry-run, --verbose

   gorgon resume <workflow-id>
   - List resumable workflows if no ID given
   - Resume from last checkpoint

   gorgon list
   - List available workflows

   gorgon validate <workflow>
   - Validate workflow YAML without running

   gorgon status <workflow-id>
   - Show workflow status and checkpoints

   gorgon budget-report <workflow-id>
   - Show token usage breakdown

   gorgon history
   - List recent workflow runs
   - Options: --limit, --status filter

3. Output formatting:
   - Default: human-readable with colors (if terminal)
   - --json flag for JSON output
   - --quiet flag for minimal output

4. Error handling:
   - Catch all GorgonErrors and display nicely
   - Exit codes: 0 success, 1 workflow failed, 2 config error, 3 system error

5. Add entry point in setup.py or pyproject.toml:
   gorgon = gorgon.cli:main

Create tests/test_cli.py with subprocess tests for each command.
```

---

## Prompt 7: Agent Base Implementation

```
Continue building Gorgon. Now implement the base agent class and concrete agents.

Add to the project:
gorgon/
├── agents/
│   ├── __init__.py
│   ├── base.py
│   ├── planner.py
│   ├── builder.py
│   ├── tester.py
│   └── reviewer.py

Requirements:

1. agents/base.py:
   - BaseAgent abstract class:
     - __init__(contract: AgentContract, budget_manager: BudgetManager, logger: GorgonLogger)
     - abstract execute(input_data: dict) -> dict
     - _validate_input(data) - uses contract
     - _validate_output(data) - uses contract
     - _call_llm(prompt, max_tokens) - placeholder for LLM integration
     - _estimate_tokens(prompt) -> rough token count

2. agents/planner.py - PlannerAgent:
   - Takes request and context
   - Outputs structured plan with tasks, architecture, success_criteria
   - Prompt template for planning

3. agents/builder.py - BuilderAgent:
   - Takes plan and specific task
   - Can receive feedback from tester/reviewer
   - Outputs code and file list
   - Prompt template for implementation

4. agents/tester.py - TesterAgent:
   - Takes code and success criteria
   - Generates and "runs" tests (simulated for now)
   - Outputs pass/fail with detailed results
   - Can provide feedback_for_builder

5. agents/reviewer.py - ReviewerAgent:
   - Takes code, plan, and test results
   - Outputs approval decision with score and findings
   - Can provide rework_instructions

6. Each agent:
   - Implements execute() following its contract
   - Tracks token usage via budget_manager
   - Logs via logger with agent context

7. For now, _call_llm can be a stub that returns mock data.
   Add TODO comment for Claude API integration.

Create tests/test_agents.py with mock LLM responses.
```

---

## Prompt 8: Integration & Final Assembly

```
Finalize Gorgon. Wire everything together and ensure it runs end-to-end.

Tasks:

1. Update gorgon/__init__.py with clean public API:
   from gorgon import Gorgon, WorkflowConfig, run_workflow

2. Create gorgon/core.py:
   - Gorgon class as main entry point
   - __init__(workflows_dir="workflows", db_path="gorgon-state.db")
   - run(workflow_name, request, **options)
   - resume(workflow_id)
   - status(workflow_id)

3. Verify all integrations:
   - Contracts validate between agent handoffs
   - State persists checkpoints at each stage
   - Budget tracks and enforces limits
   - Logging captures all events with trace IDs
   - CLI commands work end-to-end

4. Create example usage in examples/:
   - examples/simple_feature.py - programmatic usage
   - examples/README.md - quick start guide

5. Update main README.md:
   - Installation instructions
   - Quick start (CLI and Python)
   - Architecture overview
   - Link to docs

6. Create pyproject.toml:
   - Project metadata
   - Dependencies: jsonschema, pyyaml
   - Dev dependencies: pytest, pytest-cov
   - Entry points for CLI

7. Add GitHub Actions workflow .github/workflows/test.yml:
   - Run tests on push
   - Python 3.9, 3.10, 3.11

8. Run full test suite, fix any failures:
   pytest tests/ -v --cov=gorgon

Verify this works:
   gorgon run feature-build "Add user authentication with JWT tokens"
```

---

## Bonus: Self-Hosted LLM Backend (Post-Core)

> Run these AFTER prompts 1-8 are complete. These add the pluggable LLM layer
> that enables local inference via Ollama and air-gapped deployment.
> See GORGON_SELF_HOSTED_BACKEND.md for full architecture details.

### Prompt 9: LLM Base Interface + Mock Provider

```
Read GORGON_SELF_HOSTED_BACKEND.md if present in the project root.

Add LLM backend abstraction to Gorgon:

gorgon/
├── llm/
│   ├── __init__.py
│   ├── base.py
│   └── providers/
│       ├── __init__.py
│       └── mock.py

Requirements:

1. llm/base.py:
   - ModelTier enum (REASONING, STANDARD, FAST)
   - LLMRequest dataclass: messages, system_prompt, model_tier, agent_id, max_tokens, temperature
   - LLMResponse dataclass: content, model, provider, input_tokens, output_tokens, total_tokens, latency_ms
   - LLMProvider abstract base class:
     - abstract generate(request: LLMRequest) -> LLMResponse
     - abstract stream(request: LLMRequest) -> AsyncIterator[str]
     - abstract health_check() -> bool
     - name property

2. llm/providers/mock.py:
   - MockProvider that returns configurable deterministic responses
   - Useful for testing workflows without burning tokens
   - Configurable latency simulation

Create tests/llm/test_base.py covering all dataclass creation and mock provider.
```

### Prompt 10: Ollama Provider

```
Continue the LLM backend. Implement the Ollama provider for local inference.

Add: gorgon/llm/providers/ollama.py

Requirements:

1. OllamaProvider class implementing LLMProvider:
   - __init__(base_url="http://localhost:11434")
   - Uses httpx async client for API calls
   - generate() calls /api/generate
   - stream() calls /api/generate with stream=True
   - health_check() calls /api/tags
   - refresh_models() fetches available models
   - pull_model(name) pulls from Ollama registry

2. Tier-based model selection with _select_model():
   - REASONING -> largest available (e.g. qwen2.5:72b, llama3.1:70b)
   - STANDARD -> mid-range (e.g. qwen2.5:32b, llama3.1:8b)
   - FAST -> smallest (e.g. qwen2.5:3b, phi3:mini)
   - Falls back to whatever is available if preferred not found

3. Add httpx to requirements.txt

Create tests/llm/test_ollama.py with mocked HTTP responses.
```

### Prompt 11: LLM Router

```
Continue the LLM backend. Implement the intelligent model router.

Add: gorgon/llm/router.py

Requirements:

1. LLMRouter class:
   - register_provider(provider, tiers) - register provider for specific tiers
   - generate(request) - routes to appropriate provider based on tier
   - force_local_only(enabled) - switch for budget governor to force local inference
   - Failover: if primary provider fails, try next registered provider for that tier

2. Integration with existing BudgetManager:
   - When budget hits CRITICAL, auto-switch to force_local_only
   - Local inference = zero token cost

3. Configuration via YAML:
   ```yaml
   llm:
     default_provider: ollama
     providers:
       ollama:
         base_url: http://localhost:11434
         tiers: [reasoning, standard, fast]
       anthropic:
         tiers: [reasoning, standard]
     routing:
       reasoning: [anthropic, ollama]  # prefer API, fallback local
       standard: [ollama, anthropic]   # prefer local
       fast: [ollama]                  # always local
   ```

Create tests/llm/test_router.py covering routing, failover, and force_local scenarios.
```

### Prompt 12: Hardware Detection

```
Continue the LLM backend. Implement hardware detection for model recommendations.

Add: gorgon/llm/hardware.py

Requirements:

1. HardwareProfile dataclass:
   - platform (macos_arm, macos_intel, linux_nvidia, linux_cpu)
   - total_memory_gb, available_memory_gb
   - gpu_info (if applicable)
   - max_model_params_b (calculated)
   - recommended_models list
   - max_concurrent_models int

2. detect_hardware() function:
   - Detect Apple Silicon unified memory
   - Detect NVIDIA GPU VRAM
   - Calculate max model size based on available memory
   - Suggest models by tier for the detected hardware

3. Add psutil to requirements.txt

Create tests/llm/test_hardware.py with mocked system info.
```

---

## Post-Build Verification

After all prompts are complete, run the full verification:

```bash
cd ~/projects/Gorgon

# Full test suite
pytest tests/ -v --cov=gorgon

# Verify CLI
gorgon list
gorgon validate feature-build
gorgon run feature-build "Add user authentication with JWT tokens" --dry-run

# Check budget report
gorgon budget-report <workflow-id>

# Verify resume capability
gorgon history
gorgon resume <workflow-id>

# If self-hosted backend is implemented:
python -c "from gorgon.llm.hardware import detect_hardware; print(detect_hardware())"
```

---

## Target Directory Structure (Complete)

```
Gorgon/
├── gorgon/
│   ├── __init__.py
│   ├── core.py
│   ├── cli.py
│   ├── errors.py
│   ├── logging.py
│   ├── contracts/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── definitions.py
│   │   └── validator.py
│   ├── state/
│   │   ├── __init__.py
│   │   ├── persistence.py
│   │   └── checkpoint.py
│   ├── workflow/
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   └── executor.py
│   ├── budget/
│   │   ├── __init__.py
│   │   ├── manager.py
│   │   └── strategies.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── planner.py
│   │   ├── builder.py
│   │   ├── tester.py
│   │   └── reviewer.py
│   └── llm/                    # Bonus: Self-hosted backend
│       ├── __init__.py
│       ├── base.py
│       ├── router.py
│       ├── hardware.py
│       └── providers/
│           ├── __init__.py
│           ├── mock.py
│           ├── ollama.py
│           └── anthropic.py
├── workflows/
│   ├── feature-build.yaml
│   ├── bug-fix.yaml
│   └── refactor.yaml
├── examples/
│   ├── simple_feature.py
│   └── README.md
├── tests/
│   ├── test_contracts.py
│   ├── test_state.py
│   ├── test_workflow.py
│   ├── test_budget.py
│   ├── test_logging.py
│   ├── test_cli.py
│   ├── test_agents.py
│   └── llm/
│       ├── test_base.py
│       ├── test_ollama.py
│       ├── test_router.py
│       └── test_hardware.py
├── .github/
│   └── workflows/
│       └── test.yml
├── pyproject.toml
├── requirements.txt
├── README.md
└── GORGON_SELF_HOSTED_BACKEND.md
```
