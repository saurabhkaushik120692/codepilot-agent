"""Semantic Memory — lessons learned from past tasks.

ChromaDB-backed semantic memory that stores "lessons learned"
and retrieves them by similarity to new issues. Answers "have
we seen something like this before?" across different issues.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

COLLECTION_NAME = "codepilot_lessons"


@dataclass
class Lesson:
    """A lesson learned from a past task."""

    issue_id: int
    task_type: str
    problem: str
    solution: str
    pitfalls: str = ""
    patterns: list[str] = field(default_factory=list)


class SemanticMemory:
    """ChromaDB-backed semantic memory for lessons learned.

    Stores lessons from completed tasks and retrieves similar
    ones when starting new tasks. Uses ChromaDB's default
    embedding function.
    """

    def __init__(self, persist_dir: str):
        self._persist_dir = persist_dir
        self._collection: Any = None
        self._lessons: list[Lesson] = []

    def _get_collection(self) -> Any:
        """Lazy-init the ChromaDB collection."""
        if self._collection is not None:
            return self._collection

        try:
            import chromadb  # noqa: F811

            client = chromadb.PersistentClient(path=self._persist_dir)
            try:
                self._collection = client.get_collection(COLLECTION_NAME)
            except Exception:
                self._collection = client.create_collection(COLLECTION_NAME)
            return self._collection
        except Exception:
            logger.warning("ChromaDB not available, using in-memory fallback")
            return None

    async def store_lesson(self, lesson: Lesson) -> None:
        """Embed and store a lesson."""
        self._lessons.append(lesson)

        collection = self._get_collection()
        if collection is not None:
            try:
                doc = (
                    f"Problem: {lesson.problem}\n"
                    f"Solution: {lesson.solution}\n"
                    f"Pitfalls: {lesson.pitfalls}"
                )
                collection.add(
                    ids=[str(lesson.issue_id)],
                    documents=[doc],
                    metadatas=[
                        {
                            "issue_id": lesson.issue_id,
                            "task_type": lesson.task_type,
                            "patterns": ",".join(lesson.patterns),
                        }
                    ],
                )
            except Exception as e:
                logger.warning(f"Failed to store lesson: {e}")

    async def retrieve_similar(self, query: str, top_k: int = 3) -> list[Lesson]:
        """Find lessons similar to the query.

        Args:
            query: The task description or issue text.
            top_k: Maximum number of results.

        Returns:
            List of similar lessons sorted by relevance.
        """
        collection = self._get_collection()
        if collection is not None:
            try:
                results = collection.query(query_texts=[query], n_results=top_k)
                ids: list[str] = []
                for doc_id in results.get("ids", [[]])[0]:
                    ids.append(doc_id)

                found: list[Lesson] = []
                for doc_id in ids:
                    for lesson in self._lessons:
                        if str(lesson.issue_id) == doc_id:
                            found.append(lesson)
                return found
            except Exception as e:
                logger.warning(f"Retrieval failed: {e}")

        return [
            lesson
            for lesson in self._lessons
            if any(
                word in lesson.problem.lower()
                for word in query.lower().split()
                if len(word) > 2
            )
        ][:top_k]

    async def get_patterns_for_type(self, task_type: str) -> list[str]:
        """Get common patterns for a task type."""
        patterns: list[str] = []
        for lesson in self._lessons:
            if lesson.task_type == task_type:
                patterns.extend(lesson.patterns)
        return list(set(patterns))
