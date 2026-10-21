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

import os

import config

LATEST_RUNS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "latest_runs")

def _get_save_path(filename):
    os.makedirs(LATEST_RUNS_DIR, exist_ok=True)
    if os.path.isabs(filename):
        return filename
    return os.path.join(LATEST_RUNS_DIR, os.path.basename(filename))

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

    out_path = _get_save_path(filename)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")


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
    out_path = _get_save_path(filename)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved {out_path}")


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
    out_path = _get_save_path(filename)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved {out_path}")


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
    out_path = _get_save_path(filename)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")


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
    out_path = _get_save_path(filename)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")


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
    out_path = _get_save_path(filename)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved {out_path}")


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
    out_path = _get_save_path(filename)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved {out_path}")


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
    out_path = _get_save_path(filename)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved {out_path}")


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
    out_path = _get_save_path('plot_3d_mission_space.png')
    plt.savefig(out_path, bbox_inches='tight', dpi=150)
    plt.close()
    print(f"Saved {out_path}")


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
    out_path = _get_save_path('plot_physics_dashboard.png')
    plt.savefig(out_path, bbox_inches='tight', dpi=150)
    plt.close()
    print(f"Saved {out_path}")


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


# ─── Plot 12: Per-AMV FSM State & Fault State Timeline ───────────────────────────

