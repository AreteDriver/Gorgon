# Creating Workflows in Gorgon

A comprehensive guide to building multi-agent workflows in Gorgon. This tutorial covers everything from basic concepts to advanced patterns like parallel execution, conditional branching, and workflow composition.

## Table of Contents

1. [Workflow Concepts](#workflow-concepts)
2. [YAML Workflow Structure](#yaml-workflow-structure)
3. [Step Types](#step-types)
4. [Variables and Inputs/Outputs](#variables-and-inputsoutputs)
5. [Conditions and Branching](#conditions-and-branching)
6. [Agent Roles](#agent-roles)
7. [Parallel Execution Patterns](#parallel-execution-patterns)
8. [Complete Example Workflows](#complete-example-workflows)
9. [Best Practices](#best-practices)
10. [Debugging Workflows](#debugging-workflows)

---

## Workflow Concepts

### What is a Workflow?

A **workflow** is a sequence of coordinated steps that accomplish a complex task by orchestrating multiple AI agents and tools. Each workflow defines:

- **Inputs**: Data the workflow needs to start
- **Steps**: Individual tasks executed in sequence or parallel
- **Outputs**: Results produced by the workflow

### The Multi-Agent Model

Gorgon uses a multi-agent architecture where specialized AI "agents" handle different aspects of a task:

```
    +-----------+     +-----------+     +-----------+
    |  Planner  | --> |  Builder  | --> |  Tester   |
    +-----------+     +-----------+     +-----------+
                                              |
                                              v
                                        +-----------+
                                        | Reviewer  |
                                        +-----------+
```

Each agent has a specific role (e.g., planning, coding, testing) and the workflow orchestrates their collaboration.

### Core Components

| Component | Description |
|-----------|-------------|
| **WorkflowConfig** | The complete workflow definition |
| **StepConfig** | Configuration for a single step |
| **WorkflowExecutor** | Engine that runs workflows |
| **Context** | Shared state passed between steps |

---

## YAML Workflow Structure

### Basic Template

Every workflow YAML file follows this structure:

```yaml
name: Workflow Name
version: "1.0"
description: What this workflow does

# Resource limits
token_budget: 100000      # Max tokens across all steps
timeout_seconds: 3600     # Max execution time

# Define required inputs
inputs:
  input_name:
    type: string
    required: true
    description: What this input is for
  optional_input:
    type: string
    required: false
    default: "fallback value"

# Define what the workflow produces
outputs:
  - output_name_1
  - output_name_2

# Workflow settings (optional)
settings:
  auto_parallel: false
  auto_parallel_max_workers: 4

# The actual steps
steps:
  - id: step_1
    type: claude_code
    params:
      role: planner
      prompt: |
        Your prompt here with ${input_name}
    outputs:
      - result_1

  - id: step_2
    type: claude_code
    params:
      role: builder
      prompt: |
        Build based on: ${result_1}
    outputs:
      - result_2

# Optional metadata
metadata:
  author: your-name
  category: development
  tags:
    - feature
    - automation
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Human-readable workflow name |
| `version` | No | Semantic version (default: "1.0") |
| `description` | No | What the workflow does |
| `token_budget` | No | Maximum tokens (default: 100000) |
| `timeout_seconds` | No | Max runtime (default: 3600) |
| `inputs` | No | Input variable definitions |
| `outputs` | No | List of output variable names |
| `settings` | No | Workflow-level settings |
| `steps` | Yes | List of step configurations |
| `metadata` | No | Tags, author, category |

---

## Step Types

Gorgon supports several step types for different tasks:

### 1. claude_code - Claude/Anthropic AI

Execute prompts using Claude Code (Anthropic API).

```yaml
- id: analyze_code
  type: claude_code
  params:
    role: reviewer          # Agent role (see Agent Roles section)
    prompt: |
      Analyze this code for security issues:
      ${code_content}
    estimated_tokens: 5000  # Token estimate for budgeting
  outputs:
    - security_report
  on_failure: retry
  max_retries: 2
  timeout_seconds: 300
```

### 2. openai - OpenAI API

Execute prompts using OpenAI models.

```yaml
- id: generate_summary
  type: openai
  params:
    model: gpt-4              # Model to use
    prompt: |
      Summarize the following:
      ${document}
    max_tokens: 1000
  outputs:
    - summary
```

### 3. shell - Shell Commands

Execute shell commands for file operations, builds, tests, etc.

```yaml
- id: run_tests
  type: shell
  params:
    command: "cd ${codebase_path} && pytest --verbose"
    allow_failure: false    # If true, step succeeds even if command fails
  outputs:
    - test_results
  timeout_seconds: 300
```

**Security**: Shell commands undergo validation to prevent injection attacks. Variables are safely substituted.

### 4. parallel - Concurrent Execution

Execute multiple sub-steps concurrently.

```yaml
- id: parallel_analysis
  type: parallel
  params:
    strategy: threading     # threading, asyncio, or process
    max_workers: 4          # Maximum concurrent tasks
    fail_fast: false        # Stop all if one fails
    steps:
      - id: security
        type: claude_code
        params:
          role: reviewer
          prompt: "Security analysis..."
        outputs:
          - security_report

      - id: performance
        type: claude_code
        params:
          role: analyst
          prompt: "Performance analysis..."
        outputs:
          - performance_report
```

### 5. checkpoint - Execution Checkpoint

Create a checkpoint for state persistence and resumability.

```yaml
- id: checkpoint_after_build
  type: checkpoint
  params:
    message: "Build phase complete, ready for testing"
```

Checkpoints enable:
- Workflow resumption after failures
- Human approval gates
- Progress tracking

### 6. fan_out - Scatter Pattern

Process a list of items concurrently.

```yaml
- id: review_files
  type: fan_out
  params:
    items: "${file_list}"           # List to iterate over
    max_concurrent: 5               # Parallelism limit
    fail_fast: false
    step_template:
      type: claude_code
      params:
        role: reviewer
        prompt: |
          Review file: ${item}      # ${item} = current list item
          Index: ${index}           # ${index} = 0-based index
  outputs:
    - file_reviews
```

### 7. fan_in - Gather Pattern

Aggregate results from a previous fan-out or parallel step.

```yaml
- id: summarize_reviews
  type: fan_in
  depends_on: [review_files]
  params:
    input: "${file_reviews}"
    aggregation: claude_code        # concat, claude_code, or openai
    aggregate_prompt: |
      Summarize these code reviews:
      ${items}
  outputs:
    - review_summary
```

### 8. map_reduce - Combined Scatter-Gather

Combines fan-out and fan-in in a single step.

```yaml
- id: analyze_logs
  type: map_reduce
  params:
    items: "${log_files}"
    max_concurrent: 3

    # Map step runs on each item
    map_step:
      type: claude_code
      params:
        role: analyst
        prompt: "Analyze log file: ${item}"

    # Reduce step aggregates all map results
    reduce_step:
      type: claude_code
      params:
        role: reporter
        prompt: |
          Combine log analyses:
          ${map_results}
  outputs:
    - analysis_report
```

---

## Variables and Inputs/Outputs

### Defining Inputs

Inputs are defined at the workflow level with type, required, default, and description:

```yaml
inputs:
  feature_request:
    type: string
    required: true
    description: Description of the feature to build

  codebase_path:
    type: string
    required: true
    description: Path to the codebase

  test_command:
    type: string
    required: false
    default: "pytest"
    description: Command to run tests

  options:
    type: object
    required: false
    description: Additional configuration options
```

**Input Types**:
- `string` - Text values
- `object` - JSON/dict structures
- `list` - Arrays of items
- `boolean` - True/false values

### Using Variables

Reference variables in prompts and commands using `${variable_name}`:

```yaml
steps:
  - id: plan
    type: claude_code
    params:
      prompt: |
        Feature: ${feature_request}
        Codebase: ${codebase_path}
    outputs:
      - plan

  - id: build
    type: claude_code
    params:
      prompt: |
        Implement based on plan:
        ${plan}                    # Uses output from previous step
```

### Capturing Outputs

Each step can declare outputs that become available to subsequent steps:

```yaml
- id: diagnose
  type: claude_code
  params:
    prompt: "Diagnose the bug..."
  outputs:
    - diagnosis          # Captured from response
    - root_cause         # Multiple outputs possible
    - affected_files

- id: fix
  type: claude_code
  params:
    prompt: |
      Root cause: ${root_cause}
      Files: ${affected_files}
```

### Workflow Outputs

Define which variables are returned as workflow results:

```yaml
outputs:
  - plan
  - code
  - test_results
  - review
```

These are collected from the execution context when the workflow completes.

---

## Conditions and Branching

### Conditional Step Execution

Steps can have conditions that determine whether they run:

```yaml
- id: review
  type: claude_code
  condition:
    field: test_results       # Variable to check
    operator: contains        # Comparison operator
    value: "passed"           # Expected value
  params:
    prompt: "Review the implementation..."
```

If the condition evaluates to `false`, the step is skipped.

### Condition Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `equals` | Exact match | `value: "success"` |
| `not_equals` | Not equal | `value: "failed"` |
| `contains` | Substring/element check | `value: "error"` |
| `greater_than` | Numeric comparison | `value: 80` |
| `less_than` | Numeric comparison | `value: 50` |
| `in` | Value in list | `value: ["all", "security"]` |
| `not_empty` | Value exists and not empty | (no value needed) |

### Examples

```yaml
# Run only if score is high enough
- id: generate_tickets
  type: claude_code
  condition:
    field: health_score
    operator: less_than
    value: 80
  params:
    prompt: "Generate improvement tickets..."

# Run only for certain review types
- id: security_review
  type: claude_code
  condition:
    field: review_focus
    operator: in
    value: ["all", "security"]
  params:
    prompt: "Perform security review..."

# Run only if previous step produced output
- id: compare_tests
  type: claude_code
  condition:
    field: test_results
    operator: not_empty
  params:
    prompt: "Compare test results..."
```

### Failure Handling

Control what happens when a step fails:

```yaml
- id: risky_operation
  type: claude_code
  on_failure: retry          # abort, skip, retry, fallback, continue_with_default
  max_retries: 3             # For retry mode
  timeout_seconds: 300
  params:
    prompt: "..."

# With fallback
- id: api_call
  type: openai
  on_failure: fallback
  fallback:
    type: default_value
    value: { "status": "unavailable" }
  params:
    prompt: "..."

# With default output
- id: optional_step
  type: claude_code
  on_failure: continue_with_default
  default_output:
    summary: "Analysis not available"
  params:
    prompt: "..."
```

**Failure Modes**:

| Mode | Behavior |
|------|----------|
| `abort` | Stop workflow, mark as failed (default) |
| `skip` | Mark step as skipped, continue workflow |
| `retry` | Retry up to `max_retries` times |
| `fallback` | Execute fallback configuration |
| `continue_with_default` | Use `default_output` values |

---

## Agent Roles

Agent roles define the persona and expertise of the AI for each step. The role is passed as context to shape the AI's response.

### Available Roles

| Role | Purpose | Use Case |
|------|---------|----------|
| `planner` | Breaks down tasks into actionable steps | Feature planning, bug diagnosis, analysis planning |
| `builder` | Writes production-ready code | Implementation, code generation |
| `tester` | Creates comprehensive test suites | Test generation, test coverage |
| `reviewer` | Identifies issues and improvements | Code review, security audit, quality analysis |
| `architect` | Makes architectural decisions | Design decisions, system architecture |
| `documenter` | Creates documentation | API docs, guides, READMEs |
| `analyst` | Statistical analysis, pattern finding | Data analysis, log analysis |
| `visualizer` | Creates charts and dashboards | Data visualization |
| `reporter` | Executive summaries | Status reports, summaries |
| `security_analyst` | Security-focused analysis | Vulnerability assessment |
| `data_analyst` | Data processing and analysis | SQL, pandas, data insights |

### When to Use Each Role

**Planner** - Start workflows with planning to break complex tasks into steps:
```yaml
- id: plan
  type: claude_code
  params:
    role: planner
    prompt: |
      Analyze the feature request and create a plan:
      ${feature_request}
```

**Builder** - Code implementation tasks:
```yaml
- id: implement
  type: claude_code
  params:
    role: builder
    prompt: |
      Implement the feature according to this plan:
      ${plan}
```

**Reviewer** - Quality and security checks:
```yaml
- id: review
  type: claude_code
  params:
    role: reviewer
    prompt: |
      Review this code for security and quality:
      ${code}
```

**Reporter** - Synthesize results into summaries:
```yaml
- id: summary
  type: claude_code
  params:
    role: reporter
    prompt: |
      Create an executive summary combining:
      - Security: ${security_report}
      - Performance: ${performance_report}
```

---

## Parallel Execution Patterns

### Pattern 1: Auto-Parallel

Enable automatic parallelization based on step dependencies:

```yaml
name: Auto-Parallel Analysis
settings:
  auto_parallel: true
  auto_parallel_max_workers: 4

steps:
  # These run in parallel (no depends_on)
  - id: security_scan
    type: claude_code
    params:
      prompt: "Security analysis..."
    outputs: [security_report]

  - id: code_quality
    type: claude_code
    params:
      prompt: "Quality analysis..."
    outputs: [quality_report]

  - id: architecture_review
    type: openai
    params:
      prompt: "Architecture analysis..."
    outputs: [architecture_report]

  # This waits for all above to complete
  - id: executive_summary
    type: claude_code
    depends_on: [security_scan, code_quality, architecture_review]
    params:
      prompt: |
        Combine all analyses:
        ${security_report}
        ${quality_report}
        ${architecture_report}
```

**How it works**:
1. Builds dependency graph from `depends_on`
2. Groups independent steps together
3. Executes groups in parallel, respecting dependencies

### Pattern 2: Explicit Parallel Block

Define a parallel section with sub-steps:

```yaml
- id: parallel_analysis
  type: parallel
  params:
    strategy: threading
    max_workers: 4
    fail_fast: false
    steps:
      - id: security
        type: claude_code
        params:
          role: reviewer
          prompt: "Security check..."
        outputs: [security_report]

      - id: performance
        type: claude_code
        params:
          role: analyst
          prompt: "Performance check..."
        outputs: [performance_report]

      # Depends on both above within the parallel block
      - id: summary
        type: claude_code
        depends_on: [security, performance]
        params:
          role: reporter
          prompt: |
            Summarize:
            ${security_report}
            ${performance_report}
```

### Pattern 3: Fan-Out / Fan-In

Process a list of items in parallel, then aggregate:

```yaml
# Fan out: review each file
- id: review_files
  type: fan_out
  params:
    items: "${files}"
    max_concurrent: 5
    step_template:
      type: claude_code
      params:
        role: reviewer
        prompt: "Review: ${item}"
  outputs: [file_reviews]

# Fan in: aggregate reviews
- id: summarize
  type: fan_in
  depends_on: [review_files]
  params:
    input: "${file_reviews}"
    aggregation: claude_code
    aggregate_prompt: |
      Summarize all file reviews:
      ${items}
  outputs: [review_summary]
```

### Pattern 4: Map-Reduce

Combined scatter-gather in one step:

```yaml
- id: analyze_logs
  type: map_reduce
  params:
    items: "${log_files}"
    max_concurrent: 3
    map_step:
      type: claude_code
      params:
        role: analyst
        prompt: "Analyze: ${item}"
    reduce_step:
      type: claude_code
      params:
        role: reporter
        prompt: "Combine: ${map_results}"
  outputs: [analysis_report]
```

### Dependency Syntax

```yaml
# Single dependency
depends_on: security_scan

# Multiple dependencies (list)
depends_on:
  - security_scan
  - performance_scan

# Inline list
depends_on: [security_scan, performance_scan]
```

---

## Complete Example Workflows

### Example 1: Feature Build Workflow

End-to-end feature development with planning, implementation, testing, and review.

```yaml
name: Feature Build
version: "1.0"
description: Multi-agent workflow for building new features from requirements

token_budget: 150000
timeout_seconds: 3600

inputs:
  feature_request:
    type: string
    required: true
    description: Description of the feature to build
  codebase_path:
    type: string
    required: true
    description: Path to the codebase
  test_command:
    type: string
    required: false
    default: "pytest"
    description: Command to run tests

outputs:
  - plan
  - code
  - test_results
  - review

steps:
  # Step 1: Planning
  - id: plan
    type: claude_code
    params:
      role: planner
      prompt: |
        Analyze the following feature request and create a detailed implementation plan:

        Feature: ${feature_request}
        Codebase: ${codebase_path}

        Provide:
        1. Tasks breakdown
        2. Affected files
        3. Dependencies
        4. Risks and mitigations
      estimated_tokens: 5000
    outputs:
      - plan
      - tasks
    on_failure: abort

  # Step 2: Implementation
  - id: build
    type: claude_code
    params:
      role: builder
      prompt: |
        Implement the feature according to this plan:

        ${plan}

        Write production-quality code with:
        - Type hints
        - Error handling
        - Documentation
      estimated_tokens: 20000
    outputs:
      - code
      - files_modified
    on_failure: retry
    max_retries: 2

  # Checkpoint after build
  - id: checkpoint_after_build
    type: checkpoint
    params:
      message: "Build phase complete"

  # Step 3: Test Generation
  - id: test
    type: claude_code
    params:
      role: tester
      prompt: |
        Write comprehensive tests for the new feature:

        Code: ${code}
        Files: ${files_modified}

        Include:
        - Unit tests
        - Edge cases
        - Integration tests where appropriate
      estimated_tokens: 10000
    outputs:
      - tests
    on_failure: retry
    max_retries: 2

  # Step 4: Run Tests
  - id: run_tests
    type: shell
    params:
      command: "cd ${codebase_path} && ${test_command}"
      allow_failure: false
    outputs:
      - test_results
    on_failure: abort
    timeout_seconds: 300

  # Step 5: Review (only if tests pass)
  - id: review
    type: claude_code
    params:
      role: reviewer
      prompt: |
        Review the implementation:

        Code: ${code}
        Tests: ${tests}
        Test Results: ${test_results}

        Evaluate:
        - Code quality
        - Security concerns
        - Performance implications
        - Test coverage
      estimated_tokens: 5000
    condition:
      field: test_results
      operator: contains
      value: "passed"
    outputs:
      - review
      - approved
    on_failure: skip

metadata:
  author: gorgon
  category: development
  tags:
    - feature
    - build
    - ci
```

### Example 2: Parallel Code Analysis

Multi-perspective analysis with automatic parallelization.

```yaml
name: Parallel Code Analysis
version: "1.0"
description: Multi-agent parallel analysis workflow

settings:
  auto_parallel: true
  auto_parallel_max_workers: 4

inputs:
  codebase_path:
    type: string
    required: true

outputs:
  - security_report
  - performance_report
  - maintainability_report
  - final_summary

steps:
  # Gather context first
  - id: gather_context
    type: claude_code
    params:
      role: analyst
      prompt: |
        Analyze the structure of: ${codebase_path}
        Provide key directories, entry points, and dependencies.
    outputs:
      - codebase_context
      - file_list

  # Parallel analysis phase - these run concurrently
  - id: security
    type: claude_code
    depends_on: [gather_context]
    params:
      role: security_analyst
      prompt: |
        Security analysis of:
        ${codebase_context}
        Check for vulnerabilities, secrets, injection issues.
    outputs:
      - security_report
      - security_score

  - id: performance
    type: claude_code
    depends_on: [gather_context]
    params:
      role: analyst
      prompt: |
        Performance analysis of:
        ${codebase_context}
        Check complexity, memory, caching opportunities.
    outputs:
      - performance_report
      - performance_score

  - id: maintainability
    type: claude_code
    depends_on: [gather_context]
    params:
      role: reviewer
      prompt: |
        Maintainability analysis of:
        ${codebase_context}
        Check organization, naming, documentation, tests.
    outputs:
      - maintainability_report
      - maintainability_grade

  # Summary waits for all analyses
  - id: summary
    type: claude_code
    depends_on: [security, performance, maintainability]
    params:
      role: reporter
      prompt: |
        Create an executive summary:

        Security: ${security_report}
        Performance: ${performance_report}
        Maintainability: ${maintainability_report}

        Provide overall health score and top priorities.
    outputs:
      - final_summary
      - health_score
```

### Example 3: Decision Support Pipeline

Enterprise decision analysis with audit trail.

```yaml
name: Decision Support Pipeline
version: "1.0"
description: Analyze options and produce structured recommendations

inputs:
  decision_question:
    type: string
    required: true
  context:
    type: string
    required: false
    default: ""
  stakeholders:
    type: string
    required: false
    default: "general"

outputs:
  - situation_analysis
  - options_matrix
  - recommendation
  - audit_trail

steps:
  # Phase 1: Situation Analysis
  - id: analyze_situation
    type: claude_code
    params:
      role: analyst
      prompt: |
        # Decision Analysis

        Question: ${decision_question}
        Context: ${context}
        Stakeholders: ${stakeholders}

        Perform structured analysis:
        1. Problem Statement
        2. Key Factors
        3. Constraints
        4. Assumptions
        5. Information Gaps
        6. Success Criteria
    outputs:
      - situation_analysis

  # Phase 2: Options Analysis
  - id: generate_options
    type: claude_code
    params:
      role: architect
      prompt: |
        Based on this situation:
        ${situation_analysis}

        Generate 3-5 distinct options with:
        - Pros and cons
        - Effort and risk level
        - Reversibility
        - Dependencies
    outputs:
      - options_matrix
      - option_count

  # Checkpoint for human review
  - id: checkpoint_options
    type: checkpoint
    params:
      message: "Options generated. Review before proceeding."

  # Phase 3: Recommendation
  - id: generate_recommendation
    type: claude_code
    params:
      role: reporter
      prompt: |
        Generate recommendation:

        Question: ${decision_question}
        Analysis: ${situation_analysis}
        Options: ${options_matrix}

        Provide:
        - Executive summary
        - Recommended option with rationale
        - Implementation considerations
        - Alternative recommendation (Plan B)
        - Dissenting view (steel-man the counterargument)
    outputs:
      - recommendation
      - confidence_level

  # Phase 4: Audit Trail
  - id: create_audit_trail
    type: claude_code
    params:
      role: documenter
      prompt: |
        Create compliance-ready audit trail:

        Question: ${decision_question}
        Analysis: ${situation_analysis}
        Options: ${options_matrix}
        Recommendation: ${recommendation}

        Include:
        - Process metadata
        - Decision trail
        - Reasoning chain
        - Limitations and caveats
    outputs:
      - audit_trail
    on_failure: skip
```

---

## Best Practices

### 1. Workflow Design

**Keep workflows focused**
- One workflow = one purpose
- Split complex workflows into composable sub-workflows
- Use clear, descriptive names

**Plan step order carefully**
```yaml
# Good: Plan -> Build -> Test -> Review
steps:
  - id: plan
  - id: build
  - id: test
  - id: review

# Bad: Jumping around without clear flow
```

### 2. Input/Output Management

**Define all inputs explicitly**
```yaml
inputs:
  required_input:
    type: string
    required: true
    description: Clear description of what's needed

  optional_input:
    type: string
    required: false
    default: "sensible default"
```

**Use meaningful output names**
```yaml
outputs:
  - implementation_plan      # Good: descriptive
  - security_findings
  - p                        # Bad: cryptic
```

### 3. Error Handling

**Configure failure modes appropriately**
```yaml
# Critical steps: abort on failure
- id: database_migration
  on_failure: abort

# Optional steps: skip on failure
- id: generate_stats
  on_failure: skip

# Flaky steps: retry
- id: external_api_call
  on_failure: retry
  max_retries: 3

# Steps with fallbacks
- id: ai_analysis
  on_failure: continue_with_default
  default_output:
    analysis: "Analysis unavailable"
```

### 4. Token Budget Management

**Estimate tokens per step**
```yaml
- id: large_analysis
  type: claude_code
  params:
    estimated_tokens: 15000  # Help budget tracking
```

**Set reasonable workflow budgets**
```yaml
token_budget: 100000  # Total workflow limit
```

### 5. Parallelization

**Use auto-parallel for independent steps**
```yaml
settings:
  auto_parallel: true
```

**Control parallelism for rate-limited APIs**
```yaml
- id: parallel_calls
  type: parallel
  params:
    max_workers: 3  # Don't overwhelm API
```

### 6. Security

**Never hardcode secrets**
```yaml
# Bad: hardcoded
params:
  api_key: "sk-abc123"

# Good: use environment variables
params:
  api_key: "${OPENAI_API_KEY}"
```

**Validate shell commands**
```yaml
# Commands are validated for safety
- id: safe_command
  type: shell
  params:
    command: "cd ${path} && pytest"  # Variables safely substituted
```

### 7. Documentation

**Add metadata for discoverability**
```yaml
metadata:
  author: your-team
  category: development
  tags:
    - security
    - review
```

**Include examples**
```yaml
metadata:
  examples:
    - description: Security audit
      inputs:
        codebase_path: /path/to/project
        focus: security
```

---

## Debugging Workflows

### Common Issues

#### 1. Step Not Executing

**Symptom**: Step is skipped unexpectedly

**Check**:
- Is there a condition that's evaluating to false?
- Is `depends_on` referencing a step that failed?
- Is `on_failure: skip` set on a failing step?

```yaml
# Debug: Check condition
- id: conditional_step
  condition:
    field: previous_result
    operator: contains
    value: "success"
  # Add logging or checkpoint before to verify previous_result
```

#### 2. Variable Not Found

**Symptom**: `${variable}` appears literally in output

**Check**:
- Is the variable spelled correctly?
- Is it defined in a previous step's `outputs`?
- Did the producing step complete successfully?

```yaml
# Debug: Add checkpoint to inspect context
- id: debug_checkpoint
  type: checkpoint
  params:
    message: "Current context state"
```

#### 3. Step Timeout

**Symptom**: Step fails with timeout error

**Solutions**:
```yaml
# Increase step timeout
- id: long_running_step
  timeout_seconds: 600  # 10 minutes instead of default 300

# Or increase workflow timeout
timeout_seconds: 7200  # 2 hours
```

#### 4. Token Budget Exceeded

**Symptom**: Workflow stops with "Token budget exceeded"

**Solutions**:
```yaml
# Increase budget
token_budget: 200000

# Or reduce estimated tokens per step
- id: efficient_step
  params:
    estimated_tokens: 3000  # Lower estimate
    prompt: "Concise prompt..."  # Shorter prompts
```

#### 5. Parallel Step Failures

**Symptom**: Some parallel branches fail, others succeed

**Debugging**:
```yaml
- id: parallel_section
  type: parallel
  params:
    fail_fast: false  # Let all branches complete for debugging
    steps:
      - id: branch_1
        on_failure: skip  # Continue even if this fails
```

### Debugging Tools

#### 1. Checkpoints

Insert checkpoints to pause and inspect state:

```yaml
- id: debug_checkpoint_1
  type: checkpoint
  params:
    message: |
      Debug Info:
      - plan: ${plan}
      - code available: ${code}
```

#### 2. Dry Run Mode

Execute without making real API calls:

```python
executor = WorkflowExecutor(dry_run=True)
result = executor.execute(workflow, inputs)
```

#### 3. Verbose Logging

Enable debug logging:

```python
import logging
logging.getLogger("test_ai.workflow").setLevel(logging.DEBUG)
```

#### 4. Step-by-Step Execution

Use the CLI for interactive execution:

```bash
./gorgon workflow run my-workflow.yaml --step-by-step
```

### Error Messages Guide

| Error | Cause | Solution |
|-------|-------|----------|
| "Missing required input: X" | Required input not provided | Add input when running workflow |
| "Token budget exceeded" | Workflow used too many tokens | Increase `token_budget` |
| "Circular dependency detected" | Steps depend on each other in a loop | Fix `depends_on` relationships |
| "Invalid step type: X" | Unknown step type | Use valid type: `claude_code`, `openai`, `shell`, etc. |
| "Workflow validation failed" | YAML structure issues | Check required fields, step IDs |

---

## Further Reading

- [PARALLEL_EXECUTION.md](./PARALLEL_EXECUTION.md) - Detailed parallel execution guide
- [EXAMPLES.md](./EXAMPLES.md) - More workflow examples
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture
- [workflows/](../workflows/) - Example workflow files
