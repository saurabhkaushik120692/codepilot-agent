# CLAUDE.md — CodePilot Agent Project Intelligence

> This file is the authoritative reference for any AI coding assistant working on this codebase.
> Read this before making any changes. Update it when conventions evolve.

---

## Project Identity

**Name:** CodePilot — Multi-Agent Coding Platform
**Repo:** `codepilot-agent`
**Location:** `c:\ai-engineering\codepilot-agent\`
**Language:** Python 3.13+
**Package Manager:** `uv` (NOT pip, NOT poetry)
**Build System:** Hatchling (`pyproject.toml`)
**Package Name:** `codepilot` (importable as `from codepilot.xxx import ...`)

---

## Quick Reference

```bash
# Activate virtual environment
source .venv/Scripts/activate     # Windows (Git Bash)
.venv\Scripts\activate            # Windows (PowerShell)

# Install / sync dependencies
uv sync

# Run the application
uv run python -m codepilot.main

# Run tests
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_core/test_agent_factory.py -v

# Type check
uv run mypy src/codepilot/

# Lint
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

---

## Architecture Overview

CodePilot is a **terminal-based, multi-agent AI platform** that autonomously triages GitHub issues, implements fixes in a sandboxed environment, and opens pull requests — with human-in-the-loop approval for risky operations.

### Core Stack

| Layer | Technology |
|-------|-----------|
| **Agent Framework** | `deepagents` (LangChain/LangGraph) behind an abstraction layer |
| **Primary LLM** | Claude Sonnet (`langchain-anthropic`) |
| **Fallback LLMs** | GPT-4o (`langchain-openai`), Gemini 1.5 Pro (`langchain-google-genai`) |
| **TUI** | `textual` (4-panel terminal UI) |
| **Episodic Memory** | LangGraph Memory Store (`langgraph.store`) |
| **Semantic Memory** | ChromaDB (persistent directory) |
| **Working Memory** | In-memory Python dict |
| **Guardrails** | NeMo Guardrails (Colang 2.0) + custom filters |
| **GitHub Integration** | `GitHubToolkit` (langchain-community) wrapped behind `GitHubService` |
| **Config** | `pydantic-settings` loading from `.env` |
| **Testing** | `pytest` + `pytest-asyncio` |

### Agent Hierarchy

```
Orchestrator (root agent)
├── Repo Explorer (subagent) — finds relevant files
├── Coder (subagent) — implements changes in sandbox
│   └── Test Agent (sub-subagent) — runs tests
└── PR Agent (subagent) — creates branches, commits, PRs
```

### State Machine (per task)

```
TRIAGED → EXPLORING → IMPLEMENTING → TESTING → PR_OPENED → DONE | FAILED
```

---

## Directory Structure