def plot_fsm_timeline(fsm_state_log, deadlock_log, completion_log,
                      fault_log=None, fault_events=None, fault_injection_events=None,
                      fsm_transitions=None, unknown_fault_log=None,
                      filename='plot_fsm_timeline.png', **kwargs):
    """
    Colour-coded horizontal timeline of each AMV's FSM state with overlaid fault states,
    open-set UNKNOWN_FAULT indicators, and annotated fault injection events over time.

    fsm_state_log: {amv_id: [(timestep, fsm_state), ...]}
    deadlock_log:  [{timestep, ...}, ...]
    completion_log: [{timestep, task_id, ...}, ...]
    fault_log:     {amv_id: [(timestep, fault_state), ...]} (optional)
    fault_events:  [{timestep, amv_id, fault_state, ...}, ...] (optional)
    """
    if fault_events is None and fault_injection_events is not None:
        fault_events = fault_injection_events

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

    fig, ax = plt.subplots(figsize=(18, 7.5))
    fig.subplots_adjust(right=0.72)

    has_fault_overlay = fault_log is not None and len(fault_log) > 0

    # ── Alternating row shading ──────────────────────────────────────────
    for row_idx in range(len(amv_ids)):
        if row_idx % 2 == 0:
            ax.axhspan(row_idx - 0.45, row_idx + 0.45, color='#f5f5f5', zorder=0)

    # ── Draw coloured segments per AMV ───────────────────────────────────
    for row_idx, amv_id in enumerate(amv_ids):
        records = fsm_state_log[amv_id]
        if not records:
            continue

        # Build contiguous FSM segments
        segments = []
        cur_state = records[0][1]
        seg_start = records[0][0]
        for ts, state in records[1:]:
            if state != cur_state:
                segments.append((seg_start, ts, cur_state))
                cur_state = state
                seg_start = ts
        segments.append((seg_start, records[-1][0] + 1, cur_state))

        fsm_y = row_idx + 0.12 if has_fault_overlay else row_idx
        fsm_h = 0.32 if has_fault_overlay else 0.55

        for start, end, state in segments:
            color = FSM_COLORS.get(state, '#95a5a6')
            ax.barh(fsm_y, end - start, left=start, height=fsm_h,
                    color=color, edgecolor='white', linewidth=0.5, zorder=2)

        # ── Overlay Fault State if available ──────────────────────────────
        if has_fault_overlay and amv_id in fault_log:
            f_records = fault_log[amv_id]
            if f_records:
                f_segments = []
                cur_f = f_records[0][1]
                seg_f_start = f_records[0][0]
                for f_ts, f_state in f_records[1:]:
                    if f_state != cur_f:
                        f_segments.append((seg_f_start, f_ts, cur_f))
                        cur_f = f_state
                        seg_f_start = f_ts
                f_segments.append((seg_f_start, f_records[-1][0] + 1, cur_f))

                fault_y = row_idx - 0.18
                fault_h = 0.22
                for start, end, state in f_segments:
                    f_color = FAULT_COLORS.get(state, '#95a5a6')
                    ax.barh(fault_y, end - start, left=start, height=fault_h,
                            color=f_color, edgecolor='white', linewidth=0.5, zorder=2)

        # ── Overlay UNKNOWN_FAULT if flagged ─────────────────────────────
        if unknown_fault_log:
            u_events = [e for e in unknown_fault_log if (isinstance(e, dict) and e.get('amv_id') == amv_id) or (isinstance(e, (tuple, list)) and e[1] == amv_id)]
            for u in u_events:
                u_ts = u['timestep'] if isinstance(u, dict) else u[0]
                target_y = row_idx - 0.18 if has_fault_overlay else row_idx
                target_h = 0.22 if has_fault_overlay else 0.55
                ax.barh(target_y, 10, left=u_ts, height=target_h,
                        color='none', edgecolor='#D50000', hatch='///', linewidth=1.5, zorder=5)

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
                fontsize=7, va='center', color='#333333', fontweight='bold')

    # ── Deadlock events — red dashed vlines ──────────────────────────────
    dl_label = True
    for evt in deadlock_log:
        ax.axvline(x=evt['timestep'], color='#E53935', linestyle='--',
                   linewidth=1.2, alpha=0.7, zorder=3,
                   label='Deadlock Event' if dl_label else None)
        dl_label = False

    # ── Completion events — green dashed vlines ──────────────────────────
    cl_label = True
    for evt in completion_log:
        ax.axvline(x=evt['timestep'], color='#43A047', linestyle='--',
                   linewidth=1.2, alpha=0.5, zorder=3,
                   label='Task Completion' if cl_label else None)
        cl_label = False

    # ── Fault injection events — purple dash-dot vlines and annotations ────
    if fault_events:
        fe_label = True
        for fe in fault_events:
            fe_ts = fe.get('timestep', 0)
            fe_aid = fe.get('amv_id', -1)
            fe_type = fe.get('type', fe.get('fault_state', 'fault'))
            ax.axvline(x=fe_ts, color='#8E24AA', linestyle='-.',
                       linewidth=1.8, alpha=0.85, zorder=4,
                       label='Fault Injection Event' if fe_label else None)
            fe_label = False
            ax.scatter(fe_ts, fe_aid if fe_aid in amv_ids else 0,
                       marker='D', color='#8E24AA', s=80, edgecolors='black',
                       linewidths=1.0, zorder=6)
            ax.text(fe_ts + 2, fe_aid + 0.28, f"Fault: AMV{fe_aid} ({fe_type})",
                    fontsize=7, fontweight='bold', color='#6A1B9A', rotation=25,
                    bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='#8E24AA', alpha=0.85))

    # ── Axis & legend ────────────────────────────────────────────────────
    ax.set_yticks(range(len(amv_ids)))
    if has_fault_overlay:
        ax.set_yticklabels([f'AMV {i}\n[FSM / Fault]' for i in amv_ids], fontsize=9, fontweight='bold')
    else:
        ax.set_yticklabels([f'AMV {i}' for i in amv_ids], fontsize=9, fontweight='bold')
    ax.set_xlabel('Timestep', fontsize=11, fontweight='bold')
    ax.set_ylabel('AMV', fontsize=11, fontweight='bold')
    title_suffix = " (with Overlaid Fault State & Fault Injections)" if has_fault_overlay else ""
    ax.set_title(f'Per-AMV FSM State Timeline{title_suffix}', fontsize=14, fontweight='bold')
    ax.xaxis.set_major_locator(mpl.ticker.MultipleLocator(50))
    ax.grid(axis='x', alpha=0.4)

    # Colour legend — FSM states
    state_patches = [mpatches.Patch(color=FSM_COLORS[s], label=f"FSM: {s}")
                     for s in FSM_COLORS]
    
    fault_patches = []
    if has_fault_overlay:
        fault_patches = [mpatches.Patch(color=FAULT_COLORS[s], label=f"Fault: {s}")
                         for s in FAULT_COLORS]

    # Event markers to legend
    event_handles = [
        mlines.Line2D([], [], color='#E53935', linestyle='--', label='Deadlock Event'),
        mlines.Line2D([], [], color='#43A047', linestyle='--', label='Task Completion'),
    ]
    if fault_events:
        event_handles.append(
            mlines.Line2D([], [], color='#8E24AA', linestyle='-.', marker='D',
                          markersize=6, label='Fault Injection Event')
        )
    if unknown_fault_log:
        event_handles.append(
            mpatches.Patch(facecolor='none', edgecolor='#D50000', hatch='///', linewidth=1.5,
                           label='Open-Set: UNKNOWN_FAULT')
        )

    all_handles = state_patches + fault_patches + event_handles
    ax.legend(handles=all_handles,
              loc='upper left', bbox_to_anchor=(1.01, 1),
              borderaxespad=0, fontsize=7.5, framealpha=0.95)

    fig.tight_layout()
    out_path = _get_save_path(filename)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")



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
    out_path = _get_save_path(filename)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")


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
    out_path = _get_save_path(filename)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")


