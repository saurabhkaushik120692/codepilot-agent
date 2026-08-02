"""Tests for the Meta Test Agent."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from codepilot.agents.meta_test_agent import (
    INFRA_FAILURE_PATTERNS,
    META_TEST_AGENT_PROMPT,
    MetaTestAgent,
    TestFailureType,
)
from codepilot.config import Config
from codepilot.core.base_agent import AgentResult, BaseAgent
from codepilot.guardrails.command_filter import CommandFilter
from codepilot.guardrails.file_filter import FileFilter
from codepilot.sandbox.manager import SandboxManager


@pytest.fixture
def config():
    return Config(_env_file=None)


@pytest.fixture
def mock_agent():
    agent = AsyncMock(spec=BaseAgent)
    agent.invoke.return_value = AgentResult(success=True, output="Fixed import error")
    return agent


@pytest.fixture
def mock_sandbox():
    return MagicMock(spec=SandboxManager)


@pytest.fixture
def mock_cmd_filter():
    return MagicMock(spec=CommandFilter)


@pytest.fixture
def mock_file_filter():
    return MagicMock(spec=FileFilter)


class TestMetaTestAgent:
    """Test self-healing test agent."""

    def test_classify_infra_failure(self):
        output = "ModuleNotFoundError: No module named 'nonexistent'"
        assert (
            MetaTestAgent.classify_failure(output)
            == TestFailureType.INFRASTRUCTURE_FAILURE
        )

    def test_classify_import_error(self):
        output = "ImportError: cannot import name 'Foo' from 'bar'"
        assert (
            MetaTestAgent.classify_failure(output)
            == TestFailureType.INFRASTRUCTURE_FAILURE
        )

    def test_classify_syntax_error(self):
        output = "SyntaxError: invalid syntax in test_foo.py"
        assert (
            MetaTestAgent.classify_failure(output)
            == TestFailureType.INFRASTRUCTURE_FAILURE
        )

    def test_classify_assertion_failure(self):
        output = (
            "1 passed, 2 failed in 0.5s\nFAILED test_foo.py::test_bar - assert 1 == 2"
        )
        assert (
            MetaTestAgent.classify_failure(output) == TestFailureType.ASSERTION_FAILURE
        )

    def test_classify_internal_error(self):
        output = "INTERNALERROR> some traceback"
        assert (
            MetaTestAgent.classify_failure(output)
            == TestFailureType.INFRASTRUCTURE_FAILURE
        )

    @pytest.mark.asyncio
    async def test_self_heal_success(
        self, config, mock_agent, mock_sandbox, mock_cmd_filter, mock_file_filter
    ):
        agent = MetaTestAgent(
            mock_agent, config, mock_sandbox, mock_cmd_filter, mock_file_filter
        )
        result = await agent.self_heal(
            error_output="ModuleNotFoundError: No module named 'foo'",
            test_files=["tests/test_calc.py"],
            sandbox_path="/tmp/sandbox/42",
        )
        assert result is True
        mock_agent.invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_self_heal_failure(
        self, config, mock_agent, mock_sandbox, mock_cmd_filter, mock_file_filter
    ):
        mock_agent.invoke.side_effect = Exception("LLM error")
        agent = MetaTestAgent(
            mock_agent, config, mock_sandbox, mock_cmd_filter, mock_file_filter
        )
        result = await agent.self_heal(
            error_output="error",
            test_files=["tests/test_calc.py"],
            sandbox_path="/tmp/sandbox/42",
        )
        assert result is False


class TestMetaTestAgentPrompt:
    def test_prompt_mentions_infra(self):
        assert "INFRASTRUCTURE" in META_TEST_AGENT_PROMPT

    def test_infra_patterns_non_empty(self):
        assert len(INFRA_FAILURE_PATTERNS) > 0
        assert "ImportError" in INFRA_FAILURE_PATTERNS
