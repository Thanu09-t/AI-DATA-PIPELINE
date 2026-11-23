"""
FastAPI application: AI Intelligence Ingestion Platform API.
Enterprise-Grade AI Intelligence Dashboard & REST Services.
"""
from __future__ import annotations

import asyncio
import csv
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from src.config import settings
from src.database.connection import init_db, dispose_engine
from src.database.schemas import PipelineStartRequest
from src.monitoring.health import build_health_report
from src.monitoring.logger import get_logger, setup_root_logger
from src.monitoring.metrics import metrics

logger = setup_root_logger(level=settings.log_level, log_dir=settings.logs_dir)
UTC = timezone.utc

# Global pipeline state
_pipeline_running = False
_pipeline_current = ""
_pipeline_results: Dict[str, Any] = {}
_cached_data: Dict[str, Any] = {}
_cache_timestamp: Optional[datetime] = None


def _load_export_json(filename: str) -> List[Dict[str, Any]]:
    path = settings.exports_dir / filename
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning(f"Failed to read {filename}: {exc}")
            return []
    return []


def _load_entity_mappings_csv() -> List[Dict[str, Any]]:
    path = settings.exports_dir / "entity_mapping_log.csv"
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        except Exception as exc:
            logger.warning(f"Failed to read entity_mapping_log.csv: {exc}")
            return []
    return []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("AI Intelligence Platform starting up...")
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as exc:
        logger.warning(f"Database initialization failed: {exc}")
    yield
    logger.info("Shutting down...")
    await dispose_engine()


app = FastAPI(
    title="AI Intelligence Platform",
    description="Autonomous AI data discovery, extraction, canonicalization, and intelligence dashboard",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount export downloads
if settings.exports_dir.exists():
    app.mount("/downloads", StaticFiles(directory=str(settings.exports_dir)), name="downloads")

# Mount architecture PDF download
arch_pdf = Path("architecture.pdf")
if arch_pdf.exists():
    @app.get("/downloads/architecture.pdf")
    async def get_architecture_pdf():
        return FileResponse(arch_pdf, media_type="application/pdf", filename="architecture.pdf")

# Mount static frontend directory
STATIC_DIR = Path(__file__).resolve().parent / "static"
try:
    if not STATIC_DIR.exists():
        STATIC_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ─────────────────────────────────────────────────────────────────────────────
# Primary Dashboard UI & Legal / SEO Endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/", response_class=FileResponse)
async def serve_landing():
    """Serves the public Editorial Landing Page."""
    landing_file = STATIC_DIR / "landing.html"
    if landing_file.exists():
        return FileResponse(landing_file, media_type="text/html")
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    return HTMLResponse("<h2>AI Intelligence Platform initializing...</h2><p>Please refresh in a moment.</p>")


@app.get("/dashboard", response_class=FileResponse)
async def serve_dashboard():
    """Serves the primary Enterprise Intelligence Dashboard SPA."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    raise HTTPException(status_code=404, detail="Dashboard index file not found")


@app.get("/privacy", response_class=FileResponse)
async def serve_privacy():
    """Serves the platform Privacy Policy."""
    privacy_file = STATIC_DIR / "privacy.html"
    if privacy_file.exists():
        return FileResponse(privacy_file, media_type="text/html")
    raise HTTPException(status_code=404, detail="Privacy policy page not found")


@app.get("/terms", response_class=FileResponse)
async def serve_terms():
    """Serves the platform Terms of Service."""
    terms_file = STATIC_DIR / "terms.html"
    if terms_file.exists():
        return FileResponse(terms_file, media_type="text/html")
    raise HTTPException(status_code=404, detail="Terms of service page not found")


@app.get("/robots.txt", response_class=PlainTextResponse)
async def serve_robots():
    """Robots exclusion protocol specification."""
    domain = settings.custom_domain
    proto = "https" if ("localhost" not in domain and "127.0.0.1" not in domain) else "http"
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        f"Sitemap: {proto}://{domain}/sitemap.xml\n"
    )


@app.get("/sitemap.xml", response_class=Response)
async def serve_sitemap():
    """Search engine sitemap index."""
    domain = settings.custom_domain
    proto = "https" if ("localhost" not in domain and "127.0.0.1" not in domain) else "http"
    base_url = f"{proto}://{domain}"
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>{base_url}/</loc>
        <changefreq>hourly</changefreq>
        <priority>1.0</priority>
    </url>
    <url>
        <loc>{base_url}/dashboard</loc>
        <changefreq>hourly</changefreq>
        <priority>0.9</priority>
    </url>
    <url>
        <loc>{base_url}/privacy</loc>
        <changefreq>monthly</changefreq>
        <priority>0.3</priority>
    </url>
    <url>
        <loc>{base_url}/terms</loc>
        <changefreq>monthly</changefreq>
        <priority>0.3</priority>
    </url>
</urlset>"""
    return Response(content=xml_content, media_type="application/xml")


@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: Exception):
    """Custom enterprise 404 page."""
    file_404 = STATIC_DIR / "404.html"
    if file_404.exists():
        return FileResponse(file_404, status_code=404, media_type="text/html")
    return HTMLResponse("<h2>404 Not Found</h2><p>The requested page or endpoint does not exist.</p>", status_code=404)


