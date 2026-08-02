"""GitHub API abstraction layer.

Wraps PyGithub behind a clean interface so agent code never
depends on a specific GitHub library.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from codepilot.config import Config

logger = logging.getLogger(__name__)


@dataclass
class Issue:
    """A GitHub issue with fields relevant to CodePilot."""

    id: int
    number: int
    title: str
    body: str
    labels: list[str]
    state: str
    assignee: str | None = None


@dataclass
class Branch:
    """A Git branch."""

    name: str
    ref: str


@dataclass
class PullRequest:
    """A GitHub pull request."""

    number: int
    title: str
    body: str
    html_url: str
    state: str


class GitHubServiceError(Exception):
    """Raised when a GitHub API call fails."""


class GitHubService:
    """Abstraction over the GitHub API using PyGithub."""

    def __init__(self, config: Config):
        self._config = config
        self._repo: Any = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialize the PyGithub client."""
        try:
            import github  # type: ignore[import-untyped]

            with open(self._config.github_app_private_key_path) as f:
                private_key = f.read()

            integration = github.GithubIntegration(
                integration_id=self._config.github_app_id,
                private_key=private_key,
            )
            installation = integration.get_installations()[0]
            client = installation.get_github_for_installation()
            self._repo = client.get_repo(self._config.github_repository)
            logger.info("GitHubService initialized with PyGithub")
        except Exception as e:
            raise GitHubServiceError(f"Failed to initialize GitHub client: {e}") from e

    async def list_issues(
        self, labels: list[str] | None = None, state: str = "open"
    ) -> list[Issue]:
        """List issues matching the given labels and state.

        Args:
            labels: Filter by labels (e.g., ["ai-assignable"]).
            state: "open", "closed", or "all".

        Returns:
            A list of Issue dataclasses.
        """
        try:
            raw_issues = self._repo.get_issues(state=state, labels=labels)
            return [
                Issue(
                    id=issue.id,
                    number=issue.number,
                    title=issue.title,
                    body=issue.body or "",
                    labels=[lbl.name for lbl in issue.labels],
                    state=issue.state,
                    assignee=issue.assignee.login if issue.assignee else None,
                )
                for issue in raw_issues
            ]
        except Exception as e:
            raise GitHubServiceError(f"Failed to list issues: {e}") from e

    async def create_branch(self, name: str, from_ref: str = "main") -> Branch:
        """Create a new branch from the given reference."""
        try:
            source_branch = self._repo.get_branch(from_ref)
            self._repo.create_git_ref(
                ref=f"refs/heads/{name}",
                sha=source_branch.commit.sha,
            )
            return Branch(name=name, ref=f"refs/heads/{name}")
        except Exception as e:
            raise GitHubServiceError(f"Failed to create branch '{name}': {e}") from e

    async def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        labels: list[str] | None = None,
    ) -> PullRequest:
        """Create a pull request."""
        try:
            pr = self._repo.create_pull(
                title=title,
                body=body,
                head=head,
                base=base,
            )
            if labels:
                pr.add_to_labels(*labels)
            return PullRequest(
                number=pr.number,
                title=pr.title,
                body=pr.body or "",
                html_url=pr.html_url,
                state=pr.state,
            )
        except Exception as e:
            raise GitHubServiceError(f"Failed to create PR: {e}") from e
