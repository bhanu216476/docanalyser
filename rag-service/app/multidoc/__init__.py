"""
Multi-Document Intelligence Package for DocAnalyser RAG Platform.
"""

from app.multidoc.models import (
    ComparisonDifference,
    DocumentConflict,
    MultiDocComparisonRequest,
    MultiDocComparisonResponse,
)
from app.multidoc.service import MultiDocumentIntelligenceService

__all__ = [
    "ComparisonDifference",
    "DocumentConflict",
    "MultiDocComparisonRequest",
    "MultiDocComparisonResponse",
    "MultiDocumentIntelligenceService",
]
