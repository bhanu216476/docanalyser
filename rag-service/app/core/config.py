from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    project_name: str = "DocAnalyser RAG Service"
    version: str = "1.0.0"
    
    # Placeholder for future config
    qdrant_url: str = "http://localhost:6333"
    redis_url: str = "redis://localhost:6379"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

settings = Settings()
