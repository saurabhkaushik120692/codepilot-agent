"""Issue Triage Scorer — scores issues 1-10 for estimated complexity.

Helps CodePilot focus on issues it can actually solve by scoring
complexity before attempting. Issues above COMPLEXITY_THRESHOLD
(default 7) are skipped to avoid wasted LLM calls.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from codepilot.config import Config
from codepilot.core.llm_provider import LLMProvider
from codepilot.github_integration.github_service import Issue

logger = logging.getLogger(__name__)


@dataclass
class TriageScore:
    """Complexity score for an issue (1-10)."""

    score: int
    reasoning: str
    estimated_files_affected: int = 0
    estimated_effort: str = "unknown"


class TriageScorer:
    """Scores issues by estimated complexity using the LLM.

    Results are cached by issue ID to avoid redundant LLM calls.
    """

    def __init__(self, llm_provider: LLMProvider, config: Config):
        self._llm = llm_provider
        self._config = config
        self._cache: dict[int, TriageScore] = {}

    async def score(self, issue: Issue, repo_map: str | None = None) -> TriageScore:
        """Score issue complexity 1-10.

        Args:
            issue: The GitHub issue to score.
            repo_map: Optional repo map for context.

        Returns:
            A TriageScore with the complexity rating.
        """
        if issue.id in self._cache:
            return self._cache[issue.id]

        prompt = (
            f"Score this issue's complexity 1-10 (1=trivial, 10=extremely complex).\n\n"
            f"Title: {issue.title}\n"
            f"Body: {issue.body[:1500]}\n"
            f"Labels: {', '.join(issue.labels)}\n"
            f"Assignee: {issue.assignee or 'none'}\n\n"
            "Consider: number of files likely affected, risk, dependencies, "
            "type of change needed.\n\n"
            'Respond with JSON: {"score": 1-10, "reasoning": "...", '
            '"estimated_files_affected": N, '
            '"estimated_effort": "trivial|small|medium|large|complex"}'
        )

        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You score issue complexity. Respond with valid JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ]
            response = await self._llm.invoke_with_fallback(messages)
            raw = response.content if hasattr(response, "content") else str(response)
            data = self._parse_json(raw)

            score = TriageScore(
                score=max(1, min(10, int(data.get("score", 5)))),
                reasoning=data.get("reasoning", ""),
                estimated_files_affected=int(data.get("estimated_files_affected", 0)),
                estimated_effort=data.get("estimated_effort", "medium"),
            )

            self._cache[issue.id] = score
            logger.info(
                f"Issue #{issue.number} score: {score.score}/10 "
                f"({score.estimated_effort})"
            )
            return score

        except Exception as e:
            logger.warning(f"Triage scoring failed for #{issue.number}: {e}")
            return TriageScore(score=5, reasoning="Scoring failed, defaulting to 5")

    def is_too_complex(self, score: TriageScore) -> bool:
        """Check if an issue exceeds the complexity threshold."""
        return score.score > self._config.complexity_threshold

    def _parse_json(self, raw: str) -> dict:
        text = raw.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)

    def clear_cache(self) -> None:
        self._cache.clear()
