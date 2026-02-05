"""Visual Workflow Builder for Streamlit dashboard.

A drag-and-drop style workflow builder that renders workflows as visual graphs
and allows users to create, edit, and export YAML workflow definitions.
"""

from __future__ import annotations

import json
import logging
import re
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
    if "builder_current_file" not in st.session_state:
        st.session_state.builder_current_file = None
    if "builder_dirty" not in st.session_state:
        st.session_state.builder_dirty = False


def _get_workflows_dir() -> Path:
    """Get the workflows directory from settings."""
    return get_settings().workflows_dir


def _get_builder_state_path(workflow_name: str) -> Path:
    """Get path for builder state JSON file."""
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "-", workflow_name.lower())
    return _get_workflows_dir() / f".builder-{safe_name}.json"


def _save_builder_state(workflow_name: str) -> bool:
    """Save the current builder state to a JSON file.

    Args:
        workflow_name: Name of the workflow

    Returns:
        True if saved successfully
    """
    try:
        workflows_dir = _get_workflows_dir()
        workflows_dir.mkdir(parents=True, exist_ok=True)

        state = {
            "nodes": st.session_state.builder_nodes,
            "edges": st.session_state.builder_edges,
            "metadata": st.session_state.builder_metadata,
            "inputs": st.session_state.builder_inputs,
            "outputs": st.session_state.builder_outputs,
        }

        state_path = _get_builder_state_path(workflow_name)
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)

        logger.info(f"Saved builder state to {state_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save builder state: {e}")
        return False


def _load_builder_state(workflow_name: str) -> bool:
    """Load builder state from a JSON file.

    Args:
        workflow_name: Name of the workflow

    Returns:
        True if loaded successfully
    """
    try:
        state_path = _get_builder_state_path(workflow_name)
        if not state_path.exists():
            return False

        with open(state_path) as f:
            state = json.load(f)

        st.session_state.builder_nodes = state.get("nodes", [])
        st.session_state.builder_edges = state.get("edges", [])
        st.session_state.builder_metadata = state.get(
            "metadata",
            {
                "name": "New Workflow",
                "version": "1.0",
                "description": "",
                "token_budget": 100000,
                "timeout_seconds": 3600,
            },
        )
        st.session_state.builder_inputs = state.get("inputs", {})
        st.session_state.builder_outputs = state.get("outputs", [])
        st.session_state.selected_node = None
        st.session_state.builder_dirty = False

        logger.info(f"Loaded builder state from {state_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to load builder state: {e}")
        return False


def _list_saved_workflows() -> list[dict]:
    """List all saved workflows with their metadata.

    Returns:
        List of dicts with name, path, has_builder_state
    """
    workflows = []
    workflows_dir = _get_workflows_dir()

    if not workflows_dir.exists():
        return workflows

    for yaml_path in workflows_dir.glob("*.yaml"):
        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f)

            name = data.get("name", yaml_path.stem)
            builder_state_path = _get_builder_state_path(name)

            workflows.append(
                {
                    "name": name,
                    "path": yaml_path,
                    "description": data.get("description", ""),
                    "has_builder_state": builder_state_path.exists(),
                }
            )
        except Exception as e:
            logger.warning(f"Failed to read workflow {yaml_path}: {e}")
            continue

    return sorted(workflows, key=lambda w: w["name"].lower())


def _save_workflow_yaml(workflow_name: str) -> Path | None:
    """Save the current workflow as YAML.

    Args:
        workflow_name: Name of the workflow

    Returns:
        Path to saved file, or None on failure
    """
    try:
        workflows_dir = _get_workflows_dir()
        workflows_dir.mkdir(parents=True, exist_ok=True)

        workflow = _build_yaml_from_state()
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "-", workflow_name.lower())
        filepath = workflows_dir / f"{safe_name}.yaml"

        with open(filepath, "w") as f:
            yaml.dump(workflow, f, default_flow_style=False, sort_keys=False)

        # Also save builder state
        _save_builder_state(workflow_name)

        st.session_state.builder_current_file = str(filepath)
        st.session_state.builder_dirty = False

        logger.info(f"Saved workflow to {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to save workflow: {e}")
        return None


