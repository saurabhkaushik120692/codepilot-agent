"""Bug Fix Skill — workflow for fixing reported bugs."""

from codepilot.skills.base import Skill, SkillContext


class BugFixSkill(Skill):
    name = "bug_fix"
    description = "Fix a reported bug in the codebase"

    example_prompts = [
        "Fix the division by zero error in the calculate() function",
        "The login endpoint returns 500 when password is empty",
        "Memory leak in the file watcher on large directories",
    ]

    forbidden_actions = [
        "Modifying test infrastructure without approval",
        "Skipping existing tests",
        "Changing public API signatures",
        "Introducing new dependencies without explicit authorization",
    ]

    def get_system_prompt(self, context: SkillContext) -> str:
        previous = ""
        if context.previous_attempts:
            previous = "\nPrevious attempts that failed:\n" + "\n".join(
                f"- {a}" for a in context.previous_attempts
            )

        return f"""You are fixing a bug reported in the codebase.

BUG: {context.issue_title}
DETAILS: {context.issue_body}
FILES: {", ".join(context.relevant_files)}
{previous}

Workflow (CRITICAL — follow these steps in order):

{chr(10).join(self.get_workflow_steps())}

IMPORTANT RULES:
- Always write a reproducer or failing test first
- Make the MINIMAL fix — avoid refactoring unrelated code
- Run the full test suite after your fix
- If tests fail, analyze the failure before retrying
- Never skip existing tests; never modify test infrastructure"""

    def get_workflow_steps(self) -> list[str]:
        return [
            "1. Read the relevant files to understand the code",
            "2. Reproduce the bug (write a failing test if possible)",
            "3. Identify the root cause",
            "4. Implement the minimal fix",
            "5. Run tests to verify the fix",
            "6. Ensure no regressions by running full test suite",
        ]

    def get_checklist_template(self, context: SkillContext) -> list[str]:
        return [
            f"Reproduce: {context.issue_title}",
            "Root cause identified",
            "Fix implemented",
            "Regression test added",
            "All existing tests pass",
        ]