```
c:\ai-engineering\codepilot-agent\
├── src/
│   └── codepilot/
│       ├── __init__.py
│       ├── main.py                  # Entry point
│       ├── config.py                # Settings (pydantic-settings)
│       ├── core/                    # ★ Abstraction layer over deepagents
│       │   ├── __init__.py
│       │   ├── agent_factory.py     # Wraps create_deep_agent()
│       │   ├── base_agent.py        # Abstract agent interface
│       │   ├── tool_registry.py     # Tool management abstraction
│       │   └── llm_provider.py      # Multi-provider LLM factory
│       ├── agents/                  # Concrete agent implementations
│       │   ├── __init__.py
│       │   ├── orchestrator.py      # Root Orchestrator agent
│       │   ├── repo_explorer.py     # Repo Explorer subagent
│       │   ├── coder.py             # Coder subagent
│       │   ├── test_agent.py        # Test Agent subagent
│       │   └── pr_agent.py          # PR Agent subagent
│       ├── skills/                  # Task-type skill definitions
│       │   ├── __init__.py
│       │   ├── base.py              # Skill dataclass / registry
│       │   ├── bug_fix.py
│       │   ├── feature_addition.py
│       │   ├── dependency_update.py
│       │   └── documentation.py
│       ├── memory/                  # 3-tier memory system
│       │   ├── __init__.py
│       │   ├── episodic.py          # LangGraph Memory Store
│       │   ├── semantic.py          # ChromaDB vector store
│       │   └── working.py           # In-memory task state
│       ├── guardrails/              # Safety layer
│       │   ├── __init__.py
│       │   ├── command_filter.py    # Dangerous command blocker
│       │   ├── file_filter.py       # Sensitive file write blocker
│       │   ├── hitl.py              # Human-in-the-loop gate logic
│       │   └── config/              # NeMo Guardrails config
│       │       ├── config.yml
│       │       ├── rails.co
│       │       └── actions.py
│       ├── github_integration/      # GitHub API layer
│       │   ├── __init__.py
│       │   ├── github_service.py    # Wraps GitHubToolkit
│       │   ├── issue_poller.py      # Polling loop & filtering
│       │   ├── pr_builder.py        # Branch, commit, PR creation
│       │   └── classifier.py        # Issue → task type classifier
│       ├── context/                 # Context engineering
│       │   ├── __init__.py
│       │   ├── repo_map.py          # Repo Map builder & cache
│       │   └── retriever.py         # Keyword + embedding retrieval
│       ├── sandbox/                 # Sandboxed execution
│       │   ├── __init__.py
│       │   └── manager.py           # Sandbox setup, copy, teardown
│       └── tui/                     # Terminal UI
│           ├── __init__.py
│           ├── app.py               # Textual App class
│           ├── panels/
│           │   ├── __init__.py
│           │   ├── issues.py        # GitHub Issues panel
│           │   ├── active_task.py   # Active Task panel
│           │   ├── agent_logs.py    # Streaming Agent Logs panel
│           │   └── approval.py      # Human Approval panel
│           └── styles.tcss          # Textual CSS
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Shared fixtures
│   ├── test_core/
│   │   ├── test_agent_factory.py
│   │   └── test_llm_provider.py
│   ├── test_orchestrator.py
│   ├── test_repo_explorer.py
│   ├── test_coder.py
│   ├── test_skills.py
│   ├── test_memory.py
│   ├── test_guardrails.py
│   └── test_tui.py
├── docs/
│   ├── implementation_plan.md       # Full 6-phase implementation plan
│   ├── architecture.md              # Architecture documentation
│   └── network_architecture.md
├── pyproject.toml
├── .env                             # Local secrets (git-ignored)
├── .env.sample                      # Template for env vars
├── .gitignore
├── .python-version                  # 3.13
├── uv.lock
├── README.md
└── CLAUDE.md                        # ← You are here
```

---

## Critical Design Decisions

### 1. Abstraction Layer Over `deepagents` (THE Key Decision)

All agent code interacts with `deepagents` **only** through `src/codepilot/core/`. No `deepagents` types may leak into agent business logic (`agents/`, `skills/`, `memory/`, etc.).

- `BaseAgent` is our abstract class; agents implement this, NOT deepagents interfaces
- `AgentResult` and `AgentEvent` are our own dataclasses
- `DeepAgentFactory` is the single file that touches `create_deep_agent()`
- **If deepagents breaks:** swap `DeepAgentFactory` → `LangGraphFactory` in one file

```python
# ✅ CORRECT — agent code uses our abstraction
from codepilot.core.base_agent import BaseAgent, AgentResult

# ❌ WRONG — direct deepagents import in agent logic
from deepagents import create_deep_agent
```

### 2. GitHubService Abstraction

Similarly, all GitHub API calls go through `GitHubService` — never call `GitHubToolkit` or `PyGithub` directly from agent code.

### 3. Context Engineering Rules

These are **non-negotiable** across the entire codebase:

- **No file contents in spawning prompts.** Subagents use `read_file` on-demand.
- **Orchestrator passes only file paths** when delegating to subagents.
- **Auto-summarization** of older conversation turns is enabled by default (threshold: 20 turns).
- Token budgets are respected — Repo Map must fit within `REPO_MAP_TOKEN_BUDGET` (default 4000).

### 4. GitHub Authentication

Uses **GitHub App** auth (App ID + private key `.pem`), NOT personal access tokens.

### 5. Memory Architecture

| Tier | Backend | Purpose | Persistence |
|------|---------|---------|-------------|
| Episodic | LangGraph Memory Store (`InMemoryStore`) | Session summaries, task records | In-memory (upgradable to PostgresStore) |
| Semantic | ChromaDB (persistent dir) | Lessons learned, similar task retrieval | Disk (`~/.codepilot/data/chromadb/`) |
| Working | Python `dict` | Active task state | None (cleared on DONE/FAILED) |

---

## Coding Conventions

### Python Style

