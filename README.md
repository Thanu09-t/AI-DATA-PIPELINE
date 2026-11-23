# AI Intelligence Ingestion Platform

> **Production-grade AI data intelligence platform**: discovers, extracts, normalizes, enriches, deduplicates, and stores information about AI startups, products, research papers, jobs, and news at scale.

---

## Key Capabilities

| Capability | Implementation |
|---|---|
| **Multi-source ingestion** | arXiv API, YC Algolia, HF API, GitHub API, 5 RSS feeds, 5 job board APIs |
| **Async concurrency** | `aiohttp` + `asyncio` with configurable worker limits |
| **LLM extraction fallback** | Gemini Flash → Groq Llama 3 → DeepSeek with circuit breakers |
| **24-hour freshness** | Strict UTC-based filtering with verified/inferred distinction |
| **Entity resolution** | Deterministic pipeline: normalization → aliases → fuzzy matching → semantic |
| **GitHub enrichment** | Automatic star count retrieval from paper abstracts |
| **Deduplication** | URL-hash + fuzzy name dedup, idempotent DB upserts |
| **Anti-bot compliance** | Detects and reports protected sources: no bypass attempted |
| **Full exports** | Google Sheets (6 tabs) + CSV + JSON + Excel |
| **REST API** | FastAPI with 10 endpoints for pipeline control and monitoring |
| **Resumable** | Checkpoint-based recovery: restart from interruption |

---

## Technology Stack

### Backend
- Python 3.11+, FastAPI, asyncio, aiohttp, Playwright
- Pydantic v2, BeautifulSoup4, lxml

### AI & LLM
- Google Gemini Flash (primary)
- Groq Llama 3-70b (secondary)
- DeepSeek Chat (tertiary)
- Configurable multi-provider fallback with circuit breakers

### Data Processing
- Pandas, NumPy, RapidFuzz, python-dateutil, Tenacity

### Database
- PostgreSQL (primary) with SQLAlchemy async
- Redis (caching, rate limiting, Celery broker)
- ChromaDB (semantic entity matching)

### Background Processing
- Celery distributed task queue
- Redis broker

### Export
- Google Sheets API (gspread + service account)
- CSV, JSON, Excel (openpyxl)

---

## Project Structure

```
ai-intelligence-ingestion/
├── src/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Settings (pydantic-settings)
│   ├── collectors/             # Async data collectors
│   │   ├── base_collector.py   # Rate limiting, retry, checkpoints
│   │   ├── startup_collector.py # YC, HF, GitHub orgs
│   │   ├── product_collector.py # HF Models, Spaces, GitHub tools
│   │   ├── research_collector.py # arXiv API
│   │   ├── github_collector.py  # GitHub stars enrichment
│   │   ├── news_collector.py    # 5 RSS sources
│   │   ├── job_collector.py     # Greenhouse, Lever, YC, Ashby, HN
│   │   └── browser_collector.py # Playwright fallback
│   ├── extraction/             # LLM extraction
│   │   ├── llm_orchestrator.py # Fallback chain + circuit breaker
│   │   ├── gemini_provider.py
│   │   ├── groq_provider.py
│   │   ├── deepseek_provider.py
│   │   ├── structured_extractor.py
│   │   └── chunking.py         # Semantic text chunking
│   ├── resolution/             # Entity resolution
│   │   ├── entity_resolver.py  # Full resolution pipeline
│   │   ├── canonical_registry.py
│   │   ├── fuzzy_matcher.py
│   │   └── mapping_logger.py
│   ├── processing/             # Data processing
│   │   ├── date_normalizer.py
│   │   ├── deduplicator.py
│   │   ├── validators.py
│   │   ├── enrichment.py
│   │   └── freshness_filter.py
│   ├── database/               # Persistence
│   │   ├── models.py           # SQLAlchemy ORM models
│   │   ├── schemas.py          # Pydantic schemas
│   │   ├── connection.py       # Async engine
│   │   └── repository.py      # CRUD operations
│   ├── pipelines/              # Pipeline orchestration
│   │   ├── startup_pipeline.py
│   │   ├── product_pipeline.py
│   │   ├── research_pipeline.py
│   │   ├── news_pipeline.py
│   │   ├── jobs_pipeline.py
│   │   └── orchestrator.py    # Master coordinator
│   ├── exports/                # Data export
│   │   ├── csv_exporter.py
│   │   ├── json_exporter.py
│   │   ├── excel_exporter.py
│   │   └── google_sheets_exporter.py
│   ├── monitoring/             # Observability
│   │   ├── logger.py           # Structured JSON logging
│   │   ├── metrics.py          # In-process metrics
│   │   └── health.py           # Health checks
│   └── api/                    # FastAPI routes
├── tests/
│   └── test_pipeline.py        # 25 automated tests
├── data/
│   ├── raw/                    # Checkpoint files
│   ├── processed/
│   ├── exports/                # CSV, JSON, Excel outputs
│   └── logs/
├── scripts/
│   ├── run_all.py              # Run all pipelines
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

---

## Installation

### Prerequisites
- Python 3.11+ (Python 3.14 also works)
- PostgreSQL 14+ (optional: SQLite fallback available for local dev)
- Redis 6+ (optional: required for Celery distributed workers)

### 1. Clone & Create Environment

**PowerShell (Windows):**
```powershell
cd "AI PIPELINE\ai-intelligence-ingestion"
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Terminal (Linux/macOS):**
```bash
cd ai-intelligence-ingestion
python -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Playwright Browsers (optional: only for JS-rendered sources)
```bash
playwright install chromium
```

### 4. Configure Environment

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

### 5. Local Development (without PostgreSQL/Redis)

```env
USE_SQLITE_FALLBACK=1
```

The platform uses SQLite automatically and skips Redis when not configured.

### 6. Database Setup

```powershell
# Start PostgreSQL (or use Docker)
docker compose up postgres redis -d

