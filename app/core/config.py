"""Configuration management for the Transaction Management service.

Configuration is loaded from environment variables with secrets
managed through Doppler.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Constants for database URL construction
POSTGRESQL_PREFIX = "postgresql://"
ASYNCPG_DRIVER = "+asyncpg"
PSYCPG_DRIVER = "+psycopg"


class AppEnvironment(str, Enum):
    LOCAL = "local"
    TEST = "test"
    PROD = "prod"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AppConfig(BaseSettings):
    name: str = Field(default="fraud-transaction-management")
    env: AppEnvironment = Field(default=AppEnvironment.LOCAL)
    version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)
    log_level: LogLevel = Field(default=LogLevel.INFO)
    api_prefix: str = Field(default="/v1")

    model_config = SettingsConfigDict(env_prefix="APP_")

    @field_validator("env", mode="before")
    @classmethod
    def validate_env(cls, v: str | AppEnvironment) -> AppEnvironment:
        if isinstance(v, AppEnvironment):
            return v
        return AppEnvironment(v)

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v: str | LogLevel) -> LogLevel:
        if isinstance(v, LogLevel):
            return v
        return LogLevel(v)


class ServerConfig(BaseSettings):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080)
    workers: int = Field(default=4)
    max_connections: int = Field(default=100)
    keepalive_timeout: int = Field(default=5)

    model_config = SettingsConfigDict(env_prefix="SERVER_")


class DatabaseConfig(BaseSettings):
    # Primary: Full connection URL (preferred, matches rule-management pattern)
    url_app: str = Field(default="", alias="database_url_app")

    # Admin URL for schema migrations (optional)
    url_admin: str = Field(default="", alias="database_url_admin")

    # Fallback: Individual components for backward compatibility
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    name: str = Field(default="fraud_tm")
    user: str = Field(default="postgres")
    password: SecretStr = Field(default=SecretStr(""))
    pool_size: int = Field(default=10)
    max_overflow: int = Field(default=20)
    pool_timeout: int = Field(default=30)
    pool_recycle: int = Field(default=1800)
    echo: bool = Field(default=False)
    require_ssl: bool = Field(default=True)

    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
        populate_by_name=True,  # Allow alias to work
    )

    @property
    def async_url(self) -> str:
        """Build async database URL."""
        if self.url_app:
            # Convert postgresql:// to postgresql+asyncpg:// if needed
            url = self.url_app
            if url.startswith(POSTGRESQL_PREFIX) and ASYNCPG_DRIVER not in url:
                new_prefix = POSTGRESQL_PREFIX.removesuffix("://") + ASYNCPG_DRIVER + "://"
                url = url.replace(POSTGRESQL_PREFIX, new_prefix, 1)
            return url
        # Fallback to individual components
        password = self.password.get_secret_value()
        return f"postgresql{ASYNCPG_DRIVER}://{self.user}:{password}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_url(self) -> str:
        """Build sync database URL for migrations."""
        if self.url_app:
            # Ensure postgresql:// or postgresql+psycopg:// format
            url = self.url_app
            if ASYNCPG_DRIVER in url:
                url = url.replace(ASYNCPG_DRIVER, PSYCPG_DRIVER, 1)
            elif "+psycopg" not in url:
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            return url
        # Fallback to individual components
        password = self.password.get_secret_value()
        return f"postgresql+psycopg://{self.user}:{password}@{self.host}:{self.port}/{self.name}"


class KafkaConfig(BaseSettings):
    enabled: bool = Field(default=False)
    bootstrap_servers: str = Field(default="")
    consumer_group_id: str = Field(default="")
    topic_decisions: str = Field(default="fraud.card.decisions.v1")
    topic_dlq: str | None = Field(default=None)
    auto_offset_reset: str = Field(default="earliest")
    enable_auto_commit: bool = Field(default=True)
    auto_commit_interval_ms: int = Field(default=5000)
    session_timeout_ms: int = Field(default=30000)
    heartbeat_interval_ms: int = Field(default=10000)
    max_poll_records: int = Field(default=500)
    consumer_timeout_ms: int = Field(default=300000)
    security_protocol: str = Field(default="SASL_SSL")
    sasl_mechanism: str = Field(default="SCRAM-SHA-512")
    sasl_username: str = Field(default="")
    sasl_password: SecretStr = Field(default=SecretStr(""))

    model_config = SettingsConfigDict(env_prefix="KAFKA_")


class S3Config(BaseSettings):
    endpoint_url: str = Field(default="")
    region: str = Field(default="us-east-1")
    bucket_name: str = Field(default="")
    access_key_id: str = Field(default="")
    secret_access_key: SecretStr = Field(default=SecretStr(""))
    use_path_style: bool = Field(default=True)
    signature_version: str = Field(default="s3v4")

    model_config = SettingsConfigDict(env_prefix="S3_")


class Auth0Config(BaseSettings):
    domain: str = Field(default="")
    audience: str = Field(default="")
    client_id: str = Field(default="")
    client_secret: SecretStr = Field(default=SecretStr(""))
    algorithms: str = Field(default="RS256")  # Comma-separated string like rule-management
    issuer: str | None = Field(default=None)
    jwks_cache_ttl: int = Field(default=600)

    model_config = SettingsConfigDict(env_prefix="AUTH0_")

    @property
    def jwks_url(self) -> str:
        """Build JWKS URL."""
        return f"https://{self.domain}/.well-known/jwks.json"

    @property
    def issuer_url(self) -> str:
        """Build issuer URL."""
        return f"https://{self.domain}/"

    @property
    def algorithms_list(self) -> list[str]:
        """Parse Auth0 algorithms string into a list."""
        return [algo.strip() for algo in self.algorithms.split(",")]


class RuleManagementConfig(BaseSettings):
    base_url: str = Field(default="")
    timeout: int = Field(default=30)
    retries: int = Field(default=3)
    cache_ttl_seconds: int = Field(default=300)
    cache_max_size: int = Field(default=10000)

    model_config = SettingsConfigDict(env_prefix="RULE_MANAGEMENT_")


class ObservabilityConfig(BaseSettings):
    service_name: str = Field(default="fraud-transaction-management")
    otlp_endpoint: str | None = Field(default=None)
    otlp_insecure: bool = Field(default=True)  # Use HTTPS in production, HTTP only for local dev
    traces_sampler: str = Field(default="always_on")
    metrics_export_interval: int = Field(default=60000)
    log_record_format: str = Field(default="json")
    datadog_agent_host: str | None = Field(default=None)
    datadog_trace_agent_port: int = Field(default=8126)

    model_config = SettingsConfigDict(env_prefix="OTEL_")


class FeatureFlagsConfig(BaseSettings):
    enable_http_ingestion: bool = Field(default=False)
    enable_rule_enrichment: bool = Field(default=True)
    require_analyst_approval: bool = Field(default=False)
    enable_auto_review_creation: bool = Field(default=True)

    model_config = SettingsConfigDict(env_prefix="FEATURE_")


class SecurityConfig(BaseSettings):
    cors_allowed_origins: str = Field(default="http://localhost:3000,http://localhost:8000")
    cors_allow_credentials: bool = Field(default=True)
    cors_allow_methods: list[str] = Field(default=["GET", "POST", "PATCH", "DELETE", "PUT"])
    cors_allow_headers: list[str] = Field(default=["Authorization", "Content-Type", "X-Request-ID"])
    sanitize_errors: bool = Field(default=True)  # Hide sensitive details in production

    # Local Development: Skip JWT validation
    # SECURITY: ONLY allowed in local environment. Will raise error in test/prod.
    # Used for e2e load testing and local development without Auth0.
    skip_jwt_validation: bool = Field(default=False)

    model_config = SettingsConfigDict(env_prefix="SECURITY_")

    @field_validator("cors_allowed_origins", mode="after")
    @classmethod
    def validate_cors_allowed_origins(cls, v: str | list[str]) -> list[str]:
        """Parse comma-separated string into list of origins."""
        if isinstance(v, str):
            # Split by comma and strip whitespace
            origins = [origin.strip() for origin in v.split(",") if origin.strip()]
            return origins
        return v

    @field_validator("skip_jwt_validation", mode="before")
    @classmethod
    def parse_skip_jwt_validation(cls, v: bool | str) -> bool:
        """Parse boolean from environment variable (string "true"/"false")."""
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return v


class Settings(BaseSettings):
    app: AppConfig = Field(default_factory=AppConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    kafka: KafkaConfig = Field(default_factory=KafkaConfig)
    s3: S3Config = Field(default_factory=S3Config)
    auth0: Auth0Config = Field(default_factory=Auth0Config)
    rule_management: RuleManagementConfig = Field(default_factory=RuleManagementConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    features: FeatureFlagsConfig = Field(default_factory=FeatureFlagsConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    @model_validator(mode="after")
    def validate_security_settings(self) -> Settings:
        """Validate security settings after all configs are loaded."""
        # SECURITY: JWT validation bypass is ONLY allowed in local environment
        if self.security.skip_jwt_validation and self.app.env != AppEnvironment.LOCAL:
            raise ValueError(
                "SECURITY_SKIP_JWT_VALIDATION can only be set in local environment. "
                f"Current environment: {self.app.env.value}"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def reload_settings() -> Settings:
    """Reload settings (useful for testing)."""
    get_settings.cache_clear()
    return get_settings()
