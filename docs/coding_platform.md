# Assignment 01 — Multi-Agent Coding Platform (CodePilot)


## 🏢 Business Context

**DevStream Labs** is a mid-sized software company whose engineering teams manage dozens of active GitHub repositories. Their developers spend significant time triaging and fixing routine GitHub issues — dependency upgrades, bug fixes flagged by tests, documentation gaps, and configuration drift. These are well-defined tasks that follow repeatable patterns, but they consume hours of developer attention every sprint.

The engineering lead has green-lit an internal project: build **CodePilot**, a terminal-based AI coding agent that can autonomously solve GitHub issues and open pull requests, while also responding to direct tasks typed by engineers in a TUI. CodePilot should behave like a skilled junior engineer — it reads the issue, explores the codebase, writes a plan, implements the fix, runs tests, and opens a PR — asking for human approval before any destructive or ambiguous operation.

You are building CodePilot.

---

## 🎯 Project Objective

Build a **multi-agent coding platform** as a TUI application that:

- Proactively polls a GitHub repository for open, unassigned issues and attempts to solve them autonomously
- Accepts direct task instructions from the user via a terminal interface
- Executes code in a sandboxed local environment to verify solutions before committing
- Uses Skills for reusable coding workflows and Memory to learn patterns across sessions
- Enforces Guardrails to prevent unsafe operations
- Opens GitHub Pull Requests with structured descriptions upon successful task completion

---

## 🤖 Agent Architecture

CodePilot is built as a multi-agent system using DeepAgents' subagent spawning capability. The **Orchestrator** is the root agent; all others are subagents spawned via the `task` tool.

```
┌─────────────────────────────────────────────────────┐
│                    TUI (Textual)                     │
│  [Issue Feed] [Active Task] [Agent Logs] [Shell]     │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
          ┌────────────────────────┐
          │   Orchestrator Agent   │  ← Root deep agent
          │   - Reads issues       │    create_deep_agent()
          │   - Plans tasks        │    with write_todos tool
          │   - Spawns subagents   │
          │   - Manages memory     │
          └────────┬───────────────┘
        ┌──────────┼─────────────────────┐
        ▼          ▼                     ▼
┌─────────────┐ ┌──────────────┐  ┌──────────────┐
│ Repo        │ │ Coder Agent  │  │   PR Agent   │
│ Explorer    │ │ - Writes code│  │ - Creates    │
│ - Maps repo │ │ - Edits files│  │   branch     │
│ - Finds     │ │ - Runs tests │  │ - Commits    │
│   context   │ │   in sandbox │  │ - Opens PR   │
└─────────────┘ └──────┬───────┘  └──────────────┘
                        │
               ┌────────▼────────┐
               │   Test Agent    │
               │ - Writes tests  │
               │ - Runs suite    │
               │ - Reports fails │
               └─────────────────┘
```

### Agent Responsibilities

| Agent | DeepAgents Role | Key Tools |
|---|---|---|
| **Orchestrator** | Root `create_deep_agent` with planning loop | `write_todos`, `task` (spawn subagents), GitHub Toolkit: `list_issues`, LangGraph Memory Store |
| **Repo Explorer** | Subagent spawned for codebase analysis | `ls`, `read_file`, semantic code search, repo map builder |
| **Coder** | Subagent spawned for implementation | `read_file`, `write_file`, `edit_file`, `execute` (sandboxed), filesystem permissions |
| **Test Agent** | Subagent spawned by Coder for verification | `write_file`, `execute`, test result parser |
| **PR Agent** | Subagent spawned after tests pass | GitHub Toolkit: `create_branch`, `create_pull_request`, `create_commit` |

---

## 🔧 Technical Requirements

### Component 1 — Orchestrator Agent with Issue Polling

The Orchestrator is the system's brain. It runs a continuous loop: poll GitHub for open unassigned issues → classify the issue → spawn the appropriate subagent chain → track completion → repeat.

**Requirements:**

