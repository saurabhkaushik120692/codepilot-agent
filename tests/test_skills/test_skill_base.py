"""Tests for Skill base classes and registry."""

import pytest

from codepilot.skills.base import Skill, SkillContext, SkillRegistry


class TestSkillContext:
    """Test the SkillContext dataclass."""

    def test_defaults(self):
        ctx = SkillContext(
            issue_title="Fix bug",
            issue_body="Description",
            relevant_files=["main.py"],
            repo_map="main.py [Python]",
        )
        assert ctx.issue_title == "Fix bug"
        assert ctx.previous_attempts == []

    def test_with_previous_attempts(self):
        ctx = SkillContext(
            issue_title="Fix bug",
            issue_body="Description",
            relevant_files=[],
            repo_map="",
            previous_attempts=["Tried X, failed"],
        )
        assert len(ctx.previous_attempts) == 1


class TestSkillRegistry:
    """Test the SkillRegistry."""

    def test_register_and_get(self):
        reg = SkillRegistry()
        skill = _FakeSkill(
            name="bug_fix",
            description="Fix bugs",
            example_prompts=["fix X"],
            forbidden_actions=["skip tests"],
        )
        reg.register("bug_fix", skill)
        assert reg.get("bug_fix") is skill

    def test_get_unknown_returns_none(self):
        reg = SkillRegistry()
        assert reg.get("unknown_type") is None

    def test_list_types(self):
        reg = SkillRegistry()
        skill = _FakeSkill(
            name="bug_fix",
            description="Fix bugs",
            example_prompts=[],
            forbidden_actions=[],
        )
        reg.register("bug_fix", skill)
        reg.register("feature_addition", skill)
        assert set(reg.list_types()) == {"bug_fix", "feature_addition"}


class TestSkillABC:
    """Test the Skill ABC enforces interface."""

    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            Skill()  # type: ignore[abstract]

    def test_subclass_missing_methods_fails(self):
        with pytest.raises(TypeError):

            class IncompleteSkill(Skill):
                name = "test"
                description = "test"
                example_prompts = []
                forbidden_actions = []

            IncompleteSkill()

    def test_complete_subclass_works(self):
        skill = _FakeSkill(
            name="test",
            description="Test skill",
            example_prompts=["prompt 1"],
            forbidden_actions=["action 1"],
        )
        assert skill.name == "test"
        ctx = SkillContext(
            issue_title="Test", issue_body="", relevant_files=[], repo_map=""
        )
        prompt = skill.get_system_prompt(ctx)
        assert isinstance(prompt, str)
        assert len(prompt) > 0


class _FakeSkill(Skill):
    """Fake skill implementation for testing."""

    def __init__(
        self,
        name: str,
        description: str,
        example_prompts: list[str],
        forbidden_actions: list[str],
    ):
        self.name = name
        self.description = description
        self.example_prompts = example_prompts
        self.forbidden_actions = forbidden_actions

    def get_system_prompt(self, context: SkillContext) -> str:
        return f"Fake skill: {context.issue_title}"

    def get_workflow_steps(self) -> list[str]:
        return ["Step 1", "Step 2", "Step 3"]

    def get_checklist_template(self, context: SkillContext) -> list[str]:
        return ["Item 1", "Item 2"]
