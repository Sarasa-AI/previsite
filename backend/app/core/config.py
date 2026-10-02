import logging
from datetime import timedelta
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

INSECURE_SECRET_KEY_VALUES = frozenset(
    {
        "",
        "change-me-in-production",
        "changeme",
        "replace-me",
        "replace-with-a-long-random-secret",
        "secret",
        "your-secret-key",
    }
)

DEV_ONLY_DB_PASSWORDS = frozenset({"postgres", "password", "admin"})
DEV_ONLY_S3_CREDENTIALS = frozenset({"minioadmin"})


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
        """Sync URL for Alembic migrations."""
        if self.database_url:
            url = self.database_url
            # Handle PostgreSQL async -> sync
            if url.startswith("postgresql+asyncpg://"):
                return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
            # Handle SQLite async -> sync
            if url.startswith("sqlite+aiosqlite://"):
                return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
            return url
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # Security — SECRET_KEY must be set via env; insecure defaults fail at startup
    secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("secret_key", "SECRET_KEY"),
    )
    algorithm: str = "HS256"
    # Short-lived access JWT. Idle/absolute session continuity uses refresh tokens.
    access_token_expire_minutes: int = Field(
        default=15,
        validation_alias=AliasChoices(
            "access_token_expire_minutes",
            "ACCESS_TOKEN_EXPIRE_MINUTES",
        ),
    )
    # Rotating opaque refresh tokens (hash-at-rest). Idle = inactivity window;
    # absolute = max family lifetime from first issue.
    refresh_token_idle_minutes: int = Field(
        default=60,
        validation_alias=AliasChoices(
            "refresh_token_idle_minutes",
            "REFRESH_TOKEN_IDLE_MINUTES",
        ),
    )
    refresh_token_absolute_days: int = Field(
        default=7,
        validation_alias=AliasChoices(
            "refresh_token_absolute_days",
            "REFRESH_TOKEN_ABSOLUTE_DAYS",
        ),
    )

    # Default doctor seed (password from env only — never hardcode in source)
    seed_doctor_username: str = Field(
        default="bagherzade",
        validation_alias=AliasChoices(
            "seed_doctor_username",
            "SEED_DOCTOR_USERNAME",
        ),
    )
    seed_doctor_password: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "seed_doctor_password",
            "SEED_DOCTOR_PASSWORD",
        ),
    )

    # When true, any doctor may access any session (legacy single-clinic mode)
    single_doctor_mode: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "single_doctor_mode",
            "SINGLE_DOCTOR_MODE",
        ),
    )

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
    openrouter_inference_timeout: float = Field(
        default=30.0,
        validation_alias=AliasChoices(
            "openrouter_inference_timeout",
            "OPENROUTER_INFERENCE_TIMEOUT",
            "OPENROUTER_TIMEOUT",
        ),
    )
    intake_llm_model: str = "google/gemini-2.5-flash-lite"
    intake_llm_timeout_seconds: float = 20.0

    # LLM cascade / circuit breaker
    llm_circuit_failure_threshold: int = 3
    llm_circuit_cooldown_seconds: int = 60
    llm_tier2_provider: str = "gapgpt"
    llm_tier2_openrouter_model: str = "qwen/qwen-2.5-7b-instruct"

    # Outbound HTTP proxy for LLM API calls
    http_proxy: Optional[str] = None

    # Ollama / embeddings (Phase 2 RAG)
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    max_embedding_tokens: int = 512
    # openrouter — production uses OpenRouter for embeddings
    embedding_provider: str = "openrouter"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"

    # Optional CrossEncoder rerank after pgvector cosine retrieval
    reranker_enabled: bool = False
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_candidates: int = 20

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

    # CORS / Runtime (APP_ENV; ENVIRONMENT accepted as alias)
    app_env: str = Field(
        default="development",
        validation_alias=AliasChoices("app_env", "APP_ENV", "ENVIRONMENT"),
    )
    cors_origins: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:3001,"
        "http://127.0.0.1:3001,"
        "https://sarasa-ai.liara.run"
    )
    log_level: str = "INFO"
    skip_health_check: bool = False

    # Observability (optional — empty DSN disables Sentry)
    sentry_dsn: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("sentry_dsn", "SENTRY_DSN"),
    )
    # Optional static bearer for GET /metrics scrapers. Name only in docs.
    # When unset in production, anonymous access returns 404 (endpoint hidden).
    metrics_bearer_token: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "metrics_bearer_token",
            "METRICS_BEARER_TOKEN",
        ),
    )

    # MFA / TOTP for doctors (feature-flagged; default off)
    mfa_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("mfa_enabled", "MFA_ENABLED"),
    )
    doctor_mfa_required: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "doctor_mfa_required",
            "DOCTOR_MFA_REQUIRED",
        ),
    )
    admin_mfa_required: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "admin_mfa_required",
            "ADMIN_MFA_REQUIRED",
        ),
    )

    # Consent enforcement (P2-A). Default off — structure/API only until legal copy lands.
    consent_enforcement_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "consent_enforcement_enabled",
            "CONSENT_ENFORCEMENT_ENABLED",
        ),
    )
    consent_version_ai_processing: str = Field(
        default="v1",
        validation_alias=AliasChoices(
            "consent_version_ai_processing",
            "CONSENT_VERSION_AI_PROCESSING",
        ),
    )
    consent_version_data_processing: str = Field(
        default="v1",
        validation_alias=AliasChoices(
            "consent_version_data_processing",
            "CONSENT_VERSION_DATA_PROCESSING",
        ),
    )
    consent_version_recording: str = Field(
        default="v1",
        validation_alias=AliasChoices(
            "consent_version_recording",
            "CONSENT_VERSION_RECORDING",
        ),
    )
    consent_version_external_llm_processing: str = Field(
        default="v1",
        validation_alias=AliasChoices(
            "consent_version_external_llm_processing",
            "CONSENT_VERSION_EXTERNAL_LLM_PROCESSING",
        ),
    )
    # Fernet key for field-level encryption (mfa_secret in P1). Required when
    # MFA_ENABLED=true in production. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    field_encryption_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "field_encryption_key",
            "FIELD_ENCRYPTION_KEY",
        ),
    )

    # Patient data export / account erasure (P2-A Task 7).
    # Product owner must confirm LEGAL_RETENTION_* before production erasure.
    account_deletion_cool_off_hours: int = Field(
        default=72,
        validation_alias=AliasChoices(
            "account_deletion_cool_off_hours",
            "ACCOUNT_DELETION_COOL_OFF_HOURS",
        ),
    )
    legal_retention_keep_session_shell: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "legal_retention_keep_session_shell",
            "LEGAL_RETENTION_KEEP_SESSION_SHELL",
        ),
    )
    legal_retention_keep_pmh_shell: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "legal_retention_keep_pmh_shell",
            "LEGAL_RETENTION_KEEP_PMH_SHELL",
        ),
    )
    privacy_export_rate_limit_requests: int = Field(
        default=3,
        validation_alias=AliasChoices(
            "privacy_export_rate_limit_requests",
            "PRIVACY_EXPORT_RATE_LIMIT_REQUESTS",
        ),
    )
    privacy_export_rate_limit_window_seconds: int = Field(
        default=86400,
        validation_alias=AliasChoices(
            "privacy_export_rate_limit_window_seconds",
            "PRIVACY_EXPORT_RATE_LIMIT_WINDOW_SECONDS",
        ),
    )
    privacy_export_download_url_seconds: int = Field(
        default=3600,
        validation_alias=AliasChoices(
            "privacy_export_download_url_seconds",
            "PRIVACY_EXPORT_DOWNLOAD_URL_SECONDS",
        ),
    )
    privacy_export_bundle_ttl_hours: int = Field(
        default=168,
        validation_alias=AliasChoices(
            "privacy_export_bundle_ttl_hours",
            "PRIVACY_EXPORT_BUNDLE_TTL_HOURS",
        ),
    )

    # Rate limiting
    chat_rate_limit_requests: int = 20
    chat_rate_limit_window_seconds: int = 60
    llm_rate_limit_requests: int = 60
    llm_rate_limit_window_seconds: int = 60

    # Per-user limits on newly sensitive routes (conservative; in-process only)
    intake_write_rate_limit_requests: int = 60
    intake_write_rate_limit_window_seconds: int = 60
    file_upload_rate_limit_requests: int = 30
    file_upload_rate_limit_window_seconds: int = 60
    pdf_export_rate_limit_requests: int = 20
    pdf_export_rate_limit_window_seconds: int = 60
    ocr_read_rate_limit_requests: int = 60
    ocr_read_rate_limit_window_seconds: int = 60
    medications_search_rate_limit_requests: int = 60
    medications_search_rate_limit_window_seconds: int = 60
    mfa_verify_rate_limit_requests: int = 10
    mfa_verify_rate_limit_window_seconds: int = 300

    # Auth brute-force protection (login shared by patients and doctors)
    auth_login_max_failures: int = 5
    auth_login_window_seconds: int = 900
    auth_login_lockout_seconds: int = 900
    auth_register_max_requests: int = 20
    auth_register_window_seconds: int = 900

    # P2-B OTP / SMS
    sms_provider: str = Field(
        default="console",
        validation_alias=AliasChoices("sms_provider", "SMS_PROVIDER"),
    )
    otp_login_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("otp_login_enabled", "OTP_LOGIN_ENABLED"),
    )
    otp_ttl_seconds: int = Field(
        default=120,
        validation_alias=AliasChoices("otp_ttl_seconds", "OTP_TTL_SECONDS"),
    )
    otp_max_attempts: int = Field(
        default=5,
        validation_alias=AliasChoices("otp_max_attempts", "OTP_MAX_ATTEMPTS"),
    )
    otp_resend_cooldown_seconds: int = Field(
        default=60,
        validation_alias=AliasChoices(
            "otp_resend_cooldown_seconds",
            "OTP_RESEND_COOLDOWN_SECONDS",
        ),
    )
    otp_request_per_phone_limit: int = Field(
        default=5,
        validation_alias=AliasChoices(
            "otp_request_per_phone_limit",
            "OTP_REQUEST_PER_PHONE_LIMIT",
        ),
    )
    otp_request_per_phone_window_seconds: int = Field(
        default=900,
        validation_alias=AliasChoices(
            "otp_request_per_phone_window_seconds",
            "OTP_REQUEST_PER_PHONE_WINDOW_SECONDS",
        ),
    )
    otp_request_per_ip_limit: int = Field(
        default=20,
        validation_alias=AliasChoices(
            "otp_request_per_ip_limit",
            "OTP_REQUEST_PER_IP_LIMIT",
        ),
    )
    otp_request_per_ip_window_seconds: int = Field(
        default=900,
        validation_alias=AliasChoices(
            "otp_request_per_ip_window_seconds",
            "OTP_REQUEST_PER_IP_WINDOW_SECONDS",
        ),
    )
    otp_phone_daily_cap: int = Field(
        default=10,
        validation_alias=AliasChoices(
            "otp_phone_daily_cap",
            "OTP_PHONE_DAILY_CAP",
        ),
    )
    legacy_patient_password_login_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "legacy_patient_password_login_enabled",
            "LEGACY_PATIENT_PASSWORD_LOGIN_ENABLED",
        ),
    )

    # P2-B LLM de-identification gateway
    external_llm_deidentification_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "external_llm_deidentification_enabled",
            "EXTERNAL_LLM_DEIDENTIFICATION_ENABLED",
        ),
    )
    allow_external_image_inference: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "allow_external_image_inference",
            "ALLOW_EXTERNAL_IMAGE_INFERENCE",
        ),
    )
    # Comma-separated host allow-list (openrouter.ai, api.gapgpt.app, …)
    external_llm_provider_allowlist: str = Field(
        default="openrouter.ai,api.gapgpt.app",
        validation_alias=AliasChoices(
            "external_llm_provider_allowlist",
            "EXTERNAL_LLM_PROVIDER_ALLOWLIST",
        ),
    )
    llm_scrub_date_mode: str = Field(
        default="year",
        validation_alias=AliasChoices(
            "llm_scrub_date_mode",
            "LLM_SCRUB_DATE_MODE",
        ),
    )
    llm_egress_log_retention_days: int = Field(
        default=90,
        validation_alias=AliasChoices(
            "llm_egress_log_retention_days",
            "LLM_EGRESS_LOG_RETENTION_DAYS",
        ),
    )

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
    def REFRESH_TOKEN_IDLE_MINUTES(self) -> int:
        return self.refresh_token_idle_minutes

    @property
    def REFRESH_TOKEN_ABSOLUTE_DAYS(self) -> int:
        return self.refresh_token_absolute_days

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

    def account_deletion_cool_off_timedelta(self) -> timedelta:
        return timedelta(hours=max(0, int(self.account_deletion_cool_off_hours)))


