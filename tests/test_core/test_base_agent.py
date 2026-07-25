"""Tests for base agent interface and core data types."""

import pytest

from codepilot.core.base_agent import (
    AgentEvent,
    AgentEventType,
    AgentResult,
    BaseAgent,
)


class TestAgentResult:
    """Tests for the AgentResult dataclass."""

    def test_create_with_required_fields(self):
        result = AgentResult(success=True, output="done")
        assert result.success is True
        assert result.output == "done"

    def test_defaults_for_optional_fields(self):
        result = AgentResult(success=True, output="done")
        assert result.tool_calls_made == []
        assert result.todos == []
        assert result.metadata == {}

    def test_create_with_all_fields(self):
        result = AgentResult(
            success=False,
            output="failed",
            tool_calls_made=[{"name": "read_file", "args": {"path": "x.py"}}],
            todos=["Fix bug", "Add test"],
            metadata={"retry_count": 2},
        )
        assert result.success is False
        assert len(result.tool_calls_made) == 1
        assert len(result.todos) == 2
        assert result.metadata["retry_count"] == 2


class TestAgentEvent:
    """Tests for the AgentEvent dataclass."""

    def test_create_event(self):
        event = AgentEvent(
            type=AgentEventType.MESSAGE,
            agent_name="Orchestrator",
            content="Planning task...",
        )
        assert event.type == AgentEventType.MESSAGE
        assert event.agent_name == "Orchestrator"
        assert event.content == "Planning task..."

    def test_event_metadata_defaults_to_empty(self):
        event = AgentEvent(
            type=AgentEventType.THINKING,
            agent_name="Coder",
            content="Analyzing...",
        )
        assert event.metadata == {}

    def test_all_event_types_are_strings(self):
        """AgentEventType values should be usable as plain strings."""
        assert AgentEventType.THINKING == "thinking"
        assert AgentEventType.TOOL_CALL == "tool_call"
        assert AgentEventType.DONE == "done"


class TestBaseAgent:
    """Tests for the BaseAgent abstract class."""

    def test_cannot_instantiate_directly(self):
        """BaseAgent is abstract — instantiation must fail."""
        with pytest.raises(TypeError):
            BaseAgent("test", None)

    def test_subclass_missing_methods_fails(self):
        """A subclass that doesn't implement all abstract methods
            can't be instantiated."""

        class IncompleteAgent(BaseAgent):
            async def invoke(self, messages, context=None):
                return AgentResult(success=True, output="ok")
            # Missing: stream() and spawn_subagent()

        with pytest.raises(TypeError):
            IncompleteAgent("test", None)

    def test_complete_subclass_works(self):
        """A subclass implementing all methods can be instantiated."""

        class FakeAgent(BaseAgent):
            async def invoke(self, messages, context=None):
                return AgentResult(success=True, output="ok")

            async def stream(self, messages, context=None):
                yield AgentEvent(
                    type=AgentEventType.DONE,
                    agent_name=self.name,
                    content="done",
                )

            async def spawn_subagent(self, task, agent_type, **kwargs):
                return FakeAgent("sub", self.config)

        agent = FakeAgent("test-agent", None)
        assert agent.name == "test-agent"
