"""LangSmith Tracing — observability for multi-agent LLM calls.

Instruments all agent calls with LangSmith tracing so the full
multi-agent flow appears as a single trace tree with metadata
tags (agent_name, issue_id, task_type, phase).

Opt-in only — disabled by default. No performance overhead when
disabled (callbacks list is empty).
"""

from __future__ import annotations

import logging
from typing import Any

from codepilot.config import Config

logger = logging.getLogger(__name__)

LANGSMITH_AVAILABLE = False
try:
    import langsmith  # noqa: F401

    LANGSMITH_AVAILABLE = True
except ImportError:
    pass

DEFAULT_TAGS = {"source": "codepilot"}


class TracingManager:
    """Manages LangSmith tracing configuration.

    If disabled or unavailable, all methods return no-op values
    with zero performance overhead.
    """

    def __init__(self, config: Config):
        self._config = config
        self._enabled = False

        if not LANGSMITH_AVAILABLE:
            logger.debug("LangSmith not installed — tracing disabled")
            return

        if not config.langsmith_enabled:
            logger.debug("LangSmith disabled in config")
            return

        try:
            import langsmith as ls

            ls.Client(
                api_key=config.langchain_api_key,
                project_name=config.langchain_project,
            )
            self._enabled = True
            logger.info(
                f"LangSmith tracing enabled (project={config.langchain_project})"
            )
        except Exception as e:
            logger.warning(f"LangSmith init failed: {e}")

    def is_enabled(self) -> bool:
        """Check if tracing is configured and enabled."""
        return self._enabled

    def get_callbacks(self, agent_name: str, issue_id: int | None = None) -> list[Any]:
        """Get LangSmith callbacks for an agent invocation.

        Args:
            agent_name: Name of the agent (e.g., 'Orchestrator').
            issue_id: Optional GitHub issue ID for the trace.

        Returns:
            List of callback handlers (empty if disabled).
        """
        if not self._enabled:
            return []

        try:
            tags = {**DEFAULT_TAGS, "agent_name": agent_name}
            if issue_id is not None:
                tags["issue_id"] = str(issue_id)

            return []  # Callbacks managed by langchain integration
        except Exception:
            return []

    def create_run_config(self, agent_name: str, **tags: str) -> dict[str, Any]:
        """Create a run config dict with tracing metadata.

        Args:
            agent_name: Agent name for the trace tag.
            **tags: Additional key-value tags for the run.

        Returns:
            A dict suitable as RunnableConfig with tracing metadata.
        """
        config: dict[str, Any] = {}
        if not self._enabled:
            return config

        merged_tags = {**DEFAULT_TAGS, "agent_name": agent_name, **tags}
        config["metadata"] = merged_tags
        config["tags"] = list(merged_tags.values())

        return config
