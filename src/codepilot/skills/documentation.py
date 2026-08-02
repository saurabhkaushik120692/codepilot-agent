"""Documentation Skill — workflow for writing documentation."""

from codepilot.skills.base import Skill, SkillContext


class DocumentationSkill(Skill):
    name = "documentation"
    description = "Add or improve project documentation"

    example_prompts = [
        "Add docstrings to all public functions in the utils module",
        "Write API documentation for the v2 endpoints",
        "Update the README with the new installation instructions",
    ]

    forbidden_actions = [
        "Modifying source code logic",
        "Changing function signatures",
        "Altering configuration files",
    ]

    def get_system_prompt(self, context: SkillContext) -> str:
        return f"""You are improving project documentation.

TASK: {context.issue_title}
DETAILS: {context.issue_body}
FILES: {", ".join(context.relevant_files)}

Workflow (CRITICAL — follow these steps in order):

{chr(10).join(self.get_workflow_steps())}

IMPORTANT RULES:
- Only modify documentation — never change code logic
- Use the project's existing documentation style
- Verify docstrings render correctly (e.g., with pydoc)
- Ensure all public APIs are documented
- Format READMEs and markdown files consistently"""

    def get_workflow_steps(self) -> list[str]:
        return [
            "1. Identify all undocumented public functions and classes",
            "2. Write clear, concise docstrings for each",
            "3. Ensure docstrings follow project conventions",
            "4. Update any affected README or markdown files",
            "5. Verify documentation renders correctly",
        ]

    def get_checklist_template(self, context: SkillContext) -> list[str]:
        return [
            "Undocumented items identified",
            "Docstrings written",
            "Style conventions followed",
            "Documentation verified",
        ]
