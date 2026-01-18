"""Tests for the contracts module."""

import pytest
import sys
sys.path.insert(0, 'src')

from test_ai.contracts import (
    AgentContract,
    AgentRole,
    ContractViolation,
    get_contract,
    PLANNER_CONTRACT,
    BUILDER_CONTRACT,
    TESTER_CONTRACT,
    REVIEWER_CONTRACT,
)
from test_ai.contracts.validator import ContractValidator, ValidationResult
from test_ai.contracts.definitions import list_contracts


class TestAgentRole:
    """Tests for AgentRole enum."""

    def test_roles_exist(self):
        """All expected roles are defined."""
        assert AgentRole.PLANNER.value == "planner"
        assert AgentRole.BUILDER.value == "builder"
        assert AgentRole.TESTER.value == "tester"
        assert AgentRole.REVIEWER.value == "reviewer"

    def test_role_from_string(self):
        """Can create role from string value."""
        assert AgentRole("planner") == AgentRole.PLANNER


class TestAgentContract:
    """Tests for AgentContract class."""

    def test_create_contract(self):
        """Can create a contract with schema."""
        contract = AgentContract(
            role=AgentRole.PLANNER,
            input_schema={
                "type": "object",
                "required": ["task"],
                "properties": {"task": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "required": ["plan"],
                "properties": {"plan": {"type": "string"}},
            },
            description="Test contract",
        )
        assert contract.role == AgentRole.PLANNER
        assert "task" in contract.input_schema["required"]

    def test_validate_input_success(self):
        """Valid input passes validation."""
        contract = get_contract(AgentRole.PLANNER)
        # PLANNER requires 'request' and 'context' fields
        valid_input = {"request": "Build a REST API", "context": {}}
        assert contract.validate_input(valid_input) is True

    def test_validate_input_failure(self):
        """Invalid input raises ContractViolation."""
        contract = get_contract(AgentRole.PLANNER)
        invalid_input = {}  # Missing required fields
        with pytest.raises(ContractViolation):
            contract.validate_input(invalid_input)

    def test_validate_output_success(self):
        """Valid output passes validation."""
        contract = get_contract(AgentRole.PLANNER)
        valid_output = {
            "tasks": [{"id": "1", "description": "Step 1", "dependencies": []}],
            "architecture": "Simple architecture",
            "success_criteria": ["Tests pass"],
        }
        assert contract.validate_output(valid_output) is True

    def test_validate_output_failure(self):
        """Invalid output raises ContractViolation."""
        contract = get_contract(AgentRole.PLANNER)
        invalid_output = {"wrong": "data"}
        with pytest.raises(ContractViolation):
            contract.validate_output(invalid_output)

    def test_check_context(self):
        """Context checking identifies missing fields."""
        contract = AgentContract(
            role=AgentRole.BUILDER,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            required_context=["plan", "requirements"],
        )
        missing = contract.check_context({"plan": "..."})
        assert "requirements" in missing
        assert "plan" not in missing


class TestGetContract:
    """Tests for get_contract function."""

    def test_get_by_enum(self):
        """Can get contract by AgentRole enum."""
        contract = get_contract(AgentRole.BUILDER)
        assert contract.role == AgentRole.BUILDER

    def test_get_by_string(self):
        """Can get contract by string name."""
        contract = get_contract("tester")
        assert contract.role == AgentRole.TESTER

    def test_unknown_role_raises(self):
        """Unknown role raises ValueError."""
        with pytest.raises(ValueError):
            get_contract("unknown_role")

    def test_core_roles_have_contracts(self):
        """Core AgentRole values have contracts defined."""
        core_roles = [AgentRole.PLANNER, AgentRole.BUILDER, AgentRole.TESTER, AgentRole.REVIEWER]
        for role in core_roles:
            contract = get_contract(role)
            assert contract is not None


class TestContractValidator:
    """Tests for ContractValidator class."""

    def test_validate_input_strict(self):
        """Strict mode raises on validation failure."""
        validator = ContractValidator(strict=True)
        with pytest.raises(ContractViolation):
            validator.validate_input("planner", {})

    def test_validate_input_non_strict(self):
        """Non-strict mode returns ValidationResult."""
        validator = ContractValidator(strict=False)
        result = validator.validate_input("planner", {})
        assert isinstance(result, ValidationResult)
        assert result.valid is False
        assert len(result.errors) > 0

    def test_validate_output(self):
        """Output validation works."""
        validator = ContractValidator(strict=False)
        result = validator.validate_output("builder", {
            "code": "print('hello')",
            "files_created": ["main.py"],
            "status": "complete",
        })
        assert result.valid is True

    def test_validate_handoff(self):
        """Handoff validation checks both sides."""
        validator = ContractValidator(strict=False)
        data = {
            "tasks": [{"id": "1", "description": "Task 1", "dependencies": []}],
            "architecture": "Simple architecture",
            "success_criteria": ["Tests pass"],
        }
        output_result, input_result = validator.validate_handoff(
            "planner", "builder", data
        )
        assert output_result.valid is True
        # Builder input might have different requirements
        assert isinstance(input_result, ValidationResult)

    def test_validation_history(self):
        """Validator tracks validation history."""
        validator = ContractValidator(strict=False)
        validator.validate_input("planner", {"request": "test", "context": {}})
        validator.validate_output("planner", {
            "tasks": [{"id": "1", "description": "Task", "dependencies": []}],
            "architecture": "Simple",
            "success_criteria": ["Pass"],
        })
        history = validator.get_history()
        assert len(history) == 2

    def test_validation_stats(self):
        """Validator provides statistics."""
        validator = ContractValidator(strict=False)
        validator.validate_input("planner", {"request": "test", "context": {}})  # Valid
        validator.validate_input("planner", {})  # Invalid
        stats = validator.get_stats()
        assert stats["total"] == 2
        assert stats["valid"] == 1
        assert stats["invalid"] == 1


class TestContractViolation:
    """Tests for ContractViolation exception."""

    def test_violation_message(self):
        """Violation includes message."""
        violation = ContractViolation("Test error", role="planner")
        assert "Test error" in str(violation)

    def test_violation_role(self):
        """Violation includes role."""
        violation = ContractViolation("Error", role="builder")
        assert violation.role == "builder"
