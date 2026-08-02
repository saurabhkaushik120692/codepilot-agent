"""PR Builder — pure functions for branch names, commit messages, and PR bodies.

No API calls — deterministic string construction only. Separated
from the PR Agent for testability and reuse.
"""

from __future__ import annotations

import re
import uuid


def build_branch_name(issue_number: int | None, title: str) -> str:
    """Generate a branch name from issue number and title.

    Rules:
    - Prefix with 'codepilot/'
    - Slug the title (lowercase, hyphens, max 50 chars)
    - Include issue number for GitHub issues
    - Use 'manual' prefix for manual tasks
    """
    slug = _slugify(title, max_length=50)
    if issue_number is not None:
        return f"codepilot/issue-{issue_number}-{slug}"
    return f"codepilot/manual-{slug}"


def build_commit_message(
    issue_number: int | None,
    summary: str,
    changes: list[str],
    reason: str,
    is_manual: bool = False,
) -> str:
    """Generate a conventional commit message.

    Format:
        fix(#42): one-line summary

        - change 1
        - change 2
        - why
        - Closes #42

    Manual tasks use chore(manual): prefix.
    """
    if is_manual or issue_number is None:
        prefix = f"chore(manual): {summary}"
    else:
        prefix = f"fix(#{issue_number}): {summary}"

    lines = [prefix, ""]
    for change in changes:
        lines.append(f"- {change}")
    lines.append(f"- {reason}")

    if issue_number is not None:
        lines.append(f"\nCloses #{issue_number}")

    return "\n".join(lines)


def build_pr_body(
    issue_title: str,
    issue_body: str,
    approach: str,
    files_changed: list[str],
    test_results: str,
    issue_number: int | None = None,
) -> str:
    """Generate a PR body with sections for approach, files, and tests.

    Sections:
    - Issue (with link back to original)
    - Approach
    - Files Changed
    - Test Results
    """
    sections = []

    sections.append("## Issue")
    sections.append(f"**{issue_title}**")
    if issue_body:
        sections.append(f"\n{issue_body}")

    if issue_number:
        sections.append(f"\nCloses #{issue_number}")

    sections.append("\n## Approach")
    sections.append(approach)

    sections.append("\n## Files Changed")
    for f in files_changed:
        sections.append(f"- `{f}`")

    sections.append("\n## Test Results")
    sections.append(test_results)

    return "\n".join(sections)


def generate_manual_task_id() -> str:
    """Generate a unique ID for manual tasks."""
    return f"manual-{uuid.uuid4().hex[:8]}"


def slugify(text: str, max_length: int = 50) -> str:
    """Convert text to a URL-safe slug."""
    slug = _slugify(text, max_length)
    return slug


def _slugify(text: str, max_length: int = 50) -> str:
    """Internal slugification helper."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug if slug else "task"
