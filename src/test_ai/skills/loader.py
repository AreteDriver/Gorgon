"""Load skill definitions from disk."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from .models import SkillCapability, SkillDefinition, SkillRegistry

logger = logging.getLogger(__name__)


def load_skill(skill_dir: Path) -> SkillDefinition:
    """Load a single skill from a directory containing schema.yaml and optionally SKILL.md."""
    schema_path = skill_dir / "schema.yaml"
    if not schema_path.exists():
        raise FileNotFoundError(f"No schema.yaml in {skill_dir}")

    with open(schema_path) as f:
        raw = yaml.safe_load(f)

    # Parse capabilities from the schema
    capabilities: list[SkillCapability] = []
    raw_caps = raw.get("capabilities", {})
    if isinstance(raw_caps, dict):
        for cap_name, cap_data in raw_caps.items():
            if not isinstance(cap_data, dict):
                continue
            capabilities.append(
                SkillCapability(
                    name=cap_name,
                    description=cap_data.get("description", ""),
                    inputs=cap_data.get("inputs", {}),
                    outputs=cap_data.get("outputs", {}),
                    risk_level=cap_data.get("risk_level", "low"),
                    consensus_required=cap_data.get("consensus_required", "any"),
                    requires_user_confirmation=cap_data.get(
                        "requires_user_confirmation", False
                    ),
                    side_effects=cap_data.get("side_effects", []),
                    warnings=cap_data.get("warnings", []),
                    examples=cap_data.get("examples", []),
                )
            )

    # Read SKILL.md if present
    skill_doc = ""
    skill_md_path = skill_dir / "SKILL.md"
    if skill_md_path.exists():
        skill_doc = skill_md_path.read_text()

    return SkillDefinition(
        name=raw.get("skill_name", skill_dir.name),
        version=raw.get("version", "1.0.0"),
        agent=raw.get("agent", "unknown"),
        description=raw.get("description", ""),
        capabilities=capabilities,
        capability_names=[c.name for c in capabilities],
        protected_paths=raw.get("protected_paths", []),
        blocked_patterns=raw.get("blocked_patterns", []),
        dependencies=raw.get("dependencies", {}),
        skill_doc=skill_doc,
    )


def load_registry(skills_dir: Path) -> SkillRegistry:
    """Load the full skill registry from a directory containing registry.yaml."""
    registry_path = skills_dir / "registry.yaml"
    if not registry_path.exists():
        raise FileNotFoundError(f"No registry.yaml in {skills_dir}")

    with open(registry_path) as f:
        raw = yaml.safe_load(f)

    skills: list[SkillDefinition] = []
    for entry in raw.get("skills", []):
        skill_path = skills_dir / entry["path"]
        if not skill_path.exists():
            logger.warning("Skill path not found: %s", skill_path)
            continue
        try:
            skill = load_skill(skill_path)
            # Override status from registry if present
            skill.status = entry.get("status", "active")
            skills.append(skill)
        except Exception:
            logger.exception("Failed to load skill from %s", skill_path)

    return SkillRegistry(
        version=raw.get("version", "1.0.0"),
        skills=skills,
        categories=raw.get("categories", {}),
        consensus_levels=raw.get("consensus_levels", {}),
    )
