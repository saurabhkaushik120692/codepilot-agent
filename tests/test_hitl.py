"""Tests for the HITL system."""

import asyncio

import pytest

from codepilot.guardrails.hitl import (
    HITLAction,
    HITLGateType,
    HITLManager,
    HITLNotification,
    HITLRequest,
)


class TestHITLRequest:
    """Test HITLRequest dataclass."""

    def test_defaults(self):
        req = HITLRequest(
            gate_type=HITLGateType.PR_TO_PROTECTED,
            task_id=42,
            description="PR to main",
        )
        assert req.result is None
        assert not req.event.is_set()


class TestHITLManager:
    """Test HITL Manager operations."""

    def test_should_gate_pr_to_main(self):
        mgr = HITLManager()
        assert mgr.should_gate(HITLGateType.PR_TO_PROTECTED, {"target_branch": "main"})
        assert not mgr.should_gate(
            HITLGateType.PR_TO_PROTECTED, {"target_branch": "dev"}
        )

    def test_should_gate_large_commit(self):
        mgr = HITLManager()
        assert mgr.should_gate(HITLGateType.LARGE_COMMIT, {"file_count": 10})
        assert not mgr.should_gate(HITLGateType.LARGE_COMMIT, {"file_count": 3})

    def test_should_gate_retry(self):
        mgr = HITLManager()
        assert mgr.should_gate(HITLGateType.RETRY_AFTER_FAILURES, {"retry_count": 3})
        assert not mgr.should_gate(
            HITLGateType.RETRY_AFTER_FAILURES, {"retry_count": 0}
        )

    def test_get_pending_empty(self):
        mgr = HITLManager()
        assert mgr.get_pending() == []

    def test_resolve_updates_result(self):
        mgr = HITLManager()
        req = HITLRequest(
            gate_type=HITLGateType.PR_TO_PROTECTED,
            task_id=1,
            description="Test",
        )
        mgr._requests[1] = req
        assert mgr.resolve(1, HITLAction.APPROVE)
        assert req.result == HITLAction.APPROVE
        assert req.event.is_set()

    def test_resolve_unknown_task(self):
        mgr = HITLManager()
        assert not mgr.resolve(999, HITLAction.APPROVE)

    @pytest.mark.asyncio
    async def test_request_approval_blocks_then_resolves(self):
        mgr = HITLManager()
        req = HITLRequest(
            gate_type=HITLGateType.PR_TO_PROTECTED,
            task_id=2,
            description="Test",
        )

        async def resolve_later():
            await asyncio.sleep(0.05)
            mgr.resolve(2, HITLAction.APPROVE)

        async def wait_for_approval():
            return await mgr.request_approval(req)

        resolve_task = asyncio.create_task(resolve_later())
        result = await asyncio.wait_for(wait_for_approval(), timeout=2)
        assert result == HITLAction.APPROVE
        await resolve_task

    def test_notifications(self):
        mgr = HITLManager()
        notif = HITLNotification(
            type="merge_conflict",
            issue_id=42,
            message="Merge conflict on main",
        )
        mgr.notify(notif)
        assert len(mgr.get_notifications()) == 1

    def test_clear_notifications(self):
        mgr = HITLManager()
        mgr.notify(HITLNotification(type="test", issue_id=1, message="test"))
        mgr.clear_notifications()
        assert len(mgr.get_notifications()) == 0

    def test_get_pending_excludes_resolved(self):
        mgr = HITLManager()
        req = HITLRequest(
            gate_type=HITLGateType.PR_TO_PROTECTED,
            task_id=3,
            description="Test",
        )
        mgr._requests[3] = req
        req.event.set()
        assert len(mgr.get_pending()) == 0
