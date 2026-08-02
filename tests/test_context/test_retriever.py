"""Tests for the File Retriever."""

from unittest.mock import patch

import pytest

from codepilot.config import Config
from codepilot.context.retriever import (
    EmbeddingRetriever,
    FileRetriever,
    KeywordRetriever,
)


@pytest.fixture
def config():
    return Config(
        _env_file=None,
        max_relevant_files=10,
    )


@pytest.fixture
def sample_repo_map():
    return (
        "src/\n"
        "  main.py [Python]  def greet, class Greeter\n"
        "  utils.py [Python]  def helper\n"
        "tests/\n"
        "  test_main.py [Python]  def test_greet\n"
        "  test_utils.py [Python]  def test_helper\n"
        "README.md [Markdown]\n"
        "config.json [JSON]\n"
    )


class TestKeywordRetriever:
    """Test keyword-based retrieval."""

    def test_retrieve_returns_relevant_files(self, sample_repo_map):
        r = KeywordRetriever()
        results = r.retrieve("greet function", sample_repo_map, top_k=5)
        assert len(results) > 0
        assert "main.py" in results

    def test_retrieve_no_match_returns_empty(self, sample_repo_map):
        r = KeywordRetriever()
        results = r.retrieve("xyzzy_nonexistent", sample_repo_map, top_k=5)
        assert results == []

    def test_retrieve_respects_top_k(self, sample_repo_map):
        r = KeywordRetriever()
        results = r.retrieve("test helper greet", sample_repo_map, top_k=2)
        assert len(results) <= 2

    def test_empty_query(self, sample_repo_map):
        r = KeywordRetriever()
        results = r.retrieve("", sample_repo_map)
        assert results == []


class TestEmbeddingRetriever:
    """Test embedding-based retrieval with ChromaDB."""

    def test_index_and_retrieve(self, tmp_path):
        chroma_dir = str(tmp_path / "chroma")
        r = EmbeddingRetriever(persist_dir=chroma_dir)

        mock_collection = patch.object(
            r, "_get_collection"
        ).start()
        mock_collection.return_value.query.return_value = {
            "metadatas": [[{"filepath": "test.py"}]],
        }

        test_file = tmp_path / "test.py"
        test_file.write_text("def calculate_tax(amount):\n    return amount * 0.1\n")
        r.index_files([str(test_file)])

        results = r.retrieve("tax calculation", top_k=3)
        assert len(results) > 0
        assert "test.py" in results

        patch.stopall()

    def test_chunk_text(self, tmp_path):
        chroma_dir = str(tmp_path / "chroma")
        r = EmbeddingRetriever(persist_dir=chroma_dir)
        long_text = "word " * 1000
        chunks = r._chunk_text(long_text, chunk_size=200)
        assert len(chunks) > 1
        assert all(len(c) > 0 for c in chunks)


class TestFileRetriever:
    """Test the unified FileRetriever facade."""

    def test_small_repo_uses_keyword(self, config, sample_repo_map):
        r = FileRetriever(config)
        results = r.retrieve("greet", sample_repo_map, repo_path="/tmp/test")
        assert len(results) > 0

    def test_large_repo_uses_embedding(self, config, tmp_path):
        r = FileRetriever(config)
        test_file = tmp_path / "calc.py"
        test_file.write_text("def add(a, b):\n    return a + b\n")
        big_list = [str(test_file)] * FileRetriever.SMALL_REPO_THRESHOLD + [
            str(tmp_path / f"extra_{i}.py") for i in range(10)
        ]

        with patch.object(
            EmbeddingRetriever, "index_files", return_value=None
        ), patch.object(
            EmbeddingRetriever,
            "retrieve",
            return_value=["calc.py"],
        ):
            results = r.retrieve(
                "addition", sample_repo_map, repo_path=str(tmp_path),
                file_paths=big_list
            )
            assert "calc.py" in results
