"""Agent Logs Panel — streams agent thoughts and tool calls in real-time.

RichLog widget with auto-scroll and agent name prefix.
Max 1000 lines buffer with toggle via 'l' keybinding.
"""

from __future__ import annotations

from textual.widgets import RichLog


class AgentLogsPanel(RichLog):
    """Panel streaming agent logs with auto-scroll."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "Agent Logs"
        self.max_lines = 1000
        self.write("CodePilot agent logs...")

    def add_entry(self, agent_name: str, message: str) -> None:
        """Add a log entry with agent prefix.

        Args:
            agent_name: Name of the agent (e.g., '[Orchestrator]').
            message: The log message text.
        """
        formatted = f"[bold]{agent_name}[/bold] {message}"
        self.write(formatted)
