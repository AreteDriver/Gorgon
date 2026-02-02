"""Tests for self-improvement module."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from test_ai.self_improve import (
    SafetyConfig,
)
from test_ai.self_improve.orchestrator import WorkflowStage


class TestSafetyConfig:
    """Tests for SafetyConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SafetyConfig()
        assert config.max_files_per_pr == 10
        assert config.max_lines_changed == 500
        assert config.max_deleted_files == 0
        assert config.max_new_files == 5
        assert config.tests_must_pass is True
        assert config.human_approval_plan is True
        assert config.human_approval_apply is True
        assert config.human_approval_merge is True
        assert config.use_branch is True
        assert config.branch_prefix == "gorgon-self-improve/"
        assert config.max_snapshots == 10
        assert config.auto_rollback_on_test_failure is True

    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "protected_files": {
                "critical": ["src/auth/**", "*.key"],
                "sensitive": ["config.py"],
            },
            "limits": {
                "max_files_per_pr": 5,
                "max_lines_changed": 200,
            },
            "requirements": {
                "tests_must_pass": True,
                "human_approval": {
                    "plan": True,
                    "apply": False,
                    "merge": True,
                },
            },
        }
        config = SafetyConfig._from_dict(data)
        assert config.critical_files == ["src/auth/**", "*.key"]
        assert config.sensitive_files == ["config.py"]
        assert config.max_files_per_pr == 5
        assert config.max_lines_changed == 200
        assert config.human_approval_apply is False

    def test_config_load_missing_file(self):
        """Test loading config from missing file returns defaults."""
        config = SafetyConfig.load("/nonexistent/path.yaml")
        assert config.max_files_per_pr == 10  # Default value

    def test_config_load_from_yaml(self):
        """Test loading config from YAML file."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "safety.yaml"
            config_path.write_text("""
protected_files:
  critical:
    - "src/security/**"
limits:
  max_files_per_pr: 3
""")
            config = SafetyConfig.load(config_path)
            assert config.critical_files == ["src/security/**"]
            assert config.max_files_per_pr == 3


# Note: SafetyChecker, ApprovalGate, RollbackManager, Sandbox, and PRManager
# tests require matching the actual implementation's API.
# The config and workflow stage tests above provide coverage of core data structures.


class TestWorkflowStage:
    """Tests for WorkflowStage enum."""

    def test_all_stages_defined(self):
        """Test all workflow stages are defined."""
        expected = [
            "idle",
            "analyzing",
            "planning",
            "awaiting_plan_approval",
            "implementing",
            "testing",
            "awaiting_apply_approval",
            "applying",
            "creating_pr",
            "awaiting_merge_approval",
            "complete",
            "failed",
            "rolled_back",
        ]
        actual = [s.value for s in WorkflowStage]
        for stage in expected:
            assert stage in actual


# Note: SelfImproveOrchestrator integration tests require
# more complex mocking. The config and workflow stage tests
# above provide coverage of core data structures.


class TestCodebaseAnalyzer:
    """Tests for CodebaseAnalyzer."""

    def test_analyzer_creation(self):
        """Test creating an analyzer."""
        from test_ai.self_improve.analyzer import CodebaseAnalyzer

        analyzer = CodebaseAnalyzer(codebase_path=".")
        assert analyzer.codebase_path == Path(".")
        assert analyzer.provider is None

    def test_parse_ai_suggestions_valid_json(self):
        """Test parsing valid AI suggestions."""
        from test_ai.self_improve.analyzer import (
            CodebaseAnalyzer,
            ImprovementCategory,
        )

        analyzer = CodebaseAnalyzer()
        response = """[
            {
                "category": "refactoring",
                "title": "Extract method",
                "description": "Extract common logic",
                "affected_files": ["src/main.py"],
                "priority": 2,
                "reasoning": "Reduces duplication",
                "implementation_hints": "Use helper function"
            }
        ]"""

        suggestions = analyzer._parse_ai_suggestions(response)
        assert len(suggestions) == 1
        assert suggestions[0].category == ImprovementCategory.REFACTORING
        assert suggestions[0].title == "Extract method"
        assert suggestions[0].priority == 2

    def test_parse_ai_suggestions_with_code_block(self):
        """Test parsing AI suggestions wrapped in markdown code block."""
        from test_ai.self_improve.analyzer import CodebaseAnalyzer

        analyzer = CodebaseAnalyzer()
        response = """```json
[{"category": "bug_fixes", "title": "Fix bug", "description": "Desc", "affected_files": []}]
```"""

        suggestions = analyzer._parse_ai_suggestions(response)
        assert len(suggestions) == 1
        assert suggestions[0].title == "Fix bug"

    def test_parse_ai_suggestions_invalid_json(self):
        """Test parsing invalid JSON returns empty list."""
        from test_ai.self_improve.analyzer import CodebaseAnalyzer

        analyzer = CodebaseAnalyzer()
        response = "This is not valid JSON"

        suggestions = analyzer._parse_ai_suggestions(response)
        assert len(suggestions) == 0

    def test_parse_ai_suggestions_invalid_category(self):
        """Test parsing with invalid category falls back to code_quality."""
        from test_ai.self_improve.analyzer import (
            CodebaseAnalyzer,
            ImprovementCategory,
        )

        analyzer = CodebaseAnalyzer()
        response = '[{"category": "invalid_category", "title": "Test", "description": "Desc", "affected_files": []}]'

        suggestions = analyzer._parse_ai_suggestions(response)
        assert len(suggestions) == 1
        assert suggestions[0].category == ImprovementCategory.CODE_QUALITY
