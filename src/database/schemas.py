"""
Pydantic v2 schemas (request/response DTOs) for the ingestion platform.
These mirror the canonical JSON schemas from the assignment spec.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────
class PricingModel(str, Enum):
    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    PAID = "PAID"
    ENTERPRISE = "ENTERPRISE"
    REVIEW = "REVIEW"  # Flag for manual review when evidence is insufficient


class MatchingMethod(str, Enum):
    EXACT = "exact"
    FUZZY_HIGH = "fuzzy_high"
    FUZZY_LOW = "fuzzy_low"
    SEMANTIC = "semantic"
    SEED = "seed"
    MANUAL_REVIEW = "manual_review"


class RecordType(str, Enum):
    STARTUP = "STARTUP"
    PRODUCT = "PRODUCT"
    RESEARCH_PAPER = "RESEARCH_PAPER"
    JOB = "JOB"
    NEWS = "NEWS"


# ─────────────────────────────────────────────────────────────────────────────
# Source metadata
# ─────────────────────────────────────────────────────────────────────────────
class SourceMeta(BaseModel):
    name: str
    url: str


# ─────────────────────────────────────────────────────────────────────────────
# STARTUP SCHEMA  (assignment canonical)
# ─────────────────────────────────────────────────────────────────────────────
class StartupData(BaseModel):
    employeeCount: Optional[int] = None
    description: Optional[str] = None


class StartupContent(BaseModel):
    entityName: str
    data: StartupData = Field(default_factory=StartupData)


class StartupSchema(BaseModel):
    schemaVersion: str = "1.0"
    recordType: RecordType = RecordType.STARTUP
    source: SourceMeta
    content: StartupContent
    collectedAt: str  # ISO-8601

    @field_validator("collectedAt")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCT SCHEMA
# ─────────────────────────────────────────────────────────────────────────────
class ProductContent(BaseModel):
    entityName: str
    startupName: Optional[str] = None
    pricingModel: PricingModel = PricingModel.REVIEW
    description: Optional[str] = None


class ProductSchema(BaseModel):
    schemaVersion: str = "1.0"
    recordType: RecordType = RecordType.PRODUCT
    source: SourceMeta
    content: ProductContent
    collectedAt: str


# ─────────────────────────────────────────────────────────────────────────────
# RESEARCH PAPER SCHEMA
# ─────────────────────────────────────────────────────────────────────────────
class ResearchPaperContent(BaseModel):
    title: str
    authors: List[str] = Field(default_factory=list)
    paper_url: str
    abstract: Optional[str] = None
    github_url: Optional[str] = None
    github_stars: Optional[int] = None
    github_stars_collected_at: Optional[str] = None
    published_date: Optional[str] = None  # ISO-8601
    arxiv_id: Optional[str] = None


class ResearchPaperSchema(BaseModel):
    schemaVersion: str = "1.0"
    recordType: RecordType = RecordType.RESEARCH_PAPER
    source: SourceMeta = Field(
        default_factory=lambda: SourceMeta(name="arXiv", url="https://arxiv.org")
    )
    content: ResearchPaperContent
    collectedAt: str


# ─────────────────────────────────────────────────────────────────────────────
# JOB SCHEMA
# ─────────────────────────────────────────────────────────────────────────────
class JobContent(BaseModel):
    title: str
    company: Optional[str] = None
    canonical_company: Optional[str] = None
    date: Optional[str] = None  # ISO-8601 published date
    date_verified: bool = False
    date_method: Optional[str] = None
    is_remote: Optional[bool] = None
    role_family: Optional[str] = None
    location: Optional[str] = None
    source_url: str
    discovered_at: Optional[str] = None
    is_fresh: bool = False


class JobSchema(BaseModel):
    schemaVersion: str = "1.0"
    recordType: RecordType = RecordType.JOB
    source: SourceMeta
    content: JobContent
    collectedAt: str


# ─────────────────────────────────────────────────────────────────────────────
# NEWS SCHEMA
# ─────────────────────────────────────────────────────────────────────────────
class NewsContent(BaseModel):
    title: str
    full_text: Optional[str] = None
    source_name: str
    source_url: str
    published_at: Optional[str] = None  # ISO-8601
    published_at_verified: bool = False
    published_at_method: Optional[str] = None
    discovered_at: Optional[str] = None
    is_fresh: bool = False


class NewsSchema(BaseModel):
    schemaVersion: str = "1.0"
    recordType: RecordType = RecordType.NEWS
    source: SourceMeta
    content: NewsContent
    collectedAt: str


# ─────────────────────────────────────────────────────────────────────────────
# ENTITY MAPPING SCHEMA
# ─────────────────────────────────────────────────────────────────────────────
class EntityMappingSchema(BaseModel):
    raw_name: str
    canonical_name: str
    normalized_name: Optional[str] = None
    matching_method: MatchingMethod
    confidence_score: Optional[float] = None
    source_url: Optional[str] = None
    record_type: Optional[str] = None
    resolved_at: str
    requires_review: bool = False
    notes: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# API response wrappers
# ─────────────────────────────────────────────────────────────────────────────
class PipelineStatus(BaseModel):
    pipeline: str
    status: str
    records_discovered: int = 0
    records_validated: int = 0
    records_rejected: int = 0
    duplicates_removed: int = 0
    elapsed_seconds: float = 0.0
    errors: int = 0
    message: Optional[str] = None


class PipelineStartRequest(BaseModel):
    pipelines: List[str] = Field(
        default=["startups", "products", "research", "news", "jobs"],
        description="Pipelines to run",
    )
    max_records: Optional[int] = None
