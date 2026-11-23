# AI Intelligence Ingestion Platform: Architecture

## 1. Platform Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                                         │
│  arXiv API │ YC Algolia │ HF Models/Spaces │ GitHub API │ RSS Feeds │ Job APIs│
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ASYNC COLLECTORS (aiohttp + asyncio)                     │
│  StartupCollector │ ProductCollector │ ResearchCollector │ News │ Jobs       │
│  ├── Rate Limiter (token bucket, per-source)                                │
│  ├── Retry Handler (exp. backoff + jitter, 429/5xx)                        │
│  ├── Semaphore (max concurrent requests)                                   │
│  └── Checkpoint Manager (file-based, resume on restart)                    │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RAW DATA BUFFER (data/raw/)                              │
│  Paginated results accumulated in memory + file checkpoints                │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HTML / TEXT PROCESSING                                   │
│  BeautifulSoup4 │ lxml │ Date Normalizer │ Freshness Filter               │
│  ├── ISO-8601, RFC, relative dates ("2 hours ago")                        │
│  ├── JSON-LD, OpenGraph, HTML time element extraction                     │
│  └── Timezone-aware UTC normalization                                      │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SEMANTIC CHUNKING (chunking.py)                          │
│  Token estimation → semantic boundary split → overlap preservation         │
│  Handles 413 / context window overflow by reducing chunk size              │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MULTI-LLM EXTRACTION ENGINE                              │
│  PRIMARY: Google Gemini Flash                                              │
│  SECONDARY: Groq (Llama 3-70b)                                             │
│  TERTIARY: DeepSeek Chat                                                   │
│  ├── Circuit breaker (5 failures → 120s open period)                      │
│  ├── 429: Exponential backoff + jitter + Retry-After header               │
│  ├── 413: Chunk size reduction + retry                                     │
│  ├── Provider switch on circuit open                                       │
│  └── Structured JSON extraction with Pydantic validation                  │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PYDANTIC VALIDATION                                      │
│  StartupSchema │ ProductSchema │ ResearchPaperSchema │ JobSchema │ NewsSchema│
│  Source provenance preserved on every record                               │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ENTITY RESOLUTION (entity_resolver.py)                  │
│  1. Whitespace normalization                                                │
│  2. Legal suffix removal (Inc., LLC, Ltd., Corp.)                          │
│  3. Case normalization + ASCII transliteration                             │
│  4. Alias map lookup (manual overrides)                                    │
│  5. Seed registry exact match (70+ canonical AI org names)                │
│  6. RapidFuzz token_sort_ratio (≥90 = high-confidence, 75-89 = review)   │
│  7. Semantic similarity via ChromaDB (for ambiguous cases)                │
│  Every decision logged to EntityMapping table                              │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                DEDUPLICATION & FRESHNESS (deduplicator.py)                 │
│  ├── URL hash dedup (SHA-256, unique constraint in DB)                    │
│  ├── Name-based fuzzy dedup (RapidFuzz, 95% threshold)                   │
│  ├── Idempotent DB upserts (ON CONFLICT DO NOTHING)                       │
│  └── 24-hour freshness filter with verified/inferred distinction          │
└─────────────────────┬────────────────────────────────────────────────────────┘
                      │
           ┌──────────┴──────────┐
           ▼                     ▼
