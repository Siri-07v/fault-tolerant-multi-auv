"""
visualize.py — 12 plots for the Miele et al. upgraded AUV swarm simulation.
"""
import numpy as np
import matplotlib
if not getattr(__import__('config'), 'LIVE_VIZ_ENABLED', False):
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import matplotlib.ticker
import networkx as nx
from mpl_toolkits.mplot3d import Axes3D

import config

# ─── Global style ────────────────────────────────────────────────────────────────
plt.style.use('seaborn-v0_8-whitegrid')
mpl.rcParams.update({
    'figure.dpi': 150,
    'font.family': 'DejaVu Sans',
    'font.size': 11,
    'axes.titlesize': 14,
    'axes.titleweight': 'bold',
    'axes.labelsize': 12,
    'axes.labelweight': 'bold',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 9,
    'legend.framealpha': 0.85,
    'legend.edgecolor': '#cccccc',
    'lines.linewidth': 2.0,
    'grid.alpha': 0.4,
    'grid.linestyle': '--',
})

# Consistent AMV color palette — vivid, distinct
AMV_COLORS = ['#2196F3', '#FF9800', '#4CAF50', '#F44336', '#9C27B0']
# Blue, Orange, Green, Red, Purple

# Consistent fault state color palette
FAULT_COLORS = {
    'normal': '#4CAF50',
    'load_fault': '#FF9800',
    'sensor_failure': '#F44336',
    'actuator_degraded_severe': '#9C27B0',
    'actuator_degraded_mild': '#2196F3',
}


# ─── Plot 1: Before / After Mission Space ───────────────────────────────────────

def plot_mission_space(amvs, tasks, initial_positions, reallocation_log,
                       initial_graph, trajectory_log=None,
                       filename="plot_mission_space.png"):
    """Two side-by-side subplots: initial state and final state."""
    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(20, 9))
    fig.suptitle('AMV Swarm Mission Space', fontsize=16, fontweight='bold', y=1.01)

    # ── LEFT: Before (Timestep 0) ───────────────────────────────────────────
    ax = ax_left
    ax.set_facecolor('#f0f4f8')
    ax.set_title("Before: Initial State (Timestep 0)", fontsize=13, fontweight="bold")

    # Subplot borders
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color('#cccccc')

    # Comm graph edges
    if initial_graph is not None:
        pos = nx.get_node_attributes(initial_graph, "pos")
        for u, v in initial_graph.edges():
            if u in pos and v in pos:
                ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                        color='#90CAF9', linestyle='--', linewidth=1.2, alpha=0.5)

    # Tasks — gray squares
    for task in tasks:
        if task.is_dummy:
            continue
        ax.scatter(*task.position, c="gray", marker="s", s=180, zorder=5,
                   edgecolors="black", linewidths=1.5)
        ax.annotate(f"T{task.task_id}", task.position, fontsize=8,
                    textcoords="offset points", xytext=(6, 6))

    # AMV starting positions
    for amv in amvs:
        c = AMV_COLORS[amv.amv_id % len(AMV_COLORS)]
        ipos = initial_positions[amv.amv_id]
        ax.scatter(ipos[0], ipos[1], c=c, marker="^", s=250, zorder=6,
                   edgecolors="black", linewidths=2)
        ax.annotate(f"AMV{amv.amv_id}", (ipos[0], ipos[1]), fontsize=9,
                    fontweight="bold", textcoords="offset points", xytext=(6, -12))

    # Legend
    handles_l = [
        mpatches.Patch(color="gray", label="Task"),
        plt.Line2D([], [], color='#90CAF9', linestyle='--', label="Comm Link"),
    ]
    for amv in amvs:
        handles_l.append(plt.Line2D([], [], marker="^", color="w",
                         markerfacecolor=AMV_COLORS[amv.amv_id % len(AMV_COLORS)],
                         markersize=10, label=f"AMV {amv.amv_id}"))
    ax.legend(handles=handles_l, loc="upper right", fontsize=7)
    ax.set_xlim(0, 1000); ax.set_ylim(0, 1000)
    ax.set_xlabel('X Position (m)'); ax.set_ylabel('Y Position (m)')
    ax.set_aspect("equal"); ax.grid(True, alpha=0.3)

    # ── RIGHT: After (Final State) ──────────────────────────────────────────
    ax = ax_right
    ax.set_facecolor('#f0f4f8')
    ax.set_title(f"After: Final State (Timestep {config.SIMULATION_TIMESTEPS})",
                 fontsize=13, fontweight="bold")

    # Subplot borders
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color('#cccccc')

    # Draw actual trajectory paths first (behind everything, zorder=1)
    if trajectory_log is not None:
        for amv_id in sorted(trajectory_log.keys()):
            pts = trajectory_log[amv_id]
            if len(pts) < 2:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            c = AMV_COLORS[amv_id % len(AMV_COLORS)]
            ax.plot(xs, ys, color=c, alpha=0.5, linewidth=1.8, zorder=1)

    # Reallocation markers
    realloc_ts_by_amv = {}
    for evt in reallocation_log:
        realloc_ts_by_amv.setdefault(evt["amv_id"], []).append(evt["timestep"])

    for amv in amvs:
        c = AMV_COLORS[amv.amv_id % len(AMV_COLORS)]

        # Reallocation markers on trajectory_log path (spaced ≥20 timesteps)
        last_marker_t = -999
        for rs in sorted(realloc_ts_by_amv.get(amv.amv_id, [])):
            if rs - last_marker_t < 20:
                continue
            if trajectory_log is not None and amv.amv_id in trajectory_log:
                traj_pts = trajectory_log[amv.amv_id]
                idx = min(rs, len(traj_pts) - 1)
                ax.scatter(traj_pts[idx][0], traj_pts[idx][1], marker="X",
                           c="orange", s=90, zorder=7, edgecolors="black",
                           linewidths=0.5)
                last_marker_t = rs

        # AMV final position
        ax.scatter(amv.position[0], amv.position[1], c=c, marker="^", s=250,
                   zorder=6, edgecolors="black", linewidths=2)
        ax.annotate(f"AMV{amv.amv_id}", amv.position, fontsize=9,
                    fontweight="bold", textcoords="offset points", xytext=(6, -12))

    # Tasks coloured by status
    for task in tasks:
        if task.is_dummy:
            continue
        color = '#4CAF50' if task.status == "completed" else '#F44336'
        ax.scatter(*task.position, c=color, marker="s", s=180, zorder=5,
                   edgecolors="black", linewidths=1.5)
        label_txt = f"T{task.task_id}"
        if task.status == "completed" and task.assigned_to is not None:
            label_txt += f"→AMV{task.assigned_to}"
        ax.annotate(label_txt, task.position, fontsize=7, fontweight='bold',
                    textcoords="offset points", xytext=(6, 6),
                    arrowprops=dict(arrowstyle='->', color='#555555', lw=0.8) if (task.status == "completed" and task.assigned_to is not None) else None)

    handles_r = [
        mpatches.Patch(color='#4CAF50', label="Completed Task"),
        mpatches.Patch(color='#F44336', label="Uncompleted Task"),
        plt.Line2D([], [], marker="X", color="w", markerfacecolor="orange",
                   markersize=10, label="Reallocation Event"),
    ]
    ax.legend(handles=handles_r, loc="upper right", fontsize=7)
    ax.set_xlim(0, 1000); ax.set_ylim(0, 1000)
    ax.set_xlabel('X Position (m)'); ax.set_ylabel('Y Position (m)')
    ax.set_aspect("equal"); ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {filename}")


