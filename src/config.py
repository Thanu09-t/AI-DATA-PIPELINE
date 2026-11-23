"""
AI Intelligence Ingestion Platform
Central Configuration Module
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ Domain & Environment
    custom_domain: str = Field("localhost:8000", alias="CUSTOM_DOMAIN")
    app_env: str = Field("development", alias="APP_ENV")
    force_https: bool = Field(False, alias="FORCE_HTTPS")

    # ------------------------------------------------------------------ LLM
    gemini_api_key: Optional[str] = Field(None, alias="GEMINI_API_KEY")
    groq_api_key: Optional[str] = Field(None, alias="GROQ_API_KEY")
    deepseek_api_key: Optional[str] = Field(None, alias="DEEPSEEK_API_KEY")

    primary_llm_provider: str = Field("gemini", alias="PRIMARY_LLM_PROVIDER")
    primary_llm_model: str = Field("gemini-1.5-flash", alias="PRIMARY_LLM_MODEL")
    secondary_llm_provider: str = Field("groq", alias="SECONDARY_LLM_PROVIDER")
    secondary_llm_model: str = Field("llama3-70b-8192", alias="SECONDARY_LLM_MODEL")
    tertiary_llm_provider: str = Field("deepseek", alias="TERTIARY_LLM_PROVIDER")
    tertiary_llm_model: str = Field("deepseek-chat", alias="TERTIARY_LLM_MODEL")

    # ------------------------------------------------------------------ GitHub
    github_token: Optional[str] = Field(None, alias="GITHUB_TOKEN")

    # ------------------------------------------------------------------ Database
    database_url: str = Field(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_intelligence",
        alias="DATABASE_URL",
    )
    db_pool_size: int = Field(10, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(20, alias="DB_MAX_OVERFLOW")

    # ------------------------------------------------------------------ Redis
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")

    # ------------------------------------------------------------------ Google Sheets
    google_sheets_credentials: Optional[str] = Field(
        None, alias="GOOGLE_SHEETS_CREDENTIALS"
    )
    google_spreadsheet_id: Optional[str] = Field(None, alias="GOOGLE_SPREADSHEET_ID")

    # ------------------------------------------------------------------ Logging
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    # ------------------------------------------------------------------ Concurrency
    max_concurrent_requests: int = Field(20, alias="MAX_CONCURRENT_REQUESTS")
    batch_size: int = Field(50, alias="BATCH_SIZE")
    chunk_token_limit: int = Field(4000, alias="CHUNK_TOKEN_LIMIT")

    # ------------------------------------------------------------------ Pipeline targets
    target_startups: int = Field(1000, alias="TARGET_STARTUPS")
    target_products: int = Field(1000, alias="TARGET_PRODUCTS")
    target_papers: int = Field(1000, alias="TARGET_PAPERS")
    freshness_hours: int = Field(24, alias="FRESHNESS_HOURS")

    # ------------------------------------------------------------------ arXiv
    arxiv_max_results: int = Field(1500, alias="ARXIV_MAX_RESULTS")
    arxiv_categories: str = Field(
        "cs.AI,cs.LG,cs.CL,cs.CV,cs.RO,stat.ML", alias="ARXIV_CATEGORIES"
    )

    @property
    def arxiv_category_list(self) -> List[str]:
        return [c.strip() for c in self.arxiv_categories.split(",")]

    # ------------------------------------------------------------------ Rate limits
    arxiv_rate_limit: int = Field(30, alias="ARXIV_RATE_LIMIT")
    github_rate_limit: int = Field(30, alias="GITHUB_RATE_LIMIT")
    producthunt_rate_limit: int = Field(10, alias="PRODUCTHUNT_RATE_LIMIT")
    hf_rate_limit: int = Field(20, alias="HF_RATE_LIMIT")
    news_rate_limit: int = Field(15, alias="NEWS_RATE_LIMIT")
    job_rate_limit: int = Field(15, alias="JOB_RATE_LIMIT")

    # ------------------------------------------------------------------ Retry
    max_retries: int = Field(5, alias="MAX_RETRIES")
    retry_base_delay: float = Field(1.0, alias="RETRY_BASE_DELAY")
    retry_max_delay: float = Field(60.0, alias="RETRY_MAX_DELAY")

    # ------------------------------------------------------------------ Celery
    celery_broker_url: str = Field("redis://localhost:6379/1", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(
        "redis://localhost:6379/2", alias="CELERY_RESULT_BACKEND"
    )

    # ------------------------------------------------------------------ ChromaDB
    chroma_persist_dir: str = Field("data/chroma", alias="CHROMA_PERSIST_DIR")

    # ------------------------------------------------------------------ Paths
    @property
    def data_dir(self) -> Path:
        return BASE_DIR / "data"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def chroma_dir(self) -> Path:
        return BASE_DIR / self.chroma_persist_dir

    def ensure_dirs(self) -> None:
        for d in [self.raw_dir, self.processed_dir, self.exports_dir, self.logs_dir, self.chroma_dir]:
            d.mkdir(parents=True, exist_ok=True)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v = v.upper()
        if v not in valid:
            raise ValueError(f"log_level must be one of {valid}")
        return v


# Singleton
settings = Settings()
settings.ensure_dirs()
