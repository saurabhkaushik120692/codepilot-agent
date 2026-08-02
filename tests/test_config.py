"""Tests for the configuration system."""

from codepilot.config import Config


class TestConfigDefaults:
    """Test that Config loads with sensible defaults."""

    def test_loads_without_env_file(self):
        """Config should work even if .env is missing."""
        config = Config(_env_file=None)
        assert config.primary_llm == "google:gemini-1.5-pro"

    def test_default_poll_interval(self):
        config = Config(_env_file=None)
        assert config.poll_interval_minutes == 5

    def test_default_max_coder_retries(self):
        config = Config(_env_file=None)
        assert config.max_coder_retries == 3

    def test_default_summarization_enabled(self):
        config = Config(_env_file=None)
        assert config.auto_summarization_enabled is True

    def test_default_summarization_threshold(self):
        config = Config(_env_file=None)
        assert config.summarization_threshold == 20


class TestConfigParsing:
    """Test the helper properties that parse compound config values."""

    def test_primary_provider(self):
        config = Config(_env_file=None)
        assert config.primary_provider == "google"

    def test_primary_model(self):
        config = Config(_env_file=None)
        assert config.primary_model == "gemini-1.5-pro"

    def test_fallback_chain(self):
        config = Config(_env_file=None)
        assert config.fallback_chain == [
            ("groq", "llama-3.2-90b-text-preview"),
            ("anthropic", "claude-sonnet-4-20250514"),
        ]

    def test_custom_primary_llm(self, monkeypatch):
        monkeypatch.setenv("PRIMARY_LLM", "openai:gpt-4o")
        config = Config(_env_file=None)
        assert config.primary_provider == "openai"
        assert config.primary_model == "gpt-4o"


class TestConfigEnvOverrides:
    """Test that environment variables override defaults."""

    def test_env_overrides_poll_interval(self, monkeypatch):
        monkeypatch.setenv("POLL_INTERVAL_MINUTES", "10")
        config = Config(_env_file=None)
        assert config.poll_interval_minutes == 10

    def test_env_overrides_max_retries(self, monkeypatch):
        monkeypatch.setenv("MAX_CODER_RETRIES", "5")
        config = Config(_env_file=None)
        assert config.max_coder_retries == 5

    def test_env_overrides_api_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
        config = Config(_env_file=None)
        assert config.anthropic_api_key == "sk-ant-test-key"