┌──────────────────┐   ┌─────────────────────────────────────────────────────┐
│   PostgreSQL     │   │          ChromaDB (Vector Storage)                  │
│  (Primary DB)    │   │  Semantic entity similarity for ambiguous matches   │
│  ├── JSONB cols  │   │  Embeddings of canonical names for near-match search│
│  ├── UUID PKs    │   └─────────────────────────────────────────────────────┘
│  ├── Indexes     │
│  └── Constraints │
└──────────┬───────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EXPORT LAYER                                             │
│  ├── Google Sheets (6 tabs: Startups, Products, Papers, Jobs, News, Map)  │
│  ├── CSV exports (data/exports/*.csv)                                      │
│  ├── JSON exports (data/exports/*.json)                                    │
│  └── Excel workbook (data/exports/ai_intelligence_output.xlsx)            │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│          COORDINATION & SCALING INFRASTRUCTURE                              │
│  Redis: Rate limit coordination │ Caching │ Celery broker │ Result backend  │
│  Celery: Distributed task queue │ Configurable workers │ Dead-letter queue  │
│  FastAPI: REST API (8 pipeline endpoints) │ Health checks │ Metrics        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Scaling to 500,000+ Records

The platform is designed for horizontal scaling through:

- **Async concurrency**: `aiohttp` with configurable semaphore (`MAX_CONCURRENT_REQUESTS`)
- **Celery distributed workers**: Multiple workers process independent source batches
- **Redis coordination**: Distributed rate limiting and task deduplication
- **Checkpoint recovery**: File-based checkpoints allow interrupted runs to resume
- **Database batch inserts**: Bulk `INSERT ... ON CONFLICT DO NOTHING` with connection pooling
- **Configurable batch sizes**: `BATCH_SIZE` and `ARXIV_MAX_RESULTS` control throughput
- **Stateless workers**: Pipeline state is in Redis/PostgreSQL: any worker can process any task

To scale to 500K+ records:
1. Increase `MAX_CONCURRENT_REQUESTS`, `BATCH_SIZE` in `.env`
2. Add Celery workers: `celery -A src.tasks worker --concurrency=16`
3. Scale PostgreSQL with read replicas for query parallelism
4. Use partitioned tables by date for research papers

---

## 3. HTTP 429 Rate Limit Handling

```
Request → 429 Response
         ├── Read Retry-After header
         ├── Compute: wait = min(Retry-After + jitter, max_delay)
         ├── Increment retry counter
         ├── If retry < MAX_RETRIES: sleep(wait) → retry
         ├── If retry == MAX_RETRIES: increment provider failure count
         └── If failures >= circuit_threshold: open circuit breaker
```

Circuit breaker: after 5 consecutive failures, provider is marked unavailable for 120 seconds.

---

## 4. HTTP 413 / Context Window Handling

```
Large content → estimate_tokens() > chunk_token_limit
├── SemanticChunker splits at: headings → paragraphs → sentences → chars
├── Each chunk sent independently to LLM
├── Results merged: first non-null value wins per field
├── If provider still rejects: halve content, retry
└── If all strategies fail: log failure, return None (never invent data)
```

---

## 5. Duplicate Prevention Across Distributed Workers

**Layer 1: URL hash deduplication**: SHA-256 of URL is stored in `url_hash` column with a `UNIQUE` constraint. Any worker inserting a duplicate URL gets `ON CONFLICT DO NOTHING`: idempotent and safe.

**Layer 2: Redis distributed lock**: Before processing a URL, workers check a Redis key `processing:{hash}` with TTL. If key exists, another worker is processing it: skip.

**Layer 3: Name fuzzy dedup**: In-memory RapidFuzz dedup before batch DB insert.

---

## 6. Why PostgreSQL

- **ACID transactions**: Critical for idempotent upserts across concurrent workers
- **JSONB**: Flexible schema for `extra_data` without migrations per new field
- **Partial indexes**: `WHERE is_fresh = TRUE` for fast freshness queries
- **UUID primary keys**: Globally unique across distributed workers without coordination
- **Connection pooling**: SQLAlchemy async pool handles burst traffic gracefully
- **Mature ecosystem**: pgBouncer, read replicas, and logical replication for scaling

---

## 7. Vector Storage & Graph Relationships

**ChromaDB** stores embeddings of canonical entity names for semantic similarity search when RapidFuzz fuzzy matching is insufficient (score 75-89%). An embedding query finds the most semantically similar canonical name without false positives from substring matches.

**Graph-ready schema**: The `Startup → Product` foreign key relationship and the `EntityMapping` table form the foundation of an entity graph. Future extensions can materialize this into a graph database (Neo4j) for relationship traversal queries like "all products from YC batch W23 companies."

---

## 8. LLM Fallback Chain

```
Content arrives at orchestrator
│
├─→ [1] Gemini Flash (PRIMARY)
│   ├── Success → validated JSON → return
│   ├── 429 → backoff/retry (up to MAX_RETRIES)
│   ├── 413 → reduce chunk size → retry
│   └── Circuit open (5+ failures) → switch
│
├─→ [2] Groq Llama 3 (SECONDARY)
│   └── Same handling as above
│
└─→ [3] DeepSeek (TERTIARY)
    └── Same handling as above
        └── All failed → return None, log error
```

Provider name and model identifier are environment-variable configurable.

---

## 9. Publication Timestamp & 24-Hour Freshness

**Discovery order:**
1. JSON-LD (`datePublished`, `dateModified`)
2. OpenGraph (`article:published_time`)
3. HTML `<time datetime="...">` element
4. Meta tags (`pubdate`, `DC.date`, etc.)
5. RSS `<pubDate>` or Atom `<published>` elements
6. HN Firebase API Unix timestamp
7. Lever/Greenhouse API timestamps (Unix ms or ISO-8601)
8. Relative text ("2 hours ago")

**Verification flags:**
- `published_at_verified = True` → timestamp from explicit, machine-readable source
- `published_at_verified = False` → inferred/fuzzy-parsed
- Never labels inferred timestamps as verified

**Freshness gate**: `cutoff <= pub_dt_utc <= now`, strictly applied. Records without verified timestamps are classified as `is_fresh = False` unless a heuristic override is documented.

---

## 10. GitHub Stars Retrieval & Update

1. GitHub URL extracted from paper abstract using regex (`github.com/{owner}/{repo}`)
2. URL normalized (trailing `/`, `.git` removed)
3. `GET /repos/{owner}/{repo}` with Bearer token (5000 req/hr)
4. `stargazers_count` stored with `github_stars_collected_at` timestamp
5. `github_enriched = True` flag prevents re-fetching on restart
6. Unenriched papers with `github_url IS NOT NULL` queried for incremental re-enrichment

---

## 11. Anti-Bot Protection: Compliant Handling

For Cloudflare/DataDome-protected sources:
1. **Detect** challenge pages by checking for `challenge-platform`, `cf-challenge`, `turnstile` indicators
2. **Never bypass** CAPTCHA, TLS fingerprinting, or authentication guards
3. **Log** the detection and mark source status as `access_denied`
4. **Fall back** to official APIs, RSS feeds, or licensed data
5. **Document** the limitation in the pipeline report

Sources avoided due to protection: Wellfound (Cloudflare), Product Hunt (requires paid API).
Fallback: Hugging Face API, Greenhouse API, Lever API, Ashby API, GitHub API: all publicly accessible without CAPTCHA bypass.
