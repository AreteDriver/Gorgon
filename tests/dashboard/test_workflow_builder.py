"""Tests for the visual workflow builder."""

import pytest

from test_ai.dashboard.workflow_builder import (
    NODE_TYPE_CONFIG,
    AGENT_ROLES,
    _generate_node_id,
    _build_yaml_from_state,
    _load_yaml_to_state,
)


class TestNodeTypeConfig:
    """Test node type configuration."""

    def test_all_step_types_have_config(self):
        """All valid step types should have node configuration."""
        expected_types = {
            "claude_code",
            "openai",
            "shell",
            "parallel",
            "checkpoint",
            "fan_out",
            "fan_in",
            "map_reduce",
            "branch",
            "loop",
        }
        assert set(NODE_TYPE_CONFIG.keys()) == expected_types

    def test_config_has_required_fields(self):
        """Each config should have required fields."""
        for step_type, config in NODE_TYPE_CONFIG.items():
            assert "label" in config, f"{step_type} missing label"
            assert "icon" in config, f"{step_type} missing icon"
            assert "color" in config, f"{step_type} missing color"
            assert "description" in config, f"{step_type} missing description"
            assert "params" in config, f"{step_type} missing params"


class TestAgentRoles:
    """Test agent roles configuration."""

    def test_all_roles_present(self):
        """All expected agent roles should be present."""
        expected_roles = {
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
        }
        assert set(AGENT_ROLES) == expected_roles


class TestNodeIdGeneration:
    """Test node ID generation."""

    def test_generate_node_id_basic(self, mock_session_state):
        """Should generate basic node IDs."""
        mock_session_state.builder_nodes = []
        node_id = _generate_node_id("claude_code")
        assert node_id == "claude-code-1"

    def test_generate_node_id_increments(self, mock_session_state):
        """Should increment IDs when nodes exist."""
        mock_session_state.builder_nodes = [
            {"id": "claude-code-1"},
            {"id": "claude-code-2"},
        ]
        node_id = _generate_node_id("claude_code")
        assert node_id == "claude-code-3"

    def test_generate_node_id_different_types(self, mock_session_state):
        """Different node types should have separate counters."""
        mock_session_state.builder_nodes = [
            {"id": "claude-code-1"},
        ]
        node_id = _generate_node_id("shell")
        assert node_id == "shell-1"


