"""Prototype retrieval components for the assistant."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from robot_assistant.config.defaults import RetrievalConfig


@dataclass
class Document:
    """Container for knowledge base entries."""

    doc_id: str
    content: str
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """Structured retrieval output with scoring breakdown."""

    document: Document
    score: float
    components: Dict[str, float]


class EmbeddingProvider:
    """Lightweight embedding generator (placeholder for provider-backed embeddings)."""

    def __init__(self, dimension: int = 64) -> None:
        self.dimension = dimension

    def embed(self, text: str) -> List[float]:
        """Produce a deterministic sparse embedding vector."""
        vector = [0.0] * self.dimension
        tokens = self._tokenize(text)
        for token, count in Counter(tokens).items():
            index = hash(token) % self.dimension
            vector[index] += float(count)
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [token.lower() for token in text.split() if token]


class InMemoryVectorStore:
    """Stores document embeddings in-process for experimentation."""

    def __init__(self, embedder: EmbeddingProvider) -> None:
        self.embedder = embedder
        self._docs: Dict[str, Document] = {}
        self._vectors: Dict[str, List[float]] = {}

    def add_documents(self, documents: Iterable[Document]) -> None:
        """Insert or replace documents in the vector store."""
        for doc in documents:
            self._docs[doc.doc_id] = doc
            self._vectors[doc.doc_id] = self.embedder.embed(doc.content)

    def similarity_search(self, query: str, top_k: int = 4) -> List[Tuple[Document, float]]:
        """Return the top_k documents based on cosine similarity."""
        query_vec = self.embedder.embed(query)
        scored: List[Tuple[Document, float]] = []
        for doc_id, vector in self._vectors.items():
            score = self._cosine_similarity(query_vec, vector)
            scored.append((self._docs[doc_id], score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        return sum(x * y for x, y in zip(a, b))


class KnowledgeRetriever:
    """Hybrid retriever combining lexical and dense similarity."""

    def __init__(self, store: InMemoryVectorStore, config: RetrievalConfig) -> None:
        self.store = store
        self.config = config

    def ingest(self, documents: Iterable[Document]) -> None:
        """Populate the knowledge base."""
        self.store.add_documents(documents)

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[RetrievalResult]:
        """Fetch documents ordered by combined lexical + vector score."""
        top_k = top_k or self.config.top_k
        dense_results = self.store.similarity_search(query, top_k * 3)
        query_tokens = Counter(self._tokenize(query))
        scored: List[RetrievalResult] = []

        for document, dense_score in dense_results:
            lexical_score = self._lexical_score(query_tokens, document.content)
            combined = (
                self.config.vector_weight * dense_score
                + self.config.lexical_weight * lexical_score
            )
            if combined < self.config.min_score:
                continue
            scored.append(
                RetrievalResult(
                    document=document,
                    score=combined,
                    components={"vector": dense_score, "lexical": lexical_score},
                )
            )

        scored.sort(key=lambda result: result.score, reverse=True)
        return scored[:top_k]

    @staticmethod
    def _lexical_score(query_tokens: Counter, content: str) -> float:
        doc_tokens = Counter(KnowledgeRetriever._tokenize(content))
        intersection = sum(min(query_tokens[token], doc_tokens.get(token, 0)) for token in query_tokens)
        union = sum(query_tokens.values()) + sum(doc_tokens.values()) - intersection
        if union == 0:
            return 0.0
        return intersection / union

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [token.lower() for token in text.split() if token]