- **Python 3.13+** — use modern syntax: `type` unions (`X | Y`), `match` statements, f-strings
- **Type hints** on ALL function signatures (args + return types)
- **Docstrings** on all public classes and functions (Google style)
- **Async-first** — use `async def` for all I/O-bound operations
- **Dataclasses** for data structures; `pydantic.BaseModel` for validated/serialized models
- Use `pydantic-settings` for configuration — NOT manual env parsing

### Naming

- **Files:** `snake_case.py`
- **Classes:** `PascalCase`
- **Functions/methods:** `snake_case`
- **Constants:** `UPPER_SNAKE_CASE`
- **Private members:** `_leading_underscore`
- **Test files:** `test_<module_name>.py`
- **Test functions:** `test_<what_it_tests>` or `test_<scenario>_<expected_behavior>`

### Import Order

```python
# 1. Standard library
import asyncio
from pathlib import Path

# 2. Third-party
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel

# 3. Local — always use absolute imports from the package root
from codepilot.core.base_agent import BaseAgent
from codepilot.config import Config
```

### Error Handling

- Raise domain-specific exceptions, not generic `Exception`
- Define custom exceptions in each module's `__init__.py` or a dedicated `exceptions.py`
- Agent failures should transition the task state to `FAILED` with a reason string
- LLM API errors should trigger the fallback chain (Claude → GPT-4o → Gemini)

### Logging

- Use Python's `logging` module — NOT `print()` statements
- Logger per module: `logger = logging.getLogger(__name__)`
- Log levels: `DEBUG` for internals, `INFO` for state transitions, `WARNING` for fallbacks, `ERROR` for failures

---

## Dependency Management

### Adding Dependencies

```bash
# Add a runtime dependency
uv add <package>

# Add a dev dependency
uv add --dev <package>

# Sync after changes
uv sync
```

### Key Dependencies

| Package | Purpose |
|---------|---------|
| `deepagents` | Core agent framework |
| `langchain-anthropic` | Primary LLM (Claude Sonnet) |
| `langchain-openai` | Fallback LLM (GPT-4o) |
| `langchain-google-genai` | Fallback LLM (Gemini 1.5 Pro) |
| `langchain-community` | GitHub Toolkit |
| `langgraph` | Agent runtime + checkpointing + memory store |
| `chromadb` | Semantic memory vector store |
| `textual` | TUI framework |
| `nemoguardrails` | Guardrails framework (Colang 2.0) |
| `pydantic-settings` | Configuration management |
| `tiktoken` | Token counting for Repo Map budget |
| `pygithub` | GitHub API (fallback behind GitHubService) |
| `aiosqlite` | Async SQLite for LangGraph SqliteSaver checkpointing |
| `pytest` | Testing (dev) |
| `pytest-asyncio` | Async test support (dev) |
| `ruff` | Linting & formatting (dev) |
| `mypy` | Type checking (dev) |

---

## Configuration

All configuration flows through `src/codepilot/config.py` using `pydantic-settings`.

### Required Environment Variables (`.env`)

```env
# LLM Providers
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...

# GitHub App
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_PATH=./keys/codepilot.pem
GITHUB_REPOSITORY=owner/codepilot-test-repo
```

### Optional Configuration (with defaults)

```env
# LLM
PRIMARY_LLM=anthropic:claude-sonnet-4-20250514
FALLBACK_LLMS=openai:gpt-4o,google:gemini-1.5-pro

# Polling
POLL_INTERVAL_MINUTES=5

# Context
REPO_MAP_TOKEN_BUDGET=4000
MAX_RELEVANT_FILES=10

# Agent
MAX_CODER_RETRIES=3
COMPLEXITY_THRESHOLD=7

# Summarization
AUTO_SUMMARIZATION_ENABLED=true
SUMMARIZATION_THRESHOLD=20

# Storage
SANDBOX_BASE_DIR=~/.codepilot/sandboxes/
CHROMADB_PERSIST_DIR=~/.codepilot/data/chromadb/

# Tracing (Bonus)
LANGSMITH_ENABLED=false
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=codepilot

# Sandbox (Bonus)
SANDBOX_PROVIDER=local

# ACP (Bonus)
ACP_ENABLED=false
ACP_PORT=8420
```

---

## Testing Strategy

### Test Structure

- Tests mirror the `src/codepilot/` structure under `tests/`
- Use `pytest` with `pytest-asyncio` for async tests
- Fixtures go in `tests/conftest.py` (shared) or test-local `conftest.py`

### Mocking Guidelines

