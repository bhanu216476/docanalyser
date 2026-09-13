from pydantic import field_validator
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

    @field_validator("bm25_k1")
    @classmethod
    def validate_bm25_k1(cls, v: float) -> float:
        if v < 0.0:
            raise ValueError(f"bm25_k1 must be non-negative (got {v})")
        return v

    @field_validator("bm25_b")
    @classmethod
    def validate_bm25_b(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"bm25_b must be between 0.0 and 1.0 inclusive (got {v})")
        return v

    @field_validator("bm25_default_top_k", "bm25_max_top_k")
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"top_k bounds must be positive (got {v})")
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()


