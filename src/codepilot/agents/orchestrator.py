"""Orchestrator — the root agent that manages the task lifecycle.

The Orchestrator:
1. Receives tasks (from GitHub issues or manual input)
2. Creates a TODO checklist via write_todos
3. Delegates work to subagents (Repo Explorer, Coder, etc.)
4. Monitors progress through the state machine
5. Handles failures and retries

It uses BaseAgent (via AgentFactory) — never touches
deepagents directly.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from codepilot.config import Config
from codepilot.core.base_agent import AgentResult, BaseAgent

if TYPE_CHECKING:
    from codepilot.core.agent_factory import DeepAgentFactory

logger = logging.getLogger(__name__)

ORCHESTRATOR_SYSTEM_PROMPT = """\
You are the Orchestrator agent for CodePilot, \
a multi-agent coding platform.

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
   TRIAGED → EXPLORING → IMPLEMENTING → TESTING \
→ PR_OPENED → DONE | FAILED

Always start by creating a TODO checklist using \
write_todos before delegating work.
"""


class Orchestrator:
    """Root orchestrator for CodePilot.

    Manages the task lifecycle from triage to PR creation.
    Uses the BaseAgent interface — never touches deepagents.
    """

    def __init__(
        self, agent: BaseAgent, config: Config
    ):
        self._agent = agent
        self._config = config
        logger.info("Orchestrator initialized")

    @classmethod
    def create(
        cls,
        factory: "DeepAgentFactory",
        config: Config,
    ) -> "Orchestrator":
        """Create an Orchestrator using the agent factory.

        Args:
            factory: The agent factory (creates the
                underlying agent).
            config: Application configuration.
        """
        agent = factory.create_orchestrator()
        return cls(agent=agent, config=config)

    async def handle_message(
        self, message: str
    ) -> AgentResult:
        """Process a single message through the orchestrator.

        Args:
            message: The user message or task description.

        Returns:
            AgentResult with the orchestrator's response.
        """
        logger.info(
            "Orchestrator handling message: "
            f"{message[:100]}..."
        )
        messages = [
            {"role": "user", "content": message}
        ]
        result = await self._agent.invoke(messages)
        logger.info(
            "Orchestrator result: "
            f"success={result.success}"
        )
        return result

    async def start_idle_loop(self) -> None:
        """Enter the idle loop waiting for tasks.

        In Phase 1, this just logs and returns.
        Phase 2 will add issue polling here.
        """
        logger.info(
            "Orchestrator idle — waiting for tasks..."
        )
        logger.info(
            "(Issue polling will be added in Phase 2)"
        )
