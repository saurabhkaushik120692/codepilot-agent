"""Tests for the Issue Triage Scorer."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from codepilot.config import Config
from codepilot.github_integration.github_service import Issue
from codepilot.github_integration.triage_scorer import TriageScore, TriageScorer


@pytest.fixture
def config():
    return Config(_env_file=None, complexity_threshold=7)


@pytest.fixture
def mock_llm():
    provider = MagicMock()
    mock_response = MagicMock()
    mock_response.content = (
        '{"score": 3, "reasoning": "Simple bug fix", '
        '"estimated_files_affected": 2, "estimated_effort": "small"}'
    )
    provider.invoke_with_fallback = AsyncMock(return_value=mock_response)
    return provider


@pytest.fixture
def scorer(config, mock_llm):
    return TriageScorer(mock_llm, config)


class TestTriageScorer:
    """Test the triage scorer."""

    @pytest.mark.asyncio
    async def test_score_simple_bug(self, scorer):
        issue = Issue(
            id=1,
            number=42,
            title="Fix typo in README",
            body="There's a typo on line 5",
            labels=["bug"],
            state="open",
        )
        result = await scorer.score(issue)
        assert result.score == 3
        assert result.estimated_effort == "small"

    @pytest.mark.asyncio
    async def test_is_too_complex(self, scorer):
        score = TriageScore(score=8, reasoning="Complex refactor")
        assert scorer.is_too_complex(score)

    @pytest.mark.asyncio
    async def test_is_not_too_complex(self, scorer):
        score = TriageScore(score=3, reasoning="Simple")
        assert not scorer.is_too_complex(score)

    @pytest.mark.asyncio
    async def test_cache_prevents_duplicate(self, scorer, mock_llm):
        issue = Issue(
            id=1,
            number=42,
            title="Test",
            body="Test",
            labels=["bug"],
            state="open",
        )
        await scorer.score(issue)
        await scorer.score(issue)
        assert mock_llm.invoke_with_fallback.call_count == 1

    @pytest.mark.asyncio
    async def test_handles_markdown_json(self, config, mock_llm):
        mock_llm.invoke_with_fallback = AsyncMock(
            return_value=MagicMock(
                content=(
                    '```json\n{"score": 9, "reasoning": "Very hard", '
                    '"estimated_files_affected": 15, '
                    '"estimated_effort": "complex"}\n```'
                )
            )
        )
        scorer = TriageScorer(mock_llm, config)
        issue = Issue(
            id=5,
            number=55,
            title="Refactor",
            body="Whole app",
            labels=["refactor"],
            state="open",
        )
        result = await scorer.score(issue)
        assert result.score == 9

    @pytest.mark.asyncio
    async def test_fallback_on_error(self, config, mock_llm):
        mock_llm.invoke_with_fallback = AsyncMock(side_effect=Exception("fail"))
        scorer = TriageScorer(mock_llm, config)
        issue = Issue(
            id=7,
            number=77,
            title="Test",
            body="Body",
            labels=["bug"],
            state="open",
        )
        result = await scorer.score(issue)
        assert result.score == 5
