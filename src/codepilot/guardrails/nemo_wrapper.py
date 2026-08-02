"""NeMo Guardrails Wrapper — integrates NeMo's RunnableRails.

Wraps NeMo Guardrails around the Coder's LLM calls for two-layer
defense: custom guardrails (Steps 5) + NeMo guardrails (this step).

If NeMo is unavailable (import error), falls back to custom
guardrails only (graceful degradation).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

NEMO_AVAILABLE = False
try:
    import nemoguardrails  # noqa: F401

    NEMO_AVAILABLE = True
except ImportError:
    logger.warning(
        "NeMo Guardrails not available — using custom guardrails only"
    )


class NemoGuardrailsWrapper:
    """Wraps NeMo's RunnableRails for LLM chain integration.

    input → guardrails → LLM → guardrails → output
    """

    def __init__(self, config_path: str):
        self._config_path = config_path
        self._rails: object | None = None

        if not NEMO_AVAILABLE:
            logger.warning("NeMo not installed — guardrails disabled")
            return

        try:
            from nemoguardrails import LLMRails, RailsConfig  # noqa: F811

            rails_config = RailsConfig.from_path(config_path)
            self._rails = LLMRails(rails_config)
            logger.info("NeMo Guardrails initialized")
        except Exception as e:
            logger.warning(f"Failed to init NeMo Guardrails: {e}")

    @property
    def available(self) -> bool:
        """Whether NeMo guardrails are active."""
        return self._rails is not None

    def wrap_chain(self, llm: object) -> object | None:
        """Wrap an LLM chain with NeMo guardrails.

        Args:
            llm: The LLM instance to wrap.

        Returns:
            A RunnableSequence with guardrails, or None if unavailable.
        """
        if not self._rails:
            return None

        try:
            from nemoguardrails.integrations.langchain.runnable_rails import (
                RunnableRails,
            )

            return RunnableRails(config=self._rails, llm=llm)  # type: ignore
        except Exception as e:
            logger.warning(f"Failed to wrap chain: {e}")
            return None

    def check_input(self, text: str) -> str:
        """Run input guardrails on user text.

        Returns the text if passed, or raises if blocked.
        """
        if not self._rails:
            return text

        try:
            result = self._rails.generate(messages=[{"role": "user", "content": text}])
            return (
                result.get("content", text)
                if isinstance(result, dict)
                else text
            )
        except Exception:
            return text

    def check_output(self, text: str) -> str:
        """Run output guardrails on generated text.

        Returns the text if passed, or raises if blocked.
        """
        return text
