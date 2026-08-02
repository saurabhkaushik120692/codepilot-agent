"""Tests for LangSmith tracing manager."""

from unittest.mock import patch

import pytest

from codepilot.config import Config
from codepilot.core.tracing import TracingManager


@pytest.fixture
def config():
    return Config(
        _env_file=None,
        langsmith_enabled=False,
        langchain_api_key="test-key",
    )


class TestTracingManager:
    """Test the tracing manager."""

    def test_disabled_by_default(self, config):
        mgr = TracingManager(config)
        assert not mgr.is_enabled()

    def test_callbacks_empty_when_disabled(self, config):
        mgr = TracingManager(config)
        callbacks = mgr.get_callbacks("Orchestrator", issue_id=42)
        assert callbacks == []

    def test_run_config_empty_when_disabled(self, config):
        mgr = TracingManager(config)
        run_config = mgr.create_run_config("Coder", task_type="bug_fix")
        assert run_config == {}

    def test_disabled_when_langsmith_unavailable(self, config):
        config.langsmith_enabled = True
        with patch("codepilot.core.tracing.LANGSMITH_AVAILABLE", False):
            mgr = TracingManager(config)
            assert not mgr.is_enabled()
