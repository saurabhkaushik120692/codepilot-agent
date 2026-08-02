"""Tests for the GitHub service — all API calls are mocked."""

from unittest.mock import MagicMock, patch

import pytest

from codepilot.config import Config
from codepilot.github_integration.github_service import (
    GitHubService,
    GitHubServiceError,
)


@pytest.fixture
def config():
    return Config(
        _env_file=None,
        github_app_id="12345",
        github_app_private_key_path="./fake-key.pem",
        github_repository="owner/test-repo",
    )


class TestGitHubServiceInit:
    """Test initialization with different backends."""

    @patch("codepilot.github_integration.github_service.GitHubService._init_client")
    def test_init_does_not_raise(self, mock_init, config):
        mock_init.return_value = None
        service = GitHubService(config)
        assert service._config == config

    def test_init_fails_without_valid_auth(self, config):
        with patch.object(GitHubService, "_init_client") as mock_init:
            mock_init.side_effect = GitHubServiceError("No backend available")
            with pytest.raises(GitHubServiceError):
                GitHubService(config)


class TestListIssues:
    """Test listing issues with mocked backend."""

    @pytest.mark.asyncio
    async def test_returns_issue_list(self, config):
        service = GitHubService.__new__(GitHubService)
        service._config = config

        mock_issue = MagicMock()
        mock_issue.id = 1
        mock_issue.number = 42
        mock_issue.title = "Test issue"
        mock_issue.body = "Description"
        mock_issue.labels = [MagicMock(name="bug")]
        mock_issue.state = "open"
        mock_issue.assignee = None
        mock_issue.labels[0].name = "bug"

        mock_repo = MagicMock()
        mock_repo.get_issues.return_value = [mock_issue]
        service._repo = mock_repo

        issues = await service.list_issues(labels=["bug"])
        assert len(issues) == 1
        assert issues[0].number == 42
        assert issues[0].title == "Test issue"
