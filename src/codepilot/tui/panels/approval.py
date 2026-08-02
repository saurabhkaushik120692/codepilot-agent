"""Approval Panel — shows pending HITL approval requests.

Two notification types:
1. Actionable — approve / reject / inspect buttons
2. Non-actionable — yellow warning banners

Subscribes to HITLManager for pending requests.
"""

from __future__ import annotations

from textual.widgets import Static


class ApprovalPanel(Static):
    """Panel showing pending HITL approval requests."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "Approvals"
        self.update("No pending approvals")

    def show_pending(self, requests: list[dict]) -> None:
        """Display pending approval requests.

        Args:
            requests: List of request dicts with keys:
                task_id, gate_type, description, details.
        """
        if not requests:
            self.update("No pending approvals")
            return

        lines = []
        for req in requests:
            lines.append(f"[bold]Task #{req['task_id']}[/bold] — {req['gate_type']}")
            lines.append(f"  {req['description']}")
            if req.get("details"):
                lines.append(f"  Details: {req['details'][:200]}")
            lines.append("  [a]Approve[/a] | [r]Reject[/r] | [i]Inspect[/i]")
            lines.append("")

        self.update("\n".join(lines))

    def show_notification(self, type: str, message: str) -> None:
        """Show a non-actionable notification banner.

        Args:
            type: Notification type (e.g., 'merge_conflict').
            message: The notification message.
        """
        self.update(f"[bold][yellow]\u26a0 {type}[/yellow][/bold]\n{message}")

    def clear(self) -> None:  # type: ignore[override]
        """Clear approval panel."""
        self.update("No pending approvals")
