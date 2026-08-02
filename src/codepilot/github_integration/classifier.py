"""Issue task classifier.

Uses Claude Sonnet (via LLMProvider) to classify each GitHub issue
into one of: bug_fix, feature_addition, dependency_update,
documentation, or config_change.
"""

import hashlib
import json
import logging
from dataclasses import dataclass

from codepilot.config import Config
from codepilot.core.llm_provider import LLMProvider
from codepilot.github_integration.github_service import Issue

logger = logging.getLogger(__name__)

TASK_TYPES = [
    "bug_fix",
    "feature_addition",
    "dependency_update",
    "documentation",
    "config_change",
]


@dataclass
class TaskClassification:
    """Result of classifying an issue."""

    type: str  # One of TASK_TYPES
    confidence: float  # 0.0 to 1.0
    reasoning: str = ""


class ClassifierError(Exception):
    """Raised when classification fails."""


class IssueClassifier:
    """Classifies GitHub issues into task types using an LLM.

    Results are cached by issue ID to avoid redundant LLM calls.
    """

    def __init__(self, llm_provider: LLMProvider, config: Config):
        self._llm = llm_provider
        self._config = config
        self._cache: dict[str, TaskClassification] = {}

    def _cache_key(self, issue: Issue) -> str:
        """Generate a cache key from issue content."""
        raw = f"{issue.number}:{issue.title}:{issue.body}"
        return hashlib.md5(raw.encode()).hexdigest()

    async def classify(self, issue: Issue) -> TaskClassification:
        """Classify an issue into a task type.

        Args:
            issue: The GitHub issue to classify.

        Returns:
            A TaskClassification with type, confidence, and reasoning.
        """
        key = self._cache_key(issue)
        if key in self._cache:
            logger.debug(f"Cache hit for issue #{issue.number}")
            return self._cache[key]

        prompt = (
            f"Classify this GitHub issue into exactly one task type.\n\n"
            f"Title: {issue.title}\n"
            f"Body: {issue.body[:2000]}\n"
            f"Labels: {', '.join(issue.labels)}\n\n"
            f"Choose from: {', '.join(TASK_TYPES)}\n\n"
            f"Respond with JSON: "
            '{"type": "...", "confidence": 0.0-1.0, "reasoning": "..."}'
        )

        try:
            messages = [
                {
                    "role": "system",
                    "content": "You classify GitHub issues into task types. "
                    "Respond with valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ]
            response = await self._llm.invoke_with_fallback(messages)
            raw = response.content if hasattr(response, "content") else str(response)

            result = self._parse_json_response(raw)

            classification = TaskClassification(
                type=result.get("type", "bug_fix"),
                confidence=float(result.get("confidence", 0.5)),
                reasoning=result.get("reasoning", ""),
            )

            if classification.type not in TASK_TYPES:
                logger.warning(
                    f"Invalid classification '{classification.type}' for issue "
                    f"#{issue.number}, defaulting to bug_fix"
                )
                classification.type = "bug_fix"

            self._cache[key] = classification
            logger.info(
                f"Classified issue #{issue.number} as {classification.type} "
                f"(confidence={classification.confidence:.2f})"
            )
            return classification

        except Exception as e:
            raise ClassifierError(
                f"Failed to classify issue #{issue.number}: {e}"
            ) from e

    def _parse_json_response(self, raw: str) -> dict:
        """Extract JSON from LLM response (handles markdown fences)."""
        text = raw.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)

    def clear_cache(self) -> None:
        """Clear the classification cache."""
        self._cache.clear()
