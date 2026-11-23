/**
 * AI Intelligence Platform: Enterprise Dashboard Application State & Logic
 */

const API_BASE = "";

// Global Application State
const state = {
    currentView: "overview",
    sidebarCollapsed: false,
    overview: null,
    tables: {
        products: { page: 1, limit: 25, total: 0, search: "", pricing: "all", sortBy: "name", sortOrder: "asc", records: [] },
        research: { page: 1, limit: 25, total: 0, search: "", hasGithub: false, sortBy: "date", sortOrder: "desc", records: [] },
        startups: { page: 1, limit: 25, total: 0, search: "", source: "all", sortBy: "name", sortOrder: "asc", records: [] },
        jobs: { page: 1, limit: 25, total: 0, search: "", roleFamily: "all", freshOnly: false, remoteOnly: false, sortBy: "date", sortOrder: "desc", records: [] },
        news: { page: 1, limit: 25, total: 0, search: "", publisher: "all", freshOnly: false, sortBy: "date", sortOrder: "desc", records: [] },
        mappings: { page: 1, limit: 25, total: 0, search: "", method: "all", sortBy: "confidence", sortOrder: "desc", records: [] },
    },
    charts: {},
    pollingInterval: null,
};

// ─────────────────────────────────────────────────────────────────────────────
// Initialization
// ─────────────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
    setupNavigation();
    setupGlobalSearch();
    setupDrawer();
    setupSidebarToggle();
    await loadOverview();
    lucide.createIcons();
    pollSystemStatus();
});

// ─────────────────────────────────────────────────────────────────────────────
// Navigation & Views
// ─────────────────────────────────────────────────────────────────────────────
function setupNavigation() {
    document.querySelectorAll(".nav-item[data-view]").forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const view = item.getAttribute("data-view");
            switchView(view);
        });
    });
}

function switchView(viewName) {
    state.currentView = viewName;

    // Update active nav item
    document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));
    const activeNav = document.querySelector(`.nav-item[data-view="${viewName}"]`);
    if (activeNav) activeNav.classList.add("active");

    // Update active view section
    document.querySelectorAll(".view-section").forEach(sec => sec.classList.remove("active"));
    const targetSec = document.getElementById(`view-${viewName}`);
    if (targetSec) targetSec.classList.add("active");

    // Update Breadcrumb
    const breadcrumb = document.getElementById("breadcrumb-current");
    if (breadcrumb) {
        const titleMap = {
            overview: "Executive Overview",
            products: "AI Products Directory",
            research: "Research Papers & arXiv",
            startups: "AI Startups & Organizations",
            jobs: "AI Jobs Intelligence",
            news: "Real-Time AI News",
            mappings: "Entity Canonicalization Log",
            exports: "Data Export Center",
            health: "System Health & Infrastructure",
            ingestion: "Pipeline Management",
        };
        breadcrumb.textContent = titleMap[viewName] || "Dashboard";
    }

    // Trigger data loading for the selected view
    if (viewName === "overview") {
        loadOverview();
    } else if (state.tables[viewName]) {
        loadCategoryData(viewName);
    } else if (viewName === "health") {
        loadHealthData();
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
}

