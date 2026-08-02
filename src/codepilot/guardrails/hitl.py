"""HITL (Human-in-the-Loop) System — blocks agent execution until approved.

Provides a centralized gate manager for risky operations:
PR to main, large commits, retries, diff escalations.
TUI subscribes to pending requests and renders them in the Approval panel.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class HITLAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    INSPECT = "inspect"


class HITLGateType(str, Enum):
    PR_TO_PROTECTED = "pr_to_protected"
    LARGE_COMMIT = "large_commit"
    GIT_PUSH = "git_push"
    RETRY_AFTER_FAILURES = "retry_after_failures"
    DIFF_ESCALATION = "diff_escalation"


@dataclass
class HITLRequest:
    """A pending approval request."""

    gate_type: HITLGateType
    task_id: int
    description: str
    details: str = ""
    event: asyncio.Event = field(default_factory=asyncio.Event)
    result: HITLAction | None = None


@dataclass
class HITLNotification:
    """A non-actionable alert (merge conflict, failure)."""

    type: str
    issue_id: int
    message: str
    actionable: bool = False


class HITLManager:
    """Centralized Human-in-the-Loop gate manager.

    Usage:
        manager = HITLManager()
        action = await manager.request_approval(request)
        if action == HITLAction.APPROVE:
            proceed()
    """

    def __init__(self):
        self._requests: dict[int, HITLRequest] = {}
        self._notifications: list[HITLNotification] = []

    async def request_approval(self, request: HITLRequest) -> HITLAction:
        """Block until the human responds. Returns the action.

        Args:
            request: The HITLRequest to await approval for.

        Returns:
            The HITLAction chosen by the human.
        """
        self._requests[request.task_id] = request
        logger.info(f"HITL gate: {request.gate_type.value} for task {request.task_id}")
        await request.event.wait()
        return request.result or HITLAction.REJECT

    def should_gate(self, gate_type: HITLGateType, context: dict) -> bool:
        """Check if this operation needs HITL approval.

        Args:
            gate_type: The type of gate to check.
            context: Additional context (file count, retry count, etc.)

        Returns:
            True if HITL approval is required.
        """
        if gate_type == HITLGateType.PR_TO_PROTECTED:
            return context.get("target_branch", "main") in ("main", "master")
        if gate_type == HITLGateType.LARGE_COMMIT:
            return context.get("file_count", 0) > 5
        if gate_type == HITLGateType.GIT_PUSH:
            return True
        if gate_type == HITLGateType.RETRY_AFTER_FAILURES:
            return context.get("retry_count", 0) >= 2
        if gate_type == HITLGateType.DIFF_ESCALATION:
            return True
        return False

    def resolve(self, task_id: int, action: HITLAction) -> bool:
        """Called by TUI when user approves/rejects.

        Args:
            task_id: The task to resolve.
            action: The human's decision.

        Returns:
            True if the task was found and resolved.
        """
        request = self._requests.get(task_id)
        if not request:
            return False
        request.result = action
        request.event.set()
        logger.info(f"HITL resolved: task {task_id} → {action.value}")
        return True

    def get_pending(self) -> list[HITLRequest]:
        """Get all pending approval requests."""
        return [r for r in self._requests.values() if not r.event.is_set()]

    def notify(self, notification: HITLNotification) -> None:
        """Post a non-actionable notification."""
        self._notifications.append(notification)
        logger.info(
            f"HITL notification: {notification.type} for issue #{notification.issue_id}"
        )

    def get_notifications(self) -> list[HITLNotification]:
        """Get all outstanding notifications."""
        return list(self._notifications)

    def clear_notifications(self) -> None:
        """Clear all notifications."""
        self._notifications.clear()
