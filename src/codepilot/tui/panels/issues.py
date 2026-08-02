"""Issues Panel — shows polled GitHub issues with status indicators.

ListView widget with status icons:
    ● open, ◐ in-progress, ✓ done, ✗ failed
    ⌨ manual task indicator
"""

from __future__ import annotations

from textual.widgets import Label, ListItem, ListView


class IssuesPanel(ListView):
    """Panel showing active issues and manual tasks."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "Issues"
        self._issue_items: list[dict] = []

    def add_issue(
        self,
        number: int,
        title: str,
        classification: str = "",
        status: str = "open",
    ) -> None:
        """Add a GitHub issue to the list.

        Args:
            number: Issue number.
            title: Issue title.
            classification: Task type classification.
            status: open, in_progress, done, failed.
        """
        icons = {
            "open": "\u25cf",
            "in_progress": "\u25d0",
            "done": "\u2713",
            "failed": "\u2717",
        }
        icon = icons.get(status, "\u25cf")
        label_text = f"{icon} #{number}: {title[:60]} [{classification}]"
        self._issue_items.append({"number": number, "title": title, "status": status})
        self.append(ListItem(Label(label_text)))

    def add_manual_task(self, task: str) -> None:
        """Add a manual task to the list."""
        label_text = f"\u2328 {task[:60]} [manual]"
        self.append(ListItem(Label(label_text)))

    def update_status(self, number: int, status: str) -> None:
        """Update the status icon for a given issue."""
        icons = {
            "open": "\u25cf",
            "in_progress": "\u25d0",
            "done": "\u2713",
            "failed": "\u2717",
        }
        icon = icons.get(status, "\u25cf")
        for i, item in enumerate(self._issue_items):
            if item["number"] == number:
                item["status"] = status
                label_text = f"{icon} #{number}: {item['title'][:60]}"
                self.replace_item(ListItem(Label(label_text)), i)
                break
