"""Tests for the tool registry."""

import pytest

from codepilot.core.tool_registry import (
    ToolDefinition,
    ToolNotFoundError,
    ToolRegistry,
)


async def mock_handler(**kwargs):
    """Dummy async handler for testing."""
    return "ok"


@pytest.fixture
def registry():
    return ToolRegistry()


@pytest.fixture
def sample_tool():
    return ToolDefinition(
        name="read_file",
        description="Read contents of a file",
        handler=mock_handler,
    )


class TestToolRegistration:
    """Test registering and retrieving tools."""

    def test_register_and_get(self, registry, sample_tool):
        registry.register(sample_tool)
        retrieved = registry.get_tool("read_file")
        assert retrieved.name == "read_file"
        assert retrieved.description == "Read contents of a file"

    def test_get_unknown_tool_raises(self, registry):
        with pytest.raises(
            ToolNotFoundError,
            match="Tool not found: unknown",
        ):
            registry.get_tool("unknown")

    def test_duplicate_registration_overwrites(
        self, registry
    ):
        tool_v1 = ToolDefinition(
            name="x",
            description="v1",
            handler=mock_handler,
        )
        tool_v2 = ToolDefinition(
            name="x",
            description="v2",
            handler=mock_handler,
        )
        registry.register(tool_v1)
        registry.register(tool_v2)
        assert registry.get_tool("x").description == "v2"

    def test_list_all(self, registry, sample_tool):
        registry.register(sample_tool)
        registry.register(
            ToolDefinition(
                name="execute",
                description="Run command",
                handler=mock_handler,
            )
        )
        assert sorted(registry.list_all()) == [
            "execute",
            "read_file",
        ]


class TestRoleTools:
    """Test role-based tool assignment."""

    def test_assign_and_retrieve_role_tools(
        self, registry, sample_tool
    ):
        registry.register(sample_tool)
        registry.register_role_tools("coder", ["read_file"])
        tools = registry.get_tools_for_role("coder")
        assert len(tools) == 1
        assert tools[0].name == "read_file"

    def test_unknown_role_returns_empty(self, registry):
        tools = registry.get_tools_for_role("nonexistent")
        assert tools == []

    def test_role_with_missing_tool_skips_it(
        self, registry
    ):
        registry.register_role_tools(
            "coder", ["read_file", "nonexistent"]
        )
        registry.register(
            ToolDefinition(
                name="read_file",
                description="Read",
                handler=mock_handler,
            )
        )
        tools = registry.get_tools_for_role("coder")
        # Only read_file, nonexistent skipped
        assert len(tools) == 1

    def test_list_roles(self, registry):
        registry.register_role_tools(
            "coder", ["read_file"]
        )
        registry.register_role_tools(
            "orchestrator", ["write_todos"]
        )
        assert sorted(registry.list_roles()) == [
            "coder",
            "orchestrator",
        ]


class TestToolFlags:
    """Test guardrail and approval flags."""

    def test_guardrail_flag(self, registry):
        tool = ToolDefinition(
            name="execute",
            description="Run a command",
            handler=mock_handler,
            requires_guardrail=True,
        )
        registry.register(tool)
        assert (
            registry.get_tool("execute").requires_guardrail
            is True
        )

    def test_approval_flag(self, registry):
        tool = ToolDefinition(
            name="git_push",
            description="Push to remote",
            handler=mock_handler,
            requires_approval=True,
        )
        registry.register(tool)
        assert (
            registry.get_tool("git_push").requires_approval
            is True
        )

    def test_default_flags_are_false(
        self, registry, sample_tool
    ):
        registry.register(sample_tool)
        tool = registry.get_tool("read_file")
        assert tool.requires_guardrail is False
        assert tool.requires_approval is False
