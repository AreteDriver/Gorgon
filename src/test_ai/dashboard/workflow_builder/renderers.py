"""Rendering functions for the visual workflow builder."""

from __future__ import annotations

import streamlit as st
import yaml

from .constants import NODE_TYPE_CONFIG, AGENT_ROLES, _get_workflow_templates
from .state import _add_node, _delete_node, _add_edge, _delete_edge, _mark_dirty
from .yaml_ops import _build_yaml_from_state, _load_yaml_to_state
from .persistence import (
    _get_workflows_dir,
    _list_saved_workflows,
    _save_workflow_yaml,
    _delete_workflow,
    _load_workflow_from_file,
)

from test_ai.workflow.loader import (
    validate_workflow,
    VALID_OPERATORS,
    VALID_ON_FAILURE,
)


def _get_node_execution_status(node_id: str) -> tuple[str, str]:
    """Get execution status and color for a node."""
    status_info = st.session_state.builder_execution_step_status.get(node_id, {})
    status = status_info.get("status", "")

    status_colors = {
        "pending": ("#f59e0b", "\u23f3"),
        "running": ("#3b82f6", "\U0001f504"),
        "completed": ("#10b981", "\u2705"),
        "failed": ("#ef4444", "\u274c"),
        "skipped": ("#6b7280", "\u23ed\ufe0f"),
    }
    return status_colors.get(status, ("", ""))


