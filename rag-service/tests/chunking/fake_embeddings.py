"""Deterministic fake embedding model for offline testing and benchmarking."""

import hashlib
import numpy as np
from langchain_core.embeddings import Embeddings


class FakeEmbeddings(Embeddings):
    """Deterministic, zero-network mock embedding model for testing.

    Maps text content to 16-dimensional normalized vectors. Known topic keywords
    (e.g., 'introduction', 'background', 'methodology', 'experiment', 'results')
    map to distinct topic vectors, ensuring high similarity within topics and low
    similarity across topic transitions.
    """

    def __init__(self, vector_dim: int = 16):
        self.vector_dim = vector_dim
        self.embed_call_count: int = 0
        self.topic_vectors = {
            "intro": self._normalize([1.0 if i == 0 else 0.0 for i in range(self.vector_dim)]),
            "background": self._normalize([1.0 if i == 1 else 0.0 for i in range(self.vector_dim)]),
            "related": self._normalize([1.0 if i == 2 else 0.0 for i in range(self.vector_dim)]),
            "method": self._normalize([1.0 if i == 3 else 0.0 for i in range(self.vector_dim)]),
            "experiment": self._normalize([1.0 if i == 4 else 0.0 for i in range(self.vector_dim)]),
            "result": self._normalize([1.0 if i == 5 else 0.0 for i in range(self.vector_dim)]),
            "discussion": self._normalize([1.0 if i == 6 else 0.0 for i in range(self.vector_dim)]),
            "conclusion": self._normalize([1.0 if i == 7 else 0.0 for i in range(self.vector_dim)]),
        }

    def _normalize(self, vec: list[float]) -> list[float]:
        arr = np.array(vec, dtype=float)
        norm = np.linalg.norm(arr)
        if norm == 0:
            return vec
        return (arr / norm).tolist()

    def _text_to_vector(self, text: str) -> list[float]:
        text_lower = text.lower()
        base_vec = None

        for topic, t_vec in self.topic_vectors.items():
            if topic in text_lower:
                base_vec = np.array(t_vec, dtype=float)
                break

        if base_vec is None:
            # Deterministic hash-based vector
            hash_bytes = hashlib.md5(text.encode("utf-8")).digest()
            raw_floats = [float(b % 100) / 100.0 for b in hash_bytes[:self.vector_dim]]
            if len(raw_floats) < self.vector_dim:
                raw_floats.extend([0.1] * (self.vector_dim - len(raw_floats)))
            base_vec = np.array(raw_floats, dtype=float)

        # Add small deterministic jitter based on text length to preserve topic closeness
        jitter = (len(text) % 10) * 0.01
        vec = base_vec + jitter
        return self._normalize(vec.tolist())

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of document strings deterministically."""
        self.embed_call_count += 1
        return [self._text_to_vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string deterministically."""
        self.embed_call_count += 1
        return self._text_to_vector(text)
