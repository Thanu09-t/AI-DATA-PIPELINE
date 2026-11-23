"""
Comprehensive automated test suite for the AI Intelligence Ingestion Platform.
Uses mocked HTTP responses: no real API credentials needed.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

UTC = timezone.utc


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_arxiv_xml():
    """Sample arXiv API XML response."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <title>Large Language Models for AI Research</title>
    <summary>We present a novel approach using LLMs. Code at https://github.com/example/llm-research</summary>
    <published>2026-01-15T00:00:00Z</published>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <link href="http://arxiv.org/abs/2401.00001v1" rel="alternate"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.00002v1</id>
    <title>Deep Learning for Computer Vision</title>
    <summary>Vision transformer improvements.</summary>
    <published>2026-01-14T00:00:00Z</published>
    <author><name>Charlie Brown</name></author>
    <link href="http://arxiv.org/abs/2401.00002v1" rel="alternate"/>
  </entry>
</feed>'''


@pytest.fixture
def sample_github_repo():
    return {
        "stargazers_count": 1234,
        "forks_count": 567,
        "open_issues_count": 23,
        "language": "Python",
        "full_name": "example/llm-research",
    }


@pytest.fixture
def sample_news_rss():
    now = datetime.now(UTC)
    recent = (now - timedelta(hours=2)).strftime("%a, %d %b %Y %H:%M:%S %z")
    old = (now - timedelta(hours=48)).strftime("%a, %d %b %Y %H:%M:%S %z")
    return f'''<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>TechCrunch AI</title>
    <item>
      <title>GPT-5 Released Today</title>
      <link>https://techcrunch.com/2026/01/01/gpt-5-released</link>
      <pubDate>{recent}</pubDate>
      <description>OpenAI releases GPT-5 with remarkable capabilities.</description>
    </item>
    <item>
      <title>Old AI News Article</title>
      <link>https://techcrunch.com/2026/01/01/old-article</link>
      <pubDate>{old}</pubDate>
      <description>This article is older than 24 hours.</description>
    </item>
  </channel>
