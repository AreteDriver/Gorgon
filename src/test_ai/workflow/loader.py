"""YAML Workflow Loader and Validator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml


@dataclass
class ConditionConfig:
    """Condition for step execution."""

    field: str
    operator: Literal["equals", "not_equals", "contains", "greater_than", "less_than"]
    value: Any

    def evaluate(self, context: dict) -> bool:
        """Evaluate condition against context."""
        actual = context.get(self.field)
        if actual is None:
            return False

        if self.operator == "equals":
            return actual == self.value
        elif self.operator == "not_equals":
            return actual != self.value
        elif self.operator == "contains":
            return self.value in actual if isinstance(actual, (str, list)) else False
        elif self.operator == "greater_than":
            return actual > self.value if isinstance(actual, (int, float)) else False
        elif self.operator == "less_than":
            return actual < self.value if isinstance(actual, (int, float)) else False
        return False


@dataclass
class StepConfig:
    """Configuration for a workflow step."""

    id: str
    type: Literal["claude_code", "openai", "shell", "parallel", "checkpoint"]
    params: dict = field(default_factory=dict)
    condition: ConditionConfig | None = None
    on_failure: Literal["abort", "skip", "retry"] = "abort"
    max_retries: int = 3
    timeout_seconds: int = 300
    outputs: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> StepConfig:
        """Create StepConfig from dictionary."""
        condition = None
        if "condition" in data:
            cond_data = data["condition"]
            condition = ConditionConfig(
                field=cond_data["field"],
                operator=cond_data["operator"],
                value=cond_data["value"],
            )

        # Parse depends_on - supports string or list
        depends_on = data.get("depends_on", [])
        if isinstance(depends_on, str):
            depends_on = [depends_on]

        return cls(
            id=data["id"],
            type=data["type"],
            params=data.get("params", {}),
            condition=condition,
            on_failure=data.get("on_failure", "abort"),
            max_retries=data.get("max_retries", 3),
            timeout_seconds=data.get("timeout_seconds", 300),
            outputs=data.get("outputs", []),
            depends_on=depends_on,
        )


@dataclass
class WorkflowConfig:
    """Configuration for a complete workflow."""

    name: str
    version: str
    description: str
    steps: list[StepConfig]
    inputs: dict = field(default_factory=dict)
    outputs: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    token_budget: int = 100000
    timeout_seconds: int = 3600

    @classmethod
    def from_dict(cls, data: dict) -> WorkflowConfig:
        """Create WorkflowConfig from dictionary."""
        steps = [StepConfig.from_dict(s) for s in data.get("steps", [])]

        return cls(
            name=data["name"],
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
            steps=steps,
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs", []),
            metadata=data.get("metadata", {}),
            token_budget=data.get("token_budget", 100000),
            timeout_seconds=data.get("timeout_seconds", 3600),
        )

    def get_step(self, step_id: str) -> StepConfig | None:
        """Get step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None


# YAML workflow schema for validation
WORKFLOW_SCHEMA = {
    "type": "object",
    "required": ["name", "steps"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "version": {"type": "string"},
        "description": {"type": "string"},
        "token_budget": {"type": "integer", "minimum": 1000},
        "timeout_seconds": {"type": "integer", "minimum": 60},
        "inputs": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "required": {"type": "boolean"},
                    "default": {},
                    "description": {"type": "string"},
                },
            },
        },
        "outputs": {
            "type": "array",
            "items": {"type": "string"},
        },
        "steps": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "type"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "type": {
                        "type": "string",
                        "enum": [
                            "claude_code",
                            "openai",
                            "shell",
                            "parallel",
                            "checkpoint",
                        ],
                    },
                    "params": {"type": "object"},
                    "condition": {
                        "type": "object",
                        "required": ["field", "operator", "value"],
                        "properties": {
                            "field": {"type": "string"},
                            "operator": {
                                "type": "string",
                                "enum": [
                                    "equals",
                                    "not_equals",
                                    "contains",
                                    "greater_than",
                                    "less_than",
                                ],
                            },
                            "value": {},
                        },
                    },
                    "on_failure": {
                        "type": "string",
                        "enum": ["abort", "skip", "retry"],
                    },
                    "max_retries": {"type": "integer", "minimum": 0},
                    "timeout_seconds": {"type": "integer", "minimum": 1},
                    "outputs": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "depends_on": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ]
                    },
                },
            },
        },
        "metadata": {"type": "object"},
    },
}


