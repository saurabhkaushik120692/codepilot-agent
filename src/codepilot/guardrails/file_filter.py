"""File Filter Guardrail — blocks edits to sensitive files.

Intercepts file operations and raises GuardrailViolation for
blocked patterns (secrets, credentials, keys, etc.).
"""

from __future__ import annotations

import logging
import re

from codepilot.guardrails.command_filter import GuardrailViolation

logger = logging.getLogger(__name__)


class FileFilter:
    """Blocks edits to sensitive files via pattern matching."""

    BLOCKED_PATTERNS: list[str] = [
        r"\.env$",
        r".*\.secret$",
        r".*\.pem$",
        r".*\.key$",
        r".*credentials.*",
        r".*\.p12$",
        r".*\.pfx$",
        r".*id_rsa.*",
        r".*id_ed25519.*",
        r".*known_hosts$",
        r"\.git/config$",
        r"\.git-credentials$",
        r".*\.token$",
        r".*token\.json$",
    ]

    def check(self, filepath: str) -> None:
        """Check a file path against blocked patterns.

        Args:
            filepath: The file path to check.

        Raises:
            GuardrailViolation: If the file is blocked.
        """
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, filepath, re.IGNORECASE):
                raise GuardrailViolation(
                    rule="blocked_sensitive_file",
                    detail=(f"File matches blocked pattern '{pattern}': {filepath}"),
                )

        logger.debug(f"File passed guardrail: {filepath}")
