"""Skill base classes and registry.

Skills are structured prompt templates + workflow instructions
that the Orchestrator injects into the Coder's system prompt.
They are NOT agents — they don't make LLM calls themselves.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SkillContext:
    """Injected context for a skill — what the skill knows."""

    issue_title: str
    issue_body: str
    relevant_files: list[str]
    repo_map: str
    previous_attempts: list[str] = field(default_factory=list)


class Skill(ABC):
    """Base class for all task-type skills.

    Each concrete skill provides:
    - System prompt: injected into the Coder's context
    - Workflow steps: ordered instructions
    - Checklist template: TODO items
    - Example prompts: few-shot examples
    - Forbidden actions: skill-specific constraints
    """

    name: str
    description: str
    example_prompts: list[str]
    forbidden_actions: list[str]

    @abstractmethod
    def get_system_prompt(self, context: SkillContext) -> str:
        """Return the system prompt for the Coder agent."""

    @abstractmethod
    def get_workflow_steps(self) -> list[str]:
        """Return ordered workflow steps for the Coder."""

    @abstractmethod
    def get_checklist_template(self, context: SkillContext) -> list[str]:
        """Return a TODO checklist template."""


class SkillRegistry:
    """Maps task classification types to Skill instances.

    Orchestrator queries this after classification to get the
    right skill for the task type.
    """

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, task_type: str, skill: Skill) -> None:
        """Register a skill for a given task type.

        Args:
            task_type: The classification type (e.g., 'bug_fix').
            skill: The skill instance to register.
        """
        self._skills[task_type] = skill

    def get(self, task_type: str) -> Skill | None:
        """Get a skill by task type.

        Args:
            task_type: The classification type to look up.

        Returns:
            The Skill instance, or None if not registered.
        """
        return self._skills.get(task_type)

    def list_types(self) -> list[str]:
        """List all registered task types."""
        return list(self._skills.keys())