# ─── Plot 2: Task Coverage Rate ─────────────────────────────────────────────────

def plot_task_coverage(log_df, reallocation_log, deadlock_log, completion_log,
                       filename="plot_task_coverage.png"):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_facecolor('#fafafa')

    coverage = log_df["tasks_completed"] / config.N_TASKS
    timesteps = log_df["timestep"]

    ax.plot(timesteps, coverage, color='#1565C0', linewidth=2.5)
    ax.fill_between(timesteps, coverage, alpha=0.15, color='#1565C0')

    # 100% reference line
    ax.axhline(y=1.0, color='gray', linestyle=':', linewidth=1, alpha=0.6,
               label='100% Coverage')

    # Deadlock vertical lines — red
    deadlock_label_drawn = False
    for evt in deadlock_log:
        ts = evt["timestep"]
        label = "Deadlock Event" if not deadlock_label_drawn else None
        ax.axvline(x=ts, color='#E53935', linestyle="--", linewidth=1.5,
                   alpha=0.7, label=label, zorder=3)
        if not deadlock_label_drawn:
            ax.text(ts + 1, 0.95, "Deadlock", color='#E53935', fontsize=7,
                    rotation=90, va="top")
            deadlock_label_drawn = True

    # Completion vertical lines — green
    completion_label_drawn = False
    for evt in completion_log:
        ts = evt["timestep"]
        label = "Completion Event" if not completion_label_drawn else None
        ax.axvline(x=ts, color='#43A047', linestyle="--", linewidth=1.5,
                   alpha=0.7, label=label, zorder=3)
        if not completion_label_drawn:
            ax.text(ts + 1, 0.05, "Complete", color='#43A047', fontsize=7,
                    rotation=90, va="bottom")
            completion_label_drawn = True

    ax.legend(loc="best", fontsize=8)

    ax.set_xlabel("Timestep")
    ax.set_ylabel("Task Coverage (completed / total)")
    ax.set_title("Task Coverage Rate Over Time")
    ax.set_ylim(0, 1.05)
    ax.yaxis.set_major_formatter(mpl.ticker.PercentFormatter(xmax=1.0))
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(filename, dpi=150)
    plt.close(fig)
    print(f"Saved {filename}")


# ─── Plot 3: Per-AMV Availability ────────────────────────────────────────────────