function setupSidebarToggle() {
    const toggleBtn = document.getElementById("sidebar-toggle");
    const sidebar = document.querySelector(".sidebar");
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener("click", () => {
            if (window.innerWidth <= 768) {
                sidebar.classList.toggle("mobile-open");
            } else {
                sidebar.classList.toggle("collapsed");
                state.sidebarCollapsed = sidebar.classList.contains("collapsed");
            }
        });
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Overview & Charts
// ─────────────────────────────────────────────────────────────────────────────
async function loadOverview() {
    try {
        const res = await fetch(`${API_BASE}/api/overview`);
        if (!res.ok) throw new Error("Failed to load overview");
        const data = await res.json();
        state.overview = data;

        // Render KPI Values with animated count
        animateCounter("kpi-products", data.metrics.products);
        animateCounter("kpi-research", data.metrics.research);
        animateCounter("kpi-startups", data.metrics.startups);
        animateCounter("kpi-jobs", data.metrics.jobs);
        animateCounter("kpi-news", data.metrics.news);
        animateCounter("kpi-mappings", data.metrics.mappings);

        // Sidebar Badges
        updateBadge("badge-products", data.metrics.products);
        updateBadge("badge-research", data.metrics.research);
        updateBadge("badge-startups", data.metrics.startups);
        updateBadge("badge-jobs", data.metrics.jobs);
        updateBadge("badge-news", data.metrics.news);
        updateBadge("badge-mappings", data.metrics.mappings);

        // Subtext details
        document.getElementById("kpi-jobs-sub").textContent = `${data.metrics.fresh_jobs} verified < 24h`;
        document.getElementById("kpi-news-sub").textContent = `${data.metrics.fresh_news} verified < 24h`;
        document.getElementById("kpi-research-sub").textContent = `${data.metrics.github_enriched} enriched with stars`;

        // Render Analytics Charts
        renderAnalyticsCharts(data.charts);

        // Render Recent Activity Stream
        renderRecentActivity(data.recent_activity);

    } catch (err) {
        console.error("Overview load error:", err);
        showToast("Error loading intelligence overview", "error");
    }
}

function animateCounter(elemId, target) {
    const el = document.getElementById(elemId);
    if (!el) return;
    const duration = 800;
    const start = 0;
    const stepTime = 20;
    const steps = duration / stepTime;
    const increment = (target - start) / steps;
    let current = start;

    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            clearInterval(timer);
            el.textContent = target.toLocaleString();
        } else {
            el.textContent = Math.floor(current).toLocaleString();
        }
    }, stepTime);
}

function updateBadge(elemId, count) {
    const el = document.getElementById(elemId);
    if (el) el.textContent = count.toLocaleString();
}

