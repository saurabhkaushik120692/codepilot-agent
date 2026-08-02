"""Cloud Sandbox — abstract interface + provider implementations.

Refactors the existing SandboxManager into a SandboxInterface ABC
with two implementations: LocalSandbox (existing) and a cloud
sandbox placeholder for Daytona/Modal.

Factory function selects provider based on SANDBOX_PROVIDER config.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from abc import ABC, abstractmethod
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


class SandboxInterface(ABC):
    """Abstract sandbox interface — local or cloud."""

    @abstractmethod
    async def create(self, config: SandboxConfig, repo_path: str) -> str:
        """Create sandbox, return sandbox path or ID."""

    @abstractmethod
    async def execute(self, sandbox_id: str, command: str) -> tuple[str, int]:
        """Run a command inside the sandbox."""

    @abstractmethod
    async def get_diff(self, sandbox_id: str, repo_path: str) -> str:
        """Generate diff of changes vs original."""

    @abstractmethod
    async def cleanup(self, sandbox_id: str) -> None:
        """Delete the sandbox."""


class LocalSandbox(SandboxInterface):
    """Existing local sandbox — directory-based isolation.

    Mirrors the SandboxManager from Phase 3, Step 4.
    """

    def __init__(self, config: Config):
        self._config = config

    async def create(self, sandbox_config: SandboxConfig, repo_path: str) -> str:
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
            f"Local sandbox created at {sandbox_path} "
            f"with {len(sandbox_config.relevant_files)} files"
        )
        return str(sandbox_path)

    async def execute(self, sandbox_path: str, command: str) -> tuple[str, int]:
        try:
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
            return stdout.decode("utf-8", errors="replace"), exit_code
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
            return stdout.decode("utf-8", errors="replace"), exit_code

    async def get_diff(self, sandbox_path: str, repo_path: str) -> str:
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
                    diff_lines.append(f"@@ -0,0 +1,{lines} @@")
                    for line in sandbox_content.splitlines():
                        diff_lines.append(f"+{line}")
                else:
                    orig_lines = orig_content.splitlines()
                    new_lines = sandbox_content.splitlines()
                    diff_lines.append(f"@@ -1,{len(orig_lines)} +1,{len(new_lines)} @@")
                    for line in orig_lines:
                        if line not in new_lines:
                            diff_lines.append(f"-{line}")
                    for line in new_lines:
                        if line not in orig_lines:
                            diff_lines.append(f"+{line}")

        return "\n".join(diff_lines)

    async def cleanup(self, sandbox_path: str) -> None:
        path = Path(sandbox_path)
        if path.exists():
            shutil.rmtree(path)
            logger.info(f"Local sandbox cleaned up: {sandbox_path}")


class CloudSandbox(SandboxInterface):
    """Cloud sandbox placeholder for Daytona/Modal.

    When a cloud provider is configured, this offers OS-level
    isolation instead of directory-level. Falls back to LocalSandbox
    if the provider is unavailable.
    """

    def __init__(self, config: Config):
        self._config = config
        self._local = LocalSandbox(config)

    async def create(self, sandbox_config: SandboxConfig, repo_path: str) -> str:
        logger.warning(
            f"Cloud sandbox ({self._config.sandbox_provider}) "
            "not available — falling back to local"
        )
        return await self._local.create(sandbox_config, repo_path)

    async def execute(self, sandbox_id: str, command: str) -> tuple[str, int]:
        return await self._local.execute(sandbox_id, command)

    async def get_diff(self, sandbox_id: str, repo_path: str) -> str:
        return await self._local.get_diff(sandbox_id, repo_path)

    async def cleanup(self, sandbox_id: str) -> None:
        await self._local.cleanup(sandbox_id)


def create_sandbox(config: Config) -> SandboxInterface:
    """Factory — picks sandbox based on SANDBOX_PROVIDER config.

    Args:
        config: Application configuration.

    Returns:
        A SandboxInterface implementation.
    """
    match config.sandbox_provider:
        case "local":
            return LocalSandbox(config)
        case _:
            logger.warning(
                f"Unknown sandbox provider '{config.sandbox_provider}' — using local"
            )
            return LocalSandbox(config)
