"""Visual Workflow Builder for Streamlit dashboard.

This module is a backward-compatibility shim. All code has been refactored
into focused submodules:

- constants.py: NODE_TYPE_CONFIG, AGENT_ROLES, WORKFLOW_TEMPLATES
- state.py: Session state management functions
- yaml_ops.py: YAML conversion operations
- persistence.py: File persistence operations
- renderers.py: UI rendering functions
- builder.py: Main entry point (render_workflow_builder)
"""

# get_settings must be importable from this package for test patch compatibility:
#   monkeypatch.setattr("test_ai.dashboard.workflow_builder.get_settings", ...)
from test_ai.config import get_settings  # noqa: F401
from test_ai.workflow.loader import (  # noqa: F401
    validate_workflow,
    VALID_OPERATORS,
    VALID_ON_FAILURE,
)

from .constants import (  # noqa: F401
    NODE_TYPE_CONFIG,
    AGENT_ROLES,
    WORKFLOW_TEMPLATES,
    _get_workflow_templates,
)
from .state import (  # noqa: F401
    _init_session_state,
    _new_workflow,
    _mark_dirty,
    _generate_node_id,
    _add_node,
    _delete_node,
    _add_edge,
    _delete_edge,
)
from .yaml_ops import _build_yaml_from_state, _load_yaml_to_state  # noqa: F401
from .persistence import (  # noqa: F401
    _get_workflows_dir,
    _get_builder_state_path,
    _save_builder_state,
    _load_builder_state,
    _list_saved_workflows,
    _save_workflow_yaml,
    _delete_workflow,
    _load_workflow_from_file,
)
from .renderers import (  # noqa: F401
    _get_node_execution_status,
    _render_node_card,
    _render_node_palette,
    _render_canvas,
    _render_node_config,
    _render_workflow_settings,
    _render_yaml_preview,
    _render_import_section,
    _render_visual_graph,
    _render_saved_workflows,
    _render_templates_section,
    _render_execute_preview,
)
from .builder import render_workflow_builder  # noqa: F401