function renderAnalyticsCharts(charts) {
    const fontConfig = { family: "'Inter', sans-serif", size: 10.5 };
    const textMuted = "#C7AEB4";
    const gridColor = "rgba(201, 163, 143, 0.12)";

    // 1. Pricing Donut Chart
    const pricingCanvas = document.getElementById("chart-pricing");
    if (pricingCanvas && charts.product_pricing) {
        if (state.charts.pricing) state.charts.pricing.destroy();
        state.charts.pricing = new Chart(pricingCanvas, {
            type: "doughnut",
            data: {
                labels: Object.keys(charts.product_pricing),
                datasets: [{
                    data: Object.values(charts.product_pricing),
                    backgroundColor: ["#F3D5CA", "#C9A38F", "#C7AEB4", "#7FA88B", "#4A1A26"],
                    borderColor: "#1E0B10",
                    borderWidth: 1,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: {
                    legend: {
                        position: "right",
                        labels: { color: textMuted, font: fontConfig, boxWidth: 10 }
                    },
                },
                cutout: "70%",
            }
        });
    }

    // 2. Job Roles Horizontal Bar Chart
    const rolesCanvas = document.getElementById("chart-roles");
    if (rolesCanvas && charts.job_roles) {
        if (state.charts.roles) state.charts.roles.destroy();
        state.charts.roles = new Chart(rolesCanvas, {
            type: "bar",
            data: {
                labels: Object.keys(charts.job_roles),
                datasets: [{
                    data: Object.values(charts.job_roles),
                    backgroundColor: "#C9A38F",
                    borderRadius: 0,
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: gridColor }, ticks: { color: textMuted, font: fontConfig } },
                    y: { grid: { display: false }, ticks: { color: "#FAEFE9", font: fontConfig } }
                }
            }
        });
    }

    // 3. arXiv Paper Categories Bar Chart
    const catCanvas = document.getElementById("chart-categories");
    if (catCanvas && charts.paper_categories) {
        if (state.charts.categories) state.charts.categories.destroy();
        state.charts.categories = new Chart(catCanvas, {
            type: "bar",
            data: {
                labels: Object.keys(charts.paper_categories),
                datasets: [{
                    data: Object.values(charts.paper_categories),
                    backgroundColor: "#F3D5CA",
                    borderRadius: 0,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false }, ticks: { color: textMuted, font: fontConfig } },
                    y: { grid: { color: gridColor }, ticks: { color: textMuted, font: fontConfig } }
                }
            }
        });
    }

    // 4. Entity Mapping Methods Donut Chart
    const methodsCanvas = document.getElementById("chart-methods");
    if (methodsCanvas && charts.mapping_methods) {
        if (state.charts.methods) state.charts.methods.destroy();
        state.charts.methods = new Chart(methodsCanvas, {
            type: "doughnut",
            data: {
                labels: Object.keys(charts.mapping_methods),
                datasets: [{
                    data: Object.values(charts.mapping_methods),
                    backgroundColor: ["#7FA88B", "#F3D5CA", "#D1A15A", "#C9A38F", "#C7AEB4"],
                    borderColor: "#1E0B10",
                    borderWidth: 1,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: {
                    legend: {
                        position: "right",
                        labels: { color: textMuted, font: fontConfig, boxWidth: 10 }
                    },
                },
                cutout: "70%",
            }
        });
    }
}

function renderRecentActivity(items) {
    const tbody = document.getElementById("recent-activity-tbody");
    if (!tbody || !items) return;
    tbody.innerHTML = items.map(item => `
        <tr onclick="openExternal('${item.url}')">
            <td><span class="badge badge-slate">${escapeHtml(item.category)}</span></td>
            <td class="fw-semibold text-truncate" style="max-width: 320px;">${escapeHtml(item.title)}</td>
            <td class="text-sub text-truncate" style="max-width: 200px;">${escapeHtml(item.subtitle)}</td>
            <td class="text-muted" style="font-size: 0.75rem;">${formatTime(item.timestamp)}</td>
            <td><span class="badge badge-slate">${escapeHtml(item.badge)}</span></td>
            <td><a href="${item.url}" target="_blank" onclick="event.stopPropagation();" style="color:var(--rose-gold);"><i data-lucide="external-link" style="width: 13px;"></i></a></td>
        </tr>
    `).join("");
    lucide.createIcons();
}

// ─────────────────────────────────────────────────────────────────────────────
// Category Data Explorer
// ─────────────────────────────────────────────────────────────────────────────
async function loadCategoryData(category) {
    const tState = state.tables[category];
    const offset = (tState.page - 1) * tState.limit;

    let url = `${API_BASE}/api/data/${category === 'research' ? 'research' : category}?limit=${tState.limit}&offset=${offset}&sort_by=${tState.sortBy}&sort_order=${tState.sortOrder}`;

    if (tState.search) url += `&search=${encodeURIComponent(tState.search)}`;
    if (category === "products" && tState.pricing !== "all") url += `&pricing=${encodeURIComponent(tState.pricing)}`;
    if (category === "research" && tState.hasGithub) url += `&has_github=true`;
    if (category === "jobs") {
        if (tState.roleFamily !== "all") url += `&role_family=${encodeURIComponent(tState.roleFamily)}`;
        if (tState.freshOnly) url += `&fresh_only=true`;
        if (tState.remoteOnly) url += `&remote_only=true`;
    }
    if (category === "news" && tState.freshOnly) url += `&fresh_only=true`;
    if (category === "mappings" && tState.method !== "all") url += `&method=${encodeURIComponent(tState.method)}`;

    // Show loading skeleton
    const tbody = document.getElementById(`${category}-tbody`);
    if (tbody) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted"><i data-lucide="loader" class="animate-spin me-2"></i> Loading intelligence data...</td></tr>`;
        lucide.createIcons();
    }

    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error("Data fetch error");
        const json = await res.json();

        tState.total = json.total;
        tState.records = json.records;

        renderCategoryTable(category);
        updatePagination(category);
    } catch (err) {
        console.error(`Error loading ${category}:`, err);
        showToast(`Failed to load ${category}`, "error");
    }
}

