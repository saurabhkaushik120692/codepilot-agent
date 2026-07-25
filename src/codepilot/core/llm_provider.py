"""Multi-provider LLM factory with automatic fallback.

Primary: Claude Sonnet (Anthropic)
Fallback chain: GPT-4o (OpenAI) → Gemini 1.5 Pro (Google)

The fallback activates when the primary provider returns a rate limit
or API error. This ensures the system stays operational even when
one provider is temporarily unavailable.
"""

import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from codepilot.config import Config

logger = logging.getLogger(__name__)


class LLMProviderError(Exception):
    """Raised when all LLM providers fail."""


class LLMProvider:
    """Factory for creating LLM instances with automatic fallback."""

    def __init__(self, config: Config):
        self._config = config

    def _create_model(
        self, provider: str, model: str
    ) -> BaseChatModel:
        """Create an LLM instance for the given provider and model.

        Args:
            provider: One of 'anthropic', 'openai', 'google'.
            model: The model identifier (e.g., 'claude-sonnet-4-20250514').

        Raises:
            ValueError: If the provider is unknown.
        """
        match provider:
            case "anthropic":
                return ChatAnthropic(
                    model=model,
                    api_key=self._config.anthropic_api_key,
                )
            case "openai":
                return ChatOpenAI(
                    model=model,
                    api_key=self._config.openai_api_key,
                )
            case "google":
                return ChatGoogleGenerativeAI(
                    model=model,
                    google_api_key=self._config.google_api_key,
                )
            case _:
                raise ValueError(
                    f"Unknown LLM provider: {provider}"
                )

    def get_primary(self) -> BaseChatModel:
        """Return the primary LLM (Claude Sonnet by default)."""
        return self._create_model(
            self._config.primary_provider,
            self._config.primary_model,
        )

    def get_model(
        self,
        provider: str | None = None,
        model: str | None = None,
    ) -> BaseChatModel:
        """Return a specific provider's model, or the primary."""
        if provider and model:
            return self._create_model(provider, model)
        return self.get_primary()

    def get_fallback_chain(self) -> list[BaseChatModel]:
        """Return [primary, fallback1, fallback2, ...]."""
        chain = [self.get_primary()]
        for provider, model in self._config.fallback_chain:
            try:
                chain.append(
                    self._create_model(provider, model)
                )
            except Exception as e:
                logger.warning(
                    f"Could not create fallback "
                    f"{provider}:{model}: {e}"
                )
        return chain

    async def invoke_with_fallback(
        self, messages: list, **kwargs: Any
    ) -> Any:
        """Try each provider in order until one succeeds.

        Args:
            messages: The messages to send to the LLM.
            **kwargs: Additional arguments passed to the LLM.

        Returns:
            The LLM response from the first successful provider.

        Raises:
            LLMProviderError: If all providers fail.
        """
        chain = self.get_fallback_chain()
        last_error: Exception | None = None

        for i, llm in enumerate(chain):
            try:
                logger.debug(
                    f"Trying LLM provider {i + 1}/{len(chain)}"
                )
                result = await llm.ainvoke(messages, **kwargs)
                return result
            except Exception as e:
                logger.warning(
                    f"LLM provider {i + 1} failed: {e}"
                )
                last_error = e
                continue

        raise LLMProviderError(
            f"All {len(chain)} LLM providers failed. "
            f"Last error: {last_error}"
        )
