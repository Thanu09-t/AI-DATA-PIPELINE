"""
SQLAlchemy ORM models for the AI Intelligence Ingestion Platform.
All tables use UUID primary keys and store source provenance.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, func, JSON,
)
try:
    from sqlalchemy.dialects.postgresql import JSONB
    JSON_TYPE = JSON().with_variant(JSONB, "postgresql")
except ImportError:
    JSON_TYPE = JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────────────────────────────────
class Startup(Base):
    __tablename__ = "startups"
    __table_args__ = (
        UniqueConstraint("source_url", name="uq_startup_source_url"),
        Index("ix_startup_entity_name", "entity_name"),
        Index("ix_startup_canonical_name", "canonical_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    schema_version: Mapped[str] = mapped_column(String(10), default="1.0")
    entity_name: Mapped[str] = mapped_column(String(512), nullable=False)
    product_name: Mapped[Optional[str]] = mapped_column(String(512))
    startup_name: Mapped[Optional[str]] = mapped_column(String(512))
    company_name: Mapped[Optional[str]] = mapped_column(String(512))
    canonical_name: Mapped[Optional[str]] = mapped_column(String(512))
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    employee_count: Mapped[Optional[int]] = mapped_column(Integer)
    description: Mapped[Optional[str]] = mapped_column(Text)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON_TYPE)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    products: Mapped[list["Product"]] = relationship("Product", back_populates="startup", lazy="select")


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCT
# ─────────────────────────────────────────────────────────────────────────────
class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("source_url", name="uq_product_source_url"),
        Index("ix_product_entity_name", "entity_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    schema_version: Mapped[str] = mapped_column(String(10), default="1.0")
    entity_name: Mapped[str] = mapped_column(String(512), nullable=False)
    product_name: Mapped[Optional[str]] = mapped_column(String(512))
    startup_name: Mapped[Optional[str]] = mapped_column(String(512))
    company_name: Mapped[Optional[str]] = mapped_column(String(512))
    startup_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("startups.id", ondelete="SET NULL"), nullable=True
    )
    pricing_model: Mapped[Optional[str]] = mapped_column(String(50))  # FREE|FREEMIUM|PAID|ENTERPRISE|REVIEW
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON_TYPE)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    startup: Mapped[Optional["Startup"]] = relationship("Startup", back_populates="products")


# ─────────────────────────────────────────────────────────────────────────────
# RESEARCH PAPER
# ─────────────────────────────────────────────────────────────────────────────
class ResearchPaper(Base):
    __tablename__ = "research_papers"
    __table_args__ = (
        UniqueConstraint("paper_url", name="uq_paper_url"),
        Index("ix_paper_title", "title"),
        Index("ix_paper_published_date", "published_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    schema_version: Mapped[str] = mapped_column(String(10), default="1.0")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[Optional[dict]] = mapped_column(JSON_TYPE)  # list of author names
    paper_url: Mapped[str] = mapped_column(Text, nullable=False)
    arxiv_id: Mapped[Optional[str]] = mapped_column(String(50))
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    github_url: Mapped[Optional[str]] = mapped_column(Text)
    github_stars: Mapped[Optional[int]] = mapped_column(Integer)
    github_stars_collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    github_enriched: Mapped[bool] = mapped_column(Boolean, default=False)
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    source_name: Mapped[str] = mapped_column(String(255), default="arXiv")
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON_TYPE)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────────────────────────────────────
# NEWS ARTICLE
# ─────────────────────────────────────────────────────────────────────────────
class NewsArticle(Base):
    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint("url_hash", name="uq_news_url_hash"),
        Index("ix_news_published_at", "published_at"),
        Index("ix_news_source_name", "source_name"),
        Index("ix_news_is_fresh", "is_fresh"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    schema_version: Mapped[str] = mapped_column(String(10), default="1.0")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    full_text: Mapped[Optional[str]] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 of source_url
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    published_at_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at_method: Mapped[Optional[str]] = mapped_column(String(100))
    discovered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_fresh: Mapped[bool] = mapped_column(Boolean, default=False)
    freshness_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON_TYPE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────────────────────────────────────
# JOB
# ─────────────────────────────────────────────────────────────────────────────
class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("url_hash", name="uq_job_url_hash"),
        Index("ix_job_company", "company"),
        Index("ix_job_published_at", "published_at"),
        Index("ix_job_is_fresh", "is_fresh"),
        Index("ix_job_role_family", "role_family"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    schema_version: Mapped[str] = mapped_column(String(10), default="1.0")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String(512))
    canonical_company: Mapped[Optional[str]] = mapped_column(String(512))
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    published_at_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at_method: Mapped[Optional[str]] = mapped_column(String(100))
    discovered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_remote: Mapped[Optional[bool]] = mapped_column(Boolean)
    role_family: Mapped[Optional[str]] = mapped_column(String(100))
    location: Mapped[Optional[str]] = mapped_column(String(255))
    is_fresh: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON_TYPE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────────────────────────────────────
# ENTITY MAPPING LOG
# ─────────────────────────────────────────────────────────────────────────────
class EntityMapping(Base):
    __tablename__ = "entity_mappings"
    __table_args__ = (
        Index("ix_entity_mapping_raw_name", "raw_name"),
        Index("ix_entity_mapping_canonical_name", "canonical_name"),
        Index("ix_entity_mapping_method", "matching_method"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    raw_name: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[Optional[str]] = mapped_column(Text)
    matching_method: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # exact|fuzzy_high|fuzzy_low|semantic|seed|manual_review
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    record_type: Mapped[Optional[str]] = mapped_column(String(50))
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)


# ─────────────────────────────────────────────────────────────────────────────
# LLM EXTRACTION LOG
# ─────────────────────────────────────────────────────────────────────────────
class LLMExtractionLog(Base):
    __tablename__ = "llm_extraction_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    record_type: Mapped[Optional[str]] = mapped_column(String(50))
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_status: Mapped[Optional[str]] = mapped_column(String(50))
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
