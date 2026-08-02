"""Tests for the TUI app and panels."""

import pytest

from codepilot.tui.app import CodePilotApp
from codepilot.tui.panels.active_task import ActiveTaskPanel
from codepilot.tui.panels.agent_logs import AgentLogsPanel
from codepilot.tui.panels.approval import ApprovalPanel
from codepilot.tui.panels.issues import IssuesPanel


class TestCodePilotApp:
    """Test the TUI application."""

    @pytest.mark.asyncio
    async def test_app_instantiates(self):
        app = CodePilotApp()
        assert app is not None
        assert app.TITLE == "CodePilot"

    def test_bindings_exist(self):
        app = CodePilotApp()
        binding_keys = {b.key for b in app.BINDINGS}
        assert "q" in binding_keys
        assert "i" in binding_keys
        assert "s" in binding_keys
        assert "l" in binding_keys

    @pytest.mark.asyncio
    async def test_compose_creates_four_panels(self):
        app = CodePilotApp()
        async with app.run_test() as pilot:
            assert pilot.app.query_one("#issues-panel") is not None
            assert pilot.app.query_one("#task-panel") is not None
            assert pilot.app.query_one("#logs-panel") is not None
            assert pilot.app.query_one("#approval-panel") is not None


class TestIssuesPanel:
    """Test the Issues panel."""

    @pytest.mark.asyncio
    async def test_add_issue(self):
        app = CodePilotApp()
        async with app.run_test() as pilot:
            panel = pilot.app.query_one("#issues-panel", IssuesPanel)
            panel.add_issue(42, "Fix bug", "bug_fix")
            assert len(panel._issue_items) >= 1

    @pytest.mark.asyncio
    async def test_add_manual_task(self):
        app = CodePilotApp()
        async with app.run_test() as pilot:
            panel = pilot.app.query_one("#issues-panel", IssuesPanel)
            panel.add_manual_task("Add dark mode")
            assert len(panel.children) >= 1


class TestActiveTaskPanel:
    """Test the Active Task panel."""

    def test_default_shows_no_task(self):
        panel = ActiveTaskPanel()
        content = panel._Static__content  # type: ignore[attr-defined]
        assert "No active task" in content

    def test_show_task(self):
        panel = ActiveTaskPanel()
        panel.show_task(
            42,
            "Fix bug",
            "IMPLEMENTING",
            skill="bug_fix",
            todos=["Read files", "Fix", "Test"],
        )
        content = panel._Static__content  # type: ignore[attr-defined]
        assert "Fix bug" in content
        assert "IMPLEMENTING" in content
        assert "bug_fix" in content

    def test_clear_task(self):
        panel = ActiveTaskPanel()
        panel.show_task(1, "Test", "EXPLORING")
        panel.clear_task()
        content = panel._Static__content  # type: ignore[attr-defined]
        assert "No active task" in content


class TestAgentLogsPanel:
    """Test the Agent Logs panel."""

    def test_add_entry(self):
        panel = AgentLogsPanel()
        panel.add_entry("[Orchestrator]", "Processing task")
        assert panel is not None


class TestApprovalPanel:
    """Test the Approval panel."""

    def test_no_pending(self):
        panel = ApprovalPanel()
        content = panel._Static__content  # type: ignore[attr-defined]
        assert "No pending approvals" in content

    def test_show_pending(self):
        panel = ApprovalPanel()
        panel.show_pending(
            [
                {
                    "task_id": 42,
                    "gate_type": "pr_to_protected",
                    "description": "PR to main branch",
                }
            ]
        )
        content = panel._Static__content  # type: ignore[attr-defined]
        assert "Task #42" in content

    def test_show_notification(self):
        panel = ApprovalPanel()
        panel.show_notification("merge_conflict", "Conflict on main")
        content = panel._Static__content  # type: ignore[attr-defined]
        assert "merge_conflict" in content
