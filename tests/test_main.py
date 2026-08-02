"""Tests for the main entry point — all external calls are mocked."""

from unittest.mock import AsyncMock, patch

import pytest

from codepilot.agents.orchestrator import Orchestrator


class TestMainStartup:
    """Test the full startup flow."""

    @patch(
        "codepilot.core.agent_factory.DEEPAGENTS_AVAILABLE",
        False,
    )
    @pytest.mark.asyncio
    async def test_startup_returns_orchestrator(self):
        from codepilot.main import startup

        orchestrator, config = await startup()
        assert isinstance(orchestrator, Orchestrator)

    @patch(
        "codepilot.core.agent_factory.DEEPAGENTS_AVAILABLE",
        False,
    )
    @pytest.mark.asyncio
    async def test_start_polling_skips_if_not_configured(self):
        from codepilot.config import Config
        from codepilot.main import start_polling

        config = Config(
            _env_file=None,
            github_app_id="",
        )
        orchestrator = AsyncMock(spec=Orchestrator)

        await start_polling(orchestrator, config)
        # Should return without error
