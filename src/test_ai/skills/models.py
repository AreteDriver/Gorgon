"""Pydantic models for skill definitions."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkillCapability(BaseModel):
    """A single capability within a skill."""

    name: str
    description: str = ""
    inputs: dict = Field(default_factory=dict)
    outputs: dict = Field(default_factory=dict)
    risk_level: str = "low"
    consensus_required: str = "any"
    requires_user_confirmation: bool = False
    side_effects: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    examples: list[dict] = Field(default_factory=list)


class SkillDefinition(BaseModel):
    """Full skill definition loaded from schema.yaml + SKILL.md."""

    name: str
    version: str = "1.0.0"
    agent: str
    description: str = ""
    capabilities: list[SkillCapability] = Field(default_factory=list)
    capability_names: list[str] = Field(default_factory=list)
    protected_paths: list[str] = Field(default_factory=list)
    blocked_patterns: list[str] = Field(default_factory=list)
    dependencies: dict = Field(default_factory=dict)
    status: str = "active"
    skill_doc: str = ""  # Contents of SKILL.md

    def get_capability(self, name: str) -> SkillCapability | None:
        """Get a capability by name."""
        for cap in self.capabilities:
            if cap.name == name:
                return cap
        return None


class SkillRegistry(BaseModel):
    """Collection of loaded skills."""

    version: str = "1.0.0"
    skills: list[SkillDefinition] = Field(default_factory=list)
    categories: dict[str, str] = Field(default_factory=dict)
    consensus_levels: dict[str, dict] = Field(default_factory=dict)

    def get_skill(self, name: str) -> SkillDefinition | None:
        """Find a skill by name."""
        for skill in self.skills:
            if skill.name == name:
                return skill
        return None

    def get_skills_for_agent(self, agent: str) -> list[SkillDefinition]:
        """Get all active skills assigned to an agent."""
        return [s for s in self.skills if s.agent == agent and s.status == "active"]
