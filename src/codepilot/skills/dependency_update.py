"""Dependency Update Skill — workflow for updating dependencies."""

from codepilot.skills.base import Skill, SkillContext


class DependencyUpdateSkill(Skill):
    name = "dependency_update"
    description = "Update a project dependency to a new version"

    example_prompts = [
        "Update requests from 2.28 to 2.31",
        "Bump numpy to latest stable version",
        "Upgrade fastapi to 0.110+",
    ]

    forbidden_actions = [
        "Updating unrelated dependencies",
        "Removing existing dependency version pins without approval",
        "Pushing directly to main without CI checks",
    ]

    def get_system_prompt(self, context: SkillContext) -> str:
        return f"""You are updating a project dependency.

DEPENDENCY: {context.issue_title}
DETAILS: {context.issue_body}
FILES: {", ".join(context.relevant_files)}

Workflow (CRITICAL — follow these steps in order):

{chr(10).join(self.get_workflow_steps())}

IMPORTANT RULES:
- Read the changelog of the new version before updating
- Check for breaking changes in the changelog
- Update ONLY the specified dependency
- Run the full test suite — dependency updates can break anything
- If tests fail, analyze and adjust"""

    def get_workflow_steps(self) -> list[str]:
        return [
            "1. Read the current dependency specification",
            "2. Check the changelog for the new version",
            "3. Update the version in the config file",
            "4. Install the new version",
            "5. Run the full test suite",
            "6. Fix any compatibility issues discovered",
        ]

    def get_checklist_template(self, context: SkillContext) -> list[str]:
        return [
            "Changelog reviewed",
            "Version updated",
            "Dependency installed",
            "Full test suite passes",
        ]
