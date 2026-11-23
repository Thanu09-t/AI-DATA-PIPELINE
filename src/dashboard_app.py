"""
Streamlit Web Application: AI Intelligence Ingestion Platform.
High-performance visual explorer with search, analytics charts, and data exports.
"""
import json
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import requests

st.set_page_config(
    page_title="FrontierAtlas | AI Intelligence Platform",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown("""
<style>
    .main {
        background-color: #0b0f19;
    }
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }
    .metric-val {
        font-size: 2.2rem;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-lbl {
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        border-radius: 8px;
        padding: 0 20px;
        background-color: #1e293b;
        color: #f1f5f9;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563eb !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

DATA_DIR = Path("data/exports")
API_BASE = "http://127.0.0.1:8000"


@st.cache_data
def load_data():
    def _read_json(fname):
        p = DATA_DIR / fname
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return pd.DataFrame(json.load(f))
        return pd.DataFrame()

    def _read_csv(fname):
        p = DATA_DIR / fname
        if p.exists():
            return pd.read_csv(p)
        return pd.DataFrame()

    products = _read_json("products.json")
    papers = _read_json("research_papers.json")
    startups = _read_json("startups.json")
    jobs = _read_json("jobs.json")
    news = _read_json("news.json")
    mappings = _read_csv("entity_mapping_log.csv")

    return products, papers, startups, jobs, news, mappings


products_df, papers_df, startups_df, jobs_df, news_df, mappings_df = load_data()

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🧠 AI Intelligence")
    st.caption("FrontierAtlas / GraphOne Autonomous Platform")
    st.markdown("---")

    nav = st.radio(
        "Navigation",
        [
            "📊 Executive Dashboard",
            "🚀 AI Products",
            "📚 Research Papers",
            "🏢 AI Startups",
            "💼 AI Jobs",
            "📰 AI News",
            "🔗 Entity Resolution",
            "⚡ Pipeline Controller",
        ],
        index=0,
    )

    st.markdown("---")
    st.subheader("📥 Export Downloads")
    excel_path = DATA_DIR / "ai_intelligence_output.xlsx"
    if excel_path.exists():
        with open(excel_path, "rb") as f:
            st.download_button(
                "📗 Complete Excel (.xlsx)",
                f.read(),
                file_name="ai_intelligence_output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    st.markdown("---")
    st.caption("Backend Status: 🟢 **FastAPI Live** on port 8000")


# ─────────────────────────────────────────────────────────────────────────────
# View: Executive Dashboard
# ─────────────────────────────────────────────────────────────────────────────
if nav == "📊 Executive Dashboard":
    st.title("📊 Executive Intelligence Dashboard")
    st.markdown("Continuous discovery, normalization, and entity resolution overview.")

    # KPI Metrics
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.markdown(f"""<div class="metric-card"><div class="metric-val">{len(products_df):,}</div><div class="metric-lbl">AI Products</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="metric-card"><div class="metric-val" style="color:#60a5fa">{len(papers_df):,}</div><div class="metric-lbl">Research Papers</div></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="metric-card"><div class="metric-val" style="color:#f59e0b">{len(startups_df):,}</div><div class="metric-lbl">AI Startups</div></div>""", unsafe_allow_html=True)
    with c4:
        fresh_jobs = sum(jobs_df.get("is_fresh_24h", [0]))
        st.markdown(f"""<div class="metric-card"><div class="metric-val" style="color:#10b981">{len(jobs_df):,}</div><div class="metric-lbl">AI Jobs ({fresh_jobs} &lt;24h)</div></div>""", unsafe_allow_html=True)
    with c5:
        fresh_news = sum(news_df.get("is_fresh_24h", [0]))
        st.markdown(f"""<div class="metric-card"><div class="metric-val" style="color:#c084fc">{len(news_df):,}</div><div class="metric-lbl">AI News ({fresh_news} &lt;24h)</div></div>""", unsafe_allow_html=True)
    with c6:
        st.markdown(f"""<div class="metric-card"><div class="metric-val" style="color:#f43f5e">{len(mappings_df):,}</div><div class="metric-lbl">Entity Mappings</div></div>""", unsafe_allow_html=True)

    st.markdown("###")

    # Analytics Charts Row
    r1_col1, r1_col2 = st.columns(2)

    with r1_col1:
        st.subheader("AI Products by Pricing Model")
        if not products_df.empty and "pricing_model" in products_df.columns:
            counts = products_df["pricing_model"].value_counts().reset_index()
            counts.columns = ["Pricing Model", "Count"]
            fig_pricing = px.pie(
                counts,
                values="Count",
                names="Pricing Model",
                hole=0.45,
                color_discrete_sequence=px.colors.sequential.Teal,
            )
            fig_pricing.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_pricing, use_container_width=True)

    with r1_col2:
        st.subheader("AI Jobs by Role Family")
        if not jobs_df.empty and "role_family" in jobs_df.columns:
            role_counts = jobs_df["role_family"].value_counts().reset_index()
            role_counts.columns = ["Role Family", "Count"]
            fig_jobs = px.bar(
                role_counts,
                x="Count",
                y="Role Family",
                orientation="h",
                color="Count",
                color_continuous_scale="Purples",
            )
            fig_jobs.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_jobs, use_container_width=True)

    r2_col1, r2_col2 = st.columns(2)
    with r2_col1:
        st.subheader("Top AI Job Employers (ATS Boards)")
        if not jobs_df.empty and "company" in jobs_df.columns:
            comp_counts = jobs_df["company"].value_counts().head(8).reset_index()
            comp_counts.columns = ["Company", "Job Postings"]
            fig_comp = px.bar(
                comp_counts,
                x="Company",
                y="Job Postings",
                color="Job Postings",
                color_continuous_scale="Viridis",
            )
            fig_comp.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_comp, use_container_width=True)

    with r2_col2:
        st.subheader("Entity Canonicalization Methods")
        if not mappings_df.empty and "resolution_method" in mappings_df.columns:
            method_counts = mappings_df["resolution_method"].value_counts().reset_index()
            method_counts.columns = ["Method", "Count"]
            fig_methods = px.pie(
                method_counts,
                values="Count",
                names="Method",
                hole=0.45,
                color_discrete_sequence=px.colors.sequential.Electric,
            )
            fig_methods.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_methods, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# View: AI Products
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "🚀 AI Products":
    st.title("🚀 AI Products Directory")
    st.caption(f"Displaying {len(products_df):,} verified AI models, spaces, and tooling products.")

    c1, c2 = st.columns([3, 1])
    with c1:
        search = st.text_input("🔍 Search products by name, company, or task", "")
    with c2:
        pricing_filter = st.selectbox("Pricing Filter", ["All"] + list(products_df["pricing_model"].dropna().unique()))

    filtered = products_df
    if pricing_filter != "All":
        filtered = filtered[filtered["pricing_model"] == pricing_filter]
    if search:
        s = search.lower()
        filtered = filtered[
            filtered["product_name"].astype(str).str.lower().str.contains(s)
            | filtered["company_name"].astype(str).str.lower().str.contains(s)
        ]

    st.write(f"Showing **{len(filtered):,}** matching products:")
    cols_to_show = ["product_name", "company_name", "pricing_model", "source_name", "source_url", "collected_at"]
    st.dataframe(
        filtered[[c for c in cols_to_show if c in filtered.columns]],
        use_container_width=True,
        hide_index=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# View: Research Papers
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "📚 Research Papers":
    st.title("📚 AI Research Papers")
    st.caption(f"Ingested {len(papers_df):,} arXiv publications with extracted GitHub repositories.")

    c1, c2 = st.columns([3, 1])
    with c1:
        search = st.text_input("🔍 Search research papers by title or keywords", "")
    with c2:
        has_gh = st.checkbox("Only papers with GitHub repos", False)

    filtered = papers_df
    if has_gh:
        filtered = filtered[filtered["github_url"].notna() & (filtered["github_url"] != "")]
    if search:
        s = search.lower()
        filtered = filtered[filtered["title"].astype(str).str.lower().str.contains(s)]

    st.write(f"Showing **{len(filtered):,}** matching papers:")
    cols = ["title", "published_at", "github_url", "github_stars", "paper_url"]
    st.dataframe(
        filtered[[c for c in cols if c in filtered.columns]],
        use_container_width=True,
        hide_index=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# View: AI Startups
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "🏢 AI Startups":
    st.title("🏢 AI Startups & Organizations")
    st.caption(f"Tracking {len(startups_df):,} verified AI creator entities and engineering organizations.")

    search = st.text_input("🔍 Search startups by name", "")
    filtered = startups_df
    if search:
        s = search.lower()
        filtered = filtered[filtered["startup_name"].astype(str).str.lower().str.contains(s)]

    st.write(f"Showing **{len(filtered):,}** entities:")
    cols = ["startup_name", "source_name", "source_url", "collected_at"]
    st.dataframe(
        filtered[[c for c in cols if c in filtered.columns]],
        use_container_width=True,
        hide_index=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# View: AI Jobs
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "💼 AI Jobs":
    st.title("💼 AI Jobs Ingestion")
    st.caption(f"Tracking {len(jobs_df):,} positions extracted from official Greenhouse, Ashby, and Lever ATS boards.")

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        search = st.text_input("🔍 Search jobs by title or company", "")
    with c2:
        fresh_only = st.checkbox("Strictly Fresh (<24 Hours)", False)
    with c3:
        remote_only = st.checkbox("Remote Eligible Only", False)

    filtered = jobs_df
    if fresh_only:
        filtered = filtered[filtered["is_fresh_24h"] == True]
    if remote_only:
        filtered = filtered[filtered["remote_eligible"] == True]
    if search:
        s = search.lower()
        filtered = filtered[
            filtered["title"].astype(str).str.lower().str.contains(s)
            | filtered["company"].astype(str).str.lower().str.contains(s)
        ]

    st.write(f"Showing **{len(filtered):,}** positions:")
    cols = ["title", "company", "role_family", "location", "remote_eligible", "published_at", "is_fresh_24h", "job_url"]
    st.dataframe(
        filtered[[c for c in cols if c in filtered.columns]],
        use_container_width=True,
        hide_index=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# View: AI News
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "📰 AI News":
    st.title("📰 Real-Time AI News")
    st.caption("Continuously monitored from TechCrunch AI, The Decoder, MarkTechPost, and MIT Technology Review.")

    fresh_only = st.checkbox("Show Only Verified Fresh (<24 Hours)", False)
    filtered = news_df
    if fresh_only:
        filtered = filtered[filtered["is_fresh_24h"] == True]

    st.write(f"Showing **{len(filtered):,}** articles:")
    cols = ["title", "source_name", "published_at", "is_fresh_24h", "article_url"]
    st.dataframe(
        filtered[[c for c in cols if c in filtered.columns]],
        use_container_width=True,
        hide_index=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# View: Entity Resolution
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "🔗 Entity Resolution":
    st.title("🔗 Canonical Entity Resolution Log")
    st.caption(f"Audit log of {len(mappings_df):,} raw-to-canonical entity resolution events with confidence scores.")

    c1, c2 = st.columns([3, 1])
    with c1:
        search = st.text_input("🔍 Search raw or canonical names", "")
    with c2:
        method = st.selectbox("Resolution Method", ["All"] + list(mappings_df["resolution_method"].dropna().unique()) if not mappings_df.empty else ["All"])

    filtered = mappings_df
    if method != "All" and not filtered.empty:
        filtered = filtered[filtered["resolution_method"] == method]
    if search and not filtered.empty:
        s = search.lower()
        filtered = filtered[
            filtered["raw_name"].astype(str).str.lower().str.contains(s)
            | filtered["canonical_name"].astype(str).str.lower().str.contains(s)
        ]

    st.dataframe(filtered, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# View: Pipeline Controller
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "⚡ Pipeline Controller":
    st.title("⚡ Autonomous Pipeline Controller")
    st.markdown("Trigger distributed acquisition workers and monitor execution status live via FastAPI.")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🚀 Ingest AI Products", use_container_width=True):
            try:
                res = requests.post(f"{API_BASE}/api/pipeline/products", timeout=3)
                st.success(f"Started: {res.json()}")
            except Exception as e:
                st.error(f"Failed to connect: {e}")

        if st.button("🏢 Ingest AI Startups", use_container_width=True):
            try:
                res = requests.post(f"{API_BASE}/api/pipeline/startups", timeout=3)
                st.success(f"Started: {res.json()}")
            except Exception as e:
                st.error(f"Failed to connect: {e}")

    with c2:
        if st.button("📚 Ingest Research Papers", use_container_width=True):
            try:
                res = requests.post(f"{API_BASE}/api/pipeline/research", timeout=3)
                st.success(f"Started: {res.json()}")
            except Exception as e:
                st.error(f"Failed to connect: {e}")

        if st.button("💼 Ingest AI Jobs", use_container_width=True):
            try:
                res = requests.post(f"{API_BASE}/api/pipeline/jobs", timeout=3)
                st.success(f"Started: {res.json()}")
            except Exception as e:
                st.error(f"Failed to connect: {e}")

    with c3:
        if st.button("📰 Ingest AI News", use_container_width=True):
            try:
                res = requests.post(f"{API_BASE}/api/pipeline/news", timeout=3)
                st.success(f"Started: {res.json()}")
            except Exception as e:
                st.error(f"Failed to connect: {e}")

        if st.button("🔥 Run All Pipelines", type="primary", use_container_width=True):
            try:
                res = requests.post(f"{API_BASE}/api/pipeline/start", json={"pipelines": ["startups", "products", "research", "news", "jobs"]}, timeout=3)
                st.success(f"All pipelines launched: {res.json()}")
            except Exception as e:
                st.error(f"Failed to connect: {e}")

    st.markdown("---")
    st.subheader("Live System Status")
    try:
        status_res = requests.get(f"{API_BASE}/api/status", timeout=2).json()
        st.json(status_res)
    except Exception as e:
        st.warning(f"Could not reach API: {e}")