def plot_allocator_comparison_completion(results_df, filename='plot_allocator_comparison_completion.png'):
    """
    Plots Task Completion Rate over time for Auction vs CBBA across the 4 scenarios.
    """
    scenarios = ['none', 'amv_loss', 'comm_blackout', 'mass_fault']
    scenario_titles = {
        'none': 'Nominal (No Stress)',
        'amv_loss': 'AMV Loss Stress Scenario',
        'comm_blackout': 'Comm Blackout Stress Scenario',
        'mass_fault': 'Mass Fault Stress Scenario'
    }

    fig, axes = plt.subplots(2, 2, figsize=(15, 11), sharex=True, sharey=True)
    axes = axes.flatten()

    for idx, sc in enumerate(scenarios):
        ax = axes[idx]
        ax.set_facecolor('#fafafa')
        
        # Filter scenario data
        sc_data = results_df[results_df['scenario'] == sc]
        
        for alloc, color, label in [('auction', '#1565C0', 'Auction + EDMC (Proposed)'),
                                    ('cbba', '#E65100', 'CBBA (Baseline)')]:
            alloc_data = sc_data[sc_data['allocator'] == alloc]
            if alloc_data.empty:
                continue
            
            # Group by timestep and calculate mean/std
            grouped = alloc_data.groupby('timestep')['tasks_completed'].agg(['mean', 'std']).reset_index()
            t_vals = grouped['timestep']
            mean_rate = grouped['mean'] / config.N_TASKS
            std_rate = grouped['std'].fillna(0) / config.N_TASKS
            
            ax.plot(t_vals, mean_rate, color=color, linewidth=2.5, label=label)
            ax.fill_between(t_vals, np.clip(mean_rate - std_rate, 0, 1), np.clip(mean_rate + std_rate, 0, 1),
                            color=color, alpha=0.15)
            
        ax.set_title(scenario_titles[sc], fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(-0.05, 1.05)
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(xmax=1.0))
        
        # Stress line at t=150
        if sc != 'none':
            ax.axvline(x=150, color='#7f8c8d', linestyle=':', linewidth=1.5, zorder=1)
            ax.text(152, 0.5, 'Stress Injected', color='#7f8c8d', rotation=90, fontsize=8, va='center')

        if idx in [2, 3]:
            ax.set_xlabel('Timestep', fontweight='bold')
        if idx in [0, 2]:
            ax.set_ylabel('Task Completion Rate', fontweight='bold')

    # Add single legend
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.98), ncol=2, fontsize=10)
    fig.suptitle('Task Completion Rate Over Time: Auction vs CBBA', fontsize=16, fontweight='bold', y=1.02)
    fig.tight_layout()
    out_path = _get_save_path(filename)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")


def plot_allocator_comparison_deadlock_recovery(results_df, filename='plot_allocator_comparison_deadlock_recovery.png'):
    """
    Plots recovery timeline showing CBBA stalling vs Auction resolving via EDMC.
    """
    stress_scenarios = ['amv_loss', 'mass_fault']
    scenario_titles = {
        'amv_loss': 'AMV Loss (2 Vehicles Lost at t=150)',
        'mass_fault': 'Mass Fault (3 Vehicles Degraded at t=150)'
    }

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))
    twin_ax_legend = None
    
    for idx, sc in enumerate(stress_scenarios):
        ax1 = axes[idx]
        ax1.set_facecolor('#fafafa')
        
        # Filter scenario data
        sc_data = results_df[results_df['scenario'] == sc]
        
        # Plot Task Completion Rate on left axis
        ax1.set_xlabel('Timestep', fontweight='bold')
        ax1.set_ylabel('Task Completion Rate (Solid Line)', color='#333333', fontweight='bold')
        ax1.tick_params(axis='y', labelcolor='#333333')
        
        # Secondary axis for stalled AMVs
        ax2 = ax1.twinx()
        ax2.set_ylabel('Active Stalled AMVs (Dashed Line)', color='#7f8c8d', fontweight='bold')
        ax2.tick_params(axis='y', labelcolor='#7f8c8d')
        ax2.set_ylim(-0.2, config.N_AMVS + 0.2)
        if idx == 0:
            twin_ax_legend = ax2
        
        # Plot Auction
        auc_data = sc_data[sc_data['allocator'] == 'auction']
        if not auc_data.empty:
            auc_grouped = auc_data.groupby('timestep')[['tasks_completed', 'stalled_amvs']].mean().reset_index()
            ax1.plot(auc_grouped['timestep'], auc_grouped['tasks_completed'] / config.N_TASKS,
                     color='#1565C0', linewidth=2.5, label='Auction Completion')
            ax2.plot(auc_grouped['timestep'], auc_grouped['stalled_amvs'],
                     color='#2196F3', linewidth=1.5, linestyle='--', label='Auction Stalled')
            
        # Plot CBBA
        cbba_data = sc_data[sc_data['allocator'] == 'cbba']
        if not cbba_data.empty:
            cbba_grouped = cbba_data.groupby('timestep')[['tasks_completed', 'stalled_amvs']].mean().reset_index()
            ax1.plot(cbba_grouped['timestep'], cbba_grouped['tasks_completed'] / config.N_TASKS,
                     color='#E65100', linewidth=2.5, label='CBBA Completion')
            ax2.plot(cbba_grouped['timestep'], cbba_grouped['stalled_amvs'],
                     color='#FF9800', linewidth=1.5, linestyle='--', label='CBBA Stalled')

        ax1.grid(True, alpha=0.3)
        ax1.set_ylim(-0.05, 1.05)
        ax1.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(xmax=1.0))
        
        # Stress line at t=150
        ax1.axvline(x=150, color='red', linestyle=':', linewidth=1.5, zorder=1)
        ax1.text(152, 0.05, 'Stress Injected', color='red', fontsize=8, fontweight='bold')
        
        ax1.set_title(scenario_titles[sc], fontsize=12, fontweight='bold')

    # Collect legend handles
    handles = []
    labels = []
    for ax in [axes[0], twin_ax_legend]:
        if ax is not None:
            h, l = ax.get_legend_handles_labels()
            handles.extend(h)
            labels.extend(l)
            
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.98), ncol=4, fontsize=10)
    
    fig.suptitle('Allocator Deadlock Recovery & Stalling Under Stress Scenarios', fontsize=16, fontweight='bold', y=1.02)
    fig.tight_layout()
    out_path = _get_save_path(filename)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")


