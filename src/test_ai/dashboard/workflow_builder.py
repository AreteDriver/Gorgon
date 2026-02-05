"""Visual Workflow Builder for Streamlit dashboard.

A drag-and-drop style workflow builder that renders workflows as visual graphs
and allows users to create, edit, and export YAML workflow definitions.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

import streamlit as st
import yaml

from test_ai.config import get_settings
from test_ai.workflow.loader import (
    validate_workflow,
    VALID_OPERATORS,
    VALID_ON_FAILURE,
)

logger = logging.getLogger(__name__)

# Lazy imports for executor and config to avoid circular imports
_executor_class = None
_workflow_config_class = None


def _get_executor_class():
    """Lazily import WorkflowExecutor."""
    global _executor_class
    if _executor_class is None:
        from test_ai.workflow.executor import WorkflowExecutor
        _executor_class = WorkflowExecutor
    return _executor_class


def _get_workflow_config_class():
    """Lazily import WorkflowConfig."""
    global _workflow_config_class
    if _workflow_config_class is None:
        from test_ai.workflow.loader import WorkflowConfig
        _workflow_config_class = WorkflowConfig
    return _workflow_config_class


# Node type configurations
NODE_TYPE_CONFIG = {
    "claude_code": {
        "label": "Claude Agent",
        "icon": "🤖",
        "color": "#7c3aed",
        "description": "AI agent using Claude for code generation, analysis, or planning",
        "params": ["role", "prompt", "estimated_tokens"],
    },
    "openai": {
        "label": "OpenAI Agent",
        "icon": "🧠",
        "color": "#10b981",
        "description": "AI agent using OpenAI models",
        "params": ["role", "prompt", "model", "temperature"],
    },
    "shell": {
        "label": "Shell Command",
        "icon": "💻",
        "color": "#f59e0b",
        "description": "Execute shell commands",
        "params": ["command", "allow_failure"],
    },
    "parallel": {
        "label": "Parallel Group",
        "icon": "🔀",
        "color": "#3b82f6",
        "description": "Execute multiple steps in parallel",
        "params": ["steps"],
    },
    "checkpoint": {
        "label": "Checkpoint",
        "icon": "🏁",
        "color": "#6b7280",
        "description": "Resume point for workflow continuation",
        "params": ["message"],
    },
    "fan_out": {
        "label": "Fan Out",
        "icon": "📤",
        "color": "#ec4899",
        "description": "Distribute work across multiple parallel executions",
        "params": ["items_from", "step_template"],
    },
    "fan_in": {
        "label": "Fan In",
        "icon": "📥",
        "color": "#8b5cf6",
        "description": "Aggregate results from fan-out operations",
        "params": ["aggregate_as"],
    },
    "map_reduce": {
        "label": "Map Reduce",
        "icon": "🗺️",
        "color": "#14b8a6",
        "description": "Map-reduce pattern for data processing",
        "params": ["items", "map_step", "reduce_step"],
    },
    "branch": {
        "label": "Branch",
        "icon": "🔀",
        "color": "#f97316",
        "description": "Conditional branching based on context",
        "params": ["condition", "true_step", "false_step"],
    },
    "loop": {
        "label": "Loop",
        "icon": "🔄",
        "color": "#0ea5e9",
        "description": "Iterate over items or until condition met",
        "params": ["items", "step_template", "max_iterations"],
    },
}

# Agent roles available for claude_code/openai steps
AGENT_ROLES = [
    "planner",
    "builder",
    "tester",
    "reviewer",
    "architect",
    "documenter",
    "analyst",
    "visualizer",
    "reporter",
    "data_engineer",
]

# Pre-built workflow templates
WORKFLOW_TEMPLATES = {
    "feature_development": {
        "name": "Feature Development",
        "icon": "🚀",
        "description": "Plan, build, test, and review a new feature",
        "workflow": {
            "name": "Feature Development",
            "version": "1.0",
            "description": "End-to-end feature development workflow with planning, implementation, testing, and code review.",
            "token_budget": 150000,
            "timeout_seconds": 7200,
            "inputs": {
                "feature_request": {"type": "string", "required": True, "description": "Description of the feature to implement"},
                "codebase_context": {"type": "string", "required": False, "description": "Relevant codebase information"},
            },
            "outputs": ["plan", "code", "tests", "review"],
            "steps": [
                {
                    "id": "plan",
                    "type": "claude_code",
                    "params": {"role": "planner", "prompt": "Create a detailed implementation plan for: {{feature_request}}"},
                    "outputs": ["plan"],
                },
                {
                    "id": "build",
                    "type": "claude_code",
                    "params": {"role": "builder", "prompt": "Implement the feature based on this plan: {{plan}}"},
                    "depends_on": "plan",
                    "outputs": ["code"],
                },
                {
                    "id": "test",
                    "type": "claude_code",
                    "params": {"role": "tester", "prompt": "Write comprehensive tests for: {{code}}"},
                    "depends_on": "build",
                    "outputs": ["tests"],
                },
                {
                    "id": "review",
                    "type": "claude_code",
                    "params": {"role": "reviewer", "prompt": "Review the code and tests for quality and security: {{code}} {{tests}}"},
                    "depends_on": "test",
                    "outputs": ["review"],
                },
            ],
        },
    },
    "code_review": {
        "name": "Code Review",
        "icon": "🔍",
        "description": "Analyze code for bugs, security issues, and improvements",
        "workflow": {
            "name": "Code Review",
            "version": "1.0",
            "description": "Comprehensive code review with security analysis and improvement suggestions.",
            "token_budget": 80000,
            "timeout_seconds": 3600,
            "inputs": {
                "code": {"type": "string", "required": True, "description": "Code to review"},
                "focus_areas": {"type": "string", "required": False, "description": "Specific areas to focus on"},
            },
            "outputs": ["analysis", "security_report", "suggestions"],
            "steps": [
                {
                    "id": "analyze",
                    "type": "claude_code",
                    "params": {"role": "analyst", "prompt": "Analyze this code for correctness, patterns, and architecture: {{code}}"},
                    "outputs": ["analysis"],
                },
                {
                    "id": "security",
                    "type": "claude_code",
                    "params": {"role": "reviewer", "prompt": "Review for security vulnerabilities (OWASP Top 10, injection, etc.): {{code}}"},
                    "outputs": ["security_report"],
                },
                {
                    "id": "suggest",
                    "type": "claude_code",
                    "params": {"role": "architect", "prompt": "Based on analysis: {{analysis}} and security review: {{security_report}}, suggest improvements."},
                    "depends_on": ["analyze", "security"],
                    "outputs": ["suggestions"],
                },
            ],
        },
    },
    "documentation": {
        "name": "Documentation Generator",
        "icon": "📚",
        "description": "Generate comprehensive documentation from code",
        "workflow": {
            "name": "Documentation Generator",
            "version": "1.0",
            "description": "Automatically generate API docs, usage guides, and architecture documentation.",
            "token_budget": 100000,
            "timeout_seconds": 5400,
            "inputs": {
                "source_code": {"type": "string", "required": True, "description": "Source code to document"},
                "project_name": {"type": "string", "required": True, "description": "Name of the project"},
            },
            "outputs": ["api_docs", "usage_guide", "architecture_doc"],
            "steps": [
                {
                    "id": "analyze_structure",
                    "type": "claude_code",
                    "params": {"role": "architect", "prompt": "Analyze the structure and architecture of: {{source_code}}"},
                    "outputs": ["structure_analysis"],
                },
                {
                    "id": "generate_api_docs",
                    "type": "claude_code",
                    "params": {"role": "documenter", "prompt": "Generate API documentation for {{project_name}}: {{source_code}}"},
                    "depends_on": "analyze_structure",
                    "outputs": ["api_docs"],
                },
                {
                    "id": "generate_usage_guide",
                    "type": "claude_code",
                    "params": {"role": "documenter", "prompt": "Write a usage guide for {{project_name}} based on: {{structure_analysis}}"},
                    "depends_on": "analyze_structure",
                    "outputs": ["usage_guide"],
                },
                {
                    "id": "generate_architecture_doc",
                    "type": "claude_code",
                    "params": {"role": "architect", "prompt": "Document the architecture of {{project_name}}: {{structure_analysis}}"},
                    "depends_on": "analyze_structure",
                    "outputs": ["architecture_doc"],
                },
            ],
        },
    },
    "data_analysis": {
        "name": "Data Analysis Pipeline",
        "icon": "📊",
        "description": "Analyze data and generate visualizations with report",
        "workflow": {
            "name": "Data Analysis Pipeline",
            "version": "1.0",
            "description": "Load, analyze, visualize data and generate an executive summary report.",
            "token_budget": 120000,
            "timeout_seconds": 5400,
            "inputs": {
                "data_source": {"type": "string", "required": True, "description": "Path or description of data source"},
                "analysis_goals": {"type": "string", "required": True, "description": "What insights are you looking for?"},
            },
            "outputs": ["analysis", "visualizations", "report"],
            "steps": [
                {
                    "id": "load_and_explore",
                    "type": "claude_code",
                    "params": {"role": "data_engineer", "prompt": "Load and explore data from: {{data_source}}. Goals: {{analysis_goals}}"},
                    "outputs": ["data_summary"],
                },
                {
                    "id": "analyze",
                    "type": "claude_code",
                    "params": {"role": "analyst", "prompt": "Perform statistical analysis on: {{data_summary}} to answer: {{analysis_goals}}"},
                    "depends_on": "load_and_explore",
                    "outputs": ["analysis"],
                },
                {
                    "id": "visualize",
                    "type": "claude_code",
                    "params": {"role": "visualizer", "prompt": "Create visualizations for: {{analysis}}"},
                    "depends_on": "analyze",
                    "outputs": ["visualizations"],
                },
                {
                    "id": "report",
                    "type": "claude_code",
                    "params": {"role": "reporter", "prompt": "Generate executive summary from: {{analysis}} and {{visualizations}}"},
                    "depends_on": ["analyze", "visualize"],
                    "outputs": ["report"],
                },
            ],
        },
    },
    "bug_fix": {
        "name": "Bug Fix Workflow",
        "icon": "🐛",
        "description": "Diagnose, fix, and verify bug resolution",
        "workflow": {
            "name": "Bug Fix Workflow",
            "version": "1.0",
            "description": "Systematic bug diagnosis, fix implementation, and verification.",
            "token_budget": 80000,
            "timeout_seconds": 3600,
            "inputs": {
                "bug_report": {"type": "string", "required": True, "description": "Description of the bug"},
                "relevant_code": {"type": "string", "required": False, "description": "Code where bug might be located"},
            },
            "outputs": ["diagnosis", "fix", "verification"],
            "steps": [
                {
                    "id": "diagnose",
                    "type": "claude_code",
                    "params": {"role": "analyst", "prompt": "Diagnose the root cause of: {{bug_report}}. Context: {{relevant_code}}"},
                    "outputs": ["diagnosis"],
                },
                {
                    "id": "fix",
                    "type": "claude_code",
                    "params": {"role": "builder", "prompt": "Implement a fix based on diagnosis: {{diagnosis}}"},
                    "depends_on": "diagnose",
                    "outputs": ["fix"],
                },
                {
                    "id": "test_fix",
                    "type": "claude_code",
                    "params": {"role": "tester", "prompt": "Write tests to verify the fix works: {{fix}}"},
                    "depends_on": "fix",
                    "outputs": ["tests"],
                },
                {
                    "id": "verify",
                    "type": "claude_code",
                    "params": {"role": "reviewer", "prompt": "Verify fix is complete and doesn't introduce regressions: {{fix}} {{tests}}"},
                    "depends_on": "test_fix",
                    "outputs": ["verification"],
                },
            ],
        },
    },
    "shell_pipeline": {
        "name": "Shell Command Pipeline",
        "icon": "💻",
        "description": "Execute shell commands with AI-assisted analysis",
        "workflow": {
            "name": "Shell Command Pipeline",
            "version": "1.0",
            "description": "Run shell commands and analyze the output with AI.",
            "token_budget": 50000,
            "timeout_seconds": 1800,
            "inputs": {
                "command": {"type": "string", "required": True, "description": "Shell command to execute"},
                "analysis_prompt": {"type": "string", "required": False, "description": "What to analyze in the output"},
            },
            "outputs": ["command_output", "analysis"],
            "steps": [
                {
                    "id": "run_command",
                    "type": "shell",
                    "params": {"command": "{{command}}", "allow_failure": False},
                    "outputs": ["command_output"],
                },
                {
                    "id": "analyze_output",
                    "type": "claude_code",
                    "params": {"role": "analyst", "prompt": "Analyze this command output: {{command_output}}. {{analysis_prompt}}"},
                    "depends_on": "run_command",
                    "outputs": ["analysis"],
                },
            ],
        },
    },
}


def _get_workflow_templates() -> dict:
    """Get all available workflow templates."""
    return WORKFLOW_TEMPLATES


def _init_session_state():
    """Initialize session state for the workflow builder."""
    if "builder_nodes" not in st.session_state:
        st.session_state.builder_nodes = []
    if "builder_edges" not in st.session_state:
        st.session_state.builder_edges = []
    if "builder_metadata" not in st.session_state:
        st.session_state.builder_metadata = {
            "name": "New Workflow",
            "version": "1.0",
            "description": "",
            "token_budget": 100000,
            "timeout_seconds": 3600,
        }
    if "builder_inputs" not in st.session_state:
        st.session_state.builder_inputs = {}
    if "builder_outputs" not in st.session_state:
        st.session_state.builder_outputs = []
    if "selected_node" not in st.session_state:
        st.session_state.selected_node = None
    if "connection_mode" not in st.session_state:
        st.session_state.connection_mode = False
    if "connection_source" not in st.session_state:
        st.session_state.connection_source = None
    # Persistence state
    if "builder_current_file" not in st.session_state:
        st.session_state.builder_current_file = None  # Path to current workflow file
    if "builder_dirty" not in st.session_state:
        st.session_state.builder_dirty = False  # True if unsaved changes exist
    # Execution state
    if "builder_execution_running" not in st.session_state:
        st.session_state.builder_execution_running = False
    if "builder_execution_result" not in st.session_state:
        st.session_state.builder_execution_result = None
    if "builder_execution_step_status" not in st.session_state:
        st.session_state.builder_execution_step_status = {}  # step_id -> status
    if "builder_execution_logs" not in st.session_state:
        st.session_state.builder_execution_logs = []
    if "builder_execution_inputs" not in st.session_state:
        st.session_state.builder_execution_inputs = {}


def _get_workflows_dir() -> Path:
    """Get the workflows directory from settings."""
    try:
        return get_settings().workflows_dir
    except Exception:
        # Fallback to local workflows directory
        return Path("workflows")


def _get_builder_state_path(workflow_name: str) -> Path:
    """Get path for builder state JSON (preserves node positions/metadata)."""
    workflows_dir = _get_workflows_dir()
    builder_dir = workflows_dir / ".builder_state"
    builder_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\-]", "_", workflow_name.lower())
    return builder_dir / f"{safe_name}.json"


def _save_builder_state(workflow_name: str) -> None:
    """Save the full builder state (nodes, edges, positions) to JSON."""
    state_path = _get_builder_state_path(workflow_name)
    state = {
        "nodes": st.session_state.builder_nodes,
        "edges": st.session_state.builder_edges,
        "metadata": st.session_state.builder_metadata,
        "inputs": st.session_state.builder_inputs,
        "outputs": st.session_state.builder_outputs,
    }
    try:
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)
        logger.debug(f"Saved builder state to {state_path}")
    except Exception as e:
        logger.error(f"Failed to save builder state: {e}")


def _load_builder_state(workflow_name: str) -> bool:
    """Load builder state from JSON if it exists. Returns True if loaded."""
    state_path = _get_builder_state_path(workflow_name)
    if not state_path.exists():
        return False

    try:
        with open(state_path) as f:
            state = json.load(f)
        st.session_state.builder_nodes = state.get("nodes", [])
        st.session_state.builder_edges = state.get("edges", [])
        st.session_state.builder_metadata = state.get("metadata", {})
        st.session_state.builder_inputs = state.get("inputs", {})
        st.session_state.builder_outputs = state.get("outputs", [])
        st.session_state.selected_node = None
        logger.debug(f"Loaded builder state from {state_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to load builder state: {e}")
        return False


def _list_saved_workflows() -> list[dict]:
    """List all saved workflows with metadata."""
    workflows_dir = _get_workflows_dir()
    workflows_dir.mkdir(parents=True, exist_ok=True)

    workflows = []
    for yaml_path in sorted(workflows_dir.glob("*.yaml")):
        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f)
            workflows.append({
                "path": yaml_path,
                "name": data.get("name", yaml_path.stem),
                "version": data.get("version", "?"),
                "description": data.get("description", ""),
                "steps": len(data.get("steps", [])),
            })
        except Exception as e:
            logger.warning(f"Failed to load workflow {yaml_path}: {e}")
            workflows.append({
                "path": yaml_path,
                "name": yaml_path.stem,
                "version": "?",
                "description": f"Error: {e}",
                "steps": 0,
            })
    return workflows


def _save_workflow_yaml(filepath: Path | None = None) -> Path | None:
    """Save current workflow to YAML file. Returns path on success."""
    workflow = _build_yaml_from_state()
    errors = validate_workflow(workflow)
    if errors:
        return None

    if filepath is None:
        workflows_dir = _get_workflows_dir()
        workflows_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^\w\-]", "_", workflow["name"].lower())
        safe_name = safe_name.strip("_")[:50] or "workflow"
        filepath = workflows_dir / f"{safe_name}.yaml"

        # Ensure filepath stays within workflows_dir
        if not filepath.resolve().is_relative_to(workflows_dir.resolve()):
            logger.error("Invalid workflow name - path traversal attempt")
            return None

    try:
        with open(filepath, "w") as f:
            yaml.dump(workflow, f, default_flow_style=False, sort_keys=False)
        # Also save builder state for positions
        _save_builder_state(workflow["name"])
        st.session_state.builder_current_file = filepath
        st.session_state.builder_dirty = False
        logger.info(f"Saved workflow to {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to save workflow: {e}")
        return None


def _delete_workflow(filepath: Path) -> bool:
    """Delete a workflow YAML and its builder state."""
    try:
        # Load to get name for state file
        with open(filepath) as f:
            data = yaml.safe_load(f)
        workflow_name = data.get("name", filepath.stem)

        # Delete YAML
        filepath.unlink()

        # Delete builder state if exists
        state_path = _get_builder_state_path(workflow_name)
        if state_path.exists():
            state_path.unlink()

        logger.info(f"Deleted workflow {filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete workflow: {e}")
        return False


def _new_workflow() -> None:
    """Reset to a new empty workflow."""
    st.session_state.builder_nodes = []
    st.session_state.builder_edges = []
    st.session_state.builder_metadata = {
        "name": "New Workflow",
        "version": "1.0",
        "description": "",
        "token_budget": 100000,
        "timeout_seconds": 3600,
    }
    st.session_state.builder_inputs = {}
    st.session_state.builder_outputs = []
    st.session_state.selected_node = None
    st.session_state.builder_current_file = None
    st.session_state.builder_dirty = False


def _mark_dirty() -> None:
    """Mark the current workflow as having unsaved changes."""
    st.session_state.builder_dirty = True


def _reset_execution_state() -> None:
    """Reset execution state for a new run."""
    st.session_state.builder_execution_running = False
    st.session_state.builder_execution_result = None
    st.session_state.builder_execution_step_status = {}
    st.session_state.builder_execution_logs = []


def _add_execution_log(message: str, level: str = "info") -> None:
    """Add a log entry to execution logs."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.builder_execution_logs.append({
        "timestamp": timestamp,
        "level": level,
        "message": message,
    })


