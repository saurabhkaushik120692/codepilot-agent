"""Config Change Skill — workflow for configuration fixes."""

from codepilot.skills.base import Skill, SkillContext


class ConfigChangeSkill(Skill):
    name = "config_change"
    description = "Fix a configuration issue"

    example_prompts = [
        "Fix the typo in the database connection string in config.py",
        "Update the log level from WARN to INFO in settings.yaml",
        "Add the new API endpoint to the allowed origins list",
    ]

    forbidden_actions = [
        "Modifying production credentials or secrets",
        "Changing config validation logic",
        "Removing existing config options without approval",
        "Exposing secrets in logs or output",
    ]

    def get_system_prompt(self, context: SkillContext) -> str:
        return f"""You are fixing a configuration issue.

ISSUE: {context.issue_title}
DETAILS: {context.issue_body}
FILES: {", ".join(context.relevant_files)}

Workflow (CRITICAL — follow these steps in order):

{chr(10).join(self.get_workflow_steps())}

IMPORTANT RULES:
- Never modify credentials, secrets, or validation logic
- Validate config syntax before applying
- Make the minimal change — avoid sweeping config rewrites
- Verify the application starts/behaves correctly after the change
- Never expose credentials or secrets in any output"""

    def get_workflow_steps(self) -> list[str]:
        return [
            "1. Identify the config file(s) mentioned in the issue",
            "2. Read the current configuration",
            "3. Validate the proposed change (syntax, values)",
            "4. Apply the minimal config change",
            "5. Verify the application starts/behaves correctly",
            "6. Ensure no existing functionality is broken",
        ]

    def get_checklist_template(self, context: SkillContext) -> list[str]:
        return [
            "Config file(s) identified",
            "Current values understood",
            "Change validated for syntax",
            "Config updated",
            "Application verified",
        ]
