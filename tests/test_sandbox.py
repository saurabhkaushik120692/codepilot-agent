"""Tests for the Sandbox Manager."""

from pathlib import Path

import pytest

from codepilot.config import Config
from codepilot.sandbox.manager import SandboxConfig, SandboxManager


@pytest.fixture
def config():
    return Config(
        _env_file=None,
        sandbox_base_dir="~/.codepilot/sandboxes/",
    )


@pytest.fixture
def sandbox_config(tmp_path):
    return SandboxConfig(
        base_dir=str(tmp_path / "sandboxes"),
        issue_id=42,
        relevant_files=["src/main.py", "README.md"],
    )


@pytest.fixture
def test_repo(tmp_path):
    """Create a small test repo with files."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("def greet():\n    return 'hello'\n")
    (tmp_path / "README.md").write_text("# Test Project\n")
    return tmp_path


class TestSandboxManager:
    """Test sandbox creation, execution, diff, and cleanup."""

    def test_create_copies_relevant_files(self, config, sandbox_config, test_repo):
        mgr = SandboxManager(config)
        sandbox_path = mgr.create(sandbox_config, str(test_repo))

        assert Path(sandbox_path).exists()
        assert (Path(sandbox_path) / "src" / "main.py").exists()
        assert (Path(sandbox_path) / "README.md").exists()

    def test_create_skips_missing_files(self, config, tmp_path, test_repo):
        sc = SandboxConfig(
            base_dir=str(tmp_path / "sandboxes"),
            issue_id=99,
            relevant_files=["nonexistent.py"],
        )
        mgr = SandboxManager(config)
        sandbox_path = mgr.create(sc, str(test_repo))
        assert not (Path(sandbox_path) / "nonexistent.py").exists()

    @pytest.mark.asyncio
    async def test_execute_command(self, config, sandbox_config, test_repo):
        mgr = SandboxManager(config)
        sandbox_path = mgr.create(sandbox_config, str(test_repo))

        output, exit_code = await mgr.execute(sandbox_path, "echo hello")
        assert exit_code == 0
        assert "hello" in output

    def test_diff_shows_changes(self, config, sandbox_config, test_repo):
        mgr = SandboxManager(config)
        sandbox_path = mgr.create(sandbox_config, str(test_repo))

        (Path(sandbox_path) / "src" / "main.py").write_text(
            "def greet():\n    return 'hi'\n"
        )

        diff = mgr.get_diff(sandbox_path, str(test_repo))
        diff_normalized = diff.replace("\\", "/")
        assert "def greet" in diff or "+" in diff or "-" in diff
        assert "src/main.py" in diff_normalized

    def test_diff_no_changes(self, config, sandbox_config, test_repo):
        mgr = SandboxManager(config)
        sandbox_path = mgr.create(sandbox_config, str(test_repo))

        diff = mgr.get_diff(sandbox_path, str(test_repo))
        assert diff == "" or all(len(line) == 0 for line in diff.split("\n"))

    def test_cleanup_removes_sandbox(self, config, sandbox_config, test_repo):
        mgr = SandboxManager(config)
        sandbox_path = mgr.create(sandbox_config, str(test_repo))
        assert Path(sandbox_path).exists()

        mgr.cleanup(sandbox_path)
        assert not Path(sandbox_path).exists()

    def test_sandbox_changes_dont_affect_original(
        self, config, sandbox_config, test_repo
    ):
        mgr = SandboxManager(config)
        sandbox_path = mgr.create(sandbox_config, str(test_repo))

        (Path(sandbox_path) / "src" / "main.py").write_text("CHANGED\n")

        orig_content = (test_repo / "src" / "main.py").read_text()
        assert orig_content == "def greet():\n    return 'hello'\n"
