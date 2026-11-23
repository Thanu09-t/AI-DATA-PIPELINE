"""
Data synchronization script.
Normalizes fields across all intelligence datasets, writes clean JSON/CSV/Excel exports,
and populates the SQLite/PostgreSQL database so that database queries return live counts.
"""
from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path
from datetime import datetime, timezone

from src.config import settings
from src.database.connection import init_db, get_session
from src.database.repository import (
    StartupRepository, ProductRepository, PaperRepository,
    JobRepository, NewsRepository, EntityMappingRepository,
)
from src.exports.csv_exporter import export_all_csv
from src.exports.excel_exporter import export_excel
from src.exports.json_exporter import export_all_json

EXPORTS_DIR = settings.exports_dir


def normalize_pricing(p_val: str | None, tags: list | None = None) -> str:
    if not p_val or str(p_val).strip().upper() in ("REVIEW", "UNKNOWN", "NONE", ""):
        # Check if source tags explicitly state pricing
        if tags and isinstance(tags, list):
            tag_str = " ".join(str(t).lower() for t in tags)
            if any(k in tag_str for k in ["open-source", "free", "mit", "apache"]):
                return "FREE"
            if any(k in tag_str for k in ["commercial", "paid"]):
                return "PAID"
        return "Not listed"
    val = str(p_val).strip()
    if val.upper() in ("FREE", "FREEMIUM", "PAID", "ENTERPRISE"):
        return val.upper()
    return "Not listed"


