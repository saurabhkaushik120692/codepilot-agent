"""Coder Agent — implements code changes in a sandboxed environment.

The Coder is the workhorse agent. It receives a task + relevant
file paths from the Repo Explorer, reads files on-demand, makes
edits in the sandbox, runs commands to verify, and produces a
proposed diff.

This is where all Phase 3 components come together.
"""

from __future__ import annotations

import logging

from codepilot.config import Config
from codepilot.core.base_agent import BaseAgent
from codepilot.guardrails.command_filter import CommandFilter
from codepilot.guardrails.file_filter import FileFilter
from codepilot.memory.working import TaskState, WorkingMemory
from codepilot.sandbox.manager import SandboxConfig, SandboxManager

logger = logging.getLogger(__name__)

CODER_SYSTEM_PROMPT = """\
You are the Coder agent for CodePilot.

Your workflow:
1. Read relevant files using read_file to understand the codebase
2. Create an implementation checklist using write_todos
3. Make surgical edits using edit_file (ONLY change what's needed)
4. Create new files with write_file if necessary
5. Run commands using execute to verify your changes
6. Spawn the Test Agent to run the test suite

Rules:
- Edit ONLY files inside the sandbox directory
- Never modify .env, key files, or credential files
- Keep changes minimal and focused
- Report any errors to the Orchestrator
- Produce a summary of all changes made
"""


class Coder:
    """Implements code changes in a sandboxed environment.

    Composition over inheritance — wraps a BaseAgent, similar to
    Orchestrator and RepoExplorer patterns.
    """

    def __init__(
        self,
        agent: BaseAgent,
        config: Config,
        sandbox: SandboxManager,
        command_filter: CommandFilter,
        file_filter: FileFilter,
    ):
        self._agent = agent
        self._config = config
        self._sandbox = sandbox
        self._command_filter = command_filter
        self._file_filter = file_filter
        logger.info("Coder agent initialized")

    async def implement(
        self,
        task: str,
        relevant_files: list[str],
        working_memory: WorkingMemory,
        repo_path: str,
    ) -> str:
        """Execute the coding task in a sandbox.

        Args:
            task: The task description.
            relevant_files: List of relevant file paths from RepoExplorer.
            working_memory: The current working memory for state tracking.
            repo_path: Path to the repository root.

        Returns:
            A unified diff string showing all changes made.
        """
        sandbox_config = SandboxConfig(
            base_dir=self._config.sandbox_base_dir,
            issue_id=working_memory.issue_id,
            relevant_files=relevant_files,
        )

        sandbox_path = self._sandbox.create(sandbox_config, repo_path)
        logger.info(
            f"Coder working in sandbox {sandbox_path} with {len(relevant_files)} files"
        )

        try:
            working_memory.transition_to(TaskState.IMPLEMENTING)
        except Exception:
            pass

        try:
            messages = [
                {
                    "role": "system",
                    "content": CODER_SYSTEM_PROMPT
                    + f"\n\nSandbox path: {sandbox_path}",
                },
                {
                    "role": "user",
                    "content": (
                        f"Task: {task}\n\n"
                        f"Relevant files: {', '.join(relevant_files)}\n\n"
                        f"Please implement the changes."
                    ),
                },
            ]
            result = await self._agent.invoke(messages)
            logger.info(f"Coder result: success={result.success}")

            diff = self._sandbox.get_diff(sandbox_path, repo_path)
            working_memory.current_diff = diff

            if not result.success:
                self._handle_failure(working_memory)

            return diff

        except Exception as e:
            logger.error(f"Coder failed: {e}")
            self._handle_failure(working_memory)
            return ""

        finally:
            pass

    def _handle_failure(self, working_memory: WorkingMemory) -> None:
        """Handle coder failure — increment retry, maybe transition to FAILED."""
        working_memory.retry_count += 1
        if working_memory.retry_count >= self._config.max_coder_retries:
            try:
                working_memory.transition_to(TaskState.FAILED)
            except Exception:
                working_memory.state = TaskState.FAILED
            working_memory.failure_reason = (
                f"Max retries ({self._config.max_coder_retries}) exceeded"
            )
            logger.error(working_memory.failure_reason)
