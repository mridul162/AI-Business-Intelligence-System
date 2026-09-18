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
    # LLM Reliability
    # ------------------------------------------------------------------

    llm_timeout: float = Field(
        default=20.0,
        gt=0,
        validation_alias="AIBI_LLM_TIMEOUT",
    )

    llm_max_attempts: int = Field(
        default=3,
        ge=1,
        validation_alias="AIBI_LLM_MAX_ATTEMPTS",
    )

    llm_retry_initial_backoff: float = Field(
        default=0.5,
        ge=0,
        validation_alias="AIBI_LLM_RETRY_INITIAL_BACKOFF",
    )

    llm_retry_max_backoff: float = Field(
        default=2.0,
        ge=0,
        validation_alias="AIBI_LLM_RETRY_MAX_BACKOFF",
    )

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
        gt=0,
        validation_alias="AIBI_DB_POOL_SIZE",
    )

    db_max_overflow: int = Field(
        default=10,
        gt=0,
        validation_alias="AIBI_DB_MAX_OVERFLOW",
    )

    # ------------------------------------------------------------------
    # Timeout Policy
    # ------------------------------------------------------------------

    db_connect_timeout: int = Field(
        default=5,
        gt=0,
        validation_alias="AIBI_DB_CONNECT_TIMEOUT",
    )

    db_statement_timeout: int = Field(
        default=30,
        gt=0,
        validation_alias="AIBI_DB_STATEMENT_TIMEOUT",
    )

    db_pool_timeout: int = Field(
        default=10,
        gt=0,
        validation_alias="AIBI_DB_POOL_TIMEOUT",
    )
    
    # ------------------------------------------------------------------
    # Rate Limiting
    # ------------------------------------------------------------------ 
  
    rate_limit_requests: int = Field(
        default=30,
        gt=0,
        validation_alias="AIBI_RATE_LIMIT_REQUESTS",
    )

    rate_limit_window_seconds: int = Field(
        default=60,
        gt=0,
        validation_alias="AIBI_RATE_LIMIT_WINDOW_SECONDS",
    )

    rate_limit_burst: int = Field(
        default=10,
        ge=0,
        validation_alias="AIBI_RATE_LIMIT_BURST",
    )

    # ------------------------------------------------------------------
    # Analytics Cost Controls
    # ------------------------------------------------------------------     
    
    max_queries_per_request: int = Field(
        default=5,
        gt=0,
        validation_alias="AIBI_MAX_QUERIES_PER_REQUEST",
    )

    max_result_rows: int = Field(
        default=1000,
        gt=0,
        validation_alias="AIBI_MAX_RESULT_ROWS",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide application settings."""
    return Settings() # type: ignore