"""Runtime API for querying skills."""

from __future__ import annotations

import logging
from pathlib import Path

from .loader import load_registry
from .models import SkillCapability, SkillDefinition, SkillRegistry

logger = logging.getLogger(__name__)

_DEFAULT_SKILLS_DIR = Path(__file__).parent.parent.parent.parent / "skills"


class SkillLibrary:
    """Load and query skill definitions at runtime."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        self._skills_dir = skills_dir or _DEFAULT_SKILLS_DIR
        self._registry: SkillRegistry = load_registry(self._skills_dir)

    @property
    def registry(self) -> SkillRegistry:
        return self._registry

    def get_skill(self, name: str) -> SkillDefinition | None:
        return self._registry.get_skill(name)

    def get_skills_for_agent(self, agent: str) -> list[SkillDefinition]:
        return self._registry.get_skills_for_agent(agent)

    def get_capabilities(self, name: str) -> list[SkillCapability]:
        skill = self._registry.get_skill(name)
        if skill is None:
            return []
        return skill.capabilities

    def get_consensus_level(self, skill: str, capability: str) -> str | None:
        """Return the consensus level for a specific capability, or None if not found."""
        skill_def = self._registry.get_skill(skill)
        if skill_def is None:
            return None
        cap = skill_def.get_capability(capability)
        if cap is None:
            return None
        return cap.consensus_required

    def build_skill_context(self, agent: str) -> str:
        """Render skill docs into a prompt-injectable string for an agent."""
        skills = self.get_skills_for_agent(agent)
        if not skills:
            return ""

        sections: list[str] = [f"# Skills for {agent} agent\n"]
        for skill in skills:
            sections.append(f"## {skill.name} (v{skill.version})")
            sections.append(skill.description.strip())
            sections.append("")
            sections.append("### Capabilities")
            for cap in skill.capabilities:
                risk = cap.risk_level
                consensus = cap.consensus_required
                sections.append(
                    f"- **{cap.name}** — {cap.description} "
                    f"[risk={risk}, consensus={consensus}]"
                )
            if skill.protected_paths:
                sections.append("")
                sections.append("### Protected paths")
                for p in skill.protected_paths:
                    sections.append(f"- `{p}`")
            sections.append("")

        return "\n".join(sections)
