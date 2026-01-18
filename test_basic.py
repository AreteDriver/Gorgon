"""Test basic functionality of the AI Workflow Orchestrator."""

import os

# Set up a test environment
os.environ["OPENAI_API_KEY"] = "test-key"

from test_ai.config import get_settings
from test_ai.prompts import PromptTemplateManager, PromptTemplate
from test_ai.orchestrator import WorkflowEngine, Workflow, WorkflowStep, StepType


def test_settings():
    """Test settings configuration."""
    settings = get_settings()
    assert settings.app_name == "Gorgon"
    print("✓ Settings configuration working")


def test_prompt_manager():
    """Test prompt template manager."""
    manager = PromptTemplateManager()

    # Create a test template
    template = PromptTemplate(
        id="test_template",
        name="Test Template",
        description="A test template",
        user_prompt="Test prompt with {variable}",
        variables=["variable"],
    )

    # Save and load
    assert manager.save_template(template)
    loaded = manager.load_template("test_template")
    assert loaded is not None
    assert loaded.id == "test_template"
    assert loaded.name == "Test Template"

    # Format
    formatted = loaded.format(variable="test value")
    assert formatted == "Test prompt with test value"

    # List
    templates = manager.list_templates()
    assert any(t["id"] == "test_template" for t in templates)

    # Delete
    assert manager.delete_template("test_template")

    print("✓ Prompt template manager working")


def test_workflow_definition():
    """Test workflow creation."""
    workflow = Workflow(
        id="test_workflow",
        name="Test Workflow",
        description="A test workflow",
        steps=[
            WorkflowStep(
                id="step1",
                type=StepType.TRANSFORM,
                action="format",
                params={"template": "Hello {name}"},
                next_step=None,
            )
        ],
        variables={"name": "World"},
    )

    assert workflow.id == "test_workflow"
    assert len(workflow.steps) == 1
    assert workflow.steps[0].type == StepType.TRANSFORM

    print("✓ Workflow definition working")


def test_workflow_save_load():
    """Test saving and loading workflows."""
    engine = WorkflowEngine()

    workflow = Workflow(
        id="test_save_workflow",
        name="Test Save Workflow",
        description="Test saving and loading",
        steps=[],
        variables={},
    )

    # Save
    assert engine.save_workflow(workflow)

    # Load
    loaded = engine.load_workflow("test_save_workflow")
    assert loaded is not None
    assert loaded.id == "test_save_workflow"
    assert loaded.name == "Test Save Workflow"

    # List
    workflows = engine.list_workflows()
    assert any(w["id"] == "test_save_workflow" for w in workflows)

    print("✓ Workflow save/load working")


def test_auth():
    """Test authentication."""
    from test_ai.auth import create_access_token, verify_token

    token = create_access_token("test_user")
    assert token is not None

    user_id = verify_token(token)
    assert user_id == "test_user"

    invalid_user = verify_token("invalid_token")
    assert invalid_user is None

    print("✓ Authentication working")


if __name__ == "__main__":
    print("\n🧪 Testing AI Workflow Orchestrator...\n")

    test_settings()
    test_prompt_manager()
    test_workflow_definition()
    test_workflow_save_load()
    test_auth()

    print("\n✅ All tests passed!\n")
