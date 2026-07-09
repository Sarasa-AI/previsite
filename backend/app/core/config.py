import logging
from typing import Optional

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY_PLACEHOLDERS = frozenset(
    {
        "",
        "your-openrouter-api-key",
        "replace-me",
        "changeme",
        "sk-or-v1-placeholder",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_host: str = "localhost"
    db_port: str = "5432"
    db_name: str = "previsit"
    database_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("database_url", "DATABASE_URL")
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def sanitize_database_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not isinstance(v, str):
            return v
        # Strip all whitespaces, invisible newline characters (\n, \r), 
        # and explicit string quotes (" or ')
        sanitized = v.strip().replace("\n", "").replace("\r", "").strip("'\"")
        
        # Normalize to asyncpg driver for the application runtime
        if sanitized.startswith("postgres://"):
            sanitized = sanitized.replace("postgres://", "postgresql+asyncpg://", 1)
        elif sanitized.startswith("postgresql+psycopg2://"):
            sanitized = sanitized.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        elif sanitized.startswith("postgresql://") and "+asyncpg" not in sanitized:
            sanitized = sanitized.replace("postgresql://", "postgresql+asyncpg://", 1)

        logger.debug(f"Sanitized DATABASE_URL (length: {len(sanitized)})")
        return sanitized

    @property
    def DATABASE_URL(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Sync URL for Alembic migrations (psycopg2)."""
        if self.database_url:
            url = self.database_url
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # Security
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # LLM Configuration
    llm_provider: str = "openrouter"
    llm_model: str = "google/gemini-2.5-flash-lite"
    
    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    
    # Anthropic
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    
    # GapGPT
    gapgpt_api_key: Optional[str] = None
    gapgpt_base_url: str = "https://api.gapgpt.app/v1"
    gapgpt_model: str = "gapgpt-qwen-3.5"

    # OpenRouter (primary LLM provider)
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_default_model: str = Field(
        default="google/gemini-2.5-flash-lite",
        validation_alias=AliasChoices(
            "openrouter_default_model",
            "OPENROUTER_DEFAULT_MODEL",
            "OPENROUTER_MODEL",
        ),
    )
    openrouter_http_referer: str = "http://localhost:3000"
    openrouter_app_title: str = "PreVisit MVP"
    intake_llm_model: str = "google/gemini-2.5-flash-lite"
    intake_llm_timeout_seconds: float = 20.0

    # LLM cascade / circuit breaker
    llm_circuit_failure_threshold: int = 3
    llm_circuit_cooldown_seconds: int = 60
    llm_tier2_provider: str = "gapgpt"
    llm_tier2_ollama_model: str = "llama3.2"
    llm_tier2_openrouter_model: str = "qwen/qwen-2.5-7b-instruct"

    # Outbound HTTP proxy for LLM API calls
    http_proxy: Optional[str] = None

    # Ollama / embeddings (Phase 2 RAG)
    ollama_host: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    max_embedding_tokens: int = 512

    # File Upload
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: list[str] = ["pdf", "jpg", "jpeg", "png", "doc", "docx", "txt"]
    upload_dir: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("upload_dir", "UPLOAD_DIR"),
    )

    # S3-compatible object storage
    s3_endpoint: Optional[str] = "http://localhost:9000"
    s3_bucket_name: str = "previsit-files"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_use_ssl: bool = False

    # CORS / Runtime
    app_env: str = "development"
    cors_origins: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:3001,"
        "http://127.0.0.1:3001,"
        "https://sarasa-ai.liara.run"
    )
    log_level: str = "INFO"
    skip_health_check: bool = False

    # Rate limiting
    chat_rate_limit_requests: int = 20
    chat_rate_limit_window_seconds: int = 60
    llm_rate_limit_requests: int = 60
    llm_rate_limit_window_seconds: int = 60

    @property
    def SECRET_KEY(self) -> str:
        return self.secret_key

    @property
    def ALGORITHM(self) -> str:
        return self.algorithm

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        return self.access_token_expire_minutes

    @property
    def HTTP_PROXY(self) -> Optional[str]:
        return self.http_proxy

    @property
    def openrouter_model(self) -> str:
        """Backward-compatible alias for openrouter_default_model."""
        return self.openrouter_default_model

    @property
    def SKIP_HEALTH_CHECK(self) -> bool:
        return self.skip_health_check


def is_openrouter_api_key_configured(api_key: Optional[str] = None) -> bool:
    """Return True when a non-placeholder OpenRouter API key is present."""
    key = api_key if api_key is not None else settings.openrouter_api_key
    if key is None:
        return False
    normalized = key.strip()
    if not normalized:
        return False
    return normalized.lower() not in OPENROUTER_API_KEY_PLACEHOLDERS


def validate_startup_config() -> None:
    """Log severe warnings for missing configuration that degrades AI features."""
    if not is_openrouter_api_key_configured():
        banner = "=" * 72
        logger.warning(banner)
        logger.warning(
            "AI features are disabled due to missing OPENROUTER_API_KEY. "
            "System will operate in deterministic fallback mode."
        )
        logger.warning(banner)


settings = Settings()
