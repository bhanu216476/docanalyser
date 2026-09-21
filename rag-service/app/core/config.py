import math
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    project_name: str = "DocAnalyser RAG Service"
    version: str = "1.0.0"

    # ------------------------------------------------------------------
    # Vector Store (Qdrant) Configuration
    # ------------------------------------------------------------------
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "documents"
    qdrant_vector_size: int = 1536  # Matches text-embedding-3-small
    qdrant_distance: str = "Cosine"
    qdrant_timeout: float = 10.0
    qdrant_batch_size: int = 64
    qdrant_max_retries: int = 3
    qdrant_retry_base_delay: float = 0.5

    # Redis URL (placeholder for future caching/celery)
    redis_url: str = "redis://localhost:6379"

    # ------------------------------------------------------------------
    # Embedding Service Configuration
    # ------------------------------------------------------------------
    # Name of the embedding model to use (must match provider's model identifier).
    # For OpenAI: "text-embedding-3-small" or "text-embedding-3-large".
    embedding_model: str = "text-embedding-3-small"

    # Number of chunks/texts to send per provider API call.
    # Must be > 0. Larger values reduce API round-trips but increase memory use.
    embedding_batch_size: int = 20

    # Maximum tokens per single text input.
    # MUST match the selected embedding model's token limit.
    # text-embedding-3-small: 8191
    # text-embedding-3-large: 8191
    # text-embedding-ada-002: 8191
    embedding_max_tokens: int = 8191

    # Maximum number of retry attempts for transient provider failures.
    # 0 means no retries. Permanent errors are never retried regardless.
    embedding_max_retries: int = 3

    # Base delay in seconds for exponential backoff between retry attempts.
    # Actual delay = base_delay * (2 ** attempt) + jitter.
    embedding_retry_base_delay: float = 1.0

    # OpenAI API credentials. Read from environment only — never logged.
    # Leave empty when using FakeEmbeddingProvider (testing / no credentials).
    openai_api_key: str = ""

    # ------------------------------------------------------------------
    # LLM Generation Configuration
    # ------------------------------------------------------------------
    # Override with LLM_MODEL in .env for deployments using another model.
    llm_model: str = "gpt-5.6-luna"
    llm_temperature: float = 0.2
    llm_max_input_tokens: int = 12000
    llm_max_output_tokens: int = 1500
    llm_timeout: float = 60.0
    llm_max_retries: int = 3
    llm_retry_base_delay: float = 1.0

    # ------------------------------------------------------------------
    # Dense Retrieval Configuration
    # ------------------------------------------------------------------
    # Default number of top-K chunks returned per retrieval request.
    # Can be overridden per-request via RetrievalRequest.top_k.
    retrieval_default_top_k: int = 10

    # Hard upper bound on top_k to prevent unbounded vector searches.
    # Requests with top_k > retrieval_max_top_k are rejected with a
    # validation error rather than silently clamped.
    retrieval_max_top_k: int = 100

    # ------------------------------------------------------------------
    # BM25 Lexical Retrieval Configuration
    # ------------------------------------------------------------------
    # Term-frequency saturation parameter (k1 >= 0.0, default 1.2).
    bm25_k1: float = 1.2

    # Document length normalization parameter (0.0 <= b <= 1.0, default 0.75).
    bm25_b: float = 0.75

    # Default number of top-K chunks returned per BM25 retrieval request.
    bm25_default_top_k: int = 10

    # Maximum allowed top-K for BM25 retrieval requests.
    bm25_max_top_k: int = 100

    # ------------------------------------------------------------------
    # Hybrid Retrieval (RRF) Configuration
    # ------------------------------------------------------------------
    # Ranking constant k for Reciprocal Rank Fusion (k > 0, default 60).
    rrf_k: int = 60

    # Default number of top-K chunks returned per hybrid retrieval request.
    hybrid_default_top_k: int = 10

    # Maximum allowed top-K for hybrid retrieval requests.
    hybrid_max_top_k: int = 100

    # Number of candidates to retrieve from dense retriever before fusion.
    hybrid_dense_top_k: int = 20

    # Number of candidates to retrieve from BM25 retriever before fusion.
    hybrid_bm25_top_k: int = 20

    # ------------------------------------------------------------------
    # Reranking Configuration
    # ------------------------------------------------------------------
    # Default number of top-K candidates to return after reranking.
    reranker_default_top_k: int = 5

    # Maximum allowed top-K for reranking requests.
    reranker_max_top_k: int = 50

    # Candidate and final limits used by the composable reranking pipeline.
    hybrid_candidate_top_k: int = 20
    hybrid_rrf_k: int = 60
    rerank_candidate_top_k: int = 20
    rerank_top_k: int = 5

    # ------------------------------------------------------------------
    # Context Builder Configuration
    # ------------------------------------------------------------------
    # Total token budget for LLM context assembly.
    context_token_budget: int = 2000

    # Optional hard cap on the number of evidence chunks selected.
    context_max_chunks: int = 10

    # Whether to include source metadata in the formatted evidence text.
    context_include_metadata: bool = True

    # Whether to include retrieval/reranker scores in the formatted evidence text.
    context_include_scores: bool = False

    # Policy when a candidate chunk exceeds the remaining token budget: 'skip' or 'truncate'.
    context_oversized_policy: str = "skip"

    # ------------------------------------------------------------------
    # Prompt Engineering Configuration
    # ------------------------------------------------------------------
    # Default prompt version to use for LLM context assembly.
    # Valid values: 'v1' (baseline), 'v2' (grounded+citation), 'v3' (structured).
    prompt_version: str = "v2"

    # ------------------------------------------------------------------
    # Citation Verification Configuration
    # ------------------------------------------------------------------
    # Master switch for the citation verification layer.
    # When False, verification is skipped and the raw answer is passed through.
    citation_verification_enabled: bool = True

    # Verification mode: 'rule_based', 'llm', or 'hybrid'.
    # rule_based : Deterministic checks only; no LLM call required.
    # llm        : Semantic LLM-based verification only.
    # hybrid     : Rule-based first; escalates to LLM for inconclusive cases.
    citation_verification_mode: str = "rule_based"

    # When True, raise a VerificationError if any claim is UNSUPPORTED.
    # For V0.1, keep False: flag claims and expose result without failing.
    citation_verification_fail_on_unsupported: bool = False

    # ------------------------------------------------------------------
    # Confidence Scoring Configuration
    # ------------------------------------------------------------------
    # Initial engineering weights for RAG confidence calculation.
    # Must sum to 1.0 and each weight must be >= 0.0.
    confidence_retrieval_weight: float = 0.20
    confidence_reranking_weight: float = 0.25
    confidence_citation_weight: float = 0.35
    confidence_answerability_weight: float = 0.20

    # Diagnostic score bands thresholds
    confidence_high_threshold: float = 0.80
    confidence_low_threshold: float = 0.50

    @field_validator("bm25_k1")
    @classmethod
    def validate_bm25_k1(cls, v: float) -> float:
        if v < 0.0:
            raise ValueError(f"bm25_k1 must be non-negative (got {v})")
        return v

    @field_validator("llm_model")
    @classmethod
    def validate_llm_model(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("llm_model must not be empty")
        return v.strip()

    @field_validator("llm_max_input_tokens", "llm_max_output_tokens")
    @classmethod
    def validate_llm_token_limits(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("LLM token limits must be greater than 0")
        return v

    @field_validator("llm_timeout")
    @classmethod
    def validate_llm_timeout(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("llm_timeout must be greater than 0")
        return v

    @field_validator("llm_max_retries")
    @classmethod
    def validate_llm_max_retries(cls, v: int) -> int:
        if v < 0:
            raise ValueError("llm_max_retries must be non-negative")
        return v

    @field_validator("llm_retry_base_delay")
    @classmethod
    def validate_llm_retry_base_delay(cls, v: float) -> float:
        if v < 0:
            raise ValueError("llm_retry_base_delay must be non-negative")
        return v

    @field_validator("bm25_b")
    @classmethod
    def validate_bm25_b(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"bm25_b must be between 0.0 and 1.0 inclusive (got {v})")
        return v

    @field_validator(
        "bm25_default_top_k",
        "bm25_max_top_k",
        "rrf_k",
        "hybrid_default_top_k",
        "hybrid_max_top_k",
        "hybrid_dense_top_k",
        "hybrid_bm25_top_k",
        "reranker_default_top_k",
        "reranker_max_top_k",
        "hybrid_candidate_top_k",
        "hybrid_rrf_k",
        "rerank_candidate_top_k",
        "rerank_top_k",
        "context_token_budget",
        "context_max_chunks",
    )
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"configuration bounds must be positive (got {v})")
        return v

    @field_validator("context_oversized_policy")
    @classmethod
    def validate_oversized_policy(cls, v: str) -> str:
        if v not in ("skip", "truncate"):
            raise ValueError(
                f"context_oversized_policy must be 'skip' or 'truncate', got '{v}'"
            )
        return v

    @field_validator("prompt_version")
    @classmethod
    def validate_prompt_version(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in ("v1", "v2", "v3"):
            raise ValueError(
                f"prompt_version must be one of 'v1', 'v2', 'v3', got '{v}'"
            )
        return normalized

    @field_validator("citation_verification_mode")
    @classmethod
    def validate_citation_verification_mode(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in ("rule_based", "llm", "hybrid"):
            raise ValueError(
                f"citation_verification_mode must be one of 'rule_based', 'llm', "
                f"'hybrid', got '{v}'"
            )
        return normalized

    @field_validator("llm_temperature")
    @classmethod
    def validate_llm_temperature(cls, v: float) -> float:
        if not (0.0 <= v <= 2.0):
            raise ValueError(
                f"llm_temperature must be between 0.0 and 2.0 inclusive (got {v})"
            )
        return v

    @field_validator(
        "confidence_retrieval_weight",
        "confidence_reranking_weight",
        "confidence_citation_weight",
        "confidence_answerability_weight",
    )
    @classmethod
    def validate_confidence_weights_non_negative(cls, v: float) -> float:
        if v < 0.0:
            raise ValueError(f"Confidence weights must be non-negative (got {v})")
        return v

    @field_validator("confidence_high_threshold", "confidence_low_threshold")
    @classmethod
    def validate_confidence_thresholds(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(
                f"Confidence threshold must be between 0.0 and 1.0 inclusive (got {v})"
            )
        return v

    @model_validator(mode="after")
    def validate_reranking_limits(self) -> "Settings":
        if self.rerank_top_k > self.rerank_candidate_top_k:
            raise ValueError(
                "rerank_top_k must be less than or equal to rerank_candidate_top_k"
            )
        if self.hybrid_candidate_top_k > (
            self.hybrid_dense_top_k + self.hybrid_bm25_top_k
        ):
            raise ValueError(
                "hybrid_candidate_top_k must be less than or equal to "
                "hybrid_dense_top_k + hybrid_bm25_top_k"
            )
        total_confidence_weight = (
            self.confidence_retrieval_weight
            + self.confidence_reranking_weight
            + self.confidence_citation_weight
            + self.confidence_answerability_weight
        )
        if not math.isclose(total_confidence_weight, 1.0, rel_tol=1e-5, abs_tol=1e-5):
            raise ValueError(
                f"Confidence weights must sum to 1.0, got {total_confidence_weight:.4f} "
                f"(retrieval={self.confidence_retrieval_weight}, "
                f"reranking={self.confidence_reranking_weight}, "
                f"citation={self.confidence_citation_weight}, "
                f"answerability={self.confidence_answerability_weight})"
            )
        if self.confidence_low_threshold > self.confidence_high_threshold:
            raise ValueError(
                f"confidence_low_threshold ({self.confidence_low_threshold}) cannot "
                f"exceed confidence_high_threshold ({self.confidence_high_threshold})"
            )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
