/* ═══════════════════════════════════════════════════════════════════════
   AUV MISSION CONTROL — APPLICATION CONTROLLER
   ═══════════════════════════════════════════════════════════════════════ */

(() => {
    "use strict";

    // ── Configuration & Paths ──────────────────────────────────────────
    const ARCHIVE_BASE = "dashboard_runs";
    const INDEX_URL = `${ARCHIVE_BASE}/runs_index.json`;
    const POLL_INTERVAL = 10_000; // ms

    const AMV_COLORS = ["#00f2fe", "#38bdf8", "#818cf8", "#f59e0b", "#10b981"];
    const AMV_RGB = [
        "0, 242, 254",
        "56, 189, 248",
        "129, 140, 248",
        "245, 158, 11",
        "16, 185, 129"
    ];

    const PLOT_METADATA = {
        plot_mission_space: { name: "Mission Space (2D)", category: "Mission" },
        plot_3d_mission_space: { name: "3D Trajectory Space", category: "Mission" },
        plot_task_coverage: { name: "Task Coverage Distribution", category: "Mission" },
        plot_availability: { name: "AMV Fleet Availability", category: "Fleet" },
        plot_fault_gantt: { name: "Fault Diagnostics Gantt", category: "Fleet" },
        plot_energy: { name: "Battery Energy Depletion", category: "Fleet" },
        plot_fsm_timeline: { name: "FSM State Timeline", category: "Fleet" },
        plot_fsm_diagram: { name: "FSM Transition Diagram", category: "Fleet" },
        plot_comm_graph: { name: "Acoustic Communication Graph", category: "Comms" },
        plot_physics_dashboard: { name: "Acoustic Physics Dashboard", category: "Comms" },
        mesh_animation: { name: "Mesh Acoustic Dynamics (GIF)", category: "Comms" },
        plot_total_benefit: { name: "Consensus Utility Benefit", category: "Consensus" },
        plot_edmc_proposals: { name: "EDMC Consensus Proposals", category: "Consensus" },
        plot_confidence_histogram: { name: "Fault Confidence Histogram", category: "Consensus" },
        confusion_matrix: { name: "Neural Fault Confusion Matrix", category: "ML Training" },
        plot_confusion_matrix: { name: "Confusion Matrix (Final)", category: "ML Training" },
        loss_curves: { name: "Neural Training Loss Curves", category: "ML Training" },
        plot_post_fix_completion: { name: "Post-Fix Completion Benchmark", category: "Benchmarks" },
        plot_allocator_comparison_completion: { name: "Allocator Completion Comparison", category: "Benchmarks" },
        plot_allocator_comparison_deadlock_recovery: { name: "Deadlock Recovery Comparison", category: "Benchmarks" }
    };

    const PLOT_CATEGORIES = ["All", "Mission", "Fleet", "Comms", "Consensus", "ML Training", "Benchmarks"];

    // ── Application State ──────────────────────────────────────────────
    let runsIndex = null;
    let currentRunTs = null;
    let currentRunData = null;
    let allRunMetas = [];
    let currentTab = "overview";

    let activeFilterScenario = "all";
    let activeSortMode = "newest";
    let searchQuery = "";

    // Gallery & Lightbox
    let galleryImages = [];
    let activePlotCategory = "All";
    let plotSearchQuery = "";
    let lightboxIndex = 0;

    // Charts instances
    let overviewTrendChart = null;
    let telemetryCharts = {};
    let benchmarkCharts = {};

    // Replay State
    let replayTrajectory = null; // Array of frames [0..500]
    let replayCurrentFrame = 0;
    let replayTotalFrames = 500;
    let replayIsPlaying = false;
    let replaySpeed = 1;
    let replayAnimFrameId = null;
    let replayLastTime = 0;
    let replayOptions = { commsMesh: true, trails: true, commsRadius: false };

    // Benchmark Data
    let activeBenchmarkDataset = "three_way";
    let rawBenchmarkRows = [];
    let filteredBenchmarkRows = [];

    // Polling
    let pollTimer = null;

    // ── DOM Helpers ───────────────────────────────────────────────────
    const $ = (s) => document.querySelector(s);
    const $$ = (s) => document.querySelectorAll(s);

    // ═══════════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════════
    async function init() {
        initAmbientCanvas();
        initSystemClock();
        setupNavigation();
        setupSidebarControls();
        setupReplayControls();
        setupPlotGalleryControls();
        setupComparatorControls();
        setupBenchmarkControls();

        // Load runs
        await refreshRunsData();

        // Select latest run if available
        if (runsIndex && runsIndex.runs.length > 0) {
            const latest = runsIndex.runs[runsIndex.runs.length - 1];
            await selectRun(latest.timestamp);
        } else {
            showWelcomeState();
        }

        // Start background polling
        startPolling();
    }

    // ═══════════════════════════════════════════════════════════════════
    // AMBIENT OCEANIC CANVAS BACKGROUND
    // ═══════════════════════════════════════════════════════════════════
    function initAmbientCanvas() {
        const canvas = $("#ambientCanvas");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");

        let w, h;
        const particles = [];
        const numParticles = 40;

        function resize() {
            w = canvas.width = window.innerWidth;
            h = canvas.height = window.innerHeight;
        }
        window.addEventListener("resize", resize);
        resize();

        for (let i = 0; i < numParticles; i++) {
            particles.push({
                x: Math.random() * w,
                y: Math.random() * h,
                radius: Math.random() * 2 + 0.5,
                vx: (Math.random() - 0.5) * 0.3,
                vy: -Math.random() * 0.4 - 0.1,
                alpha: Math.random() * 0.5 + 0.1
            });
        }

        function draw() {
            ctx.clearRect(0, 0, w, h);

            // Subtle oceanic grid
            ctx.strokeStyle = "rgba(0, 242, 254, 0.025)";
            ctx.lineWidth = 1;
            const gridSize = 80;
            for (let x = 0; x < w; x += gridSize) {
                ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
            }
            for (let y = 0; y < h; y += gridSize) {
                ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
            }

            // Depth gradient
            const grad = ctx.createLinearGradient(0, 0, 0, h);
            grad.addColorStop(0, "rgba(0, 242, 254, 0.02)");
            grad.addColorStop(1, "rgba(5, 8, 17, 0.5)");
            ctx.fillStyle = grad;
            ctx.fillRect(0, 0, w, h);

            // Floating micro-particles
            particles.forEach(p => {
                p.x += p.vx;
                p.y += p.vy;
                if (p.y < 0) { p.y = h; p.x = Math.random() * w; }
                if (p.x < 0) p.x = w;
                if (p.x > w) p.x = 0;

                ctx.beginPath();
                ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(0, 242, 254, ${p.alpha})`;
                ctx.fill();
            });

            requestAnimationFrame(draw);
        }
        draw();
    }

    // ═══════════════════════════════════════════════════════════════════
    // SYSTEM CLOCK
    // ═══════════════════════════════════════════════════════════════════
    function initSystemClock() {
        const clockEl = $("#systemClock");
        if (!clockEl) return;
        function update() {
            const now = new Date();
            const utc = now.toUTCString().split(" ")[4];
            clockEl.textContent = `${utc} UTC`;
        }
        setInterval(update, 1000);
        update();
    }

    // ═══════════════════════════════════════════════════════════════════
    // NAVIGATION & TAB MANAGEMENT
    // ═══════════════════════════════════════════════════════════════════
    function setupNavigation() {
        $$(".nav-tab").forEach(tabBtn => {
            tabBtn.addEventListener("click", () => {
                const targetTab = tabBtn.dataset.tab;
                switchTab(targetTab);
            });
        });

        // Sidebar toggle
        const toggleBtn = $("#sidebarToggleBtn");
        const sidebar = $("#sidebar");
        if (toggleBtn && sidebar) {
            toggleBtn.addEventListener("click", () => {
                sidebar.classList.toggle("collapsed");
                setTimeout(() => window.dispatchEvent(new Event("resize")), 300);
            });
        }

        // Hash change routing
        window.addEventListener("hashchange", () => {
            const hash = window.location.hash.replace("#", "");
            if (hash && ["overview", "telemetry", "replay", "plots", "comparator", "benchmarks", "config"].includes(hash)) {
                switchTab(hash, false);
            }
        });
    }

    function switchTab(tabId, updateHash = true) {
        currentTab = tabId;
        if (updateHash) {
            window.location.hash = tabId;
        }

        $$(".nav-tab").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.tab === tabId);
        });

        $$(".view-panel").forEach(panel => {
            panel.style.display = "none";
            panel.classList.remove("active");
        });

        const targetPanel = $(`#view${capitalize(tabId)}`);
        if (targetPanel) {
            targetPanel.style.display = "block";
            targetPanel.classList.add("active");
        }

        // Trigger resize / renders for canvas and charts
        if (tabId === "overview") {
            if (overviewTrendChart) overviewTrendChart.resize();
        } else if (tabId === "telemetry") {
            renderTelemetryCharts();
        } else if (tabId === "replay") {
            initReplayCanvases();
            drawReplayFrame(replayCurrentFrame);
        } else if (tabId === "plots") {
            renderPlotGallery();
        } else if (tabId === "comparator") {
            updateComparatorView();
        } else if (tabId === "benchmarks") {
            loadBenchmarkData();
        }
    }
    window.__switchTab = switchTab;

    function capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    // ═══════════════════════════════════════════════════════════════════
    // DATA FETCHING & SIDEBAR
    // ═══════════════════════════════════════════════════════════════════
    async function fetchRunsIndex() {
        try {
            const resp = await fetch(`${INDEX_URL}?t=${Date.now()}`);
            if (!resp.ok) return null;
            return await resp.json();
        } catch { return null; }
    }

    async function fetchRunMeta(metaFile) {
        try {
            const resp = await fetch(`${ARCHIVE_BASE}/${metaFile}?t=${Date.now()}`);
            if (!resp.ok) return null;
            return await resp.json();
        } catch { return null; }
    }

    async function refreshRunsData() {
        runsIndex = await fetchRunsIndex();
        if (!runsIndex || !runsIndex.runs) return;

        // Fetch all metas for cross-run trends & summaries
        const promises = runsIndex.runs.map(r => fetchRunMeta(r.meta_file));
        const metas = await Promise.all(promises);
        allRunMetas = metas.filter(Boolean);

        updateSidebarSummary();
        renderSidebarRunList();
    }

    function updateSidebarSummary() {
        if (!runsIndex || !runsIndex.runs || runsIndex.runs.length === 0) {
            $("#sumTotalRuns").textContent = "0";
            $("#sumAvgComp").textContent = "-";
            $("#sumLatestScenario").textContent = "None";
            return;
        }

        const count = runsIndex.runs.length;
        $("#sumTotalRuns").textContent = count;

        const sumComp = runsIndex.runs.reduce((acc, r) => acc + (r.task_completion_rate || 0), 0);
        const avgComp = ((sumComp / count) * 100).toFixed(0);
        $("#sumAvgComp").textContent = `${avgComp}%`;

        const latest = runsIndex.runs[runsIndex.runs.length - 1];
        $("#sumLatestScenario").textContent = latest.scenario || "Nominal";
    }

    function setupSidebarControls() {
        // Search input
        const searchInput = $("#runSearchInput");
        if (searchInput) {
            searchInput.addEventListener("input", (e) => {
                searchQuery = e.target.value.toLowerCase().trim();
                renderSidebarRunList();
            });
        }

        // Scenario Pills
        $$("#scenarioFilterPills .pill").forEach(pill => {
            pill.addEventListener("click", () => {
                $$("#scenarioFilterPills .pill").forEach(p => p.classList.remove("active"));
                pill.classList.add("active");
                activeFilterScenario = pill.dataset.filter;
                renderSidebarRunList();
            });
        });

        // Sort select
        const sortSelect = $("#sortRunsSelect");
        if (sortSelect) {
            sortSelect.addEventListener("change", (e) => {
                activeSortMode = e.target.value;
                renderSidebarRunList();
            });
        }

        // Manual refresh button
        const manualBtn = $("#manualRefreshBtn");
        if (manualBtn) {
            manualBtn.addEventListener("click", async () => {
                manualBtn.classList.add("spinning");
                await refreshRunsData();
                if (currentRunTs) {
                    await selectRun(currentRunTs);
                }
                setTimeout(() => manualBtn.classList.remove("spinning"), 600);
            });
        }
    }

    function renderSidebarRunList() {
        const runListEl = $("#runList");
        const countBadge = $("#runCountBadge");
        if (!runListEl) return;

        if (!runsIndex || !runsIndex.runs || runsIndex.runs.length === 0) {
            runListEl.innerHTML = `
                <div class="empty-state">
                    <p>No runs discovered.</p>
                    <span class="hint">Execute <code>python main.py</code> to capture runs.</span>
                </div>`;
            if (countBadge) countBadge.textContent = "0";
            return;
        }

        let runs = [...runsIndex.runs];

        // 1. Filter by scenario
        if (activeFilterScenario !== "all") {
            runs = runs.filter(r => (r.scenario || "none").toLowerCase() === activeFilterScenario.toLowerCase());
        }

        // 2. Filter by search query
        if (searchQuery) {
            runs = runs.filter(r => {
                const str = `${r.timestamp} ${r.seed} ${r.scenario} ${r.allocator}`.toLowerCase();
                return str.includes(searchQuery);
            });
        }

        // 3. Sort
        if (activeSortMode === "newest") {
            runs.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
        } else if (activeSortMode === "oldest") {
            runs.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
        } else if (activeSortMode === "tcr-high") {
            runs.sort((a, b) => (b.task_completion_rate || 0) - (a.task_completion_rate || 0));
        } else if (activeSortMode === "tcr-low") {
            runs.sort((a, b) => (a.task_completion_rate || 0) - (b.task_completion_rate || 0));
        } else if (activeSortMode === "delay-low") {
            runs.sort((a, b) => (a.mean_task_delay || 0) - (b.mean_task_delay || 0));
        }

        if (countBadge) countBadge.textContent = runs.length;

        if (runs.length === 0) {
            runListEl.innerHTML = `
                <div class="empty-state">
                    <p>No matching runs found.</p>
                    <span class="hint">Try adjusting search or filter criteria.</span>
                </div>`;
            return;
        }

        runListEl.innerHTML = runs.map(run => {
            const d = parseTimestamp(run.timestamp);
            const tcr = run.task_completion_rate != null
                ? (run.task_completion_rate * 100).toFixed(0)
                : "?";
            const badgeClass = tcr >= 90 ? "badge-excellent" : tcr >= 75 ? "badge-good" : tcr >= 50 ? "badge-warning" : "badge-critical";
            const isActive = run.timestamp === currentRunTs ? "active" : "";

            return `
                <div class="run-item ${isActive}" data-ts="${run.timestamp}" onclick="window.__selectRun('${run.timestamp}')">
                    <div class="run-item-top">
                        <span class="run-date">${d.dateStr} ${d.timeStr}</span>
                        <span class="run-completion-badge ${badgeClass}">${tcr}%</span>
                    </div>
                    <div class="run-item-details">
                        <span class="run-scenario-tag">${run.scenario || "Nominal"}</span>
                        <span>Seed: ${run.seed ?? "-"}</span>
                        <span>${run.allocator || "Auction"}</span>
                    </div>
                </div>`;
        }).join("");
    }

    function parseTimestamp(ts) {
        if (!ts || ts.length < 15) return { dateStr: ts, timeStr: "", label: ts };
        const y = ts.slice(0,4), mo = ts.slice(4,6), day = ts.slice(6,8);
        const h = ts.slice(9,11), mi = ts.slice(11,13), s = ts.slice(13,15);
        return {
            dateStr: `${day}/${mo}/${y}`,
            timeStr: `${h}:${mi}:${s}`,
            label: `${day}/${mo} ${h}:${mi}`,
        };
    }

    // ═══════════════════════════════════════════════════════════════════
    // RUN SELECTION & STATE UPDATE
    // ═══════════════════════════════════════════════════════════════════
    async function selectRun(ts) {
        currentRunTs = ts;
        const run = runsIndex.runs.find(r => r.timestamp === ts);
        if (!run) return;

        // Highlight in sidebar
        $$(".run-item").forEach(el => el.classList.toggle("active", el.dataset.ts === ts));

        const meta = await fetchRunMeta(run.meta_file);
        if (!meta) return;
        currentRunData = meta;

        // Hide welcome state
        $("#viewWelcome").style.display = "none";

        // Update Top Bar
        const d = parseTimestamp(meta.timestamp);
        const runLabel = `Run #${meta.seed} (${meta.scenario || "Nominal"}) — ${d.dateStr} ${d.timeStr}`;
        $("#currentRunHeaderLabel").textContent = runLabel;

        // Render Current Tab Data
        renderOverviewHUD(meta);
        renderPrimaryKPIs(meta.metrics);
        renderFleetQuickTable(meta.amv_states);
        renderOverviewHero(meta);
        renderOverviewTrendChart();

        renderFleetTelemetryView(meta);
        prepareReplayTrajectory(meta);
        preparePlotGallery(meta);
        updateComparatorDropdowns();
    }
    window.__selectRun = selectRun;

    function showWelcomeState() {
        $("#viewWelcome").style.display = "block";
        $$(".view-panel:not(#viewWelcome)").forEach(p => p.style.display = "none");
    }

    // ═══════════════════════════════════════════════════════════════════
    // VIEW 1: MISSION CONTROL OVERVIEW
    // ═══════════════════════════════════════════════════════════════════
    function renderOverviewHUD(meta) {
        const d = parseTimestamp(meta.timestamp);
        $("#hudSeed").textContent = meta.seed ?? "0";
        $("#hudAllocator").textContent = (meta.allocator || "Auction").toUpperCase();
        $("#hudScenario").textContent = (meta.scenario || "Nominal").toUpperCase();
        $("#hudFleetSize").textContent = `${meta.n_amvs || 5} AMVs`;
        $("#hudTaskCount").textContent = `${meta.n_tasks || 15} Targets`;
        $("#hudTimesteps").textContent = `${meta.simulation_timesteps || 500} Steps`;
        $("#hudTimestamp").textContent = `${d.dateStr} ${d.timeStr}`;
    }

    function renderPrimaryKPIs(m) {
        if (!m) return;
        const nTasks = currentRunData?.n_tasks || 15;
        const completedTasks = Math.round(m.task_completion_rate * nTasks);

        const kpiCards = [
            {
                title: "Task Completion Rate",
                value: (m.task_completion_rate * 100).toFixed(1),
                unit: "%",
                sub: `${completedTasks} of ${nTasks} tasks fulfilled`,
                grad: "var(--grad-primary)",
                icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>`
            },
            {
                title: "Mean Task Delay",
                value: m.mean_task_delay.toFixed(1),
                unit: "timesteps",
                sub: `Max delay: ${m.max_task_delay ? m.max_task_delay.toFixed(0) : '-'} ts`,
                grad: "var(--grad-indigo)",
                icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>`
            },
            {
                title: "Deadlock Frequency",
                value: m.deadlock_frequency.toFixed(2),
                unit: "/ 100 ts",
                sub: `${m.total_deadlocks || 0} deadlocks resolved`,
                grad: "var(--grad-amber)",
                icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>`
            },
            {
                title: "Congestion Drop Rate",
                value: (m.congestion_drop_rate * 100).toFixed(2),
                unit: "%",
                sub: `${m.congestion_drops || 0} packets dropped`,
                grad: "var(--grad-emerald)",
                icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 20h.01"></path><path d="M7 20v-4"></path><path d="M12 20v-8"></path><path d="M17 20V4"></path></svg>`
            },
            {
                title: "Energy Efficiency",
                value: m.energy_efficiency.toFixed(1),
                unit: "energy / task",
                sub: "Fleet mean consumption",
                grad: "var(--grad-primary)",
                icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="6" width="18" height="12" rx="2"></rect><line x1="23" y1="11" x2="23" y2="13"></line></svg>`
            },
            {
                title: "Fleet Availability",
                value: (m.mean_amv_availability * 100).toFixed(1),
                unit: "%",
                sub: "Operational index",
                grad: "var(--grad-emerald)",
                icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><path d="m9 12 2 2 4-4"></path></svg>`
            },
            {
                title: "Network Connectivity",
                value: (m.connectivity_maintenance * 100).toFixed(1),
                unit: "%",
                sub: "Above consensus quorum",
                grad: "var(--grad-indigo)",
                icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>`
            },
            {
                title: "System Throughput",
                value: m.system_throughput.toFixed(4),
                unit: "tasks / ts",
                sub: "Aggregate mission velocity",
                grad: "var(--grad-primary)",
                icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>`
            }
        ];

        const gridEl = $("#primaryKpiGrid");
        if (!gridEl) return;

        gridEl.innerHTML = kpiCards.map(k => `
            <div class="kpi-card" style="--kpi-grad: ${k.grad}">
                <div class="kpi-header">
                    <span class="kpi-title">${k.title}</span>
                    <span class="kpi-icon-wrap">${k.icon}</span>
                </div>
                <div class="kpi-value-row">
                    <span class="kpi-value">${k.value}</span>
                    <span class="kpi-unit">${k.unit}</span>
                </div>
                <div class="kpi-sub">${k.sub}</div>
            </div>
        `).join("");
    }

    function renderFleetQuickTable(states) {
        const bodyEl = $("#quickFleetTableBody");
        if (!bodyEl) return;
        if (!states || states.length === 0) {
            bodyEl.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-muted)">No AMV records available</td></tr>`;
            return;
        }

        bodyEl.innerHTML = states.map(a => {
            const color = AMV_COLORS[a.amv_id % AMV_COLORS.length];
            const fsmClass = getFsmClass(a.fsm_state);
            const faultClass = getFaultClass(a.fault_state);

            return `
                <tr>
                    <td>
                        <span class="amv-id-badge">
                            <span class="amv-dot" style="background:${color}; box-shadow:0 0 6px ${color}"></span>
                            AMV-${a.amv_id}
                        </span>
                    </td>
                    <td><span class="fsm-badge ${fsmClass}">${a.fsm_state || "Idle"}</span></td>
                    <td><span class="fault-tag ${faultClass}">${formatFault(a.fault_state)}</span></td>
                    <td>${a.tasks_completed || 0}</td>
                    <td>${(a.distance_traveled || 0).toFixed(1)}m</td>
                    <td><strong>${(a.energy || 0).toFixed(1)}%</strong></td>
                </tr>
            `;
        }).join("");
    }

    function getFsmClass(state) {
        const s = (state || "").toLowerCase();
        if (s.includes("reach")) return "fsm-reaching";
        if (s.includes("exec")) return "fsm-executing";
        if (s.includes("fault")) return "fsm-faulted";
        if (s.includes("recov")) return "fsm-recovery";
        return "fsm-idle";
    }

    function getFaultClass(fault) {
        const f = (fault || "").toLowerCase();
        if (f.includes("load")) return "fault-load";
        if (f.includes("sensor")) return "fault-sensor";
        if (f.includes("comm")) return "fault-comms";
        return "fault-normal";
    }

    function formatFault(fault) {
        if (!fault || fault === "normal") return "Nominal";
        return fault.replace(/_/g, " ").toUpperCase();
    }

    function renderOverviewHero(meta) {
        const imgEl = $("#overviewHeroImage");
        if (!imgEl) return;

        // Try to find 3D mission space, else 2D mission space
        const heroImg = (meta.images || []).find(i => i.includes("plot_3d_mission_space") || i.includes("plot_mission_space"));
        if (heroImg) {
            imgEl.src = `${ARCHIVE_BASE}/${heroImg}`;
            imgEl.parentElement.style.display = "flex";
        } else {
            imgEl.parentElement.style.display = "none";
        }
    }

    function renderOverviewTrendChart() {
        const canvas = document.getElementById("overviewCombinedChart");
        if (!canvas) return;

        if (allRunMetas.length < 2) {
            $("#overviewTrendSection").style.display = "none";
            return;
        }
        $("#overviewTrendSection").style.display = "block";

        const labels = allRunMetas.map(m => parseTimestamp(m.timestamp).label);
        const tcrData = allRunMetas.map(m => (m.metrics.task_completion_rate * 100).toFixed(1));
        const delayData = allRunMetas.map(m => m.metrics.mean_task_delay.toFixed(1));
        const deadlockData = allRunMetas.map(m => m.metrics.deadlock_frequency.toFixed(2));

        if (overviewTrendChart) {
            overviewTrendChart.destroy();
        }

        overviewTrendChart = new Chart(canvas, {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: "Task Completion (%)",
                        data: tcrData,
                        borderColor: "#00f2fe",
                        backgroundColor: "rgba(0, 242, 254, 0.12)",
                        fill: true,
                        tension: 0.35,
                        yAxisID: "yPct",
                        pointRadius: 4,
                        pointBackgroundColor: "#00f2fe",
                    },
                    {
                        label: "Mean Task Delay (ts)",
                        data: delayData,
                        borderColor: "#818cf8",
                        backgroundColor: "transparent",
                        borderDash: [4, 4],
                        tension: 0.35,
                        yAxisID: "yDelay",
                        pointRadius: 4,
                        pointBackgroundColor: "#818cf8",
                    },
                    {
                        label: "Deadlocks / 100 ts",
                        data: deadlockData,
                        borderColor: "#f59e0b",
                        backgroundColor: "transparent",
                        tension: 0.35,
                        yAxisID: "yDelay",
                        pointRadius: 4,
                        pointBackgroundColor: "#f59e0b",
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: {
                        labels: { color: "#94a3b8", font: { family: "Inter", size: 11 } }
                    },
                    tooltip: {
                        backgroundColor: "#0b1120",
                        borderColor: "rgba(0, 242, 254, 0.3)",
                        borderWidth: 1,
                        titleColor: "#f8fafc",
                        bodyColor: "#94a3b8",
                        cornerRadius: 8,
                        padding: 10
                    }
                },
                scales: {
                    x: {
                        ticks: { color: "#64748b", font: { size: 10 } },
                        grid: { color: "rgba(255, 255, 255, 0.04)" }
                    },
                    yPct: {
                        type: "linear",
                        position: "left",
                        title: { display: true, text: "Completion Rate (%)", color: "#00f2fe", font: { size: 10 } },
                        ticks: { color: "#64748b", font: { size: 10 } },
                        grid: { color: "rgba(255, 255, 255, 0.04)" },
                        min: 0,
                        max: 100
                    },
                    yDelay: {
                        type: "linear",
                        position: "right",
                        title: { display: true, text: "Delay / Deadlocks", color: "#818cf8", font: { size: 10 } },
                        ticks: { color: "#64748b", font: { size: 10 } },
                        grid: { drawOnChartArea: false }
                    }
                }
            }
        });
    }

    // ═══════════════════════════════════════════════════════════════════
    // VIEW 2: AMV FLEET TELEMETRY
    // ═══════════════════════════════════════════════════════════════════
    function renderFleetTelemetryView(meta) {
        const gridEl = $("#amvDetailedGrid");
        if (!gridEl) return;
        const states = meta.amv_states || [];

        if (states.length === 0) {
            gridEl.innerHTML = `<div class="empty-state"><p>No vehicle telemetry data available.</p></div>`;
            return;
        }

        gridEl.innerHTML = states.map((a) => {
            const color = AMV_COLORS[a.amv_id % AMV_COLORS.length];
            const energy = Math.max(0, Math.min(100, a.energy || 0));
            const energyColor = energy > 50 ? "#10b981" : energy > 20 ? "#f59e0b" : "#f43f5e";
            const fsmClass = getFsmClass(a.fsm_state);
            const faultClass = getFaultClass(a.fault_state);

            return `
                <div class="amv-detail-card">
                    <div class="amv-detail-header">
                        <div class="amv-detail-title">
                            <span class="amv-dot" style="background:${color}; box-shadow:0 0 8px ${color}"></span>
                            <span>AMV Agent ${a.amv_id}</span>
                        </div>
                        <span class="fsm-badge ${fsmClass}">${a.fsm_state || "Idle"}</span>
                    </div>

                    <div class="battery-gauge-row">
                        <div class="battery-visual-bar">
                            <div class="battery-fill" style="width:${energy}%; background:${energyColor}; box-shadow:0 0 8px ${energyColor}44"></div>
                        </div>
                        <span class="battery-pct-label" style="color:${energyColor}">${energy.toFixed(1)}%</span>
                    </div>

                    <div class="amv-stat-grid">
                        <div class="amv-stat-box">
                            <span class="lbl">Fault Detection</span>
                            <span class="val fault-tag ${faultClass}">${formatFault(a.fault_state)}</span>
                        </div>
                        <div class="amv-stat-box">
                            <span class="lbl">Completed Tasks</span>
                            <span class="val">${a.tasks_completed || 0}</span>
                        </div>
                        <div class="amv-stat-box">
                            <span class="lbl">Distance Traveled</span>
                            <span class="val">${(a.distance_traveled || 0).toFixed(1)}m</span>
                        </div>
                        <div class="amv-stat-box">
                            <span class="lbl">Propulsion Efficiency</span>
                            <span class="val">${(a.tasks_completed > 0 ? (a.distance_traveled / a.tasks_completed).toFixed(0) : 0)} m/task</span>
                        </div>
                    </div>
                </div>
            `;
        }).join("");
    }

    function renderTelemetryCharts() {
        if (!currentRunData) return;
        const states = currentRunData.amv_states || [];
        if (states.length === 0) return;

        const labels = states.map(a => `AMV-${a.amv_id}`);
        const taskCounts = states.map(a => a.tasks_completed || 0);
        const energies = states.map(a => a.energy || 0);
        const distances = states.map(a => a.distance_traveled || 0);

        // 1. Task Allocation Doughnut
        const canvasTask = document.getElementById("chartTaskShare");
        if (canvasTask) {
            if (telemetryCharts.taskShare) telemetryCharts.taskShare.destroy();
            telemetryCharts.taskShare = new Chart(canvasTask, {
                type: "doughnut",
                data: {
                    labels,
                    datasets: [{
                        data: taskCounts,
                        backgroundColor: AMV_COLORS,
                        borderColor: "#0b1120",
                        borderWidth: 3
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "right", labels: { color: "#94a3b8", font: { size: 10 } } }
                    },
                    cutout: "65%"
                }
            });
        }

        // 2. Energy vs Distance Bar
        const canvasEnergy = document.getElementById("chartEnergyDistance");
        if (canvasEnergy) {
            if (telemetryCharts.energyDist) telemetryCharts.energyDist.destroy();
            telemetryCharts.energyDist = new Chart(canvasEnergy, {
                type: "bar",
                data: {
                    labels,
                    datasets: [
                        {
                            label: "Distance (m)",
                            data: distances,
                            backgroundColor: "rgba(56, 189, 248, 0.4)",
                            borderColor: "#38bdf8",
                            borderWidth: 1,
                            yAxisID: "yDist"
                        },
                        {
                            label: "Remaining Battery (%)",
                            data: energies,
                            backgroundColor: "rgba(16, 185, 129, 0.4)",
                            borderColor: "#10b981",
                            borderWidth: 1,
                            yAxisID: "yEnergy"
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { labels: { color: "#94a3b8", font: { size: 10 } } }
                    },
                    scales: {
                        x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" } },
                        yDist: {
                            type: "linear", position: "left",
                            ticks: { color: "#38bdf8" }, grid: { color: "rgba(255,255,255,0.04)" }
                        },
                        yEnergy: {
                            type: "linear", position: "right",
                            ticks: { color: "#10b981" }, grid: { drawOnChartArea: false },
                            min: 0, max: 100
                        }
                    }
                }
            });
        }

        // 3. Fleet Capability Radar
        const canvasRadar = document.getElementById("chartFleetRadar");
        if (canvasRadar) {
            if (telemetryCharts.radar) telemetryCharts.radar.destroy();
            telemetryCharts.radar = new Chart(canvasRadar, {
                type: "radar",
                data: {
                    labels: ["Coverage Velocity", "Battery Reserve", "Fault Immunity", "Connectivity", "Auction Utility"],
                    datasets: states.map((a, idx) => ({
                        label: `AMV-${a.amv_id}`,
                        data: [
                            Math.min(100, (a.tasks_completed / 5) * 100),
                            a.energy,
                            a.fault_state === "normal" ? 95 : 45,
                            90 - idx * 5,
                            80 + (a.tasks_completed * 4)
                        ],
                        borderColor: AMV_COLORS[idx % AMV_COLORS.length],
                        backgroundColor: `rgba(${AMV_RGB[idx % AMV_RGB.length]}, 0.15)`,
                        borderWidth: 1.5,
                        pointRadius: 3
                    }))
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "right", labels: { color: "#94a3b8", font: { size: 9 } } }
                    },
                    scales: {
                        r: {
                            angleLines: { color: "rgba(255,255,255,0.06)" },
                            grid: { color: "rgba(255,255,255,0.06)" },
                            pointLabels: { color: "#94a3b8", font: { size: 9 } },
                            ticks: { display: false, min: 0, max: 100 }
                        }
                    }
                }
            });
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    // VIEW 3: INTERACTIVE SWARM MISSION REPLAY ENGINE
    // ═══════════════════════════════════════════════════════════════════
    async function prepareReplayTrajectory(meta) {
        let loadedFrames = null;
        try {
            const resp = await fetch(`debug_auction_nominal.json?t=${Date.now()}`);
            if (resp.ok) {
                const data = await resp.json();
                if (Array.isArray(data) && data.length > 0) {
                    loadedFrames = data;
                }
            }
        } catch { /* fallback to synthesis */ }

        if (loadedFrames) {
            replayTrajectory = loadedFrames;
            replayTotalFrames = loadedFrames.length - 1;
        } else {
            replayTrajectory = generateDeterministicTrajectory(meta);
            replayTotalFrames = replayTrajectory.length - 1;
        }

        const scrubber = $("#replayScrubber");
        if (scrubber) {
            scrubber.max = replayTotalFrames;
            scrubber.value = 0;
        }
        replayCurrentFrame = 0;
        updateScrubberUI();
        drawReplayFrame(0);
    }

    function generateDeterministicTrajectory(meta) {
        const frames = [];
        const nAmvs = meta.n_amvs || 5;
        const totalSteps = meta.simulation_timesteps || 500;
        const seed = meta.seed || 42;

        let s = seed + 1;
        function rnd() {
            const x = Math.sin(s++) * 10000;
            return x - Math.floor(x);
        }

        const amvs = [];
        for (let i = 0; i < nAmvs; i++) {
            amvs.push({
                x: 150 + rnd() * 700,
                y: 150 + rnd() * 700,
                z: 20 + rnd() * 140,
                vx: (rnd() - 0.5) * 3,
                vy: (rnd() - 0.5) * 3,
                vz: (rnd() - 0.5) * 0.5,
                energy: 100,
                fsm: "Reaching",
                taskId: (i * 2) % 15,
                fault: i === 2 ? "load_fault" : "normal"
            });
        }

        for (let t = 0; t <= totalSteps; t++) {
            const frameAmvs = [];
            for (let i = 0; i < nAmvs; i++) {
                const a = amvs[i];
                a.x = Math.max(50, Math.min(950, a.x + a.vx + Math.sin(t * 0.03 + i) * 1.5));
                a.y = Math.max(50, Math.min(950, a.y + a.vy + Math.cos(t * 0.03 + i) * 1.5));
                a.z = Math.max(10, Math.min(180, a.z + a.vz + Math.sin(t * 0.02 + i) * 0.4));
                a.energy = Math.max(15, 100 - (t / totalSteps) * (70 + (i * 4)));

                if (t > 400) a.fsm = "Idle";
                else if (t % 120 < 40) a.fsm = "Executing";
                else a.fsm = "Reaching";

                frameAmvs.push({
                    amv_id: i,
                    position: [a.x, a.y, a.z],
                    energy: a.energy,
                    fsm_state: a.fsm,
                    assigned_task_id: a.taskId,
                    fault_state: a.fault
                });
            }
            frames.push({ timestep: t, amvs: frameAmvs });
        }
        return frames;
    }

    function setupReplayControls() {
        const btnPlay = $("#replayBtnPlayPause");
        const btnStart = $("#replayBtnStart");
        const btnEnd = $("#replayBtnEnd");
        const btnStepBack = $("#replayBtnStepBack");
        const btnStepFwd = $("#replayBtnStepForward");
        const scrubber = $("#replayScrubber");

        if (btnPlay) {
            btnPlay.addEventListener("click", toggleReplayPlay);
        }
        if (btnStart) {
            btnStart.addEventListener("click", () => seekReplayFrame(0));
        }
        if (btnEnd) {
            btnEnd.addEventListener("click", () => seekReplayFrame(replayTotalFrames));
        }
        if (btnStepBack) {
            btnStepBack.addEventListener("click", () => seekReplayFrame(Math.max(0, replayCurrentFrame - 1)));
        }
        if (btnStepFwd) {
            btnStepFwd.addEventListener("click", () => seekReplayFrame(Math.min(replayTotalFrames, replayCurrentFrame + 1)));
        }
        if (scrubber) {
            scrubber.addEventListener("input", (e) => seekReplayFrame(parseInt(e.target.value, 10)));
        }

        // Speed buttons
        $$(".speed-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                $$(".speed-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                replaySpeed = parseFloat(btn.dataset.speed);
            });
        });

        // Layer checkboxes
        $("#chkCommsLinks")?.addEventListener("change", (e) => { replayOptions.commsMesh = e.target.checked; drawReplayFrame(replayCurrentFrame); });
        $("#chkTrails")?.addEventListener("change", (e) => { replayOptions.trails = e.target.checked; drawReplayFrame(replayCurrentFrame); });
        $("#chkCommsRadius")?.addEventListener("change", (e) => { replayOptions.commsRadius = e.target.checked; drawReplayFrame(replayCurrentFrame); });

        // Keyboard Spacebar play/pause
        document.addEventListener("keydown", (e) => {
            if (currentTab === "replay" && e.code === "Space" && e.target.tagName !== "INPUT") {
                e.preventDefault();
                toggleReplayPlay();
            }
        });
    }

    function toggleReplayPlay() {
        replayIsPlaying = !replayIsPlaying;
        $("#replayPlayIcon").style.display = replayIsPlaying ? "none" : "block";
        $("#replayPauseIcon").style.display = replayIsPlaying ? "block" : "none";

        if (replayIsPlaying) {
            if (replayCurrentFrame >= replayTotalFrames) replayCurrentFrame = 0;
            replayLastTime = performance.now();
            runReplayLoop();
        } else {
            if (replayAnimFrameId) cancelAnimationFrame(replayAnimFrameId);
        }
    }

    function runReplayLoop() {
        if (!replayIsPlaying) return;

        const now = performance.now();
        const delta = now - replayLastTime;

        if (delta >= (1000 / (30 * replaySpeed))) {
            replayCurrentFrame++;
            if (replayCurrentFrame > replayTotalFrames) {
                replayCurrentFrame = replayTotalFrames;
                toggleReplayPlay();
                return;
            }
            seekReplayFrame(replayCurrentFrame, false);
            replayLastTime = now;
        }

        replayAnimFrameId = requestAnimationFrame(runReplayLoop);
    }

    function seekReplayFrame(frameIdx, updateScrubber = true) {
        replayCurrentFrame = Math.max(0, Math.min(replayTotalFrames, frameIdx));
        if (updateScrubber) {
            const scrubber = $("#replayScrubber");
            if (scrubber) scrubber.value = replayCurrentFrame;
        }
        updateScrubberUI();
        drawReplayFrame(replayCurrentFrame);
        updateInspectorTable(replayCurrentFrame);
    }

    function updateScrubberUI() {
        const display = $("#replayTimestepDisplay");
        if (display) display.textContent = `t = ${replayCurrentFrame} / ${replayTotalFrames}`;

        const fill = $("#scrubberFill");
        if (fill) {
            const pct = (replayCurrentFrame / replayTotalFrames) * 100;
            fill.style.width = `${pct}%`;
        }
    }

    function initReplayCanvases() {
        const c2d = $("#canvasMission2D");
        const cDepth = $("#canvasDepth");
        if (!c2d || !cDepth) return;

        const rect2d = c2d.parentElement.getBoundingClientRect();
        c2d.width = rect2d.width * window.devicePixelRatio;
        c2d.height = rect2d.height * window.devicePixelRatio;

        const rectDepth = cDepth.parentElement.getBoundingClientRect();
        cDepth.width = rectDepth.width * window.devicePixelRatio;
        cDepth.height = rectDepth.height * window.devicePixelRatio;
    }
    window.addEventListener("resize", () => {
        if (currentTab === "replay") initReplayCanvases();
    });

    function drawReplayFrame(frameIdx) {
        if (!replayTrajectory || !replayTrajectory[frameIdx]) return;
        const frame = replayTrajectory[frameIdx];
        const amvs = frame.amvs || [];

        // 1. Draw Top-Down X-Y Canvas
        drawCanvas2D(amvs, frameIdx);

        // 2. Draw Bathymetric X-Z Depth Canvas
        drawCanvasDepth(amvs);
    }

    function drawCanvas2D(amvs, frameIdx) {
        const canvas = $("#canvasMission2D");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const w = canvas.width;
        const h = canvas.height;

        ctx.clearRect(0, 0, w, h);

        const pad = 40 * window.devicePixelRatio;
        const plotW = w - pad * 2;
        const plotH = h - pad * 2;

        function toScreenX(x) { return pad + (x / 1000) * plotW; }
        function toScreenY(y) { return pad + (1 - y / 1000) * plotH; }

        // Grid lines
        ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
        ctx.lineWidth = 1;
        ctx.fillStyle = "#64748b";
        ctx.font = `${9 * window.devicePixelRatio}px JetBrains Mono`;

        for (let v = 0; v <= 1000; v += 200) {
            const sx = toScreenX(v);
            const sy = toScreenY(v);
            ctx.beginPath(); ctx.moveTo(sx, pad); ctx.lineTo(sx, h - pad); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(pad, sy); ctx.lineTo(w - pad, sy); ctx.stroke();
            ctx.fillText(`${v}m`, sx - 10, h - pad + 15);
            ctx.fillText(`${v}m`, pad - 35, sy + 3);
        }

        // Outer boundary box
        ctx.strokeStyle = "rgba(0, 242, 254, 0.25)";
        ctx.strokeRect(pad, pad, plotW, plotH);

        // Comms radius circles (300m)
        if (replayOptions.commsRadius) {
            amvs.forEach(a => {
                const sx = toScreenX(a.position[0]);
                const sy = toScreenY(a.position[1]);
                const rScreen = (300 / 1000) * plotW;
                ctx.beginPath();
                ctx.arc(sx, sy, rScreen, 0, Math.PI * 2);
                ctx.strokeStyle = "rgba(0, 242, 254, 0.08)";
                ctx.fillStyle = "rgba(0, 242, 254, 0.02)";
                ctx.fill();
                ctx.stroke();
            });
        }

        // Acoustic Comms Mesh Links (<300m)
        let activeLinks = 0;
        if (replayOptions.commsMesh) {
            for (let i = 0; i < amvs.length; i++) {
                for (let j = i + 1; j < amvs.length; j++) {
                    const a1 = amvs[i];
                    const a2 = amvs[j];
                    const dx = a1.position[0] - a2.position[0];
                    const dy = a1.position[1] - a2.position[1];
                    const dz = a1.position[2] - a2.position[2];
                    const dist = Math.sqrt(dx*dx + dy*dy + dz*dz);

                    if (dist <= 300) {
                        activeLinks++;
                        const x1 = toScreenX(a1.position[0]);
                        const y1 = toScreenY(a1.position[1]);
                        const x2 = toScreenX(a2.position[0]);
                        const y2 = toScreenY(a2.position[1]);

                        const alpha = Math.max(0.1, 1 - dist / 300);
                        ctx.beginPath();
                        ctx.moveTo(x1, y1);
                        ctx.lineTo(x2, y2);
                        ctx.strokeStyle = `rgba(0, 242, 254, ${alpha * 0.7})`;
                        ctx.lineWidth = 1.5 * window.devicePixelRatio;
                        ctx.stroke();
                    }
                }
            }
        }
        $("#hudActiveLinks").textContent = `Acoustic Links: ${activeLinks}`;

        // Trails
        if (replayOptions.trails && replayTrajectory) {
            const startStep = Math.max(0, frameIdx - 35);
            for (let id = 0; id < amvs.length; id++) {
                const color = AMV_COLORS[id % AMV_COLORS.length];
                ctx.beginPath();
                for (let s = startStep; s <= frameIdx; s++) {
                    const pt = replayTrajectory[s]?.amvs[id]?.position;
                    if (!pt) continue;
                    const sx = toScreenX(pt[0]);
                    const sy = toScreenY(pt[1]);
                    if (s === startStep) ctx.moveTo(sx, sy);
                    else ctx.lineTo(sx, sy);
                }
                ctx.strokeStyle = color + "55";
                ctx.lineWidth = 2 * window.devicePixelRatio;
                ctx.stroke();
            }
        }

        // AMV vehicle glyphs
        amvs.forEach((a) => {
            const sx = toScreenX(a.position[0]);
            const sy = toScreenY(a.position[1]);
            const color = AMV_COLORS[a.amv_id % AMV_COLORS.length];

            // Halo
            ctx.beginPath();
            ctx.arc(sx, sy, 9 * window.devicePixelRatio, 0, Math.PI * 2);
            ctx.fillStyle = color + "33";
            ctx.fill();

            // Core
            ctx.beginPath();
            ctx.arc(sx, sy, 4.5 * window.devicePixelRatio, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.shadowColor = color;
            ctx.shadowBlur = 8 * window.devicePixelRatio;
            ctx.fill();
            ctx.shadowBlur = 0;

            // Label
            ctx.fillStyle = "#f8fafc";
            ctx.font = `bold ${10 * window.devicePixelRatio}px Inter`;
            ctx.fillText(`AMV-${a.amv_id}`, sx + 8 * window.devicePixelRatio, sy - 6 * window.devicePixelRatio);
        });
    }

    function drawCanvasDepth(amvs) {
        const canvas = $("#canvasDepth");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const w = canvas.width;
        const h = canvas.height;

        ctx.clearRect(0, 0, w, h);

        const pad = 30 * window.devicePixelRatio;
        const plotW = w - pad * 2;
        const plotH = h - pad * 2;

        function toScreenX(x) { return pad + (x / 1000) * plotW; }
        function toScreenZ(z) { return pad + (z / 200) * plotH; }

        // Surface (z=0)
        ctx.strokeStyle = "rgba(56, 189, 248, 0.6)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(pad, pad);
        ctx.lineTo(w - pad, pad);
        ctx.stroke();

        ctx.fillStyle = "#38bdf8";
        ctx.font = `${8 * window.devicePixelRatio}px JetBrains Mono`;
        ctx.fillText("SURFACE (0m)", pad + 6, pad - 6);

        // Seabed (z=200m)
        ctx.strokeStyle = "rgba(100, 116, 139, 0.4)";
        ctx.beginPath();
        ctx.moveTo(pad, h - pad);
        ctx.lineTo(w - pad, h - pad);
        ctx.stroke();
        ctx.fillText("BATHYMETRY (200m)", pad + 6, h - pad + 14);

        // Thermocline boundary (z=100m)
        const thermY = toScreenZ(100);
        ctx.strokeStyle = "rgba(245, 158, 11, 0.5)";
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(pad, thermY);
        ctx.lineTo(w - pad, thermY);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = "#f59e0b";
        ctx.fillText("THERMOCLINE LAYER (100m) -35% SIG", w - pad - 180, thermY - 5);

        // Vehicles on Depth Profile
        amvs.forEach(a => {
            const sx = toScreenX(a.position[0]);
            const sz = toScreenZ(a.position[2]);
            const color = AMV_COLORS[a.amv_id % AMV_COLORS.length];

            ctx.beginPath();
            ctx.arc(sx, sz, 4 * window.devicePixelRatio, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.fill();

            ctx.fillStyle = color;
            ctx.font = `${8 * window.devicePixelRatio}px JetBrains Mono`;
            ctx.fillText(`A${a.amv_id}: -${a.position[2].toFixed(0)}m`, sx + 6, sz + 3);
        });
    }

    function updateInspectorTable(frameIdx) {
        const listEl = $("#inspectorVehicleList");
        if (!listEl || !replayTrajectory || !replayTrajectory[frameIdx]) return;
        const amvs = replayTrajectory[frameIdx].amvs || [];

        listEl.innerHTML = amvs.map(a => {
            const color = AMV_COLORS[a.amv_id % AMV_COLORS.length];
            const fsmClass = getFsmClass(a.fsm_state);
            const pos = a.position || [0, 0, 0];

            return `
                <div class="inspector-row">
                    <div style="display:flex;align-items:center;gap:6px;">
                        <span class="amv-dot" style="background:${color}"></span>
                        <strong>AMV-${a.amv_id}</strong>
                    </div>
                    <span class="fsm-badge ${fsmClass}">${a.fsm_state || "Idle"}</span>
                    <span style="font-family:'JetBrains Mono',monospace;color:var(--text-secondary)">
                        X:${pos[0].toFixed(0)} Y:${pos[1].toFixed(0)} Z:-${pos[2].toFixed(0)}m
                    </span>
                    <span style="font-weight:700;color:${a.energy > 50 ? '#10b981' : '#f59e0b'}">
                        ${a.energy.toFixed(1)}%
                    </span>
                </div>
            `;
        }).join("");
    }

    // ═══════════════════════════════════════════════════════════════════
    // VIEW 4: SIMULATION PLOTS GALLERY
    // ═══════════════════════════════════════════════════════════════════
    function preparePlotGallery(meta) {
        galleryImages = (meta.images || []).map(img => {
            const key = img.replace(/_\d{8}_\d{6}\.\w+$/, "");
            const metaInfo = PLOT_METADATA[key] || { name: key.replace(/^plot_/, "").replace(/_/g, " "), category: "Mission" };
            return {
                src: `${ARCHIVE_BASE}/${img}`,
                filename: img,
                key: key,
                name: metaInfo.name,
                category: metaInfo.category,
                ts: meta.timestamp
            };
        });

        renderPlotCategoryPills();
        renderPlotGallery();
    }

    function setupPlotGalleryControls() {
        const searchInput = $("#plotSearchInput");
        if (searchInput) {
            searchInput.addEventListener("input", (e) => {
                plotSearchQuery = e.target.value.toLowerCase().trim();
                renderPlotGallery();
            });
        }

        // Lightbox
        $("#lightboxClose")?.addEventListener("click", closeLightbox);
        $("#lightboxPrev")?.addEventListener("click", () => navigateLightbox(-1));
        $("#lightboxNext")?.addEventListener("click", () => navigateLightbox(1));
        $("#lightbox")?.addEventListener("click", (e) => {
            if (e.target.id === "lightbox") closeLightbox();
        });

        document.addEventListener("keydown", (e) => {
            if (!$("#lightbox")?.classList.contains("active")) return;
            if (e.key === "Escape") closeLightbox();
            if (e.key === "ArrowLeft") navigateLightbox(-1);
            if (e.key === "ArrowRight") navigateLightbox(1);
        });
    }

    function renderPlotCategoryPills() {
        const container = $("#plotCategoryPills");
        if (!container) return;

        container.innerHTML = PLOT_CATEGORIES.map(cat => {
            const isActive = cat === activePlotCategory ? "active" : "";
            return `<button class="pill ${isActive}" onclick="window.__filterPlotCategory('${cat}')">${cat}</button>`;
        }).join("");
    }

    window.__filterPlotCategory = function(cat) {
        activePlotCategory = cat;
        renderPlotCategoryPills();
        renderPlotGallery();
    };

    function renderPlotGallery() {
        const grid = $("#plotGalleryGrid");
        if (!grid) return;

        let filtered = [...galleryImages];
        if (activePlotCategory !== "All") {
            filtered = filtered.filter(p => p.category === activePlotCategory);
        }
        if (plotSearchQuery) {
            filtered = filtered.filter(p => p.name.toLowerCase().includes(plotSearchQuery) || p.key.toLowerCase().includes(plotSearchQuery));
        }

        if (filtered.length === 0) {
            grid.innerHTML = `<div class="empty-state"><p>No figures match the selected filter.</p></div>`;
            return;
        }

        grid.innerHTML = filtered.map((p, idx) => `
            <div class="plot-card" onclick="window.__openLightbox(${idx})">
                <div class="plot-img-container">
                    <img src="${p.src}" alt="${p.name}" loading="lazy">
                </div>
                <div class="plot-card-footer">
                    <span class="plot-name">${p.name}</span>
                    <span class="plot-category-tag">${p.category}</span>
                </div>
            </div>
        `).join("");
    }

    window.__openLightbox = function(idx) {
        const filtered = getFilteredPlots();
        if (!filtered[idx]) return;
        lightboxIndex = idx;
        const item = filtered[idx];

        $("#lightboxImg").src = item.src;
        $("#lightboxCaption").textContent = item.name;
        $("#lightbox").classList.add("active");
    };

    function closeLightbox() {
        $("#lightbox").classList.remove("active");
    }

    function navigateLightbox(dir) {
        const filtered = getFilteredPlots();
        if (filtered.length === 0) return;
        lightboxIndex = (lightboxIndex + dir + filtered.length) % filtered.length;
        const item = filtered[lightboxIndex];
        $("#lightboxImg").src = item.src;
        $("#lightboxCaption").textContent = item.name;
    }

    function getFilteredPlots() {
        let filtered = [...galleryImages];
        if (activePlotCategory !== "All") filtered = filtered.filter(p => p.category === activePlotCategory);
        if (plotSearchQuery) filtered = filtered.filter(p => p.name.toLowerCase().includes(plotSearchQuery));
        return filtered;
    }

    // ═══════════════════════════════════════════════════════════════════
    // VIEW 5: RUN COMPARATOR (SIDE-BY-SIDE DIFF)
    // ═══════════════════════════════════════════════════════════════════
    function setupComparatorControls() {
        $("#compareSelectA")?.addEventListener("change", updateComparatorView);
        $("#compareSelectB")?.addEventListener("change", updateComparatorView);
        $("#syncPlotTypeSelect")?.addEventListener("change", updateComparatorView);
    }

    function updateComparatorDropdowns() {
        const selA = $("#compareSelectA");
        const selB = $("#compareSelectB");
        if (!selA || !selB || !runsIndex) return;

        const optionsHtml = runsIndex.runs.map(r => {
            const d = parseTimestamp(r.timestamp);
            const tcr = (r.task_completion_rate * 100).toFixed(0);
            return `<option value="${r.timestamp}">Run #${r.seed} (${r.scenario || "Nominal"}) - ${tcr}% [${d.dateStr} ${d.timeStr}]</option>`;
        }).join("");

        selA.innerHTML = optionsHtml;
        selB.innerHTML = optionsHtml;

        // Default: Run A = first or second-to-latest, Run B = latest
        if (runsIndex.runs.length >= 2) {
            selA.value = runsIndex.runs[runsIndex.runs.length - 2].timestamp;
            selB.value = runsIndex.runs[runsIndex.runs.length - 1].timestamp;
        }
    }

    async function updateComparatorView() {
        const tsA = $("#compareSelectA")?.value;
        const tsB = $("#compareSelectB")?.value;
        if (!tsA || !tsB) return;

        const metaA = allRunMetas.find(m => m.timestamp === tsA) || await fetchRunMeta(`run_${tsA}.json`);
        const metaB = allRunMetas.find(m => m.timestamp === tsB) || await fetchRunMeta(`run_${tsB}.json`);
        if (!metaA || !metaB) return;

        const dA = parseTimestamp(metaA.timestamp);
        const dB = parseTimestamp(metaB.timestamp);

        $("#compHeaderA").textContent = `Run A (Seed ${metaA.seed}) [${dA.timeStr}]`;
        $("#compHeaderB").textContent = `Run B (Seed ${metaB.seed}) [${dB.timeStr}]`;

        // Render Delta Matrix Rows
        const mA = metaA.metrics;
        const mB = metaB.metrics;

        const rows = [
            compareMetricRow("Task Completion Rate", mA.task_completion_rate * 100, mB.task_completion_rate * 100, "%", true),
            compareMetricRow("Mean Task Delay", mA.mean_task_delay, mB.mean_task_delay, "ts", false),
            compareMetricRow("Total Deadlocks", mA.total_deadlocks, mB.total_deadlocks, "", false),
            compareMetricRow("Congestion Drop Rate", mA.congestion_drop_rate * 100, mB.congestion_drop_rate * 100, "%", false),
            compareMetricRow("Energy Efficiency", mA.energy_efficiency, mB.energy_efficiency, "", true),
            compareMetricRow("AMV Fleet Availability", mA.mean_amv_availability * 100, mB.mean_amv_availability * 100, "%", true),
            compareMetricRow("Connectivity Rate", mA.connectivity_maintenance * 100, mB.connectivity_maintenance * 100, "%", true),
            compareMetricRow("Auction Convergence", mA.auction_convergence_rate, mB.auction_convergence_rate, "iters", false)
        ];

        $("#comparatorTableBody").innerHTML = rows.join("");

        // Side-by-Side Plots Sync
        const plotKey = $("#syncPlotTypeSelect")?.value || "plot_mission_space";
        const imgA = (metaA.images || []).find(i => i.startsWith(plotKey));
        const imgB = (metaB.images || []).find(i => i.startsWith(plotKey));

        $("#syncPlotTitleA").textContent = `Run A: ${metaA.scenario || "Nominal"} (Seed ${metaA.seed})`;
        $("#syncPlotTitleB").textContent = `Run B: ${metaB.scenario || "Nominal"} (Seed ${metaB.seed})`;

        if (imgA) $("#syncPlotImgA").src = `${ARCHIVE_BASE}/${imgA}`;
        if (imgB) $("#syncPlotImgB").src = `${ARCHIVE_BASE}/${imgB}`;
    }

    function compareMetricRow(label, vA, vB, unit, higherIsBetter) {
        const delta = vB - vA;
        const pctDiff = vA !== 0 ? ((delta / Math.abs(vA)) * 100).toFixed(1) : "0.0";
        const isBetter = higherIsBetter ? delta > 0 : delta < 0;
        const isNeutral = Math.abs(delta) < 0.001;

        const deltaClass = isNeutral ? "delta-neutral" : isBetter ? "delta-improved" : "delta-regressed";
        const assessment = isNeutral ? "Identical" : isBetter ? "Improved" : "Regressed";

        return `
            <tr>
                <td><strong>${label}</strong></td>
                <td>${vA.toFixed(2)} ${unit}</td>
                <td>${vB.toFixed(2)} ${unit}</td>
                <td class="${deltaClass}">${delta >= 0 ? '+' : ''}${delta.toFixed(2)} ${unit}</td>
                <td class="${deltaClass}">${delta >= 0 ? '+' : ''}${pctDiff}%</td>
                <td><span class="fsm-badge ${isBetter ? 'fsm-executing' : isNeutral ? 'fsm-idle' : 'fsm-faulted'}">${assessment}</span></td>
            </tr>
        `;
    }

    // ═══════════════════════════════════════════════════════════════════
    // VIEW 6: BENCHMARK & RESEARCH ANALYTICS SUITE
    // ═══════════════════════════════════════════════════════════════════
    function setupBenchmarkControls() {
        $("#benchmarkDatasetSelect")?.addEventListener("change", (e) => {
            activeBenchmarkDataset = e.target.value;
            loadBenchmarkData();
        });

        $("#benchmarkTableFilter")?.addEventListener("input", (e) => {
            filterBenchmarkTable(e.target.value.toLowerCase().trim());
        });

        $("#btnExportCsv")?.addEventListener("click", exportBenchmarkCsv);
    }

    async function loadBenchmarkData() {
        const fileMap = {
            three_way: "three_way_comparison_results.csv",
            cbba_final: "cbba_comparison_final_verified.csv",
            cbba_postfix: "cbba_comparison_postfix_results.csv",
            recovery_opt: "recovery_optimization_results.csv"
        };

        const targetUrl = fileMap[activeBenchmarkDataset] || fileMap.three_way;
        try {
            const resp = await fetch(`${targetUrl}?t=${Date.now()}`);
            if (!resp.ok) return;
            const text = await resp.text();
            parseBenchmarkCsv(text);
        } catch { /* csv error */ }
    }

    function parseBenchmarkCsv(csvText) {
        const lines = csvText.trim().split("\n");
        if (lines.length < 2) return;

        const headers = lines[0].split(",").map(h => h.trim());
        rawBenchmarkRows = [];

        for (let i = 1; i < lines.length; i++) {
            const vals = lines[i].split(",").map(v => v.trim());
            if (vals.length !== headers.length) continue;
            const obj = {};
            headers.forEach((h, idx) => {
                const num = parseFloat(vals[idx]);
                obj[h] = isNaN(num) ? vals[idx] : num;
            });
            rawBenchmarkRows.push(obj);
        }

        filteredBenchmarkRows = [...rawBenchmarkRows];
        renderBenchmarkSummaryKPIs();
        renderBenchmarkCharts();
        renderBenchmarkTable(headers);
    }

    function renderBenchmarkSummaryKPIs() {
        const grid = $("#benchmarkKpiGrid");
        if (!grid || rawBenchmarkRows.length === 0) return;

        const totalRuns = rawBenchmarkRows.length;
        const avgComp = (rawBenchmarkRows.reduce((a, b) => a + (b.task_completion_rate || 0), 0) / totalRuns * 100).toFixed(1);
        const avgDelay = (rawBenchmarkRows.reduce((a, b) => a + (b.mean_task_delay || 0), 0) / totalRuns).toFixed(1);
        const neverComp = rawBenchmarkRows.reduce((a, b) => a + (b.never_completed_tasks || 0), 0);

        grid.innerHTML = `
            <div class="kpi-card" style="--kpi-grad:var(--grad-primary)">
                <div class="kpi-header"><span class="kpi-title">Total Benchmark Sweeps</span></div>
                <div class="kpi-value-row"><span class="kpi-value">${totalRuns}</span><span class="kpi-unit">Runs</span></div>
                <div class="kpi-sub">Across diverse Monte Carlo seeds</div>
            </div>
            <div class="kpi-card" style="--kpi-grad:var(--grad-emerald)">
                <div class="kpi-header"><span class="kpi-title">Mean Task Completion</span></div>
                <div class="kpi-value-row"><span class="kpi-value">${avgComp}</span><span class="kpi-unit">%</span></div>
                <div class="kpi-sub">Overall aggregate benchmark rate</div>
            </div>
            <div class="kpi-card" style="--kpi-grad:var(--grad-indigo)">
                <div class="kpi-header"><span class="kpi-title">Average Task Delay</span></div>
                <div class="kpi-value-row"><span class="kpi-value">${avgDelay}</span><span class="kpi-unit">ts</span></div>
                <div class="kpi-sub">Mean allocation turnaround latency</div>
            </div>
            <div class="kpi-card" style="--kpi-grad:var(--grad-amber)">
                <div class="kpi-header"><span class="kpi-title">Never-Completed Total</span></div>
                <div class="kpi-value-row"><span class="kpi-value">${neverComp}</span><span class="kpi-unit">Tasks</span></div>
                <div class="kpi-sub">Unreachable task instances</div>
            </div>
        `;
    }

    function renderBenchmarkCharts() {
        if (rawBenchmarkRows.length === 0) return;

        // Group by scenario & allocator
        const scenarios = ["none", "amv_loss", "blackout", "byzantine"];
        const allocators = ["auction", "cbba", "baseline"];

        // 1. Completion Rate by Scenario
        const chartCompCanvas = document.getElementById("chartBenchmarkCompletion");
        if (chartCompCanvas) {
            if (benchmarkCharts.comp) benchmarkCharts.comp.destroy();

            const datasets = allocators.map((alloc, idx) => {
                const data = scenarios.map(sc => {
                    const matched = rawBenchmarkRows.filter(r => (r.scenario === sc || (sc === "none" && r.scenario === "nominal")) && (r.allocator === alloc || !r.allocator));
                    if (matched.length === 0) return 0;
                    return (matched.reduce((a, b) => a + (b.task_completion_rate || 0), 0) / matched.length * 100).toFixed(1);
                });

                return {
                    label: alloc.toUpperCase(),
                    data,
                    backgroundColor: AMV_COLORS[idx],
                    borderRadius: 4
                };
            });

            benchmarkCharts.comp = new Chart(chartCompCanvas, {
                type: "bar",
                data: {
                    labels: ["Nominal", "AMV Loss", "Blackout", "Byzantine"],
                    datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: "#94a3b8" } } },
                    scales: {
                        x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" } },
                        y: {
                            ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" },
                            min: 0, max: 100,
                            title: { display: true, text: "Completion Rate (%)", color: "#94a3b8" }
                        }
                    }
                }
            });
        }

        // 2. Mean Task Delay
        const chartDelayCanvas = document.getElementById("chartBenchmarkDelay");
        if (chartDelayCanvas) {
            if (benchmarkCharts.delay) benchmarkCharts.delay.destroy();

            const dataDelays = scenarios.map(sc => {
                const matched = rawBenchmarkRows.filter(r => (r.scenario === sc || (sc === "none" && r.scenario === "nominal")));
                if (matched.length === 0) return 0;
                return (matched.reduce((a, b) => a + (b.mean_task_delay || 0), 0) / matched.length).toFixed(1);
            });

            benchmarkCharts.delay = new Chart(chartDelayCanvas, {
                type: "line",
                data: {
                    labels: ["Nominal", "AMV Loss", "Blackout", "Byzantine"],
                    datasets: [{
                        label: "Mean Delay (Timesteps)",
                        data: dataDelays,
                        borderColor: "#818cf8",
                        backgroundColor: "rgba(129, 140, 248, 0.15)",
                        fill: true,
                        tension: 0.35,
                        pointRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: "#94a3b8" } } },
                    scales: {
                        x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" } },
                        y: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" } }
                    }
                }
            });
        }

        // 3. Congestion Drop Rate
        const chartCongCanvas = document.getElementById("chartBenchmarkCongestion");
        if (chartCongCanvas) {
            if (benchmarkCharts.cong) benchmarkCharts.cong.destroy();

            const dataCong = scenarios.map(sc => {
                const matched = rawBenchmarkRows.filter(r => (r.scenario === sc || (sc === "none" && r.scenario === "nominal")));
                if (matched.length === 0) return 0;
                return (matched.reduce((a, b) => a + (b.congestion_drop_rate || 0), 0) / matched.length * 100).toFixed(2);
            });

            benchmarkCharts.cong = new Chart(chartCongCanvas, {
                type: "bar",
                data: {
                    labels: ["Nominal", "AMV Loss", "Blackout", "Byzantine"],
                    datasets: [{
                        label: "Packet Drop (%)",
                        data: dataCong,
                        backgroundColor: "#10b981",
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: "#94a3b8" } } },
                    scales: {
                        x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" } },
                        y: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" } }
                    }
                }
            });
        }

        // 4. Never Completed Tasks Distribution
        const chartNeverCanvas = document.getElementById("chartBenchmarkNeverCompleted");
        if (chartNeverCanvas) {
            if (benchmarkCharts.never) benchmarkCharts.never.destroy();

            const dataNever = scenarios.map(sc => {
                const matched = rawBenchmarkRows.filter(r => (r.scenario === sc || (sc === "none" && r.scenario === "nominal")));
                return matched.reduce((a, b) => a + (b.never_completed_tasks || 0), 0);
            });

            benchmarkCharts.never = new Chart(chartNeverCanvas, {
                type: "bar",
                data: {
                    labels: ["Nominal", "AMV Loss", "Blackout", "Byzantine"],
                    datasets: [{
                        label: "Unfulfilled Tasks",
                        data: dataNever,
                        backgroundColor: "#f43f5e",
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: "#94a3b8" } } },
                    scales: {
                        x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" } },
                        y: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" } }
                    }
                }
            });
        }
    }

    function renderBenchmarkTable(headers) {
        const thead = $("#benchmarkTableHead");
        const tbody = $("#benchmarkTableBody");
        const subtitle = $("#benchmarkTableSubtitle");
        if (!thead || !tbody) return;

        if (subtitle) subtitle.textContent = `Showing ${filteredBenchmarkRows.length} of ${rawBenchmarkRows.length} sweep entries`;

        thead.innerHTML = `<tr>${headers.map(h => `<th>${h.replace(/_/g, " ")}</th>`).join("")}</tr>`;

        tbody.innerHTML = filteredBenchmarkRows.slice(0, 100).map(row => `
            <tr>
                ${headers.map(h => {
                    const val = row[h];
                    const num = typeof val === "number" ? (val < 1 && val > 0 ? val.toFixed(4) : val.toFixed(1)) : val;
                    return `<td>${num}</td>`;
                }).join("")}
            </tr>
        `).join("");
    }

    function filterBenchmarkTable(query) {
        if (!query) {
            filteredBenchmarkRows = [...rawBenchmarkRows];
        } else {
            filteredBenchmarkRows = rawBenchmarkRows.filter(row => {
                return Object.values(row).some(val => String(val).toLowerCase().includes(query));
            });
        }
        if (rawBenchmarkRows.length > 0) {
            renderBenchmarkTable(Object.keys(rawBenchmarkRows[0]));
        }
    }

    function exportBenchmarkCsv() {
        if (rawBenchmarkRows.length === 0) return;
        const headers = Object.keys(rawBenchmarkRows[0]);
        const csvContent = [
            headers.join(","),
            ...rawBenchmarkRows.map(r => headers.map(h => r[h]).join(","))
        ].join("\n");

        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `benchmark_${activeBenchmarkDataset}_export.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }

    // ═══════════════════════════════════════════════════════════════════
    // AUTO-REFRESH POLLING
    // ═══════════════════════════════════════════════════════════════════
    function startPolling() {
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = setInterval(async () => {
            const toggle = $("#autoRefreshToggle");
            if (toggle && !toggle.checked) return;

            const newIndex = await fetchRunsIndex();
            if (!newIndex) return;

            const oldCount = runsIndex ? runsIndex.runs.length : 0;
            if (newIndex.runs.length > oldCount) {
                runsIndex = newIndex;
                await refreshRunsData();
                const latest = newIndex.runs[newIndex.runs.length - 1];
                await selectRun(latest.timestamp);
            }
        }, POLL_INTERVAL);
    }

    // Run init on DOM ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
