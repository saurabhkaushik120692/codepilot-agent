"""Command Filter Guardrail — blocks dangerous shell commands.

Intercepts commands before they execute and raises GuardrailViolation
for blocked patterns. Works with regex-based matching — deterministic,
no LLM needed.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


class GuardrailViolation(Exception):  # noqa: N818
    """Raised when a guardrail blocks an operation."""

    def __init__(self, rule: str, detail: str):
        self.rule = rule
        self.detail = detail
        super().__init__(f"{rule}: {detail}")


class CommandFilter:
    """Blocks dangerous shell commands via pattern matching.

    Checks commands against blocked shell patterns and blocked
    filesystem paths. Also verifies commands stay within the
    sandbox directory.
    """

    BLOCKED_PATTERNS: list[str] = [
        r"rm\s+-rf",
        r"rmdir",
        r"curl\s+",
        r"wget\s+",
        r"pip\s+install",
        r"npm\s+install",
        r"yarn\s+add",
        r"sudo\s+",
        r"chmod\s+777",
        r"mkfs\.",
        r"dd\s+if=",
        r":(){ :|:& };:",
        r">\s*/dev/sda",
        r"shutdown",
        r"reboot",
        r"init\s+[0-6]",
        r"systemctl\s+stop",
        r"kill\s+-9",
        r"git\s+push\s+--force",
        r"git\s+push\s+-f",
    ]

    BLOCKED_PATH_PATTERNS: list[str] = [
        r"/etc/",
        r"/usr/",
        r"/bin/",
        r"/sbin/",
        r"/boot/",
        r"/sys/",
        r"/proc/",
        r"/dev/",
        r"C:\\Windows",
        r"C:\\Program Files",
        r"C:\\ProgramData",
    ]

    def check(self, command: str, sandbox_path: str) -> None:
        """Check a command against blocked patterns.

        Args:
            command: The shell command to check.
            sandbox_path: The allowed sandbox directory.

        Raises:
            GuardrailViolation: If the command is blocked.
        """
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                raise GuardrailViolation(
                    rule="blocked_command_pattern",
                    detail=(
                        f"Command matches '{pattern}': "
                        f"{command[:100]}"
                    ),
                )

        for pattern in self.BLOCKED_PATH_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                raise GuardrailViolation(
                    rule="blocked_system_path",
                    detail=(
                        f"Command references '{pattern}': "
                        f"{command[:100]}"
                    ),
                )

        logger.debug(f"Command passed guardrail: {command[:80]}")