- **Always mock LLM calls** in unit tests — never make real API calls
- **Mock `deepagents`** at the abstraction layer boundary (`core/agent_factory.py`)
- **Mock GitHub API** via `GitHubService` — never hit real GitHub in unit tests
- Use `pytest.fixture` for reusable mocks; use `unittest.mock.AsyncMock` for async methods

### Running Tests

```bash
# All tests
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ -v --cov=codepilot --cov-report=term-missing

# Specific test module
uv run pytest tests/test_core/ -v

# Only unit tests (skip integration)
uv run pytest tests/ -v -m "not integration"
```

---

## Implementation Phases

The project follows a 6-phase plan (see `docs/implementation_plan.md` for full detail):

| Phase | Focus | Dependencies |
|-------|-------|-------------|
| **Phase 1** | Scaffolding, Abstraction Layer, Orchestrator skeleton | — |
| **Phase 2** | GitHub Integration, Issue Polling, Task Classification | Phase 1 |
| **Phase 3** | Context Engineering, Repo Explorer, Coder Agent, Guardrails | Phase 1, 2 |
| **Phase 4** | Skills System, 3-Tier Memory, Test Agent | Phase 3 |
| **Phase 5** | PR Agent, TUI (4-panel), HITL, E2E Integration | Phase 2, 3, 4 |
| **Phase 6** | All 5 Bonus Challenges | Phase 5 |

### Phase 1 Deliverables (Current)

1. **Project scaffolding** — directory structure, pyproject.toml, .env.sample
2. **Abstraction layer** (`core/`) — `BaseAgent`, `AgentFactory`, `LLMProvider`, `ToolRegistry`
3. **Orchestrator skeleton** — basic tool-calling loop with `write_todos`
4. **Config** — `pydantic-settings` with all Phase 1 settings
5. **Verification** — unit tests for abstraction layer + Orchestrator

---

## Guardrails & Safety

### Command Filtering (execute tool)

**Blocked patterns:** `rm -rf`, `curl`, `wget`, `pip install`, paths outside `/sandbox/`

### File Filtering (edit_file / write_file)

**Blocked file patterns:** `.env`, `*.secret`, `*.pem`, `*.key`, `*credentials*`

### HITL Gates (Human Approval Required)

| Gate | Trigger |
|------|---------|
| PR to `main`/`master` | PR Agent targets protected branch |
| Large commit | Commit touches > 5 files |
| `git push` | Any `execute` containing `git push` |
| Retry after failures | `retry_count >= 2` for test failures |

### NeMo Guardrails (Colang 2.0)

- Prompt injection detection (input rail)
- Hardcoded secrets detection (output rail)
- Sandbox escape detection (output rail)

---

## Git Workflow

- **Branch naming:** `codepilot/issue-{number}-{slug}` (for agent-generated PRs)
- **Commit messages:** `type(#{issue}): description` (e.g., `fix(#1): handle division by zero`)
- **PR titles:** `[CodePilot] {issue title}`
- **PR labels:** `codepilot-generated`, `needs-review`
- Secrets (`.env`, `*.pem`, `*.key`, `*.secret`) are git-ignored

---

## Common Pitfalls

1. **Don't import `deepagents` outside of `core/`** — the abstraction layer exists for a reason
2. **Don't pass file contents in agent spawn prompts** — only pass file paths; let subagents `read_file` themselves
3. **Don't use `pip install`** — use `uv add` for dependency management
4. **Don't store secrets in code** — use `.env` and `pydantic-settings`
5. **Don't skip the HITL gate** — risky operations must go through `hitl.py`
6. **Don't write synchronous I/O code** — all I/O should be `async`
7. **Don't create agents without going through `AgentFactory`** — it handles tool registration, guardrails, and LLM wiring
8. **Don't forget the state machine** — every task must transition through valid states only
9. **Don't use `print()`** — use `logging` with proper levels
10. **Don't hardcode LLM model names** — they come from `config.py`

---

## Documentation References

- [Implementation Plan](docs/implementation_plan.md) — Full 6-phase breakdown
- [Architecture](docs/architecture.md) — System architecture documentation
- [Network Architecture](docs/network_architecture.md) — Network layer design
- [deepagents docs](https://github.com/deepagents/deepagents) — Agent framework reference
- [Textual docs](https://textual.textualize.io/) — TUI framework
- [NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails) — Guardrails framework
- [LangGraph Memory Store](https://langchain-ai.github.io/langgraph/concepts/memory/) — Episodic memory backend
