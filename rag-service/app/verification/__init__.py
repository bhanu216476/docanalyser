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

from app.verification.models import (
    Claim,
    ClaimVerificationResult,
    VerificationResult,
    VerificationStatus,
    VerificationMode,
    VerificationPolicy,
)
from app.verification.claim_extractor import ClaimExtractor
from app.verification.citation_verifier import CitationVerifier
from app.verification.rules import RuleBasedVerifier, RuleCheckOutcome
from app.verification.evidence_verifier import (
    EvidenceVerifier,
    MockEvidenceVerifier,
    LLMEvidenceVerifier,
    SemanticVerificationOutcome,
)

__all__ = [
    # Models
    "Claim",
    "ClaimVerificationResult",
    "VerificationResult",
    "VerificationStatus",
    "VerificationMode",
    "VerificationPolicy",
    # Core components
    "ClaimExtractor",
    "CitationVerifier",
    "RuleBasedVerifier",
    "RuleCheckOutcome",
    # Evidence verifier abstraction + implementations
    "EvidenceVerifier",
    "MockEvidenceVerifier",
    "LLMEvidenceVerifier",
    "SemanticVerificationOutcome",
]

