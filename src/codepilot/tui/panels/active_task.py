"""Active Task Panel — shows current task state, TODOs, and agent status.

Displays:
    - Task title and state machine position
    - TODO checklist with progress indicators
    - Loaded skill name
    - Retry count and failure reason if applicable
"""

from __future__ import annotations

from textual.widgets import Static


class ActiveTaskPanel(Static):
    """Panel showing the currently active task details."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "Active Task"
        self.update("No active task")

    def show_task(
        self,
        task_id: int,
        title: str,
        state: str,
        skill: str = "",
        todos: list[str] | None = None,
        retry_count: int = 0,
        failure_reason: str = "",
    ) -> None:
        """Display the current task information.

        Args:
            task_id: Task identifier.
            title: Task description.
            state: Current state machine state.
            skill: Loaded skill name.
            todos: TODO checklist items.
            retry_count: Current retry count.
            failure_reason: Reason for failure if applicable.
        """
        lines = [
            f"Task #{task_id}: {title[:80]}",
            f"[bold]Status:[/bold] {state}",
        ]

        if skill:
            lines.append(f"[bold]Skill:[/bold] {skill}")

        if todos:
            lines.append("\n[bold]Checklist:[/bold]")
            for todo in todos:
                lines.append(f"  [ ] {todo}")

        if retry_count > 0:
            lines.append(f"\n[bold]Retries:[/bold] {retry_count}")

        if failure_reason:
            lines.append(f"[bold]Failure:[/bold] {failure_reason}")

        self.update("\n".join(lines))

    def clear_task(self) -> None:
        """Clear the active task display."""
        self.update("No active task")