function renderCategoryTable(category) {
    const tState = state.tables[category];
    const tbody = document.getElementById(`${category}-tbody`);
    if (!tbody) return;

    if (!tState.records || tState.records.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-5 text-muted"><i data-lucide="inbox" style="width: 28px; height: 28px; margin: 0 auto 0.5rem; display: block; opacity: 0.5;"></i> No matching records found</td></tr>`;
        lucide.createIcons();
        return;
    }

    let rowsHtml = "";
    tState.records.forEach(rec => {
        if (category === "products") {
            const prodName = rec.product_name || rec.entity_name || "Unknown Product";
            const compName = rec.company_name || rec.startup_name || "Unknown";
            const pricingVal = (rec.pricing_model && rec.pricing_model !== "REVIEW") ? rec.pricing_model : "Not listed";
            const pricingClass = pricingVal === "FREE" ? "badge-emerald" : pricingVal === "PAID" ? "badge-amber" : "badge-slate";
            rowsHtml += `
                <tr onclick="openDrawerFromRecord('products', '${rec.id}')">
                    <td class="fw-semibold text-main">${escapeHtml(prodName)}</td>
                    <td><span class="badge badge-slate">${escapeHtml(compName)}</span></td>
                    <td><span class="badge ${pricingClass}">${escapeHtml(pricingVal)}</span></td>
                    <td class="text-muted">${escapeHtml(rec.source_name || 'Hugging Face')}</td>
                    <td class="text-muted" style="font-size:0.75rem;">${formatTime(rec.collected_at)}</td>
                    <td><a href="${rec.source_url}" target="_blank" onclick="event.stopPropagation();" class="text-sub"><i data-lucide="external-link" style="width: 13px;"></i></a></td>
                </tr>`;
        } else if (category === "research") {
            const ghStars = rec.github_stars !== null && rec.github_stars !== undefined 
                ? `<span class="badge badge-amber"><i data-lucide="star" style="width:10px;"></i> ${Number(rec.github_stars).toLocaleString()}</span>` 
                : `<span class="text-muted">-</span>`;
            const ghLink = rec.github_url 
                ? `<a href="${rec.github_url}" target="_blank" onclick="event.stopPropagation();" class="badge badge-slate"><i data-lucide="github" style="width:10px;"></i> Repo</a>` 
                : `<span class="text-muted">None</span>`;
            rowsHtml += `
                <tr onclick="openDrawerFromRecord('research', '${rec.id}')">
                    <td class="fw-semibold text-main text-truncate" style="max-width: 380px;">${escapeHtml(rec.title)}</td>
                    <td class="text-muted text-truncate" style="max-width: 180px;">${escapeHtml((rec.authors || []).slice(0, 2).join(", "))}</td>
                    <td>${ghLink}</td>
                    <td>${ghStars}</td>
                    <td class="text-muted" style="font-size:0.75rem;">${formatTime(rec.published_at)}</td>
                    <td><a href="${rec.paper_url}" target="_blank" onclick="event.stopPropagation();" class="text-sub">arXiv <i data-lucide="external-link" style="width: 11px;"></i></a></td>
                </tr>`;
        } else if (category === "startups") {
            rowsHtml += `
                <tr onclick="openDrawerFromRecord('startups', '${rec.id}')">
                    <td class="fw-semibold text-main">${escapeHtml(rec.startup_name)}</td>
                    <td><span class="badge badge-slate">${escapeHtml(rec.source_name)}</span></td>
                    <td class="text-muted text-truncate" style="max-width: 280px;">${escapeHtml(rec.source_url)}</td>
                    <td class="text-muted" style="font-size:0.75rem;">${formatTime(rec.collected_at)}</td>
                    <td><a href="${rec.source_url}" target="_blank" onclick="event.stopPropagation();" class="text-sub"><i data-lucide="external-link" style="width: 13px;"></i></a></td>
                </tr>`;
        } else if (category === "jobs") {
            const isFresh = rec.is_fresh || rec.is_fresh_24h;
            const isRemote = rec.is_remote || rec.remote_eligible;
            const jobUrl = rec.source_url || rec.job_url || "#";
            const freshBadge = isFresh ? `<span class="badge badge-emerald">Fresh &lt;24h</span>` : `<span class="badge badge-slate">Archived</span>`;
            const remoteBadge = isRemote ? `<span class="badge badge-amber">Remote</span>` : `<span class="badge badge-slate">Onsite</span>`;
            rowsHtml += `
                <tr onclick="openDrawerFromRecord('jobs', '${rec.id}')">
                    <td class="fw-semibold text-main">${escapeHtml(rec.title)}</td>
                    <td><span class="badge badge-slate">${escapeHtml(rec.company)}</span></td>
                    <td><span class="badge badge-slate">${escapeHtml(rec.role_family || 'Engineering')}</span></td>
                    <td>${remoteBadge}</td>
                    <td>${freshBadge}</td>
                    <td class="text-muted" style="font-size:0.75rem;">${formatTime(rec.published_at)}</td>
                    <td><a href="${jobUrl}" target="_blank" onclick="event.stopPropagation();" class="text-sub">Apply <i data-lucide="external-link" style="width: 11px;"></i></a></td>
                </tr>`;
        } else if (category === "news") {
            const isFresh = rec.is_fresh || rec.is_fresh_24h;
            const newsUrl = rec.source_url || rec.article_url || "#";
            const freshBadge = isFresh ? `<span class="badge badge-emerald">Fresh &lt;24h</span>` : `<span class="badge badge-slate">Archived</span>`;
            rowsHtml += `
                <tr onclick="openDrawerFromRecord('news', '${rec.id}')">
                    <td class="fw-semibold text-main text-truncate" style="max-width: 440px;">${escapeHtml(rec.title)}</td>
                    <td><span class="badge badge-slate">${escapeHtml(rec.source_name)}</span></td>
                    <td>${freshBadge}</td>
                    <td class="text-muted" style="font-size:0.75rem;">${formatTime(rec.published_at)}</td>
                    <td><a href="${newsUrl}" target="_blank" onclick="event.stopPropagation();" class="text-sub">Read <i data-lucide="external-link" style="width: 11px;"></i></a></td>
                </tr>`;
        } else if (category === "mappings") {
            const conf = parseFloat(rec.confidence_score) || 0;
            const confColor = conf >= 0.9 ? "badge-emerald" : conf >= 0.7 ? "badge-slate" : "badge-amber";
            rowsHtml += `
                <tr onclick="openDrawerFromRecord('mappings', '${rec.raw_name}')">
                    <td class="fw-semibold text-main">${escapeHtml(rec.raw_name)}</td>
                    <td><span class="badge badge-slate">${escapeHtml(rec.canonical_name)}</span></td>
                    <td><span class="badge badge-slate">${escapeHtml(rec.matching_method || 'exact')}</span></td>
                    <td><span class="badge ${confColor}">${conf.toFixed(2)}</span></td>
                    <td class="text-muted" style="font-size:0.75rem;">${formatTime(rec.resolved_at)}</td>
                    <td><a href="${rec.source_url}" target="_blank" onclick="event.stopPropagation();" class="text-sub"><i data-lucide="external-link" style="width: 13px;"></i></a></td>
                </tr>`;
        }
    });

    tbody.innerHTML = rowsHtml;
    lucide.createIcons();
}

