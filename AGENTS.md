# AGENTS.md — CodePilot Agent

> Phase 1 complete (scaffolding + abstraction layer). Phases 2-6 in planning.

## Commands

```bash
# Activate env (required before anything else)
.venv\Scripts\activate    # Windows PowerShell
# source .venv/Scripts/activate  # Windows Git Bash

uv sync                   # install/sync dependencies

# Run the app
uv run python -m codepilot.main

# Test all (59 tests)
uv run pytest tests/ -v

# Test a single file or subset
uv run pytest tests/test_core/test_agent_factory.py -v
uv run pytest tests/ -v -k "llm"

# Lint (must pass before committing)
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Typecheck
uv run mypy src/codepilot/
```

## Architecture

Python 3.13+, package manager `uv` (NOT pip), build system hatchling.
Package `codepilot-agent`, import as `from codepilot.xxx`.

The key architectural rule: **deepagents is only imported in one file** —
`src/codepilot/core/agent_factory.py`. All other code imports from
`codepilot.core.base_agent`. If deepagents breaks, swap the factory.

```
startup chain: Config → LLMProvider → ToolRegistry → DeepAgentFactory → Orchestrator
```

Currently built (Phase 1):
- `core/`: BaseAgent (ABC), AgentResult/AgentEvent datatypes, LLMProvider (fallback chain), ToolRegistry, DeepAgentFactory
- `agents/`: Orchestrator skeleton only — `handle_message()` + `start_idle_loop()`
- `config.py`: pydantic-settings from `.env`, all Phase 1-6 config fields declared

Not yet built: repo_explorer, coder, test_agent, pr_agent, memory, skills, sandbox, guardrails, TUI.

## Testing conventions

- `pytest` + `pytest-asyncio`, `asyncio_mode = "auto"` (no decorators needed)
- All LLM calls must be mocked (`AsyncMock`). Never hit real APIs in unit tests.
- Mock `deepagents` availability via `patch("codepilot.core.agent_factory.DEEPAGENTS_AVAILABLE", False)`
- Config in tests uses `Config(_env_file=None)` to skip `.env` file loading
- `tests/conftest.py` for shared fixtures; test-local fixtures in test files
- Test files mirror `src/codepilot/` structure: `tests/test_core/` ↔ `src/codepilot/core/`

## Gotchas

- **`uv add` only** — never `pip install` or `poetry add`
- **Async-first** — all I/O uses `async def`; use `pytest.mark.asyncio` in tests
- **Abstraction boundary** — if you import `deepagents` anywhere outside `core/agent_factory.py`, you broke it
- **logging, not print()** — `logger = logging.getLogger(__name__)`
- **Type hints required** on all function signatures
- Python 3.13+ syntax: `X | Y` for unions, `match` statements, f-strings
- No CI, no pre-commit hooks — run `ruff check` + `pytest` manually before pushing
