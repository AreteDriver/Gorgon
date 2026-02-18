"""User identity and profile persistence.

Maps to Animus Core Layer: identity, preferences, boundaries, ethics.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from test_ai.state.backends import DatabaseBackend, SQLiteBackend

from .models import UserProfile

logger = logging.getLogger(__name__)


class IdentityStore:
    """Persistent store for user profiles and preferences.

    Implements the identity portion of Animus's Core Layer,
    storing user preferences, boundaries, and ethics configuration
    that agents must respect during workflow execution.
    """

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS user_profiles (
            id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL DEFAULT 'User',
            preferences TEXT,
            boundaries TEXT,
            ethics_config TEXT,
            learning_config TEXT,
            metadata TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_profiles_active
        ON user_profiles(is_active);
    """

    def __init__(
        self,
        backend: DatabaseBackend | None = None,
        db_path: str = "gorgon-animus-memory.db",
    ):
        self.backend = backend or SQLiteBackend(db_path=db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        self.backend.executescript(self.SCHEMA)

    def create_profile(self, profile: UserProfile) -> str:
        """Create a new user profile. Returns the profile ID."""
        with self.backend.transaction():
            self.backend.execute(
                """
                INSERT INTO user_profiles
                (id, display_name, preferences, boundaries, ethics_config,
                 learning_config, metadata, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.id,
                    profile.display_name,
                    json.dumps(profile.preferences),
                    json.dumps(profile.boundaries),
                    json.dumps(profile.ethics_config),
                    json.dumps(profile.learning_config),
                    json.dumps(profile.metadata),
                    1 if profile.is_active else 0,
                    profile.created_at.isoformat(),
                    profile.updated_at.isoformat(),
                ),
            )
        logger.info("Created user profile %s (%s)", profile.id, profile.display_name)
        return profile.id

    def get_profile(self, profile_id: str) -> UserProfile | None:
        """Retrieve a profile by ID."""
        row = self.backend.fetchone(
            "SELECT * FROM user_profiles WHERE id = ?",
            (profile_id,),
        )
        if not row:
            return None
        return self._row_to_profile(row)

    def get_active_profile(self) -> UserProfile | None:
        """Get the currently active user profile."""
        row = self.backend.fetchone(
            "SELECT * FROM user_profiles WHERE is_active = 1 ORDER BY updated_at DESC LIMIT 1",
            (),
        )
        if not row:
            return None
        return self._row_to_profile(row)

    def update_profile(self, profile: UserProfile) -> bool:
        """Update an existing profile."""
        profile.updated_at = datetime.now(timezone.utc)
        with self.backend.transaction():
            cursor = self.backend.execute(
                """
                UPDATE user_profiles
                SET display_name = ?, preferences = ?, boundaries = ?,
                    ethics_config = ?, learning_config = ?, metadata = ?,
                    is_active = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    profile.display_name,
                    json.dumps(profile.preferences),
                    json.dumps(profile.boundaries),
                    json.dumps(profile.ethics_config),
                    json.dumps(profile.learning_config),
                    json.dumps(profile.metadata),
                    1 if profile.is_active else 0,
                    profile.updated_at.isoformat(),
                    profile.id,
                ),
            )
        updated = cursor.rowcount > 0
        if updated:
            logger.info("Updated profile %s", profile.id)
        return updated

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile by ID."""
        with self.backend.transaction():
            cursor = self.backend.execute(
                "DELETE FROM user_profiles WHERE id = ?",
                (profile_id,),
            )
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Deleted profile %s", profile_id)
        return deleted

    def list_profiles(self) -> list[UserProfile]:
        """List all user profiles."""
        rows = self.backend.fetchall(
            "SELECT * FROM user_profiles ORDER BY updated_at DESC",
            (),
        )
        return [self._row_to_profile(row) for row in rows]

    # --- Preference helpers ---

    def get_preference(self, profile_id: str, key: str) -> Any:
        """Get a single preference value."""
        profile = self.get_profile(profile_id)
        if not profile:
            return None
        return profile.preferences.get(key)

    def set_preference(self, profile_id: str, key: str, value: Any) -> bool:
        """Set a single preference value."""
        profile = self.get_profile(profile_id)
        if not profile:
            return False
        profile.preferences[key] = value
        return self.update_profile(profile)

    # --- Boundary helpers ---

    def get_boundaries(self, profile_id: str) -> list[str]:
        """Get the user's boundaries (things the system must not do)."""
        profile = self.get_profile(profile_id)
        if not profile:
            return []
        return profile.boundaries

    def add_boundary(self, profile_id: str, boundary: str) -> bool:
        """Add a boundary constraint."""
        profile = self.get_profile(profile_id)
        if not profile:
            return False
        if boundary not in profile.boundaries:
            profile.boundaries.append(boundary)
            return self.update_profile(profile)
        return True

    def remove_boundary(self, profile_id: str, boundary: str) -> bool:
        """Remove a boundary constraint."""
        profile = self.get_profile(profile_id)
        if not profile:
            return False
        if boundary in profile.boundaries:
            profile.boundaries.remove(boundary)
            return self.update_profile(profile)
        return True

    # --- Context injection ---

    def get_identity_context(self, profile_id: str | None = None) -> str:
        """Build a prompt context string from the user's identity.

        This is injected into agent prompts so they respect the user's
        preferences and boundaries.
        """
        profile = (
            self.get_profile(profile_id) if profile_id else self.get_active_profile()
        )
        if not profile:
            return ""

        parts: list[str] = []
        parts.append(f"User: {profile.display_name}")

        if profile.preferences:
            pref_lines = [f"  - {k}: {v}" for k, v in profile.preferences.items()]
            parts.append("Preferences:\n" + "\n".join(pref_lines))

        if profile.boundaries:
            boundary_lines = [f"  - {b}" for b in profile.boundaries]
            parts.append("Boundaries (do NOT violate):\n" + "\n".join(boundary_lines))

        if profile.ethics_config:
            ethics_lines = [
                f"  - {k}: {v}" for k, v in profile.ethics_config.items()
            ]
            parts.append("Ethics:\n" + "\n".join(ethics_lines))

        return "\n\n".join(parts)

    # --- Private helpers ---

    def _row_to_profile(self, row: dict) -> UserProfile:
        """Convert a database row to a UserProfile."""
        return UserProfile(
            id=row["id"],
            display_name=row["display_name"],
            preferences=json.loads(row["preferences"]) if row["preferences"] else {},
            boundaries=json.loads(row["boundaries"]) if row["boundaries"] else [],
            ethics_config=(
                json.loads(row["ethics_config"]) if row["ethics_config"] else {}
            ),
            learning_config=(
                json.loads(row["learning_config"]) if row["learning_config"] else {}
            ),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            is_active=bool(row["is_active"]),
        )