function updatePagination(category) {
    const tState = state.tables[category];
    const start = (tState.page - 1) * tState.limit + 1;
    const end = Math.min(tState.page * tState.limit, tState.total);
    const totalPages = Math.ceil(tState.total / tState.limit) || 1;

    const infoEl = document.getElementById(`${category}-page-info`);
    if (infoEl) infoEl.textContent = `Showing ${tState.total > 0 ? start : 0} to ${end} of ${tState.total.toLocaleString()} records (Page ${tState.page} of ${totalPages})`;

    const prevBtn = document.getElementById(`${category}-prev`);
    const nextBtn = document.getElementById(`${category}-next`);
    if (prevBtn) prevBtn.disabled = (tState.page <= 1);
    if (nextBtn) nextBtn.disabled = (tState.page >= totalPages);
}

function changePage(category, delta) {
    const tState = state.tables[category];
    const totalPages = Math.ceil(tState.total / tState.limit) || 1;
    const newPage = tState.page + delta;
    if (newPage >= 1 && newPage <= totalPages) {
        tState.page = newPage;
        loadCategoryData(category);
    }
}

function handleSearch(category, val) {
    state.tables[category].search = val.trim();
    state.tables[category].page = 1;
    loadCategoryData(category);
}

function handleFilter(category, key, val) {
    state.tables[category][key] = val;
    state.tables[category].page = 1;
    loadCategoryData(category);
}