def load_workflow(path: str | Path) -> WorkflowConfig:
    """Load workflow from YAML file.

    Args:
        path: Path to YAML workflow file

    Returns:
        WorkflowConfig object

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If YAML is invalid or schema validation fails
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Workflow file not found: {path}")

    with open(path) as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {path}: {e}")

    if not isinstance(data, dict):
        raise ValueError(f"Workflow file must contain a YAML mapping: {path}")

    # Validate schema
    errors = validate_workflow(data)
    if errors:
        raise ValueError(f"Workflow validation failed: {'; '.join(errors)}")

    return WorkflowConfig.from_dict(data)


def validate_workflow(data: dict) -> list[str]:
    """Validate workflow data against schema.

    Args:
        data: Workflow dictionary

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Required fields
    if "name" not in data:
        errors.append("Missing required field: name")
    elif not isinstance(data["name"], str) or not data["name"].strip():
        errors.append("Field 'name' must be a non-empty string")

    if "steps" not in data:
        errors.append("Missing required field: steps")
    elif not isinstance(data["steps"], list):
        errors.append("Field 'steps' must be a list")
    elif len(data["steps"]) == 0:
        errors.append("Workflow must have at least one step")
    else:
        step_ids = set()
        for i, step in enumerate(data["steps"]):
            step_errors = _validate_step(step, i)
            errors.extend(step_errors)

            # Check for duplicate IDs
            step_id = step.get("id")
            if step_id in step_ids:
                errors.append(f"Duplicate step ID: {step_id}")
            elif step_id:
                step_ids.add(step_id)

    # Validate inputs schema
    if "inputs" in data and not isinstance(data["inputs"], dict):
        errors.append("Field 'inputs' must be an object")

    # Validate outputs
    if "outputs" in data:
        if not isinstance(data["outputs"], list):
            errors.append("Field 'outputs' must be a list")
        elif not all(isinstance(o, str) for o in data["outputs"]):
            errors.append("All output names must be strings")

    # Validate budget and timeout
    if "token_budget" in data:
        if not isinstance(data["token_budget"], int) or data["token_budget"] < 1000:
            errors.append("token_budget must be an integer >= 1000")

    if "timeout_seconds" in data:
        if not isinstance(data["timeout_seconds"], int) or data["timeout_seconds"] < 60:
            errors.append("timeout_seconds must be an integer >= 60")

    return errors


def _validate_step(step: dict, index: int) -> list[str]:
    """Validate a single workflow step."""
    errors = []
    prefix = f"Step {index + 1}"

    if not isinstance(step, dict):
        return [f"{prefix}: must be an object"]

    # Required fields
    if "id" not in step:
        errors.append(f"{prefix}: missing required field 'id'")
    elif not isinstance(step["id"], str) or not step["id"].strip():
        errors.append(f"{prefix}: 'id' must be a non-empty string")
    else:
        prefix = f"Step '{step['id']}'"

    if "type" not in step:
        errors.append(f"{prefix}: missing required field 'type'")
    elif step["type"] not in (
        "claude_code",
        "openai",
        "shell",
        "parallel",
        "checkpoint",
    ):
        errors.append(f"{prefix}: invalid type '{step['type']}'")

    # Validate condition if present
    if "condition" in step:
        cond = step["condition"]
        if not isinstance(cond, dict):
            errors.append(f"{prefix}: condition must be an object")
        else:
            for req in ("field", "operator", "value"):
                if req not in cond:
                    errors.append(f"{prefix}: condition missing '{req}'")
            if "operator" in cond and cond["operator"] not in (
                "equals",
                "not_equals",
                "contains",
                "greater_than",
                "less_than",
            ):
                errors.append(
                    f"{prefix}: invalid condition operator '{cond['operator']}'"
                )

    # Validate on_failure
    if "on_failure" in step and step["on_failure"] not in ("abort", "skip", "retry"):
        errors.append(f"{prefix}: invalid on_failure value '{step['on_failure']}'")

    # Validate retries and timeout
    if "max_retries" in step:
        if not isinstance(step["max_retries"], int) or step["max_retries"] < 0:
            errors.append(f"{prefix}: max_retries must be a non-negative integer")

    if "timeout_seconds" in step:
        if not isinstance(step["timeout_seconds"], int) or step["timeout_seconds"] < 1:
            errors.append(f"{prefix}: timeout_seconds must be a positive integer")

    # Validate depends_on
    if "depends_on" in step:
        deps = step["depends_on"]
        if isinstance(deps, str):
            deps = [deps]
        if not isinstance(deps, list):
            errors.append(f"{prefix}: depends_on must be a string or list of strings")
        elif not all(isinstance(d, str) for d in deps):
            errors.append(f"{prefix}: all depends_on values must be strings")

    return errors


def list_workflows(directory: str | Path = "workflows") -> list[dict]:
    """List all workflow files in a directory.

    Args:
        directory: Directory to search for .yaml files

    Returns:
        List of workflow summaries with name, path, and description
    """
    directory = Path(directory)
    if not directory.exists():
        return []

    workflows = []
    for yaml_file in directory.glob("*.yaml"):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                workflows.append(
                    {
                        "path": str(yaml_file),
                        "name": data.get("name", yaml_file.stem),
                        "version": data.get("version", "1.0"),
                        "description": data.get("description", ""),
                    }
                )
        except Exception:
            # Skip invalid files
            pass

    return sorted(workflows, key=lambda w: w["name"])