# ─── Plot 15: Task-to-AMV Completion Mapping & Table ─────────────────────────────

def plot_task_completion_mapping(task_completion_log, tasks=None,
                                 n_amvs=None, filename='plot_task_completion_mapping.png', **kwargs):
    """
    Color-coded timeline + structured attribution table showing Task ID -> Completing AMV -> Completion Timestep.

    task_completion_log: [{timestep, task_id, amv_id}, ...]
    tasks: list of Task objects
    """
    # Handle swapped or named parameters
    if tasks is None:
        if isinstance(task_completion_log, list) and len(task_completion_log) > 0 and hasattr(task_completion_log[0], 'task_id'):
            tasks = task_completion_log
            task_completion_log = kwargs.get('task_completion_log', [])
    elif isinstance(task_completion_log, list) and len(task_completion_log) > 0 and hasattr(task_completion_log[0], 'task_id'):
        # Swapped: first arg is tasks list, second is completion log
        tasks, task_completion_log = task_completion_log, tasks

    real_tasks = [t for t in (tasks or []) if not getattr(t, 'is_dummy', False)]
    if not real_tasks:
        print("No tasks to plot for task completion mapping.")
        return

    # Map task completions: {task_id: {'amv_id': aid, 'timestep': t}}
    completion_map = {}
    for entry in (task_completion_log or []):
        tid = entry['task_id']
        completion_map[tid] = {
            'amv_id': entry['amv_id'],
            'timestep': entry['timestep']
        }

    # If task is marked completed on task object but not in log (fallback)
    for t in real_tasks:
        if t.status == 'completed' and t.task_id not in completion_map:
            completion_map[t.task_id] = {
                'amv_id': t.assigned_to,
                'timestep': getattr(t, 'completion_timestep', config.SIMULATION_TIMESTEPS)
            }

    sorted_tasks = sorted(real_tasks, key=lambda x: x.task_id)
    n_tasks = len(sorted_tasks)

    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.8, 1.2], hspace=0.35)
    ax_chart = fig.add_subplot(gs[0])
    ax_table = fig.add_subplot(gs[1])

    ax_chart.set_facecolor('#fafafa')

    # Alternating row background shading
    for idx in range(n_tasks):
        if idx % 2 == 0:
            ax_chart.axhspan(idx - 0.4, idx + 0.4, color='#f0f4f8', zorder=0)

    max_t = config.SIMULATION_TIMESTEPS
    for t_entry in completion_map.values():
        if t_entry['timestep'] is not None and t_entry['timestep'] > max_t:
            max_t = t_entry['timestep']

    # Draw horizontal bars per task
    for idx, t in enumerate(sorted_tasks):
        tid = t.task_id
        if tid in completion_map and t.status == 'completed':
            c_info = completion_map[tid]
            aid = c_info['amv_id']
            t_comp = c_info['timestep']
            c_color = AMV_COLORS[aid % len(AMV_COLORS)] if aid is not None else '#4CAF50'

            # Bar from 0 to completion timestep
            ax_chart.barh(idx, t_comp, left=0, height=0.55, color=c_color,
                          alpha=0.85, edgecolor='white', linewidth=1.0, zorder=2)

            # Marker at completion timestep
            ax_chart.scatter(t_comp, idx, marker='*', s=180, color='#FFD700',
                             edgecolors='black', linewidths=1.0, zorder=4)

            # Label on the right of bar
            label_str = f"Completed at t={t_comp} by AMV{aid}" if aid is not None else f"Completed at t={t_comp}"
            ax_chart.text(t_comp + 4, idx, label_str,
                          fontsize=8, fontweight='bold', va='center', color='#1A237E', zorder=3)
        else:
            # Uncompleted task: gray / red bar
            ax_chart.barh(idx, max_t * 0.15, left=0, height=0.55, color='#E0E0E0',
                          alpha=0.6, edgecolor='#BDBDBD', linewidth=1.0, zorder=2)
            ax_chart.text(max_t * 0.15 + 4, idx, "Uncompleted / Unassigned",
                          fontsize=8, fontstyle='italic', va='center', color='#D32F2F', zorder=3)

    ax_chart.set_yticks(range(n_tasks))
    ax_chart.set_yticklabels([f"Task {t.task_id} (prio={t.priority_weight:.2f})" for t in sorted_tasks],
                             fontsize=8.5, fontweight='bold')
    ax_chart.set_xlabel("Simulation Timestep", fontsize=11, fontweight='bold')
    ax_chart.set_ylabel("Task ID", fontsize=11, fontweight='bold')
    ax_chart.set_title("Task-to-AMV Completion Attribution Timeline", fontsize=13, fontweight='bold')
    ax_chart.set_xlim(0, max(max_t + 100, 100))
    ax_chart.grid(axis='x', alpha=0.4)

    # Legend for AMVs
    amv_handles = [
        mpatches.Patch(color=AMV_COLORS[i % len(AMV_COLORS)], label=f"AMV {i}")
        for i in range(config.N_AMVS)
    ]
    amv_handles.append(mlines.Line2D([], [], marker='*', color='w', markerfacecolor='#FFD700',
                                     markeredgecolor='black', markersize=10, label="Task Completion Point"))
    ax_chart.legend(handles=amv_handles, loc="upper right", fontsize=8, framealpha=0.9)

    # ── Table Subplot ────────────────────────────────────────────────────────
    ax_table.axis('off')
    table_data = []
    cell_colors = []
    
    table_headers = ["Task ID", "Priority", "Status", "Quality", "Completing AMV", "Completion Timestep"]
    
    for t in sorted_tasks:
        tid = t.task_id
        is_comp = (t.status == 'completed')
        c_info = completion_map.get(tid, {})
        aid = c_info.get('amv_id', t.assigned_to)
        t_comp = c_info.get('timestep', '—') if is_comp else '—'
        
        status_str = "COMPLETED" if is_comp else t.status.upper()
        quality_str = getattr(t, 'completion_quality', '—') if is_comp else '—'
        if not quality_str:
            quality_str = '—'
        amv_str = f"AMV {aid}" if (is_comp and aid is not None) else "—"
        
        row = [f"Task {tid}", f"{t.priority_weight:.2f}", status_str, quality_str, amv_str, str(t_comp)]
        table_data.append(row)
        
        # Color row cells
        if is_comp:
            q_col = '#C8E6C9' if quality_str == 'completed_clean' else '#FFE0B2'
            row_col = ['#E8F5E9', '#E8F5E9', '#C8E6C9', q_col, '#E3F2FD', '#E8F5E9']
        else:
            row_col = ['#FFEBEE', '#FFEBEE', '#FFCDD2', '#F5F5F5', '#F5F5F5', '#F5F5F5']
        cell_colors.append(row_col)

    table = ax_table.table(cellText=table_data, colLabels=table_headers,
                           cellColours=cell_colors, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    table.scale(1.0, 1.25)

    # Style header row
    for col_idx in range(len(table_headers)):
        cell = table[(0, col_idx)]
        cell.set_facecolor('#1A237E')
        cell.set_text_props(color='white', fontweight='bold')

    ax_table.set_title("Task Completion Attribution Summary Table", fontsize=12, fontweight='bold', pad=10)

    fig.tight_layout()
    out_path = _get_save_path(filename)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")


# ─── Plot 16: Per-AMV Trust Score Timeline ───────────────────────────────────────

def plot_trust_timeline(trust_log, trust_release_events=None,
                        filename='plot_trust_timeline.png'):
    """
    Per-AMV TrustScore line chart over time with release threshold (0.4) marked
    and task-release events annotated on the timeline.

    trust_log: {amv_id: [(timestep, trust_score, declared_fault_state, observed_speed), ...]}
    trust_release_events: list of dicts: [{timestep, amv_id, task_id, trust_score, ...}, ...]
    """
    if not trust_log:
        print("No trust log data — skipping plot_trust_timeline.png")
        return

    fig, (ax_trust, ax_speed) = plt.subplots(2, 1, figsize=(15, 8.5), sharex=True,
                                             gridspec_kw={'height_ratios': [1.8, 1.2]})
    fig.subplots_adjust(hspace=0.15)

    amv_ids = sorted(trust_log.keys())

    # ── TOP: Trust Score Timeline ──────────────────────────────────────────
    ax_trust.set_facecolor('#fafafa')

    # Shaded Untrusted Zone below 0.4
    ax_trust.axhspan(-0.05, config.TRUST_THRESHOLD, color='#FFEBEE', alpha=0.7, zorder=0)
    ax_trust.axhline(y=config.TRUST_THRESHOLD, color='#D32F2F', linestyle='--', linewidth=2.0,
                     label=f'Trust Release Threshold ({config.TRUST_THRESHOLD})', zorder=3)
    ax_trust.text(5, config.TRUST_THRESHOLD + 0.03, f"Release Threshold ({config.TRUST_THRESHOLD})",
                  color='#D32F2F', fontsize=8.5, fontweight='bold', zorder=4)

    for aid in amv_ids:
        records = trust_log[aid]
        if not records:
            continue
        ts = [r[0] for r in records]
        scores = [r[1] for r in records]
        c = AMV_COLORS[aid % len(AMV_COLORS)]
        ax_trust.plot(ts, scores, label=f"AMV {aid}", color=c, linewidth=2.4, zorder=2)

    # Annotate Trust Release Events
    if trust_release_events:
        rel_drawn = False
        for evt in trust_release_events:
            e_ts = evt.get('timestep', 0)
            e_aid = evt.get('amv_id', -1)
            e_tid = evt.get('task_id', -1)
            e_score = evt.get('trust_score', 0.0)
            c = AMV_COLORS[e_aid % len(AMV_COLORS)]

            label_str = "Task Release Event" if not rel_drawn else None
            ax_trust.axvline(x=e_ts, color='#C62828', linestyle=':', linewidth=1.8,
                             alpha=0.85, label=label_str, zorder=3)
            rel_drawn = True

            ax_trust.scatter(e_ts, e_score, marker='X', color='#D32F2F', s=120,
                             edgecolors='black', linewidths=1.0, zorder=5)
            ax_trust.annotate(
                f"AMV{e_aid} released T{e_tid}\n(Trust={e_score:.2f})",
                xy=(e_ts, e_score),
                xytext=(e_ts + 8, max(0.1, e_score - 0.15)),
                fontsize=7.5, fontweight='bold', color='#B71C1C',
                bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='#D32F2F', alpha=0.9),
                arrowprops=dict(arrowstyle='->', color='#D32F2F', lw=1.2),
                zorder=6
            )

    ax_trust.set_ylabel("Trust Score", fontsize=11, fontweight='bold')
    ax_trust.set_ylim(-0.05, 1.05)
    ax_trust.set_title("Per-AMV Trust Score Timeline & Task Release Verification",
                       fontsize=13, fontweight='bold')
    ax_trust.legend(loc="upper right", fontsize=8, framealpha=0.9)
    ax_trust.grid(True, alpha=0.3)

    # ── BOTTOM: Observed Speed vs Implied Speed ─────────────────────────────
    ax_speed.set_facecolor('#fafafa')

    for aid in amv_ids:
        records = trust_log[aid]
        if not records:
            continue
        ts = [r[0] for r in records]
        speeds = [r[3] for r in records]
        c = AMV_COLORS[aid % len(AMV_COLORS)]
        ax_speed.plot(ts, speeds, label=f"AMV {aid} Speed", color=c, linewidth=1.8, zorder=2)

    ax_speed.set_xlabel("Timestep", fontsize=11, fontweight='bold')
    ax_speed.set_ylabel("Observed Speed (m/s)", fontsize=11, fontweight='bold')
    ax_speed.set_title("Physical Kinematic Speed Verification", fontsize=11, fontweight='bold')
    ax_speed.legend(loc="upper right", fontsize=7.5, ncol=3, framealpha=0.9)
    ax_speed.grid(True, alpha=0.3)

    fig.tight_layout()
    out_path = _get_save_path(filename)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")