async def main():
    print("1. Initializing database schema...")
    await init_db()

    print("2. Reading exported intelligence files...")
    with open(EXPORTS_DIR / "products.json", encoding="utf-8") as f:
        products = json.load(f)
    with open(EXPORTS_DIR / "research_papers.json", encoding="utf-8") as f:
        papers = json.load(f)
    with open(EXPORTS_DIR / "startups.json", encoding="utf-8") as f:
        startups = json.load(f)
    with open(EXPORTS_DIR / "jobs.json", encoding="utf-8") as f:
        jobs = json.load(f)
    with open(EXPORTS_DIR / "news.json", encoding="utf-8") as f:
        news = json.load(f)

    mappings_path = EXPORTS_DIR / "entity_mapping_log.csv"
    with open(mappings_path, encoding="utf-8") as f:
        mappings = list(csv.DictReader(f))

    print("3. Normalizing product records...")
    for p in products:
        url = p.get("source_url", "")
        existing_name = p.get("product_name") or p.get("entity_name") or ""
        tags = (p.get("extra_data") or {}).get("tags", []) if isinstance(p.get("extra_data"), dict) else []

        if "huggingface.co/spaces/" in url:
            slug = url.split("huggingface.co/spaces/")[-1].strip("/")
            parts = slug.split("/", 1)
            company = parts[0].strip() if len(parts) > 1 and parts[0].strip() else "Unknown"
            prod_name = parts[-1].strip() if parts[-1].strip() else existing_name
            source = "Hugging Face Spaces"
        elif "huggingface.co/" in url:
            slug = url.split("huggingface.co/")[-1].strip("/")
            parts = slug.split("/", 1)
            company = parts[0].strip() if len(parts) > 1 and parts[0].strip() else "Unknown"
            prod_name = parts[-1].strip() if parts[-1].strip() else existing_name
            source = "Hugging Face Models"
        elif "github.com/" in url:
            slug = url.split("github.com/")[-1].strip("/")
            parts = slug.split("/", 1)
            company = parts[0].strip() if len(parts) > 1 and parts[0].strip() else "Unknown"
            prod_name = parts[-1].strip() if parts[-1].strip() else existing_name
            source = "GitHub AI Tools"
        else:
            company = p.get("company_name") or p.get("startup_name") or "Unknown"
            prod_name = existing_name
            source = p.get("source_name") or "AI Product Directory"

        p["product_name"] = prod_name
        p["entity_name"] = prod_name
        p["company_name"] = company
        p["startup_name"] = company
        p["source_name"] = source
        p["pricing_model"] = normalize_pricing(p.get("pricing_model"), tags)

    print("4. Normalizing startups, papers, jobs, and news records...")
    for s in startups:
        name = s.get("startup_name") or s.get("entity_name") or s.get("canonical_name") or "Unknown"
        s["startup_name"] = name
        s["entity_name"] = name

    for p in papers:
        dt = p.get("published_date") or p.get("published_at")
        p["published_date"] = dt
        p["published_at"] = dt

    for j in jobs:
        url = j.get("source_url") or j.get("job_url") or ""
        j["source_url"] = url
        j["job_url"] = url
        is_fresh = bool(j.get("is_fresh") or j.get("is_fresh_24h"))
        j["is_fresh"] = is_fresh
        j["is_fresh_24h"] = is_fresh
        is_remote = bool(j.get("is_remote") or j.get("remote_eligible"))
        j["is_remote"] = is_remote
        j["remote_eligible"] = is_remote

    for n in news:
        url = n.get("source_url") or n.get("article_url") or ""
        n["source_url"] = url
        n["article_url"] = url
        is_fresh = bool(n.get("is_fresh") or n.get("is_fresh_24h"))
        n["is_fresh"] = is_fresh
        n["is_fresh_24h"] = is_fresh

    data = {
        "startups": startups,
        "products": products,
        "research_papers": papers,
        "jobs": jobs,
        "news": news,
    }

    print("5. Re-exporting normalized JSON and CSV files...")
    export_all_json(data, EXPORTS_DIR)
    export_all_csv(data, EXPORTS_DIR)
    excel_path = EXPORTS_DIR / "ai_intelligence_output.xlsx"
    export_excel(data, excel_path, mappings)

    print("6. Populating SQLite database...")
    async with get_session() as session:
        s_repo = StartupRepository(session)
        p_repo = ProductRepository(session)
        paper_repo = PaperRepository(session)
        j_repo = JobRepository(session)
        n_repo = NewsRepository(session)
        m_repo = EntityMappingRepository(session)

        # Batch insert Startups
        print(f"   Writing {len(startups)} startups to database...")
        s_records = []
        for s in startups:
            s_records.append({
                "id": s.get("id"),
                "entity_name": s["entity_name"],
                "startup_name": s["startup_name"],
                "canonical_name": s.get("canonical_name"),
                "source_name": s["source_name"],
                "source_url": s["source_url"],
                "employee_count": s.get("employee_count"),
                "description": s.get("description"),
                "extra_data": s.get("extra_data"),
            })
        await s_repo.bulk_upsert(s_records)

        # Batch insert Products
        print(f"   Writing {len(products)} products to database...")
        p_records = []
        for p in products:
            p_records.append({
                "id": p.get("id"),
                "entity_name": p["entity_name"],
                "product_name": p["product_name"],
                "startup_name": p["startup_name"],
                "company_name": p["company_name"],
                "pricing_model": p.get("pricing_model"),
                "source_name": p["source_name"],
                "source_url": p["source_url"],
                "description": p.get("description"),
                "extra_data": p.get("extra_data"),
            })
        await p_repo.bulk_upsert(p_records)

        # Batch insert Research Papers
        print(f"   Writing {len(papers)} papers to database...")
        paper_records = []
        for p in papers:
            paper_records.append({
                "id": p.get("id"),
                "title": p["title"],
                "authors": p.get("authors"),
                "paper_url": p["paper_url"],
                "arxiv_id": p.get("arxiv_id"),
                "abstract": p.get("abstract"),
                "github_url": p.get("github_url"),
                "github_stars": p.get("github_stars"),
                "github_enriched": bool(p.get("github_enriched")),
                "source_name": p.get("source_name", "arXiv"),
            })
        await paper_repo.bulk_upsert(paper_records)

        # Batch insert Jobs
        print(f"   Writing {len(jobs)} jobs to database...")
        j_records = []
        for j in jobs:
            j_records.append({
                "id": j.get("id"),
                "title": j["title"],
                "company": j.get("company"),
                "canonical_company": j.get("canonical_company"),
                "source_name": j["source_name"],
                "source_url": j["source_url"],
                "role_family": j.get("role_family"),
                "location": j.get("location"),
                "is_remote": bool(j.get("is_remote")),
                "is_fresh": bool(j.get("is_fresh")),
                "extra_data": j.get("extra_data"),
            })
        await j_repo.bulk_upsert(j_records)

        # Batch insert News
        print(f"   Writing {len(news)} news articles to database...")
        n_records = []
        for n in news:
            n_records.append({
                "id": n.get("id"),
                "title": n["title"],
                "source_name": n["source_name"],
                "source_url": n["source_url"],
                "is_fresh": bool(n.get("is_fresh")),
                "full_text": n.get("full_text"),
                "extra_data": n.get("extra_data"),
            })
        await n_repo.bulk_upsert(n_records)

        # Batch insert Entity Mappings
        print(f"   Writing {len(mappings)} entity mappings to database...")
        m_records = []
        for m in mappings:
            try:
                score = float(m.get("confidence_score") or 0.0)
            except ValueError:
                score = 0.0
            m_records.append({
                "raw_name": m["raw_name"],
                "canonical_name": m["canonical_name"],
                "matching_method": m.get("matching_method", "exact"),
                "confidence_score": score,
                "source_url": m.get("source_url"),
                "record_type": m.get("record_type", "PRODUCT"),
                "requires_review": m.get("requires_review") == "True",
                "notes": m.get("notes"),
            })
        await m_repo.bulk_log(m_records)

        await session.commit()

        # Query and verify database counts directly
        db_s = await s_repo.count()
        db_p = await p_repo.count()
        db_papers = await paper_repo.count()
        db_j = await j_repo.count()
        db_n = await n_repo.count()
        db_m = await m_repo.count()

        print("\n=======================================================")
        print("DATABASE COUNTS VERIFIED DIRECTLY FROM SQL QUERIES:")
        print(f"  Startups:        {db_s}")
        print(f"  Products:        {db_p}")
        print(f"  Research Papers: {db_papers}")
        print(f"  Jobs:            {db_j}")
        print(f"  News Articles:   {db_n}")
        print(f"  Entity Mappings: {db_m}")
        print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(main())
