/* ═══════════════════════════════════════════════════════════════════════
   AUV Swarm Dashboard — Application Logic
   ═══════════════════════════════════════════════════════════════════════ */

(() => {
    "use strict";

    // ── Constants ──────────────────────────────────────────────────────
    const ARCHIVE_BASE = "../dashboard_runs";
    const INDEX_URL = `${ARCHIVE_BASE}/runs_index.json`;
    const POLL_INTERVAL = 10_000; // ms

    const AMV_COLORS = ["#2196F3", "#FF9800", "#4CAF50", "#F44336", "#9C27B0"];

    // Pretty names for plot files
    const PLOT_LABELS = {
        plot_mission_space:    "Mission Space",
        plot_task_coverage:    "Task Coverage",
        plot_availability:     "AMV Availability",
        plot_fault_gantt:      "Fault Gantt Chart",
        plot_comm_graph:       "Communication Graph",
        plot_energy:           "Energy Levels",
        plot_total_benefit:    "Total Benefit",
        plot_edmc_proposals:   "EDMC Proposals",
        plot_3d_mission_space: "3D Trajectory View",
        plot_physics_dashboard: "Physics Dashboard",
        plot_fsm_timeline:     "FSM Timeline",
        plot_fsm_diagram:      "FSM State Diagram",
        plot_confidence_histogram: "Confidence Histogram",
        mesh_animation:        "Mesh Animation",
        confusion_matrix:      "Confusion Matrix",
        loss_curves:           "Loss Curves",
        plot_confusion_matrix: "Confusion Matrix (Train)",
        plot_post_fix_completion:  "Post-Fix Completion",
        plot_allocator_comparison_completion: "Allocator Comparison",
        plot_allocator_comparison_deadlock_recovery: "Deadlock Recovery Comparison",
    };

    // Plot category grouping
    const PLOT_CATEGORIES = {
        "All": null,
        "Mission": ["mission_space", "3d_mission_space", "task_coverage"],
        "Fleet": ["availability", "fault_gantt", "energy", "fsm_timeline", "fsm_diagram"],
        "Comms": ["comm_graph", "physics_dashboard", "mesh_animation"],
        "Consensus": ["total_benefit", "edmc_proposals", "confidence_histogram"],
        "Training": ["confusion_matrix", "loss_curves", "plot_confusion_matrix"],
    };

    // ── State ─────────────────────────────────────────────────────────
    let runsIndex = null;
    let currentRunTs = null;
    let currentRunData = null;
    let galleryImages = [];
    let lightboxIndex = 0;
    let pollTimer = null;
    let trendCharts = {};

    // ── DOM refs ──────────────────────────────────────────────────────
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const runListEl        = $("#runList");
    const welcomeState     = $("#welcomeState");
    const dashboardState   = $("#dashboardState");
    const runTitle         = $("#runTitle");
    const runTags          = $("#runTags");
    const kpiGrid          = $("#kpiGrid");
    const amvGrid          = $("#amvGrid");
    const galleryFilter    = $("#galleryFilter");
    const galleryGrid      = $("#galleryGrid");
    const trendSection     = $("#trendSection");
    const lightbox         = $("#lightbox");
    const lightboxImg      = $("#lightboxImg");
    const lightboxCaption  = $("#lightboxCaption");
    const autoRefreshToggle = $("#autoRefreshToggle");
    const refreshIndicator = $("#refreshIndicator");

    // ═══════════════════════════════════════════════════════════════════
    // DATA FETCHING
    // ═══════════════════════════════════════════════════════════════════

    async function fetchRunsIndex() {
        try {
            const resp = await fetch(INDEX_URL + "?t=" + Date.now());
            if (!resp.ok) return null;
            return await resp.json();
        } catch { return null; }
    }

    async function fetchRunMeta(metaFile) {
        try {
            const resp = await fetch(`${ARCHIVE_BASE}/${metaFile}?t=` + Date.now());
            if (!resp.ok) return null;
            return await resp.json();
        } catch { return null; }
    }

    // ═══════════════════════════════════════════════════════════════════
    // SIDEBAR — RUN LIST
    // ═══════════════════════════════════════════════════════════════════

    function renderRunList(index) {
        if (!index || !index.runs || index.runs.length === 0) {
            runListEl.innerHTML = `
                <div class="empty-state">
                    <p>No runs found yet.</p>
                    <p class="hint">Run <code>python main.py</code> to generate data.</p>
                </div>`;
            return;
        }

        // Show newest first
        const runs = [...index.runs].reverse();
        runListEl.innerHTML = runs.map(run => {
            const d = parseTimestamp(run.timestamp);
            const tcr = run.task_completion_rate != null
                ? (run.task_completion_rate * 100).toFixed(0)
                : "?";
            const badgeClass = tcr >= 85 ? "badge-green" : tcr >= 70 ? "badge-amber" : "badge-red";
            const isActive = run.timestamp === currentRunTs ? "active" : "";

            return `
                <div class="run-item ${isActive}" data-ts="${run.timestamp}" onclick="window.__selectRun('${run.timestamp}')">
                    <div class="run-date">${d.dateStr}</div>
                    <div class="run-meta">
                        <span>${d.timeStr}</span>
                        <span class="run-metric-badge ${badgeClass}">${tcr}%</span>
                        <span>${run.scenario || "nominal"}</span>
                    </div>
                </div>`;
        }).join("");
    }

    function parseTimestamp(ts) {
        // ts format: 20260826_110530
        const y = ts.slice(0,4), mo = ts.slice(4,6), day = ts.slice(6,8);
        const h = ts.slice(9,11), mi = ts.slice(11,13), s = ts.slice(13,15);
        return {
            dateStr: `${day}/${mo}/${y}`,
            timeStr: `${h}:${mi}:${s}`,
            label: `${day}/${mo} ${h}:${mi}`,
        };
    }

    // ═══════════════════════════════════════════════════════════════════
    // RUN SELECTION
    // ═══════════════════════════════════════════════════════════════════

    window.__selectRun = async function(ts) {
        currentRunTs = ts;
        const run = runsIndex.runs.find(r => r.timestamp === ts);
        if (!run) return;

        // Highlight in sidebar
        $$(".run-item").forEach(el => el.classList.toggle("active", el.dataset.ts === ts));

        const meta = await fetchRunMeta(run.meta_file);
        if (!meta) return;
        currentRunData = meta;

        welcomeState.style.display = "none";
        dashboardState.style.display = "block";

        renderHeader(meta);
        renderKPIs(meta.metrics);
        renderAMVs(meta.amv_states);
        renderGallery(meta.images, ts);
        renderTrends();
    };

    // ═══════════════════════════════════════════════════════════════════
    // HEADER
    // ═══════════════════════════════════════════════════════════════════

    function renderHeader(meta) {
        const d = parseTimestamp(meta.timestamp);
        runTitle.textContent = `Run — ${d.dateStr} at ${d.timeStr}`;
        runTags.innerHTML = [
            tag("Seed", meta.seed, "#06b6d4"),
            tag("Scenario", meta.scenario || "none", "#8b5cf6"),
            tag("Allocator", meta.allocator, "#10b981"),
            tag("AMVs", meta.n_amvs, "#f59e0b"),
            tag("Tasks", meta.n_tasks, "#3b82f6"),
            tag("Timesteps", meta.simulation_timesteps, "#ec4899"),
        ].join("");
    }

    function tag(label, value, color) {
        return `<span class="tag"><span class="tag-dot" style="background:${color}"></span>${label}: ${value}</span>`;
    }

    // ═══════════════════════════════════════════════════════════════════
    // KPI CARDS
    // ═══════════════════════════════════════════════════════════════════

    function renderKPIs(m) {
        const kpis = [
            { label: "Task Completion", value: pct(m.task_completion_rate), sub: `${Math.round(m.task_completion_rate * (currentRunData?.n_tasks||15))}/${currentRunData?.n_tasks||15} tasks`, gradient: "var(--gradient-green)", icon: "✓" },
            { label: "Mean Task Delay", value: `${m.mean_task_delay.toFixed(1)}`, sub: "timesteps", gradient: "var(--gradient-blue)", icon: "⏱" },
            { label: "Deadlock Frequency", value: `${m.deadlock_frequency.toFixed(2)}`, sub: "per 100 timesteps", gradient: "var(--gradient-amber)", icon: "⚡" },
            { label: "Congestion Drop Rate", value: pct(m.congestion_drop_rate), sub: `${m.congestion_drops} drops total`, gradient: "var(--gradient-primary)", icon: "📡" },
            { label: "Packet Loss Rate", value: pct(m.mean_packet_loss_rate), sub: "total lost / sent", gradient: "var(--gradient-amber)", icon: "📉" },
            { label: "Energy Efficiency", value: `${m.energy_efficiency.toFixed(1)}`, sub: "energy / task", gradient: "var(--gradient-green)", icon: "⚡" },
            { label: "AMV Availability", value: `${(m.mean_amv_availability).toFixed(3)}`, sub: "mean score", gradient: "var(--gradient-blue)", icon: "🔋" },
            { label: "Connectivity", value: pct(m.connectivity_maintenance), sub: "above threshold", gradient: "var(--gradient-primary)", icon: "🔗" },
            { label: "System Throughput", value: `${m.system_throughput.toFixed(4)}`, sub: "tasks / timestep", gradient: "var(--gradient-green)", icon: "📊" },
            { label: "Fault Impact", value: pct(m.fault_impact_score), sub: "degraded AMV-timesteps", gradient: "var(--gradient-amber)", icon: "⚠" },
            { label: "Auction Convergence", value: `${m.auction_convergence_rate.toFixed(2)}`, sub: "iters / round", gradient: "var(--gradient-blue)", icon: "🔄" },
            { label: "Thermocline Penalty", value: pct(m.thermocline_crossing_penalty), sub: "messages affected", gradient: "var(--gradient-primary)", icon: "🌊" },
        ];

        kpiGrid.innerHTML = kpis.map((k, i) => `
            <div class="kpi-card" style="--kpi-accent: ${k.gradient}">
                <div class="kpi-icon">${k.icon}</div>
                <div class="kpi-label">${k.label}</div>
                <div class="kpi-value">${k.value}</div>
                <div class="kpi-sub">${k.sub}</div>
            </div>
        `).join("");
    }

    function pct(v) { return (v * 100).toFixed(1) + "%"; }

    // ═══════════════════════════════════════════════════════════════════
    // AMV STATUS CARDS
    // ═══════════════════════════════════════════════════════════════════

    function renderAMVs(states) {
        if (!states || states.length === 0) {
            amvGrid.innerHTML = "<p style='color:var(--text-muted)'>No AMV data available.</p>";
            return;
        }

        amvGrid.innerHTML = states.map((a, i) => {
            const color = AMV_COLORS[a.amv_id % AMV_COLORS.length];
            const energyPct = Math.max(0, Math.min(100, a.energy));
            const energyColor = energyPct > 50 ? "#10b981" : energyPct > 20 ? "#f59e0b" : "#ef4444";

            return `
                <div class="amv-card" style="animation-delay: ${i * 0.05}s">
                    <div class="amv-card-header">
                        <span class="amv-name">AMV ${a.amv_id}</span>
                        <span class="amv-color-dot" style="background:${color}; color:${color}"></span>
                    </div>
                    <div class="amv-stat"><span class="amv-stat-label">FSM State</span><span class="amv-stat-value">${a.fsm_state}</span></div>
                    <div class="amv-stat"><span class="amv-stat-label">Fault</span><span class="amv-stat-value">${a.fault_state}</span></div>
                    <div class="amv-stat"><span class="amv-stat-label">Tasks Done</span><span class="amv-stat-value">${a.tasks_completed}</span></div>
                    <div class="amv-stat"><span class="amv-stat-label">Distance</span><span class="amv-stat-value">${a.distance_traveled}m</span></div>
                    <div class="amv-stat"><span class="amv-stat-label">Energy</span><span class="amv-stat-value">${a.energy.toFixed(1)}%</span></div>
                    <div class="amv-energy-bar">
                        <div class="amv-energy-fill" style="width:${energyPct}%; background:${energyColor}"></div>
                    </div>
                </div>`;
        }).join("");
    }

    // ═══════════════════════════════════════════════════════════════════
    // IMAGE GALLERY
    // ═══════════════════════════════════════════════════════════════════

    let activeFilter = "All";

    function renderGallery(images, ts) {
        galleryImages = (images || []).map(img => ({
            src: `${ARCHIVE_BASE}/${img}`,
            filename: img,
            plotKey: extractPlotKey(img),
            label: getPlotLabel(img),
            ts: ts,
        }));

        renderFilterButtons();
        renderGalleryItems();
    }

    function extractPlotKey(filename) {
        // Remove timestamp suffix: plot_mission_space_20260826_110530.png → plot_mission_space
        return filename.replace(/_\d{8}_\d{6}\.\w+$/, "");
    }

    function getPlotLabel(filename) {
        const key = extractPlotKey(filename);
        return PLOT_LABELS[key] || key.replace(/^plot_/, "").replace(/_/g, " ");
    }

    function renderFilterButtons() {
        galleryFilter.innerHTML = Object.keys(PLOT_CATEGORIES).map(cat => {
            const cls = cat === activeFilter ? "filter-btn active" : "filter-btn";
            return `<button class="${cls}" onclick="window.__filterGallery('${cat}')">${cat}</button>`;
        }).join("");
    }

    window.__filterGallery = function(cat) {
        activeFilter = cat;
        renderFilterButtons();
        renderGalleryItems();
    };

    function renderGalleryItems() {
        const catKeys = PLOT_CATEGORIES[activeFilter];
        const filtered = catKeys
            ? galleryImages.filter(img => catKeys.some(k => img.plotKey.includes(k)))
            : galleryImages;

        galleryGrid.innerHTML = filtered.map((img, i) => {
            const d = parseTimestamp(img.ts);
            return `
                <div class="gallery-item" onclick="window.__openLightbox(${i})" style="animation-delay: ${i * 0.03}s">
                    <img src="${img.src}" alt="${img.label}" loading="lazy">
                    <div class="gallery-item-info">
                        <div class="gallery-item-title">${img.label}</div>
                        <div class="gallery-item-time">${d.dateStr} ${d.timeStr}</div>
                    </div>
                </div>`;
        }).join("");
    }

    // ═══════════════════════════════════════════════════════════════════
    // LIGHTBOX
    // ═══════════════════════════════════════════════════════════════════

    window.__openLightbox = function(idx) {
        const catKeys = PLOT_CATEGORIES[activeFilter];
        const filtered = catKeys
            ? galleryImages.filter(img => catKeys.some(k => img.plotKey.includes(k)))
            : galleryImages;
        lightboxIndex = idx;
        lightboxImg.src = filtered[idx].src;
        lightboxCaption.textContent = filtered[idx].label;
        lightbox.classList.add("active");
    };

    function closeLightbox() { lightbox.classList.remove("active"); }

    function navigateLightbox(dir) {
        const catKeys = PLOT_CATEGORIES[activeFilter];
        const filtered = catKeys
            ? galleryImages.filter(img => catKeys.some(k => img.plotKey.includes(k)))
            : galleryImages;
        lightboxIndex = (lightboxIndex + dir + filtered.length) % filtered.length;
        lightboxImg.src = filtered[lightboxIndex].src;
        lightboxCaption.textContent = filtered[lightboxIndex].label;
    }

    $("#lightboxClose").addEventListener("click", closeLightbox);
    $("#lightboxPrev").addEventListener("click", () => navigateLightbox(-1));
    $("#lightboxNext").addEventListener("click", () => navigateLightbox(1));
    lightbox.addEventListener("click", (e) => { if (e.target === lightbox) closeLightbox(); });
    document.addEventListener("keydown", (e) => {
        if (!lightbox.classList.contains("active")) return;
        if (e.key === "Escape") closeLightbox();
        if (e.key === "ArrowLeft") navigateLightbox(-1);
        if (e.key === "ArrowRight") navigateLightbox(1);
    });

    // ═══════════════════════════════════════════════════════════════════
    // TREND CHARTS (cross-run comparison)
    // ═══════════════════════════════════════════════════════════════════

    function renderTrends() {
        if (!runsIndex || runsIndex.runs.length < 2) {
            trendSection.style.display = "none";
            return;
        }
        trendSection.style.display = "block";

        // We need to load all run meta files
        loadAllRunMetas().then(allMetas => {
            if (allMetas.length < 2) return;

            const labels = allMetas.map(m => parseTimestamp(m.timestamp).label);

            buildTrendChart("chartCompletion", labels,
                allMetas.map(m => (m.metrics.task_completion_rate * 100)),
                "Completion %", "#10b981");
            buildTrendChart("chartDeadlock", labels,
                allMetas.map(m => m.metrics.deadlock_frequency),
                "per 100 ts", "#f59e0b");
            buildTrendChart("chartDelay", labels,
                allMetas.map(m => m.metrics.mean_task_delay),
                "timesteps", "#3b82f6");
            buildTrendChart("chartCongestion", labels,
                allMetas.map(m => (m.metrics.congestion_drop_rate * 100)),
                "Drop %", "#8b5cf6");
        });
    }

    async function loadAllRunMetas() {
        const promises = runsIndex.runs.map(r => fetchRunMeta(r.meta_file));
        const results = await Promise.all(promises);
        return results.filter(Boolean);
    }

    function buildTrendChart(canvasId, labels, data, yLabel, color) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        // Destroy existing chart
        if (trendCharts[canvasId]) {
            trendCharts[canvasId].destroy();
        }

        trendCharts[canvasId] = new Chart(canvas, {
            type: "line",
            data: {
                labels,
                datasets: [{
                    data,
                    borderColor: color,
                    backgroundColor: color + "22",
                    fill: true,
                    tension: 0.35,
                    pointRadius: 4,
                    pointBackgroundColor: color,
                    pointBorderColor: "#0a0e1a",
                    pointBorderWidth: 2,
                    pointHoverRadius: 7,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: "#1a1f35",
                        titleColor: "#f1f5f9",
                        bodyColor: "#94a3b8",
                        borderColor: color + "44",
                        borderWidth: 1,
                        cornerRadius: 8,
                        padding: 10,
                    }
                },
                scales: {
                    x: {
                        ticks: { color: "#64748b", font: { size: 10 } },
                        grid: { color: "rgba(255,255,255,0.04)" },
                    },
                    y: {
                        title: { display: true, text: yLabel, color: "#94a3b8", font: { size: 11 } },
                        ticks: { color: "#64748b", font: { size: 10 } },
                        grid: { color: "rgba(255,255,255,0.04)" },
                    }
                },
                interaction: {
                    intersect: false,
                    mode: "index",
                }
            }
        });
    }

    // ═══════════════════════════════════════════════════════════════════
    // AUTO-REFRESH POLLING
    // ═══════════════════════════════════════════════════════════════════

    async function pollForUpdates() {
        const newIndex = await fetchRunsIndex();
        if (!newIndex) return;

        const oldCount = runsIndex ? runsIndex.runs.length : 0;
        runsIndex = newIndex;
        renderRunList(runsIndex);

        // Flash indicator
        refreshIndicator.classList.add("active");
        setTimeout(() => refreshIndicator.classList.remove("active"), 1500);

        // If new runs appeared and we have a run selected, optionally refresh trends
        if (newIndex.runs.length > oldCount && currentRunTs) {
            renderTrends();
        }

        // Auto-select the latest run if nothing selected
        if (!currentRunTs && newIndex.runs.length > 0) {
            const latest = newIndex.runs[newIndex.runs.length - 1];
            window.__selectRun(latest.timestamp);
        }
    }

    function startPolling() {
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = setInterval(pollForUpdates, POLL_INTERVAL);
    }

    function stopPolling() {
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    }

    autoRefreshToggle.addEventListener("change", () => {
        if (autoRefreshToggle.checked) startPolling();
        else stopPolling();
    });

    // ═══════════════════════════════════════════════════════════════════
    // INIT
    // ═══════════════════════════════════════════════════════════════════

    async function init() {
        runsIndex = await fetchRunsIndex();
        if (runsIndex) {
            renderRunList(runsIndex);
            // Auto-select latest run
            if (runsIndex.runs.length > 0) {
                const latest = runsIndex.runs[runsIndex.runs.length - 1];
                window.__selectRun(latest.timestamp);
            }
        }
        startPolling();
    }

    init();
})();
