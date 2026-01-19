"""Tests for workflow orchestration engine."""

import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from test_ai.orchestrator.workflow_engine import (
    StepType,
    WorkflowStep,
    Workflow,
    WorkflowResult,
    WorkflowEngine,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directories for workflows and logs."""
    workflows_dir = tmp_path / "workflows"
    logs_dir = tmp_path / "logs"
    workflows_dir.mkdir()
    logs_dir.mkdir()
    return {"workflows_dir": workflows_dir, "logs_dir": logs_dir}


@pytest.fixture
def mock_settings(temp_dirs):
    """Create mock settings."""
    settings = MagicMock()
    settings.workflows_dir = temp_dirs["workflows_dir"]
    settings.logs_dir = temp_dirs["logs_dir"]
    return settings


@pytest.fixture
def workflow_engine(mock_settings):
    """Create workflow engine with mocked clients."""
    with patch(
        "test_ai.orchestrator.workflow_engine.get_settings"
    ) as mock_get_settings:
        mock_get_settings.return_value = mock_settings
        with patch("test_ai.orchestrator.workflow_engine.OpenAIClient"):
            with patch("test_ai.orchestrator.workflow_engine.GitHubClient"):
                with patch("test_ai.orchestrator.workflow_engine.NotionClientWrapper"):
                    with patch("test_ai.orchestrator.workflow_engine.GmailClient"):
                        with patch(
                            "test_ai.orchestrator.workflow_engine.ClaudeCodeClient"
                        ):
                            engine = WorkflowEngine()
                            yield engine


@pytest.fixture
def simple_workflow():
    """Create a simple workflow."""
    return Workflow(
        id="test-workflow",
        name="Test Workflow",
        description="A test workflow",
        steps=[
            WorkflowStep(
                id="step1",
                type=StepType.TRANSFORM,
                action="format",
                params={"template": "Hello, {name}!"},
                next_step="step2",
            ),
            WorkflowStep(
                id="step2",
                type=StepType.TRANSFORM,
                action="extract",
                params={"source": "data", "key": "value"},
            ),
        ],
        variables={"name": "World", "data": {"value": 42}},
    )


# =============================================================================
# Test StepType Enum
# =============================================================================


class TestStepType:
    """Tests for StepType enum."""

    def test_openai_value(self):
        """Test OPENAI type value."""
        assert StepType.OPENAI.value == "openai"

    def test_github_value(self):
        """Test GITHUB type value."""
        assert StepType.GITHUB.value == "github"

    def test_notion_value(self):
        """Test NOTION type value."""
        assert StepType.NOTION.value == "notion"

    def test_gmail_value(self):
        """Test GMAIL type value."""
        assert StepType.GMAIL.value == "gmail"

    def test_transform_value(self):
        """Test TRANSFORM type value."""
        assert StepType.TRANSFORM.value == "transform"

    def test_claude_code_value(self):
        """Test CLAUDE_CODE type value."""
        assert StepType.CLAUDE_CODE.value == "claude_code"

    def test_from_string(self):
        """Test creating from string value."""
        assert StepType("openai") == StepType.OPENAI
        assert StepType("github") == StepType.GITHUB


# =============================================================================
# Test WorkflowStep Model
# =============================================================================


class TestWorkflowStep:
    """Tests for WorkflowStep model."""

    def test_create_step(self):
        """Test creating a workflow step."""
        step = WorkflowStep(
            id="test-step",
            type=StepType.OPENAI,
            action="generate_completion",
        )
        assert step.id == "test-step"
        assert step.type == StepType.OPENAI
        assert step.action == "generate_completion"

    def test_step_with_params(self):
        """Test step with parameters."""
        step = WorkflowStep(
            id="test",
            type=StepType.OPENAI,
            action="generate_completion",
            params={"prompt": "Hello", "max_tokens": 100},
        )
        assert step.params["prompt"] == "Hello"
        assert step.params["max_tokens"] == 100

    def test_step_with_next(self):
        """Test step with next_step."""
        step = WorkflowStep(
            id="step1",
            type=StepType.TRANSFORM,
            action="format",
            next_step="step2",
        )
        assert step.next_step == "step2"

    def test_default_params(self):
        """Test default params is empty dict."""
        step = WorkflowStep(
            id="test",
            type=StepType.TRANSFORM,
            action="extract",
        )
        assert step.params == {}

    def test_default_next_step(self):
        """Test default next_step is None."""
        step = WorkflowStep(
            id="test",
            type=StepType.TRANSFORM,
            action="extract",
        )
        assert step.next_step is None

    def test_step_serialization(self):
        """Test step can be serialized."""
        step = WorkflowStep(
            id="test",
            type=StepType.OPENAI,
            action="generate_completion",
            params={"prompt": "test"},
        )
        data = step.model_dump()
        assert data["id"] == "test"
        assert data["type"] == "openai"


# =============================================================================
# Test Workflow Model
# =============================================================================


class TestWorkflow:
    """Tests for Workflow model."""

    def test_create_workflow(self):
        """Test creating a workflow."""
        workflow = Workflow(
            id="test",
            name="Test Workflow",
            description="A test",
        )
        assert workflow.id == "test"
        assert workflow.name == "Test Workflow"
        assert workflow.steps == []
        assert workflow.variables == {}

    def test_workflow_with_steps(self, simple_workflow):
        """Test workflow with steps."""
        assert len(simple_workflow.steps) == 2
        assert simple_workflow.steps[0].id == "step1"
        assert simple_workflow.steps[1].id == "step2"

    def test_workflow_with_variables(self, simple_workflow):
        """Test workflow with variables."""
        assert simple_workflow.variables["name"] == "World"
        assert simple_workflow.variables["data"]["value"] == 42

    def test_workflow_serialization(self, simple_workflow):
        """Test workflow can be serialized."""
        data = simple_workflow.model_dump()
        assert data["id"] == "test-workflow"
        assert data["name"] == "Test Workflow"
        assert len(data["steps"]) == 2


# =============================================================================
# Test WorkflowResult Model
# =============================================================================


class TestWorkflowResult:
    """Tests for WorkflowResult model."""

    def test_create_result(self):
        """Test creating a workflow result."""
        result = WorkflowResult(
            workflow_id="test",
            status="running",
            started_at=datetime.now(),
        )
        assert result.workflow_id == "test"
        assert result.status == "running"
        assert result.completed_at is None

    def test_result_with_outputs(self):
        """Test result with outputs."""
        result = WorkflowResult(
            workflow_id="test",
            status="completed",
            started_at=datetime.now(),
            steps_executed=["step1", "step2"],
            outputs={"step1": "result1", "step2": "result2"},
        )
        assert len(result.steps_executed) == 2
        assert result.outputs["step1"] == "result1"

    def test_result_with_errors(self):
        """Test result with errors."""
        result = WorkflowResult(
            workflow_id="test",
            status="failed",
            started_at=datetime.now(),
            errors=["Error 1", "Error 2"],
        )
        assert result.status == "failed"
        assert len(result.errors) == 2

    def test_result_serialization(self):
        """Test result can be serialized."""
        result = WorkflowResult(
            workflow_id="test",
            status="completed",
            started_at=datetime.now(),
            completed_at=datetime.now(),
        )
        data = result.model_dump(mode="json")
        assert data["workflow_id"] == "test"
        assert "started_at" in data


# =============================================================================
# Test WorkflowEngine Initialization
# =============================================================================


class TestWorkflowEngineInit:
    """Tests for WorkflowEngine initialization."""

    def test_engine_init(self, workflow_engine):
        """Test engine initializes correctly."""
        assert workflow_engine is not None
        assert workflow_engine.settings is not None

    def test_engine_has_clients(self, workflow_engine):
        """Test engine has API clients."""
        assert workflow_engine.openai_client is not None
        assert workflow_engine.github_client is not None
        assert workflow_engine.notion_client is not None
        assert workflow_engine.gmail_client is not None
        assert workflow_engine.claude_code_client is not None


# =============================================================================
# Test Workflow Execution
# =============================================================================


class TestWorkflowExecution:
    """Tests for workflow execution."""

    def test_execute_empty_workflow(self, workflow_engine):
        """Test executing empty workflow."""
        workflow = Workflow(
            id="empty",
            name="Empty",
            description="Empty workflow",
        )
        result = workflow_engine.execute_workflow(workflow)
        assert result.status == "completed"
        assert len(result.steps_executed) == 0

    def test_execute_transform_workflow(self, workflow_engine, simple_workflow):
        """Test executing workflow with transform steps."""
        result = workflow_engine.execute_workflow(simple_workflow)
        assert result.status == "completed"
        assert "step1" in result.steps_executed
        assert "step2" in result.steps_executed

    def test_execute_stores_outputs(self, workflow_engine, simple_workflow):
        """Test execution stores step outputs."""
        result = workflow_engine.execute_workflow(simple_workflow)
        assert "step1" in result.outputs
        assert result.outputs["step1"] == "Hello, World!"

    def test_execute_handles_errors(self, workflow_engine):
        """Test execution handles step errors."""
        workflow = Workflow(
            id="error-test",
            name="Error Test",
            description="Test error handling",
            steps=[
                WorkflowStep(
                    id="bad-step",
                    type=StepType.TRANSFORM,
                    action="unknown_action",
                )
            ],
        )
        result = workflow_engine.execute_workflow(workflow)
        assert result.status == "failed"
        assert len(result.errors) > 0

    def test_execute_follows_next_step(self, workflow_engine):
        """Test execution follows next_step chain."""
        workflow = Workflow(
            id="chain",
            name="Chain",
            description="Test step chaining",
            steps=[
                WorkflowStep(
                    id="step1",
                    type=StepType.TRANSFORM,
                    action="format",
                    params={"template": "First"},
                    next_step="step3",  # Skip step2
                ),
                WorkflowStep(
                    id="step2",
                    type=StepType.TRANSFORM,
                    action="format",
                    params={"template": "Second"},
                ),
                WorkflowStep(
                    id="step3",
                    type=StepType.TRANSFORM,
                    action="format",
                    params={"template": "Third"},
                ),
            ],
        )
        result = workflow_engine.execute_workflow(workflow)
        assert "step1" in result.steps_executed
        assert "step2" not in result.steps_executed  # Skipped
        assert "step3" in result.steps_executed

    def test_execute_saves_log(self, workflow_engine, simple_workflow, mock_settings):
        """Test execution saves log file."""
        workflow_engine.execute_workflow(simple_workflow)
        log_files = list(mock_settings.logs_dir.glob("*.json"))
        assert len(log_files) == 1


# =============================================================================
# Test Step Execution
# =============================================================================


class TestStepExecution:
    """Tests for individual step execution."""

    def test_execute_openai_generate(self, workflow_engine):
        """Test OpenAI generate_completion step."""
        workflow_engine.openai_client.generate_completion.return_value = (
            "Generated text"
        )
        step = WorkflowStep(
            id="test",
            type=StepType.OPENAI,
            action="generate_completion",
            params={"prompt": "Hello"},
        )
        result = workflow_engine._execute_step(step, {})
        assert result == "Generated text"

    def test_execute_openai_summarize(self, workflow_engine):
        """Test OpenAI summarize step."""
        workflow_engine.openai_client.summarize_text.return_value = "Summary"
        step = WorkflowStep(
            id="test",
            type=StepType.OPENAI,
            action="summarize",
            params={"text": "Long text..."},
        )
        result = workflow_engine._execute_step(step, {})
        assert result == "Summary"

    def test_execute_openai_sop(self, workflow_engine):
        """Test OpenAI generate_sop step."""
        workflow_engine.openai_client.generate_sop.return_value = "SOP document"
        step = WorkflowStep(
            id="test",
            type=StepType.OPENAI,
            action="generate_sop",
            params={"task_description": "Task"},
        )
        result = workflow_engine._execute_step(step, {})
        assert result == "SOP document"

    def test_execute_openai_unknown_action(self, workflow_engine):
        """Test OpenAI step with unknown action raises error."""
        step = WorkflowStep(
            id="test",
            type=StepType.OPENAI,
            action="unknown_action",
        )
        with pytest.raises(ValueError, match="Unknown OpenAI action"):
            workflow_engine._execute_step(step, {})

    def test_execute_github_create_issue(self, workflow_engine):
        """Test GitHub create_issue step."""
        workflow_engine.github_client.create_issue.return_value = {"number": 123}
        step = WorkflowStep(
            id="test",
            type=StepType.GITHUB,
            action="create_issue",
            params={"repo": "test/repo", "title": "Test"},
        )
        result = workflow_engine._execute_step(step, {})
        assert result["number"] == 123

    def test_execute_github_commit_file(self, workflow_engine):
        """Test GitHub commit_file step."""
        workflow_engine.github_client.commit_file.return_value = {"sha": "abc123"}
        step = WorkflowStep(
            id="test",
            type=StepType.GITHUB,
            action="commit_file",
            params={"repo": "test/repo", "path": "test.txt"},
        )
        result = workflow_engine._execute_step(step, {})
        assert result["sha"] == "abc123"

    def test_execute_github_list_repos(self, workflow_engine):
        """Test GitHub list_repositories step."""
        workflow_engine.github_client.list_repositories.return_value = [
            {"name": "repo1"}
        ]
        step = WorkflowStep(
            id="test",
            type=StepType.GITHUB,
            action="list_repositories",
        )
        result = workflow_engine._execute_step(step, {})
        assert len(result) == 1

    def test_execute_github_unknown_action(self, workflow_engine):
        """Test GitHub step with unknown action raises error."""
        step = WorkflowStep(
            id="test",
            type=StepType.GITHUB,
            action="unknown_action",
        )
        with pytest.raises(ValueError, match="Unknown GitHub action"):
            workflow_engine._execute_step(step, {})

    def test_execute_notion_create_page(self, workflow_engine):
        """Test Notion create_page step."""
        workflow_engine.notion_client.create_page.return_value = {"id": "page-123"}
        step = WorkflowStep(
            id="test",
            type=StepType.NOTION,
            action="create_page",
            params={"parent_id": "parent", "title": "Test"},
        )
        result = workflow_engine._execute_step(step, {})
        assert result["id"] == "page-123"

    def test_execute_notion_append(self, workflow_engine):
        """Test Notion append_to_page step."""
        workflow_engine.notion_client.append_to_page.return_value = True
        step = WorkflowStep(
            id="test",
            type=StepType.NOTION,
            action="append_to_page",
            params={"page_id": "page-123", "content": "New content"},
        )
        result = workflow_engine._execute_step(step, {})
        assert result is True

    def test_execute_notion_search(self, workflow_engine):
        """Test Notion search_pages step."""
        workflow_engine.notion_client.search_pages.return_value = [{"id": "page-1"}]
        step = WorkflowStep(
            id="test",
            type=StepType.NOTION,
            action="search_pages",
            params={"query": "test"},
        )
        result = workflow_engine._execute_step(step, {})
        assert len(result) == 1

    def test_execute_notion_unknown_action(self, workflow_engine):
        """Test Notion step with unknown action raises error."""
        step = WorkflowStep(
            id="test",
            type=StepType.NOTION,
            action="unknown_action",
        )
        with pytest.raises(ValueError, match="Unknown Notion action"):
            workflow_engine._execute_step(step, {})

    def test_execute_gmail_list_messages(self, workflow_engine):
        """Test Gmail list_messages step."""
        workflow_engine.gmail_client.list_messages.return_value = [{"id": "msg-1"}]
        step = WorkflowStep(
            id="test",
            type=StepType.GMAIL,
            action="list_messages",
            params={"query": "is:unread"},
        )
        result = workflow_engine._execute_step(step, {})
        assert len(result) == 1

    def test_execute_gmail_get_message(self, workflow_engine):
        """Test Gmail get_message step."""
        workflow_engine.gmail_client.get_message.return_value = {
            "id": "msg-1",
            "body": "content",
        }
        step = WorkflowStep(
            id="test",
            type=StepType.GMAIL,
            action="get_message",
            params={"message_id": "msg-1"},
        )
        result = workflow_engine._execute_step(step, {})
        assert result["id"] == "msg-1"

    def test_execute_gmail_unknown_action(self, workflow_engine):
        """Test Gmail step with unknown action raises error."""
        step = WorkflowStep(
            id="test",
            type=StepType.GMAIL,
            action="unknown_action",
        )
        with pytest.raises(ValueError, match="Unknown Gmail action"):
            workflow_engine._execute_step(step, {})

    def test_execute_claude_code_agent(self, workflow_engine):
        """Test Claude Code execute_agent step."""
        workflow_engine.claude_code_client.execute_agent.return_value = {
            "response": "Done"
        }
        step = WorkflowStep(
            id="test",
            type=StepType.CLAUDE_CODE,
            action="execute_agent",
            params={"role": "builder", "prompt": "Build something"},
        )
        result = workflow_engine._execute_step(step, {})
        assert result["response"] == "Done"

    def test_execute_claude_code_completion(self, workflow_engine):
        """Test Claude Code generate_completion step."""
        workflow_engine.claude_code_client.generate_completion.return_value = (
            "Generated"
        )
        step = WorkflowStep(
            id="test",
            type=StepType.CLAUDE_CODE,
            action="generate_completion",
            params={"prompt": "Hello"},
        )
        result = workflow_engine._execute_step(step, {})
        assert result == "Generated"

    def test_execute_claude_code_cli(self, workflow_engine):
        """Test Claude Code execute_cli step."""
        workflow_engine.claude_code_client.execute_cli_command.return_value = (
            "CLI output"
        )
        step = WorkflowStep(
            id="test",
            type=StepType.CLAUDE_CODE,
            action="execute_cli",
            params={"command": "test command"},
        )
        result = workflow_engine._execute_step(step, {})
        assert result == "CLI output"

    def test_execute_claude_code_unknown_action(self, workflow_engine):
        """Test Claude Code step with unknown action raises error."""
        step = WorkflowStep(
            id="test",
            type=StepType.CLAUDE_CODE,
            action="unknown_action",
        )
        with pytest.raises(ValueError, match="Unknown Claude Code action"):
            workflow_engine._execute_step(step, {})


# =============================================================================
# Test Transform Steps
# =============================================================================


class TestTransformSteps:
    """Tests for transform step execution."""

    def test_transform_extract(self, workflow_engine):
        """Test transform extract action."""
        step = WorkflowStep(
            id="test",
            type=StepType.TRANSFORM,
            action="extract",
            params={"source": "data", "key": "name"},
        )
        context = {"data": {"name": "John", "age": 30}}
        result = workflow_engine._execute_step(step, context)
        assert result == "John"

    def test_transform_extract_missing_key(self, workflow_engine):
        """Test transform extract with missing key."""
        step = WorkflowStep(
            id="test",
            type=StepType.TRANSFORM,
            action="extract",
            params={"source": "data", "key": "missing"},
        )
        context = {"data": {"name": "John"}}
        result = workflow_engine._execute_step(step, context)
        assert result == ""

    def test_transform_extract_missing_source(self, workflow_engine):
        """Test transform extract with missing source."""
        step = WorkflowStep(
            id="test",
            type=StepType.TRANSFORM,
            action="extract",
            params={"source": "missing", "key": "name"},
        )
        result = workflow_engine._execute_step(step, {})
        assert result == ""

    def test_transform_format(self, workflow_engine):
        """Test transform format action."""
        step = WorkflowStep(
            id="test",
            type=StepType.TRANSFORM,
            action="format",
            params={"template": "Hello, {name}! You are {age} years old."},
        )
        context = {"name": "John", "age": 30}
        result = workflow_engine._execute_step(step, context)
        assert result == "Hello, John! You are 30 years old."

    def test_transform_unknown_action(self, workflow_engine):
        """Test transform with unknown action raises error."""
        step = WorkflowStep(
            id="test",
            type=StepType.TRANSFORM,
            action="unknown_action",
        )
        with pytest.raises(ValueError, match="Unknown transform action"):
            workflow_engine._execute_step(step, {})


# =============================================================================
# Test Parameter Interpolation
# =============================================================================


class TestParameterInterpolation:
    """Tests for parameter interpolation."""

    def test_interpolate_simple(self, workflow_engine):
        """Test simple variable interpolation."""
        params = {"message": "{{greeting}}"}
        context = {"greeting": "Hello"}
        result = workflow_engine._interpolate_params(params, context)
        assert result["message"] == "Hello"

    def test_interpolate_preserves_non_variables(self, workflow_engine):
        """Test interpolation preserves non-variable values."""
        params = {"message": "Hello", "count": 5}
        result = workflow_engine._interpolate_params(params, {})
        assert result["message"] == "Hello"
        assert result["count"] == 5

    def test_interpolate_missing_variable(self, workflow_engine):
        """Test interpolation with missing variable keeps original."""
        params = {"message": "{{missing}}"}
        result = workflow_engine._interpolate_params(params, {})
        assert result["message"] == "{{missing}}"

    def test_interpolate_with_spaces(self, workflow_engine):
        """Test interpolation with spaces around variable name."""
        params = {"message": "{{ greeting }}"}
        context = {"greeting": "Hello"}
        result = workflow_engine._interpolate_params(params, context)
        assert result["message"] == "Hello"

    def test_interpolate_multiple_params(self, workflow_engine):
        """Test interpolation with multiple parameters."""
        params = {
            "first": "{{a}}",
            "second": "{{b}}",
            "third": "static",
        }
        context = {"a": "A", "b": "B"}
        result = workflow_engine._interpolate_params(params, context)
        assert result["first"] == "A"
        assert result["second"] == "B"
        assert result["third"] == "static"


# =============================================================================
# Test Workflow Persistence
# =============================================================================


class TestWorkflowPersistence:
    """Tests for workflow save/load/list operations."""

    def test_save_workflow(self, workflow_engine, simple_workflow, mock_settings):
        """Test saving a workflow."""
        result = workflow_engine.save_workflow(simple_workflow)
        assert result is True
        file_path = mock_settings.workflows_dir / f"{simple_workflow.id}.json"
        assert file_path.exists()

    def test_save_workflow_creates_valid_json(
        self, workflow_engine, simple_workflow, mock_settings
    ):
        """Test saved workflow is valid JSON."""
        workflow_engine.save_workflow(simple_workflow)
        file_path = mock_settings.workflows_dir / f"{simple_workflow.id}.json"
        with open(file_path) as f:
            data = json.load(f)
        assert data["id"] == "test-workflow"
        assert len(data["steps"]) == 2

    def test_load_workflow(self, workflow_engine, simple_workflow, mock_settings):
        """Test loading a workflow."""
        workflow_engine.save_workflow(simple_workflow)
        loaded = workflow_engine.load_workflow(simple_workflow.id)
        assert loaded is not None
        assert loaded.id == simple_workflow.id
        assert len(loaded.steps) == 2

    def test_load_nonexistent_workflow(self, workflow_engine):
        """Test loading nonexistent workflow returns None."""
        result = workflow_engine.load_workflow("nonexistent")
        assert result is None

    def test_list_workflows_empty(self, workflow_engine):
        """Test listing workflows when none exist."""
        result = workflow_engine.list_workflows()
        assert result == []

    def test_list_workflows(self, workflow_engine, mock_settings):
        """Test listing workflows."""
        # Save some workflows
        for i in range(3):
            workflow = Workflow(
                id=f"workflow-{i}",
                name=f"Workflow {i}",
                description=f"Description {i}",
            )
            workflow_engine.save_workflow(workflow)

        result = workflow_engine.list_workflows()
        assert len(result) == 3
        ids = [w["id"] for w in result]
        assert "workflow-0" in ids
        assert "workflow-1" in ids
        assert "workflow-2" in ids

    def test_list_workflows_handles_invalid_files(self, workflow_engine, mock_settings):
        """Test list_workflows handles invalid JSON files."""
        # Create valid workflow
        workflow = Workflow(id="valid", name="Valid", description="Valid workflow")
        workflow_engine.save_workflow(workflow)

        # Create invalid JSON file
        invalid_path = mock_settings.workflows_dir / "invalid.json"
        with open(invalid_path, "w") as f:
            f.write("not valid json")

        result = workflow_engine.list_workflows()
        assert len(result) == 1
        assert result[0]["id"] == "valid"


# =============================================================================
# Test Unknown Step Type
# =============================================================================


class TestUnknownStepType:
    """Tests for handling unknown step types."""

    def test_execute_unknown_step_type(self, workflow_engine):
        """Test executing step with unknown type raises error."""
        # Create a step with a mocked type that's not in the switch
        step = WorkflowStep(
            id="test",
            type=StepType.OPENAI,  # Will be changed
            action="test",
        )
        # Manually change the type to simulate an unknown type
        step.type = MagicMock()
        step.type.value = "unknown"

        with pytest.raises(ValueError, match="Unknown step type"):
            workflow_engine._execute_step(step, {})
