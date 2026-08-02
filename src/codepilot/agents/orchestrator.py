"""Orchestrator — the root agent that manages the task lifecycle.

The Orchestrator:
1. Receives tasks (from GitHub issues or manual input)
2. Loads the appropriate skill based on classification type
3. Queries episodic + semantic memory for context
4. Spawns Repo Explorer → Coder → Test Agent
5. Stores lessons and session summaries
6. Transitions through the state machine

It uses BaseAgent (via AgentFactory) — never touches deepagents directly.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from codepilot.config import Config
from codepilot.core.base_agent import AgentResult, BaseAgent
from codepilot.memory.working import (
    InvalidTransitionError,
    TaskState,
    WorkingMemory,
)

if TYPE_CHECKING:
    from codepilot.core.agent_factory import DeepAgentFactory
    from codepilot.memory.episodic import EpisodicMemory
    from codepilot.memory.semantic import SemanticMemory
    from codepilot.skills.base import SkillRegistry

logger = logging.getLogger(__name__)

ORCHESTRATOR_SYSTEM_PROMPT = """\
You are the Orchestrator agent for CodePilot, a multi-agent coding platform.

Your responsibilities:
1. Receive tasks (from GitHub issues or manual input)
2. Decompose tasks into actionable steps using write_todos
3. Delegate work to specialized subagents:
   - Repo Explorer: find relevant files in the repository
   - Coder: implement changes in a sandboxed environment
   - Test Agent: run and verify tests
   - PR Agent: create pull requests
4. Monitor progress and handle failures
5. Maintain task state through the state machine:
   TRIAGED → EXPLORING → IMPLEMENTING → TESTING → PR_OPENED → DONE | FAILED

Always start by creating a TODO checklist using write_todos before delegating work.
"""


class Orchestrator:
    """Root orchestrator for CodePilot.

    Manages the task lifecycle from triage to PR creation.
    Uses the BaseAgent interface — never touches deepagents directly.
    """

    def __init__(
        self,
        agent: BaseAgent,
        config: Config,
        skill_registry: SkillRegistry | None = None,
        episodic: EpisodicMemory | None = None,
        semantic: SemanticMemory | None = None,
    ):
        self._agent = agent
        self._config = config
        self._skill_registry = skill_registry
        self._episodic = episodic
        self._semantic = semantic
        self._active_tasks: dict[int, WorkingMemory] = {}
        logger.info("Orchestrator initialized")

    @classmethod
    def create(cls, factory: "DeepAgentFactory", config: Config) -> "Orchestrator":
        """Create an Orchestrator using the agent factory."""
        agent = factory.create_orchestrator()
        return cls(agent=agent, config=config)

    async def handle_message(
        self, message: str, issue_id: int | None = None
    ) -> AgentResult:
        """Process a single message through the orchestrator.

        Creates a new WorkingMemory entry for new tasks and tracks
        state through the lifecycle.

        Args:
            message: The user message or task description.
            issue_id: Optional GitHub issue ID for tracking.

        Returns:
            AgentResult with the orchestrator's response.
        """
        task_id = issue_id or hash(message) % 100000
        if task_id not in self._active_tasks:
            self._active_tasks[task_id] = WorkingMemory(issue_id=task_id)
            logger.info(f"Created new task {task_id}: {message[:80]}...")

        wm = self._active_tasks[task_id]

        logger.info(
            f"Orchestrator handling message (task={task_id}, state={wm.state.value})"
        )

        if self._skill_registry:
            skill = self._skill_registry.get(self._get_task_type_from_message(message))
            if skill:
                logger.info(f"Loaded skill: {skill.name}")
        else:
            skill = None

        if self._episodic and issue_id:
            session = await self._episodic.get_session_for_issue(issue_id)
            if session:
                logger.info(f"Previous attempt found for issue #{issue_id}")

        messages = [{"role": "user", "content": message}]
        result = await self._agent.invoke(messages)

        if result.success:
            try:
                wm.transition_to(TaskState.EXPLORING)
            except InvalidTransitionError:
                pass

        logger.info(f"Orchestrator result: success={result.success}")
        return result

    def _get_task_type_from_message(self, message: str) -> str:
        """Extract task type from a message (simple heuristic)."""
        msg_lower = message.lower()
        if "bug" in msg_lower or "fix" in msg_lower:
            return "bug_fix"
        if "feature" in msg_lower or "add" in msg_lower:
            return "feature_addition"
        if "update" in msg_lower or "upgrade" in msg_lower or "bump" in msg_lower:
            return "dependency_update"
        if "document" in msg_lower or "docstring" in msg_lower or "readme" in msg_lower:
            return "documentation"
        if "config" in msg_lower or "setting" in msg_lower:
            return "config_change"
        return "bug_fix"

    def get_task_state(self, task_id: int) -> TaskState | None:
        """Get the current state of a task."""
        wm = self._active_tasks.get(task_id)
        return wm.state if wm else None

    def transition_task(self, task_id: int, new_state: TaskState) -> bool:
        """Attempt to transition a task to a new state.

        Returns True if the transition was valid and applied.
        """
        wm = self._active_tasks.get(task_id)
        if not wm:
            logger.warning(f"Cannot transition unknown task {task_id}")
            return False
        try:
            wm.transition_to(new_state)
            logger.info(f"Task {task_id} → {new_state.value}")
            return True
        except InvalidTransitionError as e:
            logger.warning(f"Invalid transition for task {task_id}: {e}")
            return False

    def fail_task(self, task_id: int, reason: str = "") -> None:
        """Mark a task as failed with an optional reason."""
        wm = self._active_tasks.get(task_id)
        if wm:
            wm.state = TaskState.FAILED
            wm.failure_reason = reason
            logger.info(f"Task {task_id} failed: {reason}")

    async def start_idle_loop(self) -> None:
        """Enter the idle loop waiting for tasks."""
        logger.info("Orchestrator idle — waiting for tasks...")

    def get_active_tasks(self) -> dict[int, WorkingMemory]:
        """Return all active task memory entries."""
        return dict(self._active_tasks)
