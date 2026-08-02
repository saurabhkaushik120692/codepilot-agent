"""Test Agent — runs tests in sandbox and returns structured results.

After the Coder makes changes, the Test Agent verifies them by
running pytest in the sandbox, parsing the output, and returning
structured results. The Orchestrator uses test results to decide
next steps: pass → PR, fail → retry Coder.
"""

from __future__ import annotations

import logging
import re

from codepilot.config import Config
from codepilot.core.base_agent import BaseAgent
from codepilot.guardrails.command_filter import CommandFilter
from codepilot.memory.working import TestResult
from codepilot.sandbox.manager import SandboxManager

logger = logging.getLogger(__name__)

TEST_AGENT_SYSTEM_PROMPT = """\
You are the Test Agent for CodePilot.

Your responsibilities:
1. Run the existing test suite using execute
2. Parse the test output for pass/fail/error counts
3. If tests fail, analyze the error messages
4. Return structured test results with failure details

Run tests ONLY in the sandbox directory — never in the live repo.
"""


class TestAgent:
    """Runs tests in the sandbox and reports structured results.

    Composition over inheritance — wraps a BaseAgent.
    The Orchestrator decides retry logic, not the Test Agent.
    """

    def __init__(
        self,
        agent: BaseAgent,
        config: Config,
        sandbox: SandboxManager,
        command_filter: CommandFilter,
    ):
        self._agent = agent
        self._config = config
        self._sandbox = sandbox
        self._command_filter = command_filter
        logger.info("Test Agent initialized")

    async def run_tests(
        self, sandbox_path: str, test_command: str = "pytest"
    ) -> TestResult:
        """Run tests and return structured results.

        Args:
            sandbox_path: The sandbox directory path.
            test_command: The test command to run (default: pytest).

        Returns:
            A TestResult with pass/fail counts and failure details.
        """
        self._command_filter.check(test_command, sandbox_path)

        output, exit_code = await self._sandbox.execute(sandbox_path, test_command)

        if "pytest" in test_command:
            result = self._parse_pytest_output(output)
        else:
            result = self._parse_generic_output(output, exit_code)

        logger.info(f"Test results: {result.passed}P/{result.failed}F/{result.errors}E")
        return result

    def _parse_pytest_output(self, output: str) -> TestResult:
        """Parse pytest output into TestResult dataclass.

        Args:
            output: The raw stdout from pytest.

        Returns:
            A structured TestResult.
        """
        passed = 0
        failed = 0
        errors = 0
        failure_details: list[str] = []

        # Match patterns like "10 passed" or "5 failed"
        passed_match = re.search(r"(\d+)\s+passed", output)
        if passed_match:
            passed = int(passed_match.group(1))

        failed_match = re.search(r"(\d+)\s+failed", output)
        if failed_match:
            failed = int(failed_match.group(1))

        error_match = re.search(r"(\d+)\s+error", output)
        if error_match:
            errors = int(error_match.group(1))

        # Collect failure details
        for match in re.finditer(r"FAILED\s+(.+)", output):
            failure_details.append(match.group(1).strip())

        return TestResult(
            passed=passed,
            failed=failed,
            errors=errors,
            failure_details=failure_details,
        )

    def _parse_generic_output(self, output: str, exit_code: int) -> TestResult:
        """Parse non-pytest test output."""
        return TestResult(
            passed=1 if exit_code == 0 else 0,
            failed=0 if exit_code == 0 else 1,
            errors=0,
            failure_details=[] if exit_code == 0 else [output[:500]],
        )