# Tables are auto-created on first run
# Or use Alembic for production:
alembic upgrade head
```

### 7. Google Sheets Setup (optional)

1. Create Google Cloud project
2. Enable Sheets API and Drive API
3. Create service account → download JSON credentials
4. Set in `.env`:
   ```env
   GOOGLE_SHEETS_CREDENTIALS=credentials/google_sheets_credentials.json
   ```
5. Leave `GOOGLE_SPREADSHEET_ID` blank to auto-create

---

## Running the Platform

### Run All Pipelines

**PowerShell:**
```powershell
cd "c:\Users\Admin\OneDrive\Desktop\AI PIPELINE\ai-intelligence-ingestion"
python scripts\run_all.py
```

**Terminal:**
```bash
python scripts/run_all.py
```

### Run Individual Pipelines

```bash
python scripts/run_startups.py    # Startup collection only
python scripts/run_products.py    # Product collection only
python scripts/run_research.py    # Research papers only
python scripts/run_news.py        # News articles only
python scripts/run_jobs.py        # Jobs only
```

### Start the API Server

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Platform health check |
| GET | `/metrics` | Pipeline metrics |
| GET | `/api/status` | Current pipeline status |
| POST | `/api/pipeline/start` | Start all pipelines |
| POST | `/api/pipeline/startups` | Start startup pipeline |
| POST | `/api/pipeline/products` | Start product pipeline |
| POST | `/api/pipeline/research` | Start research pipeline |
| POST | `/api/pipeline/news` | Start news pipeline |
| POST | `/api/pipeline/jobs` | Start jobs pipeline |
| GET | `/api/results/summary` | Last run results |
| GET | `/api/sources` | Configured sources |

### Example: Start pipeline via API

```bash
curl -X POST http://localhost:8000/api/pipeline/start \
  -H "Content-Type: application/json" \
  -d '{"pipelines": ["startups", "products", "research", "news", "jobs"]}'
```

---

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Run specific test
pytest tests/test_pipeline.py::test_freshness_filter_24h -v
```

**Tests do not require real API credentials**: all HTTP calls are mocked.

---

## Export Locations

After running the pipeline:

| File | Contents |
|---|---|
| `data/exports/startups.csv` | Startup records |
| `data/exports/products.csv` | Product records |
| `data/exports/research_papers.csv` | Research papers + GitHub metrics |
| `data/exports/jobs.csv` | All collected jobs |
| `data/exports/news.csv` | All collected news |
| `data/exports/entity_mapping_log.csv` | Entity resolution decisions |
| `data/exports/ai_intelligence_output.xlsx` | Combined Excel workbook (6 sheets) |

Google Sheets URL is printed to console and returned in `/api/results/summary` when configured.

---

## Docker Deployment

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f api

# Run pipeline via API
curl -X POST http://localhost:8000/api/pipeline/start \
  -d '{"pipelines": ["startups", "products", "research", "news", "jobs"]}'
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| DB connection failed | Set `USE_SQLITE_FALLBACK=1` in `.env` for local dev |
| `asyncpg.exceptions.TooManyConnectionsError` | Reduce `DB_POOL_SIZE` in `.env` |
| arXiv rate limit | Increase sleep between requests in `research_collector.py` |
| GitHub 403 | Add `GITHUB_TOKEN` to `.env` |
| All LLM providers unavailable | Check API keys in `.env` |
| Google Sheets 403 | Verify service account has edit access to spreadsheet |
| Playwright not found | Run `playwright install chromium` |

---

## Scalability

The platform is designed to scale to **500,000+ records** via:
- Horizontal Celery workers (each processes independent source batches)
- PostgreSQL connection pooling (configurable `DB_POOL_SIZE`)
- Redis distributed rate limiting (prevents API quota violations across workers)
- Checkpoint recovery (workers resume from last successful position after restart)
- Configurable batch sizes (`BATCH_SIZE` in `.env`)

See [`docs/architecture.md`](docs/architecture.md) for detailed scaling design.

---

## Known Limitations & Source Availability

| Source | Status | Reason |
|---|---|---|
| Wellfound | ⚠️ Limited | Cloudflare protection: no bypass; uses YC API instead |
| Product Hunt | ⚠️ Paid API | Requires paid API key: not included; uses HF/GitHub instead |
| Crunchbase | ⚠️ Paid API | Licensed data only: uses YC Algolia as free alternative |
| Papers with Code | ✅ Included | Public API endpoints used where accessible |
| arXiv | ✅ Full access | Official API, no auth required |
| GitHub API | ✅ Full access | Public API; 60 req/hr without token, 5000/hr with token |
| Greenhouse/Lever/Ashby | ✅ Full access | Public job board APIs |
| RSS Feeds | ✅ Full access | Standard RSS: TechCrunch, VentureBeat, MIT TR, The Decoder, MarkTechPost |

---

## Engineering Decisions

1. **SQLite fallback**: Allows local development without PostgreSQL infrastructure
2. **In-process metrics**: Thread-safe counters avoid Redis dependency for basic monitoring
3. **arXiv rate limit**: 3.5s between requests: below arXiv's recommended limit
4. **GitHub enrichment**: Papers without GitHub URLs are stored without enrichment (not discarded)
5. **Pricing model**: `REVIEW` flag used when evidence is insufficient: never guessed
6. **Entity resolution**: NEVER merges entities below 90% fuzzy threshold automatically
7. **Fresh date classification**: Records without verifiable dates are classified as `is_fresh = False`