- Instantiate the Orchestrator using `create_deep_agent()` from `deepagents` with a planning-oriented system prompt
- Implement a GitHub issue polling loop using the **LangChain GitHub Toolkit** (`GitHubToolkit` from `langchain_community.agent_toolkits`):
  - Poll every N minutes (configurable, default 5)
  - Filter to issues labelled `ai-assignable` or unassigned issues below a configurable complexity threshold
  - Exclude issues already being processed (track in-progress issue IDs in working memory)
- Use the built-in `write_todos` tool to break each issue into an implementation checklist before spawning subagents
- Implement a **task classification** step before planning: categorize each issue as one of `bug_fix`, `feature_addition`, `dependency_update`, `documentation`, `config_change` — this determines which Skill is loaded and which subagents are spawned
- Maintain an **Orchestrator state machine** per task: `TRIAGED → EXPLORING → IMPLEMENTING → TESTING → PR_OPENED → DONE | FAILED`

---

### Component 2 — Repo Explorer Agent & Context Engineering

The single hardest problem in coding agents is context management: a real repository may have thousands of files, and the full codebase cannot fit in any context window. The Repo Explorer must build a compressed, queryable representation of the repo — a **Repo Map** — that lets the Coder agent find relevant files without reading everything.

**Requirements:**

**Repo Map Construction:**
- Recursively walk the repository, building a structured map: directory tree + per-file summaries (file path, language, exported symbols, 1-line description)
- The Repo Map must fit within a configurable token budget (default 4000 tokens). Summarize or truncate aggressively to stay under budget
- Cache the Repo Map to disk and invalidate it when files change (use git diff to detect changes since last run)
- Store the Repo Map in the DeepAgents virtual filesystem via `write_file` so all subagents can access it without rebuilding

**Relevant File Retrieval:**
- Given a task description, the Repo Explorer uses semantic search over the Repo Map to return the top-K most relevant files (default K=10)
- Implement two retrieval strategies and let the Orchestrator choose:
  - **Keyword matching** — fast, using file summaries
  - **Embedding search** — slower, using embeddings of file content chunks stored in ChromaDB

