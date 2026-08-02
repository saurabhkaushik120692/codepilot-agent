"""Tests for working memory and state machine."""

import pytest

from codepilot.memory.working import (
    InvalidTransitionError,
    TaskState,
    WorkingMemory,
)


class TestTaskState:
    """Test the TaskState enum."""

    def test_all_states_defined(self):
        assert TaskState.TRIAGED.value == "TRIAGED"
        assert TaskState.EXPLORING.value == "EXPLORING"
        assert TaskState.IMPLEMENTING.value == "IMPLEMENTING"
        assert TaskState.TESTING.value == "TESTING"
        assert TaskState.PR_OPENED.value == "PR_OPENED"
        assert TaskState.DONE.value == "DONE"
        assert TaskState.FAILED.value == "FAILED"


class TestWorkingMemory:
    """Test working memory state transitions."""

    def test_initial_state_is_triaged(self):
        wm = WorkingMemory(issue_id=1)
        assert wm.state == TaskState.TRIAGED

    def test_valid_transition(self):
        wm = WorkingMemory(issue_id=1)
        wm.transition_to(TaskState.EXPLORING)
        assert wm.state == TaskState.EXPLORING

    def test_invalid_transition_raises(self):
        wm = WorkingMemory(issue_id=1)
        with pytest.raises(InvalidTransitionError):
            wm.transition_to(TaskState.DONE)

    def test_full_valid_flow(self):
        wm = WorkingMemory(issue_id=1)
        wm.transition_to(TaskState.EXPLORING)
        wm.transition_to(TaskState.IMPLEMENTING)
        wm.transition_to(TaskState.TESTING)
        wm.transition_to(TaskState.PR_OPENED)
        wm.transition_to(TaskState.DONE)
        assert wm.state == TaskState.DONE

    def test_any_state_to_failed(self):
        wm = WorkingMemory(issue_id=1)
        wm.transition_to(TaskState.FAILED)
        assert wm.state == TaskState.FAILED

    def test_retry_transition_back_to_implementing(self):
        wm = WorkingMemory(issue_id=1)
        wm.transition_to(TaskState.EXPLORING)
        wm.transition_to(TaskState.IMPLEMENTING)
        wm.transition_to(TaskState.TESTING)
        wm.transition_to(TaskState.IMPLEMENTING)
        assert wm.state == TaskState.IMPLEMENTING

    def test_defaults(self):
        wm = WorkingMemory(issue_id=42)
        assert wm.issue_id == 42
        assert wm.relevant_files == []
        assert wm.retry_count == 0
        assert wm.failure_reason == ""