def plot_availability(availability_log, fault_log, filename="plot_availability.png"):
    fig, ax = plt.subplots(figsize=(10, 5))

    # Danger zone
    ax.axhspan(0, 0.15, alpha=0.08, color='red', label='Below Threshold')
    ax.axhline(0.15, color='red', linestyle=':', linewidth=1.2, alpha=0.7,
               label='Availability Threshold')

    n_amvs = len(availability_log)
    last_label_t = {i: -999 for i in range(n_amvs)}

    for amv_id in sorted(availability_log.keys()):
        records = availability_log[amv_id]
        ts = [r[0] for r in records]
        av = [r[1] for r in records]
        c = AMV_COLORS[amv_id % len(AMV_COLORS)]
        ax.plot(ts, av, label=f"AMV {amv_id}", color=c, linewidth=2.2)

        # Fault transition markers — diamond (filtered for clutter)
        faults = fault_log.get(amv_id, [])
        prev_state = None
        prev_avail = av[0] if av else 1.0
        for i, (ft, fstate) in enumerate(faults):
            if fstate != prev_state and prev_state is not None:
                idx = min(i, len(av) - 1)
                new_avail = av[idx]
                # Only label significant transitions with spacing
                if abs(new_avail - prev_avail) > 0.15 and (ft - last_label_t[amv_id]) > 15:
                    y_offset = 0.03 * (amv_id % 3)
                    ax.scatter(ft, av[idx], c=c, s=49, zorder=5, marker='D',
                               edgecolors='black', linewidths=0.8)
                    short_label = fstate.replace("actuator_degraded_", "act_")
                    ax.annotate(f"→{short_label}", (ft, av[idx] + y_offset),
                                fontsize=7, color=c, textcoords="offset points",
                                xytext=(3, 5), rotation=35)
                    last_label_t[amv_id] = ft
                prev_avail = new_avail
            prev_state = fstate

    ax.set_xlabel("Timestep")
    ax.set_ylabel("Availability Score")
    ax.set_title("Per-AMV Availability Over Time")
    ax.legend(loc="best", fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(filename, dpi=150)
    plt.close(fig)
    print(f"Saved {filename}")


# ─── Plot 4: Fault State Gantt Chart ────────────────────────────────────────────

def plot_fault_gantt(fault_log, filename="plot_fault_gantt.png"):
    fig, ax = plt.subplots(figsize=(12, 4))
    all_states = list(FAULT_COLORS.keys())
    amv_ids = sorted(fault_log.keys())

    # Alternating row shading
    for row_idx, amv_id in enumerate(amv_ids):
        if row_idx % 2 == 0:
            ax.axhspan(row_idx - 0.4, row_idx + 0.4, color='#f5f5f5', zorder=0)

    for row_idx, amv_id in enumerate(amv_ids):
        records = fault_log[amv_id]
        if not records:
            continue
        segments = []
        current_state = records[0][1]
        seg_start = records[0][0]
        for ts, state in records[1:]:
            if state != current_state:
                segments.append((seg_start, ts, current_state))
                current_state = state
                seg_start = ts
        segments.append((seg_start, records[-1][0] + 1, current_state))

        for start, end, state in segments:
            color = FAULT_COLORS.get(state, "#95a5a6")
            ax.barh(row_idx, end - start, left=start, height=0.55,
                    color=color, edgecolor="white", linewidth=0.5)

    ax.set_yticks(range(len(amv_ids)))
    ax.set_yticklabels([f"AMV {i}" for i in amv_ids])
    ax.set_xlabel("Timestep")
    ax.set_ylabel("AMV")
    ax.set_title("Fault State Gantt Chart")

    # Vertical gridlines every 50 timesteps
    ax.xaxis.set_major_locator(mpl.ticker.MultipleLocator(50))
    ax.grid(axis='x', alpha=0.4)

    patches = [mpatches.Patch(color=FAULT_COLORS[s], label=s) for s in all_states]
    ax.legend(handles=patches, loc='upper left', bbox_to_anchor=(1.01, 1),
              borderaxespad=0, fontsize=8)
    fig.tight_layout()
    fig.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {filename}")


# ─── Plot 5: Communication Graph Snapshots ──────────────────────────────────────

def plot_comm_graph_snapshots(graph_snapshots, energy_snapshots=None,
                              filename="plot_comm_graph.png"):
    """Edge thickness by link quality, node size by energy, consistent AMV colors."""
    snapshot_labels = sorted(graph_snapshots.keys())
    n = len(snapshot_labels)
    fig, axes = plt.subplots(1, n, figsize=(6 * n, 6))
    fig.suptitle('Communication Graph Evolution', fontsize=14, fontweight='bold')
    if n == 1:
        axes = [axes]

    for ax, label in zip(axes, snapshot_labels):
        G = graph_snapshots[label]
        pos = nx.get_node_attributes(G, "pos")
        if not pos:
            ax.set_title(f"Timestep {label}\n(no nodes)")
            ax.set_xlim(0, 1000); ax.set_ylim(0, 1000); ax.set_aspect("equal")
            ax.set_xlabel('X Position (m)', fontsize=10)
            ax.set_ylabel('Y Position (m)', fontsize=10)
            continue

        # Count active edges for subtitle
        n_edges = G.number_of_edges()

        # Node sizes by energy
        node_order = sorted(G.nodes())
        node_sizes = []
        node_colors = []
        for nid in node_order:
            en = 80.0  # default
            if energy_snapshots and label in energy_snapshots:
                en = energy_snapshots[label].get(nid, 80.0)
            node_sizes.append(max(200, en * 8))
            node_colors.append(AMV_COLORS[nid % len(AMV_COLORS)])

        # Draw edges with thickness and color based on link quality
        for u, v, data in G.edges(data=True):
            plp = data.get("packet_loss_prob", 0.5)
            quality = 1.0 - plp
            lw = max(0.5, quality * 4)
            edge_color = plt.cm.Blues(0.4 + 0.6 * (1 - plp))
            pu, pv = pos[u], pos[v]
            ax.plot([pu[0], pv[0]], [pu[1], pv[1]], color=edge_color,
                    linewidth=lw, alpha=0.6)
            # Label
            mx, my = (pu[0] + pv[0]) / 2, (pu[1] + pv[1]) / 2
            ax.text(mx, my, f"{plp*100:.1f}%", fontsize=6, ha="center",
                    color='#555555', alpha=0.8)

        # Draw nodes
        for i, nid in enumerate(node_order):
            p = pos[nid]
            ax.scatter(p[0], p[1], c=node_colors[i], s=node_sizes[i],
                       zorder=5, edgecolors="black", linewidths=0.8)
            ax.annotate(f"AMV{nid}", p, fontsize=9, fontweight="bold",
                        textcoords="offset points", xytext=(0, 10),
                        verticalalignment='bottom')

        ax.set_facecolor('#f8f9fa')
        for spine in ax.spines.values():
            spine.set_visible(True)

        # Axis labels, ticks, limits
        ax.set_xlabel('X Position (m)', fontsize=10)
        ax.set_ylabel('Y Position (m)', fontsize=10)
        ax.set_xticks([0, 200, 400, 600, 800, 1000])
        ax.set_yticks([0, 200, 400, 600, 800, 1000])
        ax.set_xlim(0, 1000)
        ax.set_ylim(0, 1000)
        ax.set_title(f'Timestep {label}\n{n_edges} active links', fontsize=10)
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.2)

    fig.tight_layout()
    fig.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {filename}")


# ─── Plot 6: Energy Depletion ───────────────────────────────────────────────────

def plot_energy(energy_log, reallocation_log_by_amv, fsm_deadlock_events=None,
                filename="plot_energy.png"):
    """
    Fix A: reallocation_log_by_amv is {amv_id: [timestep, ...]} (per-AMV dict).
    Fix B: fsm_deadlock_events is {amv_id: [timestep, ...]}.
    """
    fig, ax = plt.subplots(figsize=(10, 5))

    # Danger zone
    ax.axhspan(0, 15, alpha=0.08, color='red')
    ax.axhline(15, color='red', linestyle=':', linewidth=1.2, alpha=0.7,
               label='Critical Energy')

    for amv_id in sorted(energy_log.keys()):
        records = energy_log[amv_id]
        ts = [r[0] for r in records]
        en = [r[1] for r in records]
        c = AMV_COLORS[amv_id % len(AMV_COLORS)]
        ax.plot(ts, en, label=f"AMV {amv_id}", color=c, linewidth=2.2)

        # Reallocation markers from per-AMV dict (spaced ≥20 timesteps)
        last_marker_t = -999
        for rts in sorted(reallocation_log_by_amv.get(amv_id, [])):
            if rts - last_marker_t < 20:
                continue  # skip — too close to previous marker
            idx = min(range(len(ts)), key=lambda i: abs(ts[i] - rts))
            ax.plot(rts, en[idx], marker="x", color='#E53935', markersize=11,
                    markeredgewidth=2.5, zorder=6)
            last_marker_t = rts

        # FSM deadlock entry annotations with rounded box
        if fsm_deadlock_events and amv_id in fsm_deadlock_events:
            for dl_ts in fsm_deadlock_events[amv_id]:
                idx = min(range(len(ts)), key=lambda i: abs(ts[i] - dl_ts))
                ax.annotate(
                    "→DL",
                    xy=(dl_ts, en[idx]),
                    xytext=(dl_ts + 3, en[idx] + 1.5),
                    fontsize=6,
                    color="darkred",
                    ha="left",
                    va="bottom",
                    arrowprops=dict(arrowstyle="->", color="darkred", lw=0.8),
                    bbox=dict(boxstyle='round,pad=0.2', fc='#FFEBEE',
                              ec='darkred', alpha=0.8),
                )

    ax.set_xlabel("Timestep")
    ax.set_ylabel("Energy (%)")
    ax.set_title("Energy Depletion Per AMV")
    ax.set_ylim(0, 105)
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(filename, dpi=150)
    plt.close(fig)
    print(f"Saved {filename}")


