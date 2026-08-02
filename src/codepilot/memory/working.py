"""Working memory — per-task in-memory state.

Working memory tracks the active task's metadata, state machine position,
relevant files, and retry count. It is passed explicitly to subagents
at spawn time (not through conversation history).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskState(str, Enum):
    """Valid states in the task lifecycle state machine."""

    TRIAGED = "TRIAGED"
    EXPLORING = "EXPLORING"
    IMPLEMENTING = "IMPLEMENTING"
    TESTING = "TESTING"
    PR_OPENED = "PR_OPENED"
    DONE = "DONE"
    FAILED = "FAILED"


VALID_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.TRIAGED: {TaskState.EXPLORING, TaskState.FAILED},
    TaskState.EXPLORING: {TaskState.IMPLEMENTING, TaskState.FAILED},
    TaskState.IMPLEMENTING: {TaskState.TESTING, TaskState.FAILED},
    TaskState.TESTING: {TaskState.PR_OPENED, TaskState.IMPLEMENTING, TaskState.FAILED},
    TaskState.PR_OPENED: {TaskState.DONE, TaskState.FAILED},
    TaskState.DONE: set(),
    TaskState.FAILED: set(),
}


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""


@dataclass
class TaskSource:
    """Identifies the origin of a task.

    Attributes:
        source: 'github_issue' for polled issues, 'user_input' for manual tasks.
        issue_id: GitHub issue ID (None for manual tasks).
        issue_number: GitHub issue number (None for manual tasks).
        description: Full task description.
        title: Short title.
    """

    source: str  # "github_issue" | "user_input"
    issue_id: int | None = None
    issue_number: int | None = None
    description: str = ""
    title: str = ""


@dataclass
class TestResult:
    """Structured result from the Test Agent."""

    passed: int = 0
    failed: int = 0
    errors: int = 0
    failure_details: list[str] = field(default_factory=list)
    coverage: float | None = None


@dataclass
class WorkingMemory:
    """Per-task state tracked during execution.

    This is passed to subagents at spawn time so they have the full
    context without relying on conversation history.
    """

    issue_id: int
    issue_metadata: dict[str, Any] = field(default_factory=dict)
    repo_map: str = ""
    relevant_files: list[str] = field(default_factory=list)
    current_diff: str | None = None
    test_results: list[TestResult] = field(default_factory=list)
    retry_count: int = 0
    state: TaskState = TaskState.TRIAGED
    failure_reason: str = ""

    def transition_to(self, new_state: TaskState) -> None:
        """Transition to a new state, validating the move.

        Args:
            new_state: The state to transition to.

        Raises:
            InvalidTransitionError: If the transition is not allowed.
        """
        allowed = VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition from {self.state.value} to {new_state.value}. "
                f"Allowed next states: {[s.value for s in allowed]}"
            )
        self.state = new_state