def is_openrouter_api_key_configured(api_key: Optional[str] = None) -> bool:
    """Return True when a non-placeholder OpenRouter API key is present."""
    key = api_key if api_key is not None else settings.openrouter_api_key
    if key is None:
        return False
    normalized = key.strip()
    if not normalized:
        return False
    return normalized.lower() not in OPENROUTER_API_KEY_PLACEHOLDERS


def _normalized_env(value: str) -> str:
    return (value or "").strip().lower()


def is_production_env() -> bool:
    return _normalized_env(settings.app_env) == "production"


def validate_startup_config() -> None:
    """Fail fast on insecure secrets; warn when AI keys are missing."""
    secret = (settings.secret_key or "").strip()
    if secret.lower() in INSECURE_SECRET_KEY_VALUES or len(secret) < 16:
        raise SystemExit(
            "FATAL: SECRET_KEY must be set to a strong random value via environment. "
            "Do not use empty, placeholder, or 'change-me-in-production' values."
        )

    from app.security.field_crypto import validate_fernet_key

    field_key = (settings.field_encryption_key or "").strip() or None
    mfa_at_rest_required = (
        settings.mfa_enabled
        or settings.doctor_mfa_required
        or settings.admin_mfa_required
    )
    if mfa_at_rest_required:
        if is_production_env():
            if not validate_fernet_key(field_key):
                raise SystemExit(
                    "FATAL: FIELD_ENCRYPTION_KEY must be a valid Fernet key when "
                    "MFA is enabled (MFA_ENABLED / DOCTOR_MFA_REQUIRED / "
                    "ADMIN_MFA_REQUIRED) and APP_ENV/ENVIRONMENT=production."
                )
        elif not validate_fernet_key(field_key):
            logger.warning(
                "MFA is enabled but FIELD_ENCRYPTION_KEY is missing or invalid. "
                "mfa_secret values will not be encrypted at rest until a valid key is set."
            )
    elif field_key and not validate_fernet_key(field_key):
        logger.warning("FIELD_ENCRYPTION_KEY is set but invalid; ignoring.")
    elif not field_key and not mfa_at_rest_required:
        logger.warning(
            "FIELD_ENCRYPTION_KEY is not set. MFA secrets will remain plaintext "
            "if MFA is later enabled without configuring a key."
        )

    if is_production_env():
        db_password = (settings.db_password or "").strip().lower()
        s3_user = (settings.s3_access_key or "").strip().lower()
        s3_secret = (settings.s3_secret_key or "").strip().lower()
        if db_password in DEV_ONLY_DB_PASSWORDS:
            raise SystemExit(
                "FATAL: Default database password "
                f"({settings.db_password!r}) must not be used when "
                "APP_ENV/ENVIRONMENT=production. Set DB_PASSWORD to a strong secret."
            )
        if (
            s3_user in DEV_ONLY_S3_CREDENTIALS
            or s3_secret in DEV_ONLY_S3_CREDENTIALS
        ):
            raise SystemExit(
                "FATAL: Default MinIO/S3 credentials (minioadmin) must not be used "
                "when APP_ENV/ENVIRONMENT=production. Set S3_ACCESS_KEY and "
                "S3_SECRET_KEY to production values."
            )
        if not (settings.seed_doctor_password or "").strip():
            raise SystemExit(
                "FATAL: SEED_DOCTOR_PASSWORD must be set when "
                "APP_ENV/ENVIRONMENT=production so the default doctor account "
                "is not created with a random password that only appears in logs."
            )

    if not is_openrouter_api_key_configured():
        banner = "=" * 72
        logger.warning(banner)
        logger.warning(
            "AI features are disabled due to missing OPENROUTER_API_KEY. "
            "System will operate in deterministic fallback mode."
        )
        logger.warning(banner)

    # P2-B: OTP requires a real SMS provider in production.
    if settings.otp_login_enabled and is_production_env():
        sms = (settings.sms_provider or "").strip().lower()
        if sms in ("", "console", "test", "http"):
            raise SystemExit(
                "FATAL: OTP_LOGIN_ENABLED is true in production but SMS_PROVIDER "
                f"is {sms!r}. Configure a real SMS provider (not console/test/http "
                "stub) before enabling OTP in production."
            )

    if (
        is_production_env()
        and not settings.external_llm_deidentification_enabled
    ):
        logger.warning(
            "EXTERNAL_LLM_DEIDENTIFICATION_ENABLED is false in production. "
            "Patient identifiers may leave the system on external LLM calls."
        )


settings = Settings()
