"""Agent factory — the bridge between our abstraction and deepagents.

THIS IS THE ONLY FILE THAT IMPORTS DEEPAGENTS.

If deepagents breaks or we want to swap to raw LangGraph, replace
this single file with a LangGraphFactory. No other code changes.
"""

import logging
from typing import Any, AsyncIterator

from codepilot.config import Config
from codepilot.core.base_agent import (
    AgentEvent,
    AgentEventType,
    AgentResult,
    BaseAgent,
)
from codepilot.core.llm_provider import LLMProvider
from codepilot.core.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

# --- deepagents imports (ONLY HERE) ---
try:
    from deepagents.agents import create_deep_agent

    DEEPAGENTS_AVAILABLE = True
except ImportError:
    logger.warning("deepagents not installed — using mock agent")
    DEEPAGENTS_AVAILABLE = False


class DeepAgent(BaseAgent):
    """Concrete agent backed by deepagents.

    Translates between our BaseAgent interface and the
    deepagents API. All deepagents types are converted to
    AgentResult/AgentEvent at this boundary.
    """

    def __init__(
        self,
        name: str,
        config: Config,
        deep_agent_instance: Any,
        tool_registry: ToolRegistry,
        llm_provider: LLMProvider,
        factory: "DeepAgentFactory",
    ):
        super().__init__(name, config)
        self._agent = deep_agent_instance
        self._tool_registry = tool_registry
        self._llm_provider = llm_provider
        self._factory = factory

    async def invoke(
        self,
        messages: list[dict],
        context: dict | None = None,
    ) -> AgentResult:
        """Run the deepagents agent and translate result."""
        try:
            # Build the prompt from messages
            prompt = "\n".join(
                f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages
            )

            # Run through deepagents
            if self._agent is not None:
                result = await self._agent.ainvoke(prompt)
                return AgentResult(
                    success=True,
                    output=str(result) if result else "",
                    metadata={"agent_name": self.name},
                )
            else:
                # Mock mode when deepagents isn't available
                return AgentResult(
                    success=True,
                    output=(f"[{self.name}] Mock response — deepagents not available"),
                    metadata={
                        "agent_name": self.name,
                        "mock": True,
                    },
                )
        except Exception as e:
            logger.error(f"Agent {self.name} invoke failed: {e}")
            return AgentResult(
                success=False,
                output=str(e),
                metadata={
                    "agent_name": self.name,
                    "error": str(e),
                },
            )

    async def stream(
        self,
        messages: list[dict],
        context: dict | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Stream events from the agent."""
        yield AgentEvent(
            type=AgentEventType.THINKING,
            agent_name=self.name,
            content=f"{self.name} is processing...",
        )

        result = await self.invoke(messages, context)

        yield AgentEvent(
            type=AgentEventType.MESSAGE,
            agent_name=self.name,
            content=result.output,
        )

        yield AgentEvent(
            type=AgentEventType.DONE,
            agent_name=self.name,
            content="Complete",
            metadata={"success": result.success},
        )

    async def spawn_subagent(
        self, task: str, agent_type: str, **kwargs: Any
    ) -> BaseAgent:
        """Spawn a subagent using the factory."""
        return self._factory.create_agent(
            name=f"{self.name}/{agent_type}",
            system_prompt=task,
            role=agent_type,
        )


class DeepAgentFactory:
    """Factory for creating agents through deepagents.

    This is the abstraction boundary. If deepagents breaks,
    replace this class with LangGraphFactory — nothing else
    changes.
    """

    def __init__(
        self,
        config: Config,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
    ):
        self._config = config
        self._llm_provider = llm_provider
        self._tool_registry = tool_registry

    def create_agent(
        self,
        name: str,
        system_prompt: str,
        role: str,
        tools: list[str] | None = None,
    ) -> BaseAgent:
        """Create an agent with the specified role and tools.

        Args:
            name: Human-readable agent name.
            system_prompt: The system prompt for the agent.
            role: Agent role (used to look up tools).
            tools: Optional explicit tool list (overrides
                role-based lookup).
        """
        deep_agent = None

        if DEEPAGENTS_AVAILABLE:
            try:
                llm = self._llm_provider.get_primary()
                role_tools = self._tool_registry.get_tools_for_role(role)

                deep_agent = create_deep_agent(
                    model=llm,
                    task=system_prompt,
                    tools=([t.handler for t in role_tools] if role_tools else None),
                )
                logger.info(f"Created deepagents agent: {name} (role={role})")
            except Exception as e:
                logger.warning(
                    f"Failed to create deepagents agent "
                    f"'{name}': {e}. "
                    "Falling back to mock agent."
                )
        else:
            logger.info(f"Created mock agent: {name} (deepagents not available)")

        return DeepAgent(
            name=name,
            config=self._config,
            deep_agent_instance=deep_agent,
            tool_registry=self._tool_registry,
            llm_provider=self._llm_provider,
            factory=self,
        )

    def create_orchestrator(self) -> BaseAgent:
        """Create the Orchestrator agent.

        Convenience method — the Orchestrator always uses
        the same system prompt and role.
        """
        from codepilot.agents.orchestrator import (
            ORCHESTRATOR_SYSTEM_PROMPT,
        )

        return self.create_agent(
            name="Orchestrator",
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            role="orchestrator",
        )
