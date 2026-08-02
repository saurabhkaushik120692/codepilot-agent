"""Repo Map Builder — compressed tree of a repository's structure.

Produces a token-budgeted tree view with exported symbols for agents
to get a "bird's eye view" without loading every file.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import tiktoken

from codepilot.config import Config

logger = logging.getLogger(__name__)

IGNORED_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
    ".venv",
    "venv",
    "build",
    "dist",
    ".tox",
    ".eggs",
    "*.egg-info",
}

EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript React",
    ".jsx": "JavaScript React",
    ".html": "HTML",
    ".css": "CSS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".sh": "Shell",
    ".bat": "Batch",
    ".ps1": "PowerShell",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".cpp": "C++",
    ".c": "C",
    ".h": "C Header",
    ".rb": "Ruby",
    ".php": "PHP",
    ".sql": "SQL",
    ".graphql": "GraphQL",
    ".proto": "Protobuf",
    ".cfg": "Config",
    ".ini": "INI",
    ".env": "Environment",
    ".dockerfile": "Dockerfile",
    ".txt": "Text",
}


@dataclass
class FileEntry:
    """A single file entry in the repo map."""

    path: str
    language: str
    symbols: list[str]
    summary: str = ""


class RepoMapBuilder:
    """Builds a token-budgeted tree map of a repository.

    Walks the directory, extracts Python symbols via AST, and
    produces a compressed tree string within the configured
    token budget. Caches results to disk and invalidates
    when git diff detects changes.
    """

    def __init__(self, config: Config):
        self._config = config
        self._encoder: Any = None
        try:
            self._encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            logger.warning("tiktoken encoder not available, using char-based estimate")

    def build(self, repo_path: str) -> str:
        """Walk directory, extract symbols, build tree within token budget.

        Args:
            repo_path: Absolute or relative path to the repository root.

        Returns:
            A token-budgeted tree string representation.
        """
        cached = self._load_cached(repo_path)
        if cached is not None:
            logger.debug("Using cached repo map")
            return cached

        root = Path(repo_path).resolve()
        entries: list[FileEntry] = []
        self._walk(root, root, entries)

        tree = self._format_tree(entries)
        tree = self._truncate_to_budget(tree)
        self._save_cache(repo_path, tree)
        return tree

    def build_and_store(
        self, repo_path: str, write_file_fn: Callable[[str, str], None]
    ) -> str:
        """Build repo map and store via write_file_fn for subagent access.

        Args:
            repo_path: Path to the repository root.
            write_file_fn: Function to persist content (path, content).

        Returns:
            The repo map string.
        """
        repo_map = self.build(repo_path)
        write_file_fn("/.repo_map.json", json.dumps({"repo_map": repo_map}))
        return repo_map

    def _walk(self, root: Path, current: Path, entries: list[FileEntry]) -> None:
        """Recursively walk directories, collecting FileEntry objects."""
        try:
            items = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return

        for item in items:
            if item.is_dir():
                if item.name in IGNORED_DIRS or item.name.startswith("."):
                    continue
                self._walk(root, item, entries)
            elif item.is_file():
                rel_path = str(item.relative_to(root))
                lang = self._detect_language(item.name)
                symbols: list[str] = []
                if item.suffix == ".py":
                    try:
                        symbols = self._extract_symbols(str(item))
                    except Exception:
                        pass

                entries.append(FileEntry(path=rel_path, language=lang, symbols=symbols))

    def _detect_language(self, filename: str) -> str:
        """Detect language from filename extension."""
        suffix = Path(filename).suffix.lower()
        if suffix in EXTENSION_LANGUAGE_MAP:
            return EXTENSION_LANGUAGE_MAP[suffix]
        if filename.lower() == "dockerfile":
            return "Dockerfile"
        if filename.lower() in ("makefile",):
            return "Makefile"
        return "Unknown"

    def _extract_symbols(self, filepath: str) -> list[str]:
        """Extract exported symbols from a Python file using AST."""
        with open(filepath, encoding="utf-8") as f:
            source = f.read()
        try:
            tree = ast.parse(source, filename=filepath)
        except SyntaxError:
            return ["<parse error>"]

        symbols: list[str] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                symbols.append(f"def {node.name}")
            elif isinstance(node, ast.AsyncFunctionDef):
                symbols.append(f"async def {node.name}")
            elif isinstance(node, ast.ClassDef):
                methods = []
                for sub in ast.iter_child_nodes(node):
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append(sub.name)
                symbols.append(f"class {node.name}(methods: {methods})")
        return symbols

    def _format_tree(self, entries: list[FileEntry]) -> str:
        """Format entries into an indented tree string."""
        lines: list[str] = []
        by_dir: dict[str, list[FileEntry]] = {}
        for entry in entries:
            dirname = os.path.dirname(entry.path) or "."
            by_dir.setdefault(dirname, []).append(entry)

        for dirname in sorted(by_dir):
            if dirname == ".":
                lines.append(".")
            else:
                lines.append(f"{dirname}/")
            for entry in sorted(by_dir[dirname], key=lambda e: (not e.symbols, e.path)):
                line = f"  {os.path.basename(entry.path)} [{entry.language}]"
                if entry.symbols:
                    line += "  " + ", ".join(entry.symbols)
                lines.append(line)
        return "\n".join(lines)

    def _count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken or estimated chars/4."""
        if self._encoder:
            return len(self._encoder.encode(text))
        return len(text) // 4

    def _truncate_to_budget(self, tree: str) -> str:
        """Remove deepest lines until under the token budget."""
        budget = self._config.repo_map_token_budget
        lines = tree.split("\n")
        while self._count_tokens("\n".join(lines)) > budget and len(lines) > 1:
            max_indent_line = max(
                range(len(lines)),
                key=lambda i: (
                    len(lines[i]) - len(lines[i].lstrip()),
                    i,
                ),
            )
            lines.pop(max_indent_line)
        return "\n".join(lines)

    def _cache_path(self, repo_path: str) -> Path:
        """Get the cache file path for a given repo."""
        repo_hash = abs(hash(Path(repo_path).resolve()))
        cache_dir = Path.home() / ".codepilot" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / f"repo_map_{repo_hash}.json"

    def _load_cached(self, repo_path: str) -> str | None:
        """Load cached repo map from disk, return None if stale/missing."""
        cache_path = self._cache_path(repo_path)
        if not cache_path.exists():
            return None
        if not self._is_cache_valid(repo_path):
            logger.debug("Cache stale, rebuilding")
            return None
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            return data.get("repo_map", "")
        except Exception:
            return None

    def _save_cache(self, repo_path: str, repo_map: str) -> None:
        """Save repo map JSON to disk cache."""
        cache_path = self._cache_path(repo_path)
        cache_path.write_text(
            json.dumps({"repo_map": repo_map, "repo_path": repo_path}),
            encoding="utf-8",
        )

    def _is_cache_valid(self, repo_path: str) -> bool:
        """Check if cached repo map is still valid via git diff HEAD."""
        try:
            result = subprocess.run(
                ["git", "diff", "--stat", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            return not result.stdout.strip()
        except Exception:
            return True
