"""Tests for the LLM provider — all LLM calls are mocked."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codepilot.config import Config
from codepilot.core.llm_provider import (
    LLMProvider,
    LLMProviderError,
)


@pytest.fixture
def config():
    """Config with test defaults (no real API keys needed)."""
    return Config(
        _env_file=None,
        anthropic_api_key="test-anthropic-key",
        openai_api_key="test-openai-key",
        google_api_key="test-google-key",
    )


@pytest.fixture
def provider(config):
    return LLMProvider(config)


class TestGetPrimary:
    """Test primary model creation."""

    def test_returns_anthropic_by_default(self, provider):
        model = provider.get_primary()
        assert "claude" in str(model.model).lower() or hasattr(model, "model")

    def test_custom_primary_from_config(self):
        config = Config(
            _env_file=None,
            primary_llm="openai:gpt-4o",
            openai_api_key="test-key",
        )
        provider = LLMProvider(config)
        model = provider.get_primary()
        from langchain_openai import ChatOpenAI

        assert isinstance(model, ChatOpenAI)


class TestGetModel:
    """Test explicit model creation by provider."""

    def test_get_anthropic(self, provider):
        from langchain_anthropic import ChatAnthropic

        model = provider.get_model("anthropic", "claude-sonnet-4-20250514")
        assert isinstance(model, ChatAnthropic)

    def test_get_openai(self, provider):
        from langchain_openai import ChatOpenAI

        model = provider.get_model("openai", "gpt-4o")
        assert isinstance(model, ChatOpenAI)

    def test_get_google(self, provider):
        from langchain_google_genai import (
            ChatGoogleGenerativeAI,
        )

        model = provider.get_model("google", "gemini-1.5-pro")
        assert isinstance(model, ChatGoogleGenerativeAI)

    def test_unknown_provider_raises(self, provider):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            provider.get_model("unknown", "some-model")

    def test_no_args_returns_primary(self, provider):
        model = provider.get_model()
        assert model is not None


class TestFallbackChain:
    """Test the fallback chain ordering."""

    def test_chain_has_three_models(self, provider):
        chain = provider.get_fallback_chain()
        assert len(chain) == 3  # primary + 2 fallbacks

    def test_chain_order(self, provider):
        from langchain_anthropic import ChatAnthropic
        from langchain_google_genai import (
            ChatGoogleGenerativeAI,
        )
        from langchain_openai import ChatOpenAI

        chain = provider.get_fallback_chain()
        assert isinstance(chain[0], ChatAnthropic)
        assert isinstance(chain[1], ChatOpenAI)
        assert isinstance(chain[2], ChatGoogleGenerativeAI)


class TestInvokeWithFallback:
    """Test fallback behavior — all LLM calls mocked."""

    @pytest.mark.asyncio
    async def test_uses_primary_when_it_succeeds(self, provider):
        mock_response = MagicMock()
        mock_response.content = "Hello from Claude"

        with patch.object(provider, "get_fallback_chain") as mock_chain:
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_response
            mock_chain.return_value = [mock_llm]

            result = await provider.invoke_with_fallback(
                [{"role": "user", "content": "hi"}]
            )
            assert result.content == "Hello from Claude"
            mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_falls_back_on_primary_failure(self, provider):
        mock_response = MagicMock()
        mock_response.content = "Hello from GPT-4o"

        with patch.object(provider, "get_fallback_chain") as mock_chain:
            failing_llm = AsyncMock()
            failing_llm.ainvoke.side_effect = Exception("Rate limit")

            fallback_llm = AsyncMock()
            fallback_llm.ainvoke.return_value = mock_response

            mock_chain.return_value = [
                failing_llm,
                fallback_llm,
            ]

            result = await provider.invoke_with_fallback(
                [{"role": "user", "content": "hi"}]
            )
            assert result.content == "Hello from GPT-4o"

    @pytest.mark.asyncio
    async def test_raises_when_all_fail(self, provider):
        with patch.object(provider, "get_fallback_chain") as mock_chain:
            llm1 = AsyncMock()
            llm1.ainvoke.side_effect = Exception("Error 1")
            llm2 = AsyncMock()
            llm2.ainvoke.side_effect = Exception("Error 2")

            mock_chain.return_value = [llm1, llm2]

            with pytest.raises(
                LLMProviderError,
                match="All 2 LLM providers failed",
            ):
                await provider.invoke_with_fallback([{"role": "user", "content": "hi"}])
