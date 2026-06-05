from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    llm_provider: str = "gapgpt"
    llm_model: str = "gapgpt-qwen-3.5"
    
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

    # File Upload
    upload_dir: str = "uploads"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: list[str] = ["pdf", "jpg", "jpeg", "png", "doc", "docx", "txt"]

    # CORS / Runtime
    app_env: str = "development"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    log_level: str = "INFO"

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


settings = Settings()