function handleSort(category, colName) {
    const tState = state.tables[category];
    if (tState.sortBy === colName) {
        tState.sortOrder = tState.sortOrder === "asc" ? "desc" : "asc";
    } else {
        tState.sortBy = colName;
        tState.sortOrder = "asc";
    }
    loadCategoryData(category);
}

// ─────────────────────────────────────────────────────────────────────────────
// Detail Slide-Out Drawer
// ─────────────────────────────────────────────────────────────────────────────
function setupDrawer() {
    const drawer = document.getElementById("detail-drawer");
    const closeBtn = document.getElementById("drawer-close-btn");
    if (closeBtn && drawer) {
        closeBtn.addEventListener("click", () => drawer.classList.remove("open"));
    }
}

function openDrawerFromRecord(category, idOrName) {
    const tState = state.tables[category];
    const rec = tState.records.find(r => (r.id === idOrName || r.raw_name === idOrName));
    if (!rec) return;
    openDrawer(rec, category);
}

function openDrawer(record, category) {
    const drawer = document.getElementById("detail-drawer");
    const drawerTitle = document.getElementById("drawer-title");
    const drawerCategory = document.getElementById("drawer-category");
    const drawerBody = document.getElementById("drawer-body");
    const drawerOpenBtn = document.getElementById("drawer-open-btn");
    const drawerCopyBtn = document.getElementById("drawer-copy-btn");

    if (!drawer) return;

    drawerCategory.textContent = category.toUpperCase();
    drawerTitle.textContent = record.product_name || record.title || record.startup_name || record.raw_name || "Record Details";

    const targetUrl = record.source_url || record.paper_url || record.job_url || record.article_url || "#";
    drawerOpenBtn.onclick = () => window.open(targetUrl, "_blank");
    drawerCopyBtn.onclick = () => {
        navigator.clipboard.writeText(targetUrl);
        showToast("Link copied to clipboard!", "success");
    };

    let fieldsHtml = "";
    for (const [key, val] of Object.entries(record)) {
        if (key === "id" || val === null || val === undefined || val === "") continue;
        const formattedVal = typeof val === "object" ? `<pre style="background:#0f172a; padding:8px; border-radius:6px; font-size:11px; max-height:160px; overflow:auto;">${escapeHtml(JSON.stringify(val, null, 2))}</pre>` : escapeHtml(String(val));
        fieldsHtml += `
            <div class="drawer-field">
                <span class="drawer-field-label">${key.replace(/_/g, " ")}</span>
                <span class="drawer-field-val">${formattedVal}</span>
            </div>`;
    }

    drawerBody.innerHTML = fieldsHtml;
    drawer.classList.add("open");
    lucide.createIcons();
}

