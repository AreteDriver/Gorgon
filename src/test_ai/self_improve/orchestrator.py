"""Self-improvement orchestrator - coordinates the entire self-improvement workflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .analyzer import CodebaseAnalyzer, ImprovementSuggestion
from .approval import ApprovalGate, ApprovalStage
from .pr_manager import PRManager, PullRequest
from .rollback import RollbackManager, Snapshot
from .safety import SafetyChecker, SafetyConfig, SafetyViolation
from .sandbox import Sandbox, SandboxResult

if TYPE_CHECKING:
    from test_ai.agents.provider_wrapper import AgentProvider

logger = logging.getLogger(__name__)


class WorkflowStage(str, Enum):
    """Stages of the self-improvement workflow."""

    IDLE = "idle"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    AWAITING_APPLY_APPROVAL = "awaiting_apply_approval"
    APPLYING = "applying"
    CREATING_PR = "creating_pr"
    AWAITING_MERGE_APPROVAL = "awaiting_merge_approval"
    COMPLETE = "complete"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ImprovementPlan:
    """Plan for implementing improvements."""

    id: str
    title: str
    description: str
    suggestions: list[ImprovementSuggestion]
    implementation_steps: list[str]
    estimated_files: list[str]
    estimated_lines: int
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ImprovementResult:
    """Result of a self-improvement run."""

    success: bool
    stage_reached: WorkflowStage
    plan: ImprovementPlan | None = None
    snapshot: Snapshot | None = None
    sandbox_result: SandboxResult | None = None
    pull_request: PullRequest | None = None
    error: str | None = None
    violations: list[SafetyViolation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class SelfImproveOrchestrator:
    """Orchestrates the complete self-improvement workflow.

    Workflow:
    1. Analyze codebase for improvement opportunities
    2. Create improvement plan
    3. Get human approval for plan
    4. Implement changes in sandbox
    5. Run tests in sandbox
    6. Get human approval to apply changes
    7. Create snapshot for rollback
    8. Apply changes to working tree
    9. Create PR
    10. Get human approval to merge
    """

    def __init__(
        self,
        codebase_path: Path | str = ".",
        provider: "AgentProvider | None" = None,
        config: SafetyConfig | None = None,
    ):
        """Initialize the orchestrator.

        Args:
            codebase_path: Path to codebase root.
            provider: Optional AI provider for intelligent improvements.
            config: Safety configuration.
        """
        self.codebase_path = Path(codebase_path)
        self.provider = provider
        self.config = config or SafetyConfig.load()

        # Initialize components
        self.safety_checker = SafetyChecker(self.config)
        self.analyzer = CodebaseAnalyzer(provider, self.codebase_path)
        self.approval_gate = ApprovalGate()
        self.rollback_manager = RollbackManager(
            self.codebase_path / ".gorgon/snapshots",
            self.config.max_snapshots,
        )
        self.pr_manager = PRManager(self.codebase_path, self.config.branch_prefix)

        self._current_stage = WorkflowStage.IDLE
        self._current_plan: ImprovementPlan | None = None

    @property
    def current_stage(self) -> WorkflowStage:
        """Get current workflow stage."""
        return self._current_stage

    async def run(
        self,
        focus_category: str | None = None,
        auto_approve: bool = False,
    ) -> ImprovementResult:
        """Run the complete self-improvement workflow.

        Args:
            focus_category: Optional category to focus on.
            auto_approve: If True, auto-approve all stages (for testing).

        Returns:
            Result of the improvement run.
        """
        try:
            # Stage 1: Analyze
            self._current_stage = WorkflowStage.ANALYZING
            logger.info("Starting analysis...")
            analysis = self.analyzer.analyze()

            if not analysis.suggestions:
                logger.info("No improvement opportunities found")
                self._current_stage = WorkflowStage.COMPLETE
                return ImprovementResult(
                    success=True,
                    stage_reached=WorkflowStage.COMPLETE,
                    metadata={"message": "No improvements needed"},
                )

            # Stage 2: Create plan
            self._current_stage = WorkflowStage.PLANNING
            plan = self._create_plan(analysis.suggestions[:5])  # Limit to top 5
            self._current_plan = plan

            # Check safety violations
            violations = self.safety_checker.check_changes(
                files_modified=plan.estimated_files,
                files_added=[],
                files_deleted=[],
                lines_changed=plan.estimated_lines,
                category=focus_category,
            )

            if self.safety_checker.has_blocking_violations(violations):
                self._current_stage = WorkflowStage.FAILED
                return ImprovementResult(
                    success=False,
                    stage_reached=WorkflowStage.PLANNING,
                    plan=plan,
                    violations=violations,
                    error="Safety violations prevent this improvement",
                )

            # Stage 3: Get plan approval
            if self.config.human_approval_plan:
                self._current_stage = WorkflowStage.AWAITING_PLAN_APPROVAL
                approval = self.approval_gate.request_approval(
                    stage=ApprovalStage.PLAN,
                    title=f"Self-Improvement Plan: {plan.title}",
                    description=plan.description,
                    details={
                        "suggestions": [s.title for s in plan.suggestions],
                        "estimated_files": plan.estimated_files,
                        "estimated_lines": plan.estimated_lines,
                    },
                )

                if auto_approve:
                    self.approval_gate.auto_approve_for_testing(approval.id)

                if not self.approval_gate.is_approved(approval.id):
                    logger.info("Waiting for plan approval...")
                    # In real implementation, would wait here
                    if not auto_approve:
                        return ImprovementResult(
                            success=False,
                            stage_reached=WorkflowStage.AWAITING_PLAN_APPROVAL,
                            plan=plan,
                            error="Plan approval required",
                        )

            # Stage 4: Implement in sandbox
            self._current_stage = WorkflowStage.IMPLEMENTING
            logger.info("Implementing changes in sandbox...")

            if self.provider is None:
                self._current_stage = WorkflowStage.FAILED
                return ImprovementResult(
                    success=False,
                    stage_reached=WorkflowStage.IMPLEMENTING,
                    plan=plan,
                    error="No AI provider configured for code generation",
                )

            changes = await self._generate_changes(plan)
            if not changes:
                self._current_stage = WorkflowStage.FAILED
                return ImprovementResult(
                    success=False,
                    stage_reached=WorkflowStage.IMPLEMENTING,
                    plan=plan,
                    error="AI provider returned no changes",
                )

            logger.info("Generated changes for %d files", len(changes))

            # Stage 5: Test in sandbox
            self._current_stage = WorkflowStage.TESTING
            with Sandbox(self.codebase_path) as sandbox:
                applied = await sandbox.apply_changes(changes)
                if not applied:
                    self._current_stage = WorkflowStage.FAILED
                    return ImprovementResult(
                        success=False,
                        stage_reached=WorkflowStage.TESTING,
                        plan=plan,
                        error="Failed to apply changes to sandbox",
                    )

                sandbox_result = await sandbox.validate_changes(
                    changed_files=list(changes.keys())
                )

            if not sandbox_result.tests_passed:
                if self.config.auto_rollback_on_test_failure:
                    self._current_stage = WorkflowStage.FAILED
                    return ImprovementResult(
                        success=False,
                        stage_reached=WorkflowStage.TESTING,
                        plan=plan,
                        sandbox_result=sandbox_result,
                        error="Tests failed in sandbox",
                    )

            # Stage 6: Get apply approval
            if self.config.human_approval_apply:
                self._current_stage = WorkflowStage.AWAITING_APPLY_APPROVAL
                approval = self.approval_gate.request_approval(
                    stage=ApprovalStage.APPLY,
                    title=f"Apply Changes: {plan.title}",
                    description="Changes have passed testing. Ready to apply to working tree.",
                    details={
                        "sandbox_status": sandbox_result.status.value,
                        "tests_passed": sandbox_result.tests_passed,
                        "lint_passed": sandbox_result.lint_passed,
                    },
                )

                if auto_approve:
                    self.approval_gate.auto_approve_for_testing(approval.id)

                if not self.approval_gate.is_approved(approval.id):
                    if not auto_approve:
                        return ImprovementResult(
                            success=False,
                            stage_reached=WorkflowStage.AWAITING_APPLY_APPROVAL,
                            plan=plan,
                            sandbox_result=sandbox_result,
                            error="Apply approval required",
                        )

            # Stage 7: Create snapshot
            snapshot = self.rollback_manager.create_snapshot(
                files=plan.estimated_files,
                description=f"Before: {plan.title}",
                codebase_path=self.codebase_path,
            )

            # Stage 8: Apply changes
            self._current_stage = WorkflowStage.APPLYING
            logger.info("Applying changes to working tree...")
            for file_path, content in changes.items():
                full_path = self.codebase_path / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)
                logger.info("Applied: %s", file_path)

            # Stage 9: Create PR
            self._current_stage = WorkflowStage.CREATING_PR
            branch = self.pr_manager.create_branch(plan.id)
            pr = self.pr_manager.create_pr(
                branch=branch,
                title=plan.title,
                description=plan.description,
                files_changed=plan.estimated_files,
                draft=True,
            )

            # Stage 10: Get merge approval
            if self.config.human_approval_merge:
                self._current_stage = WorkflowStage.AWAITING_MERGE_APPROVAL
                approval = self.approval_gate.request_approval(
                    stage=ApprovalStage.MERGE,
                    title=f"Merge PR: {plan.title}",
                    description="PR is ready for merge.",
                    details={"pr_url": pr.url},
                )

                if not auto_approve:
                    return ImprovementResult(
                        success=True,
                        stage_reached=WorkflowStage.AWAITING_MERGE_APPROVAL,
                        plan=plan,
                        snapshot=snapshot,
                        sandbox_result=sandbox_result,
                        pull_request=pr,
                    )

            self._current_stage = WorkflowStage.COMPLETE
            return ImprovementResult(
                success=True,
                stage_reached=WorkflowStage.COMPLETE,
                plan=plan,
                snapshot=snapshot,
                sandbox_result=sandbox_result,
                pull_request=pr,
            )

        except Exception as e:
            logger.error(f"Self-improvement failed: {e}", exc_info=True)
            self._current_stage = WorkflowStage.FAILED
            return ImprovementResult(
                success=False,
                stage_reached=self._current_stage,
                error=str(e),
            )

    def _create_plan(self, suggestions: list[ImprovementSuggestion]) -> ImprovementPlan:
        """Create an improvement plan from suggestions.

        Args:
            suggestions: List of improvement suggestions.

        Returns:
            Created plan.
        """
        import uuid

        # Aggregate files and estimates
        all_files = set()
        total_lines = 0
        for suggestion in suggestions:
            all_files.update(suggestion.affected_files)
            total_lines += suggestion.estimated_lines

        # Generate title and description
        if len(suggestions) == 1:
            title = suggestions[0].title
            description = suggestions[0].description
        else:
            title = f"Multiple improvements ({len(suggestions)} items)"
            description = "\n".join(f"- {s.title}" for s in suggestions)

        # Generate implementation steps
        steps = [f"Implement: {s.title}" for s in suggestions]

        return ImprovementPlan(
            id=str(uuid.uuid4())[:8],
            title=title,
            description=description,
            suggestions=suggestions,
            implementation_steps=steps,
            estimated_files=list(all_files),
            estimated_lines=total_lines,
        )

    async def _generate_changes(self, plan: ImprovementPlan) -> dict[str, str]:
        """Use the AI provider to generate code changes for the plan.

        Reads each affected file, sends it to the provider with the plan
        context, and collects the modified file contents.

        Args:
            plan: The improvement plan with suggestions and affected files.

        Returns:
            Dict mapping file paths (relative to codebase root) to new content.
            Empty dict if generation fails.
        """
        changes: dict[str, str] = {}

        # Build the plan context once
        plan_context = (
            f"# Improvement Plan: {plan.title}\n\n"
            f"{plan.description}\n\n"
            "## Implementation Steps\n"
            + "\n".join(f"- {step}" for step in plan.implementation_steps)
        )

        for file_path in plan.estimated_files:
            full_path = self.codebase_path / file_path
            if not full_path.is_file():
                logger.warning("Skipping non-existent file: %s", file_path)
                continue

            try:
                original_content = full_path.read_text()
            except Exception as exc:
                logger.warning("Cannot read %s: %s", file_path, exc)
                continue

            prompt = (
                f"{plan_context}\n\n"
                f"## File to Modify: {file_path}\n\n"
                f"```python\n{original_content}\n```\n\n"
                "Apply the improvements described above to this file. "
                "Return ONLY the complete modified file content, no explanation. "
                "Do not wrap in markdown code fences. "
                "Preserve all existing functionality — only add or refactor "
                "what the plan describes."
            )

            try:
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are a senior software engineer performing "
                            "precise code improvements. Return only the "
                            "complete modified file content."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ]
                response = await self.provider.complete(messages, max_tokens=16384)

                # Strip markdown fences if the model wraps anyway
                content = response.strip()
                if content.startswith("```"):
                    first_nl = content.index("\n")
                    content = content[first_nl + 1 :]
                if content.endswith("```"):
                    content = content[:-3].rstrip()

                if content:
                    changes[file_path] = content
                    logger.info("Generated changes for %s", file_path)
                else:
                    logger.warning("Empty response for %s", file_path)

            except Exception as exc:
                logger.error("Code generation failed for %s: %s", file_path, exc)

        return changes

    def rollback(self, snapshot_id: str) -> bool:
        """Rollback to a previous snapshot.

        Args:
            snapshot_id: ID of snapshot to rollback to.

        Returns:
            True if rollback succeeded.
        """
        result = self.rollback_manager.rollback(snapshot_id, self.codebase_path)
        if result:
            self._current_stage = WorkflowStage.ROLLED_BACK
        return result

    def get_status(self) -> dict[str, Any]:
        """Get current orchestrator status.

        Returns:
            Status dictionary.
        """
        return {
            "stage": self._current_stage.value,
            "current_plan": self._current_plan.title if self._current_plan else None,
            "pending_approvals": len(self.approval_gate.get_pending()),
            "snapshots_available": len(self.rollback_manager.list_snapshots()),
        }
