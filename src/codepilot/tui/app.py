"""CodePilot TUI Application — 4-panel grid layout.

The main Textual App that renders the Issues, Active Task,
Agent Logs, and Approval panels. Handles keyboard bindings
for manual task input, issue skipping, and log toggling.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Footer, Header, Input

from codepilot.tui.panels.active_task import ActiveTaskPanel
from codepilot.tui.panels.agent_logs import AgentLogsPanel
from codepilot.tui.panels.approval import ApprovalPanel
from codepilot.tui.panels.issues import IssuesPanel


class CodePilotApp(App):
    """CodePilot TUI — 4-panel grid layout.

    Keyboard bindings:
        i — New manual task
        s — Skip current issue
        q — Quit
        l — Toggle agent logs
    """

    CSS_PATH = "styles.tcss"
    TITLE = "CodePilot"
    SUB_TITLE = "Multi-Agent Coding Platform"

    BINDINGS = [
        Binding("i", "new_task", "New Task"),
        Binding("s", "skip_issue", "Skip Issue"),
        Binding("q", "quit", "Quit"),
        Binding("l", "toggle_logs", "Toggle Logs"),
    ]

    def __init__(self, orchestrator=None, hitl_manager=None, config=None):
        super().__init__()
        self._orchestrator = orchestrator
        self._hitl_manager = hitl_manager
        self._config = config

    def compose(self) -> ComposeResult:
        """Create the 4-panel layout."""
        yield Header()
        yield Container(
            IssuesPanel(id="issues-panel"),
            ActiveTaskPanel(id="task-panel"),
            AgentLogsPanel(id="logs-panel"),
            ApprovalPanel(id="approval-panel"),
            id="main-grid",
        )
        yield Footer()

    async def action_new_task(self) -> None:
        """Open input modal for manual task entry."""
        await self._show_task_input()

    async def action_skip_issue(self) -> None:
        """Skip the current issue being processed."""

    async def action_toggle_logs(self) -> None:
        """Toggle the agent logs panel visibility."""
        logs = self.query_one("#logs-panel")
        logs.display = not logs.display

    async def _show_task_input(self) -> None:
        """Show input dialog for manual task entry."""

        def on_submit(value: str) -> None:
            if value.strip():
                self._handle_manual_task(value.strip())

        inp = Input(placeholder="Describe your coding task...")
        inp.styles.width = "100%"
        await self.mount(inp)
        inp.focus()

        def handle_submit(_event):
            val = inp.value
            inp.remove()
            on_submit(val)

        inp.on_submit = handle_submit  # type: ignore[method-assign]

    def _handle_manual_task(self, task: str) -> None:
        """Route a manual task to the Orchestrator."""
        issues = self.query_one("#issues-panel", IssuesPanel)
        issues.add_manual_task(task)
        logs = self.query_one("#logs-panel", AgentLogsPanel)
        logs.add_entry("[Orchestrator]", f"Manual task: {task}")