# ─── Plot 17: Comprehensive 4-Panel Telemetry Dashboard ──────────────────────────

def plot_telemetry_dashboard(fsm_state_log, fault_log=None, deadlock_log=None, completion_log=None,
                             task_completion_log=None, tasks=None, trust_log=None,
                             trust_release_events=None, fault_events=None,
                             fault_injection_events=None,
                             filename='plot_telemetry_dashboard.png', **kwargs):
    """
    Comprehensive 4-panel dashboard displaying:
      Panel 1: FSM State & Fault State Timeline with Fault Injection Annotations
      Panel 2: Task-to-AMV Completion Attribution Timeline & Gantt
      Panel 3: Per-AMV Trust Score Tracking & Threshold Verification
      Panel 4: Task Completion Attribution Summary Table
    """
    if fault_events is None and fault_injection_events is not None:
        fault_events = fault_injection_events
    if completion_log is None and task_completion_log is not None:
        completion_log = task_completion_log
    if task_completion_log is None and completion_log is not None:
        task_completion_log = completion_log
    if deadlock_log is None:
        deadlock_log = []
    if tasks is None:
        tasks = []
    if trust_log is None:
        trust_log = {}

    fig = plt.figure(figsize=(22, 14))
    gs = fig.add_gridspec(2, 2, hspace=0.28, wspace=0.22)

    ax_fsm = fig.add_subplot(gs[0, 0])
    ax_task_gantt = fig.add_subplot(gs[0, 1])
    ax_trust = fig.add_subplot(gs[1, 0])
    ax_table = fig.add_subplot(gs[1, 1])

    FSM_COLORS = {
        config.FSM_HOMING:     '#90A4AE',
        config.FSM_ASSIGNMENT: '#FFF176',
        config.FSM_REACHING:   '#42A5F5',
        config.FSM_SERVING:    '#66BB6A',
        config.FSM_IDLE:       '#EF9A9A',
        config.FSM_DEADLOCK:   '#AB47BC',
        config.FSM_PATROL:     '#FFD180',
    }

    # ── Panel 1: FSM + Fault Timeline ────────────────────────────────────────
    ax_fsm.set_facecolor('#fafafa')
    amv_ids = sorted(fsm_state_log.keys())
    has_fault_overlay = fault_log is not None and len(fault_log) > 0

    for row_idx, amv_id in enumerate(amv_ids):
        if row_idx % 2 == 0:
            ax_fsm.axhspan(row_idx - 0.45, row_idx + 0.45, color='#f0f4f8', zorder=0)

        records = fsm_state_log[amv_id]
        if records:
            segments = []
            cur_state = records[0][1]
            seg_start = records[0][0]
            for ts, state in records[1:]:
                if state != cur_state:
                    segments.append((seg_start, ts, cur_state))
                    cur_state = state
                    seg_start = ts
            segments.append((seg_start, records[-1][0] + 1, cur_state))

            fsm_y = row_idx + 0.12 if has_fault_overlay else row_idx
            fsm_h = 0.32 if has_fault_overlay else 0.55
            for start, end, state in segments:
                color = FSM_COLORS.get(state, '#95a5a6')
                ax_fsm.barh(fsm_y, end - start, left=start, height=fsm_h,
                            color=color, edgecolor='white', linewidth=0.5, zorder=2)

        if has_fault_overlay and amv_id in fault_log:
            f_records = fault_log[amv_id]
            if f_records:
                f_segments = []
                cur_f = f_records[0][1]
                seg_f_start = f_records[0][0]
                for f_ts, f_state in f_records[1:]:
                    if f_state != cur_f:
                        f_segments.append((seg_f_start, f_ts, cur_f))
                        cur_f = f_state
                        seg_f_start = f_ts
                f_segments.append((seg_f_start, f_records[-1][0] + 1, cur_f))

                fault_y = row_idx - 0.18
                fault_h = 0.22
                for start, end, state in f_segments:
                    f_color = FAULT_COLORS.get(state, '#95a5a6')
                    ax_fsm.barh(fault_y, end - start, left=start, height=fault_h,
                                color=f_color, edgecolor='white', linewidth=0.5, zorder=2)

    # Deadlock & Completion lines on Panel 1
    for evt in deadlock_log:
        ax_fsm.axvline(x=evt['timestep'], color='#E53935', linestyle='--', linewidth=1.0, alpha=0.7, zorder=3)
    for evt in completion_log:
        ax_fsm.axvline(x=evt['timestep'], color='#43A047', linestyle='--', linewidth=1.0, alpha=0.5, zorder=3)

    if fault_events:
        for fe in fault_events:
            ax_fsm.axvline(x=fe.get('timestep', 0), color='#8E24AA', linestyle='-.', linewidth=1.5, alpha=0.85, zorder=4)

    ax_fsm.set_yticks(range(len(amv_ids)))
    ax_fsm.set_yticklabels([f'AMV {i}' for i in amv_ids], fontsize=8.5, fontweight='bold')
    ax_fsm.set_xlabel('Timestep', fontsize=9.5, fontweight='bold')
    ax_fsm.set_title('Panel 1: Per-AMV FSM & Fault State Timeline', fontsize=11, fontweight='bold')
    ax_fsm.grid(axis='x', alpha=0.4)

    # ── Panel 2: Task-to-AMV Completion Mapping ──────────────────────────────
    ax_task_gantt.set_facecolor('#fafafa')
    real_tasks = [t for t in tasks if not getattr(t, 'is_dummy', False)]
    sorted_tasks = sorted(real_tasks, key=lambda x: x.task_id)
    n_tasks = len(sorted_tasks)

    completion_map = {e['task_id']: e for e in task_completion_log}
    for t in real_tasks:
        if t.status == 'completed' and t.task_id not in completion_map:
            completion_map[t.task_id] = {'amv_id': t.assigned_to, 'timestep': config.SIMULATION_TIMESTEPS}

    for idx, t in enumerate(sorted_tasks):
        if idx % 2 == 0:
            ax_task_gantt.axhspan(idx - 0.4, idx + 0.4, color='#f0f4f8', zorder=0)

        tid = t.task_id
        if tid in completion_map and t.status == 'completed':
            c_info = completion_map[tid]
            aid = c_info['amv_id']
            t_comp = c_info['timestep']
            c_color = AMV_COLORS[aid % len(AMV_COLORS)] if aid is not None else '#4CAF50'
            ax_task_gantt.barh(idx, t_comp, left=0, height=0.55, color=c_color,
                               alpha=0.85, edgecolor='white', linewidth=0.8, zorder=2)
            ax_task_gantt.scatter(t_comp, idx, marker='*', s=120, color='#FFD700',
                                  edgecolors='black', linewidths=0.8, zorder=4)
        else:
            ax_task_gantt.barh(idx, 50, left=0, height=0.55, color='#E0E0E0',
                               alpha=0.6, edgecolor='#BDBDBD', linewidth=0.8, zorder=2)

    ax_task_gantt.set_yticks(range(n_tasks))
    ax_task_gantt.set_yticklabels([f"T{t.task_id}" for t in sorted_tasks], fontsize=8, fontweight='bold')
    ax_task_gantt.set_xlabel('Completion Timestep', fontsize=9.5, fontweight='bold')
    ax_task_gantt.set_title('Panel 2: Task Completion Attribution Timeline', fontsize=11, fontweight='bold')
    ax_task_gantt.grid(axis='x', alpha=0.4)

    # ── Panel 3: Trust Score Timeline ────────────────────────────────────────
    ax_trust.set_facecolor('#fafafa')
    ax_trust.axhspan(-0.05, config.TRUST_THRESHOLD, color='#FFEBEE', alpha=0.7, zorder=0)
    ax_trust.axhline(y=config.TRUST_THRESHOLD, color='#D32F2F', linestyle='--', linewidth=1.5,
                     label=f'Threshold ({config.TRUST_THRESHOLD})', zorder=3)

    for aid in amv_ids:
        records = trust_log.get(aid, [])
        if records:
            ts = [r[0] for r in records]
            scores = [r[1] for r in records]
            c = AMV_COLORS[aid % len(AMV_COLORS)]
            ax_trust.plot(ts, scores, label=f"AMV {aid}", color=c, linewidth=2.0, zorder=2)

    if trust_release_events:
        for evt in trust_release_events:
            e_ts = evt.get('timestep', 0)
            e_score = evt.get('trust_score', 0.0)
            ax_trust.scatter(e_ts, e_score, marker='X', color='#D32F2F', s=90,
                             edgecolors='black', linewidths=0.8, zorder=5)

    ax_trust.set_ylabel("Trust Score", fontsize=9.5, fontweight='bold')
    ax_trust.set_xlabel("Timestep", fontsize=9.5, fontweight='bold')
    ax_trust.set_ylim(-0.05, 1.05)
    ax_trust.set_title("Panel 3: Per-AMV Trust Score Tracking", fontsize=11, fontweight='bold')
    ax_trust.legend(loc="upper right", fontsize=7.5, ncol=3, framealpha=0.9)
    ax_trust.grid(True, alpha=0.3)

    # ── Panel 4: Task Completion Table ───────────────────────────────────────
    ax_table.axis('off')
    table_data = []
    cell_colors = []
    table_headers = ["Task ID", "Prio", "Status", "Quality", "AMV", "Done Timestep"]

    for t in sorted_tasks:
        tid = t.task_id
        is_comp = (t.status == 'completed')
        c_info = completion_map.get(tid, {})
        aid = c_info.get('amv_id', t.assigned_to)
        t_comp = c_info.get('timestep', '—') if is_comp else '—'
        status_str = "DONE" if is_comp else t.status.upper()
        amv_str = f"AMV{aid}" if (is_comp and aid is not None) else "—"
        
        q_raw = getattr(t, 'completion_quality', None) if is_comp else None
        if q_raw == 'completed_clean':
            q_str = 'Clean'
            q_col = '#C8E6C9'
        elif q_raw == 'completed_degraded':
            q_str = 'Degraded'
            q_col = '#FFE0B2'
        else:
            q_str = '—'
            q_col = '#F5F5F5'

        table_data.append([f"T{tid}", f"{t.priority_weight:.2f}", status_str, q_str, amv_str, str(t_comp)])
        if is_comp:
            cell_colors.append(['#E8F5E9', '#E8F5E9', '#C8E6C9', q_col, '#E3F2FD', '#E8F5E9'])
        else:
            cell_colors.append(['#FFEBEE', '#FFEBEE', '#FFCDD2', '#F5F5F5', '#F5F5F5', '#F5F5F5'])

    table = ax_table.table(cellText=table_data, colLabels=table_headers,
                           cellColours=cell_colors, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(7.5)
    table.scale(1.0, 1.15)

    for col_idx in range(len(table_headers)):
        cell = table[(0, col_idx)]
        cell.set_facecolor('#1A237E')
        cell.set_text_props(color='white', fontweight='bold')

    ax_table.set_title("Panel 4: Task Completion Attribution Summary", fontsize=11, fontweight='bold', pad=8)

    fig.suptitle('Swarm Telemetry & Verification Dashboard', fontsize=15, fontweight='bold', y=0.99)
    out_path = _get_save_path(filename)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")