def _update_step_status(step_id: str, status: str, error: str | None = None) -> None:
    """Update execution status for a step."""
    st.session_state.builder_execution_step_status[step_id] = {
        "status": status,
        "error": error,
    }


def _execute_workflow_sync() -> None:
    """Execute the current workflow synchronously."""
    workflow_data = _build_yaml_from_state()
    errors = validate_workflow(workflow_data)

    if errors:
        _add_execution_log(f"Validation failed: {', '.join(errors)}", "error")
        return

    # Reset state
    _reset_execution_state()
    st.session_state.builder_execution_running = True
    _add_execution_log("Starting workflow execution...")

    try:
        # Get executor and config classes
        WorkflowExecutor = _get_executor_class()
        WorkflowConfig = _get_workflow_config_class()

        # Create config from workflow data
        config = WorkflowConfig.from_dict(workflow_data)
        _add_execution_log(f"Loaded workflow: {config.name} v{config.version}")

        # Mark all steps as pending
        for step in config.steps:
            _update_step_status(step.id, "pending")

        # Get input values from session state
        inputs = dict(st.session_state.builder_execution_inputs)
        _add_execution_log(f"Inputs: {inputs}")

        # Create executor and run
        executor = WorkflowExecutor()

        # Execute workflow
        _add_execution_log("Executing workflow...")
        result = executor.execute(
            workflow=config,
            inputs=inputs,
        )

        # Update step statuses from result
        for step_result in result.steps:
            status_str = step_result.status.value if hasattr(step_result.status, "value") else str(step_result.status)
            error_msg = step_result.error if hasattr(step_result, "error") else None
            _update_step_status(step_result.step_id, status_str, error_msg)
            if status_str == "completed":
                _add_execution_log(f"Step completed: {step_result.step_id}")
            elif status_str == "failed":
                _add_execution_log(f"Step failed: {step_result.step_id} - {error_msg}", "error")
            elif status_str == "skipped":
                _add_execution_log(f"Step skipped: {step_result.step_id}")

        st.session_state.builder_execution_result = result
        _add_execution_log(f"Workflow completed with status: {result.status}")

    except Exception as e:
        _add_execution_log(f"Execution error: {e}", "error")
        st.session_state.builder_execution_result = None
    finally:
        st.session_state.builder_execution_running = False


