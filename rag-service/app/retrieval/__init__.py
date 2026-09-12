"""Dense retrieval over embedded chunks."""

from app.retrieval.models import RetrievalResult
from app.retrieval.service import DenseRetrievalService
from app.retrieval.similarity import cosine_similarity

__all__ = ["DenseRetrievalService", "RetrievalResult", "cosine_similarity"]