# ─── Plot 7: Total Benefit Evolution ────────────────────────────────────────────

def plot_total_benefit(benefit_snapshot_log, deadlock_log, completion_log,
                       filename="plot_total_benefit.png"):
    """
    benefit_snapshot_log: list of (timestep, benefit_value) — held constant
    between auction rounds (step function, no smooth decay).
    """
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_facecolor('#fafafa')

    ts = [r[0] for r in benefit_snapshot_log]
    vals = [r[1] for r in benefit_snapshot_log]
    ax.step(ts, vals, where="post", color='#1A237E', linewidth=2.5)
    ax.fill_between(ts, vals, step='post', alpha=0.12, color='#1A237E')

    # Deadlock lines — red
    deadlock_label_drawn = False
    for evt in deadlock_log:
        t_dl = evt["timestep"]
        label = "Deadlock Event" if not deadlock_label_drawn else None
        ax.axvline(x=t_dl, color='#E53935', linestyle="--", linewidth=1.5,
                   alpha=0.7, label=label, zorder=3)
        if not deadlock_label_drawn:
            y_top = max(vals) * 0.95 if vals else 1.0
            ax.text(t_dl + 1, y_top, "Deadlock", color='#E53935', fontsize=6,
                    rotation=90, va="top")
            deadlock_label_drawn = True

    # Completion lines — green
    completion_label_drawn = False
    for evt in completion_log:
        t_cl = evt["timestep"]
        label = "Completion Event" if not completion_label_drawn else None
        ax.axvline(x=t_cl, color='#43A047', linestyle="--", linewidth=1.5,
                   alpha=0.7, label=label, zorder=3)
        if not completion_label_drawn:
            y_bot = min(vals) + 0.05 if vals else 0.0
            ax.text(t_cl + 1, y_bot, "Complete", color='#43A047', fontsize=6,
                    rotation=90, va="bottom")
            completion_label_drawn = True

    ax.legend(loc="best", fontsize=8)

    ax.set_xlabel("Timestep")
    ax.set_ylabel("Total Benefit Σβᵢⱼ")
    ax.set_title("Evolution of Total Benefit Over Time")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(filename, dpi=150)
    plt.close(fig)
    print(f"Saved {filename}")


# ─── Plot 8: Per-AMV Proposal and EDMC Consensus ───────────────────────────────

def plot_edmc_proposals(proposal_log, mt_log, deadlock_log, completion_log,
                        filename="plot_edmc_proposals.png"):
    """
    Two stacked subplots:
      Top: per-AMV m_p_i proposal over time
      Bottom: global max proposal and mt
    """
    fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    fig.subplots_adjust(hspace=0.08)

    # Gather AMV ids
    amv_ids = sorted(proposal_log.keys())

    # Shaded band at y=-1 for "inactive" value
    ax_top.axhspan(-1.4, -0.6, alpha=0.06, color='gray')

    # Top: per-AMV proposal lines
    for amv_id in amv_ids:
        records = proposal_log[amv_id]
        ts = [r[0] for r in records]
        vals = [r[1] for r in records]
        c = AMV_COLORS[amv_id % len(AMV_COLORS)]
        ax_top.step(ts, vals, where="post", label=f"AMV {amv_id}", color=c,
                    linewidth=2, drawstyle='steps-post')

    ax_top.set_ylabel("mᵢᵖ (proposal)")
    ax_top.set_title("AMV Proposals and Global Deadlock Consensus", fontsize=12)
    ax_top.legend(loc="upper right", fontsize=7)
    ax_top.yaxis.set_major_locator(mpl.ticker.MaxNLocator(integer=True))
    ax_top.grid(True, alpha=0.3)

    # Bottom: global max proposal and mt
    if mt_log:
        mt_ts = [r[0] for r in mt_log]
        mt_vals = [r[1] for r in mt_log]
        ax_bot.step(mt_ts, mt_vals, where="post", color='#1565C0', linewidth=2.5,
                    label="mt")

    # Compute global max proposal at each timestep
    all_ts = sorted(set(t for aid in amv_ids
                        for t, _ in proposal_log[aid]))
    max_proposals = []
    for t in all_ts:
        max_p = -999
        for aid in amv_ids:
            for pt, pv in proposal_log[aid]:
                if pt == t:
                    max_p = max(max_p, pv)
        max_proposals.append(max_p)
    ax_bot.step(all_ts, max_proposals, where="post", color='#E91E63',
                linewidth=2, linestyle="-.", label="max(m_p)")

    # Deadlock and completion lines on both
    for evt in deadlock_log:
        ax_top.axvline(x=evt["timestep"], color='#E53935', linestyle="--",
                       alpha=0.7, linewidth=1.2)
        ax_bot.axvline(x=evt["timestep"], color='#E53935', linestyle="--",
                       alpha=0.7, linewidth=1.2)
    for evt in completion_log:
        ax_top.axvline(x=evt["timestep"], color='#43A047', linestyle="--",
                       alpha=0.5, linewidth=1.2)
        ax_bot.axvline(x=evt["timestep"], color='#43A047', linestyle="--",
                       alpha=0.5, linewidth=1.2)

    # Annotate deadlock moments on top subplot
    for evt in deadlock_log:
        t_dl = evt["timestep"]
        mt_before = evt["mt_before"]
        mt_after = evt["mt_after"]
        ax_top.annotate(
            f"DL\nmt {mt_before}→{mt_after}",
            xy=(t_dl, mt_before - 0.5),
            fontsize=6,
            color="red",
            ha="center",
            va="top",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.6,
                      ec="red", linewidth=0.5),
        )

    ax_bot.set_xlabel("Timestep")
    ax_bot.set_ylabel("Value")
    ax_bot.text(
        305, -1, 'All Serving\nor Idle',
        fontsize=7, color='gray', va='center', ha='left'
    )
    ax_bot.legend(loc="upper right", fontsize=8)
    ax_bot.yaxis.set_major_locator(mpl.ticker.MaxNLocator(integer=True))
    ax_bot.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(filename, dpi=150)
    plt.close(fig)
    print(f"Saved {filename}")