class TestYamlConversion:
    """Test YAML to/from state conversion."""

    def test_build_yaml_from_empty_state(self, mock_session_state):
        """Should build valid YAML from empty state."""
        mock_session_state.builder_nodes = []
        mock_session_state.builder_edges = []
        mock_session_state.builder_metadata = {
            "name": "Test Workflow",
            "version": "1.0",
            "description": "A test workflow",
            "token_budget": 100000,
            "timeout_seconds": 3600,
        }
        mock_session_state.builder_inputs = {}
        mock_session_state.builder_outputs = []

        result = _build_yaml_from_state()

        assert result["name"] == "Test Workflow"
        assert result["version"] == "1.0"
        assert result["steps"] == []

    def test_build_yaml_with_nodes(self, mock_session_state):
        """Should build YAML with nodes and connections."""
        mock_session_state.builder_nodes = [
            {
                "id": "plan",
                "type": "claude_code",
                "position": {"x": 100, "y": 100},
                "data": {
                    "params": {"role": "planner", "prompt": "Create a plan"},
                    "on_failure": "abort",
                    "max_retries": 3,
                    "timeout_seconds": 300,
                    "outputs": ["plan"],
                    "depends_on": [],
                    "condition": None,
                },
            },
            {
                "id": "build",
                "type": "claude_code",
                "position": {"x": 100, "y": 280},
                "data": {
                    "params": {"role": "builder", "prompt": "Build the feature"},
                    "on_failure": "retry",
                    "max_retries": 2,
                    "timeout_seconds": 600,
                    "outputs": ["code"],
                    "depends_on": ["plan"],
                    "condition": None,
                },
            },
        ]
        mock_session_state.builder_edges = [
            {
                "id": "edge-plan-build",
                "source": "plan",
                "target": "build",
                "label": None,
            }
        ]
        mock_session_state.builder_metadata = {
            "name": "Feature Build",
            "version": "1.0",
            "description": "Build a feature",
            "token_budget": 50000,
            "timeout_seconds": 1800,
        }
        mock_session_state.builder_inputs = {
            "feature_request": {"type": "string", "required": True}
        }
        mock_session_state.builder_outputs = ["plan", "code"]

        result = _build_yaml_from_state()

        assert result["name"] == "Feature Build"
        assert len(result["steps"]) == 2
        assert result["steps"][0]["id"] == "plan"
        assert result["steps"][0]["params"]["role"] == "planner"
        assert result["steps"][1]["id"] == "build"
        assert result["steps"][1]["depends_on"] == "plan"  # Single dep is string
        assert result["steps"][1]["on_failure"] == "retry"
        assert result["steps"][1]["max_retries"] == 2
        assert result["inputs"] == {
            "feature_request": {"type": "string", "required": True}
        }
        assert result["outputs"] == ["plan", "code"]

    def test_load_yaml_to_state(self, mock_session_state):
        """Should load YAML workflow into state."""
        workflow_data = {
            "name": "Loaded Workflow",
            "version": "2.0",
            "description": "A loaded workflow",
            "token_budget": 75000,
            "timeout_seconds": 2400,
            "inputs": {"input_var": {"type": "string", "required": True}},
            "outputs": ["result"],
            "steps": [
                {
                    "id": "step1",
                    "type": "claude_code",
                    "params": {"role": "builder", "prompt": "Do something"},
                    "outputs": ["output1"],
                },
                {
                    "id": "step2",
                    "type": "shell",
                    "params": {"command": "echo hello"},
                    "depends_on": "step1",
                },
            ],
        }

        _load_yaml_to_state(workflow_data)

        assert mock_session_state.builder_metadata["name"] == "Loaded Workflow"
        assert mock_session_state.builder_metadata["version"] == "2.0"
        assert len(mock_session_state.builder_nodes) == 2
        assert mock_session_state.builder_nodes[0]["id"] == "step1"
        assert mock_session_state.builder_nodes[1]["id"] == "step2"
        assert mock_session_state.builder_nodes[1]["data"]["depends_on"] == ["step1"]
        assert len(mock_session_state.builder_edges) == 1
        assert mock_session_state.builder_edges[0]["source"] == "step1"
        assert mock_session_state.builder_edges[0]["target"] == "step2"
        assert mock_session_state.builder_inputs == {
            "input_var": {"type": "string", "required": True}
        }
        assert mock_session_state.builder_outputs == ["result"]

    def test_roundtrip_conversion(self, mock_session_state):
        """YAML -> state -> YAML should preserve structure."""
        original = {
            "name": "Roundtrip Test",
            "version": "1.0",
            "description": "Testing roundtrip",
            "token_budget": 100000,
            "timeout_seconds": 3600,
            "inputs": {"req": {"type": "string", "required": True}},
            "outputs": ["final"],
            "steps": [
                {
                    "id": "first",
                    "type": "claude_code",
                    "params": {"role": "planner", "prompt": "Plan"},
                    "outputs": ["plan"],
                },
                {
                    "id": "second",
                    "type": "claude_code",
                    "params": {"role": "builder", "prompt": "Build"},
                    "depends_on": "first",
                    "outputs": ["final"],
                },
            ],
        }

        _load_yaml_to_state(original)
        result = _build_yaml_from_state()

        assert result["name"] == original["name"]
        assert result["version"] == original["version"]
        assert len(result["steps"]) == len(original["steps"])
        assert result["steps"][0]["id"] == "first"
        assert result["steps"][1]["id"] == "second"
        assert result["steps"][1]["depends_on"] == "first"


@pytest.fixture
def mock_session_state(monkeypatch):
    """Mock Streamlit session state."""

    class MockSessionState:
        def __init__(self):
            self.builder_nodes = []
            self.builder_edges = []
            self.builder_metadata = {
                "name": "New Workflow",
                "version": "1.0",
                "description": "",
                "token_budget": 100000,
                "timeout_seconds": 3600,
            }
            self.builder_inputs = {}
            self.builder_outputs = []
            self.selected_node = None

    mock_state = MockSessionState()

    # Patch streamlit session_state
    import streamlit as st

    monkeypatch.setattr(st, "session_state", mock_state)

    return mock_state
