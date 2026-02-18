"""Animus SafetyGuard protocol integration with audit logging.

Conforms to the SafetyGuard protocol defined in animus/protocols/safety.py:
    check_action(action) -> tuple[bool, str | None]
    check_learning(content, category) -> tuple[bool, str | None]

Also provides a workflow executor hook for pre-step safety validation.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from test_ai.state.backends import DatabaseBackend, SQLiteBackend

from .config import AnimusBridgeConfig
from .models import SafetyCheckResult

logger = logging.getLogger(__name__)


# Default boundaries applied when no user profile is loaded
DEFAULT_BOUNDARIES: list[str] = [
    "Cannot take actions that harm user",
    "Cannot exfiltrate user data",
    "Cannot modify own safety constraints",
    "Must be transparent about capabilities and limitations",
]


class SafetyGuardBridge:
    """SafetyGuard implementation with persistent audit logging.

    Evaluates actions and learning proposals against the user's
    boundaries (from their IdentityStore profile) and logs all
    checks for auditability.

    When an external Animus SafetyGuard is available (via API),
    delegates to it. Otherwise, evaluates locally against the
    user's configured boundaries.
    """

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS safety_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            allowed INTEGER NOT NULL,
            reason TEXT,
            check_type TEXT NOT NULL DEFAULT 'action',
            workflow_id TEXT,
            step_id TEXT,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_safety_audit_time
        ON safety_audit_log(checked_at DESC);

        CREATE INDEX IF NOT EXISTS idx_safety_audit_workflow
        ON safety_audit_log(workflow_id);

        CREATE INDEX IF NOT EXISTS idx_safety_audit_allowed
        ON safety_audit_log(allowed);
    """

    def __init__(
        self,
        backend: DatabaseBackend | None = None,
        db_path: str = "gorgon-animus-memory.db",
        config: AnimusBridgeConfig | None = None,
        boundaries: list[str] | None = None,
    ):
        self.backend = backend or SQLiteBackend(db_path=db_path)
        self.config = config or AnimusBridgeConfig()
        self.boundaries = boundaries if boundaries is not None else list(DEFAULT_BOUNDARIES)
        self._init_schema()

    def _init_schema(self) -> None:
        self.backend.executescript(self.SCHEMA)

    # --- SafetyGuard protocol methods ---

    def check_action(self, action: dict[str, Any]) -> tuple[bool, str | None]:
        """Check whether an action is allowed.

        Evaluates the action description against configured boundaries.
        Returns (allowed, violation_reason).
        """
        action_desc = action.get("description", json.dumps(action))
        violation = self._evaluate_boundaries(action_desc)

        allowed = violation is None
        result = SafetyCheckResult(
            allowed=allowed,
            reason=violation,
            action=action,
            workflow_id=action.get("workflow_id"),
            step_id=action.get("step_id"),
        )

        if self.config.log_safety_checks:
            self._log_check(result, check_type="action")

        if not allowed:
            logger.warning(
                "Safety guard BLOCKED action: %s (reason: %s)",
                action_desc[:100],
                violation,
            )
        else:
            logger.debug("Safety guard ALLOWED action: %s", action_desc[:100])

        return (allowed, violation)

    def check_learning(
        self, content: str, category: str
    ) -> tuple[bool, str | None]:
        """Check whether a learning proposal is allowed.

        Evaluates the learning content and category against boundaries.
        Returns (allowed, violation_reason).
        """
        # Check against boundaries
        violation = self._evaluate_boundaries(content)

        # Category-specific checks
        if violation is None and category in ("capability", "boundary"):
            # High-risk categories require explicit boundary allowance
            violation = self._check_high_risk_learning(content, category)

        allowed = violation is None
        result = SafetyCheckResult(
            allowed=allowed,
            reason=violation,
            action={"content": content, "category": category},
        )

        if self.config.log_safety_checks:
            self._log_check(result, check_type="learning")

        return (allowed, violation)

    # --- Boundary management ---

    def add_boundary(self, boundary: str) -> None:
        """Add a safety boundary."""
        if boundary not in self.boundaries:
            self.boundaries.append(boundary)
            logger.info("Added safety boundary: %s", boundary)

    def remove_boundary(self, boundary: str) -> bool:
        """Remove a non-default boundary.

        Default boundaries (the core four) cannot be removed.
        """
        if boundary in DEFAULT_BOUNDARIES:
            logger.warning("Cannot remove default boundary: %s", boundary)
            return False
        if boundary in self.boundaries:
            self.boundaries.remove(boundary)
            logger.info("Removed safety boundary: %s", boundary)
            return True
        return False

    def load_boundaries_from_profile(self, profile_boundaries: list[str]) -> None:
        """Load boundaries from a user profile, merging with defaults."""
        self.boundaries = list(DEFAULT_BOUNDARIES)
        for b in profile_boundaries:
            if b not in self.boundaries:
                self.boundaries.append(b)

    # --- Audit log ---

    def get_audit_log(
        self,
        limit: int = 50,
        workflow_id: str | None = None,
        allowed_only: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve safety audit log entries."""
        conditions: list[str] = []
        params: list[Any] = []

        if workflow_id is not None:
            conditions.append("workflow_id = ?")
            params.append(workflow_id)

        if allowed_only is not None:
            conditions.append("allowed = ?")
            params.append(1 if allowed_only else 0)

        where = " AND ".join(conditions) if conditions else "1=1"
        rows = self.backend.fetchall(
            f"SELECT * FROM safety_audit_log WHERE {where} ORDER BY checked_at DESC LIMIT ?",
            (*params, limit),
        )
        return [dict(row) for row in rows]

    def get_violation_count(self, workflow_id: str | None = None) -> int:
        """Count blocked actions."""
        if workflow_id:
            row = self.backend.fetchone(
                "SELECT COUNT(*) as count FROM safety_audit_log WHERE allowed = 0 AND workflow_id = ?",
                (workflow_id,),
            )
        else:
            row = self.backend.fetchone(
                "SELECT COUNT(*) as count FROM safety_audit_log WHERE allowed = 0",
                (),
            )
        return row["count"] if row else 0

    # --- Private helpers ---

    def _evaluate_boundaries(self, description: str) -> str | None:
        """Check a description against all boundaries.

        Returns the violated boundary text, or None if allowed.
        Simple keyword matching — production deployments should use
        the full Animus SafetyGuard via API for semantic evaluation.
        """
        desc_lower = description.lower()

        # Check for explicit boundary violations via keyword patterns
        violation_patterns = {
            "harm": "Cannot take actions that harm user",
            "exfiltrate": "Cannot exfiltrate user data",
            "leak": "Cannot exfiltrate user data",
            "send data to": "Cannot exfiltrate user data",
            "modify safety": "Cannot modify own safety constraints",
            "disable guard": "Cannot modify own safety constraints",
            "remove boundary": "Cannot modify own safety constraints",
        }

        for keyword, boundary in violation_patterns.items():
            if keyword in desc_lower and boundary in self.boundaries:
                return f"Boundary violation: {boundary}"

        return None

    def _check_high_risk_learning(
        self, content: str, category: str
    ) -> str | None:
        """Additional checks for high-risk learning categories."""
        content_lower = content.lower()

        # Capability changes that affect safety
        if category == "capability":
            risky_terms = ["delete", "drop", "destroy", "admin", "root", "sudo"]
            for term in risky_terms:
                if term in content_lower:
                    return (
                        f"High-risk capability learning blocked: "
                        f"contains '{term}' (category: {category})"
                    )

        # Boundary changes
        if category == "boundary":
            if any(b.lower() in content_lower for b in DEFAULT_BOUNDARIES):
                return "Cannot learn modifications to core safety boundaries"

        return None

    def _log_check(
        self, result: SafetyCheckResult, check_type: str = "action"
    ) -> None:
        """Persist a safety check result to the audit log."""
        with self.backend.transaction():
            self.backend.execute(
                """
                INSERT INTO safety_audit_log
                (action, allowed, reason, check_type, workflow_id, step_id, checked_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    json.dumps(result.action),
                    1 if result.allowed else 0,
                    result.reason,
                    check_type,
                    result.workflow_id,
                    result.step_id,
                    result.checked_at.isoformat(),
                ),
            )