# ─── Plot 9: 3D Space-Time Trajectory View ──────────────────────────────────────

def plot_3d_mission_space(trajectory_log, task_positions, completed_tasks,
                           amv_colors, n_timesteps=300):
    fig = plt.figure(figsize=(14, 8))
    fig.suptitle('AMV Swarm — 3D Space-Time Trajectory View',
                 fontsize=15, fontweight='bold')

    # LEFT: Before — just initial positions at t=0 in 3D space
    ax1 = fig.add_subplot(121, projection='3d')
    ax1.set_title('Before Task Allocation (t=0)', fontsize=11, fontweight='bold')

    for i, traj in trajectory_log.items():
        x0, y0 = traj[0]
        ax1.scatter(x0, y0, 0, color=amv_colors[i % len(amv_colors)], s=120,
                    marker='^', edgecolors='black', linewidths=1, zorder=5)
        ax1.text(x0, y0, 5, f'AMV{i}', fontsize=7,
                 color=amv_colors[i % len(amv_colors)], fontweight='bold')

    for j, (tx, ty) in enumerate(task_positions):
        ax1.scatter(tx, ty, 0, color='gray', s=80, marker='s',
                    edgecolors='black', linewidths=1)
        ax1.text(tx, ty, 5, f'T{j}', fontsize=6, color='#333333')

    ax1.set_xlabel('X (m)', labelpad=8)
    ax1.set_ylabel('Y (m)', labelpad=8)
    ax1.set_zlabel('Time', labelpad=8)
    ax1.set_xlim(0, 1000)
    ax1.set_ylim(0, 1000)
    ax1.set_zlim(0, n_timesteps)
    ax1.view_init(elev=25, azim=-60)
    ax1.set_facecolor('#f0f4f8')

    # RIGHT: After — full 3D trajectories through time
    ax2 = fig.add_subplot(122, projection='3d')
    ax2.set_title('After Task Allocation — Space-Time Trajectories',
                  fontsize=11, fontweight='bold')

    for i, traj in trajectory_log.items():
        xs = [p[0] for p in traj]
        ys = [p[1] for p in traj]
        zs = list(range(len(traj)))
        ax2.plot(xs, ys, zs, color=amv_colors[i % len(amv_colors)], linewidth=1.8,
                 alpha=0.85, label=f'AMV {i}')
        # Mark start
        ax2.scatter(xs[0], ys[0], 0, color=amv_colors[i % len(amv_colors)], s=80,
                    marker='^', edgecolors='black', linewidths=1)
        # Mark end
        ax2.scatter(xs[-1], ys[-1], zs[-1], color=amv_colors[i % len(amv_colors)],
                    s=100, marker='o', edgecolors='black', linewidths=1)

    for j, (tx, ty) in enumerate(task_positions):
        color = '#4CAF50' if j in completed_tasks else '#F44336'
        ax2.scatter(tx, ty, 0, color=color, s=90, marker='s',
                    edgecolors='black', linewidths=1, zorder=5)
        ax2.text(tx, ty, 10, f'T{j}', fontsize=6, color='#333333')

    ax2.set_xlabel('X (m)', labelpad=8)
    ax2.set_ylabel('Y (m)', labelpad=8)
    ax2.set_zlabel('Timestep', labelpad=8)
    ax2.set_xlim(0, 1000)
    ax2.set_ylim(0, 1000)
    ax2.set_zlim(0, n_timesteps)
    ax2.view_init(elev=25, azim=-60)
    ax2.legend(loc='upper left', fontsize=8)
    ax2.set_facecolor('#f0f4f8')

    plt.tight_layout()
    plt.savefig('plot_3d_mission_space.png', bbox_inches='tight', dpi=150)
    plt.close()
    print("Saved plot_3d_mission_space.png")


# ─── Plot 10: Physics Dashboard ──────────────────────────────────────────────────

