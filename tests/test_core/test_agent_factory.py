"""Tests for the agent factory — deepagents is mocked."""

from unittest.mock import AsyncMock, patch

import pytest

from codepilot.config import Config
from codepilot.core.agent_factory import (
    DeepAgent,
    DeepAgentFactory,
)
from codepilot.core.base_agent import (
    AgentEventType,
    AgentResult,
    BaseAgent,
)
from codepilot.core.llm_provider import LLMProvider
from codepilot.core.tool_registry import ToolRegistry


@pytest.fixture
def config():
    return Config(
        _env_file=None,
        anthropic_api_key="test-key",
        openai_api_key="test-key",
        google_api_key="test-key",
        groq_api_key="test-key",
    )


@pytest.fixture
def llm_provider(config):
    return LLMProvider(config)


@pytest.fixture
def tool_registry():
    return ToolRegistry()


@pytest.fixture
def factory(config, llm_provider, tool_registry):
    return DeepAgentFactory(config, llm_provider, tool_registry)


class TestDeepAgentFactory:
    """Test the factory creates agents correctly."""

    @patch(
        "codepilot.core.agent_factory.DEEPAGENTS_AVAILABLE",
        False,
    )
    def test_creates_mock_agent_when_unavailable(self, factory):
        agent = factory.create_agent(
            name="TestAgent",
            system_prompt="You are a test agent.",
            role="test",
        )
        assert isinstance(agent, BaseAgent)
        assert agent.name == "TestAgent"

    @patch(
        "codepilot.core.agent_factory.DEEPAGENTS_AVAILABLE",
        False,
    )
    def test_create_orchestrator(self, factory):
        # Need orchestrator module — tested in Step 7
        # For now, test the generic create_agent
        agent = factory.create_agent(
            name="Orchestrator",
            system_prompt="You are the orchestrator.",
            role="orchestrator",
        )
        assert agent.name == "Orchestrator"


class TestDeepAgent:
    """Test the DeepAgent concrete implementation."""

    @pytest.fixture
    def mock_agent(self, config, tool_registry, llm_provider, factory):
        return DeepAgent(
            name="TestAgent",
            config=config,
            deep_agent_instance=None,  # Mock mode
            tool_registry=tool_registry,
            llm_provider=llm_provider,
            factory=factory,
        )

    @pytest.mark.asyncio
    async def test_invoke_returns_agent_result(self, mock_agent):
        result = await mock_agent.invoke([{"role": "user", "content": "hello"}])
        assert isinstance(result, AgentResult)
        assert result.success is True
        assert "Mock response" in result.output

    @pytest.mark.asyncio
    async def test_stream_yields_events(self, mock_agent):
        events = []
        async for event in mock_agent.stream([{"role": "user", "content": "hi"}]):
            events.append(event)

        assert len(events) == 3
        assert events[0].type == AgentEventType.THINKING
        assert events[1].type == AgentEventType.MESSAGE
        assert events[2].type == AgentEventType.DONE

    @pytest.mark.asyncio
    async def test_spawn_subagent(self, mock_agent):
        sub = await mock_agent.spawn_subagent(
            task="Fix the bug",
            agent_type="coder",
        )
        assert isinstance(sub, BaseAgent)
        assert "coder" in sub.name

    @pytest.mark.asyncio
    async def test_invoke_with_real_deepagent(
        self,
        config,
        tool_registry,
        llm_provider,
        factory,
    ):
        """Test that a real deepagents instance is called."""
        mock_deep = AsyncMock()
        mock_deep.ainvoke.return_value = "Fixed the bug!"

        agent = DeepAgent(
            name="TestAgent",
            config=config,
            deep_agent_instance=mock_deep,
            tool_registry=tool_registry,
            llm_provider=llm_provider,
            factory=factory,
        )

        result = await agent.invoke([{"role": "user", "content": "Fix the bug"}])
        assert result.success is True
        assert result.output == "Fixed the bug!"
        mock_deep.ainvoke.assert_called_once()
