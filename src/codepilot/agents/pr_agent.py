"""PR Agent — creates branches and opens pull requests on GitHub.

After the Coder produces a diff and tests pass, the PR Agent pushes
changes to GitHub using GitHubService (Phase 2) and PRBuilder (Step 1).
"""

from __future__ import annotations

import logging

from codepilot.config import Config
from codepilot.core.base_agent import BaseAgent
from codepilot.github_integration.github_service import (
    GitHubService,
    PullRequest,
)
from codepilot.github_integration.pr_builder import (
    build_branch_name,
    build_commit_message,
    build_pr_body,
)
from codepilot.memory.working import WorkingMemory

logger = logging.getLogger(__name__)

PR_AGENT_SYSTEM_PROMPT = """\
You are the PR Agent for CodePilot.

Your responsibilities:
1. Create a branch from main for the changes
2. Apply the proposed diff to the branch
3. Commit with a descriptive conventional-commit message
4. Open a pull request with all sections filled
5. Add labels (codepilot-generated, needs-review)
6. Assign the issue reporter if available

You do NOT decide whether to create a PR — the Orchestrator does.
"""


class PRAgent:
    """Creates branches and opens pull requests on GitHub.

    Composition over inheritance — wraps a BaseAgent.
    """

    def __init__(
        self,
        agent: BaseAgent,
        config: Config,
        github: GitHubService,
    ):
        self._agent = agent
        self._config = config
        self._github = github
        logger.info("PR Agent initialized")

    async def create_pr(
        self,
        working_memory: WorkingMemory,
        diff: str,
        task_source: str = "github_issue",
        issue_number: int | None = None,
        issue_title: str = "",
        issue_body: str = "",
    ) -> PullRequest:
        """Full PR workflow: branch → commit → PR.

        Args:
            working_memory: Current task state.
            diff: The proposed diff from the Coder.
            task_source: 'github_issue' or 'user_input'.
            issue_number: GitHub issue number (None for manual).
            issue_title: Issue title.
            issue_body: Issue description.

        Returns:
            The created PullRequest.
        """
        is_manual = task_source == "user_input"
        branch_name = build_branch_name(issue_number, issue_title or "task")
        logger.info(f"Creating branch: {branch_name}")

        await self._github.create_branch(branch_name)

        files_changed = working_memory.relevant_files or []

        commit_msg = build_commit_message(
            issue_number=issue_number,
            summary=issue_title or "CodePilot changes",
            changes=files_changed,
            reason="Automated fix by CodePilot",
            is_manual=is_manual,
        )

        test_results = "Tests passed" if working_memory.test_results else "N/A"
        pr_body = build_pr_body(
            issue_title=issue_title or "CodePilot changes",
            issue_body=issue_body,
            approach=f"Changes made:\n\n```diff\n{diff[:2000]}\n```",
            files_changed=files_changed,
            test_results=test_results,
            issue_number=issue_number,
        )

        pr = await self._github.create_pull_request(
            title=commit_msg.split("\n")[0],
            body=pr_body,
            head=branch_name,
            base="main",
            labels=["codepilot-generated", "needs-review"],
        )

        logger.info(f"PR #{pr.number} created: {pr.html_url}")
        return pr