def plot_physics_dashboard(physics_log, fault_log=None):
    """
    5-panel figure: depth, temperature, pressure, sound speed, DVL drift.
    physics_log: {amv_id: [{'t': ..., 'depth': ..., 'temp': ..., 'pressure': ...,
                            'sound_speed': ..., 'buoyancy': ..., 'dvl_drift': ...}]}
    fault_log:   {amv_id: [(timestep, fault_state), ...]}
    """
    fig, axes = plt.subplots(5, 1, figsize=(14, 18), sharex=True)
    fig.suptitle('Physics Dashboard — AMV Operating Environment',
                 fontsize=16, fontweight='bold', y=0.96)

    amv_ids = sorted(physics_log.keys())
    for amv_id in amv_ids:
        records = physics_log[amv_id]
        ts  = [r['t'] for r in records]
        c   = AMV_COLORS[amv_id % len(AMV_COLORS)]
        lbl = f'AMV {amv_id}'

        # Panel 1: Depth (inverted y)
        depths = [r['depth'] for r in records]
        axes[0].plot(ts, depths, color=c, linewidth=1.5, label=lbl, alpha=0.85)

        # Panel 2: Temperature
        temps = [r['temp'] for r in records]
        axes[1].plot(ts, temps, color=c, linewidth=1.5, label=lbl, alpha=0.85)

        # Panel 3: Pressure
        pressures = [r['pressure'] for r in records]
        axes[2].plot(ts, pressures, color=c, linewidth=1.5, label=lbl, alpha=0.85)

        # Panel 4: Sound speed
        speeds = [r['sound_speed'] for r in records]
        axes[3].plot(ts, speeds, color=c, linewidth=1.5, label=lbl, alpha=0.85)

        # Panel 5: DVL drift (with fill)
        dvl_drifts = [r.get('dvl_drift', 0.0) for r in records]
        axes[4].plot(ts, dvl_drifts, color=c, linewidth=1.8,
                     label=lbl, alpha=0.9)
        axes[4].fill_between(ts, dvl_drifts, alpha=0.08, color=c)

    # Mark sensor_failure timesteps with red dots on DVL panel
    if fault_log is not None:
        for amv_id in amv_ids:
            records = physics_log[amv_id]
            faults  = fault_log.get(amv_id, [])
            for i, r in enumerate(records):
                if i < len(faults) and faults[i][1] == 'sensor_failure':
                    axes[4].scatter(r['t'], r.get('dvl_drift', 0.0),
                                    color='red', s=20, zorder=6, alpha=0.8)

    # Depth panel
    axes[0].set_ylabel('Depth (m)', fontweight='bold')
    axes[0].invert_yaxis()
    axes[0].legend(loc='upper right', fontsize=8)
    axes[0].set_title('Operating Depth', fontsize=11)

    # Temperature panel
    axes[1].set_ylabel('Temperature (°C)', fontweight='bold')
    import config as _cfg
    thermo_temp = (_cfg.SURFACE_TEMP + _cfg.DEEP_TEMP) / 2.0
    axes[1].axhline(y=thermo_temp, color='#E91E63', linestyle='--', linewidth=1.5,
                    alpha=0.6, label=f'Thermocline ~{thermo_temp:.0f}°C')
    axes[1].legend(loc='upper right', fontsize=8)
    axes[1].set_title('Water Temperature at AMV Depth', fontsize=11)

    # Pressure panel
    axes[2].set_ylabel('Pressure (bar)', fontweight='bold')
    axes[2].set_title('Hydrostatic Pressure', fontsize=11)

    # Sound speed panel
    axes[3].set_ylabel('Sound Speed (m/s)', fontweight='bold')
    axes[3].set_title('Mackenzie Sound Speed', fontsize=11)

    # DVL drift panel — threshold, labels, danger zone, legend
    axes[4].set_ylabel('Position Error (m)', fontweight='bold')
    axes[4].set_xlabel('Timestep', fontweight='bold')
    axes[4].set_title('DVL Dead Reckoning Drift — Navigation Position Error',
                      fontsize=11)
    axes[4].axhline(y=15.0, color='#E91E63', linestyle='--', linewidth=1.5,
                    alpha=0.7, label='Navigation Uncertainty Threshold (15 m)')
    # Danger zone above threshold
    y_top = max(axes[4].get_ylim()[1], 20)
    axes[4].axhspan(15.0, y_top, alpha=0.06, color='red')
    # Legend with AMV lines + sensor_failure dot
    from matplotlib.lines import Line2D as _Line2D
    _amv_handles = [_Line2D([0], [0], color=AMV_COLORS[i % len(AMV_COLORS)],
                            linewidth=2, label=f'AMV {i}')
                    for i in amv_ids]
    _sensor_dot = _Line2D([0], [0], marker='o', color='w',
                          markerfacecolor='red', markersize=6,
                          label='sensor_failure active')
    _thresh_line = _Line2D([0], [0], color='#E91E63', linestyle='--',
                           linewidth=1.5, label='Uncertainty Threshold (15 m)')
    axes[4].legend(handles=_amv_handles + [_sensor_dot, _thresh_line],
                   loc='upper left', fontsize=7)

    for ax in axes:
        ax.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    plt.savefig('plot_physics_dashboard.png', bbox_inches='tight', dpi=150)
    plt.close()
    print("Saved plot_physics_dashboard.png")


# ─── Plot 11: Acoustic Communication Mesh Animation ─────────────────────────────

def plot_mesh_animation(mesh_snapshots, filename='mesh_animation.gif'):
    """
    Save an animated GIF showing how the acoustic communication mesh evolves.

    mesh_snapshots: list of dicts, each with keys:
        timestep, amv_positions, amv_states, amv_depths,
        task_statuses, edges
    """
    from matplotlib.animation import FuncAnimation, PillowWriter

    if not mesh_snapshots:
        print("No mesh snapshots to animate — skipping mesh_animation.gif")
        return

    # FSM state abbreviation mapping
    _STATE_ABBREV = {
        'Homing': 'H', 'Assignment': 'A', 'Reaching': 'R',
        'Serving': 'S', 'Idle': 'I', 'Deadlock': 'D', 'Patrol': 'P',
    }

    fig, ax = plt.subplots(figsize=(9, 9))

    def _draw_frame(frame_idx):
        ax.clear()
        snap = mesh_snapshots[frame_idx]
        ts = snap['timestep']
        amv_pos = snap['amv_positions']
        amv_states = snap['amv_states']
        amv_depths = snap['amv_depths']
        task_statuses = snap['task_statuses']
        edges = snap['edges']

        ax.set_facecolor('#f0f4f8')
        ax.set_xlim(-30, 1030)
        ax.set_ylim(-30, 1030)
        ax.set_aspect('equal')
        ax.set_xlabel('X Position (m)')
        ax.set_ylabel('Y Position (m)')
        ax.grid(True, alpha=0.2)

        # ── Tasks ────────────────────────────────────────────────────────
        for tid, (tpos, tstatus) in task_statuses.items():
            color = '#BDBDBD' if tstatus == 'unassigned' else (
                    '#FF9800' if tstatus == 'active' else '#4CAF50')
            ax.scatter(tpos[0], tpos[1], c=color, marker='s', s=160,
                       zorder=4, edgecolors='black', linewidths=1.2)
            ax.annotate(f'T{tid}', (tpos[0], tpos[1]), fontsize=6,
                        textcoords='offset points', xytext=(5, 5))

        # ── Acoustic links ───────────────────────────────────────────────
        n_links = 0
        for u, v, plp in edges:
            if u not in amv_pos or v not in amv_pos:
                continue
            quality = 1.0 - plp
            lw = max(0.6, quality * 4.5)
            edge_color = plt.cm.Blues(0.3 + 0.7 * quality)
            pu, pv = amv_pos[u], amv_pos[v]
            ax.plot([pu[0], pv[0]], [pu[1], pv[1]], color=edge_color,
                    linewidth=lw, alpha=0.7, zorder=2)
            n_links += 1

        # ── AMVs — triangles, range circles, labels ──────────────────────
        for aid in sorted(amv_pos.keys()):
            pos = amv_pos[aid]
            c = AMV_COLORS[aid % len(AMV_COLORS)]
            ax.scatter(pos[0], pos[1], c=c, marker='^', s=220, zorder=6,
                       edgecolors='black', linewidths=1.5)

            # Range circle — depth-dependent
            depth = amv_depths.get(aid, 0.0)
            frac = min(depth / config.DEPTH_MAX, 1.0)
            radius = config.ACOUSTIC_RANGE_SURFACE * (1 - frac) + \
                     config.ACOUSTIC_RANGE_DEEP * frac
            circle = plt.Circle((pos[0], pos[1]), radius,
                                fill=False, color='#E53935',
                                linestyle='--', linewidth=0.9, alpha=0.5)
            ax.add_patch(circle)

            # FSM state abbreviation label
            state_str = amv_states.get(aid, '')
            abbrev = _STATE_ABBREV.get(state_str, '?')
            ax.annotate(f'AMV{aid} [{abbrev}]', (pos[0], pos[1]),
                        fontsize=7, fontweight='bold',
                        textcoords='offset points', xytext=(6, -14),
                        color=c)

        ax.set_title(f'Acoustic Mesh — t={ts}   ({n_links} active links)',
                     fontsize=12, fontweight='bold')

    anim = FuncAnimation(fig, _draw_frame, frames=len(mesh_snapshots),
                         interval=350, repeat=True)
    writer = PillowWriter(fps=3)
    anim.save(filename, writer=writer)
    plt.close(fig)
    print(f"Saved {filename}  ({len(mesh_snapshots)} frames)")