def _render_execution_inputs() -> None:
    """Render input fields for workflow execution."""
    inputs_config = st.session_state.builder_inputs

    if not inputs_config:
        st.info("This workflow has no required inputs.")
        return

    st.markdown("#### Workflow Inputs")

    for name, config in inputs_config.items():
        input_type = config.get("type", "string")
        required = config.get("required", False)
        description = config.get("description", "")

        label = f"{name}" + (" *" if required else "")

        if input_type == "string":
            st.session_state.builder_execution_inputs[name] = st.text_input(
                label,
                value=st.session_state.builder_execution_inputs.get(name, ""),
                help=description,
                key=f"exec_input_{name}",
            )
        elif input_type == "list":
            value = st.text_area(
                label,
                value=st.session_state.builder_execution_inputs.get(name, ""),
                help=f"{description} (one item per line)",
                key=f"exec_input_{name}",
            )
            st.session_state.builder_execution_inputs[name] = [
                line.strip() for line in value.split("\n") if line.strip()
            ]
        elif input_type == "object":
            value = st.text_area(
                label,
                value=st.session_state.builder_execution_inputs.get(name, "{}"),
                help=f"{description} (JSON format)",
                key=f"exec_input_{name}",
            )
            try:
                st.session_state.builder_execution_inputs[name] = json.loads(value)
            except json.JSONDecodeError:
                st.error(f"Invalid JSON for {name}")


def _render_step_status_indicator(step_id: str) -> str:
    """Get status indicator emoji for a step."""
    status_info = st.session_state.builder_execution_step_status.get(step_id, {})
    status = status_info.get("status", "pending")

    indicators = {
        "pending": "⏳",
        "running": "🔄",
        "completed": "✅",
        "failed": "❌",
        "skipped": "⏭️",
    }
    return indicators.get(status, "❓")


