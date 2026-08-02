"""Tests for the Orchestrator agent — including state machine."""

from unittest.mock import AsyncMock, patch

import pytest

from codepilot.agents.orchestrator import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    DiffReview,
    DiffReviewResult,
    Orchestrator,
)
from codepilot.config import Config
from codepilot.core.agent_factory import DeepAgentFactory
from codepilot.core.base_agent import AgentResult, BaseAgent
from codepilot.core.llm_provider import LLMProvider
from codepilot.core.tool_registry import ToolRegistry
from codepilot.memory.episodic import EpisodicMemory, SessionSummary
from codepilot.memory.semantic import SemanticMemory
from codepilot.memory.working import TaskState, WorkingMemory
from codepilot.skills.base import SkillRegistry
from codepilot.skills.bug_fix import BugFixSkill
from codepilot.skills.feature_addition import FeatureAdditionSkill


@pytest.fixture
def config():
    return Config(
        _env_file=None,
        anthropic_api_key="test-key",
        openai_api_key="test-key",
        google_api_key="test-key",
        groq_api_key="test-key",
    )


@pytest.fixture
def mock_agent():
    agent = AsyncMock(spec=BaseAgent)
    agent.name = "Orchestrator"
    agent.invoke.return_value = AgentResult(
        success=True,
        output="I will create a TODO list for this task.",
        todos=[
            "Analyze the issue",
            "Find relevant files",
            "Implement fix",
        ],
    )
    return agent


class TestOrchestratorCreation:
    """Test Orchestrator creation."""

    def test_create_with_mock_agent(self, mock_agent, config):
        orchestrator = Orchestrator(agent=mock_agent, config=config)
        assert orchestrator._agent == mock_agent

    @patch(
        "codepilot.core.agent_factory.DEEPAGENTS_AVAILABLE",
        False,
    )
    def test_create_via_factory(self, config):
        factory = DeepAgentFactory(config, LLMProvider(config), ToolRegistry())
        orchestrator = Orchestrator.create(factory, config)
        assert orchestrator is not None


class TestOrchestratorSystemPrompt:
    """Test the system prompt content."""

    def test_prompt_mentions_write_todos(self):
        assert "write_todos" in ORCHESTRATOR_SYSTEM_PROMPT

    def test_prompt_mentions_subagents(self):
        assert "Repo Explorer" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "Coder" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "Test Agent" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "PR Agent" in ORCHESTRATOR_SYSTEM_PROMPT

    def test_prompt_mentions_state_machine(self):
        assert "TRIAGED" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "DONE" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "FAILED" in ORCHESTRATOR_SYSTEM_PROMPT


