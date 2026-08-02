# CodePilot Agent

A terminal-based, multi-agent AI coding platform that autonomously triages GitHub issues, implements fixes in a sandboxed environment, and opens pull requests — with humans in the loop for risky operations.

```
GitHub Issues → Triage → Explore → Code → Test → Review → PR
                                                      ↑
                              Human-in-the-Loop ──────┘
```

---

## Features

- **Autonomous Issue Resolution** — Polls GitHub for `ai-assignable` issues and resolves them end-to-end
- **Multi-Agent Orchestration** — Root Orchestrator delegates to Repo Explorer, Coder, Test Agent, and PR Agent
- **Skill-Driven Code Generation** — 5 task-type skills (bug fix, feature, dependency, documentation, config) loaded based on classification
- **Sandboxed Execution** — All code changes run in isolated directories; cloud sandbox support planned
- **Human-in-the-Loop** — Risky operations (PRs to main, large commits, retries) require explicit approval
- **3-Tier Memory** — Working memory (per-task), episodic memory (session summaries), semantic memory (lessons learned)
- **Defense in Depth** — Custom command/file filters + NeMo Guardrails + HITL gates + filesystem permissions
- **Terminal UI** — Textual-based 4-panel TUI with keyboard shortcuts
- **ACP Server** — REST API for external tool integration (Zed, Cursor)
- **Self-Healing Tests** — Meta-agent debugs broken test infrastructure automatically
- **Issue Triage Scoring** — LLM-based complexity scoring (1-10) with threshold filtering

---

## Architecture

```
┌──────────────────────┬──────────────────────────────────┐
│   GitHub Issues      │          Active Task              │
│  #42 open ●          │  Issue #42: Fix null pointer      │
│  #38 in-progress ◐   │  Status: IMPLEMENTING             │
│  #31 done ✓          │  Agent: Coder (retry 1/3)         │
├──────────────────────┼──────────────────────────────────┤
│   Agent Logs         │        Human Approval             │
│  [Orchestrator]      │  ⚠ Coder wants to open PR         │
│  Spawning Repo       │  to main (5 files changed)        │
│  Explorer...         │  > approve / reject / inspect     │
└──────────────────────┴──────────────────────────────────┘
  [i] New task   [s] Skip issue   [q] Quit   [l] Logs
```

### Agent Hierarchy

```
Orchestrator (root)
├── Repo Explorer → finds relevant files
├── Coder → implements changes in sandbox
├── Test Agent → runs pytest, structured results
├── PR Agent → branch, commit, create PR
└── Meta Test Agent → self-heals test infrastructure failures
```

### State Machine

```
TRIAGED → EXPLORING → IMPLEMENTING → TESTING → PR_OPENED → DONE
                         ↑______________|              ↘ FAILED
```

### Tech Stack

| Layer | Technologies |
|-------|-------------|
| Agent Framework | deepagents, LangGraph |
| LLM | Claude Sonnet (primary) → GPT-4o → Gemini 1.5 Pro (fallback) |
| Memory | ChromaDB (semantic), LangGraph Memory Store (episodic), in-memory (working) |
| Guardrails | Custom regex filters, NeMo Guardrails (Colang 2.0), HITL gates |
| TUI | Textual — 4-panel grid layout |
| API | FastAPI (ACP server) |
| Config | pydantic-settings from `.env` |

Full architecture: [docs/architecture.md](docs/architecture.md)

---

## Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager
- Git

### Setup

```bash
git clone https://github.com/your-org/codepilot-agent.git
cd codepilot-agent

# Create virtual env and install dependencies
uv sync

# Activate environment
.venv\Scripts\activate    # Windows PowerShell
# source .venv/bin/activate  # macOS/Linux
```

### Configuration

Copy `.env.sample` to `.env` and fill in your keys:

```env
# Required: at least one LLM API key
ANTHROPIC_API_KEY=sk-ant-your-key
OPENAI_API_KEY=sk-your-key
GOOGLE_API_KEY=your-key

# GitHub Integration (for issue polling + PR creation)
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_PATH=./keys/codepilot.pem
GITHUB_REPOSITORY=owner/codepilot-test-repo

# Optional: LangSmith tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-key
LANGCHAIN_PROJECT=codepilot

# Optional: ACP server
ACP_ENABLED=true
ACP_PORT=8420
```

### Run

```bash
# Launch the TUI
uv run python -m codepilot.main

# TUI keyboard shortcuts:
#   i — New manual task
#   s — Skip current issue
#   q — Quit
#   l — Toggle full logs
```

---

## Development

### Commands

```bash
uv sync                       # install/sync dependencies

# Run all tests (305 tests)
uv run pytest tests/ -v

# Test a single file
uv run pytest tests/test_core/test_agent_factory.py -v

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Typecheck
uv run mypy src/codepilot/
```

### Project Structure

```
src/codepilot/
├── main.py                     # Entry point
├── config.py                   # pydantic-settings
├── core/                       # Abstraction layer (BaseAgent, LLMProvider, ToolRegistry)
├── agents/                     # Orchestrator, RepoExplorer, Coder, TestAgent, PRAgent
├── skills/                     # 5 task-type skills (bug_fix, feature_addition, etc.)
├── memory/                     # Working, episodic (LangGraph), semantic (ChromaDB)
├── guardrails/                 # Command filter, file filter, HITL, NeMo Guardrails
├── github_integration/         # GitHubService, issue poller, classifier, PR builder
├── context/                    # Repo map builder, file retriever (keyword + embedding)
├── sandbox/                    # Local sandbox, cloud sandbox interface
├── tui/                        # Textual TUI with 4 panels
└── acp_server.py               # ACP HTTP API (FastAPI)

tests/                          # Mirrors src/ structure
```

### Conventions

- **Async-first** — all I/O uses `async def`; `pytest-asyncio` with `asyncio_mode = "auto"`
- **Abstraction boundary** — `deepagents` imported ONLY in `core/agent_factory.py`
- **Type hints required** on all function signatures
- **Python 3.13+** syntax: `X | Y` unions, f-strings
- **`uv add` only** — never `pip install`
- **logging, not `print()`**

---

## Bonus Features

| Feature | Description | Module |
|---------|-------------|--------|
| Self-Healing Tests | Meta-agent debugs broken test infrastructure (ImportError, SyntaxError) | `agents/meta_test_agent.py` |
| Issue Triage Scoring | LLM-based complexity scoring (1-10); skips issues above threshold | `github_integration/triage_scorer.py` |
| LangSmith Tracing | Full observability with trace trees, metadata tags | `core/tracing.py` |
| Cloud Sandbox | Extensible sandbox interface (local + cloud placeholder) | `sandbox/cloud_sandbox.py` |
| ACP Integration | REST API for Zed/Cursor: `POST /tasks`, `GET /tasks/{id}/result`, HITL approval | `acp_server.py` |

---

## License

MIT
