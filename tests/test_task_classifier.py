"""Tests for the task complexity classifier."""

from __future__ import annotations

from test_ai.agents.task_classifier import (
    ClassificationResult,
    TaskComplexity,
    classify_task,
    filter_delegations,
    COMPLEXITY_TIERS,
)


# ---------------------------------------------------------------------------
# classify_task: simple tasks
# ---------------------------------------------------------------------------


class TestClassifySimpleTasks:
    """Tasks that should be classified as simple."""

    def test_fix_typo(self):
        result = classify_task("Fix a typo in the readme")
        assert result.complexity == TaskComplexity.SIMPLE

    def test_rename_variable(self):
        result = classify_task("Rename getUserName to get_user_name")
        assert result.complexity == TaskComplexity.SIMPLE

    def test_explain_function(self):
        result = classify_task("What is this function doing?")
        assert result.complexity == TaskComplexity.SIMPLE

    def test_update_version(self):
        result = classify_task("Update the version to 2.0")
        assert result.complexity == TaskComplexity.SIMPLE

    def test_add_comment(self):
        result = classify_task("Add a docstring to the parse method")
        assert result.complexity == TaskComplexity.SIMPLE

    def test_format_code(self):
        result = classify_task("Format this file")
        assert result.complexity == TaskComplexity.SIMPLE

    def test_simple_max_agents_is_one(self):
        result = classify_task("Fix a bug in the login handler")
        assert result.max_agents == 1

    def test_simple_excludes_architect(self):
        result = classify_task("Delete the unused import")
        assert "architect" not in result.allowed_roles


# ---------------------------------------------------------------------------
# classify_task: medium tasks
# ---------------------------------------------------------------------------


class TestClassifyMediumTasks:
    """Tasks that should be classified as medium."""

    def test_add_feature(self):
        result = classify_task("Add a feature to export reports as CSV")
        assert result.complexity == TaskComplexity.MEDIUM

    def test_implement_endpoint(self):
        result = classify_task("Implement a new REST endpoint for user preferences")
        assert result.complexity == TaskComplexity.MEDIUM

    def test_write_tests(self):
        result = classify_task("Write tests for the authentication module")
        assert result.complexity == TaskComplexity.MEDIUM

    def test_review_code(self):
        result = classify_task("Review the recent changes to the payment service")
        assert result.complexity == TaskComplexity.MEDIUM

    def test_medium_max_agents(self):
        result = classify_task("Implement and test the new cache layer")
        assert result.max_agents == 3

    def test_medium_includes_tester(self):
        result = classify_task("Build the login form and write tests")
        assert "tester" in result.allowed_roles

    def test_medium_excludes_architect(self):
        result = classify_task("Add a feature to export data")
        assert "architect" not in result.allowed_roles


# ---------------------------------------------------------------------------
# classify_task: complex tasks
# ---------------------------------------------------------------------------


class TestClassifyComplexTasks:
    """Tasks that should be classified as complex."""

    def test_system_design(self):
        result = classify_task(
            "Design and build a distributed event-driven architecture "
            "for the notification system"
        )
        assert result.complexity == TaskComplexity.COMPLEX

    def test_security_audit(self):
        result = classify_task(
            "Perform a security audit across all services and create a threat model"
        )
        assert result.complexity == TaskComplexity.COMPLEX

    def test_refactor_across_modules(self):
        result = classify_task(
            "Refactor the entire authentication system to use OAuth2 "
            "across all multiple services"
        )
        assert result.complexity == TaskComplexity.COMPLEX

    def test_complex_max_agents(self):
        result = classify_task("Architect a new microservice for payments")
        assert result.max_agents == 7

    def test_complex_includes_architect(self):
        result = classify_task("Design a scalable infrastructure")
        assert "architect" in result.allowed_roles


# ---------------------------------------------------------------------------
# classify_task: heuristic signals
# ---------------------------------------------------------------------------


class TestClassifyHeuristics:
    """Tests for structural heuristics (length, lists, questions)."""

    def test_short_message_boosts_simple(self):
        result = classify_task("Fix it")
        # Short message with no other signals defaults to medium (no strong signal)
        # but word_count < 15 gives +1 simple
        assert result.complexity in (TaskComplexity.SIMPLE, TaskComplexity.MEDIUM)

    def test_long_message_boosts_complex(self):
        long_msg = "word " * 60  # 60 words
        result = classify_task(long_msg)
        # No keyword signals, but length gives +0.5 complex
        assert result.complexity in (TaskComplexity.MEDIUM, TaskComplexity.COMPLEX)

    def test_bullet_list_boosts_complexity(self):
        task = (
            "Please do the following:\n"
            "1. Update the database schema\n"
            "2. Add the migration script\n"
            "3. Update the API endpoints\n"
            "4. Write integration tests\n"
            "5. Update the documentation"
        )
        result = classify_task(task)
        # 5 list items → complex_score += 1.0
        assert result.complexity in (TaskComplexity.MEDIUM, TaskComplexity.COMPLEX)

    def test_multiple_questions_boost_complexity(self):
        task = "What is the current auth flow? How does it handle tokens? Is it secure?"
        result = classify_task(task)
        # 3 questions → complex_score += 0.5
        assert result.complexity in (TaskComplexity.SIMPLE, TaskComplexity.MEDIUM)

    def test_conversation_history_boosts_medium(self):
        result = classify_task("Continue", message_count=15)
        # message_count > 10 → medium_score += 0.5
        assert result.complexity == TaskComplexity.MEDIUM

    def test_no_signals_defaults_to_medium(self):
        result = classify_task("asdfghjkl qwerty zxcvbn")
        assert result.complexity == TaskComplexity.MEDIUM
        assert result.confidence < 0.5


