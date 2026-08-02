"""Feature Addition Skill — workflow for adding new features."""

from codepilot.skills.base import Skill, SkillContext


class FeatureAdditionSkill(Skill):
    name = "feature_addition"
    description = "Add a new feature to the codebase"

    example_prompts = [
        "Add a modulo operation to the calculator",
        "Implement pagination for the user list endpoint",
        "Add dark mode toggle to the settings page",
    ]

    forbidden_actions = [
        "Breaking existing public APIs without migration path",
        "Adding features without corresponding tests",
        "Modifying unrelated subsystems",
        "Introducing new dependencies without explicit authorization",
    ]

    def get_system_prompt(self, context: SkillContext) -> str:
        return f"""You are implementing a new feature for the codebase.

FEATURE: {context.issue_title}
DETAILS: {context.issue_body}
FILES: {", ".join(context.relevant_files)}

Workflow (CRITICAL — follow these steps in order):

{chr(10).join(self.get_workflow_steps())}

IMPORTANT RULES:
- Design the API surface BEFORE implementing
- Write new unit tests for the feature
- Ensure backward compatibility with existing code
- Add documentation (docstrings) for all public functions
- Run the existing test suite to verify no regressions"""

    def get_workflow_steps(self) -> list[str]:
        return [
            "1. Read the relevant files and understand the codebase",
            "2. Design the API surface (function signatures, classes)",
            "3. Implement the core logic",
            "4. Add comprehensive unit tests",
            "5. Add documentation (docstrings)",
            "6. Run the full test suite",
        ]

    def get_checklist_template(self, context: SkillContext) -> list[str]:
        return [
            "Design reviewed",
            "Core logic implemented",
            "Unit tests added",
            "Documentation written",
            "All tests pass",
        ]
