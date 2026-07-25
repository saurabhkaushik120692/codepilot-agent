"""CodePilot entry point.

Wires up all components and starts the Orchestrator.
"""

import asyncio
import logging

from codepilot.agents.orchestrator import Orchestrator
from codepilot.config import Config
from codepilot.core.agent_factory import DeepAgentFactory
from codepilot.core.llm_provider import LLMProvider
from codepilot.core.tool_registry import ToolRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def startup() -> Orchestrator:
    """Initialize all components and return the Orchestrator.

    Startup order (follows dependency chain):
    1. Config — loads .env and environment variables
    2. LLMProvider — creates LLM instances with fallback
    3. ToolRegistry — manages available tools per role
    4. DeepAgentFactory — creates agents through deepagents
    5. Orchestrator — the root agent
    """
    logger.info("Starting CodePilot...")

    # 1. Load config
    config = Config()
    logger.info(
        "Config loaded — primary LLM: "
        f"{config.primary_llm}"
    )

    # 2. Create LLM provider
    llm_provider = LLMProvider(config)
    logger.info("LLM provider initialized")

    # 3. Create tool registry (tools registered in Phase 3+)
    tool_registry = ToolRegistry()
    logger.info("Tool registry initialized")

    # 4. Create agent factory
    factory = DeepAgentFactory(
        config, llm_provider, tool_registry
    )
    logger.info("Agent factory initialized")

    # 5. Create Orchestrator
    orchestrator = Orchestrator.create(factory, config)
    logger.info("Orchestrator created — ready for tasks")

    return orchestrator


async def main() -> None:
    """Main async entry point."""
    orchestrator = await startup()
    await orchestrator.start_idle_loop()


def entrypoint() -> None:
    """Sync entry point for console_scripts."""
    asyncio.run(main())


if __name__ == "__main__":
    entrypoint()