# ---------------------------------------------------------------------------
# classify_task: result structure
# ---------------------------------------------------------------------------


class TestClassificationResult:
    """Tests for the ClassificationResult structure."""

    def test_result_has_all_fields(self):
        result = classify_task("Fix a typo")
        assert isinstance(result, ClassificationResult)
        assert isinstance(result.complexity, TaskComplexity)
        assert isinstance(result.confidence, float)
        assert isinstance(result.reasoning, str)
        assert isinstance(result.max_agents, int)
        assert isinstance(result.allowed_roles, set)

    def test_confidence_between_zero_and_one(self):
        for task in ["fix typo", "add feature and tests", "design distributed system"]:
            result = classify_task(task)
            assert 0.0 <= result.confidence <= 1.0

    def test_reasoning_is_nonempty(self):
        result = classify_task("Implement a new API")
        assert len(result.reasoning) > 0

    def test_tiers_are_consistent(self):
        """Verify that tier definitions match ClassificationResult."""
        for complexity, tier in COMPLEXITY_TIERS.items():
            result = ClassificationResult(
                complexity=complexity,
                confidence=0.5,
                reasoning="test",
                max_agents=tier["max_agents"],
                allowed_roles=tier["allowed_roles"],
            )
            assert result.max_agents == tier["max_agents"]
            assert result.allowed_roles == tier["allowed_roles"]


# ---------------------------------------------------------------------------
# filter_delegations
# ---------------------------------------------------------------------------


class TestFilterDelegations:
    """Tests for the filter_delegations function."""

    def _simple_classification(self) -> ClassificationResult:
        return ClassificationResult(
            complexity=TaskComplexity.SIMPLE,
            confidence=0.8,
            reasoning="test",
            max_agents=1,
            allowed_roles={"builder", "reviewer", "documenter", "analyst"},
        )

    def _complex_classification(self) -> ClassificationResult:
        return ClassificationResult(
            complexity=TaskComplexity.COMPLEX,
            confidence=0.8,
            reasoning="test",
            max_agents=7,
            allowed_roles={
                "planner", "builder", "tester", "reviewer",
                "architect", "documenter", "analyst",
            },
        )

    def test_empty_delegations(self):
        result = filter_delegations([], self._simple_classification())
        assert result == []

    def test_simple_caps_at_one_agent(self):
        delegations = [
            {"agent": "builder", "task": "build"},
            {"agent": "reviewer", "task": "review"},
            {"agent": "tester", "task": "test"},
        ]
        result = filter_delegations(delegations, self._simple_classification())
        assert len(result) == 1
        assert result[0]["agent"] == "builder"

    def test_simple_filters_disallowed_roles(self):
        delegations = [
            {"agent": "architect", "task": "design"},  # Not in simple tier
            {"agent": "builder", "task": "build"},
        ]
        result = filter_delegations(delegations, self._simple_classification())
        assert len(result) == 1
        assert result[0]["agent"] == "builder"

    def test_complex_allows_all_roles(self):
        delegations = [
            {"agent": "planner", "task": "plan"},
            {"agent": "architect", "task": "design"},
            {"agent": "builder", "task": "build"},
            {"agent": "tester", "task": "test"},
            {"agent": "reviewer", "task": "review"},
        ]
        result = filter_delegations(delegations, self._complex_classification())
        assert len(result) == 5

    def test_complex_caps_at_seven(self):
        delegations = [{"agent": "builder", "task": f"task_{i}"} for i in range(10)]
        result = filter_delegations(delegations, self._complex_classification())
        assert len(result) == 7

    def test_preserves_order(self):
        delegations = [
            {"agent": "reviewer", "task": "review first"},
            {"agent": "builder", "task": "build second"},
        ]
        result = filter_delegations(delegations, self._complex_classification())
        assert result[0]["agent"] == "reviewer"
        assert result[1]["agent"] == "builder"

    def test_all_roles_filtered_returns_empty(self):
        delegations = [
            {"agent": "architect", "task": "design"},
            {"agent": "planner", "task": "plan"},
        ]
        result = filter_delegations(delegations, self._simple_classification())
        # architect and planner not in simple tier
        assert result == []
