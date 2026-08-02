"""Tests for the Test Agent."""  # noqa: E501

from unittest.mock import AsyncMock, MagicMock

import pytest

from codepilot.agents.test_agent import TEST_AGENT_SYSTEM_PROMPT, TestAgent
from codepilot.config import Config
from codepilot.core.base_agent import BaseAgent
from codepilot.guardrails.command_filter import CommandFilter
from codepilot.memory.working import TestResult
from codepilot.sandbox.manager import SandboxManager


@pytest.fixture
def config():
    return Config(_env_file=None)


@pytest.fixture
def mock_agent():
    return AsyncMock(spec=BaseAgent)


@pytest.fixture
def mock_sandbox():
    sandbox = MagicMock(spec=SandboxManager)
    sandbox.execute = AsyncMock(
        return_value=(
            "============================= test session starts ================\n"
            "tests/test_calc.py::test_add PASSED                              [ 33%]\n"
            "tests/test_calc.py::test_sub PASSED                              [ 66%]\n"
            "tests/test_calc.py::test_div PASSED                              [100%]\n\n"
            "============================== 3 passed in 0.12s ==================",
            0,
        )
    )
    return sandbox


@pytest.fixture
def mock_command_filter():
    return MagicMock(spec=CommandFilter)


class TestTestAgent:
    """Test the Test Agent."""

    @pytest.mark.asyncio
    async def test_run_tests_returns_test_result(
        self, config, mock_agent, mock_sandbox, mock_command_filter
    ):
        agent = TestAgent(mock_agent, config, mock_sandbox, mock_command_filter)
        result = await agent.run_tests("/tmp/sandbox/42")
        assert isinstance(result, TestResult)
        assert result.passed == 3
        assert result.failed == 0
        assert result.errors == 0

    @pytest.mark.asyncio
    async def test_parse_pytest_failures(
        self, config, mock_agent, mock_sandbox, mock_command_filter
    ):
        mock_sandbox.execute = AsyncMock(
            return_value=(
                "tests/test_calc.py::test_add PASSED                          [ 33%]\n"
                "tests/test_calc.py::test_div FAILED                          [ 66%]\n"
                "tests/test_calc.py::test_mul FAILED                          [100%]\n\n"
                "========================= 1 passed, 2 failed in 0.15s ==============",
                1,
            )
        )
        agent = TestAgent(mock_agent, config, mock_sandbox, mock_command_filter)
        result = await agent.run_tests("/tmp/sandbox/42")
        assert result.passed == 1
        assert result.failed == 2

    @pytest.mark.asyncio
    async def test_parse_failure_details(
        self, config, mock_agent, mock_sandbox, mock_command_filter
    ):
        output = (
            "FAILED tests/test_calc.py::test_div - ZeroDivisionError: division by zero\n"
            "FAILED tests/test_calc.py::test_mul - AssertionError: expected 6 got 5\n"
            "========================= 3 failed in 0.2s =========================="
        )
        mock_sandbox.execute = AsyncMock(return_value=(output, 1))
        agent = TestAgent(mock_agent, config, mock_sandbox, mock_command_filter)
        result = await agent.run_tests("/tmp/sandbox/42")
        assert len(result.failure_details) == 2

    @pytest.mark.asyncio
    async def test_parse_pytest_with_errors(
        self, config, mock_agent, mock_sandbox, mock_command_filter
    ):
        mock_sandbox.execute = AsyncMock(
            return_value=(
                "============================= test session starts ================\n"
                "tests/test_x.py::test_a ERROR                                   [ 50%]\n"
                "tests/test_x.py::test_b PASSED                                  [100%]\n\n"
                "======================== 1 passed, 1 error in 0.1s ===============",
                1,
            )
        )
        agent = TestAgent(mock_agent, config, mock_sandbox, mock_command_filter)
        result = await agent.run_tests("/tmp/sandbox/42")
        assert result.errors == 1
        assert result.passed == 1


class TestTestAgentPrompt:
    """Test the Test Agent system prompt."""

    def test_prompt_mentions_sandbox(self):
        assert "sandbox" in TEST_AGENT_SYSTEM_PROMPT.lower()

    def test_prompt_mentions_execute(self):
        assert "execute" in TEST_AGENT_SYSTEM_PROMPT

    def test_prompt_mentions_test_suite(self):
        assert "test" in TEST_AGENT_SYSTEM_PROMPT.lower()
