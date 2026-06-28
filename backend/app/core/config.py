import logging
from typing import Optional

from pydantic import AliasChoices, Field
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
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/previsit"

    # Security
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # LLM Configuration
    llm_provider: str = "openrouter"
    llm_model: str = "qwen/qwen-2.5-72b-instruct"
    
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
        default="qwen/qwen-2.5-72b-instruct",
        validation_alias=AliasChoices(
            "openrouter_default_model",
            "OPENROUTER_DEFAULT_MODEL",
            "OPENROUTER_MODEL",
        ),
    )
    openrouter_http_referer: str = "http://localhost:3000"
    openrouter_app_title: str = "PreVisit MVP"

    # Outbound HTTP proxy for LLM API calls
    http_proxy: Optional[str] = None

    # File Upload
    upload_dir: str = "uploads"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: list[str] = ["pdf", "jpg", "jpeg", "png", "doc", "docx", "txt"]

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

    # Compatibility aliases for existing code that references uppercase attrs
    @property
    def DATABASE_URL(self) -> str:
        return self.database_url

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
