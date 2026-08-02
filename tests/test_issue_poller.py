"""Tests for the issue poller — all external calls are mocked."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codepilot.config import Config
from codepilot.github_integration.classifier import TaskClassification
from codepilot.github_integration.github_service import Issue
from codepilot.github_integration.issue_poller import IssuePoller, PolledIssue


@pytest.fixture
def config():
    return Config(
        _env_file=None,
        poll_interval_minutes=1,
    )


@pytest.fixture
def mock_github():
    github = MagicMock()
    github.list_issues = AsyncMock()
    return github


@pytest.fixture
def mock_classifier():
    classifier = MagicMock()
    classifier.classify = AsyncMock()
    return classifier


class TestIssuePoller:
    """Test the polling loop."""

    @pytest.mark.asyncio
    async def test_yields_new_issues(self, config, mock_github, mock_classifier):
        issue = Issue(
            id=1,
            number=42,
            title="Test issue",
            body="Description",
            labels=["ai-assignable", "bug"],
            state="open",
        )
        mock_github.list_issues.return_value = [issue]
        mock_classifier.classify.return_value = TaskClassification(
            type="bug_fix",
            confidence=0.95,
            reasoning="Bug report",
        )

        poller = IssuePoller(mock_github, mock_classifier, config)

        async def collect_first():
            async for polled in poller.poll():
                return polled

        polled = await asyncio.wait_for(collect_first(), timeout=2)
        assert isinstance(polled, PolledIssue)
        assert polled.issue.number == 42
        assert polled.classification.type == "bug_fix"

    @pytest.mark.asyncio
    async def test_skips_seen_issues(self, config, mock_github, mock_classifier):
        issue = Issue(
            id=1,
            number=42,
            title="Test",
            body="",
            labels=["ai-assignable"],
            state="open",
        )
        mock_github.list_issues.return_value = [issue]
        mock_classifier.classify.return_value = TaskClassification(
            type="bug_fix",
            confidence=0.8,
            reasoning="",
        )

        poller = IssuePoller(mock_github, mock_classifier, config)
        poller._seen_ids.add(1)  # Already seen

        iter_count = 0

        async def count_iterations(sleep_seconds):
            nonlocal iter_count
            iter_count += 1
            if iter_count >= 3:
                raise asyncio.CancelledError("Test done")

        with patch(
            "codepilot.github_integration.issue_poller.asyncio.sleep",
            side_effect=count_iterations,
        ):
            results = []
            try:
                async for polled in poller.poll():
                    results.append(polled)
            except asyncio.CancelledError:
                pass
            assert len(results) == 0
            assert iter_count >= 2  # Should have iterated at least once

    @pytest.mark.asyncio
    async def test_skips_assigned_issues(self, config, mock_github, mock_classifier):
        issue = Issue(
            id=2,
            number=43,
            title="Assigned",
            body="",
            labels=["ai-assignable"],
            state="open",
            assignee="someuser",
        )
        mock_github.list_issues.return_value = [issue]

        poller = IssuePoller(mock_github, mock_classifier, config)

        iter_count = 0

        async def count_iterations(sleep_seconds):
            nonlocal iter_count
            iter_count += 1
            if iter_count >= 3:
                raise asyncio.CancelledError("Test done")

        with patch(
            "codepilot.github_integration.issue_poller.asyncio.sleep",
            side_effect=count_iterations,
        ):
            results = []
            try:
                async for polled in poller.poll():
                    results.append(polled)
            except asyncio.CancelledError:
                pass
            assert len(results) == 0
            assert iter_count >= 2