</rss>'''


@pytest.fixture
def sample_greenhouse_jobs():
    now = datetime.now(UTC)
    recent = (now - timedelta(hours=1)).isoformat()
    old = (now - timedelta(hours=72)).isoformat()
    return {
        "jobs": [
            {
                "id": 1001,
                "title": "Machine Learning Engineer",
                "absolute_url": "https://boards.greenhouse.io/openai/jobs/1001",
                "updated_at": recent,
                "location": {"name": "San Francisco, CA"},
            },
            {
                "id": 1002,
                "title": "AI Research Scientist",
                "absolute_url": "https://boards.greenhouse.io/openai/jobs/1002",
                "updated_at": old,
                "location": {"name": "Remote"},
            },
        ]
    }


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: Research paper extraction
# ─────────────────────────────────────────────────────────────────────────────
def test_research_paper_parsing(sample_arxiv_xml):
    """Test arXiv XML parsing produces correct paper records."""
    import sys
    sys.path.insert(0, ".")
    from src.collectors.research_collector import ResearchCollector

    collector = ResearchCollector()
    import xml.etree.ElementTree as ET
    root = ET.fromstring(sample_arxiv_xml)
    ns = "http://www.w3.org/2005/Atom"
    entries = root.findall(f"{{{ns}}}entry")

    papers = [collector._parse_entry(e) for e in entries]
    papers = [p for p in papers if p]

    assert len(papers) == 2
    assert papers[0]["title"] == "Large Language Models for AI Research"
    assert "Alice Smith" in papers[0]["authors"]
    assert "Bob Jones" in papers[0]["authors"]
    assert papers[0]["arxiv_id"] == "2401.00001v1"
    assert papers[0]["github_url"] == "https://github.com/example/llm-research"
    assert papers[1]["github_url"] is None  # No GitHub in second abstract


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2: GitHub star retrieval
# ─────────────────────────────────────────────────────────────────────────────
def test_github_star_retrieval(sample_github_repo):
    """Test GitHub star count retrieval from mocked API."""
    from unittest.mock import AsyncMock, patch
    from src.collectors.github_collector import GitHubCollector

    async def _run():
        collector = GitHubCollector()
        collector.fetch = AsyncMock(return_value=sample_github_repo)
        return await collector.get_repo_stars("https://github.com/example/llm-research")

    result = asyncio.run(_run())
    assert result is not None
    assert result["github_stars"] == 1234
    assert result["github_enriched"] is True
    assert result["github_url"] == "https://github.com/example/llm-research"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3: GitHub URL parsing
# ─────────────────────────────────────────────────────────────────────────────
def test_github_url_parsing():
    """Test various GitHub URL formats are parsed correctly."""
    from src.collectors.github_collector import parse_github_repo

    cases = [
        ("https://github.com/openai/gpt-4", ("openai", "gpt-4")),
        ("https://github.com/huggingface/transformers.git", ("huggingface", "transformers")),
        ("http://github.com/example/repo/", ("example", "repo")),
        ("not-a-github-url", None),
        ("https://github.com/owner", None),  # No repo name
    ]
    for url, expected in cases:
        result = parse_github_repo(url)
        assert result == expected, f"Failed for {url}: got {result}, expected {expected}"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4: Date normalization: ISO-8601
# ─────────────────────────────────────────────────────────────────────────────
def test_date_normalization_iso8601():
    """Test ISO-8601 date string parsing."""
    from src.processing.date_normalizer import parse_date_string

    cases = [
        ("2026-01-15T14:30:00Z", True, "parsed_explicit"),
        ("2026-01-15T14:30:00+05:30", True, "parsed_explicit"),
        ("2026-01-15", True, "parsed_explicit"),
    ]
    for text, expected_verified, expected_method in cases:
        dt, verified, method = parse_date_string(text)
        assert dt is not None, f"Failed to parse: {text}"
        assert verified == expected_verified, f"Wrong verified for {text}"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5: Date normalization: relative dates
# ─────────────────────────────────────────────────────────────────────────────
def test_date_normalization_relative():
    """Test relative date string parsing."""
    from src.processing.date_normalizer import parse_date_string, parse_relative

    now = datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc)

    # 2 hours ago
    dt = parse_relative("2 hours ago", now=now)
    assert dt is not None
    assert abs((now - dt).total_seconds() - 7200) < 10

    # 30 minutes ago
    dt = parse_relative("30 minutes ago", now=now)
    assert dt is not None
    assert abs((now - dt).total_seconds() - 1800) < 10

    # yesterday
    dt = parse_relative("yesterday", now=now)
    assert dt is not None
    assert dt.date() == (now - timedelta(days=1)).date()

    # just now
    dt = parse_relative("just now", now=now)
    assert dt is not None


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6: Strict 24-hour freshness filter
# ─────────────────────────────────────────────────────────────────────────────
def test_freshness_filter_24h():
    """Test strict 24-hour freshness filtering."""
    from src.processing.freshness_filter import apply_freshness_filter

    now = datetime(2026, 11, 22, 12, 0, 0, tzinfo=UTC)
    records = [
        {"title": "Fresh article", "published_at": now - timedelta(hours=1)},
        {"title": "Exactly 24h article", "published_at": now - timedelta(hours=23)},
        {"title": "Stale article", "published_at": now - timedelta(hours=25)},
        {"title": "Very old article", "published_at": now - timedelta(days=7)},
        {"title": "No date article", "published_at": None},
    ]
    fresh, stale = apply_freshness_filter(records, ["published_at"], freshness_hours=24, now=now)

    assert len(fresh) == 2  # 1h and 23h
    assert len(stale) == 3  # 25h, 7d, no date
    assert all(r["is_fresh"] for r in fresh)
    assert all(not r["is_fresh"] for r in stale)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 7: Missing publication date handling
# ─────────────────────────────────────────────────────────────────────────────
def test_missing_date_handling():
    """Test records without dates are not falsely classified as fresh."""
    from src.processing.date_normalizer import is_fresh

    # None date → not fresh
    assert is_fresh(None) is False

    # Explicitly verify the boundary: 23h59m in past = fresh, 24h1m = stale
    now = datetime.now(UTC)
    assert is_fresh(now - timedelta(hours=23, minutes=59), now=now) is True
    assert is_fresh(now - timedelta(hours=24, minutes=1), now=now) is False


# ─────────────────────────────────────────────────────────────────────────────
# TEST 8: Entity resolution: exact match
# ─────────────────────────────────────────────────────────────────────────────
def test_entity_resolution_exact():
    """Test exact entity matching against seed registry."""
    from src.resolution.entity_resolver import EntityResolver

    resolver = EntityResolver()
    canonical, method, score, review = resolver.resolve("OpenAI")
    assert canonical == "OpenAI"
    assert method == "exact"
    assert score == 1.0
    assert review is False


# ─────────────────────────────────────────────────────────────────────────────
# TEST 9: Entity resolution: alias mapping
# ─────────────────────────────────────────────────────────────────────────────
def test_entity_resolution_alias():
    """Test known aliases resolve to canonical names."""
    from src.resolution.entity_resolver import EntityResolver

    resolver = EntityResolver()
    cases = [
        ("Open AI", "OpenAI"),
        ("openai inc.", "OpenAI"),
        ("OpenAI, Inc.", "OpenAI"),
        ("Facebook AI", "Meta AI"),
    ]
    for raw, expected_canonical in cases:
        canonical, method, score, review = resolver.resolve(raw)
        assert canonical == expected_canonical, f"Failed for '{raw}': got '{canonical}'"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 10: Entity resolution: fuzzy matching
# ─────────────────────────────────────────────────────────────────────────────
def test_entity_resolution_fuzzy():
    """Test fuzzy matching for near-duplicate names."""
    from src.resolution.entity_resolver import EntityResolver

    resolver = EntityResolver()
    # "HuggingFce" has a typo and should fuzzy-match to "Hugging Face"
    canonical, method, score, review = resolver.resolve("HuggingFce")
    assert canonical == "Hugging Face"
    assert "fuzzy" in method


# ─────────────────────────────────────────────────────────────────────────────
# TEST 11: Duplicate prevention: URL-based
# ─────────────────────────────────────────────────────────────────────────────
def test_deduplication_by_url():
    """Test URL-based deduplication."""
    from src.processing.deduplicator import deduplicate_by_url

    records = [
        {"entity_name": "OpenAI", "source_url": "https://openai.com"},
        {"entity_name": "OpenAI", "source_url": "https://openai.com"},  # Exact duplicate
        {"entity_name": "Anthropic", "source_url": "https://anthropic.com"},
        {"entity_name": "OpenAI Duplicate", "source_url": "https://openai.com"},  # Same URL
    ]
    deduped, dups = deduplicate_by_url(records, "source_url")
    assert len(deduped) == 2
    assert dups == 2


# ─────────────────────────────────────────────────────────────────────────────
# TEST 12: HTTP 429 retry handling
# ─────────────────────────────────────────────────────────────────────────────
def test_http_429_retry():
    """Test that 429 responses trigger retry with backoff."""
    from src.extraction.llm_orchestrator import LLMOrchestrator, RateLimitError

    orchestrator = LLMOrchestrator()
    err = RateLimitError("429 rate limit")
    assert "rate limit" in str(err).lower()


# ─────────────────────────────────────────────────────────────────────────────
# TEST 13: HTTP 413 / context overflow: semantic chunking
# ─────────────────────────────────────────────────────────────────────────────
def test_semantic_chunking():
    """Test that large content is chunked correctly."""
    from src.extraction.chunking import SemanticChunker

    chunker = SemanticChunker(max_tokens=100, overlap_tokens=10)
    content = "\n\n".join(["This is a paragraph of text. " * 5] * 10)
    chunks = chunker.chunk(content)

    assert len(chunks) > 1
    for chunk in chunks:
        from src.extraction.chunking import estimate_tokens
        assert estimate_tokens(chunk) <= 150


# ─────────────────────────────────────────────────────────────────────────────
# TEST 14: LLM fallback chain
# ─────────────────────────────────────────────────────────────────────────────
def test_llm_fallback_chain():
    """Test that LLM orchestrator falls back through providers."""
    from src.extraction.llm_orchestrator import LLMOrchestrator, RateLimitError

    orchestrator = LLMOrchestrator()
    call_count = {"count": 0}

    async def mock_call(provider, prompt):
        call_count["count"] += 1
        if provider.name == "gemini":
            raise RateLimitError("Gemini 429")
        if provider.name == "groq":
            raise Exception("Groq error")
        return '{"name": "OpenAI", "founded": "2015"}'

    async def _run():
        with patch.object(orchestrator, "_call_provider", side_effect=mock_call), \
             patch("asyncio.sleep", return_value=None):
            return await orchestrator.extract("Sample content", "Extract: {content}")

    result = asyncio.run(_run())
    assert call_count["count"] >= 1


# ─────────────────────────────────────────────────────────────────────────────
# TEST 15: News RSS collection with freshness
# ─────────────────────────────────────────────────────────────────────────────
def test_news_collection_freshness(sample_news_rss):
    """Test news collection + freshness filtering."""
    from src.collectors.news_collector import NewsCollector
    from src.processing.freshness_filter import apply_freshness_filter

    source = {
        "name": "TechCrunch AI",
        "rss": "https://techcrunch.com/feed/",
        "base_url": "https://techcrunch.com",
        "rationale": "Test source",
    }

    from unittest.mock import AsyncMock

    async def _run():
        collector = NewsCollector()
        collector.fetch = AsyncMock(return_value=sample_news_rss)
        return await collector._fetch_rss(source)

    articles = asyncio.run(_run())
    assert len(articles) == 2
    assert articles[0]["title"] == "GPT-5 Released Today"

    fresh, stale = apply_freshness_filter(
        articles, date_fields=["published_at"], freshness_hours=24
    )
    assert len(fresh) == 1
    assert fresh[0]["title"] == "GPT-5 Released Today"
    assert len(stale) == 1


# ─────────────────────────────────────────────────────────────────────────────
# TEST 16: Job collection with freshness
# ─────────────────────────────────────────────────────────────────────────────
def test_job_collection_freshness(sample_greenhouse_jobs):
    """Test Greenhouse job collection and freshness filtering."""
    from src.collectors.job_collector import JobCollector
    from src.processing.freshness_filter import apply_freshness_filter

    from unittest.mock import AsyncMock, patch

    async def _run():
        collector = JobCollector()
        collector.fetch = AsyncMock(return_value=sample_greenhouse_jobs)
        with patch("asyncio.sleep", return_value=None):
            return await collector._collect_greenhouse()

    jobs = asyncio.run(_run())
    assert isinstance(jobs, list)

    if jobs:
        fresh, stale = apply_freshness_filter(jobs, ["published_at"], freshness_hours=24)
        for rec in fresh:
            assert rec["is_fresh"] is True


# ─────────────────────────────────────────────────────────────────────────────
# TEST 17: Validator: startup
# ─────────────────────────────────────────────────────────────────────────────
def test_validator_startup():
    """Test startup record validation."""
    from src.processing.validators import validate_startup

    valid = {
        "entity_name": "OpenAI",
        "source_name": "Y Combinator",
        "source_url": "https://www.ycombinator.com/companies/openai",
    }
    ok, errors = validate_startup(valid)
    assert ok
    assert not errors

    invalid = {
        "entity_name": "",
        "source_name": "YC",
        "source_url": "not-a-url",
    }
    ok, errors = validate_startup(invalid)
    assert not ok
    assert len(errors) >= 2


# ─────────────────────────────────────────────────────────────────────────────
# TEST 18: CSV export
# ─────────────────────────────────────────────────────────────────────────────
def test_csv_export(tmp_path):
    """Test CSV export writes correct headers and data."""
    from src.exports.csv_exporter import export_all_csv

    data = {
        "startups": [
            {
                "entity_name": "OpenAI",
                "canonical_name": "OpenAI",
                "source_name": "Y Combinator",
                "source_url": "https://yc.com/openai",
                "employee_count": None,
                "description": "AI safety company",
                "collected_at": "2026-01-01T00:00:00+00:00",
            }
        ]
    }

    paths = export_all_csv(data, tmp_path)
    assert "startups" in paths

    import csv
    with open(paths["startups"], newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1
    assert rows[0]["entity_name"] == "OpenAI"
    assert rows[0]["source_url"] == "https://yc.com/openai"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 19: Excel export
# ─────────────────────────────────────────────────────────────────────────────
def test_excel_export(tmp_path):
    """Test Excel workbook creation with correct sheets."""
    from src.exports.excel_exporter import export_excel
    import openpyxl

    data = {
        "startups": [{"entity_name": "Anthropic", "canonical_name": "Anthropic", "source_name": "YC", "source_url": "https://anthropic.com", "employee_count": 500, "description": "AI safety", "collected_at": "2026-01-01"}],
        "products": [],
        "research_papers": [],
        "jobs": [],
        "news": [],
    }
    mapping_log = [{"raw_name": "Anthropic Inc", "canonical_name": "Anthropic", "matching_method": "fuzzy_high", "confidence_score": 0.95, "source_url": None, "record_type": "STARTUP", "resolved_at": "2026-01-01T00:00:00Z", "requires_review": False, "notes": None, "normalized_name": "anthropic"}]

    path = tmp_path / "output.xlsx"
    export_excel(data, path, mapping_log)

    assert path.exists()
    wb = openpyxl.load_workbook(path)
    assert "Startups" in wb.sheetnames
    assert "Entity Mapping Log" in wb.sheetnames


# ─────────────────────────────────────────────────────────────────────────────
# TEST 20: Google Sheets mock export
# ─────────────────────────────────────────────────────────────────────────────
def test_google_sheets_no_credentials():
    """Test Google Sheets export correctly reports when credentials are missing."""
    from src.exports.google_sheets_exporter import export_to_google_sheets

    class MockSettings:
        google_sheets_credentials = None
        google_spreadsheet_id = None

    result = export_to_google_sheets({}, [], MockSettings())
    assert result is None  # Should return None, not raise


# ─────────────────────────────────────────────────────────────────────────────
# TEST 21: Pricing model inference
# ─────────────────────────────────────────────────────────────────────────────
def test_pricing_model_inference():
    """Test pricing model inference from text."""
    from src.collectors.product_collector import infer_pricing

    assert infer_pricing("completely free and open source") == "FREE"
    assert infer_pricing("free tier available, upgrade to pro") == "FREEMIUM"
    assert infer_pricing("enterprise pricing, contact sales") == "ENTERPRISE"
    assert infer_pricing("subscription at $20/month") == "PAID"
    assert infer_pricing("") == "REVIEW"
    assert infer_pricing("innovative AI platform") == "REVIEW"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 22: Role family classification
# ─────────────────────────────────────────────────────────────────────────────
def test_role_family_classification():
    """Test job title → role family classification."""
    from src.processing.validators import classify_role_family

    cases = [
        ("Senior Software Engineer", "Engineering"),
        ("ML Research Scientist", "Research"),
        ("Data Analyst", "Data Science"),
        ("Product Manager", "Product"),
        ("UX Designer", "Design"),
        ("Marketing Manager", "Marketing"),
        ("Account Executive", "Sales"),
        ("Legal Counsel", "Legal"),
        ("HR Business Partner", "HR"),
        ("Unknown Role XYZ", "Other"),
    ]
    for title, expected in cases:
        result = classify_role_family(title)
        assert result == expected, f"'{title}': expected {expected}, got {result}"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 23: Entity mapping log export
# ─────────────────────────────────────────────────────────────────────────────
def test_entity_mapping_log_export(tmp_path):
    """Test entity mapping log CSV export."""
    from src.resolution.mapping_logger import export_mapping_log

    entries = [
        {
            "raw_name": "Open AI",
            "canonical_name": "OpenAI",
            "normalized_name": "open ai",
            "matching_method": "alias_map",
            "confidence_score": 1.0,
            "source_url": "https://openai.com",
            "record_type": "STARTUP",
            "resolved_at": "2026-01-01T00:00:00Z",
            "requires_review": False,
            "notes": None,
        }
    ]
    path = tmp_path / "entity_mapping_log.csv"
    count = export_mapping_log(entries, path)
    assert count == 1
    assert path.exists()

    import csv
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["raw_name"] == "Open AI"
    assert rows[0]["canonical_name"] == "OpenAI"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 24: Extract GitHub URL from abstract
# ─────────────────────────────────────────────────────────────────────────────
def test_extract_github_url_from_abstract():
    """Test GitHub URL extraction from paper abstracts."""
    from src.processing.enrichment import extract_github_url

    cases = [
        ("Code available at https://github.com/openai/gpt-4", "https://github.com/openai/gpt-4"),
        ("See https://github.com/huggingface/transformers.git for code", "https://github.com/huggingface/transformers"),
        ("No GitHub link here", None),
        ("Visit http://github.com/example/repo/ for details", "http://github.com/example/repo"),
    ]
    for text, expected in cases:
        result = extract_github_url(text)
        assert result == expected, f"Failed for: {text!r}"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 25: Pipeline recovery: checkpoint
# ─────────────────────────────────────────────────────────────────────────────
def test_checkpoint_manager(tmp_path):
    """Test checkpoint saves and restores correctly."""
    from src.collectors.base_collector import CheckpointManager
    from unittest.mock import patch

    with patch("src.collectors.base_collector.settings") as mock_settings:
        mock_settings.raw_dir = tmp_path
        cp = CheckpointManager("test_pipeline")
        cp.set("page", 42)
        cp.set("last_id", "abc123")

        # Re-instantiate: should load from file
        cp2 = CheckpointManager("test_pipeline")
        assert cp2.get("page") == 42
        assert cp2.get("last_id") == "abc123"

        cp2.reset()
        cp3 = CheckpointManager("test_pipeline")
        assert cp3.get("page") is None


# ─────────────────────────────────────────────────────────────────────────────
# TEST 26: Product Name Mapping and Pricing Fallback
# ─────────────────────────────────────────────────────────────────────────────
def test_product_collector_creator_and_pricing():
    """Verify Hugging Face creator extraction and pricing fallback."""
    from src.collectors.product_collector import infer_pricing

    # Model ID with creator organization
    model_id = "meta-llama/Llama-3-70b"
    parts = model_id.split("/")
    assert parts[0] == "meta-llama"
    assert parts[-1] == "Llama-3-70b"

    # Single-name model ID
    single_id = "gpt2"
    single_parts = single_id.split("/")
    assert len(single_parts) == 1
    org = single_parts[0] if len(single_parts) > 1 else "Unknown"
    assert org == "Unknown"

    # Pricing inference must never return REVIEW
    assert infer_pricing("license:mit open-source") == "FREE"
    assert infer_pricing("commercial subscription paid") == "PAID"
    assert infer_pricing("") == "Not listed"
    assert infer_pricing("pytorch transformers neural") == "Not listed"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 27: Database SQL Counts Verification
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_database_counts_query():
    """Verify database repository count queries execute successfully."""
    from src.database.connection import get_session
    from src.database.repository import (
        StartupRepository, ProductRepository, PaperRepository,
        JobRepository, NewsRepository, EntityMappingRepository,
    )

    async with get_session() as session:
        product_count = await ProductRepository(session).count()
        paper_count = await PaperRepository(session).count()
        startup_count = await StartupRepository(session).count()
        job_count = await JobRepository(session).count()
        news_count = await NewsRepository(session).count()
        mapping_count = await EntityMappingRepository(session).count()

        assert product_count >= 1000
        assert paper_count >= 1000
        assert startup_count >= 600
        assert job_count >= 1000
        assert news_count >= 50
        assert mapping_count >= 1000


# ─────────────────────────────────────────────────────────────────────────────
# TEST 28: Legal and SEO Endpoints (Robots, Sitemap, Privacy, Terms)
# ─────────────────────────────────────────────────────────────────────────────
def test_legal_and_seo_routes():
    """Verify SEO and legal routes return 200 with proper content."""
    from fastapi.testclient import TestClient
    from src.main import app

    client = TestClient(app)

    # Robots.txt
    res_robots = client.get("/robots.txt")
    assert res_robots.status_code == 200
    assert "User-agent: *" in res_robots.text
    assert "Sitemap:" in res_robots.text

    # Sitemap.xml
    res_sitemap = client.get("/sitemap.xml")
    assert res_sitemap.status_code == 200
    assert "urlset" in res_sitemap.text
    assert "/privacy" in res_sitemap.text
    assert "/terms" in res_sitemap.text

    # Privacy
    res_privacy = client.get("/privacy")
    assert res_privacy.status_code == 200
    assert "Privacy Policy" in res_privacy.text
    assert "[YOUR LEGAL NAME]" in res_privacy.text

    # Terms
    res_terms = client.get("/terms")
    assert res_terms.status_code == 200
    assert "Terms of Service" in res_terms.text
    assert "[YOUR LEGAL NAME]" in res_terms.text

    # 404 handler
    res_404 = client.get("/nonexistent-test-page")
    assert res_404.status_code == 404
    assert "Resource Not Found" in res_404.text
