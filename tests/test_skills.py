"""Tests for skill loading and querying."""

from pathlib import Path

import pytest

from test_ai.skills import SkillLibrary, SkillCapability, SkillDefinition, SkillRegistry
from test_ai.skills.loader import load_skill, load_registry

SKILLS_DIR = Path(__file__).parent.parent / "skills"


@pytest.fixture
def library():
    return SkillLibrary(skills_dir=SKILLS_DIR)


@pytest.fixture
def registry():
    return load_registry(SKILLS_DIR)


# --- Loader tests ---


class TestLoadSkill:
    def test_load_file_operations(self):
        skill = load_skill(SKILLS_DIR / "system" / "file_operations")
        assert skill.name == "file_operations"
        assert skill.agent == "system"
        assert skill.version == "1.0.0"
        assert len(skill.capabilities) > 0
        assert skill.skill_doc  # SKILL.md loaded

    def test_load_web_search(self):
        skill = load_skill(SKILLS_DIR / "browser" / "web_search")
        assert skill.name == "web_search"
        assert skill.agent == "browser"

    def test_load_missing_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_skill(tmp_path / "nonexistent")


class TestLoadRegistry:
    def test_registry_loads_all_skills(self, registry):
        assert registry.version == "1.0.0"
        assert len(registry.skills) >= 5  # 6 active skills in registry

    def test_registry_has_categories(self, registry):
        assert "system" in registry.categories
        assert "browser" in registry.categories

    def test_registry_has_consensus_levels(self, registry):
        assert "any" in registry.consensus_levels
        assert "unanimous" in registry.consensus_levels


# --- Model tests ---


class TestSkillDefinition:
    def test_get_capability(self):
        cap = SkillCapability(name="read_file", description="Read a file")
        skill = SkillDefinition(
            name="test", agent="system", capabilities=[cap]
        )
        assert skill.get_capability("read_file") is not None
        assert skill.get_capability("nonexistent") is None


class TestSkillRegistry:
    def test_get_skill(self, registry):
        assert registry.get_skill("file_operations") is not None
        assert registry.get_skill("nonexistent_skill") is None

    def test_get_skills_for_agent(self, registry):
        system_skills = registry.get_skills_for_agent("system")
        assert len(system_skills) >= 2
        for s in system_skills:
            assert s.agent == "system"

        browser_skills = registry.get_skills_for_agent("browser")
        assert len(browser_skills) >= 2
        for s in browser_skills:
            assert s.agent == "browser"


# --- Library tests ---


class TestSkillLibrary:
    def test_get_skill(self, library):
        skill = library.get_skill("file_operations")
        assert skill is not None
        assert skill.name == "file_operations"

    def test_get_skill_missing(self, library):
        assert library.get_skill("does_not_exist") is None

    def test_get_skills_for_agent(self, library):
        skills = library.get_skills_for_agent("system")
        assert len(skills) >= 2
        names = [s.name for s in skills]
        assert "file_operations" in names
        assert "process_management" in names

    def test_get_capabilities(self, library):
        caps = library.get_capabilities("file_operations")
        assert len(caps) > 0
        cap_names = [c.name for c in caps]
        assert "read_file" in cap_names
        assert "delete_file" in cap_names

    def test_get_capabilities_missing_skill(self, library):
        assert library.get_capabilities("nonexistent") == []

    def test_get_consensus_level(self, library):
        assert library.get_consensus_level("file_operations", "read_file") == "any"
        assert library.get_consensus_level("file_operations", "delete_file") == "unanimous"

    def test_get_consensus_level_missing(self, library):
        assert library.get_consensus_level("nonexistent", "read_file") is None
        assert library.get_consensus_level("file_operations", "nonexistent") is None

    def test_build_skill_context(self, library):
        ctx = library.build_skill_context("system")
        assert "system agent" in ctx
        assert "file_operations" in ctx
        assert "read_file" in ctx
        assert "Protected paths" in ctx

    def test_build_skill_context_empty_agent(self, library):
        assert library.build_skill_context("nonexistent_agent") == ""
