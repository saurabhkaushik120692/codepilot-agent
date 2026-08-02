# CodePilot — Architecture Document

> **Version:** 1.0  
> **Last Updated:** 2026-07-19  
> **Status:** Draft  
> **Source:** [implementation_plan.md](file:///c:/ai-engineering/codepilot-agent/docs/implementation_plan.md)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Design Principles](#2-design-principles)
3. [High-Level Architecture](#3-high-level-architecture)
4. [Component Architecture](#4-component-architecture)
   - 4.1 [Abstraction Layer (`core/`)](#41-abstraction-layer-core)
   - 4.2 [Agent System (`agents/`)](#42-agent-system-agents)
   - 4.3 [Context Engineering (`context/`)](#43-context-engineering-context)
   - 4.4 [Memory System (`memory/`)](#44-memory-system-memory)
   - 4.5 [Skills System (`skills/`)](#45-skills-system-skills)
   - 4.6 [Guardrails & Security (`guardrails/`)](#46-guardrails--security-guardrails)
   - 4.7 [Sandbox Execution (`sandbox/`)](#47-sandbox-execution-sandbox)
   - 4.8 [GitHub Integration (`github_integration/`)](#48-github-integration-github_integration)
   - 4.9 [Terminal UI (`tui/`)](#49-terminal-ui-tui)
5. [Data Flow & Sequences](#5-data-flow--sequences)
6. [State Management](#6-state-management)
7. [Security Architecture](#7-security-architecture)
8. [Technology Stack](#8-technology-stack)
9. [Directory Structure](#9-directory-structure)
10. [Deployment & Configuration](#10-deployment--configuration)
11. [Extension Points (Bonus)](#11-extension-points-bonus)

---

## 1. System Overview

CodePilot is a **terminal-based, multi-agent AI coding platform** that autonomously triages GitHub issues, implements fixes in a sandboxed environment, and opens pull requests — all while keeping a human in the loop for risky operations.

```
┌──────────────────────────────────────────────────────────────────┐
│                         CodePilot                                │
│                                                                  │
│   GitHub Issues ──► Triage ──► Explore ──► Code ──► Test ──► PR  │
│                         ▲                                   │    │
│                         └──── Human-in-the-Loop ◄───────────┘    │
│                                                                  │
│   Built on: deepagents · LangGraph · Textual · ChromaDB          │
└──────────────────────────────────────────────────────────────────┘
```

### Key Capabilities

| Capability | Description |
|---|---|
| **Autonomous Issue Resolution** | Polls GitHub for `ai-assignable` issues and resolves them end-to-end |
| **Manual Task Execution** | Accepts free-form coding tasks from the user via TUI |
| **Multi-Agent Orchestration** | Root Orchestrator delegates to specialized subagents |
| **Sandboxed Execution** | All code changes run in isolated directories (or cloud sandboxes) |
| **Human-in-the-Loop** | Risky operations require explicit human approval |
| **Cross-Session Learning** | Semantic memory stores lessons learned; episodic memory tracks sessions |

---

## 2. Design Principles

| Principle | Rationale |
|---|---|
| **Abstraction over frameworks** | All agents interact with `deepagents` only through a wrapper layer. If the API changes, swap one file — not every agent. |
| **Context engineering over brute-force** | Never dump full file contents into prompts. Use Repo Maps, on-demand `read_file`, and auto-summarization to stay within token budgets. |
| **Defense in depth** | Multiple guardrail layers — custom filters, NeMo Guardrails, filesystem permissions, and HITL gates — prevent unsafe operations. |
| **Explicit state machines** | Every task follows a well-defined state machine (`TRIAGED → … → DONE | FAILED`) for observability and debuggability. |
| **Separation of concerns** | Pure helpers (e.g., `pr_builder.py`) contain no API calls. Service wrappers (e.g., `github_service.py`) abstract external APIs. Agents contain orchestration logic. |

---

## 3. High-Level Architecture

```mermaid
graph TD
    subgraph User_Layer["User Interface Layer"]
        TUI["TUI (Textual)<br/>4-panel layout"]
    end

    subgraph Agent_Layer["Agent Orchestration Layer"]
        ORC["Orchestrator Agent<br/>Root deep agent"]
        RE["Repo Explorer<br/>Subagent"]
        COD["Coder Agent<br/>Subagent"]
        TST["Test Agent<br/>Subagent"]
        PRA["PR Agent<br/>Subagent"]
    end

    subgraph Core_Layer["Core Infrastructure Layer"]
        ABS["Abstraction Layer<br/>(deepagents wrapper)"]
        LLM["LLM Provider<br/>Claude Sonnet (primary)<br/>GPT-4o / Gemini (fallback)"]
        GR["Guardrails<br/>(NeMo + Custom)"]
        SKL["Skills System<br/>(5 skills)"]
    end

    subgraph Data_Layer["Data & Integration Layer"]
        GH["GitHub API<br/>(GitHubToolkit)"]
        SB["Sandbox<br/>(Local isolated dir)"]
        MEM_E["Episodic Memory<br/>(LangGraph Memory Store)"]
        MEM_S["Semantic Memory<br/>(ChromaDB persistent)"]
        MEM_W["Working Memory<br/>(In-memory dict)"]
    end

    TUI <--> ORC
    ORC --> RE
    ORC --> COD
    COD --> TST
    ORC --> PRA
    ORC <--> GH
    PRA <--> GH
    COD <--> SB
    TST <--> SB
    ORC <--> MEM_E
    ORC <--> MEM_S
    ORC <--> MEM_W
    ORC --> SKL
    COD --> GR
    ORC --> ABS
    RE --> ABS
    COD --> ABS
    TST --> ABS
    PRA --> ABS
    ABS --> LLM

    style User_Layer fill:#1a1a2e,stroke:#e94560,color:#fff
    style Agent_Layer fill:#16213e,stroke:#0f3460,color:#fff
    style Core_Layer fill:#0f3460,stroke:#533483,color:#fff
    style Data_Layer fill:#533483,stroke:#e94560,color:#fff
```

### Layered Architecture Summary

| Layer | Responsibility | Key Components |
|---|---|---|
| **User Interface** | User interaction, TUI panels, keyboard shortcuts, HITL prompts | `tui/app.py`, `panels/*` |
| **Agent Orchestration** | Task decomposition, subagent spawning, state machine management | `agents/orchestrator.py`, `agents/*` |
| **Core Infrastructure** | Framework abstraction, LLM management, guardrails, skills | `core/*`, `guardrails/*`, `skills/*` |
| **Data & Integration** | External APIs, storage, sandbox isolation, memory persistence | `github_integration/*`, `sandbox/*`, `memory/*` |

---

## 4. Component Architecture

### 4.1 Abstraction Layer (`core/`)

> The single most important architectural decision: isolate all `deepagents` usage behind a clean interface so the rest of the system is framework-agnostic.

```mermaid
classDiagram
    class BaseAgent {
        <<abstract>>
        +invoke(messages, context) AgentResult
        +stream(messages, context) AsyncIterator~AgentEvent~
        +spawn_subagent(task, **kwargs) BaseAgent
    }

    class AgentResult {
        +content: str
        +tool_calls: list
        +metadata: dict
    }

    class AgentEvent {
        +type: str
        +data: Any
        +timestamp: datetime
    }

    class DeepAgentFactory {
        +create_orchestrator() BaseAgent
        +create_coder() BaseAgent
        +create_explorer() BaseAgent
        +create_test_agent() BaseAgent
        +create_pr_agent() BaseAgent
    }

    class LLMProvider {
        +get_model(provider?) BaseChatModel
        -_fallback_chain: list
        -_primary: str
    }

    class ToolRegistry {
        +register(name, impl, guardrail?)
        +get_tools(agent_type) list
        -_tools: dict
        -_guardrail_wrappers: dict
    }

    BaseAgent <|-- DeepAgentFactory : creates
    BaseAgent --> AgentResult
    BaseAgent --> AgentEvent
    DeepAgentFactory --> LLMProvider
    DeepAgentFactory --> ToolRegistry
```

**Key files:**

| File | Responsibility |
|---|---|
| [base_agent.py](file:///c:/ai-engineering/codepilot-agent/src/codepilot/core/base_agent.py) | Abstract `BaseAgent` interface — the contract all agents follow |
| [agent_factory.py](file:///c:/ai-engineering/codepilot-agent/src/codepilot/core/agent_factory.py) | Concrete `DeepAgentFactory` wrapping `create_deep_agent()` |
| [llm_provider.py](file:///c:/ai-engineering/codepilot-agent/src/codepilot/core/llm_provider.py) | Multi-provider LLM factory with fallback chain: Claude → GPT-4o → Gemini |
| [tool_registry.py](file:///c:/ai-engineering/codepilot-agent/src/codepilot/core/tool_registry.py) | Centralized tool registration with guardrail wrapper injection |

**Fallback Strategy:**

```
Claude Sonnet (primary)
    │ rate limit / API error
    ▼
GPT-4o (fallback #1)
    │ rate limit / API error
    ▼
Gemini 1.5 Pro (fallback #2)
```

---

### 4.2 Agent System (`agents/`)

CodePilot uses a **hierarchical multi-agent architecture** where the Orchestrator is the root agent and all others are spawned as subagents.

```mermaid
graph TD
    ORC["🧠 Orchestrator"]
    RE["🔍 Repo Explorer"]
    COD["💻 Coder"]
    TST["🧪 Test Agent"]
    PRA["📋 PR Agent"]
    META["🔧 Meta Test Agent<br/>(Bonus)"]

    ORC -->|"spawn: explore repo"| RE
    ORC -->|"spawn: implement fix"| COD
    COD -->|"spawn: run tests"| TST
    TST -.->|"spawn: self-heal"| META
    ORC -->|"spawn: create PR"| PRA

    style ORC fill:#e94560,stroke:#fff,color:#fff
    style RE fill:#0f3460,stroke:#fff,color:#fff
    style COD fill:#0f3460,stroke:#fff,color:#fff
    style TST fill:#0f3460,stroke:#fff,color:#fff
    style PRA fill:#0f3460,stroke:#fff,color:#fff
    style META fill:#2d5a27,stroke:#4a9e42,color:#fff
```

#### Agent Responsibilities & Tools

| Agent | Role | Tools Available | Input | Output |
|---|---|---|---|---|
| **Orchestrator** | Root planner, state machine, memory manager | `write_todos`, `task` (spawn), GitHub API, Memory Store | Issues / manual tasks | State transitions, delegation |
| **Repo Explorer** | Codebase analysis & file discovery | `ls`, `read_file`, semantic search, repo map | Task description + repo path | List of relevant file paths |
| **Coder** | Code implementation | `read_file`, `write_file`, `edit_file`, `execute`, `write_todos`, `spawn_subagent` | File paths, Skill, working memory | Diff + modified files |
| **Test Agent** | Test execution & reporting | `write_file`, `execute` | Sandbox path, test config | `TestResult` (pass/fail/coverage) |
| **PR Agent** | Branch/commit/PR creation | GitHub API (branch, commit, PR) | Approved diff, issue metadata | PR URL |

#### Orchestrator State Machine

```mermaid
stateDiagram-v2
    [*] --> TRIAGED : Issue polled & classified
    TRIAGED --> EXPLORING : Spawn Repo Explorer
    EXPLORING --> IMPLEMENTING : Relevant files identified
    IMPLEMENTING --> TESTING : Code changes complete
    TESTING --> IMPLEMENTING : Tests failed (retry ≤ 3)
    TESTING --> PR_OPENED : Tests passed + diff approved
    PR_OPENED --> DONE : PR created successfully
    IMPLEMENTING --> FAILED : Max retries exceeded
    TESTING --> FAILED : Max retries exceeded
    PR_OPENED --> FAILED : Merge conflict
    EXPLORING --> FAILED : No relevant files found
    
    DONE --> [*]
    FAILED --> [*]
```

#### Task Sources

The Orchestrator handles two types of tasks through a unified `TaskSource` interface:

```mermaid
graph LR
    GH_ISSUE["GitHub Issue<br/>(ai-assignable label)"]
    MANUAL["Manual Task<br/>(TUI [i] shortcut)"]
    
    GH_ISSUE --> UNIFIED["TaskSource<br/>unified interface"]
    MANUAL --> UNIFIED
    UNIFIED --> ORC["Orchestrator"]
    
    ORC -->|"GitHub tasks"| AUTO_PR["Auto PR Creation"]
    ORC -->|"Manual tasks"| HITL_PR["HITL: Open PR?<br/>approve / reject"]
```

---

### 4.3 Context Engineering (`context/`)

The context engineering subsystem ensures agents never exceed token budgets and always have the most relevant information.

```mermaid
graph TD
    subgraph Repo_Map_Pipeline["Repo Map Pipeline"]
        WALK["Recursive<br/>dir walk"] --> AST["AST parsing<br/>(symbols)"]
        AST --> TREE["Compressed<br/>tree builder"]
        TREE --> BUDGET["Token budget<br/>enforcement<br/>(tiktoken, 4000 tokens)"]
        BUDGET --> CACHE["Disk cache<br/>(invalidate on git diff)"]
    end

    subgraph Retrieval["File Retrieval"]
        KW["Keyword Matching<br/>(TF-IDF on summaries)"]
        EMB["Embedding Search<br/>(ChromaDB, cosine similarity)"]
        KW --> TOPK["Top-K files<br/>(default K=10)"]
        EMB --> TOPK
    end

    CACHE --> KW
    CACHE --> EMB
    TOPK --> EXPLORER["Repo Explorer Agent"]

    style Repo_Map_Pipeline fill:#1a1a2e,stroke:#e94560,color:#fff
    style Retrieval fill:#16213e,stroke:#0f3460,color:#fff
```

#### Context Engineering Rules

| Rule | Enforcement |
|---|---|
| **No file contents in spawn prompts** | Orchestrator passes only file paths when delegating to subagents |
| **On-demand file reading** | Subagents use `read_file` tool to load files as needed |
| **Auto-summarization** | `summarization=True` in `backend_config` compacts older conversation turns (threshold: 20 turns) |
| **Token budget** | Repo Map capped at 4000 tokens via `tiktoken`; truncate deepest leaves first |

---

### 4.4 Memory System (`memory/`)

Three-tier memory architecture providing task-scoped, session-scoped, and cross-session persistence:

```mermaid
graph LR
    subgraph Tier_1["Tier 1: Working Memory"]
        WM["In-memory dict<br/>per active task"]
    end

    subgraph Tier_2["Tier 2: Episodic Memory"]
        EM["LangGraph Memory Store<br/>(InMemoryStore)"]
    end

    subgraph Tier_3["Tier 3: Semantic Memory"]
        SM["ChromaDB<br/>persistent collection"]
    end

    WM -->|"cleared on DONE/FAILED"| EM
    EM -->|"session summaries"| SM
    SM -->|"similar lessons"| WM

    style Tier_1 fill:#e94560,stroke:#fff,color:#fff
    style Tier_2 fill:#0f3460,stroke:#fff,color:#fff
    style Tier_3 fill:#533483,stroke:#fff,color:#fff
```

| Tier | Scope | Storage | Data | Lifecycle |
|---|---|---|---|---|
| **Working Memory** | Single task | In-memory `dict` | Issue metadata, repo map, relevant files, current diff, test results, retry count, state | Created at task start; cleared on `DONE` or `FAILED` |
| **Episodic Memory** | Session | LangGraph `InMemoryStore` with namespaces | Session summaries, task records, failed issue IDs | Written at session end; last 3 loaded at startup |
| **Semantic Memory** | Cross-session | ChromaDB persistent directory | "Lessons learned" — issue summary, files changed, approach, outcome | Written after successful PR; queried before each new task (top-3 similar) |

#### Episodic Memory Namespace Convention

```
("sessions", session_id)  → session summaries
("tasks", issue_id)       → individual task records
("failed", repository)    → recently failed issues (avoid retrying)
```

---

### 4.5 Skills System (`skills/`)

Skills are structured, reusable coding workflows loaded by the Orchestrator based on task classification.

```mermaid
graph TD
    CLASSIFIER["Task Classifier<br/>(LLM structured output)"]
    
    CLASSIFIER -->|"bug_fix"| S1["🐛 Bug Fix Skill<br/>reproduce → localize → fix → verify"]
    CLASSIFIER -->|"feature_addition"| S2["✨ Feature Addition Skill<br/>explore → design → implement → test → document"]
    CLASSIFIER -->|"dependency_update"| S3["📦 Dependency Update Skill<br/>changelog → update → conflicts → test_all"]
    CLASSIFIER -->|"documentation"| S4["📝 Documentation Skill<br/>read → draft → review → update_index"]
    CLASSIFIER -->|"config_change"| S5["⚙️ Config Change Skill<br/>identify → validate → update → verify"]
    
    S1 --> CODER["Coder Agent"]
    S2 --> CODER
    S3 --> CODER
    S4 --> CODER
    S5 --> CODER

    style CLASSIFIER fill:#e94560,stroke:#fff,color:#fff
```

#### Skill Data Structure

```python
@dataclass
class Skill:
    name: str                       # e.g., "bug_fix"
    instructions: str               # Detailed instructions for the agent
    workflow_steps: list[str]       # Ordered steps: ["reproduce", "localize", "fix", "verify"]
    example_prompts: list[str]      # Example input prompts for few-shot learning
    forbidden_actions: list[str]    # Actions the agent must NOT take
```

| Skill | Workflow | Forbidden Actions |
|---|---|---|---|
| **Bug Fix** | reproduce → localize → fix → verify | Modifying test infrastructure, skipping tests |
| **Feature Addition** | explore_pattern → design → implement → test → document | Breaking public APIs without HITL approval |
| **Dependency Update** | check_changelog → update → resolve_conflicts → test_all | Major version updates without HITL approval |
| **Documentation** | read_existing → draft → review_accuracy → update_index | Removing existing docs, changing code behavior |
| **Config Change** | identify → validate → update → verify | Modifying credentials/secrets, changing validation logic |

---

### 4.6 Guardrails & Security (`guardrails/`)

Multi-layered defense preventing unsafe agent operations:

```mermaid
graph TD
    subgraph Layer_1["Layer 1: Custom Filters"]
        CF["Command Filter<br/>Blocks: rm -rf, curl,<br/>wget, pip install"]
        FF["File Filter<br/>Blocks: .env, *.pem,<br/>*.key, *credentials*"]
    end

    subgraph Layer_2["Layer 2: NeMo Guardrails"]
        PI["Prompt Injection<br/>Detection (input rail)"]
        HS["Hardcoded Secrets<br/>Detection (output rail)"]
        UP["Unsafe Path<br/>Detection (output rail)"]
    end

    subgraph Layer_3["Layer 3: HITL Gates"]
        PR_GATE["PR to main/master"]
        LARGE_GATE["Commit > 5 files"]
        PUSH_GATE["git push command"]
        RETRY_GATE["Retry after 2 failures"]
    end

    subgraph Layer_4["Layer 4: Filesystem Permissions"]
        SANDBOX_RW["Sandbox: read_write"]
        ROOT_RO["Root: read_only"]
    end

    INPUT["Agent Action"] --> Layer_1
    Layer_1 -->|"allowed"| Layer_2
    Layer_1 -->|"blocked"| HITL["HITL Interrupt"]
    Layer_2 -->|"allowed"| Layer_3
    Layer_2 -->|"blocked"| REJECT["Action Rejected"]
    Layer_3 -->|"approved"| Layer_4
    Layer_3 -->|"pending"| WAIT["Await Human Input"]
    Layer_4 -->|"permitted"| EXEC["Execute Action"]
    Layer_4 -->|"denied"| REJECT

    style Layer_1 fill:#e94560,stroke:#fff,color:#fff
    style Layer_2 fill:#c44569,stroke:#fff,color:#fff
    style Layer_3 fill:#0f3460,stroke:#fff,color:#fff
    style Layer_4 fill:#533483,stroke:#fff,color:#fff
```

#### NeMo Guardrails Integration (Colang 2.0)

NeMo Guardrails wraps the Coder agent's LLM calls via `RunnableRails`:

```
Input → NeMo (input rails) → LLM → NeMo (output rails) → Output
```

| Rail | Type | Check |
|---|---|---|
| `check prompt injection` | Input | Detects prompt override attempts |
| `check hardcoded secrets` | Output | Detects API keys/passwords in generated code |
| `check unsafe file paths` | Output | Detects paths outside the sandbox |

#### HITL Gate Configuration

| Gate | Trigger Condition | User Options |
|---|---|---|
| PR to `main`/`master` | PR Agent targets protected branch | approve / reject / inspect |
| Large commit | Commit touches > 5 files | approve / reject / inspect |
| `git push` | Any `execute` containing `git push` | approve / reject / inspect |
| Retry after failures | `retry_count >= 2` | approve / reject |

---

### 4.7 Sandbox Execution (`sandbox/`)

All code execution happens in isolated sandbox directories — never in the live repository.

```mermaid
graph TD
    REPO["Live Repository"]
    EXPLORER["Repo Explorer<br/>(identifies files)"]
    
    REPO -->|"relevant files only"| SANDBOX["Sandbox Directory<br/>~/.codepilot/sandboxes/<br/>issue-{id}/"]
    EXPLORER -->|"file list"| SANDBOX
    
    SANDBOX --> CODER["Coder Agent<br/>(read_write in /sandbox/)"]
    SANDBOX --> TEST["Test Agent<br/>(execute in /sandbox/)"]
    
    CODER -->|"edits"| DIFF["Proposed Diff<br/>working/proposed_diff.txt"]
    TEST -->|"results"| TR["TestResult<br/>{passed, failed, errors}"]
    
    SANDBOX -->|"DONE or FAILED"| CLEANUP["Cleanup<br/>(delete sandbox)"]

    style SANDBOX fill:#e94560,stroke:#fff,color:#fff
```

**Filesystem Permissions:**

| Path | Access Level |
|---|---|
| `/sandbox/` | `read_write` — Coder and Test Agent can modify |
| `/` (everything else) | `read_only` — prevents escape |

**Sandbox Providers (extensible):**

| Provider | Description |
|---|---|
| `local` (default) | Isolated directory on the local filesystem |
| `daytona` (Bonus) | Daytona cloud workspace |
| `modal` (Bonus) | Modal cloud sandbox |

---

### 4.8 GitHub Integration (`github_integration/`)

Wraps all GitHub API interactions behind a clean service interface.

```mermaid
graph TD
    subgraph Abstraction["Service Abstraction"]
        GHS["GitHubService<br/>(clean interface)"]
    end

    subgraph Implementation["Implementation Layer"]
        GHTK["GitHubToolkit<br/>(langchain-community)"]
        GHAPI["GitHubAPIWrapper<br/>(GitHub App auth)"]
        PYG["PyGithub<br/>(fallback)"]
    end

    subgraph Consumers["Consumer Modules"]
        POLLER["Issue Poller<br/>(async polling loop)"]
        CLASSIFIER["Task Classifier<br/>(LLM structured output)"]
        PRB["PR Builder<br/>(pure helper functions)"]
        SCORER["Triage Scorer<br/>(Bonus)"]
    end

    GHS --> GHTK
    GHTK --> GHAPI
    GHS -.->|"fallback"| PYG

    POLLER --> GHS
    CLASSIFIER --> GHS
    PRB --> GHS
    SCORER --> GHS

    style Abstraction fill:#e94560,stroke:#fff,color:#fff
    style Implementation fill:#0f3460,stroke:#fff,color:#fff
    style Consumers fill:#533483,stroke:#fff,color:#fff
```

#### GitHub Authentication

CodePilot uses **GitHub App authentication** (App ID + private key `.pem` file), which provides:
- Fine-grained permissions per repository
- Higher rate limits than PATs
- Installation-level access tokens

#### Issue Polling Flow

```
Poll (every N min) → Filter (ai-assignable, unassigned) → Classify (LLM) → Score (Bonus) → Yield to Orchestrator
```

---

### 4.9 Terminal UI (`tui/`)

The TUI is built with the **Textual** framework and provides a 4-panel fixed layout.

```
┌──────────────────────┬──────────────────────────────────┐
│   GitHub Issues      │          Active Task              │
│  ──────────────      │  ────────────────────────────     │
│  #42 open ●          │  Issue #42: Fix null pointer      │
│  #38 in-progress ◐   │  Status: IMPLEMENTING             │
│  #31 done ✓          │  Agent: Coder (retry 1/3)         │
│  #27 failed ✗        │  Skill: bug_fix                   │
│  ⌨ manual-a3f [manual] │  Todo: [✓] Reproduce             │
│                      │        [✓] Localize               │
│                      │        [ ] Fix                    │
├──────────────────────┼──────────────────────────────────┤
│   Agent Logs         │        Human Approval             │
│  ──────────────      │  ────────────────────────────     │
│  [Orchestrator]      │  ⚠ Coder wants to open PR         │
│  Spawning Repo       │  to main (5 files changed)        │
│  Explorer...         │                                    │
│  [RepoExplorer]      │  > approve / reject / inspect     │
│  Found 8 relevant    │                                    │
│  files               │                                    │
└──────────────────────┴──────────────────────────────────┘
  [i] New task   [s] Skip issue   [q] Quit   [l] Logs
```

#### Panel Responsibilities

| Panel | Widget | Updates Via | Content |
|---|---|---|---|
| **GitHub Issues** | `ListView` | Polling loop events | Issue list with status indicators (●◐✓✗⌨) |
| **Active Task** | Custom widget | State machine transitions | Current task details, agent, skill, todo checklist |
| **Agent Logs** | `RichLog` | `BaseAgent.stream()` | Streaming agent thoughts and tool calls (prefixed by agent name) |
| **Human Approval** | Custom widget | HITL events | Actionable requests (approve/reject/inspect) + non-actionable alerts (merge conflicts) |

#### Keyboard Shortcuts

| Key | Action |
|---|---|
| `i` | Open input modal for free-form manual task |
| `s` | Skip the current issue |
| `q` | Quit CodePilot |
| `l` | Toggle full-screen agent logs |

---

## 5. Data Flow & Sequences

### End-to-End Issue Resolution Flow

```mermaid
sequenceDiagram
    participant GH as GitHub
    participant Poller as Issue Poller
    participant ORC as Orchestrator
    participant CLS as Classifier
    participant RE as Repo Explorer
    participant COD as Coder
    participant TST as Test Agent
    participant PRA as PR Agent
    participant TUI as TUI
    participant Human as Human

    loop Every N minutes
        Poller->>GH: list_issues(labels=["ai-assignable"])
        GH-->>Poller: Open issues
    end

    Poller->>ORC: New issue detected
    ORC->>TUI: Update Issues panel (● open)
    ORC->>CLS: Classify issue
    CLS-->>ORC: TaskClassification(type, confidence)
    Note over ORC: State: TRIAGED

    ORC->>RE: spawn(task_description, repo_path)
    Note over ORC: State: EXPLORING
    RE->>RE: Build/load Repo Map
    RE->>RE: Semantic/keyword retrieval
    RE-->>ORC: Relevant file paths (top-K)

    ORC->>COD: spawn(file_paths, skill, working_memory)
    Note over ORC: State: IMPLEMENTING
    ORC->>TUI: Update Active Task panel
    COD->>COD: read_file (on-demand)
    COD->>COD: write_todos (plan)
    COD->>COD: edit_file (implement)
    COD->>COD: execute (verify in sandbox)
    
    COD->>TST: spawn(sandbox_path)
    Note over ORC: State: TESTING
    TST->>TST: Run test suite
    TST-->>COD: TestResult

    alt Tests pass
        COD-->>ORC: Diff + modified files
        ORC->>ORC: Review proposed diff
        alt Diff approved
            ORC->>PRA: spawn(diff, issue_metadata)
            Note over ORC: State: PR_OPENED
        else Diff needs retry
            ORC->>COD: Retry with feedback
        else Diff escalated
            ORC->>TUI: Show diff in Approval panel
            TUI->>Human: Request approval
            Human-->>TUI: approve / reject
        end
    else Tests fail (retry ≤ 3)
        TST-->>COD: Failure details
        COD->>COD: Retry implementation
    end

    PRA->>GH: Create branch + commit + PR
    PRA->>TUI: Show HITL gate (if PR to main)
    TUI->>Human: Approve PR?
    Human-->>TUI: approve
    PRA->>GH: Open PR
    Note over ORC: State: DONE
    ORC->>TUI: Update Issues panel (✓ done)
```

### Manual Task Flow

```mermaid
sequenceDiagram
    participant Human as Human
    participant TUI as TUI
    participant ORC as Orchestrator
    participant CLS as Classifier

    Human->>TUI: Press [i], type task
    TUI->>ORC: ManualTask(description, source="user_input")
    ORC->>CLS: Classify task → select Skill
    
    Note over ORC: Same flow as GitHub issues<br/>(TRIAGED → EXPLORING → ...)
    
    ORC->>TUI: Task complete. Open PR?
    TUI->>Human: approve (PR) / reject (local only)
    
    alt Approved
        ORC->>ORC: Spawn PR Agent (branch: codepilot/manual-{slug})
    else Rejected
        ORC->>ORC: Keep changes in sandbox, write diff
    end
```

---

## 6. State Management

### Task State Machine

```python
class TaskState(str, Enum):
    TRIAGED       = "TRIAGED"        # Issue classified, skill selected
    EXPLORING     = "EXPLORING"      # Repo Explorer analyzing codebase
    IMPLEMENTING  = "IMPLEMENTING"   # Coder Agent making changes
    TESTING       = "TESTING"        # Test Agent running test suite
    PR_OPENED     = "PR_OPENED"      # PR Agent creating pull request
    DONE          = "DONE"           # Task completed successfully
    FAILED        = "FAILED"         # Task failed (max retries, merge conflict, human rejection)
```

### Valid State Transitions

```
TRIAGED      → EXPLORING
EXPLORING    → IMPLEMENTING | FAILED
IMPLEMENTING → TESTING | FAILED
TESTING      → IMPLEMENTING (retry) | PR_OPENED (via diff review)
PR_OPENED    → DONE | FAILED (merge conflict)
```

### Working Memory Lifecycle

```mermaid
graph LR
    CREATE["Task Start<br/>(create WorkingMemory)"]
    ACTIVE["Active<br/>(modified by agents)"]
    PERSIST["Session End<br/>(write to episodic)"]
    LEARN["PR Merged<br/>(write to semantic)"]
    CLEAR["Clear<br/>(free memory)"]

    CREATE --> ACTIVE
    ACTIVE --> PERSIST
    ACTIVE --> LEARN
    PERSIST --> CLEAR
    LEARN --> CLEAR

    style CREATE fill:#2d5a27,stroke:#4a9e42,color:#fff
    style CLEAR fill:#e94560,stroke:#fff,color:#fff
```

---

## 7. Security Architecture

### Threat Model

| Threat | Mitigation |
|---|---|
| **Sandbox escape** | Filesystem permissions (`read_only` outside `/sandbox/`), path validation in command filter |
| **Dangerous commands** | Command filter blocks `rm -rf`, `curl`, `wget`, `pip install`; NeMo output rails |
| **Credential exposure** | File filter blocks `.env`, `*.pem`, `*.key`; NeMo detects hardcoded secrets |
| **Prompt injection** | NeMo input rails detect override attempts |
| **Unreviewed changes** | HITL gates for PR to main, large commits, git push, excessive retries |
| **Infinite loops** | Max retry count (`MAX_CODER_RETRIES = 3`); HITL gate after 2 test failures |

### Security Layers (ordered by execution)

```
1. Custom Filters (command_filter.py, file_filter.py)
   ↓ pass
2. NeMo Guardrails (input rails → LLM → output rails)
   ↓ pass
3. HITL Gates (hitl.py → TUI approval panel)
   ↓ approved
4. Filesystem Permissions (sandbox/manager.py)
   ↓ permitted
5. Execution in sandboxed directory
```

---

## 8. Technology Stack

```mermaid
graph TD
    subgraph Application["Application"]
        CP["CodePilot"]
    end

    subgraph Frameworks["Frameworks & Libraries"]
        DA["deepagents<br/>(Agent Framework)"]
        LG["LangGraph<br/>(Agent Runtime)"]
        TX["Textual<br/>(TUI Framework)"]
        NMG["NeMo Guardrails<br/>(Safety)"]
        PS["pydantic-settings<br/>(Config)"]
    end

    subgraph LLMs["LLM Providers"]
        CL["Claude Sonnet<br/>(langchain-anthropic)"]
        GP["GPT-4o<br/>(langchain-openai)"]
        GM["Gemini 1.5 Pro<br/>(langchain-google-genai)"]
    end

    subgraph Storage["Storage"]
        CDB["ChromaDB<br/>(Semantic memory)"]
        LMS["LangGraph Memory Store<br/>(Episodic memory)"]
        SQ["SQLite<br/>(LangGraph checkpointing)"]
    end

    subgraph External["External Services"]
        GHA["GitHub API<br/>(via GitHubToolkit)"]
        LS["LangSmith<br/>(Bonus: tracing)"]
    end

    CP --> DA
    CP --> LG
    CP --> TX
    CP --> NMG
    CP --> PS
    DA --> CL
    DA --> GP
    DA --> GM
    CP --> CDB
    CP --> LMS
    LG --> SQ
    CP --> GHA
    CP -.-> LS

    style Application fill:#e94560,stroke:#fff,color:#fff
    style Frameworks fill:#0f3460,stroke:#fff,color:#fff
    style LLMs fill:#16213e,stroke:#fff,color:#fff
    style Storage fill:#533483,stroke:#fff,color:#fff
    style External fill:#1a1a2e,stroke:#fff,color:#fff
```

### Package Summary

| Package | Purpose |
|---|---|
| `deepagents` | Core agent framework |
| `langchain-anthropic` | Primary LLM — Claude Sonnet |
| `langchain-openai` | Fallback LLM — GPT-4o |
| `langchain-google-genai` | Fallback LLM — Gemini 1.5 Pro |
| `langchain-community` | GitHub Toolkit |
| `langgraph` | Agent runtime + checkpointing |
| `chromadb` | Semantic memory vector store |
| `textual` | TUI framework |
| `nemoguardrails` | Guardrails framework (Colang 2.0) |
| `pydantic-settings` | Configuration management |
| `tiktoken` | Token counting for Repo Map budget |
| `pygithub` | GitHub API fallback |
| `aiosqlite` | Async SQLite for LangGraph checkpointing |
| `pytest` + `pytest-asyncio` | Testing |

---

## 9. Directory Structure

```
c:\ai-engineering\codepilot-agent\
├── src/
│   └── codepilot/
│       ├── __init__.py
│       ├── main.py                  # Entry point
│       ├── config.py                # Settings (pydantic-settings)
│       │
│       ├── core/                    # ★ Abstraction layer over deepagents
│       │   ├── __init__.py
│       │   ├── agent_factory.py     # Wraps create_deep_agent()
│       │   ├── base_agent.py        # Abstract agent interface
│       │   ├── tool_registry.py     # Tool management abstraction
│       │   ├── llm_provider.py      # Multi-provider LLM factory
│       │   └── tracing.py           # LangSmith instrumentation (Bonus)
│       │
│       ├── agents/                  # Agent implementations
│       │   ├── __init__.py
│       │   ├── orchestrator.py      # Root Orchestrator agent
│       │   ├── repo_explorer.py     # Repo Explorer subagent
│       │   ├── coder.py             # Coder subagent
│       │   ├── test_agent.py        # Test Agent subagent
│       │   ├── pr_agent.py          # PR Agent subagent
│       │   └── meta_test_agent.py   # Self-healing meta-agent (Bonus)
│       │
│       ├── skills/                  # Reusable coding workflows
│       │   ├── __init__.py
│       │   ├── base.py              # Skill dataclass & registry
│       │   ├── bug_fix.py
│       │   ├── feature_addition.py
│       │   ├── dependency_update.py
│       │   ├── documentation.py
│       │   └── config_change.py
│       │
│       ├── memory/                  # 3-tier memory system
│       │   ├── __init__.py
│       │   ├── episodic.py          # LangGraph Memory Store
│       │   ├── semantic.py          # ChromaDB vector store
│       │   └── working.py           # In-memory task state
│       │
│       ├── guardrails/              # Safety & approval gates
│       │   ├── __init__.py
│       │   ├── command_filter.py    # Dangerous command blocker
│       │   ├── file_filter.py       # Sensitive file write blocker
│       │   ├── hitl.py              # Human-in-the-loop gate logic
│       │   └── config/              # NeMo Guardrails configs
│       │       ├── config.yml
│       │       ├── rails.co
│       │       └── actions.py
│       │
│       ├── github_integration/      # GitHub API abstraction
│       │   ├── __init__.py
│       │   ├── github_service.py    # Wraps GitHubToolkit
│       │   ├── issue_poller.py      # Async polling loop
│       │   ├── pr_builder.py        # PR metadata helpers (pure)
│       │   ├── classifier.py        # Issue → task type classifier
│       │   └── triage_scorer.py     # Complexity scoring (Bonus)
│       │
│       ├── context/                 # Context engineering
│       │   ├── __init__.py
│       │   ├── repo_map.py          # Repo Map builder & cache
│       │   └── retriever.py         # Keyword + embedding retrieval
│       │
│       ├── sandbox/                 # Sandboxed execution
│       │   ├── __init__.py
│       │   ├── manager.py           # Local sandbox setup/teardown
│       │   └── cloud_sandbox.py     # Cloud sandbox (Bonus)
│       │
│       ├── tui/                     # Terminal UI
│       │   ├── __init__.py
│       │   ├── app.py               # Textual App class
│       │   ├── panels/
│       │   │   ├── __init__.py
│       │   │   ├── issues.py        # GitHub Issues panel
│       │   │   ├── active_task.py   # Active Task panel
│       │   │   ├── agent_logs.py    # Streaming Agent Logs panel
│       │   │   └── approval.py      # Human Approval panel
│       │   └── styles.tcss          # Textual CSS
│       │
│       └── acp_server.py            # ACP HTTP server (Bonus)
│
├── tests/
│   ├── __init__.py
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
│
├── docs/
│   ├── architecture.md              # ← This document
│   ├── implementation_plan.md
│   └── coding_platform.md
│
├── pyproject.toml
├── Makefile
├── .env.example
├── .gitignore
└── README.md
```

---

## 10. Deployment & Configuration

### Configuration (via `pydantic-settings`)

All settings are loaded from `.env` + environment variables:

| Setting | Default | Description |
|---|---|---|
| `PRIMARY_LLM` | `anthropic:claude-sonnet-4-20250514` | Primary LLM model |
| `FALLBACK_LLMS` | `openai:gpt-4o,google:gemini-1.5-pro` | Fallback chain |
| `GITHUB_APP_ID` | — | GitHub App ID |
| `GITHUB_APP_PRIVATE_KEY_PATH` | — | Path to `.pem` file |
| `GITHUB_REPOSITORY` | `codepilot-test-repo` | Target repository |
| `POLL_INTERVAL_MINUTES` | `5` | Issue polling frequency |
| `REPO_MAP_TOKEN_BUDGET` | `4000` | Max tokens for Repo Map |
| `MAX_RELEVANT_FILES` | `10` | Top-K files from retriever |
| `MAX_CODER_RETRIES` | `3` | Max retry attempts |
| `SANDBOX_BASE_DIR` | `~/.codepilot/sandboxes/` | Sandbox root directory |
| `CHROMADB_PERSIST_DIR` | `~/.codepilot/data/chromadb/` | ChromaDB directory |
| `COMPLEXITY_THRESHOLD` | `7` | Max issue complexity (1–10) |
| `AUTO_SUMMARIZATION_ENABLED` | `True` | Enable conversation summarization |
| `SUMMARIZATION_THRESHOLD` | `20` | Turns before summarization triggers |

### Data Directory Layout

```
~/.codepilot/
├── sandboxes/                    # Sandbox directories (temporary)
│   └── issue-{id}/              # Per-task sandbox
├── data/
│   └── chromadb/                 # ChromaDB persistent storage
└── cache/
    └── repo_maps/                # Cached Repo Maps (JSON)
```

---

## 11. Extension Points (Bonus)

These are additive features designed after core stability is achieved:

```mermaid
graph TD
    CORE["Core CodePilot<br/>(Phases 1–5)"]
    
    B1["🔧 Bonus 1<br/>Self-Healing Tests<br/>(meta_test_agent.py)"]
    B2["📊 Bonus 2<br/>Issue Triage Scoring<br/>(triage_scorer.py)"]
    B3["🔍 Bonus 3<br/>LangSmith Tracing<br/>(tracing.py)"]
    B4["☁️ Bonus 4<br/>Cloud Sandbox<br/>(cloud_sandbox.py)"]
    B5["🔌 Bonus 5<br/>ACP Integration<br/>(acp_server.py)"]
    
    CORE --> B1
    CORE --> B2
    CORE --> B3
    CORE --> B4
    CORE --> B5

    style CORE fill:#e94560,stroke:#fff,color:#fff
    style B1 fill:#2d5a27,stroke:#4a9e42,color:#fff
    style B2 fill:#2d5a27,stroke:#4a9e42,color:#fff
    style B3 fill:#2d5a27,stroke:#4a9e42,color:#fff
    style B4 fill:#2d5a27,stroke:#4a9e42,color:#fff
    style B5 fill:#2d5a27,stroke:#4a9e42,color:#fff
```

| Bonus | Description | Key Addition |
|---|---|---|
| **Self-Healing Tests** | Meta-agent debugs broken test infrastructure | New agent: `meta_test_agent.py` |
| **Issue Triage Scoring** | LLM-based complexity scoring (1–10) with threshold filtering | New module: `triage_scorer.py` |
| **LangSmith Tracing** | Full observability via LangSmith trace trees | New module: `tracing.py` |
| **Cloud Sandbox** | Daytona or Modal for true container isolation | New module: `cloud_sandbox.py`; `SandboxInterface` ABC |
| **ACP Integration** | HTTP API for Zed/Cursor integration | New module: `acp_server.py` |

---

## Risk Mitigation Summary

| Risk | Impact | Mitigation Strategy |
|---|---|---|
| `deepagents` API instability | High | Abstraction layer isolates all agents; swap to `LangGraphFactory` in one file |
| `langchain-community` GitHub Toolkit deprecation | Medium | `GitHubService` wrapper can swap to `PyGithub` |
| Claude Sonnet rate limits | Medium | Multi-provider fallback chain |
| Sandbox escape via `execute` | High | 4-layer guardrails: filters → NeMo → HITL → filesystem permissions |
| TUI complexity | Medium | Incremental panel development; Textual's built-in `RichLog` + `ListView` |
| LLM rate limits during polling | Medium | Classification caching; configurable poll intervals |

---

*This document is the authoritative architecture reference for CodePilot. For implementation details and phased build plan, see [implementation_plan.md](file:///c:/ai-engineering/codepilot-agent/docs/implementation_plan.md).*