# ─── Plot 12: Per-AMV FSM State Timeline ─────────────────────────────────────────

def plot_fsm_timeline(fsm_state_log, deadlock_log, completion_log,
                      filename='plot_fsm_timeline.png'):
    """
    Colour-coded horizontal timeline of each AMV's FSM state over time.

    fsm_state_log: {amv_id: [(timestep, fsm_state), ...]}
    deadlock_log:  [{timestep, ...}, ...]
    completion_log: [{timestep, task_id, ...}, ...]
    """
    FSM_COLORS = {
        config.FSM_HOMING:     '#90A4AE',
        config.FSM_ASSIGNMENT: '#FFF176',
        config.FSM_REACHING:   '#42A5F5',
        config.FSM_SERVING:    '#66BB6A',
        config.FSM_IDLE:       '#EF9A9A',
        config.FSM_DEADLOCK:   '#AB47BC',
        config.FSM_PATROL:     '#FFD180',   # light amber
    }

    amv_ids = sorted(fsm_state_log.keys())
    if not amv_ids:
        print("No FSM state data — skipping plot_fsm_timeline.png")
        return

    fig, ax = plt.subplots(figsize=(18, 6))
    fig.subplots_adjust(right=0.72)

    # ── Alternating row shading ──────────────────────────────────────────
    for row_idx in range(len(amv_ids)):
        if row_idx % 2 == 0:
            ax.axhspan(row_idx - 0.4, row_idx + 0.4, color='#f5f5f5', zorder=0)

    # ── Draw coloured segments per AMV ───────────────────────────────────
    for row_idx, amv_id in enumerate(amv_ids):
        records = fsm_state_log[amv_id]
        if not records:
            continue

        # Build contiguous segments
        segments = []
        cur_state = records[0][1]
        seg_start = records[0][0]
        for ts, state in records[1:]:
            if state != cur_state:
                segments.append((seg_start, ts, cur_state))
                cur_state = state
                seg_start = ts
        segments.append((seg_start, records[-1][0] + 1, cur_state))

        for start, end, state in segments:
            color = FSM_COLORS.get(state, '#95a5a6')
            ax.barh(row_idx, end - start, left=start, height=0.55,
                    color=color, edgecolor='white', linewidth=0.5)

        # ── Summary annotation: percentage per state ─────────────────────
        total = len(records)
        from collections import Counter
        counts = Counter(s for _, s in records)
        parts = []
        for st in [config.FSM_REACHING, config.FSM_SERVING,
                   config.FSM_IDLE, config.FSM_ASSIGNMENT,
                   config.FSM_PATROL, config.FSM_DEADLOCK,
                   config.FSM_HOMING]:
            pct = counts.get(st, 0) / total * 100
            if pct > 0.5:  # only show states with >0.5%
                short = st[:3] if len(st) <= 6 else st[:4]
                parts.append(f"{short} {pct:.0f}%")
        summary = ' | '.join(parts)
        # Place summary to the right of the row
        ax.text(records[-1][0] + 5, row_idx, summary,
                fontsize=6, va='center', color='#333333')

    # ── Deadlock events — red dashed vlines ──────────────────────────────
    dl_label = True
    for evt in deadlock_log:
        ax.axvline(x=evt['timestep'], color='#E53935', linestyle='--',
                   linewidth=1.2, alpha=0.7,
                   label='Deadlock Event' if dl_label else None)
        dl_label = False

    # ── Completion events — green dashed vlines ──────────────────────────
    cl_label = True
    for evt in completion_log:
        ax.axvline(x=evt['timestep'], color='#43A047', linestyle='--',
                   linewidth=1.2, alpha=0.5,
                   label='Task Completion' if cl_label else None)
        cl_label = False

    # ── Axis & legend ────────────────────────────────────────────────────
    ax.set_yticks(range(len(amv_ids)))
    ax.set_yticklabels([f'AMV {i}' for i in amv_ids])
    ax.set_xlabel('Timestep')
    ax.set_ylabel('AMV')
    ax.set_title('Per-AMV FSM State Timeline', fontsize=14, fontweight='bold')
    ax.xaxis.set_major_locator(mpl.ticker.MultipleLocator(50))
    ax.grid(axis='x', alpha=0.4)

    # Colour legend — FSM states
    state_patches = [mpatches.Patch(color=FSM_COLORS[s], label=s)
                     for s in FSM_COLORS]
    # Also add event markers to legend
    event_handles = [
        mlines.Line2D([], [], color='#E53935', linestyle='--', label='Deadlock Event'),
        mlines.Line2D([], [], color='#43A047', linestyle='--', label='Task Completion'),
    ]
    ax.legend(handles=state_patches + event_handles,
              loc='upper left', bbox_to_anchor=(1.01, 1),
              borderaxespad=0, fontsize=8)

    fig.tight_layout()
    fig.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {filename}")


# ─── Plot 13: FSM Transition Diagram (Static) ───────────────────────────────────