**Context Engineering rules your implementation must follow** (per DeepAgents' context engineering principles):
- Subagents must use `read_file` to load files on-demand rather than passing full file contents in the initial prompt
- The Orchestrator must not include raw file content in task delegation prompts — only file paths
- Auto-summarization must be enabled (`summarization=True` in the backend config) to compact older conversation turns


---

### Component 3 — Coder Agent with Sandboxed Execution

The Coder agent implements the actual fix. It reads relevant files, makes edits, and verifies the result by executing code in an isolated sandbox before passing control to the Test Agent.

**Requirements:**

- Use `deepagents`' **local sandbox backend** for the Coder agent so that the `execute` tool runs shell commands in an isolated directory (not the live repo)
  - The sandbox must be a copy of the relevant repo subset, not the full repo
  - Configure **filesystem permissions** declaratively to prevent the Coder from writing outside the working directory:
    ```python
    permissions=[
        Permission(path="/sandbox/", access="read_write"),
        Permission(path="/", access="read_only"),
    ]
    ```
- The Coder agent must follow this inner loop:
  1. Read relevant files identified by the Repo Explorer
  2. Formulate a change plan (write to todos)
  3. Implement edits using `edit_file` (prefer surgical edits over full-file rewrites)
  4. Run the modified code in the sandbox via `execute` to verify it doesn't crash
  5. Spawn the Test Agent; if tests fail, receive the failure report and retry (max 3 retries)
- Implement a **diff preview step**: before finalizing, the Coder generates a unified diff and writes it to `working/proposed_diff.txt` for the Orchestrator to review

**Guardrails for the Coder Agent:**
- Block any `execute` call that contains: `rm -rf`, `curl`, `wget`, `pip install` (network installs), or any command targeting paths outside `/sandbox/`
- Block file edits to: `.env`, `*.secret`, `*.pem`, `*.key`, `*credentials*`
- If the Coder requests a blocked operation, it must explain the operation it wanted to perform and ask the human via the Human-in-the-loop interrupt


---

### Component 4 — Skills System

Skills are reusable agent capabilities — pre-built workflows, domain knowledge, and specialized instructions that the Orchestrator loads based on task type. DeepAgents' Skills system (`deepagents.skills`) is the mechanism for this.

**Requirements:**

Implement at least **4 Skills** corresponding to the task classification categories:

**`bug_fix_skill`**
- Instructions: reproduce the bug first (write a failing test), then fix it (make the test pass)
- Includes: debugging checklist, common Python/JS bug patterns, stack trace parsing logic
- Workflow: `reproduce → localize → fix → verify`

**`feature_addition_skill`**
- Instructions: understand existing patterns before adding new code (read similar existing features first)
- Includes: interface design checklist, backward compatibility reminder, documentation requirement
- Workflow: `explore_pattern → design → implement → test → document`

**`dependency_update_skill`**
- Instructions: check changelog between versions, update lockfiles, run full test suite
- Includes: common breaking change patterns per ecosystem (pip, npm, cargo)
- Workflow: `check_changelog → update → resolve_conflicts → test_all`

**`documentation_skill`**
- Instructions: match existing documentation style, include code examples, update README if public API changes
- Workflow: `read_existing → draft → review_accuracy → update_index`

Skills must be stored as structured objects (not just plain strings) with: `name`, `instructions`, `workflow_steps`, `example_prompts`, and `forbidden_actions`.

The Orchestrator selects a Skill by task type and passes it to the relevant subagent at spawn time:
```python
coder = agent.task(
    "Implement the fix",
    skill=skills.load("bug_fix_skill"),
    context_files=relevant_files
)
```

---

### Component 5 — Memory Management

CodePilot must improve over time. Three tiers of memory are required, each serving a different purpose.

**Requirements:**

**Episodic Memory (session-scoped, via LangGraph Memory Store):**
- Track all tasks attempted in the current session: issue ID, task type, files modified, outcome, duration
- At session end, write a structured session summary to the memory store
- The Orchestrator reads the last 3 session summaries at startup to avoid retrying recently failed issues

**Semantic Memory (cross-session, persistent):**
- After each successfully merged PR, extract a "lesson learned" entry: what the issue was, what files were changed, what approach worked
- Store lessons in a searchable vector store (ChromaDB) keyed by repository + issue type
- Before starting a new task, the Orchestrator retrieves the top-3 most similar past lessons and injects them into the Coder agent's context

**Working Memory (task-scoped, in-memory):**
- Maintain the current task state: issue metadata, Repo Map, relevant files list, current diff, test results, retry count
- Pass working memory explicitly to each subagent at spawn time rather than relying on conversation history
- Clear working memory when a task reaches `DONE` or `FAILED`

---

### Component 6 — PR Agent & GitHub Integration

When tests pass, the PR Agent takes over. It must create a clean, well-described pull request using the LangChain GitHub Toolkit.

**Requirements:**

- Create a new branch named `codepilot/issue-{issue_number}-{slug}` (where slug is a kebab-case summary of the issue title)
- Commit all changes from the sandbox with a structured commit message:
  ```
  fix(#{issue_number}): {one-line summary}

  - {bullet: what changed}
  - {bullet: why}
  - Closes #{issue_number}
  ```
- Open a PR to the default branch with:
  - Title: `[CodePilot] {issue title}`
  - Body: issue summary, implementation approach, files changed, test results, link to the original issue
  - Labels: `codepilot-generated`, `needs-review`
  - Request review from the issue's original reporter if available
- If the PR Agent encounters a merge conflict, it must **not** attempt to resolve it automatically — instead set the task state to `FAILED` and notify the human via TUI

**Human-in-the-loop (HITL) gates:**
Configure the following operations to require explicit human approval in the TUI before proceeding:

| Operation | Reason |
|---|---|
| Opening a PR to `main` or `master` | Irreversible without revert |
| Any commit touching more than 5 files | Risk of unintended scope |
| Any `execute` call containing `git push` | Network operation |
| Retry after 2 failed test runs | Prevents infinite loops |


---

### Component 7 — TUI (Textual)

Build the terminal interface using the **Textual** library. The TUI is the user's window into CodePilot's activity.

**Requirements:**

The TUI must have 4 panels in a fixed layout:

```
┌──────────────────┬──────────────────────────────┐
│  GitHub Issues   │        Active Task            │
│  ─────────────   │  ─────────────────────────    │
│  #42 open ●      │  Issue #42: Fix null pointer  │
│  #38 in-progress │  Status: IMPLEMENTING         │
│  #31 done ✓      │  Agent: Coder (retry 1/3)     │
│                  │  Skill: bug_fix_skill          │
│                  │  Todo: [✓] Reproduce           │
│                  │         [✓] Localize           │
│                  │         [ ] Fix                │
├──────────────────┼──────────────────────────────┤
│   Agent Logs     │       Human Approval           │
│  ─────────────   │  ─────────────────────────    │
│  [Orchestrator]  │  ⚠ Coder wants to open PR     │
│  Spawning Repo   │  to main (5 files changed)    │
│  Explorer...     │                                │
│  [RepoExplorer]  │  > approve / reject / inspect  │
│  Found 8 rel.    │                                │
│  files           │                                │
└──────────────────┴──────────────────────────────┘
  [i] New task  [s] Skip issue  [q] Quit  [l] Logs
```

- The Issues panel updates in real-time as the polling loop runs
- The Agent Logs panel streams agent thoughts and tool calls as they happen (use DeepAgents' streaming support)
- The Human Approval panel surfaces HITL interrupts and waits for keyboard input (`approve` / `reject` / `inspect`)
- The `[i] New task` shortcut opens an input prompt where the user can type a free-form coding task directly (not tied to a GitHub issue)



---

## 🧰 Technology Stack

| Layer | Tool |
|---|---|
| Agent Framework | `deepagents` (LangChain) |
| Agent Runtime | LangGraph (via deepagents) |
| GitHub Integration | `langchain_community.agent_toolkits.github` |
| Sandboxed Execution | DeepAgents local sandbox backend |
| Memory Store | LangGraph Memory Store (episodic) + ChromaDB (semantic) |
| LLM | Gemini 1.5 Pro / Groq Llama / Claude Sonnet |
| TUI | `textual` or any TUI framework |
| Guardrails | Custom Python + NeMo Guardrails |
| Context Engineering | DeepAgents virtual filesystem + auto-summarization |

---

## 📐 Evaluation Criteria

| Criterion | Weight |
|---|---|
| Multi-agent architecture correctly implemented using DeepAgents subagent spawning | 20% |
| Context engineering: Repo Map quality, token budget discipline, file-on-demand retrieval | 15% |
| Skills system: 4 skills implemented, correct skill loaded per task type | 15% |
| Guardrails: dangerous commands blocked, HITL gates function correctly | 15% |
| Memory: all 3 tiers implemented, semantic memory improves task planning | 15% |
| TUI: 4 panels functional, streaming logs, HITL approval workflow | 10% |
| PR quality: structured commit message, correct branch naming, labels | 10% |

---

## 🚀 Bonus Challenges

- **Self-healing tests:** If the Test Agent's tests themselves fail to parse/run, spawn a meta-agent that debugs the test setup before retrying
- **Issue triage scoring:** Before attempting any issue, score it 1–10 for estimated complexity (using the Repo Map + issue description) and skip issues above a configurable threshold
- **LangSmith tracing:** Instrument all agent calls with LangSmith for a full trace of multi-agent execution; include a screenshot in your README
- **Daytona or Modal sandbox:** Replace the local sandbox with a cloud sandbox (Daytona or Modal, both supported natively by DeepAgents) for true isolation
- **ACP integration:** Expose CodePilot as an ACP-compatible agent so it can be used from within Zed or Cursor

---

## 📌 Submission Instructions

1. Push to a public GitHub repo named `codepilot-agent`
2. `README.md` must include: setup instructions, architecture diagram, a screen recording or GIF of the TUI in action, and at least one example of a successfully generated PR
3. Record a **5–7 minute demo** showing: issue polling, a full task execution from issue to PR, a HITL approval prompt, and a guardrail block
4. Post on LinkedIn with a demo video.

---

*CodePilot is a fictional product built for learning purposes.*