// ─────────────────────────────────────────────────────────────────────────────
// Global Search (Ctrl + K)
// ─────────────────────────────────────────────────────────────────────────────
function setupGlobalSearch() {
    const trigger = document.getElementById("global-search-btn");
    const modal = document.getElementById("search-modal");
    const input = document.getElementById("search-modal-input");
    const resultsContainer = document.getElementById("search-results-list");

    if (trigger && modal) {
        trigger.addEventListener("click", () => openSearchModal());
    }

    window.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "k") {
            e.preventDefault();
            openSearchModal();
        }
        if (e.key === "Escape" && modal && modal.classList.contains("active")) {
            closeSearchModal();
        }
    });

    if (modal) {
        modal.addEventListener("click", (e) => {
            if (e.target === modal) closeSearchModal();
        });
    }

    let searchTimeout = null;
    if (input) {
        input.addEventListener("input", (e) => {
            clearTimeout(searchTimeout);
            const q = e.target.value.trim();
            if (q.length < 2) {
                resultsContainer.innerHTML = `<div class="p-4 text-center text-muted" style="font-size:0.85rem;">Type at least 2 characters to search across all intelligence datasets...</div>`;
                return;
            }
            searchTimeout = setTimeout(async () => {
                try {
                    const res = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(q)}`);
                    const data = await res.json();
                    renderGlobalSearchResults(data.results);
                } catch (err) {
                    console.error("Search error:", err);
                }
            }, 250);
        });
    }
}

function openSearchModal() {
    const modal = document.getElementById("search-modal");
    const input = document.getElementById("search-modal-input");
    if (modal && input) {
        modal.classList.add("active");
        input.value = "";
        input.focus();
        document.getElementById("search-results-list").innerHTML = `<div class="p-4 text-center text-muted" style="font-size:0.85rem;">Search across AI Products, Research Papers, Startups, Jobs, News, and Mappings...</div>`;
    }
}

function closeSearchModal() {
    const modal = document.getElementById("search-modal");
    if (modal) modal.classList.remove("active");
}

function renderGlobalSearchResults(results) {
    const container = document.getElementById("search-results-list");
    let html = "";
    let matchCount = 0;

    for (const [catKey, items] of Object.entries(results)) {
        if (items && items.length > 0) {
            matchCount += items.length;
            html += `<div class="px-2 py-1 text-muted text-uppercase" style="font-size:0.7rem; font-weight:700; letter-spacing:0.05em; margin-top:6px;">${catKey}</div>`;
            items.forEach(item => {
                html += `
                    <div class="search-result-item" onclick="handleSearchResultClick('${catKey}', ${escapeQuotes(JSON.stringify(item.raw))})">
                        <span class="badge badge-cyan">${item.category}</span>
                        <div>
                            <div class="search-result-title">${escapeHtml(item.title)}</div>
                            <div class="search-result-sub">${escapeHtml(item.subtitle)}</div>
                        </div>
                    </div>`;
            });
        }
    }

    if (matchCount === 0) {
        html = `<div class="p-4 text-center text-muted">No intelligence matches found.</div>`;
    }

    container.innerHTML = html;
}

function handleSearchResultClick(category, record) {
    closeSearchModal();
    const viewMap = { products: "products", papers: "research", startups: "startups", jobs: "jobs", news: "news", mappings: "mappings" };
    const targetView = viewMap[category] || "overview";
    switchView(targetView);
    setTimeout(() => openDrawer(record, targetView), 150);
}

// ─────────────────────────────────────────────────────────────────────────────
// Pipeline Management & Execution
// ─────────────────────────────────────────────────────────────────────────────
async function triggerPipeline(pipelineName) {
    showToast(`Launching ${pipelineName} pipeline in background...`, "info");
    try {
        let endpoint = `${API_BASE}/api/pipeline/start`;
        let body = { pipelines: ["startups", "products", "research", "news", "jobs"] };
        if (pipelineName !== "all") {
            endpoint = `${API_BASE}/api/pipeline/${pipelineName}`;
            body = null;
        }

        const res = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: body ? JSON.stringify(body) : undefined,
        });

        if (!res.ok) throw new Error("Pipeline trigger rejected");
        const json = await res.json();
        showToast(`Pipeline started: ${pipelineName}`, "success");
        pollSystemStatus(true);
    } catch (err) {
        console.error("Trigger error:", err);
        showToast(`Failed to trigger ${pipelineName} pipeline`, "error");
    }
}

async function pollSystemStatus(immediate = false) {
    const statusBadge = document.getElementById("system-status-indicator");
    const runningPill = document.getElementById("pipeline-running-pill");

    try {
        const [statusRes, healthRes] = await Promise.all([
            fetch(`${API_BASE}/api/status`),
            fetch(`${API_BASE}/health`),
        ]);

        if (!statusRes.ok || !healthRes.ok) {
            if (statusBadge) {
                statusBadge.className = "system-status-badge status-degraded";
                statusBadge.innerHTML = `<span class="status-dot status-degraded"></span> System Degraded`;
            }
            return;
        }

        const status = await statusRes.json();
        const health = await healthRes.json();

        if (status.running) {
            if (statusBadge) {
                statusBadge.className = "system-status-badge status-degraded";
                statusBadge.innerHTML = `<span class="status-dot status-running"></span> Pipeline Running`;
            }
            if (runningPill) {
                runningPill.style.display = "inline-flex";
                runningPill.textContent = `Running: ${status.active_pipeline || 'Processing'}`;
            }
        } else if (health.status === "degraded" || health.status === "unhealthy") {
            if (statusBadge) {
                statusBadge.className = "system-status-badge status-degraded";
                statusBadge.innerHTML = `<span class="status-dot status-degraded"></span> System Degraded`;
            }
            if (runningPill) runningPill.style.display = "none";
        } else {
            if (statusBadge) {
                statusBadge.className = "system-status-badge";
                statusBadge.innerHTML = `<span class="status-dot"></span> System Live`;
            }
            if (runningPill) runningPill.style.display = "none";
        }
    } catch (err) {
        if (statusBadge) {
            statusBadge.className = "system-status-badge status-offline";
            statusBadge.innerHTML = `<span class="status-dot status-offline"></span> System Offline`;
        }
        if (runningPill) runningPill.style.display = "none";
    }
}
setInterval(pollSystemStatus, 4000);

// ─────────────────────────────────────────────────────────────────────────────
// System Health View
// ─────────────────────────────────────────────────────────────────────────────
async function loadHealthData() {
    try {
        const [healthRes, metricsRes] = await Promise.all([
            fetch(`${API_BASE}/health`),
            fetch(`${API_BASE}/metrics`),
        ]);
        const health = await healthRes.json();
        const metrics = await metricsRes.json();

        const healthBox = document.getElementById("health-report-box");
        if (healthBox) {
            healthBox.innerHTML = `
                <div class="row g-3">
                    <div class="col-md-4">
                        <div class="p-3 rounded border" style="background:var(--bg-surface); border-color:var(--border);">
                            <div class="text-sub small">Database Service</div>
                            <div class="h5 mt-1 text-emerald"><i data-lucide="check-circle" class="me-1"></i> Connected</div>
                            <div class="text-muted small">${health.services?.database?.status || 'Active (Dual Postgres/SQLite)'}</div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="p-3 rounded border" style="background:var(--bg-surface); border-color:var(--border);">
                            <div class="text-sub small">Distributed Cache & Coordination</div>
                            <div class="h5 mt-1 text-cyan"><i data-lucide="cpu" class="me-1"></i> Async Semaphore / Redis</div>
                            <div class="text-muted small">${health.services?.redis?.status || 'In-Process Concurrency Ready'}</div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="p-3 rounded border" style="background:var(--bg-surface); border-color:var(--border);">
                            <div class="text-sub small">API Uptime & Response</div>
                            <div class="h5 mt-1 text-cyan"><i data-lucide="zap" class="me-1"></i> Sub-millisecond (FastAPI)</div>
                            <div class="text-muted small">Port 8000 • Production Live</div>
                        </div>
                    </div>
                </div>
            `;
            lucide.createIcons();
        }
    } catch (err) {
        console.error("Health fetch error:", err);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Utility Helpers
// ─────────────────────────────────────────────────────────────────────────────
function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast-msg ${type}`;
    const icon = type === "success" ? "check-circle" : type === "error" ? "alert-circle" : "info";
    toast.innerHTML = `<i data-lucide="${icon}" style="width:16px; flex-shrink:0;"></i> <span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);
    lucide.createIcons();

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transition = "opacity 0.3s ease";
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

function openExternal(url) {
    if (url && url !== "#") window.open(url, "_blank");
}

function formatTime(isoStr) {
    if (!isoStr) return "-";
    try {
        const d = new Date(isoStr);
        if (isNaN(d.getTime())) return String(isoStr).slice(0, 10);
        return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch {
        return String(isoStr).slice(0, 10);
    }
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function escapeQuotes(str) {
    if (!str) return "''";
    return str.replace(/'/g, "&apos;");
}
