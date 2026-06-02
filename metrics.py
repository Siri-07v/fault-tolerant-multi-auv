"""
metrics.py — 12 evaluation metrics for the AMV swarm simulation.
All functions take only logged data as inputs — no live simulation state.
"""
import numpy as np
import config


# ─── Individual metric functions ────────────────────────────────────────────────

def task_completion_rate(tasks):
    """Fraction of tasks completed out of total tasks."""
    completed = sum(1 for t in tasks if t.status == "completed")
    return completed / max(len(tasks), 1)


def mean_task_completion_time(completion_timestamps):
    """Average timesteps from task arrival (t=0) to completion."""
    if not completion_timestamps:
        return 0.0
    return float(np.mean(list(completion_timestamps.values())))


def system_throughput(tasks, total_timesteps):
    """Tasks completed per timestep."""
    completed = sum(1 for t in tasks if t.status == "completed")
    return completed / max(total_timesteps, 1)


def mean_amv_availability(availability_log):
    """Average availability across all AMVs and all timesteps."""
    all_vals = []
    for amv_id, records in availability_log.items():
        all_vals.extend([r[1] for r in records])
    return float(np.mean(all_vals)) if all_vals else 0.0


def fault_impact_score(fault_log):
    """Fraction of AMV-timesteps in a degraded fault state."""
    total = 0
    degraded = 0
    for amv_id, records in fault_log.items():
        for _, state in records:
            total += 1
            if state != "normal":
                degraded += 1
    return degraded / max(total, 1)


def deadlock_frequency(deadlock_log, total_timesteps):
    """Deadlocks per 100 timesteps."""
    return len(deadlock_log) / max(total_timesteps, 1) * 100.0


def mean_packet_loss_rate(total_sent, total_dropped):
    """Total dropped / total sent."""
    return total_dropped / max(total_sent, 1)


def energy_efficiency(energy_log, tasks_completed_count):
    """Total energy consumed / tasks completed."""
    total_consumed = 0.0
    for amv_id, records in energy_log.items():
        if len(records) >= 2:
            total_consumed += records[0][1] - records[-1][1]
    return total_consumed / max(tasks_completed_count, 1)


def auction_convergence_rate(auction_iterations_log):
    """Average iterations per auction round."""
    if not auction_iterations_log:
        return 0.0
    return float(np.mean(auction_iterations_log))


def connectivity_maintenance_rate(connectivity_log, threshold=None):
    """Fraction of timesteps with algebraic connectivity above threshold."""
    if threshold is None:
        threshold = config.EPSILON_LAMBDA
    if not connectivity_log:
        return 0.0
    above = sum(1 for c in connectivity_log if c >= threshold)
    return above / len(connectivity_log)


def physics_impact_on_faults(physics_log, fault_log):
    """
    Pearson correlation between mean AMV depth and fault escalation events.
    Positive correlation confirms depth-coupled fault model works.
    """
    # Collect mean depth per AMV
    mean_depths = []
    fault_escalations = []
    for amv_id in sorted(physics_log.keys()):
        depths = [r["depth"] for r in physics_log[amv_id]]
        mean_depths.append(float(np.mean(depths)))

        # Count fault escalation events (transitions away from normal)
        records = fault_log.get(amv_id, [])
        escalations = 0
        prev = "normal"
        for _, state in records:
            if state != "normal" and prev == "normal":
                escalations += 1
            prev = state
        fault_escalations.append(escalations)

    if len(mean_depths) < 2:
        return 0.0

    depth_array = np.array(mean_depths)
    fault_array = np.array(fault_escalations, dtype=np.float64)

    if np.std(depth_array) < 1e-6 or np.std(fault_array) < 1e-6:
        return 0.0

    corr = np.corrcoef(depth_array, fault_array)[0, 1]
    return float(corr) if not np.isnan(corr) else 0.0


def thermocline_crossing_penalty(thermocline_messages, total_sent):
    """Fraction of messages subject to thermocline packet loss penalty."""
    return thermocline_messages / max(total_sent, 1)


# ─── Formatted Report ──────────────────────────────────────────────────────────

def print_report(tasks, completion_timestamps, total_timesteps,
                 availability_log, fault_log, deadlock_log,
                 total_sent, total_dropped,
                 energy_log, tasks_completed_count,
                 auction_iterations_log, connectivity_log,
                 physics_log, thermocline_messages,
                 congestion_drops=0):
    """Print all 13 metrics in a clean aligned table."""

    metrics = [
        ("Task Completion Rate",
         f"{task_completion_rate(tasks):.2%}"),
        ("Mean Task Completion Time",
         f"{mean_task_completion_time(completion_timestamps):.1f} timesteps"),
        ("System Throughput",
         f"{system_throughput(tasks, total_timesteps):.4f} tasks/ts"),
        ("Mean AMV Availability",
         f"{mean_amv_availability(availability_log):.3f}"),
        ("Fault Impact Score",
         f"{fault_impact_score(fault_log):.2%}"),
        ("Deadlock Frequency",
         f"{deadlock_frequency(deadlock_log, total_timesteps):.2f} per 100 ts"),
        ("Mean Packet Loss Rate",
         f"{mean_packet_loss_rate(total_sent, total_dropped):.2%}"),
        ("Energy Efficiency",
         f"{energy_efficiency(energy_log, tasks_completed_count):.2f} energy/task"),
        ("Auction Convergence Rate",
         f"{auction_convergence_rate(auction_iterations_log):.2f} iters/round"),
        ("Connectivity Maintenance",
         f"{connectivity_maintenance_rate(connectivity_log):.2%}"),
        ("Physics Impact on Faults",
         f"{physics_impact_on_faults(physics_log, fault_log):+.3f} (correlation)"),
        ("Thermocline Crossing Penalty",
         f"{thermocline_crossing_penalty(thermocline_messages, total_sent):.2%}"),
        ("Congestion Drop Rate",
         f"{congestion_drops / max(total_sent, 1):.2%} ({congestion_drops} drops)"),
    ]

    width = max(len(m[0]) for m in metrics)
    print(f"\n{'='*60}")
    print("SIMULATION METRICS REPORT")
    print(f"{'='*60}")
    for name, value in metrics:
        print(f"  {name:<{width}}  │  {value}")
    print(f"{'='*60}\n")
