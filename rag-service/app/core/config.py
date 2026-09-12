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

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()

