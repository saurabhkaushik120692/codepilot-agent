"""CodePilot configuration — loaded from .env and environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application settings.

    Values are loaded from environment variables and .env file.
    Each field name maps to an env var (case-insensitive).
    For example: `primary_llm` ← env var `PRIMARY_LLM`
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- LLM ---
    primary_llm: str = "google:gemini-1.5-pro"
    fallback_llms: str = (
        "groq:llama-3.2-90b-text-preview,"
        "anthropic:claude-sonnet-4-20250514"
    )

    # --- API Keys ---
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    groq_api_key: str = ""

    # --- GitHub ---
    github_app_id: str = ""
    github_app_private_key_path: str = ""
    github_repository: str = "codepilot-test-repo"

    # --- Polling ---
    poll_interval_minutes: int = 5

    # --- Context ---
    repo_map_token_budget: int = 4000
    max_relevant_files: int = 10

    # --- Agent ---
    max_coder_retries: int = 3
    complexity_threshold: int = 7

    # --- Summarization ---
    auto_summarization_enabled: bool = True
    summarization_threshold: int = 20

    # --- Storage ---
    sandbox_base_dir: str = "~/.codepilot/sandboxes/"
    chromadb_persist_dir: str = "~/.codepilot/data/chromadb/"

    # --- Bonus: Sandbox Provider ---
    sandbox_provider: str = "local"

    # --- Bonus: LangSmith ---
    langsmith_enabled: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "codepilot"

    # --- Bonus: ACP ---
    acp_enabled: bool = False
    acp_port: int = 8420

    # --- Helpers ---
    @property
    def primary_provider(self) -> str:
        """Extract provider name from primary_llm (e.g., 'anthropic')."""
        return self.primary_llm.split(":")[0]

    @property
    def primary_model(self) -> str:
        """Extract model name from primary_llm (e.g., 'claude-sonnet-4-20250514')."""
        return self.primary_llm.split(":")[1]

    @property
    def fallback_chain(self) -> list[tuple[str, str]]:
        """Parse fallback_llms into a list of (provider, model) tuples."""
        return [
            (entry.split(":")[0], entry.split(":")[1])
            for entry in self.fallback_llms.split(",")
        ]
