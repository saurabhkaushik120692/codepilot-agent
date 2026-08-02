"""Tests for the PR Agent."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from codepilot.agents.pr_agent import PR_AGENT_SYSTEM_PROMPT, PRAgent
from codepilot.config import Config
from codepilot.core.base_agent import BaseAgent
from codepilot.github_integration.github_service import GitHubService, PullRequest
from codepilot.memory.working import WorkingMemory


@pytest.fixture
def config():
    return Config(_env_file=None)


@pytest.fixture
def mock_agent():
    return AsyncMock(spec=BaseAgent)


@pytest.fixture
def mock_github():
    github = MagicMock(spec=GitHubService)
    github.create_branch = AsyncMock()
    github.create_pull_request = AsyncMock(
        return_value=PullRequest(
            number=1,
            title="fix(#42): Fix bug",
            body="PR body",
            html_url="https://github.com/owner/repo/pull/1",
            state="open",
        )
    )
    return github


@pytest.fixture
def working_memory():
    wm = WorkingMemory(issue_id=42)
    wm.relevant_files = ["src/calc.py", "tests/test_calc.py"]
    wm.current_diff = "--- a/src/calc.py\n+++ b/src/calc.py\n+zero check"
    return wm


class TestPRAgent:
    """Test PR Agent."""

    @pytest.mark.asyncio
    async def test_creates_pr(self, config, mock_agent, mock_github, working_memory):
        agent = PRAgent(mock_agent, config, mock_github)
        pr = await agent.create_pr(
            working_memory,
            working_memory.current_diff or "",
            issue_number=42,
            issue_title="Fix division by zero",
            issue_body="Calculator crashes",
        )
        assert pr.number == 1
        assert "github.com" in pr.html_url
        mock_github.create_branch.assert_called_once()
        mock_github.create_pull_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_manual_task_pr(
        self, config, mock_agent, mock_github, working_memory
    ):
        agent = PRAgent(mock_agent, config, mock_github)
        pr = await agent.create_pr(
            working_memory,
            "diff content",
            task_source="user_input",
            issue_title="Add dark mode",
        )
        assert pr.number == 1
        assert mock_github.create_branch.called


class TestPRAgentPrompt:
    """Test the PR Agent system prompt."""

    def test_prompt_mentions_branch(self):
        assert "branch" in PR_AGENT_SYSTEM_PROMPT

    def test_prompt_mentions_pr(self):
        assert "pull request" in PR_AGENT_SYSTEM_PROMPT.lower()

    def test_prompt_mentions_labels(self):
        assert "labels" in PR_AGENT_SYSTEM_PROMPT.lower()
