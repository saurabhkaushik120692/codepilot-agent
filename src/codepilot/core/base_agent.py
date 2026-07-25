"""Base agent interface and core data types.

This module defines the contract that ALL CodePilot agents implement.
No deepagents types appear here — this is the abstraction boundary.

If we ever swap deepagents for raw LangGraph, only the agent_factory.py
needs to change. Everything else depends on these types.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator


class AgentEventType(str, Enum):
    """Types of events an agent can emit during streaming."""

    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    MESSAGE = "message"
    TODO_UPDATE = "todo_update"
    ERROR = "error"
    DONE = "done"


@dataclass
class AgentEvent:
    """A single event emitted during agent streaming.

    Attributes:
        type: The kind of event (thinking, tool_call, message, etc.)
        agent_name: Which agent emitted this event.
        content: The event payload (text content, tool output, etc.)
        metadata: Optional extra data (tool name, error details, etc.)
    """

    type: AgentEventType
    agent_name: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """The final result of an agent invocation.

    Attributes:
        success: Whether the agent completed its task successfully.
        output: The agent's final text output.
        tool_calls_made: Record of tools the agent used.
        todos: Checklist items from write_todos calls.
        metadata: Optional extra data.
    """

    success: bool
    output: str
    tool_calls_made: list[dict[str, Any]] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Abstract base for all CodePilot agents.

    All agents interact through this interface — never through
    deepagents types directly. This is the abstraction boundary.

    Subclasses must implement: invoke(), stream(), spawn_subagent().
    """

    def __init__(self, name: str, config: Any):
        """Initialize with agent name and config.

        Args:
            name: Human-readable agent name (e.g., "Orchestrator", "Coder").
            config: Config instance — typed as Any here to avoid circular imports.
        """
        self.name = name
        self.config = config

    @abstractmethod
    async def invoke(
        self, messages: list[dict], context: dict | None = None
    ) -> AgentResult:
        """Run the agent to completion and return the final result.

        Args:
            messages: List of message dicts (role + content).
            context: Optional context dict (working memory, file paths, etc.)
        """
        ...

    @abstractmethod
    async def stream(
        self, messages: list[dict], context: dict | None = None
    ) -> AsyncIterator[AgentEvent]:
        """Run the agent and yield events as they occur.

        Args:
            messages: List of message dicts (role + content).
            context: Optional context dict.
        """
        ...

    @abstractmethod
    async def spawn_subagent(
        self, task: str, agent_type: str, **kwargs: Any
    ) -> "BaseAgent":
        """Create and return a subagent for delegated work.

        Args:
            task: Description of the task to delegate.
            agent_type: Type of subagent (e.g., "coder", "test_agent").
            **kwargs: Additional config for the subagent.
        """
        ...
