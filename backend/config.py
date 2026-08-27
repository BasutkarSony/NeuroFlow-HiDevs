from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(
        default="NeuroFlow",
        description="Application name.",
    )
    app_env: str = Field(
        default="development",
        description="Application environment.",
    )
    debug: bool = Field(
        default=False,
        description="Enable FastAPI debug behavior.",
    )

    # PostgreSQL
    postgres_host: str = Field(
        default="localhost",
        description="PostgreSQL hostname.",
    )
    postgres_port: int = Field(
        default=5432,
        description="PostgreSQL port.",
    )
    postgres_db: str = Field(
        default="neuroflow",
        description="Application PostgreSQL database.",
    )
    postgres_user: str = Field(
        default="neuroflow",
        description="PostgreSQL username.",
    )
    postgres_password: str = Field(
        description="PostgreSQL password.",
    )

    # Redis
    redis_host: str = Field(
        default="localhost",
        description="Redis hostname.",
    )
    redis_port: int = Field(
        default=6379,
        description="Redis port.",
    )
    redis_password: str = Field(
        description="Redis authentication password.",
    )

    # MLflow
    mlflow_host: str = Field(
        default="localhost",
        description="MLflow hostname.",
    )
    mlflow_port: int = Field(
        default=5000,
        description="MLflow server port.",
    )

    # OpenTelemetry
    otel_service_name: str = Field(
        default="neuroflow-api",
        description="OpenTelemetry service name.",
    )
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4317",
        description="OTLP gRPC endpoint.",
    )

    # LLM provider
    llm_api_key: str | None = Field(
        default=None,
        description="LLM provider API key.",
    )

    @property
    def postgres_dsn(self) -> str:
        """Return the asyncpg PostgreSQL connection URL."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """Return the authenticated Redis connection URL."""
        return (
            f"redis://:{self.redis_password}"
            f"@{self.redis_host}:{self.redis_port}/0"
        )

    @property
    def mlflow_url(self) -> str:
        """Return the MLflow tracking server URL."""
        return f"http://{self.mlflow_host}:{self.mlflow_port}"


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()