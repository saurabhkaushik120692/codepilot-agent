"""Tests for all 5 skill implementations."""

import pytest

from codepilot.skills.base import Skill, SkillContext
from codepilot.skills.bug_fix import BugFixSkill
from codepilot.skills.config_change import ConfigChangeSkill
from codepilot.skills.dependency_update import DependencyUpdateSkill
from codepilot.skills.documentation import DocumentationSkill
from codepilot.skills.feature_addition import FeatureAdditionSkill


@pytest.fixture
def skill_context():
    return SkillContext(
        issue_title="Fix division by zero",
        issue_body="Calculator crashes when dividing by zero",
        relevant_files=["src/calculator.py", "tests/test_calculator.py"],
        repo_map="src/calculator.py [Python]  def divide",
    )


ALL_SKILLS = [
    BugFixSkill,
    FeatureAdditionSkill,
    DependencyUpdateSkill,
    DocumentationSkill,
    ConfigChangeSkill,
]

SKILL_NAMES = [
    "bug_fix",
    "feature_addition",
    "dependency_update",
    "documentation",
    "config_change",
]


class TestAllSkills:
    """Parameterized tests for all 5 skills."""

    @pytest.mark.parametrize("skill_cls", ALL_SKILLS)
    def test_instantiates(self, skill_cls):
        skill = skill_cls()
        assert isinstance(skill, Skill)
        assert isinstance(skill.name, str)
        assert len(skill.name) > 0

    @pytest.mark.parametrize("skill_cls", ALL_SKILLS)
    def test_get_system_prompt_non_empty(self, skill_cls, skill_context):
        skill = skill_cls()
        prompt = skill.get_system_prompt(skill_context)
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert skill_context.issue_title in prompt

    @pytest.mark.parametrize("skill_cls", ALL_SKILLS)
    def test_get_workflow_steps(self, skill_cls):
        skill = skill_cls()
        steps = skill.get_workflow_steps()
        assert isinstance(steps, list)
        assert len(steps) >= 4
        assert all(isinstance(s, str) for s in steps)

    @pytest.mark.parametrize("skill_cls", ALL_SKILLS)
    def test_get_checklist_template(self, skill_cls, skill_context):
        skill = skill_cls()
        checklist = skill.get_checklist_template(skill_context)
        assert isinstance(checklist, list)
        assert len(checklist) >= 3

    @pytest.mark.parametrize("skill_cls", ALL_SKILLS)
    def test_example_prompts_non_empty(self, skill_cls):
        skill = skill_cls()
        assert len(skill.example_prompts) > 0

    @pytest.mark.parametrize("skill_cls", ALL_SKILLS)
    def test_forbidden_actions_non_empty(self, skill_cls):
        skill = skill_cls()
        assert len(skill.forbidden_actions) > 0


class TestSkillsFromRegistry:
    """Test all skills can be registered and retrieved."""

    def test_all_skills_registerable(self):
        from codepilot.skills.base import SkillRegistry

        skills = [
            BugFixSkill(),
            FeatureAdditionSkill(),
            DependencyUpdateSkill(),
            DocumentationSkill(),
            ConfigChangeSkill(),
        ]
        names = SKILL_NAMES

        reg = SkillRegistry()
        for name, skill in zip(names, skills):
            reg.register(name, skill)

        assert set(reg.list_types()) == set(names)

        for name in names:
            assert reg.get(name) is not None
