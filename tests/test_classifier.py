"""Tests for the issue classifier — LLM calls are mocked."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from codepilot.config import Config
from codepilot.github_integration.classifier import (
    IssueClassifier,
)
from codepilot.github_integration.github_service import Issue


@pytest.fixture
def config():
    return Config(_env_file=None)


@pytest.fixture
def mock_llm():
    provider = MagicMock()
    mock_response = MagicMock()
    mock_response.content = (
        '{"type": "bug_fix", "confidence": 0.95, "reasoning": "Clear bug report"}'
    )
    provider.invoke_with_fallback = AsyncMock(return_value=mock_response)
    return provider


@pytest.fixture
def classifier(config, mock_llm):
    return IssueClassifier(mock_llm, config)


class TestClassify:
    """Test issue classification."""

    @pytest.mark.asyncio
    async def test_classify_bug(self, classifier, mock_llm):
        issue = Issue(
            id=1,
            number=42,
            title="Fix division by zero",
            body="Calculator crashes when dividing by zero",
            labels=["bug"],
            state="open",
        )
        result = await classifier.classify(issue)
        assert result.type == "bug_fix"
        assert result.confidence > 0.9

    @pytest.mark.asyncio
    async def test_classify_enhancement(self, classifier):
        issue = Issue(
            id=2,
            number=43,
            title="Add modulo operation",
            body="Support the % operator",
            labels=["enhancement"],
            state="open",
        )
        classifier._llm.invoke_with_fallback = AsyncMock(
            return_value=MagicMock(
                content=(
                    '{"type": "feature_addition", "confidence": 0.88, '
                    '"reasoning": "New feature request"}'
                )
            )
        )
        result = await classifier.classify(issue)
        assert result.type == "feature_addition"

    @pytest.mark.asyncio
    async def test_cache_prevents_duplicate_calls(self, classifier, mock_llm):
        issue = Issue(
            id=1,
            number=42,
            title="Fix division by zero",
            body="Calculator crashes",
            labels=["bug"],
            state="open",
        )
        await classifier.classify(issue)
        await classifier.classify(issue)
        assert mock_llm.invoke_with_fallback.call_count == 1

    @pytest.mark.asyncio
    async def test_handles_markdown_json(self, classifier):
        issue = Issue(
            id=3,
            number=44,
            title="Update requests library",
            body="Bump from 2.28 to 2.31",
            labels=["dependencies"],
            state="open",
        )
        classifier._llm.invoke_with_fallback = AsyncMock(
            return_value=MagicMock(
                content=(
                    '```json\n{"type": "dependency_update", "confidence": 0.9, '
                    '"reasoning": "Dependency bump"}\n```'
                )
            )
        )
        result = await classifier.classify(issue)
        assert result.type == "dependency_update"
