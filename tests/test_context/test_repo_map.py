"""Tests for the Repo Map Builder."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import tiktoken

from codepilot.config import Config
from codepilot.context.repo_map import FileEntry, RepoMapBuilder


@pytest.fixture
def config():
    return Config(
        _env_file=None,
        repo_map_token_budget=4000,
    )


@pytest.fixture
def test_repo(tmp_path):
    """Create a small test repo with Python and non-Python files."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text(
        "import os\n\ndef greet(name):\n    return f'Hello, {name}'\n\n"
        "class Greeter:\n    def say_hi(self):\n        return 'hi'\n"
    )
    (src_dir / "utils.py").write_text("def helper():\n    return True\n")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text("def test_greet():\n    pass\n")
    (tmp_path / "README.md").write_text("# Test Project\n")
    (tmp_path / "package.json").write_text('{"name": "test"}')
    return str(tmp_path)


class TestRepoMapBuilder:
    """Test the repo map builder."""

    def test_build_produces_tree_string(self, config, test_repo):
        builder = RepoMapBuilder(config)
        tree = builder.build(test_repo)
        assert isinstance(tree, str)
        assert len(tree) > 0
        assert "main.py" in tree
        assert "utils.py" in tree
        assert "src/" in tree

    def test_token_budget_respected(self, config, test_repo):
        config.repo_map_token_budget = 100
        builder = RepoMapBuilder(config)
        tree = builder.build(test_repo)
        encoder = tiktoken.get_encoding("cl100k_base")
        tokens = len(encoder.encode(tree))
        assert tokens <= 100

    def test_python_symbols_extracted(self, config, test_repo):
        builder = RepoMapBuilder(config)
        tree = builder.build(test_repo)
        assert "def greet" in tree
        assert "class Greeter" in tree

    def test_non_python_files_get_language_detection(self, config, test_repo):
        builder = RepoMapBuilder(config)
        tree = builder.build(test_repo)
        assert "[Markdown]" in tree
        assert "README.md" in tree

    def test_ignored_directories_excluded(self, config, test_repo):
        git_dir = Path(test_repo) / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("dummy")
        cache_dir = Path(test_repo) / "__pycache__"
        cache_dir.mkdir()

        builder = RepoMapBuilder(config)
        tree = builder.build(test_repo)
        assert "config" not in tree
        assert "__pycache__" not in tree

    def test_cache_loads_and_saves(self, config, test_repo):
        builder = RepoMapBuilder(config)
        tree1 = builder.build(test_repo)
        tree2 = builder.build(test_repo)
        assert tree1 == tree2

    @patch.object(RepoMapBuilder, "_is_cache_valid", return_value=False)
    def test_stale_cache_skips(self, mock_valid, config, test_repo):
        builder = RepoMapBuilder(config)
        tree = builder.build(test_repo)
        assert isinstance(tree, str)

    def test_build_and_store(self, config, test_repo):
        builder = RepoMapBuilder(config)
        stored = {}

        def write_fn(path, content):
            stored[path] = content

        tree = builder.build_and_store(test_repo, write_fn)
        assert "/.repo_map.json" in stored
        data = json.loads(stored["/.repo_map.json"])
        assert "repo_map" in data
        assert data["repo_map"] == tree

    def test_symbol_extraction_handles_syntax_error(self, config, tmp_path):
        (tmp_path / "bad.py").write_text("def broken(:\n    pass\n")
        builder = RepoMapBuilder(config)
        tree = builder.build(str(tmp_path))
        assert "<parse error>" in tree

    def test_empty_directory(self, config, tmp_path):
        builder = RepoMapBuilder(config)
        tree = builder.build(str(tmp_path))
        assert tree == ""


class TestFileEntry:
    """Test the FileEntry dataclass."""

    def test_defaults(self):
        entry = FileEntry(path="src/main.py", language="Python", symbols=["def greet"])
        assert entry.path == "src/main.py"
        assert entry.summary == ""
