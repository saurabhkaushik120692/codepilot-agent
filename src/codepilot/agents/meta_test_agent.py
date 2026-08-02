"""Meta Test Agent — self-heals test infrastructure failures.

When the Test Agent encounters infrastructure failures (import
errors, syntax errors in test files, missing fixtures) rather
than assertion failures, this meta-agent debugs and fixes the
test setup, then re-runs.

Max 1 self-heal retry per task to prevent infinite loops.
"""

from __future__ import annotations

import logging
from enum import Enum

from codepilot.config import Config
from codepilot.core.base_agent import BaseAgent
from codepilot.guardrails.command_filter import CommandFilter
from codepilot.guardrails.file_filter import FileFilter
from codepilot.sandbox.manager import SandboxManager

logger = logging.getLogger(__name__)

META_TEST_AGENT_PROMPT = """\
You are the Meta Test Agent for CodePilot.

Your job is to fix test INFRASTRUCTURE failures — not assertion
failures. Infrastructure failures include:
- ImportError / ModuleNotFoundError in test files
- SyntaxError in test files
- Missing fixtures or misconfigured conftest.py
- Test collection errors

DO NOT change assertions or test logic. Only fix the setup so
tests can run. After your fix, the Test Agent will re-run.
"""

INFRA_FAILURE_PATTERNS = [
    "ImportError",
    "ModuleNotFoundError",
    "SyntaxError",
    "IndentationError",
    "NameError",
    "FixtureLookupError",
    "INTERNALERROR",
    "collecting",
    "no tests ran",
    "could not import",
]


class TestFailureType(str, Enum):
    ASSERTION_FAILURE = "assertion"
    INFRASTRUCTURE_FAILURE = "infra"


class MetaTestAgent:
    """Debugs and fixes test infrastructure failures.

    Only repairs test setup (imports, fixtures, syntax) —
    never modifies assertion logic.
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

    @staticmethod
    def classify_failure(output: str) -> TestFailureType:
        """Classify whether a test failure is assertion or infrastructure.

        Args:
            output: The raw test output.

        Returns:
            TestFailureType indicating the failure category.
        """
        for pattern in INFRA_FAILURE_PATTERNS:
            if pattern in output:
                return TestFailureType.INFRASTRUCTURE_FAILURE

        if "FAILED" in output and "passed" in output:
            return TestFailureType.ASSERTION_FAILURE

        return TestFailureType.ASSERTION_FAILURE

    async def self_heal(
        self,
        error_output: str,
        test_files: list[str],
        sandbox_path: str,
    ) -> bool:
        """Analyze error, fix test setup, return success.

        Args:
            error_output: The raw test output showing the failure.
            test_files: List of test file paths to inspect.
            sandbox_path: The sandbox directory path.

        Returns:
            True if the self-heal was successful and tests should re-run.
        """
        logger.info(f"MetaTestAgent attempting self-heal for {len(test_files)} files")

        task_prompt = (
            f"The test suite failed with infrastructure errors.\n\n"
            f"Error output:\n{error_output[:3000]}\n\n"
            f"Test files to inspect:\n"
            + "\n".join(f"- {f}" for f in test_files)
            + "\n\nFix ONLY the infrastructure issue "
            "(imports, syntax, fixtures). "
            "Do NOT change any test assertions or logic."
        )

        try:
            messages = [
                {"role": "system", "content": META_TEST_AGENT_PROMPT},
                {"role": "user", "content": task_prompt},
            ]
            result = await self._agent.invoke(messages)
            logger.info(f"MetaTestAgent result: success={result.success}")
            return result.success
        except Exception as e:
            logger.error(f"MetaTestAgent failed: {e}")
            return False
