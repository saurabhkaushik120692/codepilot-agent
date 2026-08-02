"""Repo Explorer — finds relevant files using Repo Map + Retriever.

Spawned by the Orchestrator to identify which files are relevant
to a task. Returns ONLY file paths (no file contents) — enforces
context engineering rule. The Coder will read_file on-demand.
"""

from __future__ import annotations

import logging

from codepilot.config import Config
from codepilot.context.repo_map import RepoMapBuilder
from codepilot.context.retriever import FileRetriever
from codepilot.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)

REPO_EXPLORER_SYSTEM_PROMPT = """\
You are the Repo Explorer agent for CodePilot.

Given a task description and a repository map, identify the most
relevant files that need to be examined or modified.

Rules:
- Use the repo map to understand the repository structure
- Use the file retriever for semantic search
- Return ONLY file paths (not file contents)
- Limit results to the most relevant files only
- Do not read file contents — the Coder agent does that
"""


class RepoExplorer:
    """Finds relevant files for a task using repo map and retrieval.

    Composition over inheritance — wraps a BaseAgent, similar to
    the Orchestrator pattern. Not a BaseAgent subclass itself.
    """

    def __init__(
        self,
        agent: BaseAgent,
        config: Config,
        repo_map_builder: RepoMapBuilder,
        retriever: FileRetriever,
    ):
        self._agent = agent
        self._config = config
        self._repo_map_builder = repo_map_builder
        self._retriever = retriever
        logger.info("RepoExplorer initialized")

    async def explore(self, task: str, repo_path: str) -> list[str]:
        """Build repo map, retrieve relevant files, return paths.

        Args:
            task: The task description or issue text.
            repo_path: Absolute or relative path to the repo root.

        Returns:
            List of relevant file paths (relative to repo root).
        """
        repo_map = self._repo_map_builder.build(repo_path)

        results = self._retriever.retrieve(
            query=task, repo_map=repo_map, repo_path=repo_path
        )

        logger.info(f"RepoExplorer found {len(results)} relevant files for task")
        return results
