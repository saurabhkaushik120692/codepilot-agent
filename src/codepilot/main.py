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
from codepilot.github_integration.classifier import IssueClassifier
from codepilot.github_integration.github_service import GitHubService
from codepilot.github_integration.issue_poller import IssuePoller

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def startup() -> tuple[Orchestrator, Config]:
    """Initialize all components and return the Orchestrator and Config.

    Returns a tuple so callers can reuse the Config
    without creating a second instance.
    """
    logger.info("Starting CodePilot...")

    config = Config()
    logger.info(
        "Config loaded — primary LLM: "
        f"{config.primary_llm}"
    )

    llm_provider = LLMProvider(config)
    logger.info("LLM provider initialized")

    tool_registry = ToolRegistry()
    logger.info("Tool registry initialized")

    factory = DeepAgentFactory(
        config, llm_provider, tool_registry
    )
    logger.info("Agent factory initialized")

    orchestrator = Orchestrator.create(factory, config)
    logger.info("Orchestrator created — ready for tasks")

    return orchestrator, config


async def start_polling(
    orchestrator: Orchestrator, config: Config
) -> None:
    """Start the issue polling loop (if GitHub is configured)."""
    if not config.github_app_id:
        logger.info(
            "GitHub not configured — skipping issue polling"
        )
        return

    try:
        github = GitHubService(config)
        classifier = IssueClassifier(
            LLMProvider(config), config
        )
        poller = IssuePoller(github, classifier, config)

        logger.info("Starting issue poller...")
        async for polled in poller.poll():
            logger.info(
                f"Received issue #{polled.issue.number}: "
                f"{polled.issue.title} "
                f"({polled.classification.type})"
            )
            result = await orchestrator.handle_message(
                f"Issue #{polled.issue.number}: "
                f"{polled.issue.title}\n"
                f"{polled.issue.body}\n\n"
                f"Classification: "
                f"{polled.classification.type}",
                issue_id=polled.issue.id,
            )
            logger.info(
                "Orchestrator result: "
                f"success={result.success}"
            )

    except Exception as e:
        logger.error(f"Polling failed: {e}")
        logger.info("Continuing without polling...")


async def main() -> None:
    """Main async entry point."""
    orchestrator, config = await startup()

    polling_task = asyncio.create_task(
        start_polling(orchestrator, config)
    )

    await orchestrator.start_idle_loop()

    polling_task.cancel()


def entrypoint() -> None:
    """Sync entry point for console_scripts."""
    asyncio.run(main())


if __name__ == "__main__":
    entrypoint()