def plot_fsm_diagram(filename='plot_fsm_diagram.png'):
    """Static networkx diagram of the FSM architecture with labelled transitions."""

    FSM_COLORS = {
        config.FSM_HOMING:     '#90A4AE',
        config.FSM_ASSIGNMENT: '#FFF176',
        config.FSM_REACHING:   '#42A5F5',
        config.FSM_SERVING:    '#66BB6A',
        config.FSM_IDLE:       '#EF9A9A',
        config.FSM_DEADLOCK:   '#AB47BC',
        config.FSM_PATROL:     '#FFA726',
    }

    G = nx.DiGraph()
    states = list(FSM_COLORS.keys())
    for s in states:
        G.add_node(s)

    transitions = [
        (config.FSM_HOMING,     config.FSM_ASSIGNMENT, 'Simulation start'),
        (config.FSM_ASSIGNMENT, config.FSM_REACHING,   'Task won\nat auction'),
        (config.FSM_ASSIGNMENT, config.FSM_IDLE,       'Pausing algorithm\n/ no task'),
        (config.FSM_REACHING,   config.FSM_SERVING,    'Arrived within\n15 m of task'),
        (config.FSM_REACHING,   config.FSM_DEADLOCK,   'Availability\n< threshold'),
        (config.FSM_SERVING,    config.FSM_ASSIGNMENT, 'Dwell timer\ncomplete'),
        (config.FSM_IDLE,       config.FSM_ASSIGNMENT, 'Task completion /\nperiodic auction'),
        (config.FSM_DEADLOCK,   config.FSM_ASSIGNMENT, 'Global deadlock\nresolved'),
        (config.FSM_ASSIGNMENT, config.FSM_PATROL,     'Idle > 8\ntimesteps'),
        (config.FSM_PATROL,     config.FSM_ASSIGNMENT, 'Periodic auction\nwakes AMV'),
    ]
    for src, dst, label in transitions:
        G.add_edge(src, dst, label=label)

    # Fixed positions for readability
    pos = {
        config.FSM_HOMING:     (-2.0,  1.5),
        config.FSM_ASSIGNMENT: ( 0.0,  1.5),
        config.FSM_REACHING:   ( 2.0,  1.5),
        config.FSM_SERVING:    ( 3.5,  0.0),
        config.FSM_IDLE:       (-1.5, -1.0),
        config.FSM_DEADLOCK:   ( 2.0, -1.0),
        config.FSM_PATROL:     ( 0.0, -1.0),
    }

    node_colors = [FSM_COLORS[s] for s in G.nodes()]

    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_facecolor('#fafafa')
    ax.set_title('AMV Finite-State Machine (FSM) Architecture',
                 fontsize=15, fontweight='bold', pad=20)

    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors,
                           node_size=3000, edgecolors='#333333', linewidths=1.5)
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=9, font_weight='bold')

    # Curved edges
    nx.draw_networkx_edges(
        G, pos, ax=ax,
        arrowstyle='-|>', arrowsize=18,
        edge_color='#555555', width=1.5,
        connectionstyle='arc3,rad=0.15',
        min_source_margin=25, min_target_margin=25,
    )

    # Edge labels
    edge_labels = {(u, v): d['label'] for u, v, d in G.edges(data=True)}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels,
                                 font_size=7, ax=ax, label_pos=0.5,
                                 bbox=dict(boxstyle='round,pad=0.2',
                                           fc='white', ec='#cccccc',
                                           alpha=0.85))

    ax.axis('off')
    fig.tight_layout()
    fig.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {filename}")


# ─── Plot 14: CNN Classification Confidence Distribution ─────────────────────

def plot_confidence_histogram(confidence_log, filename='plot_confidence_histogram.png'):
    """
    Two-panel figure showing CNN classification confidence.

    confidence_log: list of dicts with keys:
        timestep, amv_id, max_prob, class
    """
    if not confidence_log:
        print("No confidence data — skipping plot_confidence_histogram.png")
        return

    all_probs = [entry['max_prob'] for entry in confidence_log]
    all_classes = [entry['class'] for entry in confidence_log]

    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle('CNN Classification Confidence Distribution',
                 fontsize=15, fontweight='bold')

    # ── LEFT: Overall distribution ───────────────────────────────────────
    ax_left.hist(all_probs, bins=40, color='#1565C0', edgecolor='white',
                 alpha=0.85, linewidth=0.5)
    ax_left.axvline(x=0.75, color='red', linestyle='--', linewidth=2,
                    label='Confidence Threshold (0.75)')

    below_threshold = sum(1 for p in all_probs if p < 0.75)
    pct_below = below_threshold / max(len(all_probs), 1) * 100
    ax_left.annotate(
        f'{below_threshold} predictions ({pct_below:.1f}%)\nbelow 0.75 threshold',
        xy=(0.75, ax_left.get_ylim()[1] * 0.85 if ax_left.get_ylim()[1] > 0 else 1),
        xytext=(0.3, ax_left.get_ylim()[1] * 0.7 if ax_left.get_ylim()[1] > 0 else 0.8),
        fontsize=9, color='red', fontweight='bold',
        arrowprops=dict(arrowstyle='->', color='red', lw=1.5),
    )

    ax_left.set_xlabel('Max Softmax Probability')
    ax_left.set_ylabel('Count')
    ax_left.set_title('Overall Confidence Distribution')
    ax_left.legend(loc='upper left', fontsize=9)
    ax_left.grid(True, alpha=0.3)

    # Re-draw to get proper ylim for annotation
    fig.canvas.draw()

    # ── RIGHT: Per-class distribution ────────────────────────────────────
    unique_classes = sorted(set(all_classes))
    for cls in unique_classes:
        cls_probs = [entry['max_prob'] for entry in confidence_log
                     if entry['class'] == cls]
        color = FAULT_COLORS.get(cls, '#95a5a6')
        ax_right.hist(cls_probs, bins=40, alpha=0.5, color=color,
                      label=cls, edgecolor='white', linewidth=0.3)

    ax_right.axvline(x=0.75, color='red', linestyle='--', linewidth=2)
    ax_right.set_xlabel('Max Softmax Probability')
    ax_right.set_ylabel('Count')
    ax_right.set_title('Confidence Distribution Per Fault Class')
    ax_right.legend(loc='upper left', fontsize=8)
    ax_right.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {filename}")

