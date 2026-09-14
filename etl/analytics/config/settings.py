"""
Application configuration for the AI-BI platform.

All environment-dependent configuration should enter the application
through this module. Individual analytics components should not read
environment variables directly.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        populate_by_name=True,
    )

    # ------------------------------------------------------------------
    # OpenAI Provider
    # ------------------------------------------------------------------

    openai_api_key: str = ""
    nl_query_model: str = "gpt-4.1-mini"

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------

    environment: str = Field(
        default="development",
        validation_alias="AIBI_ENVIRONMENT",
    )

    # ------------------------------------------------------------------
    # PostgreSQL
    # ------------------------------------------------------------------

    db_host: str = Field(
        default="localhost",
        validation_alias="AIBI_DB_HOST",
    )

    db_port: int = Field(
        default=5432,
        validation_alias="AIBI_DB_PORT",
    )

    db_name: str = Field(
        validation_alias="AIBI_DB_NAME",
    )

    db_user: str = Field(
        validation_alias="AIBI_DB_USER",
    )

    db_password: str = Field(
        default="",
        validation_alias="AIBI_DB_PASSWORD",
    )

    db_echo: bool = Field(
        default=False,
        validation_alias="AIBI_DB_ECHO",
    )

    db_pool_size: int = Field(
        default=5,
        validation_alias="AIBI_DB_POOL_SIZE",
    )

    db_max_overflow: int = Field(
        default=10,
        validation_alias="AIBI_DB_MAX_OVERFLOW",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide application settings."""
    return Settings() # type: ignore