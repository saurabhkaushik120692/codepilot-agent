"""Tests for the Orchestrator agent."""

from unittest.mock import AsyncMock, patch

import pytest

from codepilot.agents.orchestrator import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    Orchestrator,
)
from codepilot.config import Config
from codepilot.core.agent_factory import DeepAgentFactory
from codepilot.core.base_agent import AgentResult, BaseAgent
from codepilot.core.llm_provider import LLMProvider
from codepilot.core.tool_registry import ToolRegistry


@pytest.fixture
def config():
    return Config(
        _env_file=None,
        anthropic_api_key="test-key",
        openai_api_key="test-key",
        google_api_key="test-key",
    )


@pytest.fixture
def mock_agent():
    """A mock BaseAgent that returns predictable results."""
    agent = AsyncMock(spec=BaseAgent)
    agent.name = "Orchestrator"
    agent.invoke.return_value = AgentResult(
        success=True,
        output="I will create a TODO list for this task.",
        todos=[
            "Analyze the issue",
            "Find relevant files",
            "Implement fix",
        ],
    )
    return agent


class TestOrchestratorCreation:
    """Test Orchestrator creation."""

    def test_create_with_mock_agent(
        self, mock_agent, config
    ):
        orchestrator = Orchestrator(
            agent=mock_agent, config=config
        )
        assert orchestrator._agent == mock_agent

    @patch(
        "codepilot.core.agent_factory"
        ".DEEPAGENTS_AVAILABLE",
        False,
    )
    def test_create_via_factory(self, config):
        factory = DeepAgentFactory(
            config, LLMProvider(config), ToolRegistry()
        )
        orchestrator = Orchestrator.create(factory, config)
        assert orchestrator is not None


class TestOrchestratorSystemPrompt:
    """Test the system prompt content."""

    def test_prompt_mentions_write_todos(self):
        assert "write_todos" in ORCHESTRATOR_SYSTEM_PROMPT

    def test_prompt_mentions_subagents(self):
        assert "Repo Explorer" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "Coder" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "Test Agent" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "PR Agent" in ORCHESTRATOR_SYSTEM_PROMPT

    def test_prompt_mentions_state_machine(self):
        assert "TRIAGED" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "DONE" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "FAILED" in ORCHESTRATOR_SYSTEM_PROMPT


class TestOrchestratorHandleMessage:
    """Test message handling."""

    @pytest.mark.asyncio
    async def test_handle_message_returns_result(
        self, mock_agent, config
    ):
        orchestrator = Orchestrator(
            agent=mock_agent, config=config
        )
        result = await orchestrator.handle_message(
            "Fix the division by zero bug"
        )
        assert isinstance(result, AgentResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_handle_message_passes_to_agent(
        self, mock_agent, config
    ):
        orchestrator = Orchestrator(
            agent=mock_agent, config=config
        )
        await orchestrator.handle_message(
            "Add modulo operation"
        )
        mock_agent.invoke.assert_called_once()
        # Verify the message was passed correctly
        call_args = mock_agent.invoke.call_args
        messages = call_args[0][0]
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Add modulo operation"

    @pytest.mark.asyncio
    async def test_handle_message_with_todos(
        self, mock_agent, config
    ):
        orchestrator = Orchestrator(
            agent=mock_agent, config=config
        )
        result = await orchestrator.handle_message(
            "Fix a bug"
        )
        assert len(result.todos) == 3
        assert "Analyze the issue" in result.todos


class TestStartupFlow:
    """Test the full startup sequence."""

    @patch(
        "codepilot.core.agent_factory"
        ".DEEPAGENTS_AVAILABLE",
        False,
    )
    @pytest.mark.asyncio
    async def test_startup_returns_orchestrator(self):
        from codepilot.main import startup

        orchestrator = await startup()
        assert isinstance(orchestrator, Orchestrator)
