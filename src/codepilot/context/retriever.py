"""File Retriever — keyword matching and embedding search.

Two strategies for finding relevant files:
1. KeywordRetriever — fast TF-based matching against repo map summaries
2. EmbeddingRetriever — ChromaDB-backed semantic search over file chunks

The FileRetriever facade picks the appropriate strategy based on
config/repo size.
"""

from __future__ import annotations

import logging
import re

from codepilot.config import Config

logger = logging.getLogger(__name__)


class KeywordRetriever:
    """Fast keyword-based file retrieval from repo map text.

    Uses simple term frequency matching — no external NLP library.
    """

    def retrieve(self, query: str, repo_map: str, top_k: int = 10) -> list[str]:
        """Find relevant file paths via keyword matching.

        Args:
            query: The task description or search query.
            repo_map: The repo map tree string from RepoMapBuilder.
            top_k: Maximum number of results to return.

        Returns:
            List of file paths sorted by relevance score descending.
        """
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        file_lines = self._extract_file_lines(repo_map)
        scores: list[tuple[str, float]] = []

        for line in file_lines:
            path = self._extract_path(line)
            if not path:
                continue
            terms = self._tokenize(line)
            score = sum(1 for qt in query_terms for t in terms if qt in t)
            if score > 0:
                scores.append((path, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [path for path, _ in scores[:top_k]]

    def _tokenize(self, text: str) -> list[str]:
        """Lowercase, split on non-alphanumeric, filter short tokens."""
        tokens = re.findall(r"[a-zA-Z_]\w+", text.lower())
        return [t for t in tokens if len(t) > 1]

    def _extract_file_lines(self, repo_map: str) -> list[str]:
        """Extract lines containing file entries from repo map text."""
        lines = repo_map.split("\n")
        return [ln for ln in lines if "[" in ln and "]" in ln]

    def _extract_path(self, line: str) -> str:
        """Extract the file path from a repo map line."""
        match = re.match(r"^\s*(.+?)\s*\[", line)
        if match:
            return match.group(1).strip()
        return ""


class EmbeddingRetriever:
    """ChromaDB-backed semantic search over file chunks.

    Uses ChromaDB for vector storage and cosine similarity search.
    Files are chunked at 500-token boundaries with overlap.
    """

    def __init__(self, persist_dir: str):
        self._persist_dir = persist_dir
        self._collection: object | None = None

    def _get_collection(self) -> object:
        """Lazy-init the ChromaDB collection."""
        if self._collection is not None:
            return self._collection

        import chromadb

        client = chromadb.PersistentClient(path=self._persist_dir)
        try:
            self._collection = client.get_collection("repo_files")
        except Exception:
            self._collection = client.create_collection("repo_files")
        return self._collection

    def index_files(self, files: list[str]) -> None:
        """Chunk files and add to ChromaDB collection.

        Args:
            files: List of file paths to index.
        """
        collection = self._get_collection()
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for filepath in files:
            try:
                with open(filepath, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            chunks = self._chunk_text(content)
            for i, chunk in enumerate(chunks):
                chunk_id = f"{filepath}:{i}"
                ids.append(chunk_id)
                documents.append(chunk)
                metadatas.append({"filepath": filepath, "chunk_index": i})

        if ids:
            collection.add(ids=ids, documents=documents, metadatas=metadatas)
            logger.info(f"Indexed {len(ids)} chunks from {len(files)} files")

    def retrieve(self, query: str, top_k: int = 10) -> list[str]:
        """Embed query, perform cosine similarity search, return file paths.

        Args:
            query: The search query or task description.
            top_k: Maximum number of results to return.

        Returns:
            List of unique file paths sorted by relevance.
        """
        collection = self._get_collection()
        results = collection.query(query_texts=[query], n_results=top_k)

        seen: set[str] = set()
        paths: list[str] = []
        for metadata in results.get("metadatas", [[]])[0]:
            filepath = metadata.get("filepath", "")
            if filepath and filepath not in seen:
                seen.add(filepath)
                paths.append(filepath)
        return paths

    def _chunk_text(self, text: str, chunk_size: int = 500) -> list[str]:
        """Split text into chunks of roughly chunk_size words with overlap."""
        words = text.split()
        if not words:
            return [text]

        chunks: list[str] = []
        step = max(1, chunk_size // 2)  # 50% overlap
        for i in range(0, len(words), step):
            chunk = " ".join(words[i : i + chunk_size])
            if chunk:
                chunks.append(chunk)
        return chunks


class FileRetriever:
    """Unified interface that picks keyword or embedding strategy.

    For small repos (< 50 files), uses fast keyword matching.
    For larger repos, uses ChromaDB embedding search for better
    semantic understanding.
    """

    SMALL_REPO_THRESHOLD = 50

    def __init__(self, config: Config):
        self._config = config
        self._keyword = KeywordRetriever()
        self._embedding: EmbeddingRetriever | None = None

    def retrieve(
        self,
        query: str,
        repo_map: str,
        repo_path: str,
        file_paths: list[str] | None = None,
    ) -> list[str]:
        """Retrieve relevant files using appropriate strategy.

        Args:
            query: The task description or search query.
            repo_map: The repo map tree string.
            repo_path: Path to the repository root.
            file_paths: Optional list of full file paths for embedding search.

        Returns:
            List of relevant file paths (capped at max_relevant_files).
        """
        if file_paths and len(file_paths) > self.SMALL_REPO_THRESHOLD:
            return self._embedding_retrieve(query, file_paths)
        else:
            return self._keyword_retrieve(query, repo_map)

    def _keyword_retrieve(self, query: str, repo_map: str) -> list[str]:
        return self._keyword.retrieve(query, repo_map, self._config.max_relevant_files)

    def _embedding_retrieve(self, query: str, files: list[str]) -> list[str]:
        if self._embedding is None:
            self._embedding = EmbeddingRetriever(self._config.chromadb_persist_dir)
        self._embedding.index_files(files)
        return self._embedding.retrieve(query, self._config.max_relevant_files)