class TestOrchestratorHandleMessage:
    """Test message handling."""

    @pytest.mark.asyncio
    async def test_handle_message_returns_result(self, mock_agent, config):
        orchestrator = Orchestrator(agent=mock_agent, config=config)
        result = await orchestrator.handle_message("Fix the division by zero bug")
        assert isinstance(result, AgentResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_handle_message_passes_to_agent(self, mock_agent, config):
        orchestrator = Orchestrator(agent=mock_agent, config=config)
        await orchestrator.handle_message("Add modulo operation")
        mock_agent.invoke.assert_called_once()
        call_args = mock_agent.invoke.call_args
        messages = call_args[0][0]
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Add modulo operation"

    @pytest.mark.asyncio
    async def test_handle_message_with_todos(self, mock_agent, config):
        orchestrator = Orchestrator(agent=mock_agent, config=config)
        result = await orchestrator.handle_message("Fix a bug")
        assert len(result.todos) == 3
        assert "Analyze the issue" in result.todos


class TestOrchestratorStateMachine:
    """Test state machine integration."""

    def test_initial_task_state(self, mock_agent, config):
        orchestrator = Orchestrator(agent=mock_agent, config=config)
        state = orchestrator.get_task_state(1)
        assert state is None  # No task yet

    @pytest.mark.asyncio
    async def test_handle_message_creates_task(self, mock_agent, config):
        orchestrator = Orchestrator(agent=mock_agent, config=config)
        await orchestrator.handle_message("Fix the bug", issue_id=42)
        state = orchestrator.get_task_state(42)
        assert state == TaskState.EXPLORING

    @pytest.mark.asyncio
    async def test_valid_transition(self, mock_agent, config):
        orchestrator = Orchestrator(agent=mock_agent, config=config)
        await orchestrator.handle_message("Test", issue_id=1)
        result = orchestrator.transition_task(1, TaskState.IMPLEMENTING)
        assert result is True
        assert orchestrator.get_task_state(1) == TaskState.IMPLEMENTING

    @pytest.mark.asyncio
    async def test_invalid_transition(self, mock_agent, config):
        orchestrator = Orchestrator(agent=mock_agent, config=config)
        await orchestrator.handle_message("Test", issue_id=2)
        result = orchestrator.transition_task(2, TaskState.DONE)
        assert result is False
        assert orchestrator.get_task_state(2) == TaskState.EXPLORING

    @pytest.mark.asyncio
    async def test_fail_task(self, mock_agent, config):
        orchestrator = Orchestrator(agent=mock_agent, config=config)
        await orchestrator.handle_message("Test", issue_id=3)
        orchestrator.fail_task(3, "Something went wrong")
        assert orchestrator.get_task_state(3) == TaskState.FAILED


class TestStartupFlow:
    """Test the full startup sequence."""

    @patch(
        "codepilot.core.agent_factory.DEEPAGENTS_AVAILABLE",
        False,
    )
    @pytest.mark.asyncio
    async def test_startup_returns_orchestrator(self):
        from codepilot.main import startup

        orchestrator, config = await startup()
        assert isinstance(orchestrator, Orchestrator)


class TestOrchestratorIntegration:
    """Integration tests for skill + memory wiring."""

    @pytest.mark.asyncio
    async def test_skill_loaded_for_bug_task(self, mock_agent, config):
        reg = SkillRegistry()
        reg.register("bug_fix", BugFixSkill())
        orchestrator = Orchestrator(agent=mock_agent, config=config, skill_registry=reg)
        result = await orchestrator.handle_message("Fix the bug in main.py")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_skill_loaded_for_feature_task(self, mock_agent, config):
        reg = SkillRegistry()
        reg.register("feature_addition", FeatureAdditionSkill())
        orchestrator = Orchestrator(agent=mock_agent, config=config, skill_registry=reg)
        result = await orchestrator.handle_message("Add a new feature to the app")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_episodic_memory_prevents_duplicate(self, mock_agent, config):
        episodic = EpisodicMemory()
        await episodic.store_session(
            SessionSummary(
                issue_id=42, task_type="bug_fix", success=False, summary="Failed"
            )
        )
        orchestrator = Orchestrator(agent=mock_agent, config=config, episodic=episodic)
        result = await orchestrator.handle_message("Fix bug", issue_id=42)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_semantic_memory_provides_lessons(self, mock_agent, config):
        from codepilot.memory.semantic import Lesson

        semantic = SemanticMemory(persist_dir="/tmp/test_chroma")
        semantic._get_collection = lambda: None
        await semantic.store_lesson(
            Lesson(
                issue_id=10,
                task_type="bug_fix",
                problem="division by zero",
                solution="add zero check",
            )
        )
        orchestrator = Orchestrator(agent=mock_agent, config=config, semantic=semantic)
        result = await orchestrator.handle_message("Fix division by zero bug")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_full_orchestrator_with_all_wiring(self, mock_agent, config):
        reg = SkillRegistry()
        reg.register("bug_fix", BugFixSkill())
        reg.register("feature_addition", FeatureAdditionSkill())
        episodic = EpisodicMemory()
        semantic = SemanticMemory(persist_dir="/tmp/test_chroma")
        semantic._get_collection = lambda: None

        orchestrator = Orchestrator(
            agent=mock_agent,
            config=config,
            skill_registry=reg,
            episodic=episodic,
            semantic=semantic,
        )
        result = await orchestrator.handle_message(
            "Fix the division by zero bug in calculator", issue_id=100
        )
        assert result.success is True
        assert orchestrator.get_task_state(100) == TaskState.EXPLORING


class TestOrchestratorDiffReview:
    """Test the diff review step."""

    @pytest.mark.asyncio
    async def test_review_diff_auto_escalate_many_files(self, mock_agent, config):
        orchestrator = Orchestrator(agent=mock_agent, config=config)
        wm = WorkingMemory(issue_id=1)
        wm.relevant_files = [f"file_{i}.py" for i in range(15)]
        wm.current_diff = "some diff"
        result = await orchestrator.review_diff(wm)
        assert result.decision == DiffReviewResult.ESCALATE

    @pytest.mark.asyncio
    async def test_review_diff_escalate_max_retries(self, mock_agent, config):
        config.max_coder_retries = 3
        orchestrator = Orchestrator(agent=mock_agent, config=config)
        wm = WorkingMemory(issue_id=2)
        wm.relevant_files = ["main.py"]
        wm.retry_count = 3
        wm.current_diff = "diff"
        result = await orchestrator.review_diff(wm)
        assert result.decision == DiffReviewResult.ESCALATE

    @pytest.mark.asyncio
    async def test_review_diff_with_few_files(self, mock_agent, config):
        orchestrator = Orchestrator(agent=mock_agent, config=config)
        mock_agent.invoke.return_value.output = (
            '{"decision": "APPROVE", "feedback": "Good", "confidence": 0.9}'
        )
        wm = WorkingMemory(issue_id=3)
        wm.relevant_files = ["main.py", "utils.py"]
        wm.current_diff = "--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n+fix"
        result = await orchestrator.review_diff(wm)
        assert result.decision in (
            DiffReviewResult.APPROVE,
            DiffReviewResult.RETRY,
            DiffReviewResult.ESCALATE,
        )

    @pytest.mark.asyncio
    async def test_review_diff_fallback_on_error(self, mock_agent, config):
        orchestrator = Orchestrator(agent=mock_agent, config=config)
        mock_agent.invoke.side_effect = Exception("LLM error")
        wm = WorkingMemory(issue_id=4)
        wm.relevant_files = ["main.py"]
        wm.current_diff = "diff"
        result = await orchestrator.review_diff(wm)
        assert result.decision == DiffReviewResult.APPROVE


class TestDiffReviewResult:
    def test_enum_values(self):
        assert DiffReviewResult.APPROVE.value == "APPROVE"
        assert DiffReviewResult.RETRY.value == "RETRY"
        assert DiffReviewResult.ESCALATE.value == "ESCALATE"

    def test_diff_review_dataclass(self):
        review = DiffReview(
            decision=DiffReviewResult.APPROVE,
            feedback="Looks good",
            confidence=0.95,
        )
        assert review.decision == DiffReviewResult.APPROVE
        assert review.confidence == 0.95
