"""Tests for episodic memory."""

import pytest

from codepilot.memory.episodic import EpisodicMemory, SessionSummary


@pytest.fixture
def memory():
    return EpisodicMemory()


@pytest.fixture
def summary():
    return SessionSummary(
        issue_id=42,
        task_type="bug_fix",
        success=True,
        summary="Fixed division by zero",
        files_changed=["src/calculator.py"],
        lessons_learned="Check for zero before division",
    )


class TestSessionSummary:
    """Test the SessionSummary dataclass."""

    def test_defaults(self):
        s = SessionSummary(issue_id=1, task_type="bug_fix", success=True, summary="ok")
        assert s.issue_id == 1
        assert s.files_changed == []
        assert s.lessons_learned == ""
        assert s.timestamp != ""


class TestEpisodicMemory:
    """Test episodic memory operations."""

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, memory, summary):
        await memory.store_session(summary)
        sessions = await memory.get_recent_sessions(limit=5)
        assert len(sessions) == 1
        assert sessions[0].issue_id == 42

    @pytest.mark.asyncio
    async def test_get_failed_issues(self, memory):
        await memory.store_session(
            SessionSummary(issue_id=1, task_type="bug", success=False, summary="failed")
        )
        await memory.store_session(
            SessionSummary(issue_id=2, task_type="bug", success=True, summary="ok")
        )
        failed = await memory.get_failed_issues()
        assert failed == [1]

    @pytest.mark.asyncio
    async def test_get_session_for_issue(self, memory, summary):
        await memory.store_session(summary)
        result = await memory.get_session_for_issue(42)
        assert result is not None
        assert result.issue_id == 42

    @pytest.mark.asyncio
    async def test_get_session_for_unknown_issue(self, memory):
        result = await memory.get_session_for_issue(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_has_attempted(self, memory, summary):
        await memory.store_session(summary)
        assert await memory.has_attempted(42)
        assert not await memory.has_attempted(99)

    @pytest.mark.asyncio
    async def test_recent_sessions_respects_limit(self, memory):
        for i in range(5):
            await memory.store_session(
                SessionSummary(
                    issue_id=i, task_type="test", success=True, summary=f"task {i}"
                )
            )
        sessions = await memory.get_recent_sessions(limit=3)
        assert len(sessions) == 3