def _render_execution_progress() -> None:
    """Render step-by-step execution progress."""
    st.markdown("#### Execution Progress")

    nodes = st.session_state.builder_nodes
    if not nodes:
        st.info("No steps to execute.")
        return

    for node in nodes:
        node_id = node["id"]
        config = NODE_TYPE_CONFIG.get(node["type"], {"icon": "📦", "label": node["type"]})
        indicator = _render_step_status_indicator(node_id)
        status_info = st.session_state.builder_execution_step_status.get(node_id, {})
        error = status_info.get("error")

        col1, col2 = st.columns([1, 4])
        with col1:
            st.markdown(f"### {indicator}")
        with col2:
            st.markdown(f"**{node_id}** ({config['label']})")
            if error:
                st.error(error)


def _render_execution_logs() -> None:
    """Render execution logs."""
    st.markdown("#### Execution Logs")

    logs = st.session_state.builder_execution_logs
    if not logs:
        st.info("No logs yet. Run the workflow to see execution logs.")
        return

    for log in logs:
        level = log["level"]
        timestamp = log["timestamp"]
        message = log["message"]

        if level == "error":
            st.error(f"[{timestamp}] {message}")
        elif level == "warning":
            st.warning(f"[{timestamp}] {message}")
        else:
            st.text(f"[{timestamp}] {message}")


def _render_execution_result() -> None:
    """Render execution result summary."""
    result = st.session_state.builder_execution_result

    if result is None:
        return

    st.markdown("#### Execution Result")

    # Status badge
    status = result.status if hasattr(result, "status") else "unknown"
    if status == "completed":
        st.success(f"Status: {status}")
    elif status == "failed":
        st.error(f"Status: {status}")
    else:
        st.info(f"Status: {status}")

    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        total_tokens = getattr(result, "total_tokens", 0)
        st.metric("Total Tokens", f"{total_tokens:,}")
    with col2:
        duration_ms = getattr(result, "total_duration_ms", 0)
        st.metric("Duration", f"{duration_ms / 1000:.1f}s")
    with col3:
        step_count = len(getattr(result, "steps", []))
        st.metric("Steps Executed", step_count)

    # Outputs
    outputs = getattr(result, "outputs", {})
    if outputs:
        st.markdown("**Outputs:**")
        st.json(outputs)


def _render_execute_tab() -> None:
    """Render the Execute tab content."""
    st.markdown("### Execute Workflow")

    # Validation check
    workflow_data = _build_yaml_from_state()
    errors = validate_workflow(workflow_data)

    if errors:
        st.error("Cannot execute - workflow has validation errors:")
        for error in errors:
            st.markdown(f"- {error}")
        return

    nodes = st.session_state.builder_nodes
    if not nodes:
        st.warning("Add some steps to your workflow before executing.")
        return

    # Execution inputs
    _render_execution_inputs()

    st.divider()

    # Run button
    is_running = st.session_state.builder_execution_running

    col1, col2 = st.columns(2)
    with col1:
        if st.button(
            "▶️ Run Workflow",
            disabled=is_running,
            use_container_width=True,
            type="primary",
        ):
            _execute_workflow_sync()
            st.rerun()

    with col2:
        if st.button(
            "🔄 Reset",
            disabled=is_running,
            use_container_width=True,
        ):
            _reset_execution_state()
            st.rerun()

    st.divider()

    # Progress and results in columns
    left, right = st.columns(2)

    with left:
        _render_execution_progress()

    with right:
        _render_execution_logs()

    # Result at bottom
    _render_execution_result()


def _generate_node_id(step_type: str) -> str:
    """Generate a unique node ID."""
    base_id = step_type.replace("_", "-")
    existing_ids = {n["id"] for n in st.session_state.builder_nodes}
    counter = 1
    while f"{base_id}-{counter}" in existing_ids:
        counter += 1
    return f"{base_id}-{counter}"


def _add_node(step_type: str):
    """Add a new node to the canvas."""
    node_id = _generate_node_id(step_type)
    config = NODE_TYPE_CONFIG[step_type]

    # Calculate position (grid layout)
    num_nodes = len(st.session_state.builder_nodes)
    col = num_nodes % 3
    row = num_nodes // 3

    node = {
        "id": node_id,
        "type": step_type,
        "position": {"x": 100 + col * 250, "y": 100 + row * 180},
        "data": {
            "label": f"{config['icon']} {node_id}",
            "params": {},
            "on_failure": "abort",
            "max_retries": 3,
            "timeout_seconds": 300,
            "outputs": [],
            "depends_on": [],
            "condition": None,
        },
    }

    st.session_state.builder_nodes.append(node)
    st.session_state.selected_node = node_id
    _mark_dirty()


def _delete_node(node_id: str):
    """Delete a node and its connections."""
    st.session_state.builder_nodes = [
        n for n in st.session_state.builder_nodes if n["id"] != node_id
    ]
    st.session_state.builder_edges = [
        e
        for e in st.session_state.builder_edges
        if e["source"] != node_id and e["target"] != node_id
    ]
    if st.session_state.selected_node == node_id:
        st.session_state.selected_node = None
    _mark_dirty()


def _add_edge(source: str, target: str, label: str | None = None):
    """Add an edge between two nodes."""
    # Check if edge already exists
    for edge in st.session_state.builder_edges:
        if edge["source"] == source and edge["target"] == target:
            return  # Edge already exists

    edge_id = f"edge-{source}-{target}"
    edge = {
        "id": edge_id,
        "source": source,
        "target": target,
        "label": label,
    }
    st.session_state.builder_edges.append(edge)
    _mark_dirty()


def _delete_edge(edge_id: str):
    """Delete an edge."""
    st.session_state.builder_edges = [
        e for e in st.session_state.builder_edges if e["id"] != edge_id
    ]
    _mark_dirty()


def _render_node_palette():
    """Render the node palette sidebar."""
    st.markdown("### Node Types")
    st.markdown("Click to add a node to the canvas")

    for step_type, config in NODE_TYPE_CONFIG.items():
        col1, col2 = st.columns([1, 4])
        with col1:
            st.markdown(
                f"<span style='font-size: 24px;'>{config['icon']}</span>",
                unsafe_allow_html=True,
            )
        with col2:
            if st.button(
                config["label"], key=f"add_{step_type}", use_container_width=True
            ):
                _add_node(step_type)
                st.rerun()

        st.caption(config["description"])
        st.divider()


def _get_node_execution_status(node_id: str) -> tuple[str, str]:
    """Get execution status and color for a node."""
    status_info = st.session_state.builder_execution_step_status.get(node_id, {})
    status = status_info.get("status", "")

    status_colors = {
        "pending": ("#f59e0b", "⏳"),
        "running": ("#3b82f6", "🔄"),
        "completed": ("#10b981", "✅"),
        "failed": ("#ef4444", "❌"),
        "skipped": ("#6b7280", "⏭️"),
    }
    return status_colors.get(status, ("", ""))


