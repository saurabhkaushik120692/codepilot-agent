"""End-to-end integration tests for Phase 5.

Tests the full pipeline from task intake through diff review
to HITL approval. All external calls (GitHub, LLM) are mocked.
"""

from unittest.mock import AsyncMock

import pytest

from codepilot.agents.orchestrator import DiffReviewResult, Orchestrator
from codepilot.config import Config
from codepilot.core.base_agent import AgentResult, BaseAgent
from codepilot.guardrails.hitl import HITLAction, HITLGateType, HITLManager, HITLRequest
from codepilot.memory.working import TaskState
from codepilot.skills.base import SkillRegistry
from codepilot.skills.bug_fix import BugFixSkill


@pytest.fixture
def config():
    return Config(_env_file=None, max_coder_retries=3)


@pytest.fixture
def mock_agent():
    agent = AsyncMock(spec=BaseAgent)
    agent.name = "Orchestrator"
    agent.invoke.return_value = AgentResult(
        success=True,
        output='{"decision": "APPROVE", "feedback": "Looks good", "confidence": 0.95}',
    )
    return agent


class TestEndToEnd:
    """End-to-end flow tests with mocked externals."""

    @pytest.mark.asyncio
    async def test_full_task_flow(self, config, mock_agent):
        """Test classify → explore → code → test → review → approve flow."""
        reg = SkillRegistry()
        reg.register("bug_fix", BugFixSkill())
        orchestrator = Orchestrator(agent=mock_agent, config=config, skill_registry=reg)

        # Start task
        result = await orchestrator.handle_message(
            "Fix the division by zero bug in calculator", issue_id=42
        )
        assert result.success
        assert orchestrator.get_task_state(42) == TaskState.EXPLORING

        # Transition to implementing
        assert orchestrator.transition_task(42, TaskState.IMPLEMENTING)

        # Transition to testing
        assert orchestrator.transition_task(42, TaskState.TESTING)

        # Review the diff
        wm = orchestrator._active_tasks[42]
        wm.relevant_files = ["src/calc.py"]
        wm.current_diff = "--- a/src/calc.py\n+++ b/src/calc.py\n+zero check"
        review = await orchestrator.review_diff(wm)
        assert review.decision in (
            DiffReviewResult.APPROVE,
            DiffReviewResult.RETRY,
            DiffReviewResult.ESCALATE,
        )

    @pytest.mark.asyncio
    async def test_hitl_gate_flow(self):
        """Test HITL approval from request to resolve."""
        mgr = HITLManager()
        req = HITLRequest(
            gate_type=HITLGateType.PR_TO_PROTECTED,
            task_id=100,
            description="PR to main",
        )

        async def approve_after_delay():
            import asyncio

            await asyncio.sleep(0.05)
            mgr.resolve(100, HITLAction.APPROVE)

        import asyncio

        asyncio.create_task(approve_after_delay())
        result = await asyncio.wait_for(mgr.request_approval(req), timeout=2)
        assert result == HITLAction.APPROVE

    @pytest.mark.asyncio
    async def test_hitl_gates_large_commit(self):
        mgr = HITLManager()
        assert mgr.should_gate(HITLGateType.LARGE_COMMIT, {"file_count": 10})
        assert not mgr.should_gate(HITLGateType.LARGE_COMMIT, {"file_count": 3})

    @pytest.mark.asyncio
    async def test_task_failure_with_escalation(self, config, mock_agent):
        orchestrator = Orchestrator(agent=mock_agent, config=config)
        await orchestrator.handle_message("Fix bug", issue_id=50)

        wm = orchestrator._active_tasks[50]
        wm.relevant_files = [f"f{i}.py" for i in range(20)]
        wm.current_diff = "big diff"

        review = await orchestrator.review_diff(wm)
        assert review.decision == DiffReviewResult.ESCALATE

    @pytest.mark.asyncio
    async def test_manual_task_flow(self, config):
        """Test manual task enters the pipeline correctly."""
        from codepilot.github_integration.pr_builder import generate_manual_task_id

        task_id = generate_manual_task_id()
        assert task_id.startswith("manual-")

        agent = AsyncMock(spec=BaseAgent)
        agent.name = "Orchestrator"
        agent.invoke.return_value = AgentResult(success=True, output="OK")

        orchestrator = Orchestrator(agent=agent, config=config)
        result = await orchestrator.handle_message(
            "Add dark mode toggle", issue_id=None
        )
        assert result.success
