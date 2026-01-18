# Claude Code Integration Guide for Gorgon

## Overview

Claude Code is Anthropic's command-line tool for agentic coding. Gorgon integrates with Claude through two modes:
- **API Mode**: Direct calls to Anthropic's API (recommended for production)
- **CLI Mode**: Subprocess execution of the `claude` CLI (useful for local development)

## Installation

### Claude CLI Installation

```bash
# Method 1: Install script (recommended)
curl -fsSL https://claude.ai/install.sh | sh

# Method 2: npm
npm install -g @anthropic-ai/claude-code

# Verify installation
claude --version
```

### Gorgon Setup

```bash
cd ~/projects/Gorgon
pip install -r requirements.txt  # Includes anthropic SDK
cp .env.example .env
```

## Configuration

### API Key Setup

```bash
# Add to .env file
echo 'ANTHROPIC_API_KEY=your-api-key-here' >> .env

# Or export directly
export ANTHROPIC_API_KEY='your-api-key-here'
```

### Gorgon Settings

In `.env`:
```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional (defaults shown)
CLAUDE_CLI_PATH=claude          # Path to CLI executable
CLAUDE_MODE=api                 # 'api' or 'cli'
```

### Get Your API Key

1. Visit [Anthropic Console](https://console.anthropic.com/settings/keys)
2. Create new API key
3. Copy and save securely

## Gorgon Integration

### How It Works

Gorgon's `ClaudeCodeClient` wraps Claude with specialized agent prompts:

```python
from test_ai.api_clients import ClaudeCodeClient

client = ClaudeCodeClient()

# Execute a specialized agent
result = client.execute_agent(
    role="planner",
    task="Build user authentication system",
    context="Using FastAPI and JWT tokens"
)

# Direct completion
result = client.generate_completion(
    prompt="Explain dependency injection",
    system_prompt="You are a senior software engineer"
)
```

### Dual-Mode Operation

**API Mode** (default):
```python
# Uses Anthropic SDK directly
self.client = anthropic.Anthropic(api_key=self.api_key)
response = self.client.messages.create(
    model="claude-sonnet-4-20250514",
    system=system_prompt,
    messages=[{"role": "user", "content": user_prompt}]
)
```

**CLI Mode**:
```python
# Uses subprocess
cmd = [self.cli_path, "-p", prompt, "--no-input"]
result = subprocess.run(cmd, capture_output=True, text=True)
```

### Built-in Agent Roles

| Role | Purpose |
|------|---------|
| `planner` | Breaks features into actionable implementation steps |
| `builder` | Writes production-ready code based on plans |
| `tester` | Creates comprehensive test suites |
| `reviewer` | Analyzes code for quality, bugs, security |
| `architect` | Designs system architecture |
| `documenter` | Creates API docs and guides |

### Custom Agent Prompts

Edit `config/agent_prompts.json`:
```json
{
  "planner": {
    "name": "Strategic Planning Agent",
    "system_prompt": "You are a strategic planning agent..."
  },
  "custom_role": {
    "name": "My Custom Agent",
    "system_prompt": "You are a specialized agent for..."
  }
}
```

## Workflow Execution

### Via REST API

```bash
# Start the API server
./run_api.sh

# Execute development workflow
curl -X POST http://localhost:8000/workflows/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "dev_workflow_plan_build_test_review",
    "variables": {
      "feature_request": "Build a REST API for user management"
    }
  }'
```

### Via Python

```python
from test_ai.orchestrator import WorkflowEngine

engine = WorkflowEngine()
workflow = engine.load_workflow("dev_workflow_plan_build_test_review")
workflow.variables["feature_request"] = "Build user authentication"

result = engine.execute_workflow(workflow)

print(f"Status: {result.status}")
for step_id, output in result.outputs.items():
    print(f"{step_id}: {output}")
```

### Development Workflow Pipeline

The `dev_workflow_plan_build_test_review` workflow executes:

```
1. Planner Agent
   ↓ Creates implementation plan

2. Builder Agent
   ↓ Implements code based on plan

3. Tester Agent
   ↓ Writes comprehensive tests

4. Reviewer Agent
   ↓ Analyzes for quality/security

5. Return Results
```

## CLI Usage (Direct)

When using Claude CLI directly:

```bash
# Interactive mode
claude

# Single prompt
claude -p "create a REST API with FastAPI"

# Non-interactive (for scripts)
claude -p "refactor auth.py" --no-input

# With working directory context
cd ~/projects/my-app
claude -p "explain the codebase structure"
```

## Troubleshooting

### Claude CLI Not Found

```bash
# Check installation
which claude

# If using npm, ensure bin is in PATH
export PATH="$PATH:$(npm config get prefix)/bin"

# Add to shell profile
echo 'export PATH="$PATH:$(npm config get prefix)/bin"' >> ~/.bashrc
source ~/.bashrc
```

### API Key Issues

```bash
# Verify key is set
echo $ANTHROPIC_API_KEY

# Test with simple call
claude -p "say hello"

# Check .env file
grep ANTHROPIC_API_KEY .env
```

### Client Not Configured

```python
from test_ai.api_clients import ClaudeCodeClient

client = ClaudeCodeClient()
if not client.is_configured():
    print("Check ANTHROPIC_API_KEY in .env")
    print(f"Mode: {client.mode}")
```

## Best Practices

### 1. Clear, Specific Prompts
```python
# Good
client.execute_agent(
    role="builder",
    task="Create FastAPI endpoint that accepts POST /users with email validation"
)

# Bad
client.execute_agent(role="builder", task="make an API")
```

### 2. Provide Context
```python
# Include relevant context from previous steps
result = client.execute_agent(
    role="builder",
    task="Implement the authentication module",
    context=plan_output  # From planner step
)
```

### 3. Use Appropriate Roles
```python
# Planning phase
plan = client.execute_agent(role="planner", task=feature)

# Implementation phase
code = client.execute_agent(role="builder", task=feature, context=plan)

# Quality assurance
review = client.execute_agent(role="reviewer", task="Review", context=code)
```

## Security Considerations

### API Key Protection

```bash
# Never commit API keys
echo ".env" >> .gitignore

# Use environment variables in production
export ANTHROPIC_API_KEY='sk-ant-...'
```

### Code Review

Always review AI-generated code before deploying:
```python
result = client.execute_agent(role="builder", task="...")
print("Generated code:")
print(result["output"])
# Review before using
```

## Integration Patterns

### Pattern 1: Sequential Pipeline
```python
plan = client.execute_agent(role="planner", task=feature)
code = client.execute_agent(role="builder", task=feature, context=plan["output"])
tests = client.execute_agent(role="tester", task=feature, context=code["output"])
review = client.execute_agent(role="reviewer", task=feature, context=code["output"])
```

### Pattern 2: Iterative Refinement
```python
initial = client.execute_agent(role="builder", task=feature)
feedback = client.execute_agent(role="reviewer", task="Review", context=initial["output"])
refined = client.execute_agent(
    role="builder",
    task="Implement improvements",
    context=f"Code:\n{initial['output']}\n\nFeedback:\n{feedback['output']}"
)
```

## Metrics and Monitoring

Workflow execution returns metrics:
```python
result = engine.execute_workflow(workflow)

print(f"Duration: {result.completed_at - result.started_at}")
print(f"Steps executed: {result.steps_executed}")
print(f"Status: {result.status}")
print(f"Errors: {result.errors}")
```

## Additional Resources

- [Claude Code Documentation](https://docs.anthropic.com/en/docs/claude-code)
- [Anthropic API Reference](https://docs.anthropic.com/en/api)
- [Gorgon GitHub](https://github.com/AreteDriver/Gorgon)

---

**Last Updated**: January 2026
**Gorgon Version**: 0.1.0