def _render_node_card(node: dict) -> None:
    """Render a single node card with enhanced visuals."""
    node_id = node["id"]
    node_type = node["type"]
    config = NODE_TYPE_CONFIG.get(
        node_type, {"icon": "📦", "color": "#666", "label": node_type}
    )
    is_selected = st.session_state.selected_node == node_id

    # Get execution status
    status_color, status_icon = _get_node_execution_status(node_id)

    # Selection styling
    if is_selected:
        border_style = "3px solid #007bff"
        box_shadow = "0 4px 12px rgba(0, 123, 255, 0.3)"
        transform = "scale(1.02)"
    else:
        border_style = f"2px solid {config['color']}50"
        box_shadow = "0 2px 8px rgba(0, 0, 0, 0.1)"
        transform = "scale(1)"

    # Get node details
    deps = node["data"].get("depends_on", [])
    outputs = node["data"].get("outputs", [])
    params = node["data"].get("params", {})
    role = params.get("role", "")

    # Build dependency badge
    deps_html = ""
    if deps:
        deps_html = f"""
            <div style="
                display: inline-flex;
                align-items: center;
                gap: 4px;
                background: #f3f4f6;
                padding: 2px 8px;
                border-radius: 12px;
                font-size: 10px;
                color: #6b7280;
                margin-top: 6px;
            ">
                <span>⬅</span> {', '.join(deps)}
            </div>
        """

    # Build outputs badge
    outputs_html = ""
    if outputs:
        outputs_html = f"""
            <div style="
                display: inline-flex;
                align-items: center;
                gap: 4px;
                background: {config['color']}15;
                padding: 2px 8px;
                border-radius: 12px;
                font-size: 10px;
                color: {config['color']};
                margin-top: 6px;
                margin-left: 4px;
            ">
                <span>📤</span> {', '.join(outputs)}
            </div>
        """

    # Build role badge
    role_html = ""
    if role:
        role_html = f"""
            <span style="
                background: {config['color']}20;
                color: {config['color']};
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 10px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            ">{role}</span>
        """

    # Build status indicator
    status_html = ""
    if status_color:
        status_html = f"""
            <div style="
                position: absolute;
                top: -6px;
                right: -6px;
                background: {status_color};
                color: white;
                width: 24px;
                height: 24px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 12px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            ">{status_icon}</div>
        """

    # Node card HTML with enhanced styling
    st.markdown(
        f"""
        <div style="
            position: relative;
            border: {border_style};
            border-radius: 16px;
            padding: 16px;
            margin: 10px 0;
            background: linear-gradient(145deg, white, {config["color"]}08);
            box-shadow: {box_shadow};
            transform: {transform};
            transition: all 0.2s ease;
        ">
            {status_html}
            <div style="display: flex; align-items: flex-start; gap: 12px;">
                <div style="
                    font-size: 32px;
                    background: {config['color']}15;
                    padding: 8px;
                    border-radius: 12px;
                    line-height: 1;
                ">{config["icon"]}</div>
                <div style="flex: 1; min-width: 0;">
                    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                        <span style="font-weight: 700; font-size: 15px; color: #1f2937;">{node_id}</span>
                        {role_html}
                    </div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 2px;">{config["label"]}</div>
                    <div style="margin-top: 4px;">
                        {deps_html}{outputs_html}
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Selection and delete buttons with better styling
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✏️ Edit", key=f"select_{node_id}", use_container_width=True):
            st.session_state.selected_node = node_id
            st.rerun()
    with col2:
        if st.button("🗑️ Delete", key=f"delete_{node_id}", use_container_width=True):
            _delete_node(node_id)
            st.rerun()


def _render_canvas():
    """Render the workflow canvas with nodes."""
    st.markdown("### 🎯 Workflow Canvas")

    nodes = st.session_state.builder_nodes

    if not nodes:
        st.markdown("""
            <div style="
                text-align: center;
                padding: 48px 24px;
                background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
                border-radius: 20px;
                border: 2px dashed #7dd3fc;
                margin: 16px 0;
            ">
                <div style="font-size: 56px; margin-bottom: 16px;">🚀</div>
                <div style="font-size: 20px; font-weight: 700; color: #0369a1; margin-bottom: 8px;">
                    Start Building Your Workflow
                </div>
                <div style="font-size: 14px; color: #0284c7; max-width: 400px; margin: 0 auto;">
                    Choose a <strong>Template</strong> to get started quickly, or add individual <strong>Nodes</strong> from the sidebar
                </div>
                <div style="
                    display: flex;
                    justify-content: center;
                    gap: 24px;
                    margin-top: 24px;
                    font-size: 13px;
                    color: #6b7280;
                ">
                    <span>📋 Templates</span>
                    <span>•</span>
                    <span>🤖 AI Agents</span>
                    <span>•</span>
                    <span>💻 Shell Commands</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        return

    # Render nodes in columns
    num_cols = min(len(nodes), 3)
    cols = st.columns(num_cols)

    for i, node in enumerate(nodes):
        with cols[i % num_cols]:
            _render_node_card(node)

    # Connection builder with improved styling
    st.markdown("---")
    st.markdown("#### 🔗 Connections")

    if len(nodes) >= 2:
        col1, col2, col3 = st.columns([2, 2, 1])

        node_ids = [n["id"] for n in nodes]

        with col1:
            source = st.selectbox("From", node_ids, key="conn_source")
        with col2:
            # Filter out source from targets
            target_options = [n for n in node_ids if n != source]
            target = st.selectbox("To", target_options, key="conn_target")
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔗 Connect", use_container_width=True, type="primary"):
                if source and target:
                    _add_edge(source, target)
                    # Also update depends_on
                    for node in st.session_state.builder_nodes:
                        if node["id"] == target:
                            deps = node["data"].get("depends_on", [])
                            if source not in deps:
                                deps.append(source)
                                node["data"]["depends_on"] = deps
                    st.rerun()

    # Show existing connections with improved styling
    edges = st.session_state.builder_edges
    if edges:
        st.markdown("""
            <div style="
                background: #f9fafb;
                border-radius: 12px;
                padding: 12px;
                margin-top: 12px;
            ">
                <div style="font-size: 12px; font-weight: 600; color: #6b7280; margin-bottom: 8px;">
                    Active Connections
                </div>
        """, unsafe_allow_html=True)

        for edge in edges:
            col1, col2 = st.columns([4, 1])
            with col1:
                source_node = next((n for n in nodes if n["id"] == edge["source"]), None)
                target_node = next((n for n in nodes if n["id"] == edge["target"]), None)
                source_config = NODE_TYPE_CONFIG.get(source_node["type"], {}) if source_node else {}
                target_config = NODE_TYPE_CONFIG.get(target_node["type"], {}) if target_node else {}

                st.markdown(f"""
                    <div style="
                        display: flex;
                        align-items: center;
                        gap: 8px;
                        padding: 6px 0;
                    ">
                        <span style="font-size: 16px;">{source_config.get('icon', '📦')}</span>
                        <span style="font-weight: 500;">{edge['source']}</span>
                        <span style="color: #9ca3af;">→</span>
                        <span style="font-size: 16px;">{target_config.get('icon', '📦')}</span>
                        <span style="font-weight: 500;">{edge['target']}</span>
                    </div>
                """, unsafe_allow_html=True)
            with col2:
                if st.button("✕", key=f"del_edge_{edge['id']}", help="Remove connection"):
                    _delete_edge(edge["id"])
                    # Also update depends_on
                    for node in st.session_state.builder_nodes:
                        if node["id"] == edge["target"]:
                            deps = node["data"].get("depends_on", [])
                            if edge["source"] in deps:
                                deps.remove(edge["source"])
                                node["data"]["depends_on"] = deps
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)


