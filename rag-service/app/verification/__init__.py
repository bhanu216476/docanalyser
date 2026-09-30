"""
Citation Verification Package.

Provides structured verification of claims in LLM-generated answers against
the authoritative evidence chunks referenced by their citation IDs.

Pipeline:
    Generated Claim
          ↓
    Referenced Citation
          ↓
    Citation Registry
          ↓
    Source Chunk
          ↓
    Evidence Comparison
          ↓
    SUPPORTED / UNSUPPORTED / UNCERTAIN / UNCITED

This package is independent from retrieval. It only consumes the
authoritative CitationRegistry produced by the Context Builder.
"""

from app.verification.citation_verifier import CitationVerifier
from app.verification.claim_extractor import ClaimExtractor
from app.verification.evidence_verifier import (
    EvidenceVerifier,
    LLMEvidenceVerifier,
    MockEvidenceVerifier,
    SemanticVerificationOutcome,
)
from app.verification.models import (
    Claim,
    ClaimVerificationResult,
    VerificationMode,
    VerificationPolicy,
    VerificationResult,
    VerificationStatus,
)
from app.verification.rules import RuleBasedVerifier, RuleCheckOutcome

__all__ = [
    "CitationVerifier",
    # Models
    "Claim",
    # Core components
    "ClaimExtractor",
    "ClaimVerificationResult",
    # Evidence verifier abstraction + implementations
    "EvidenceVerifier",
    "LLMEvidenceVerifier",
    "MockEvidenceVerifier",
    "RuleBasedVerifier",
    "RuleCheckOutcome",
    "SemanticVerificationOutcome",
    "VerificationMode",
    "VerificationPolicy",
    "VerificationResult",
    "VerificationStatus",
]
