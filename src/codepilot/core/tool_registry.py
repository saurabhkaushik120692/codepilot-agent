"""Centralized tool registration and management.

The ToolRegistry is where:
- Tools are registered by name with their handler functions
- Tools are assigned to agent roles (orchestrator, coder, etc.)
- Tools are flagged for guardrail wrapping (sensitive operations)
- The AgentFactory queries to get tools for each agent it creates
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """Definition of a tool available to agents.

    Attributes:
        name: Unique tool identifier (e.g., 'read_file').
        description: Human-readable description for the LLM.
        handler: Async function that implements the tool.
        parameters: JSON schema for tool parameters.
        requires_guardrail: If True, guardrail wrapper is
            injected before handler.
        requires_approval: If True, HITL approval is needed
            before execution.
    """

    name: str
    description: str
    handler: Callable[..., Awaitable[Any]]
    parameters: dict[str, Any] = field(default_factory=dict)
    requires_guardrail: bool = False
    requires_approval: bool = False


class ToolNotFoundError(Exception):
    """Raised when a requested tool is not registered."""


class ToolRegistry:
    """Centralized tool registration and role-based access.

    Usage:
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="read_file", ...))
        registry.register_role_tools("coder", ["read_file"])
        tools = registry.get_tools_for_role("coder")
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._role_tools: dict[str, list[str]] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool. Overwrites if name exists."""
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool: {tool.name}")
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def get_tool(self, name: str) -> ToolDefinition:
        """Get a tool by name.

        Raises:
            ToolNotFoundError: If the tool is not registered.
        """
        if name not in self._tools:
            raise ToolNotFoundError(f"Tool not found: {name}")
        return self._tools[name]

    def register_role_tools(self, role: str, tool_names: list[str]) -> None:
        """Assign a list of tool names to an agent role.

        Args:
            role: Agent role (e.g., 'orchestrator', 'coder').
            tool_names: List of registered tool names this
                role can use.
        """
        self._role_tools[role] = tool_names
        logger.debug(f"Role '{role}' assigned tools: {tool_names}")

    def get_tools_for_role(self, role: str) -> list[ToolDefinition]:
        """Get all tool definitions for a given role.

        Returns an empty list for unregistered roles.
        """
        tool_names = self._role_tools.get(role, [])
        tools = []
        for name in tool_names:
            try:
                tools.append(self.get_tool(name))
            except ToolNotFoundError:
                logger.warning(f"Role '{role}' references unregistered tool: {name}")
        return tools

    def list_all(self) -> list[str]:
        """Return all registered tool names."""
        return list(self._tools.keys())

    def list_roles(self) -> list[str]:
        """Return all registered roles."""
        return list(self._role_tools.keys())
