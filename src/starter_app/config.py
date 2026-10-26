import logging
from enum import StrEnum
from functools import lru_cache
from typing import Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    PREVIEW = "preview"
    PRODUCTION = "production"

    @property
    def is_deployed(self) -> bool:
        return self in (Environment.PREVIEW, Environment.PRODUCTION)


class LogFormat(StrEnum):
    TEXT = "text"
    JSON = "json"


class LogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    def to_logging_level(self) -> int:
        return logging.getLevelNamesMapping()[self.value.upper()]


class Settings(BaseSettings):
    """Process configuration, read from `STARTER_APP_*` environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="STARTER_APP_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "starter-app"
    environment: Environment = Environment.LOCAL

    host: str = "127.0.0.1"
    port: int = 8000
    graceful_shutdown_timeout_seconds: int = 10
    cors_allowed_origins: list[str] = []

    database_url: SecretStr = SecretStr("sqlite:///./starter_app.db")
    database_pool_size: int = 5
    database_max_overflow: int = 10

    log_level: LogLevel = LogLevel.INFO
    log_level_vendor: LogLevel = LogLevel.WARNING
    # Defaults to text locally and JSON when deployed.
    log_format: LogFormat | None = None
    # The key the log level is written under: "severity" for Google Cloud Logging, for example.
    log_level_key: str = "level"
    log_sql: bool = False

    # OTLP/HTTP collector base URL, e.g. http://localhost:4318. Unset: metrics aren't exported.
    otlp_endpoint: str | None = None

    # Header-based authentication for local development and tests. Never valid when deployed.
    dev_auth_enabled: bool | None = None

    docs_enabled: bool | None = None

    @model_validator(mode="after")
    def _derive_environment_defaults(self) -> Self:
        deployed = self.environment.is_deployed
        if self.log_format is None:
            self.log_format = LogFormat.JSON if deployed else LogFormat.TEXT
        if self.dev_auth_enabled is None:
            self.dev_auth_enabled = not deployed
        if self.docs_enabled is None:
            self.docs_enabled = not deployed
        if deployed and self.dev_auth_enabled:
            raise ValueError("dev_auth_enabled must be false in a deployed environment")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
