"""Tests for the Coder agent."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from codepilot.agents.coder import CODER_SYSTEM_PROMPT, Coder
from codepilot.config import Config
from codepilot.core.base_agent import AgentResult, BaseAgent
from codepilot.guardrails.command_filter import CommandFilter
from codepilot.guardrails.file_filter import FileFilter
from codepilot.memory.working import TaskState, WorkingMemory
from codepilot.sandbox.manager import SandboxManager


@pytest.fixture
def config():
    return Config(
        _env_file=None,
        max_coder_retries=3,
        sandbox_base_dir="/tmp/codepilot_test",
    )


@pytest.fixture
def mock_agent():
    agent = AsyncMock(spec=BaseAgent)
    agent.name = "Coder"
    agent.invoke.return_value = AgentResult(
        success=True,
        output="Changes implemented successfully.",
        todos=["Read relevant files", "Implement fix", "Run tests"],
    )
    return agent


@pytest.fixture
def mock_sandbox():
    sandbox = MagicMock(spec=SandboxManager)
    sandbox.create.return_value = "/tmp/sandbox/42"
    sandbox.get_diff.return_value = "--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n+fixed"
    return sandbox


@pytest.fixture
def mock_command_filter():
    return MagicMock(spec=CommandFilter)


@pytest.fixture
def mock_file_filter():
    return MagicMock(spec=FileFilter)


@pytest.fixture
def working_memory():
    return WorkingMemory(issue_id=42)


class TestCoder:
    """Test the Coder agent."""

    @pytest.mark.asyncio
    async def test_implements_task_returns_diff(
        self,
        config,
        mock_agent,
        mock_sandbox,
        mock_command_filter,
        mock_file_filter,
        working_memory,
    ):
        coder = Coder(
            mock_agent, config, mock_sandbox,
            mock_command_filter, mock_file_filter
        )

        diff = await coder.implement(
            task="Fix the greet function",
            relevant_files=["src/main.py"],
            working_memory=working_memory,
            repo_path="/tmp/test_repo",
        )

        assert isinstance(diff, str)
        assert len(diff) > 0
        mock_agent.invoke.assert_called_once()
        mock_sandbox.create.assert_called_once()
        mock_sandbox.get_diff.assert_called_once()

    @pytest.mark.asyncio
    async def test_transitions_to_implementing(
        self,
        config,
        mock_agent,
        mock_sandbox,
        mock_command_filter,
        mock_file_filter,
        working_memory,
    ):
        working_memory.state = TaskState.EXPLORING

        coder = Coder(
            mock_agent, config, mock_sandbox,
            mock_command_filter, mock_file_filter
        )

        await coder.implement(
            task="Fix bug",
            relevant_files=["src/main.py"],
            working_memory=working_memory,
            repo_path="/tmp/test_repo",
        )

        assert working_memory.state == TaskState.IMPLEMENTING

    @pytest.mark.asyncio
    async def test_stores_diff_in_working_memory(
        self,
        config,
        mock_agent,
        mock_sandbox,
        mock_command_filter,
        mock_file_filter,
        working_memory,
    ):
        coder = Coder(
            mock_agent, config, mock_sandbox,
            mock_command_filter, mock_file_filter
        )

        await coder.implement(
            task="Fix bug",
            relevant_files=["src/main.py"],
            working_memory=working_memory,
            repo_path="/tmp/test_repo",
        )

        assert working_memory.current_diff is not None
        assert len(working_memory.current_diff) > 0

    @pytest.mark.asyncio
    async def test_handles_agent_failure(
        self,
        config,
        mock_agent,
        mock_sandbox,
        mock_command_filter,
        mock_file_filter,
        working_memory,
    ):
        mock_agent.invoke.return_value = AgentResult(
            success=False, output="Failed to implement"
        )

        coder = Coder(
            mock_agent, config, mock_sandbox,
            mock_command_filter, mock_file_filter
        )

        await coder.implement(
            task="Fix bug",
            relevant_files=["src/main.py"],
            working_memory=working_memory,
            repo_path="/tmp/test_repo",
        )

        assert working_memory.retry_count == 1

    @pytest.mark.asyncio
    async def test_max_retries_transitions_to_failed(
        self,
        config,
        mock_agent,
        mock_sandbox,
        mock_command_filter,
        mock_file_filter,
        working_memory,
    ):
        config.max_coder_retries = 1
        mock_agent.invoke.return_value = AgentResult(
            success=False, output="Failed again"
        )
        working_memory.retry_count = 1

        coder = Coder(
            mock_agent, config, mock_sandbox,
            mock_command_filter, mock_file_filter
        )

        await coder.implement(
            task="Fix bug",
            relevant_files=["src/main.py"],
            working_memory=working_memory,
            repo_path="/tmp/test_repo",
        )

        assert working_memory.state == TaskState.FAILED
        assert "Max retries" in working_memory.failure_reason


class TestCoderPrompt:
    """Test the Coder system prompt."""

    def test_prompt_mentions_sandbox(self):
        assert "sandbox" in CODER_SYSTEM_PROMPT.lower()

    def test_prompt_mentions_edit_file(self):
        assert "edit_file" in CODER_SYSTEM_PROMPT

    def test_prompt_mentions_test_agent(self):
        assert "Test Agent" in CODER_SYSTEM_PROMPT
