"""Episodic Memory — session summaries and failed issue tracking.

Persists "what happened before" using LangGraph's Memory Store.
Tracks session summaries, failed issues, and past attempts.
The Orchestrator queries this before starting a task to avoid
repeating mistakes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SessionSummary:
    """Summary of a completed task session."""

    issue_id: int
    task_type: str
    success: bool
    summary: str
    files_changed: list[str] = field(default_factory=list)
    lessons_learned: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class EpisodicMemory:
    """Persists session summaries using LangGraph Memory Store.

    Uses InMemoryStore by default (upgradeable to AsyncSqliteSaver
    for persistent storage).
    """

    NAMESPACE = ("codepilot", "sessions")

    def __init__(self, store: Any = None):
        if store is None:
            try:
                from langgraph.store.memory import InMemoryStore

                store = InMemoryStore()
            except ImportError:
                logger.warning("langgraph.store not available, using dict fallback")
                store = None
        self._store = store
        self._sessions: list[SessionSummary] = []

    async def store_session(self, summary: SessionSummary) -> None:
        """Store a session summary."""
        self._sessions.append(summary)
        logger.debug(f"Stored session for issue #{summary.issue_id}")

        if self._store is not None:
            try:
                await self._store.aput(
                    self.NAMESPACE,
                    str(summary.issue_id),
                    {
                        "issue_id": summary.issue_id,
                        "task_type": summary.task_type,
                        "success": summary.success,
                        "summary": summary.summary,
                        "files_changed": summary.files_changed,
                        "lessons_learned": summary.lessons_learned,
                        "timestamp": summary.timestamp,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to persist session: {e}")

    async def get_recent_sessions(self, limit: int = 3) -> list[SessionSummary]:
        """Retrieve the N most recent session summaries."""
        sorted_sessions = sorted(
            self._sessions,
            key=lambda s: s.timestamp,
            reverse=True,
        )
        return sorted_sessions[:limit]

    async def get_failed_issues(self) -> list[int]:
        """Return IDs of issues that failed in previous attempts."""
        return [s.issue_id for s in self._sessions if not s.success]

    async def get_session_for_issue(self, issue_id: int) -> SessionSummary | None:
        """Check if we've attempted this issue before."""
        for s in self._sessions:
            if s.issue_id == issue_id:
                return s
        return None

    async def has_attempted(self, issue_id: int) -> bool:
        """Check if an issue has been attempted."""
        return any(s.issue_id == issue_id for s in self._sessions)