def _delete_workflow(workflow_name: str) -> bool:
    """Delete a workflow and its builder state.

    Args:
        workflow_name: Name of the workflow

    Returns:
        True if deleted successfully
    """
    try:
        workflows_dir = _get_workflows_dir()
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "-", workflow_name.lower())

        yaml_path = workflows_dir / f"{safe_name}.yaml"
        state_path = _get_builder_state_path(workflow_name)

        if yaml_path.exists():
            yaml_path.unlink()
        if state_path.exists():
            state_path.unlink()

        logger.info(f"Deleted workflow {workflow_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete workflow: {e}")
        return False


def _new_workflow():
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


def _delete_edge(edge_id: str):
    """Delete an edge."""
    st.session_state.builder_edges = [
        e for e in st.session_state.builder_edges if e["id"] != edge_id
    ]


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


def _render_node_card(node: dict) -> None:
    """Render a single node card."""
    node_id = node["id"]
    node_type = node["type"]
    config = NODE_TYPE_CONFIG.get(
        node_type, {"icon": "📦", "color": "#666", "label": node_type}
    )
    is_selected = st.session_state.selected_node == node_id

    border_style = (
        "3px solid #007bff" if is_selected else f"2px solid {config['color']}"
    )

    # Get dependencies
    deps = node["data"].get("depends_on", [])
    deps_str = f" ← {', '.join(deps)}" if deps else ""

    # Node card HTML
    st.markdown(
        f"""
        <div style="
            border: {border_style};
            border-radius: 12px;
            padding: 12px;
            margin: 8px 0;
            background: linear-gradient(135deg, {config["color"]}20, {config["color"]}10);
            cursor: pointer;
        ">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 28px;">{config["icon"]}</span>
                <div>
                    <div style="font-weight: bold; font-size: 14px;">{node_id}</div>
                    <div style="font-size: 11px; color: #666;">{config["label"]}{deps_str}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Selection and delete buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Edit", key=f"select_{node_id}", use_container_width=True):
            st.session_state.selected_node = node_id
            st.rerun()
    with col2:
        if st.button("Delete", key=f"delete_{node_id}", use_container_width=True):
            _delete_node(node_id)
            st.rerun()


def _render_canvas():
    """Render the workflow canvas with nodes."""
    st.markdown("### Workflow Canvas")

    nodes = st.session_state.builder_nodes

    if not nodes:
        st.info(
            "Add nodes from the palette on the left to start building your workflow."
        )
        return

    # Render nodes in columns
    num_cols = min(len(nodes), 3)
    cols = st.columns(num_cols)

    for i, node in enumerate(nodes):
        with cols[i % num_cols]:
            _render_node_card(node)

    # Connection builder
    st.markdown("---")
    st.markdown("#### Connections")

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
            if st.button("Connect", use_container_width=True):
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

    # Show existing connections
    edges = st.session_state.builder_edges
    if edges:
        st.markdown("**Current Connections:**")
        for edge in edges:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"`{edge['source']}` → `{edge['target']}`")
            with col2:
                if st.button("Remove", key=f"del_edge_{edge['id']}"):
                    _delete_edge(edge["id"])
                    # Also update depends_on
                    for node in st.session_state.builder_nodes:
                        if node["id"] == edge["target"]:
                            deps = node["data"].get("depends_on", [])
                            if edge["source"] in deps:
                                deps.remove(edge["source"])
                                node["data"]["depends_on"] = deps
                    st.rerun()


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
        # Save to workflows directory using persistence functions
        if st.button("Save Workflow", key="save_workflow_btn"):
            workflow_name = st.session_state.builder_metadata.get("name", "workflow")
            filepath = _save_workflow_yaml(workflow_name)
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
                try:
                    with open(selected_file) as f:
                        data = yaml.safe_load(f)

                    # First try to load builder state if available
                    workflow_name = data.get("name", selected_file.stem)
                    if not _load_builder_state(workflow_name):
                        # Fall back to loading from YAML
                        _load_yaml_to_state(data)

                    st.session_state.builder_current_file = str(selected_file)
                    st.session_state.builder_dirty = False
                    st.success(f"Loaded {selected_file.name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to load: {e}")


def _render_visual_graph():
    """Render a visual representation of the workflow graph."""
    nodes = st.session_state.builder_nodes
    edges = st.session_state.builder_edges

    if not nodes:
        return

    st.markdown("### Visual Flow")

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

    # Render level by level
    for level in sorted(level_groups.keys()):
        node_ids = level_groups[level]
        cols = st.columns(max(len(node_ids), 1))

        for i, node_id in enumerate(node_ids):
            node = node_map[node_id]
            config = NODE_TYPE_CONFIG.get(node["type"], {"icon": "📦", "color": "#666"})

            with cols[i]:
                st.markdown(
                    f"""
                    <div style="
                        text-align: center;
                        padding: 12px;
                        border: 2px solid {config["color"]};
                        border-radius: 8px;
                        background: {config["color"]}15;
                        margin: 4px;
                    ">
                        <div style="font-size: 24px;">{config["icon"]}</div>
                        <div style="font-size: 12px; font-weight: bold;">{node_id}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # Draw arrows if not last level
        if level < max(level_groups.keys()):
            st.markdown(
                """
                <div style="text-align: center; font-size: 20px; color: #999;">
                    ↓
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_saved_workflows_sidebar():
    """Render saved workflows panel in the Streamlit sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Saved Workflows")

    # Current workflow info
    current_name = st.session_state.builder_metadata.get("name", "New Workflow")
    current_file = st.session_state.builder_current_file
    is_dirty = st.session_state.builder_dirty

    status = current_name
    if is_dirty:
        status += " *"
    st.sidebar.caption(f"**Current:** {status}")

    # Quick save button
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("💾 Save", key="sidebar_save", use_container_width=True):
            filepath = _save_workflow_yaml(current_name)
            if filepath:
                st.sidebar.success("Saved!")
                st.rerun()
    with col2:
        if st.button("📄 New", key="sidebar_new", use_container_width=True):
            _new_workflow()
            st.rerun()

    # List saved workflows
    workflows = _list_saved_workflows()
    if workflows:
        st.sidebar.markdown("#### Load Workflow")
        for wf in workflows:
            col1, col2 = st.sidebar.columns([3, 1])
            with col1:
                label = wf["name"]
                if wf["has_builder_state"]:
                    label += " 📐"  # Has builder state
                if st.button(
                    label,
                    key=f"load_{wf['name']}",
                    use_container_width=True,
                    help=wf["description"] or "Click to load",
                ):
                    # Try to load builder state first
                    if not _load_builder_state(wf["name"]):
                        # Fall back to YAML
                        with open(wf["path"]) as f:
                            data = yaml.safe_load(f)
                        _load_yaml_to_state(data)

                    st.session_state.builder_current_file = str(wf["path"])
                    st.session_state.builder_dirty = False
                    st.rerun()

            with col2:
                if st.button(
                    "🗑️",
                    key=f"delete_{wf['name']}",
                    help="Delete workflow",
                ):
                    if _delete_workflow(wf["name"]):
                        if st.session_state.builder_current_file == str(wf["path"]):
                            _new_workflow()
                        st.rerun()
    else:
        st.sidebar.info("No saved workflows yet")


def render_workflow_builder():
    """Main entry point for the visual workflow builder."""
    st.title("🎨 Visual Workflow Builder")

    _init_session_state()

    # Render saved workflows in sidebar
    _render_saved_workflows_sidebar()

    # Top action bar
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        if st.button("New", use_container_width=True, help="Create new workflow"):
            _new_workflow()
            st.rerun()

    with col2:
        if st.button(
            "Save", use_container_width=True, help="Save current workflow"
        ):
            workflow_name = st.session_state.builder_metadata.get("name", "workflow")
            filepath = _save_workflow_yaml(workflow_name)
            if filepath:
                st.toast(f"Saved to {filepath}")
            else:
                st.error("Failed to save")

    with col3:
        node_count = len(st.session_state.builder_nodes)
        st.metric("Nodes", node_count)

    with col4:
        edge_count = len(st.session_state.builder_edges)
        st.metric("Edges", edge_count)

    with col5:
        workflow = _build_yaml_from_state()
        errors = validate_workflow(workflow)
        if errors:
            st.error(f"{len(errors)} error(s)")
        else:
            st.success("Valid")

    st.divider()

    # Main layout: sidebar + main content
    sidebar, main = st.columns([1, 3])

    with sidebar:
        tab1, tab2, tab3 = st.tabs(["Nodes", "Settings", "Import"])

        with tab1:
            _render_node_palette()

        with tab2:
            _render_workflow_settings()

        with tab3:
            _render_import_section()

    with main:
        tab1, tab2, tab3 = st.tabs(["Canvas", "Visual", "YAML"])

        with tab1:
            _render_canvas()
            st.divider()
            _render_node_config()

        with tab2:
            _render_visual_graph()

        with tab3:
            _render_yaml_preview()
