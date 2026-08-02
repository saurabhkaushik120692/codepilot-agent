"""Async polling loop for GitHub issues.

Runs continuously, checking for new unassigned issues with
the configured labels, classifies them, and yields them
to the Orchestrator for processing.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from codepilot.config import Config
from codepilot.github_integration.classifier import (
    IssueClassifier,
    TaskClassification,
)
from codepilot.github_integration.github_service import (
    GitHubService,
    Issue,
)

logger = logging.getLogger(__name__)


@dataclass
class PolledIssue:
    """An issue returned by the poller, already classified."""

    issue: Issue
    classification: TaskClassification


class IssuePoller:
    """Polls GitHub for new issues and classifies them.

    Usage:
        poller = IssuePoller(github, classifier, config)
        async for polled in poller.poll():
            orchestrator.handle_issue(polled)
    """

    def __init__(
        self,
        github: GitHubService,
        classifier: IssueClassifier,
        config: Config,
    ):
        self._github = github
        self._classifier = classifier
        self._config = config
        self._seen_ids: set[int] = set()

    async def poll(self) -> AsyncGenerator[PolledIssue, None]:
        """Poll for new issues indefinitely.

        Yields PolledIssue for each new, unassigned issue found.
        """
        while True:
            try:
                issues = await self._github.list_issues(
                    labels=["ai-assignable"],
                    state="open",
                )

                for issue in issues:
                    if issue.id in self._seen_ids:
                        continue
                    if issue.assignee:
                        continue  # Already assigned

                    self._seen_ids.add(issue.id)

                    try:
                        classification = await self._classifier.classify(issue)
                    except Exception as e:
                        logger.error(
                            f"Failed to classify issue #{issue.number}: {e}"
                        )
                        continue

                    logger.info(
                        f"New issue #{issue.number}: {issue.title} "
                        f"→ {classification.type} "
                        f"(confidence={classification.confidence:.2f})"
                    )

                    yield PolledIssue(issue=issue, classification=classification)

            except Exception as e:
                logger.error(f"Polling error: {e}")

            interval = self._config.poll_interval_minutes
            logger.debug(f"Next poll in {interval} minute(s)")
            await asyncio.sleep(interval * 60)
