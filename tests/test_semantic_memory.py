"""Tests for semantic memory."""

import pytest

from codepilot.memory.semantic import Lesson, SemanticMemory


@pytest.fixture
def memory():
    m = SemanticMemory(persist_dir="/tmp/test_chroma")
    m._get_collection = lambda: None  # Force keyword fallback
    return m


@pytest.fixture
def lesson():
    return Lesson(
        issue_id=42,
        task_type="bug_fix",
        problem="Division by zero in calculator",
        solution="Added zero check before division",
        pitfalls="Didn't catch negative divisors",
        patterns=["defensive programming", "input validation"],
    )


class TestLesson:
    """Test the Lesson dataclass."""

    def test_defaults(self):
        lesson = Lesson(issue_id=1, task_type="bug", problem="x", solution="y")
        assert lesson.pitfalls == ""
        assert lesson.patterns == []


class TestSemanticMemory:
    """Test semantic memory operations."""

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, memory, lesson):
        await memory.store_lesson(lesson)
        results = await memory.retrieve_similar("division by zero")
        assert len(results) == 1
        assert results[0].issue_id == 42

    @pytest.mark.asyncio
    async def test_retrieve_no_match(self, memory):
        results = await memory.retrieve_similar("nonexistent topic")
        assert results == []

    @pytest.mark.asyncio
    async def test_retrieve_respects_top_k(self, memory):
        await memory.store_lesson(
            Lesson(issue_id=1, task_type="bug", problem="memory leak", solution="fix 1")
        )
        await memory.store_lesson(
            Lesson(
                issue_id=2,
                task_type="bug",
                problem="memory usage high",
                solution="fix 2",
            )
        )
        await memory.store_lesson(
            Lesson(issue_id=3, task_type="bug", problem="high memory", solution="fix 3")
        )
        results = await memory.retrieve_similar("memory", top_k=2)
        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_get_patterns_for_type(self, memory, lesson):
        await memory.store_lesson(lesson)
        patterns = await memory.get_patterns_for_type("bug_fix")
        assert "defensive programming" in patterns
        assert "input validation" in patterns

    @pytest.mark.asyncio
    async def test_get_patterns_unknown_type(self, memory):
        patterns = await memory.get_patterns_for_type("nonexistent")
        assert patterns == []

    @pytest.mark.asyncio
    async def test_keyword_fallback_when_no_chromadb(self, memory, lesson):
        await memory.store_lesson(lesson)
        results = await memory.retrieve_similar("calculator division")
        assert len(results) == 1
