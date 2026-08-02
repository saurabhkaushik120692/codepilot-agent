"""Tests for PR Builder helper functions."""

from codepilot.github_integration.pr_builder import (
    build_branch_name,
    build_commit_message,
    build_pr_body,
    generate_manual_task_id,
    slugify,
)


class TestSlugify:
    def test_lowercase_and_replace_spaces(self):
        assert slugify("Fix Division By Zero") == "fix-division-by-zero"

    def test_remove_special_chars(self):
        assert slugify("Fix: calculator! error?") == "fix-calculator-error"

    def test_max_length(self):
        long_title = "a" * 100
        result = slugify(long_title, max_length=20)
        assert len(result) <= 20

    def test_empty_string(self):
        assert slugify("") == "task"

    def test_only_special_chars(self):
        assert slugify("!@#$%") == "task"


class TestBuildBranchName:
    def test_with_issue_number(self):
        name = build_branch_name(42, "Fix division by zero")
        assert name.startswith("codepilot/issue-42-")
        assert "fix-division-by-zero" in name

    def test_no_issue_number(self):
        name = build_branch_name(None, "Add dark mode")
        assert name.startswith("codepilot/manual-")
        assert "add-dark-mode" in name

    def test_truncates_long_title(self):
        name = build_branch_name(1, "a" * 100)
        assert len(name.split("/")[-1]) <= 60


class TestBuildCommitMessage:
    def test_conventional_format(self):
        msg = build_commit_message(
            42,
            "Fix division by zero",
            ["Added zero check", "Updated tests"],
            "Prevents crashes",
        )
        assert "fix(#42):" in msg
        assert "- Added zero check" in msg
        assert "Closes #42" in msg

    def test_manual_task_prefix(self):
        msg = build_commit_message(
            None,
            "Add dark mode",
            ["Added toggle"],
            "UX improvement",
            is_manual=True,
        )
        assert "chore(manual):" in msg
        assert "Closes" not in msg


class TestBuildPrBody:
    def test_includes_all_sections(self):
        body = build_pr_body(
            "Fix bug",
            "Calculator crashes",
            "Added zero check",
            ["src/calc.py", "tests/test_calc.py"],
            "3 passed, 0 failed",
            issue_number=42,
        )
        assert "## Issue" in body
        assert "Fix bug" in body
        assert "## Approach" in body
        assert "## Files Changed" in body
        assert "src/calc.py" in body
        assert "## Test Results" in body
        assert "3 passed" in body
        assert "Closes #42" in body


class TestGenerateManualTaskId:
    def test_returns_string_with_prefix(self):
        tid = generate_manual_task_id()
        assert tid.startswith("manual-")
        assert len(tid) > 7

    def test_unique(self):
        ids = {generate_manual_task_id() for _ in range(10)}
        assert len(ids) == 10