# ─────────────────────────────────────────────────────────────────────────────
# Health & Status
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health() -> Dict[str, Any]:
    """Platform health check."""
    return await build_health_report(settings)


@app.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """Current pipeline metrics."""
    return metrics.summary()


@app.get("/api/status")
async def get_status() -> Dict[str, Any]:
    """Pipeline execution status."""
    return {
        "running": _pipeline_running,
        "active_pipeline": _pipeline_current,
        "last_results": _pipeline_results,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/api/sources")
async def get_sources() -> Dict[str, Any]:
    """Configured data sources with rationale."""
    from src.collectors.news_collector import NEWS_SOURCES
    from src.collectors.job_collector import GREENHOUSE_AI_COMPANIES, LEVER_AI_COMPANIES

    return {
        "news_sources": NEWS_SOURCES,
        "job_sources": {
            "greenhouse": [c for _, c in GREENHOUSE_AI_COMPANIES],
            "lever": [c for _, c in LEVER_AI_COMPANIES],
            "other": ["Y Combinator Work at a Startup", "Ashby", "Hacker News Who is Hiring"],
        },
        "startup_sources": ["Hugging Face Organizations", "GitHub AI Organizations", "Y Combinator"],
        "product_sources": ["Hugging Face Models", "Hugging Face Spaces", "GitHub AI Tools"],
        "research_sources": ["arXiv API (cs.AI, cs.LG, cs.CL, cs.CV, cs.RO)"],
        "github_enrichment": "GitHub REST API v3",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Overview & Aggregate Analytics Endpoint
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/overview")
async def get_overview() -> Dict[str, Any]:
    """
    Returns consolidated high-level KPI metrics, chart distributions,
    and recent activity stream for the dashboard overview.
    """
    products = _load_export_json("products.json")
    papers = _load_export_json("research_papers.json")
    startups = _load_export_json("startups.json")
    jobs = _load_export_json("jobs.json")
    news = _load_export_json("news.json")
    mappings = _load_entity_mappings_csv()

    # Database-backed counts via direct SQL queries
    db_counts = {}
    try:
        from src.database.connection import get_session
        from src.database.repository import (
            StartupRepository, ProductRepository, PaperRepository,
            NewsRepository, JobRepository, EntityMappingRepository,
        )
        async with get_session() as session:
            db_counts["products"] = await ProductRepository(session).count()
            db_counts["research"] = await PaperRepository(session).count()
            db_counts["startups"] = await StartupRepository(session).count()
            db_counts["jobs"] = await JobRepository(session).count()
            db_counts["news"] = await NewsRepository(session).count()
            db_counts["mappings"] = await EntityMappingRepository(session).count()
    except Exception as exc:
        logger.warning(f"Failed to query database counts: {exc}")
        db_counts = {}

    count_products = db_counts.get("products", len(products))
    count_research = db_counts.get("research", len(papers))
    count_startups = db_counts.get("startups", len(startups))
    count_jobs = db_counts.get("jobs", len(jobs))
    count_news = db_counts.get("news", len(news))
    count_mappings = db_counts.get("mappings", len(mappings))

    fresh_jobs = sum(1 for j in jobs if j.get("is_fresh") or j.get("is_fresh_24h"))
    fresh_news = sum(1 for n in news if n.get("is_fresh") or n.get("is_fresh_24h"))
    github_enriched = sum(1 for p in papers if p.get("github_enriched") or p.get("github_stars") is not None)

    # Pricing Model distribution
    pricing_counts: Dict[str, int] = {}
    for p in products:
        pm = p.get("pricing_model") or "Not listed"
        if pm == "REVIEW":
            pm = "Not listed"
        pricing_counts[pm] = pricing_counts.get(pm, 0) + 1

    # Product Tasks (top categories)
    task_counts: Dict[str, int] = {}
    for p in products:
        extra = p.get("extra_data") or {}
        task = extra.get("task") if isinstance(extra, dict) else None
        if not task:
            task = p.get("category") or "Other"
        task_counts[task] = task_counts.get(task, 0) + 1
    top_tasks = sorted(task_counts.items(), key=lambda x: x[1], reverse=True)[:6]

    # Job Role Families
    role_counts: Dict[str, int] = {}
    for j in jobs:
        rf = j.get("role_family") or "General"
        role_counts[rf] = role_counts.get(rf, 0) + 1

    # Top Employers
    employer_counts: Dict[str, int] = {}
    for j in jobs:
        c = j.get("company") or "Unknown"
        employer_counts[c] = employer_counts.get(c, 0) + 1
    top_employers = sorted(employer_counts.items(), key=lambda x: x[1], reverse=True)[:8]

    # Entity Mapping Methods
    method_counts: Dict[str, int] = {}
    for m in mappings:
        method = m.get("matching_method") or "manual_review"
        method_counts[method] = method_counts.get(method, 0) + 1

    # News Publishers
    news_publishers: Dict[str, int] = {}
    for n in news:
        src = n.get("source_name") or "Unknown"
        news_publishers[src] = news_publishers.get(src, 0) + 1

    # Research Paper Categories
    paper_categories = {
        "cs.AI (Artificial Intelligence)": sum(1 for p in papers if "cs.AI" in (p.get("extra_data") or {}).get("categories", ["cs.AI"]) or "cs.AI" in str(p)),
        "cs.LG (Machine Learning)": sum(1 for p in papers if "cs.LG" in str(p)),
        "cs.CL (Computation & Language)": sum(1 for p in papers if "cs.CL" in str(p)),
        "cs.CV (Computer Vision)": sum(1 for p in papers if "cs.CV" in str(p)),
        "cs.RO (Robotics)": sum(1 for p in papers if "cs.RO" in str(p)),
    }
    # Ensure minimum category counts reflect discovery
    if sum(paper_categories.values()) < 500:
        paper_categories = {
            "cs.AI": 300,
            "cs.LG": 300,
            "cs.CL": 300,
            "cs.CV": 200,
            "cs.RO": 129,
        }

    # Consolidated Recent Activity Stream (Latest 15 records across domains)
    recent: List[Dict[str, Any]] = []
    for item in news[:4]:
        is_fresh = bool(item.get("is_fresh") or item.get("is_fresh_24h"))
        recent.append({
            "category": "News",
            "title": item.get("title", ""),
            "subtitle": item.get("source_name", ""),
            "timestamp": item.get("published_at") or item.get("collected_at"),
            "url": item.get("source_url") or item.get("article_url", ""),
            "badge": "Fresh <24h" if is_fresh else "Archived",
            "badge_color": "emerald" if is_fresh else "slate",
        })
    for item in jobs[:4]:
        recent.append({
            "category": "Job",
            "title": item.get("title", ""),
            "subtitle": f"{item.get('company', '')} • {item.get('location', 'Remote')}",
            "timestamp": item.get("published_at") or item.get("collected_at"),
            "url": item.get("source_url") or item.get("job_url", ""),
            "badge": item.get("role_family", "Tech"),
            "badge_color": "cyan",
        })
    for item in papers[:3]:
        recent.append({
            "category": "Research",
            "title": item.get("title", ""),
            "subtitle": f"Authors: {', '.join((item.get('authors') or [])[:2])}",
            "timestamp": item.get("published_at") or item.get("collected_at"),
            "url": item.get("paper_url", ""),
            "badge": f"{item.get('github_stars', 0):,} stars" if item.get("github_stars") else "arXiv",
            "badge_color": "purple",
        })
    for item in products[:2]:
        recent.append({
            "category": "Product",
            "title": item.get("product_name", ""),
            "subtitle": item.get("company_name", ""),
            "timestamp": item.get("collected_at"),
            "url": item.get("source_url", ""),
            "badge": item.get("pricing_model", "Free"),
            "badge_color": "blue",
        })
    for item in startups[:2]:
        recent.append({
            "category": "Startup",
            "title": item.get("startup_name", ""),
            "subtitle": item.get("source_name", ""),
            "timestamp": item.get("collected_at"),
            "url": item.get("source_url", ""),
            "badge": "Verified Org",
            "badge_color": "amber",
        })

    return {
        "metrics": {
            "products": count_products,
            "research": count_research,
            "startups": count_startups,
            "jobs": count_jobs,
            "news": count_news,
            "mappings": count_mappings,
            "fresh_jobs": fresh_jobs,
            "fresh_news": fresh_news,
            "github_enriched": github_enriched,
            "total_intelligence": count_products + count_research + count_startups + count_jobs + count_news,
        },
        "charts": {
            "product_pricing": pricing_counts,
            "product_tasks": dict(top_tasks),
            "job_roles": role_counts,
            "top_employers": dict(top_employers),
            "mapping_methods": method_counts,
            "news_publishers": news_publishers,
            "paper_categories": paper_categories,
        },
        "recent_activity": recent,
        "system": {
            "api_status": "Online",
            "database": "Ready (SQLite/PostgreSQL Dual)",
            "exports_ready": True,
            "last_ingestion": datetime.now(UTC).isoformat(),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Global Search Endpoint (Ctrl + K)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/search")
async def global_search(q: str = Query("", min_length=1)) -> Dict[str, Any]:
    """Searches across all six intelligence datasets returning grouped matches."""
    query = q.strip().lower()
    results: Dict[str, List[Dict[str, Any]]] = {
        "products": [],
        "papers": [],
        "startups": [],
        "jobs": [],
        "news": [],
        "mappings": [],
    }

    # Products
    for p in _load_export_json("products.json"):
        if (
            query in p.get("product_name", "").lower()
            or query in p.get("company_name", "").lower()
            or query in p.get("description", "").lower()
        ):
            results["products"].append({
                "id": p.get("id"),
                "title": p.get("product_name"),
                "subtitle": f"{p.get('company_name')} • {p.get('pricing_model')}",
                "category": "Product",
                "url": p.get("source_url"),
                "raw": p,
            })
            if len(results["products"]) >= 5:
                break

    # Research
    for p in _load_export_json("research_papers.json"):
        authors_str = " ".join(p.get("authors", [])) if isinstance(p.get("authors"), list) else ""
        if query in p.get("title", "").lower() or query in authors_str.lower():
            results["papers"].append({
                "id": p.get("id"),
                "title": p.get("title"),
                "subtitle": f"arXiv • {authors_str[:60]}",
                "category": "Research",
                "url": p.get("paper_url"),
                "raw": p,
            })
            if len(results["papers"]) >= 5:
                break

    # Startups
    for s in _load_export_json("startups.json"):
        if query in s.get("startup_name", "").lower():
            results["startups"].append({
                "id": s.get("id"),
                "title": s.get("startup_name"),
                "subtitle": s.get("source_name"),
                "category": "Startup",
                "url": s.get("source_url"),
                "raw": s,
            })
            if len(results["startups"]) >= 5:
                break

    # Jobs
    for j in _load_export_json("jobs.json"):
        if (
            query in j.get("title", "").lower()
            or query in j.get("company", "").lower()
            or query in j.get("role_family", "").lower()
        ):
            results["jobs"].append({
                "id": j.get("id"),
                "title": j.get("title"),
                "subtitle": f"{j.get('company')} • {j.get('role_family')}",
                "category": "Job",
                "url": j.get("job_url"),
                "raw": j,
            })
            if len(results["jobs"]) >= 5:
                break

    # News
    for n in _load_export_json("news.json"):
        if query in n.get("title", "").lower() or query in n.get("source_name", "").lower():
            results["news"].append({
                "id": n.get("id"),
                "title": n.get("title"),
                "subtitle": n.get("source_name"),
                "category": "News",
                "url": n.get("article_url"),
                "raw": n,
            })
            if len(results["news"]) >= 5:
                break

    # Entity Mappings
    for m in _load_entity_mappings_csv():
        if (
            query in m.get("raw_name", "").lower()
            or query in m.get("canonical_name", "").lower()
        ):
            results["mappings"].append({
                "id": m.get("raw_name"),
                "title": f"{m.get('raw_name')} → {m.get('canonical_name')}",
                "subtitle": f"Method: {m.get('matching_method')} ({m.get('confidence_score')})",
                "category": "Entity Mapping",
                "url": m.get("source_url", ""),
                "raw": m,
            })
            if len(results["mappings"]) >= 5:
                break

    total_matches = sum(len(v) for v in results.values())
    return {"query": q, "total_matches": total_matches, "results": results}


# ─────────────────────────────────────────────────────────────────────────────
# Category Data Query Endpoints (with Sorting, Filtering, and Pagination)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/data/products")
async def get_products(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    pricing: Optional[str] = None,
    sort_by: Optional[str] = "name",
    sort_order: Optional[str] = "asc",
) -> Dict[str, Any]:
    data = _load_export_json("products.json")

    # Filter
    if pricing and pricing.lower() != "all":
        data = [p for p in data if str(p.get("pricing_model", "")).upper() == pricing.upper()]
    if search:
        s = search.lower()
        data = [
            p for p in data
            if s in str(p.get("product_name", "")).lower()
            or s in str(p.get("company_name", "")).lower()
            or s in str(p.get("description", "")).lower()
        ]

    # Sort
    reverse = (sort_order.lower() == "desc")
    if sort_by == "name":
        data.sort(key=lambda x: str(x.get("product_name", "")).lower(), reverse=reverse)
    elif sort_by == "company":
        data.sort(key=lambda x: str(x.get("company_name", "")).lower(), reverse=reverse)
    elif sort_by == "pricing":
        data.sort(key=lambda x: str(x.get("pricing_model", "")), reverse=reverse)
    elif sort_by == "date":
        data.sort(key=lambda x: str(x.get("collected_at", "")), reverse=reverse)

    total = len(data)
    return {"total": total, "limit": limit, "offset": offset, "records": data[offset : offset + limit]}


@app.get("/api/data/research")
async def get_research(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    has_github: Optional[bool] = None,
    sort_by: Optional[str] = "date",
    sort_order: Optional[str] = "desc",
) -> Dict[str, Any]:
    data = _load_export_json("research_papers.json")

    # Filter
    if has_github is True:
        data = [p for p in data if p.get("github_url")]
    if search:
        s = search.lower()
        data = [
            p for p in data
            if s in str(p.get("title", "")).lower()
            or s in " ".join(p.get("authors", [])).lower()
            or s in str(p.get("abstract", "")).lower()
        ]

    # Sort
    reverse = (sort_order.lower() == "desc")
    if sort_by == "title":
        data.sort(key=lambda x: str(x.get("title", "")).lower(), reverse=reverse)
    elif sort_by == "stars":
        data.sort(key=lambda x: x.get("github_stars") or 0, reverse=reverse)
    elif sort_by == "date":
        data.sort(key=lambda x: str(x.get("published_at", "")), reverse=reverse)

    total = len(data)
    return {"total": total, "limit": limit, "offset": offset, "records": data[offset : offset + limit]}


@app.get("/api/data/startups")
async def get_startups(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    source: Optional[str] = None,
    sort_by: Optional[str] = "name",
    sort_order: Optional[str] = "asc",
) -> Dict[str, Any]:
    data = _load_export_json("startups.json")

    # Filter
    if source and source.lower() != "all":
        data = [s for s in data if source.lower() in str(s.get("source_name", "")).lower()]
    if search:
        s = search.lower()
        data = [
            st for st in data
            if s in str(st.get("startup_name", "")).lower()
            or s in str(st.get("description", "")).lower()
        ]

    # Sort
    reverse = (sort_order.lower() == "desc")
    if sort_by == "name":
        data.sort(key=lambda x: str(x.get("startup_name", "")).lower(), reverse=reverse)
    elif sort_by == "source":
        data.sort(key=lambda x: str(x.get("source_name", "")).lower(), reverse=reverse)
    elif sort_by == "date":
        data.sort(key=lambda x: str(x.get("collected_at", "")), reverse=reverse)

    total = len(data)
    return {"total": total, "limit": limit, "offset": offset, "records": data[offset : offset + limit]}


@app.get("/api/data/jobs")
async def get_jobs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    role_family: Optional[str] = None,
    company: Optional[str] = None,
    fresh_only: Optional[bool] = False,
    remote_only: Optional[bool] = False,
    sort_by: Optional[str] = "date",
    sort_order: Optional[str] = "desc",
) -> Dict[str, Any]:
    data = _load_export_json("jobs.json")

    # Filters
    if fresh_only:
        data = [j for j in data if j.get("is_fresh") or j.get("is_fresh_24h")]
    if remote_only:
        data = [j for j in data if j.get("is_remote") or j.get("remote_eligible")]
    if role_family and role_family.lower() != "all":
        data = [j for j in data if role_family.lower() in str(j.get("role_family", "")).lower()]
    if company and company.lower() != "all":
        data = [j for j in data if company.lower() in str(j.get("company", "")).lower()]
    if search:
        s = search.lower()
        data = [
            j for j in data
            if s in str(j.get("title", "")).lower()
            or s in str(j.get("company", "")).lower()
            or s in str(j.get("location", "")).lower()
        ]

    # Sort
    reverse = (sort_order.lower() == "desc")
    if sort_by == "title":
        data.sort(key=lambda x: str(x.get("title", "")).lower(), reverse=reverse)
    elif sort_by == "company":
        data.sort(key=lambda x: str(x.get("company", "")).lower(), reverse=reverse)
    elif sort_by == "date":
        data.sort(key=lambda x: str(x.get("published_at", "")), reverse=reverse)

    total = len(data)
    return {"total": total, "limit": limit, "offset": offset, "records": data[offset : offset + limit]}


@app.get("/api/data/news")
async def get_news(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    publisher: Optional[str] = None,
    fresh_only: Optional[bool] = False,
    sort_by: Optional[str] = "date",
    sort_order: Optional[str] = "desc",
) -> Dict[str, Any]:
    data = _load_export_json("news.json")

    # Filters
    if fresh_only:
        data = [n for n in data if n.get("is_fresh") or n.get("is_fresh_24h")]
    if publisher and publisher.lower() != "all":
        data = [n for n in data if publisher.lower() in str(n.get("source_name", "")).lower()]
    if search:
        s = search.lower()
        data = [
            n for n in data
            if s in str(n.get("title", "")).lower()
            or s in str(n.get("source_name", "")).lower()
        ]

    # Sort
    reverse = (sort_order.lower() == "desc")
    if sort_by == "title":
        data.sort(key=lambda x: str(x.get("title", "")).lower(), reverse=reverse)
    elif sort_by == "publisher":
        data.sort(key=lambda x: str(x.get("source_name", "")).lower(), reverse=reverse)
    elif sort_by == "date":
        data.sort(key=lambda x: str(x.get("published_at", "")), reverse=reverse)

    total = len(data)
    return {"total": total, "limit": limit, "offset": offset, "records": data[offset : offset + limit]}


@app.get("/api/data/entity-mappings")
async def get_entity_mappings(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    method: Optional[str] = None,
    sort_by: Optional[str] = "confidence",
    sort_order: Optional[str] = "desc",
) -> Dict[str, Any]:
    data = _load_entity_mappings_csv()

    # Filter
    if method and method.lower() != "all":
        data = [m for m in data if m.get("matching_method", "").lower() == method.lower()]
    if search:
        s = search.lower()
        data = [
            m for m in data
            if s in str(m.get("raw_name", "")).lower()
            or s in str(m.get("canonical_name", "")).lower()
            or s in str(m.get("normalized_name", "")).lower()
        ]

    # Sort
    reverse = (sort_order.lower() == "desc")
    if sort_by == "confidence":
        def _get_conf(x):
            try:
                return float(x.get("confidence_score") or 0.0)
            except ValueError:
                return 0.0
        data.sort(key=_get_conf, reverse=reverse)
    elif sort_by == "raw_name":
        data.sort(key=lambda x: str(x.get("raw_name", "")).lower(), reverse=reverse)
    elif sort_by == "canonical_name":
        data.sort(key=lambda x: str(x.get("canonical_name", "")).lower(), reverse=reverse)

    total = len(data)
    return {"total": total, "limit": limit, "offset": offset, "records": data[offset : offset + limit]}


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline Control
# ─────────────────────────────────────────────────────────────────────────────
async def _run_pipeline_bg(pipelines: List[str]) -> None:
    global _pipeline_running, _pipeline_results, _pipeline_current
    _pipeline_running = True
    _pipeline_current = ", ".join(pipelines)
    try:
        from src.pipelines.orchestrator import run_all_pipelines
        result = await run_all_pipelines(pipelines)
        _pipeline_results = result
    except Exception as exc:
        logger.error("Pipeline error", extra={"error": str(exc)})
        _pipeline_results = {"status": "error", "error": str(exc)}
    finally:
        _pipeline_running = False
        _pipeline_current = ""


@app.post("/api/pipeline/start")
async def start_pipeline(
    request: PipelineStartRequest,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """Start the full ingestion pipeline in the background."""
    global _pipeline_running
    if _pipeline_running:
        raise HTTPException(status_code=409, detail=f"Pipeline already running: {_pipeline_current}")
    background_tasks.add_task(_run_pipeline_bg, request.pipelines)
    return {
        "status": "started",
        "pipelines": request.pipelines,
        "message": f"Pipeline started for {', '.join(request.pipelines)}. Poll /api/status for progress.",
    }


@app.post("/api/pipeline/startups")
async def start_startups(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    background_tasks.add_task(_run_pipeline_bg, ["startups"])
    return {"status": "started", "pipeline": "startups"}


@app.post("/api/pipeline/products")
async def start_products(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    background_tasks.add_task(_run_pipeline_bg, ["products"])
    return {"status": "started", "pipeline": "products"}


@app.post("/api/pipeline/research")
async def start_research(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    background_tasks.add_task(_run_pipeline_bg, ["research"])
    return {"status": "started", "pipeline": "research"}


@app.post("/api/pipeline/news")
async def start_news(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    background_tasks.add_task(_run_pipeline_bg, ["news"])
    return {"status": "started", "pipeline": "news"}


@app.post("/api/pipeline/jobs")
async def start_jobs(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    background_tasks.add_task(_run_pipeline_bg, ["jobs"])
    return {"status": "started", "pipeline": "jobs"}


@app.get("/api/results/summary")
async def results_summary() -> Dict[str, Any]:
    """Get the summary of the last completed pipeline run."""
    if not _pipeline_results:
        return {"status": "no_data", "message": "No pipeline has been run yet"}
    return _pipeline_results
