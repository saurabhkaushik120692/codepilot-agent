"""Tests for the Repo Explorer agent."""

from unittest.mock import AsyncMock

import pytest

from codepilot.agents.repo_explorer import REPO_EXPLORER_SYSTEM_PROMPT, RepoExplorer
from codepilot.config import Config
from codepilot.context.repo_map import RepoMapBuilder
from codepilot.context.retriever import FileRetriever
from codepilot.core.base_agent import BaseAgent


@pytest.fixture
def config():
    return Config(
        _env_file=None,
        max_relevant_files=5,
    )


@pytest.fixture
def mock_agent():
    return AsyncMock(spec=BaseAgent)


@pytest.fixture
def mock_repo_map_builder():
    builder = AsyncMock(spec=RepoMapBuilder)
    builder.build.return_value = "src/main.py [Python]  def greet"
    return builder


@pytest.fixture
def mock_retriever():
    r = AsyncMock(spec=FileRetriever)
    r.retrieve.return_value = ["src/main.py", "src/utils.py"]
    return r


class TestRepoExplorer:
    """Test the Repo Explorer agent."""

    def test_initialization(
        self, config, mock_agent, mock_repo_map_builder, mock_retriever
    ):
        explorer = RepoExplorer(
            mock_agent, config, mock_repo_map_builder, mock_retriever
        )
        assert explorer._agent == mock_agent
        assert explorer._config == config

    @pytest.mark.asyncio
    async def test_explore_returns_file_paths(
        self, config, mock_agent, mock_repo_map_builder, mock_retriever
    ):
        explorer = RepoExplorer(
            mock_agent, config, mock_repo_map_builder, mock_retriever
        )
        files = await explorer.explore("Fix greet function", "/tmp/repo")
        assert isinstance(files, list)
        assert "src/main.py" in files
        mock_repo_map_builder.build.assert_called_once_with("/tmp/repo")
        mock_retriever.retrieve.assert_called_once()

    @pytest.mark.asyncio
    async def test_explore_builds_repo_map(
        self, config, mock_agent, mock_repo_map_builder, mock_retriever
    ):
        explorer = RepoExplorer(
            mock_agent, config, mock_repo_map_builder, mock_retriever
        )
        await explorer.explore("Test task", "/some/repo")
        mock_repo_map_builder.build.assert_called_once_with("/some/repo")

    @pytest.mark.asyncio
    async def test_explore_no_matches(
        self, config, mock_agent, mock_repo_map_builder, mock_retriever
    ):
        mock_retriever.retrieve.return_value = []
        explorer = RepoExplorer(
            mock_agent, config, mock_repo_map_builder, mock_retriever
        )
        files = await explorer.explore("Unknown task", "/tmp/repo")
        assert files == []


class TestRepoExplorerPrompt:
    """Test the system prompt content."""

    def test_prompt_mentions_file_paths_only(self):
        assert "ONLY file paths" in REPO_EXPLORER_SYSTEM_PROMPT

    def test_prompt_mentions_repo_map(self):
        assert "repo map" in REPO_EXPLORER_SYSTEM_PROMPT.lower()