def _render_node_config():
    """Render configuration panel for selected node."""
    selected_id = st.session_state.selected_node

    if not selected_id:
        st.info("Select a node to configure it")
        return

    # Find the selected node
    node = None
    node_idx = None
    for i, n in enumerate(st.session_state.builder_nodes):
        if n["id"] == selected_id:
            node = n
            node_idx = i
            break

    if not node:
        st.warning("Selected node not found")
        return

    node_type = node["type"]
    config = NODE_TYPE_CONFIG.get(node_type, {})

    st.markdown(f"### {config.get('icon', '📦')} Configure: {selected_id}")

    # Basic settings
    with st.expander("Basic Settings", expanded=True):
        new_id = st.text_input("Node ID", value=node["id"], key="node_id_input")
        if new_id != node["id"]:
            # Update ID in edges too
            for edge in st.session_state.builder_edges:
                if edge["source"] == node["id"]:
                    edge["source"] = new_id
                    edge["id"] = f"edge-{new_id}-{edge['target']}"
                if edge["target"] == node["id"]:
                    edge["target"] = new_id
                    edge["id"] = f"edge-{edge['source']}-{new_id}"
            # Update depends_on in other nodes
            for other_node in st.session_state.builder_nodes:
                deps = other_node["data"].get("depends_on", [])
                if node["id"] in deps:
                    deps[deps.index(node["id"])] = new_id
            node["id"] = new_id
            st.session_state.selected_node = new_id

        # Failure handling
        on_failure = st.selectbox(
            "On Failure",
            list(VALID_ON_FAILURE) + ["fallback", "continue_with_default"],
            index=0,
            key="on_failure_select",
        )
        node["data"]["on_failure"] = on_failure

        max_retries = st.number_input(
            "Max Retries",
            min_value=0,
            max_value=10,
            value=node["data"].get("max_retries", 3),
            key="max_retries_input",
        )
        node["data"]["max_retries"] = max_retries

        timeout = st.number_input(
            "Timeout (seconds)",
            min_value=1,
            max_value=3600,
            value=node["data"].get("timeout_seconds", 300),
            key="timeout_input",
        )
        node["data"]["timeout_seconds"] = timeout

    # Type-specific parameters
    with st.expander("Step Parameters", expanded=True):
        params = node["data"].get("params", {})

        if node_type in ("claude_code", "openai"):
            params["role"] = st.selectbox(
                "Agent Role",
                AGENT_ROLES,
                index=AGENT_ROLES.index(params.get("role", "builder"))
                if params.get("role") in AGENT_ROLES
                else 0,
                key="role_select",
            )

            params["prompt"] = st.text_area(
                "Prompt",
                value=params.get("prompt", ""),
                height=150,
                help="Use ${variable} for variable substitution",
                key="prompt_input",
            )

            params["estimated_tokens"] = st.number_input(
                "Estimated Tokens",
                min_value=100,
                max_value=100000,
                value=params.get("estimated_tokens", 5000),
                key="tokens_input",
            )

            if node_type == "openai":
                params["model"] = st.selectbox(
                    "Model",
                    ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
                    key="model_select",
                )
                params["temperature"] = st.slider(
                    "Temperature",
                    0.0,
                    2.0,
                    value=params.get("temperature", 0.7),
                    key="temp_slider",
                )

        elif node_type == "shell":
            params["command"] = st.text_input(
                "Command",
                value=params.get("command", ""),
                help="Shell command to execute. Use ${variable} for substitution.",
                key="command_input",
            )
            params["allow_failure"] = st.checkbox(
                "Allow Failure",
                value=params.get("allow_failure", False),
                key="allow_failure_check",
            )

        elif node_type == "checkpoint":
            params["message"] = st.text_input(
                "Checkpoint Message",
                value=params.get("message", ""),
                key="checkpoint_msg_input",
            )

        elif node_type == "fan_out":
            params["items_from"] = st.text_input(
                "Items From (variable)",
                value=params.get("items_from", ""),
                help="Variable containing list of items to fan out",
                key="fan_out_items_input",
            )

        elif node_type == "fan_in":
            params["aggregate_as"] = st.text_input(
                "Aggregate As",
                value=params.get("aggregate_as", "results"),
                help="Variable name for aggregated results",
                key="fan_in_agg_input",
            )

        elif node_type == "loop":
            params["max_iterations"] = st.number_input(
                "Max Iterations",
                min_value=1,
                max_value=100,
                value=params.get("max_iterations", 10),
                key="loop_max_input",
            )

        node["data"]["params"] = params

    # Condition configuration
    with st.expander("Condition (Optional)"):
        condition = node["data"].get("condition") or {}

        use_condition = st.checkbox(
            "Add Condition",
            value=bool(condition),
            key="use_condition_check",
        )

        if use_condition:
            cond_field = st.text_input(
                "Field",
                value=condition.get("field", ""),
                help="Context field to check",
                key="cond_field_input",
            )
            cond_operator = st.selectbox(
                "Operator",
                list(VALID_OPERATORS),
                key="cond_op_select",
            )
            cond_value = st.text_input(
                "Value",
                value=str(condition.get("value", "")),
                help="Value to compare against (not needed for not_empty)",
                key="cond_value_input",
            )

            node["data"]["condition"] = {
                "field": cond_field,
                "operator": cond_operator,
                "value": cond_value,
            }
        else:
            node["data"]["condition"] = None

    # Outputs configuration
    with st.expander("Outputs"):
        outputs_str = st.text_input(
            "Output Variables (comma-separated)",
            value=", ".join(node["data"].get("outputs", [])),
            help="Variables this step produces",
            key="outputs_input",
        )
        node["data"]["outputs"] = [
            o.strip() for o in outputs_str.split(",") if o.strip()
        ]

    # Update the node in session state
    st.session_state.builder_nodes[node_idx] = node


def _render_workflow_settings():
    """Render workflow metadata settings."""
    st.markdown("### Workflow Settings")

    meta = st.session_state.builder_metadata

    meta["name"] = st.text_input("Workflow Name", value=meta["name"], key="wf_name")
    meta["version"] = st.text_input("Version", value=meta["version"], key="wf_version")
    meta["description"] = st.text_area(
        "Description", value=meta["description"], key="wf_desc", height=100
    )

    col1, col2 = st.columns(2)
    with col1:
        meta["token_budget"] = st.number_input(
            "Token Budget",
            min_value=1000,
            max_value=1000000,
            value=meta["token_budget"],
            key="wf_budget",
        )
    with col2:
        meta["timeout_seconds"] = st.number_input(
            "Timeout (seconds)",
            min_value=60,
            max_value=86400,
            value=meta["timeout_seconds"],
            key="wf_timeout",
        )

    # Inputs configuration
    st.markdown("#### Workflow Inputs")

    inputs = st.session_state.builder_inputs

    # Add new input
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        new_input_name = st.text_input("Input Name", key="new_input_name")
    with col2:
        new_input_type = st.selectbox(
            "Type", ["string", "list", "object"], key="new_input_type"
        )
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Add Input", key="add_input_btn"):
            if new_input_name and new_input_name not in inputs:
                inputs[new_input_name] = {
                    "type": new_input_type,
                    "required": True,
                    "description": "",
                }
                st.rerun()

    # Show existing inputs
    for name, config in list(inputs.items()):
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            st.markdown(f"**{name}** ({config['type']})")
        with col2:
            config["required"] = st.checkbox(
                "Required",
                value=config.get("required", True),
                key=f"input_req_{name}",
            )
        with col3:
            if st.button("Remove", key=f"del_input_{name}"):
                del inputs[name]
                st.rerun()

    # Outputs configuration
    st.markdown("#### Workflow Outputs")
    outputs_str = st.text_input(
        "Output Variables (comma-separated)",
        value=", ".join(st.session_state.builder_outputs),
        key="wf_outputs",
    )
    st.session_state.builder_outputs = [
        o.strip() for o in outputs_str.split(",") if o.strip()
    ]


def _build_yaml_from_state() -> dict:
    """Build YAML workflow dict from current session state."""
    meta = st.session_state.builder_metadata

    # Build steps from nodes
    steps = []
    for node in st.session_state.builder_nodes:
        step = {
            "id": node["id"],
            "type": node["type"],
        }

        # Add params if not empty
        params = node["data"].get("params", {})
        if params:
            step["params"] = params

        # Add outputs if defined
        outputs = node["data"].get("outputs", [])
        if outputs:
            step["outputs"] = outputs

        # Add depends_on if defined
        deps = node["data"].get("depends_on", [])
        if deps:
            step["depends_on"] = deps if len(deps) > 1 else deps[0]

        # Add condition if defined
        condition = node["data"].get("condition")
        if condition and condition.get("field"):
            step["condition"] = condition

        # Add failure handling
        on_failure = node["data"].get("on_failure", "abort")
        if on_failure != "abort":
            step["on_failure"] = on_failure

        max_retries = node["data"].get("max_retries", 3)
        if max_retries != 3:
            step["max_retries"] = max_retries

        timeout = node["data"].get("timeout_seconds", 300)
        if timeout != 300:
            step["timeout_seconds"] = timeout

        steps.append(step)

    # Build workflow dict
    workflow = {
        "name": meta["name"],
        "version": meta["version"],
        "description": meta["description"],
        "token_budget": meta["token_budget"],
        "timeout_seconds": meta["timeout_seconds"],
    }

    # Add inputs if defined
    if st.session_state.builder_inputs:
        workflow["inputs"] = st.session_state.builder_inputs

    # Add outputs if defined
    if st.session_state.builder_outputs:
        workflow["outputs"] = st.session_state.builder_outputs

    # Add steps
    workflow["steps"] = steps

    return workflow


