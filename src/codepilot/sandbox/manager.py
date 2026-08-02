"""Sandbox Manager — isolated execution environment for Coder agent.

Creates isolated sandbox directories with only the relevant files
copied. The Coder edits inside the sandbox and produces a diff
back to the real repository. Never modifies the live repo directly.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from codepilot.config import Config

logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    """Configuration for creating a sandbox."""

    base_dir: str
    issue_id: int
    relevant_files: list[str]


class SandboxManager:
    """Manages isolated sandbox directories.

    Creates sandboxes, copies relevant files, executes commands
    inside the sandbox, generates diffs, and handles cleanup.
    """

    def __init__(self, config: Config):
        self._config = config

    def create(
        self, sandbox_config: SandboxConfig, repo_path: str
    ) -> str:
        """Create sandbox, copy relevant files, return sandbox path.

        Args:
            sandbox_config: Configuration for the sandbox.
            repo_path: Path to the real repository root.

        Returns:
            Absolute path to the created sandbox directory.
        """
        base = Path(sandbox_config.base_dir).expanduser().resolve()
        sandbox_path = base / str(sandbox_config.issue_id)

        if sandbox_path.exists():
            shutil.rmtree(sandbox_path)
        sandbox_path.mkdir(parents=True, exist_ok=True)

        repo_root = Path(repo_path).resolve()
        for rel_file in sandbox_config.relevant_files:
            src = repo_root / rel_file
            if not src.exists():
                logger.warning(f"Skipping missing file: {rel_file}")
                continue
            dst = sandbox_path / rel_file
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        logger.info(
            f"Sandbox created at {sandbox_path} "
            f"with {len(sandbox_config.relevant_files)} files"
        )
        return str(sandbox_path)

    async def execute(
        self, sandbox_path: str, command: str
    ) -> tuple[str, int]:
        """Run a command inside the sandbox directory.

        Args:
            sandbox_path: The sandbox directory path.
            command: The shell command to execute.

        Returns:
            Tuple of (stdout + stderr output, exit code).
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "bash",
                "-c",
                command,
                cwd=sandbox_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ},
            )
            stdout, _ = await proc.communicate()
            exit_code = proc.returncode if proc.returncode is not None else -1
            output = stdout.decode("utf-8", errors="replace")
            logger.debug(f"Command exited {exit_code}: {command[:80]}")
            return output, exit_code
        except FileNotFoundError:
            proc = await asyncio.create_subprocess_exec(
                "cmd",
                "/c",
                command,
                cwd=sandbox_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ},
            )
            stdout, _ = await proc.communicate()
            exit_code = proc.returncode if proc.returncode is not None else -1
            output = stdout.decode("utf-8", errors="replace")
            return output, exit_code

    def get_diff(self, sandbox_path: str, repo_path: str) -> str:
        """Generate unified diff of sandbox changes vs original.

        Args:
            sandbox_path: Path to the sandbox directory.
            repo_path: Path to the original repository root.

        Returns:
            A unified diff string showing all changes.
        """
        sandbox = Path(sandbox_path).resolve()
        repo = Path(repo_path).resolve()

        diff_lines: list[str] = []
        for sandbox_file in sandbox.rglob("*"):
            if sandbox_file.is_dir():
                continue
            rel = sandbox_file.relative_to(sandbox)
            orig = repo / rel

            try:
                with open(sandbox_file, encoding="utf-8") as f:
                    sandbox_content = f.read()
            except Exception:
                continue

            if orig.exists():
                try:
                    with open(orig, encoding="utf-8") as f:
                        orig_content = f.read()
                except Exception:
                    orig_content = ""
            else:
                orig_content = ""

            if sandbox_content != orig_content:
                diff_lines.append(f"--- a/{rel}")
                diff_lines.append(f"+++ b/{rel}")
                if not orig.exists():
                    lines = len(sandbox_content.splitlines())
                    diff_lines.append(
                        f"@@ -0,0 +1,{lines} @@"
                    )
                    for line in sandbox_content.splitlines():
                        diff_lines.append(f"+{line}")
                else:
                    orig_lines = orig_content.splitlines()
                    new_lines = sandbox_content.splitlines()
                    diff_lines.append(
                        f"@@ -1,{len(orig_lines)} +1,{len(new_lines)} @@"
                    )
                    for line in orig_lines:
                        if line not in new_lines:
                            diff_lines.append(f"-{line}")
                    for line in new_lines:
                        if line not in orig_lines:
                            diff_lines.append(f"+{line}")

        return "\n".join(diff_lines)

    def cleanup(self, sandbox_path: str) -> None:
        """Delete the sandbox directory.

        Args:
            sandbox_path: Path to the sandbox to clean up.
        """
        path = Path(sandbox_path)
        if path.exists():
            shutil.rmtree(path)
            logger.info(f"Sandbox cleaned up: {sandbox_path}")