def _render_node_card(node: dict) -> None:
    """Render a single node card with enhanced visuals."""
    node_id = node["id"]
    node_type = node["type"]
    config = NODE_TYPE_CONFIG.get(
        node_type, {"icon": "\U0001f4e6", "color": "#666", "label": node_type}
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
                <span>\u2b05</span> {", ".join(deps)}
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
                background: {config["color"]}15;
                padding: 2px 8px;
                border-radius: 12px;
                font-size: 10px;
                color: {config["color"]};
                margin-top: 6px;
                margin-left: 4px;
            ">
                <span>\U0001f4e4</span> {", ".join(outputs)}
            </div>
        """

    # Build role badge
    role_html = ""
    if role:
        role_html = f"""
            <span style="
                background: {config["color"]}20;
                color: {config["color"]};
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
                    background: {config["color"]}15;
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
        if st.button("\u270f\ufe0f Edit", key=f"select_{node_id}", use_container_width=True):
            st.session_state.selected_node = node_id
            st.rerun()
    with col2:
        if st.button("\U0001f5d1\ufe0f Delete", key=f"delete_{node_id}", use_container_width=True):
            _delete_node(node_id)
            st.rerun()


def _render_canvas() -> None:
    """Render the workflow canvas with nodes."""
    st.markdown("### \U0001f3af Workflow Canvas")

    nodes = st.session_state.builder_nodes

    if not nodes:
        st.markdown(
            """
            <div style="
                text-align: center;
                padding: 48px 24px;
                background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
                border-radius: 20px;
                border: 2px dashed #7dd3fc;
                margin: 16px 0;
            ">
                <div style="font-size: 56px; margin-bottom: 16px;">\U0001f680</div>
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
                    <span>\U0001f4cb Templates</span>
                    <span>\u2022</span>
                    <span>\U0001f916 AI Agents</span>
                    <span>\u2022</span>
                    <span>\U0001f4bb Shell Commands</span>
                </div>
            </div>
        """,
            unsafe_allow_html=True,
        )
        return

    # Render nodes in columns
    num_cols = min(len(nodes), 3)
    cols = st.columns(num_cols)

    for i, node in enumerate(nodes):
        with cols[i % num_cols]:
            _render_node_card(node)

    # Connection builder with improved styling
    st.markdown("---")
    st.markdown("#### \U0001f517 Connections")

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
            if st.button("\U0001f517 Connect", use_container_width=True, type="primary"):
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
        st.markdown(
            """
            <div style="
                background: #f9fafb;
                border-radius: 12px;
                padding: 12px;
                margin-top: 12px;
            ">
                <div style="font-size: 12px; font-weight: 600; color: #6b7280; margin-bottom: 8px;">
                    Active Connections
                </div>
        """,
            unsafe_allow_html=True,
        )

        for edge in edges:
            col1, col2 = st.columns([4, 1])
            with col1:
                source_node = next(
                    (n for n in nodes if n["id"] == edge["source"]), None
                )
                target_node = next(
                    (n for n in nodes if n["id"] == edge["target"]), None
                )
                source_config = (
                    NODE_TYPE_CONFIG.get(source_node["type"], {}) if source_node else {}
                )
                target_config = (
                    NODE_TYPE_CONFIG.get(target_node["type"], {}) if target_node else {}
                )

                st.markdown(
                    f"""
                    <div style="
                        display: flex;
                        align-items: center;
                        gap: 8px;
                        padding: 6px 0;
                    ">
                        <span style="font-size: 16px;">{source_config.get("icon", "\U0001f4e6")}</span>
                        <span style="font-weight: 500;">{edge["source"]}</span>
                        <span style="color: #9ca3af;">\u2192</span>
                        <span style="font-size: 16px;">{target_config.get("icon", "\U0001f4e6")}</span>
                        <span style="font-weight: 500;">{edge["target"]}</span>
                    </div>
                """,
                    unsafe_allow_html=True,
                )
            with col2:
                if st.button(
                    "\u2715", key=f"del_edge_{edge['id']}", help="Remove connection"
                ):
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


def _render_node_palette() -> None:
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


def _render_node_config() -> None:
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

    st.markdown(f"### {config.get('icon', '\U0001f4e6')} Configure: {selected_id}")

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


def _render_workflow_settings() -> None:
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


def _render_yaml_preview() -> None:
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


def _render_import_section() -> None:
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


def _render_visual_graph() -> None:
    """Render a visual representation of the workflow graph with enhanced styling."""
    nodes = st.session_state.builder_nodes
    edges = st.session_state.builder_edges

    if not nodes:
        st.markdown(
            """
            <div style="
                text-align: center;
                padding: 60px 20px;
                color: #9ca3af;
                background: linear-gradient(135deg, #f9fafb, #f3f4f6);
                border-radius: 16px;
                border: 2px dashed #d1d5db;
            ">
                <div style="font-size: 48px; margin-bottom: 16px;">\U0001f517</div>
                <div style="font-size: 18px; font-weight: 600;">No workflow steps yet</div>
                <div style="font-size: 14px; margin-top: 8px;">Add nodes from the Templates or Nodes tab</div>
            </div>
        """,
            unsafe_allow_html=True,
        )
        return

    st.markdown("### \U0001f500 Visual Flow")

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
            st.markdown(
                """
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
                    \U0001f500 Parallel Execution
                </div>
            """,
                unsafe_allow_html=True,
            )

        for i, node_id in enumerate(node_ids):
            node = node_map[node_id]
            config = NODE_TYPE_CONFIG.get(node["type"], {"icon": "\U0001f4e6", "color": "#666"})

            # Get execution status for visual indicator
            status_color, status_icon = _get_node_execution_status(node_id)

            # Get role if available
            params = node["data"].get("params", {})
            role = params.get("role", "")
            role_badge = (
                f'<div style="font-size: 9px; color: {config["color"]}; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px;">{role}</div>'
                if role
                else ""
            )

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
                            background: {config["color"]}15;
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
                            {f'<span style="position: absolute; top: -4px; right: -4px; font-size: 14px;">{status_icon}</span>' if status_icon else ""}
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
                        <div style="font-size: 16px; color: #3b82f6;">\u2199\ufe0f \u2b07 \u2198\ufe0f</div>
                    </div>
                """
            elif current_count > 1 and next_level_count == 1:
                # Fan in
                arrow_html = """
                    <div style="text-align: center; padding: 8px 0;">
                        <div style="font-size: 16px; color: #8b5cf6;">\u2198\ufe0f \u2b07 \u2199\ufe0f</div>
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
    st.markdown(
        f"""
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
            <span>\U0001f4ca <strong>{len(nodes)}</strong> steps</span>
            <span>\U0001f517 <strong>{len(edges)}</strong> connections</span>
            <span>\U0001f4d0 <strong>{total_levels}</strong> levels</span>
            {"<span>\U0001f500 <strong>parallel</strong></span>" if is_parallel else "<span>\U0001f4cf <strong>sequential</strong></span>"}
        </div>
    """,
        unsafe_allow_html=True,
    )


def _render_saved_workflows() -> None:
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
                if st.button(
                    "Load", key=f"load_{wf['path']}", use_container_width=True
                ):
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


def _render_templates_section() -> None:
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
            st.caption(" \u2192 ".join(step_names))

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


def _render_execute_preview() -> None:
    """Render execution preview with validation and step summary."""
    workflow = _build_yaml_from_state()
    errors = validate_workflow(workflow)

    st.markdown("### Execution Preview")

    if errors:
        st.error(
            f"**{len(errors)} validation error(s) must be fixed before execution:**"
        )
        for error in errors:
            st.markdown(f"- {error}")
        return

    st.success("Workflow is valid and ready to execute.")

    # Step execution order
    steps = workflow.get("steps", [])
    if steps:
        st.markdown("#### Execution Order")
        for i, step in enumerate(steps, 1):
            deps = step.get("depends_on", [])
            if isinstance(deps, str):
                deps = [deps]
            dep_str = f" (after: {', '.join(deps)})" if deps else ""
            condition = step.get("condition")
            cond_str = (
                f" | condition: `{condition['field']} {condition.get('operator', '==')} {condition.get('value', '')}`"
                if condition
                else ""
            )
            on_failure = step.get("on_failure", "abort")
            fail_str = f" | on_failure: {on_failure}" if on_failure != "abort" else ""
            st.markdown(
                f"**{i}.** `{step['id']}` ({step['type']}){dep_str}{cond_str}{fail_str}"
            )

    # Variables
    variables = workflow.get("variables", {})
    if variables:
        st.markdown("#### Variables")
        st.json(variables)

    st.info("Save the workflow, then execute it from the **Execute** page.")