def _load_yaml_to_state(workflow_data: dict):
    """Load a YAML workflow dict into session state."""
    # Load metadata
    st.session_state.builder_metadata = {
        "name": workflow_data.get("name", "Imported Workflow"),
        "version": workflow_data.get("version", "1.0"),
        "description": workflow_data.get("description", ""),
        "token_budget": workflow_data.get("token_budget", 100000),
        "timeout_seconds": workflow_data.get("timeout_seconds", 3600),
    }

    # Load inputs
    st.session_state.builder_inputs = workflow_data.get("inputs", {})

    # Load outputs
    st.session_state.builder_outputs = workflow_data.get("outputs", [])

    # Load steps as nodes
    nodes = []
    edges = []

    steps = workflow_data.get("steps", [])
    for i, step in enumerate(steps):
        # Calculate position
        col = i % 3
        row = i // 3

        node = {
            "id": step["id"],
            "type": step["type"],
            "position": {"x": 100 + col * 250, "y": 100 + row * 180},
            "data": {
                "label": f"{NODE_TYPE_CONFIG.get(step['type'], {}).get('icon', '📦')} {step['id']}",
                "params": step.get("params", {}),
                "on_failure": step.get("on_failure", "abort"),
                "max_retries": step.get("max_retries", 3),
                "timeout_seconds": step.get("timeout_seconds", 300),
                "outputs": step.get("outputs", []),
                "depends_on": [],
                "condition": step.get("condition"),
            },
        }

        # Handle depends_on
        deps = step.get("depends_on", [])
        if isinstance(deps, str):
            deps = [deps]
        node["data"]["depends_on"] = deps

        # Create edges from dependencies
        for dep in deps:
            edges.append(
                {
                    "id": f"edge-{dep}-{step['id']}",
                    "source": dep,
                    "target": step["id"],
                    "label": None,
                }
            )

        nodes.append(node)

    st.session_state.builder_nodes = nodes
    st.session_state.builder_edges = edges
    st.session_state.selected_node = None
    st.session_state.builder_dirty = False


def _load_workflow_from_file(filepath: Path) -> bool:
    """Load a workflow from a YAML file, trying builder state first."""
    try:
        with open(filepath) as f:
            data = yaml.safe_load(f)
        workflow_name = data.get("name", filepath.stem)

        # Try to load builder state (preserves positions)
        if _load_builder_state(workflow_name):
            st.session_state.builder_current_file = filepath
            return True

        # Fall back to loading from YAML (recalculates positions)
        _load_yaml_to_state(data)
        st.session_state.builder_current_file = filepath
        return True
    except Exception as e:
        logger.error(f"Failed to load workflow from {filepath}: {e}")
        return False


def _render_yaml_preview():
    """Render YAML preview and export options."""
    st.markdown("### YAML Preview")

    workflow = _build_yaml_from_state()
    yaml_str = yaml.dump(
        workflow, default_flow_style=False, sort_keys=False, allow_unicode=True
    )

    # Validate
    errors = validate_workflow(workflow)
    if errors:
        st.error("Validation Errors:")
        for error in errors:
            st.markdown(f"- {error}")
    else:
        st.success("Workflow is valid!")

    # Show YAML
    st.code(yaml_str, language="yaml")

    # Export options
    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            "Download YAML",
            yaml_str,
            file_name=f"{workflow['name'].lower().replace(' ', '-')}.yaml",
            mime="text/yaml",
        )

    with col2:
        # Save to workflows directory
        if st.button("Save to Workflows", disabled=bool(errors)):
            filepath = _save_workflow_yaml()
            if filepath:
                st.success(f"Saved to {filepath}")
            else:
                st.error("Failed to save workflow")


def _render_import_section():
    """Render YAML import section."""
    st.markdown("### Import Workflow")

    tab1, tab2 = st.tabs(["Upload File", "Paste YAML"])

    with tab1:
        uploaded_file = st.file_uploader(
            "Upload YAML workflow",
            type=["yaml", "yml"],
            key="yaml_upload",
        )

        if uploaded_file:
            try:
                content = uploaded_file.read().decode("utf-8")
                data = yaml.safe_load(content)

                if st.button("Import Workflow", key="import_upload"):
                    _load_yaml_to_state(data)
                    st.success("Workflow imported!")
                    st.rerun()
            except Exception as e:
                st.error(f"Failed to parse YAML: {e}")

    with tab2:
        yaml_input = st.text_area(
            "Paste YAML here",
            height=200,
            key="yaml_paste",
        )

        if yaml_input:
            if st.button("Import Workflow", key="import_paste"):
                try:
                    data = yaml.safe_load(yaml_input)
                    _load_yaml_to_state(data)
                    st.success("Workflow imported!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to parse YAML: {e}")

    # Load from existing workflows
    st.markdown("#### Or Load Existing Workflow")

    workflows_dir = _get_workflows_dir()
    if workflows_dir.exists():
        yaml_files = list(workflows_dir.glob("*.yaml"))
        if yaml_files:
            selected_file = st.selectbox(
                "Select workflow",
                yaml_files,
                format_func=lambda x: x.stem,
                key="existing_workflow_select",
            )

            if st.button("Load Workflow", key="load_existing"):
                if _load_workflow_from_file(selected_file):
                    st.success(f"Loaded {selected_file.name}")
                    st.rerun()
                else:
                    st.error("Failed to load workflow")


