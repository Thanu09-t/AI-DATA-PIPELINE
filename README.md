<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f172a,55:1e1b4b,100:6d28d9&height=200&section=header&text=AI%20Intelligence%20Ingestion&fontSize=44&fontColor=ffffff&fontAlignY=40&desc=Discover%20%C2%B7%20Extract%20%C2%B7%20Resolve%20%C2%B7%20Enrich%20%C2%B7%20Store&descSize=16&descAlignY=62" width="100%" alt="AI Intelligence Ingestion Platform" />

### A production-grade data intelligence platform for the AI ecosystem

*Discovers, extracts, normalizes, enriches, deduplicates and stores information about AI startups, products, research papers, jobs and news, at scale.*

<br/>

![Python](https://img.shields.io/badge/Python-3.11+-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?style=for-the-badge&logo=celery&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-0db7ed?style=for-the-badge&logo=docker&logoColor=white)

![Tests](https://img.shields.io/badge/tests-25_automated-22c55e?style=flat-square)
![Scale](https://img.shields.io/badge/scale-500k%2B_records-6d28d9?style=flat-square)
![Endpoints](https://img.shields.io/badge/REST_endpoints-11-0ea5e9?style=flat-square)
![Compliance](https://img.shields.io/badge/anti--bot-compliant-f59e0b?style=flat-square)

</div>

<br/>

## Contents

[Capabilities](#capabilities) · [Architecture](#architecture) · [Technology Stack](#technology-stack) · [Project Structure](#project-structure) · [Quick Start](#quick-start) · [Installation](#installation) · [Running](#running-the-platform) · [API](#api-reference) · [Testing](#testing) · [Exports](#exports) · [Docker](#docker-deployment) · [Troubleshooting](#troubleshooting) · [Scalability](#scalability) · [Source Availability](#source-availability) · [Engineering Decisions](#engineering-decisions)

---

## Capabilities

| | Capability | Implementation |
|:-:|:--|:--|
| 🌐 | **Multi-source ingestion** | arXiv API, YC Algolia, HF API, GitHub API, 5 RSS feeds, 5 job board APIs |
| ⚡ | **Async concurrency** | `aiohttp` + `asyncio` with configurable worker limits |
| 🧠 | **LLM extraction fallback** | Gemini Flash → Groq Llama 3 → DeepSeek, guarded by circuit breakers |
| 🕐 | **24-hour freshness** | Strict UTC-based filtering with a verified / inferred distinction |
| 🧬 | **Entity resolution** | Deterministic pipeline: normalization → aliases → fuzzy matching → semantic |
| ⭐ | **GitHub enrichment** | Automatic star-count retrieval from paper abstracts |
| ♻️ | **Deduplication** | URL-hash + fuzzy-name dedup with idempotent DB upserts |
| 🛡️ | **Anti-bot compliance** | Detects and reports protected sources; no bypass attempted |
| 📤 | **Full exports** | Google Sheets (6 tabs), CSV, JSON, Excel |
| 🔌 | **REST API** | FastAPI endpoints for pipeline control and monitoring |
| 🔁 | **Resumable** | Checkpoint-based recovery, restart from the point of interruption |

---

## Architecture

```mermaid
flowchart LR
    subgraph SRC["Sources"]
        A1[arXiv]:::src
        A2[YC Algolia]:::src
        A3[HF / GitHub]:::src
        A4[RSS Feeds]:::src
        A5[Job Boards]:::src
    end

    SRC --> C["Async Collectors<br/>rate limit · retry · checkpoints"]
    C --> L["LLM Orchestrator<br/>Gemini → Groq → DeepSeek"]
    L --> R["Entity Resolution<br/>normalize · alias · fuzzy · semantic"]
    R --> P["Processing<br/>dates · dedup · validate · freshness"]
    P --> D[("PostgreSQL<br/>+ ChromaDB")]
    D --> E["Exports<br/>Sheets · CSV · JSON · Excel"]

    API["FastAPI"] -. controls .-> C
    CEL["Celery + Redis"] -. distributes .-> C

    classDef src fill:#1e1b4b,stroke:#6d28d9,color:#fff;
```

See [`docs/architecture.md`](docs/architecture.md) for the full design.

---

## Technology Stack

| Layer | Technologies |
|:--|:--|
| **Backend** | Python 3.11+, FastAPI, asyncio, aiohttp, Playwright, Pydantic v2, BeautifulSoup4, lxml |
| **AI & LLM** | Google Gemini Flash (primary), Groq Llama 3-70b (secondary), DeepSeek Chat (tertiary), configurable multi-provider fallback with circuit breakers |
| **Data Processing** | Pandas, NumPy, RapidFuzz, python-dateutil, Tenacity |
| **Database** | PostgreSQL with SQLAlchemy async (primary), Redis (caching, rate limiting, Celery broker), ChromaDB (semantic entity matching) |
| **Background Jobs** | Celery distributed task queue, Redis broker |
| **Export** | Google Sheets API (gspread + service account), CSV, JSON, Excel (openpyxl) |

---

## Project Structure

<details>
<summary><b>Expand full repository tree</b></summary>

```
ai-intelligence-ingestion/
├── src/
│   ├── main.py                    # FastAPI app
│   ├── config.py                  # Settings (pydantic-settings)
│   ├── collectors/                # Async data collectors
│   │   ├── base_collector.py      # Rate limiting, retry, checkpoints
│   │   ├── startup_collector.py   # YC, HF, GitHub orgs
│   │   ├── product_collector.py   # HF Models, Spaces, GitHub tools
│   │   ├── research_collector.py  # arXiv API
│   │   ├── github_collector.py    # GitHub stars enrichment
│   │   ├── news_collector.py      # 5 RSS sources
│   │   ├── job_collector.py       # Greenhouse, Lever, YC, Ashby, HN
│   │   └── browser_collector.py   # Playwright fallback
│   ├── extraction/                # LLM extraction
│   │   ├── llm_orchestrator.py    # Fallback chain + circuit breaker
│   │   ├── gemini_provider.py
│   │   ├── groq_provider.py
│   │   ├── deepseek_provider.py
│   │   ├── structured_extractor.py
│   │   └── chunking.py            # Semantic text chunking
│   ├── resolution/                # Entity resolution
│   │   ├── entity_resolver.py     # Full resolution pipeline
│   │   ├── canonical_registry.py
│   │   ├── fuzzy_matcher.py
│   │   └── mapping_logger.py
│   ├── processing/                # Data processing
│   │   ├── date_normalizer.py
│   │   ├── deduplicator.py
│   │   ├── validators.py
│   │   ├── enrichment.py
│   │   └── freshness_filter.py
│   ├── database/                  # Persistence
│   │   ├── models.py              # SQLAlchemy ORM models
│   │   ├── schemas.py             # Pydantic schemas
│   │   ├── connection.py          # Async engine
│   │   └── repository.py          # CRUD operations
│   ├── pipelines/                 # Pipeline orchestration
│   │   ├── startup_pipeline.py
│   │   ├── product_pipeline.py
│   │   ├── research_pipeline.py
│   │   ├── news_pipeline.py
│   │   ├── jobs_pipeline.py
│   │   └── orchestrator.py        # Master coordinator
│   ├── exports/                   # Data export
│   │   ├── csv_exporter.py
│   │   ├── json_exporter.py
│   │   ├── excel_exporter.py
│   │   └── google_sheets_exporter.py
│   ├── monitoring/                # Observability
│   │   ├── logger.py              # Structured JSON logging
│   │   ├── metrics.py             # In-process metrics
│   │   └── health.py              # Health checks
│   └── api/                       # FastAPI routes
├── tests/
│   └── test_pipeline.py           # 25 automated tests
├── data/
│   ├── raw/                       # Checkpoint files
│   ├── processed/
│   ├── exports/                   # CSV, JSON, Excel outputs
│   └── logs/
├── scripts/
│   ├── run_all.py                 # Run all pipelines
│   ├── run_startups.py
│   ├── run_products.py
│   ├── run_research.py
│   ├── run_news.py
│   └── run_jobs.py
├── docs/
│   └── architecture.md
├── .env.example
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

</details>

---

## Quick Start

```bash
git clone <your-repo-url> && cd ai-intelligence-ingestion
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add your API keys
echo "USE_SQLITE_FALLBACK=1" >> .env   # optional: no Postgres/Redis needed
python scripts/run_all.py
```

> [!TIP]
> Local development works with **zero infrastructure**. Set `USE_SQLITE_FALLBACK=1` and the platform uses SQLite and skips Redis automatically.

---

## Installation

**Prerequisites**

| Requirement | Version | Notes |
|:--|:--|:--|
| Python | 3.11+ | Python 3.14 also works |
| PostgreSQL | 14+ | Optional, SQLite fallback available for local dev |
| Redis | 6+ | Optional, required only for Celery distributed workers |

<details open>
<summary><b>1 · Clone & create environment</b></summary>

<br/>

**PowerShell (Windows)**
```powershell
cd "AI PIPELINE\ai-intelligence-ingestion"
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Terminal (Linux / macOS)**
```bash
cd ai-intelligence-ingestion
python -m venv .venv
source .venv/bin/activate
```
</details>

<details>
<summary><b>2 · Install dependencies</b></summary>

<br/>

```bash
pip install -r requirements.txt
```

Optional, only for JS-rendered sources:
```bash
playwright install chromium
```
</details>

<details>
<summary><b>3 · Configure environment</b></summary>

<br/>

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required for full functionality:
```env
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
DEEPSEEK_API_KEY=your_key_here
GITHUB_TOKEN=your_token_here
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_intelligence
REDIS_URL=redis://localhost:6379/0
```

Local development without PostgreSQL / Redis:
```env
USE_SQLITE_FALLBACK=1
```
</details>

<details>
<summary><b>4 · Database setup</b></summary>

<br/>

```powershell
# Start PostgreSQL and Redis (or use Docker)
docker compose up postgres redis -d

# Tables are auto-created on first run.
# For production, use Alembic:
alembic upgrade head
```
</details>

<details>
<summary><b>5 · Google Sheets setup (optional)</b></summary>

<br/>

1. Create a Google Cloud project
2. Enable the **Sheets API** and **Drive API**
3. Create a service account and download the JSON credentials
4. Set in `.env`:
   ```env
   GOOGLE_SHEETS_CREDENTIALS=credentials/google_sheets_credentials.json
   ```
5. Leave `GOOGLE_SPREADSHEET_ID` blank to auto-create a spreadsheet
</details>

---

## Running the Platform

**Run all pipelines**

```bash
python scripts/run_all.py            # Linux / macOS
python scripts\run_all.py            # Windows
```

**Run a single pipeline**

| Command | Scope |
|:--|:--|
| `python scripts/run_startups.py` | Startup collection only |
| `python scripts/run_products.py` | Product collection only |
| `python scripts/run_research.py` | Research papers only |
| `python scripts/run_news.py` | News articles only |
| `python scripts/run_jobs.py` | Jobs only |

**Start the API server**

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## API Reference

| Method | Endpoint | Description |
|:-:|:--|:--|
| `GET` | `/health` | Platform health check |
| `GET` | `/metrics` | Pipeline metrics |
| `GET` | `/api/status` | Current pipeline status |
| `POST` | `/api/pipeline/start` | Start all pipelines |
| `POST` | `/api/pipeline/startups` | Start startup pipeline |
| `POST` | `/api/pipeline/products` | Start product pipeline |
| `POST` | `/api/pipeline/research` | Start research pipeline |
| `POST` | `/api/pipeline/news` | Start news pipeline |
| `POST` | `/api/pipeline/jobs` | Start jobs pipeline |
| `GET` | `/api/results/summary` | Last run results |
| `GET` | `/api/sources` | Configured sources |

**Example: start all pipelines**

```bash
curl -X POST http://localhost:8000/api/pipeline/start \
  -H "Content-Type: application/json" \
  -d '{"pipelines": ["startups", "products", "research", "news", "jobs"]}'
```

---

## Testing

```bash
pytest tests/ -v                                          # all tests
pytest tests/ -v --cov=src --cov-report=term-missing      # with coverage
pytest tests/test_pipeline.py::test_freshness_filter_24h -v   # single test
```

> [!NOTE]
> Tests do not require real API credentials. All HTTP calls are mocked.

---

## Exports

After a run, outputs are written to `data/exports/`:

| File | Contents |
|:--|:--|
| `startups.csv` | Startup records |
| `products.csv` | Product records |
| `research_papers.csv` | Research papers + GitHub metrics |
| `jobs.csv` | All collected jobs |
| `news.csv` | All collected news |
| `entity_mapping_log.csv` | Entity resolution decisions |
| `ai_intelligence_output.xlsx` | Combined Excel workbook (6 sheets) |

When Google Sheets is configured, the spreadsheet URL is printed to the console and returned in `/api/results/summary`.

---

## Docker Deployment

```bash
docker compose up -d                 # start all services
docker compose logs -f api           # follow API logs

curl -X POST http://localhost:8000/api/pipeline/start \
  -H "Content-Type: application/json" \
  -d '{"pipelines": ["startups", "products", "research", "news", "jobs"]}'
```

---

## Troubleshooting

| Problem | Solution |
|:--|:--|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| DB connection failed | Set `USE_SQLITE_FALLBACK=1` in `.env` for local dev |
| `asyncpg.exceptions.TooManyConnectionsError` | Reduce `DB_POOL_SIZE` in `.env` |
| arXiv rate limit | Increase sleep between requests in `research_collector.py` |
| GitHub 403 | Add `GITHUB_TOKEN` to `.env` |
| All LLM providers unavailable | Check API keys in `.env` |
| Google Sheets 403 | Verify the service account has edit access to the spreadsheet |
| Playwright not found | Run `playwright install chromium` |

---

## Scalability

Designed to scale to **500,000+ records**:

- **Horizontal Celery workers**: each processes independent source batches
- **Connection pooling**: PostgreSQL pool size configurable via `DB_POOL_SIZE`
- **Distributed rate limiting**: Redis prevents API quota violations across workers
- **Checkpoint recovery**: workers resume from the last successful position after a restart
- **Tunable batching**: configurable `BATCH_SIZE` in `.env`

---

## Source Availability

| Source | Status | Notes |
|:--|:-:|:--|
| arXiv | ✅ Full | Official API, no auth required |
| GitHub API | ✅ Full | Public API; 60 req/hr without a token, 5,000/hr with one |
| Greenhouse / Lever / Ashby | ✅ Full | Public job board APIs |
| RSS Feeds | ✅ Full | TechCrunch, VentureBeat, MIT TR, The Decoder, MarkTechPost |
| Papers with Code | ✅ Included | Public API endpoints used where accessible |
| Wellfound | ⚠️ Limited | Cloudflare protection, no bypass; uses YC API instead |
| Product Hunt | ⚠️ Paid | Requires a paid API key, not included; uses HF / GitHub instead |
| Crunchbase | ⚠️ Paid | Licensed data only; uses YC Algolia as a free alternative |

---

## Engineering Decisions

1. **SQLite fallback**: local development without PostgreSQL infrastructure
2. **In-process metrics**: thread-safe counters avoid a Redis dependency for basic monitoring
3. **arXiv rate limit**: 3.5 s between requests, below arXiv's recommended limit
4. **GitHub enrichment**: papers without GitHub URLs are stored un-enriched, never discarded
5. **Pricing model**: a `REVIEW` flag is used when evidence is insufficient, never guessed
6. **Entity resolution**: never merges entities below the 90% fuzzy threshold automatically
7. **Fresh date classification**: records without verifiable dates are classified `is_fresh = False`

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:6d28d9,55:1e1b4b,100:0f172a&height=100&section=footer" width="100%" alt="footer" />

<sub>Built for reliable, compliant, large-scale AI data intelligence.</sub>

</div>
