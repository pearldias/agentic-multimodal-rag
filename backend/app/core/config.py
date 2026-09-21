from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    PROJECT_NAME: str = "Multimodal RAG API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Data Storage Configuration (explicitly managed, no side-effect creation on import)
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    RAW_DATA_DIR: Path = DATA_DIR / "raw"
    PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
    METADATA_DIR: Path = DATA_DIR / "metadata"
    DATABASE_PATH: Path = DATA_DIR / "conversations.db"

    # Conversation History & Memory Configuration
    MEMORY_WINDOW_MESSAGES: int = 6

    # Gemini Embeddings Configuration
    GOOGLE_API_KEY: str | None = None
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIMENSION: int = 768

    # Gemini LLM Configuration
    GEMINI_LLM_MODEL: str = "gemini-3.6-flash"
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_DELAY: float = 2.0

    # Cohere Reranker Configuration
    COHERE_API_KEY: str | None = None
    COHERE_RERANK_MODEL: str = "rerank-v4.0-fast"
    RERANK_INITIAL_K: int = 15
    RERANK_TOP_K: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