def _render_visual_graph():
    """Render a visual representation of the workflow graph with enhanced styling."""
    nodes = st.session_state.builder_nodes
    edges = st.session_state.builder_edges

    if not nodes:
        st.markdown("""
            <div style="
                text-align: center;
                padding: 60px 20px;
                color: #9ca3af;
                background: linear-gradient(135deg, #f9fafb, #f3f4f6);
                border-radius: 16px;
                border: 2px dashed #d1d5db;
            ">
                <div style="font-size: 48px; margin-bottom: 16px;">🔗</div>
                <div style="font-size: 18px; font-weight: 600;">No workflow steps yet</div>
                <div style="font-size: 14px; margin-top: 8px;">Add nodes from the Templates or Nodes tab</div>
            </div>
        """, unsafe_allow_html=True)
        return

    st.markdown("### 🔀 Visual Flow")

    # Build adjacency for topological display
    node_map = {n["id"]: n for n in nodes}
    incoming = {n["id"]: set() for n in nodes}
    outgoing = {n["id"]: set() for n in nodes}

    for edge in edges:
        if edge["source"] in node_map and edge["target"] in node_map:
            incoming[edge["target"]].add(edge["source"])
            outgoing[edge["source"]].add(edge["target"])

    # Find roots (no incoming edges)
    roots = [n["id"] for n in nodes if not incoming[n["id"]]]
    if not roots:
        roots = [nodes[0]["id"]]  # Fallback to first node

    # Simple level assignment
    levels = {}
    queue = [(r, 0) for r in roots]
    visited = set()

    while queue:
        node_id, level = queue.pop(0)
        if node_id in visited:
            continue
        visited.add(node_id)
        levels[node_id] = max(levels.get(node_id, 0), level)
        for target in outgoing.get(node_id, []):
            queue.append((target, level + 1))

    # Assign unvisited nodes
    for n in nodes:
        if n["id"] not in levels:
            levels[n["id"]] = 0

    # Group by level
    level_groups = {}
    for node_id, level in levels.items():
        if level not in level_groups:
            level_groups[level] = []
        level_groups[level].append(node_id)

    # Calculate if this is a parallel workflow
    max_parallel = max(len(group) for group in level_groups.values())
    is_parallel = max_parallel > 1

    # Render level by level with enhanced visuals
    total_levels = len(level_groups)
    for level in sorted(level_groups.keys()):
        node_ids = level_groups[level]
        is_parallel_level = len(node_ids) > 1
        cols = st.columns(max(len(node_ids), 1))

        # Show parallel indicator
        if is_parallel_level:
            st.markdown("""
                <div style="
                    text-align: center;
                    font-size: 11px;
                    color: #3b82f6;
                    background: #eff6ff;
                    padding: 4px 12px;
                    border-radius: 12px;
                    display: inline-block;
                    margin: 0 auto 8px auto;
                    width: fit-content;
                ">
                    🔀 Parallel Execution
                </div>
            """, unsafe_allow_html=True)

        for i, node_id in enumerate(node_ids):
            node = node_map[node_id]
            config = NODE_TYPE_CONFIG.get(node["type"], {"icon": "📦", "color": "#666"})

            # Get execution status for visual indicator
            status_color, status_icon = _get_node_execution_status(node_id)

            # Get role if available
            params = node["data"].get("params", {})
            role = params.get("role", "")
            role_badge = f'<div style="font-size: 9px; color: {config["color"]}; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px;">{role}</div>' if role else ""

            # Status ring styling
            status_ring = ""
            if status_color:
                status_ring = f"box-shadow: 0 0 0 3px {status_color}40, 0 4px 12px rgba(0,0,0,0.15);"

            with cols[i]:
                st.markdown(
                    f"""
                    <div style="
                        text-align: center;
                        padding: 16px 12px;
                        border: 2px solid {config["color"]};
                        border-radius: 16px;
                        background: linear-gradient(145deg, white, {config["color"]}10);
                        margin: 4px;
                        {status_ring}
                        transition: all 0.2s ease;
                    ">
                        <div style="
                            font-size: 32px;
                            background: {config['color']}15;
                            width: 56px;
                            height: 56px;
                            border-radius: 14px;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            margin: 0 auto 8px auto;
                            position: relative;
                        ">
                            {config["icon"]}
                            {f'<span style="position: absolute; top: -4px; right: -4px; font-size: 14px;">{status_icon}</span>' if status_icon else ''}
                        </div>
                        <div style="font-size: 13px; font-weight: 700; color: #1f2937;">{node_id}</div>
                        <div style="font-size: 11px; color: #6b7280;">{config["label"]}</div>
                        {role_badge}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # Draw connection arrows if not last level
        if level < max(level_groups.keys()):
            next_level_count = len(level_groups.get(level + 1, []))
            current_count = len(node_ids)

            # Choose arrow style based on branching
            if current_count == 1 and next_level_count > 1:
                # Fan out
                arrow_html = """
                    <div style="text-align: center; padding: 8px 0;">
                        <div style="font-size: 16px; color: #3b82f6;">↙️ ↓ ↘️</div>
                    </div>
                """
            elif current_count > 1 and next_level_count == 1:
                # Fan in
                arrow_html = """
                    <div style="text-align: center; padding: 8px 0;">
                        <div style="font-size: 16px; color: #8b5cf6;">↘️ ↓ ↙️</div>
                    </div>
                """
            else:
                # Regular flow
                arrow_html = """
                    <div style="text-align: center; padding: 8px 0;">
                        <div style="
                            width: 2px;
                            height: 20px;
                            background: linear-gradient(to bottom, #d1d5db, #9ca3af);
                            margin: 0 auto;
                            border-radius: 1px;
                        "></div>
                        <div style="
                            width: 0;
                            height: 0;
                            border-left: 6px solid transparent;
                            border-right: 6px solid transparent;
                            border-top: 8px solid #9ca3af;
                            margin: 0 auto;
                        "></div>
                    </div>
                """
            st.markdown(arrow_html, unsafe_allow_html=True)

    # Show workflow summary
    st.markdown(f"""
        <div style="
            margin-top: 20px;
            padding: 12px 16px;
            background: #f9fafb;
            border-radius: 12px;
            display: flex;
            justify-content: center;
            gap: 24px;
            font-size: 13px;
            color: #6b7280;
        ">
            <span>📊 <strong>{len(nodes)}</strong> steps</span>
            <span>🔗 <strong>{len(edges)}</strong> connections</span>
            <span>📐 <strong>{total_levels}</strong> levels</span>
            {'<span>🔀 <strong>parallel</strong></span>' if is_parallel else '<span>📏 <strong>sequential</strong></span>'}
        </div>
    """, unsafe_allow_html=True)


def _render_saved_workflows():
    """Render saved workflows management section."""
    st.markdown("### Saved Workflows")

    workflows = _list_saved_workflows()

    if not workflows:
        st.info("No saved workflows yet. Create one and save it!")
        return

    for wf in workflows:
        with st.expander(f"**{wf['name']}** v{wf['version']}", expanded=False):
            st.caption(wf["description"] or "No description")
            st.markdown(f"Steps: {wf['steps']}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Load", key=f"load_{wf['path']}", use_container_width=True):
                    if _load_workflow_from_file(wf["path"]):
                        st.success(f"Loaded {wf['name']}")
                        st.rerun()
                    else:
                        st.error("Failed to load")
            with col2:
                if st.button(
                    "Delete", key=f"del_{wf['path']}", use_container_width=True
                ):
                    if _delete_workflow(wf["path"]):
                        st.success(f"Deleted {wf['name']}")
                        st.rerun()
                    else:
                        st.error("Failed to delete")


def _render_templates_section():
    """Render workflow templates selection section."""
    st.markdown("### Templates")
    st.caption("Start with a pre-built workflow pattern")

    templates = _get_workflow_templates()

    for template_id, template in templates.items():
        with st.expander(f"{template['icon']} **{template['name']}**", expanded=False):
            st.markdown(template["description"])

            workflow = template["workflow"]
            st.markdown(f"**Steps:** {len(workflow['steps'])}")

            # Show step preview
            step_names = [s["id"] for s in workflow["steps"]]
            st.caption(" → ".join(step_names))

            # Show required inputs
            inputs = workflow.get("inputs", {})
            required = [k for k, v in inputs.items() if v.get("required")]
            if required:
                st.caption(f"**Required inputs:** {', '.join(required)}")

            if st.button(
                "Use Template",
                key=f"template_{template_id}",
                use_container_width=True,
                type="primary",
            ):
                _load_yaml_to_state(workflow)
                _mark_dirty()
                st.success(f"Loaded template: {template['name']}")
                st.rerun()


def render_workflow_builder():
    """Main entry point for the visual workflow builder."""
    st.title("🎨 Visual Workflow Builder")

    _init_session_state()

    # Show current file status
    current_file = st.session_state.builder_current_file
    is_dirty = st.session_state.builder_dirty
    workflow_name = st.session_state.builder_metadata.get("name", "New Workflow")

    status_text = workflow_name
    if current_file:
        status_text = f"{workflow_name} ({current_file.name})"
    if is_dirty:
        status_text += " *"

    st.caption(f"Current: {status_text}")

    # Top action bar
    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])

    with col1:
        if st.button("New", use_container_width=True, help="Create new workflow"):
            _new_workflow()
            st.rerun()

    with col2:
        # Quick save button
        workflow = _build_yaml_from_state()
        errors = validate_workflow(workflow)
        save_disabled = bool(errors) or not is_dirty

        if st.button(
            "Save",
            use_container_width=True,
            disabled=save_disabled,
            help="Save workflow (Ctrl+S)",
        ):
            filepath = _save_workflow_yaml()
            if filepath:
                st.toast(f"Saved to {filepath.name}")
                st.rerun()

    with col3:
        node_count = len(st.session_state.builder_nodes)
        st.metric("Nodes", node_count)

    with col4:
        edge_count = len(st.session_state.builder_edges)
        st.metric("Connections", edge_count)

    with col5:
        if errors:
            st.error(f"{len(errors)} error(s)")
        else:
            st.success("Valid")

    st.divider()

    # Main layout: sidebar + main content
    sidebar, main = st.columns([1, 3])

    with sidebar:
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Templates", "Nodes", "Settings", "Saved", "Import"])

        with tab1:
            _render_templates_section()

        with tab2:
            _render_node_palette()

        with tab3:
            _render_workflow_settings()

        with tab4:
            _render_saved_workflows()

        with tab5:
            _render_import_section()

    with main:
        tab1, tab2, tab3, tab4 = st.tabs(["Canvas", "Visual", "YAML", "Execute"])

        with tab1:
            _render_canvas()
            st.divider()
            _render_node_config()

        with tab2:
            _render_visual_graph()

        with tab3:
            _render_yaml_preview()

        with tab4:
            _render_execute_tab()
