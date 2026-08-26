"""
main.py — Simulation loop with Miele et al. distributed auction, EDMC, and FSM.
Run train.py first to produce fault_classifier_best.pt and scaler.pkl.
"""
import os
import sys
# Reconfigure stdout/stderr to UTF-8 to prevent charmap encoding crashes on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import json
import pickle
import random
import time
from collections import defaultdict

import numpy as np
import pandas as pd
import torch

import config
from model import FaultClassifier
from simulation import AMV, Task
from comms import CommsMesh
from consensus import MieleConsensus
from physics import OceanEnvironment
from visualize import (
    plot_mission_space,
    plot_task_coverage,
    plot_availability,
    plot_fault_gantt,
    plot_comm_graph_snapshots,
    plot_energy,
    plot_total_benefit,
    plot_edmc_proposals,
    plot_3d_mission_space,
    plot_physics_dashboard,
    plot_mesh_animation,
    plot_fsm_timeline,
    plot_fsm_diagram,
    plot_confidence_histogram,
)
import metrics as sim_metrics
from symbolic_rules import SymbolicRuleEngine, log_verdict


def _gather_test_csvs():
    """Collect CSV file paths from all fault folders for sensor replay."""
    csv_paths = []
    for folder_name in config.FAULT_LABEL_MAP:
        folder = os.path.join(config.DATASET_PATH, folder_name)
        if not os.path.isdir(folder):
            continue
        for f in sorted(os.listdir(folder)):
            if f.endswith(".csv"):
                csv_paths.append(os.path.join(folder, f))
    return csv_paths


def _build_csv_pool():
    """Build a dict mapping fault class label → [csv_path, ...]."""
    pool = {}
    for folder_name, (label, _idx) in config.FAULT_LABEL_MAP.items():
        folder = os.path.join(config.DATASET_PATH, folder_name)
        if not os.path.isdir(folder):
            continue
        csvs = [os.path.join(folder, f)
                for f in sorted(os.listdir(folder)) if f.endswith(".csv")]
        if csvs:
            pool[label] = csvs
    return pool


def main():
    if config.FIXED_SEED is not None:
        seed = config.FIXED_SEED
    else:
        seed = int(time.time()) % 100000
    random.seed(seed)
    np.random.seed(seed)
    print(f"Random seed this run: {seed}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # ── Load trained model & scaler ─────────────────────────────────────────
    if not os.path.exists(config.MODEL_PATH):
        print(f"ERROR: Model checkpoint not found at {config.MODEL_PATH}")
        print("Run  python train.py  first.")
        sys.exit(1)
    if not os.path.exists(config.SCALER_PATH):
        print(f"ERROR: Scaler not found at {config.SCALER_PATH}")
        sys.exit(1)

    classifier = FaultClassifier().to(device)
    classifier.load_state_dict(torch.load(config.MODEL_PATH, map_location=device))
    classifier.eval()

    with open(config.SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)

    print("Loaded classifier and scaler.\n")

    # ── Gather CSVs for sensor replay ───────────────────────────────────────
    replay_csvs = _gather_test_csvs()
    if not replay_csvs:
        print("ERROR: No CSV files found for sensor replay.")
        sys.exit(1)

    # ── Initialise Tasks ────────────────────────────────────────────────────
    tasks = []
    for i in range(config.N_TASKS):
        pos = (
            random.uniform(50, config.MISSION_SPACE - 50),
            random.uniform(50, config.MISSION_SPACE - 50),
        )
        prio = random.uniform(config.PRIORITY_WEIGHT_MIN, config.PRIORITY_WEIGHT_MAX)
        tasks.append(Task(task_id=i, position=pos, priority_weight=prio,
                          arrival_order=i))
    print(f"Created {len(tasks)} tasks")

    # ── Ocean environment ─────────────────────────────────────────────────────
    ocean_env = OceanEnvironment()
    print("Initialised ocean environment.")

    csv_pool = _build_csv_pool()
    print(f"Built CSV pool: {', '.join(f'{k}({len(v)})' for k, v in csv_pool.items())}")

    # ── Initialise AMVs ─────────────────────────────────────────────────────
    amvs = []
    for i in range(config.N_AMVS):
        pos = (
            random.uniform(50, config.MISSION_SPACE - 50),
            random.uniform(50, config.MISSION_SPACE - 50),
        )
        energy = random.uniform(config.ENERGY_INIT_MIN, config.ENERGY_INIT_MAX)
        csv_path = random.choice(replay_csvs)
        amvs.append(AMV(amv_id=i, position=pos, energy=energy,
                        replay_csv_path=csv_path, ocean_env=ocean_env,
                        csv_pool=csv_pool))
    print(f"Created {len(amvs)} AMVs\n")

    # Save initial positions for before/after plot
    initial_positions = {a.amv_id: a.position.copy() for a in amvs}

    # ── Comms & consensus ───────────────────────────────────────────────────
    amv_positions = {a.amv_id: tuple(a.position) for a in amvs}
    amv_depths = {a.amv_id: a.depth for a in amvs}
    comms = CommsMesh(amv_positions, amv_depths=amv_depths, ocean_env=ocean_env)
    deadlock_events = []  # shared list — same object used by consensus and viz
    if config.ALLOCATOR_MODE in ("auction", "vanilla_auction"):
        consensus = MieleConsensus(n_amvs=config.N_AMVS, n_tasks=config.N_TASKS,
                                   deadlock_events=deadlock_events)
    elif config.ALLOCATOR_MODE == "cbba":
        from cbba import CBBAAllocator
        consensus = CBBAAllocator(n_amvs=config.N_AMVS, n_tasks=config.N_TASKS,
                                  deadlock_events=deadlock_events)

    # ── Live 3D Visualization ─────────────────────────────────────────────────
    live_viz = None
    if config.LIVE_VIZ_ENABLED:
        from live3d import LiveSimulation3D
        live_viz = LiveSimulation3D()
        print("Live 3D visualization window opened.")

    # ── Initial FSM: Homing → Assignment → first auction ────────────────────
    for amv in amvs:
        amv.compute_availability()
        amv.enter_assignment()  # Homing → Assignment on first task arrival

    consensus.run_auction_round(amvs, tasks, comms, current_timestep=0)
    print("Initial auction complete.")
    for a in amvs:
        tid = a.assigned_task.task_id if a.assigned_task else None
        print(f"  AMV {a.amv_id} [FSM={a.fsm_state}] → Task {tid}")

    # ── Logging structures ──────────────────────────────────────────────────
    log_rows = []
    telemetry_log = []
    availability_log = defaultdict(list)
    energy_log = defaultdict(list)
    fault_log = defaultdict(list)
    graph_snapshots = {}
    energy_snapshots = {}       # {ts: {amv_id: energy}}
    proposal_log = defaultdict(list)  # {amv_id: [(ts, m_p_i)]}
    mt_log = []                 # [(ts, mt)]

    # Fix 4: benefit snapshot — hold value constant between auctions
    last_auction_benefit = consensus.compute_total_benefit(amvs, tasks)
    benefit_snapshot_log = []   # [(ts, held_benefit)]

    # Fix 6: trajectory log — per-AMV position at every timestep
    trajectory_log = {i: [] for i in range(config.N_AMVS)}
    # Record initial positions
    for amv in amvs:
        trajectory_log[amv.amv_id].append((amv.position[0], amv.position[1]))

    # Fix A: per-AMV reallocation log for energy plot markers
    reallocation_events_by_amv = {i: [] for i in range(config.N_AMVS)}

    # Fix B: FSM deadlock entry events for energy plot
    fsm_deadlock_events = {i: [] for i in range(config.N_AMVS)}
    prev_fsm_states = {i: None for i in range(config.N_AMVS)}

    # Capture initial snapshot
    graph_snapshots[0] = comms.get_graph_snapshot()
    energy_snapshots[0] = {a.amv_id: a.energy for a in amvs}

    # Rolling snapshots for every timestep (used to pick dynamic start/mid/end)
    all_graph_snapshots = {0: graph_snapshots[0]}
    all_energy_snapshots = {0: energy_snapshots[0]}

    # Physics logging
    physics_log = {i: [] for i in range(config.N_AMVS)}
    completion_timestamps = {}          # {task_id: timestep}
    connectivity_log = []               # [lambda_2 per timestep]
    csv_switch_log = []                 # R4F4: CSV class switch events

    # New visualisation logs
    mesh_animation_log = []               # snapshot every 10 timesteps
    fsm_state_log = defaultdict(list)      # {amv_id: [(t, fsm_state), ...]}

    # Fix 3: idle counter — force patrol for stuck AMVs
    amv_idle_counter = {i: 0 for i in range(config.N_AMVS)}

    # ── Symbolic Rule Engine ────────────────────────────────────────────────
    rule_engine = SymbolicRuleEngine()
    comms.rule_engine = rule_engine
    stalled_amv_timesteps = 0
    task_active_delay = {t.task_id: 0 for t in tasks}
    amv_speed_caps = {i: 5.0 for i in range(config.N_AMVS)}  # per-AMV speed cap
    deadlock_timeout_fires = 0

    # ── CNN Confidence Logging ─────────────────────────────────────────────
    confidence_log = []  # [{timestep, amv_id, max_prob, class}, ...]

    # ── Misclassification tracking ──────────────────────────────────────────
    misclass_override_count = 0
    misclass_tasks_assigned_while_bad = 0
    misclass_energy_floor_catches = 0

    # ── Stress scenario state ──────────────────────────────────────────────
    stress_fired = False
    comm_blackout_active = False

    # Record initial telemetry at t=0
    pkt_0 = comms.log_packet_stats()
    telemetry_log.append({
        "timestep": 0,
        "packet_loss_rate": float(pkt_0["drop_rate"]),
        "amvs": [
            {
                "amv_id": amv.amv_id,
                "position": [float(amv.position[0]), float(amv.position[1]), float(amv.depth)],
                "fsm_state": amv.fsm_state,
                "assigned_task_id": amv.assigned_task.task_id if amv.assigned_task is not None else None,
                "energy": float(amv.energy)
            }
            for amv in amvs
        ]
    })

    # ── Simulation loop ─────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"Running simulation for {config.SIMULATION_TIMESTEPS} timesteps...")
    print(f"{'='*60}\n")
    for t in range(1, config.SIMULATION_TIMESTEPS + 1):
        realloc_events_this_step = 0
        auction_ran_this_step = False

        # Process delivered messages at start of step (strictly comms-gated deconfliction & recovery)
        delivered_messages = comms.deliver_messages(t)
        
        # Gossip-style retransmission of pending deadlock alerts
        if config.ALLOCATOR_MODE == "auction":
            consensus.process_pending_alerts(comms, t)
        
        # 1. Process outbid messages
        for amv in amvs:
            payloads = delivered_messages.get(amv.amv_id, [])
            for payload in payloads:
                if payload.get("type") == "outbid":
                    tid = payload["task_id"]
                    if amv.assigned_task is not None and amv.assigned_task.task_id == tid:
                        if config.ALLOCATOR_MODE == "vanilla_auction" and getattr(amv, 'task_assigned_duration', 0) > 30:
                            continue
                        amv.assigned_task.status = "unassigned"
                        amv.assigned_task.assigned_to = None
                        amv.assigned_task = None
                        amv.enter_idle()
                        print(f"  [OUTBID MESSAGE] t={t}: AMV{amv.amv_id} released T{tid} due to outbid from AMV{payload['winner_id']}")

        # 2. Process deadlock alerts
        deadlock_alert_recipients = set()
        for amv_id, payloads in delivered_messages.items():
            for payload in payloads:
                if payload.get("type") == "deadlock_alert":
                    deadlock_alert_recipients.add(amv_id)

        if deadlock_alert_recipients and config.ALLOCATOR_MODE == "auction":
            consensus.mt = max(0, consensus.mt - 1)
            paused_ids = consensus.run_pausing_algorithm(amvs, tasks, comms, t)
            for amv_id in deadlock_alert_recipients:
                if amv_id in paused_ids:
                    continue
                amv = next((a for a in amvs if a.amv_id == amv_id), None)
                if amv is not None and amv.fsm_state in (config.FSM_REACHING, config.FSM_DEADLOCK):
                    if amv.assigned_task is not None:
                        amv.assigned_task.status = "unassigned"
                        amv.assigned_task.assigned_to = None
                        amv.assigned_task = None
                    amv.enter_assignment()
                    print(f"  [DEADLOCK RESET] t={t}: AMV{amv.amv_id} reset to Assignment due to deadlock alert")

        # Deadlock timeout fallback and tick tracking
        if config.ALLOCATOR_MODE == "auction":
            for amv in amvs:
                if amv.fsm_state == config.FSM_DEADLOCK:
                    amv.deadlock_ticks += 1
                    if amv.deadlock_ticks > config.DEADLOCK_TIMEOUT:  # Parameterized timeout
                        deadlock_timeout_fires += 1
                        if amv.assigned_task is not None:
                            amv.assigned_task.status = "unassigned"
                            amv.assigned_task.assigned_to = None
                            amv.assigned_task = None
                        amv.enter_assignment()
                        amv.deadlock_ticks = 0
                        print(f"  [DEADLOCK TIMEOUT FALLBACK] t={t}: AMV{amv.amv_id} unilaterally broke deadlock after {config.DEADLOCK_TIMEOUT} ticks")
                else:
                    amv.deadlock_ticks = 0

        # Update task assignment duration and release completed tasks for vanilla_auction/cbba baselines
        for amv in amvs:
            if amv.assigned_task is not None:
                amv.task_assigned_duration = getattr(amv, 'task_assigned_duration', 0) + 1
            else:
                amv.task_assigned_duration = 0
            
            if config.ALLOCATOR_MODE in ("auction", "vanilla_auction", "cbba"):
                if amv.assigned_task is not None and amv.assigned_task.status == "completed":
                    amv.assigned_task = None
                    amv.enter_assignment()

        # 1 ── Push sensor readings & increment task waiting times
        for amv in amvs:
            amv.push_sensor_reading()
        for task in tasks:
            task.increment_waiting()

        # 1b — Depth-dependent hotel load for all AMVs (onboard systems)
        for amv in amvs:
            hotel_load = config.IDLE_ENERGY_DRAIN * (1.0 + amv.depth / config.DEPTH_MAX)
            amv.energy = max(0.0, amv.energy - hotel_load)

        # 2 — Move toward assigned tasks (physics-aware)
        for amv in amvs:
            # Bug 1 Fix: Record pre-move position
            old_pos = amv.position.copy()
            amv.move_toward_task(current_timestep=t)

            # Measure displacement and clamp to speed cap if necessary
            cap = amv_speed_caps.get(amv.amv_id, 5.0)
            if cap < 5.0:
                displacement = amv.position - old_pos
                dist_moved = np.linalg.norm(displacement)
                if dist_moved > cap and dist_moved > 0.001:
                    # Pull back along the vector of travel to match the cap exactly
                    direction = displacement / dist_moved
                    amv.position = old_pos + (direction * cap)
                    # Note: We do not modify depth, estimated_position, or FSM state

        # 3 — Check if Reaching AMVs have arrived → enter Serving
        for amv in amvs:
            amv.check_task_reached()

        # 4 — Tick Serving AMVs (dwell timer) → check completion
        completions_this_step = []
        for amv in amvs:
            if amv.tick_serving():
                # Task just completed
                completions_this_step.append(amv)

        for amv in completions_this_step:
            # Find which task was completed (last in list)
            completed_tid = amv.tasks_completed[-1] if amv.tasks_completed else None
            if completed_tid is not None:
                consensus.handle_task_completion(
                    amvs, tasks, comms, t,
                    completed_task_id=completed_tid,
                    completing_amv_id=amv.amv_id,
                )
                auction_ran_this_step = True

        # 4b — AMVs that just went Idle with no remaining tasks → Patrol
        for amv in amvs:
            if getattr(amv, 'paused_until_timestep', 0) > t:
                continue
            if amv.fsm_state == config.FSM_IDLE and amv.assigned_task is None:
                amv.enter_patrol(all_tasks=tasks)

        # 4b2 — Dynamic task respawn when all tasks complete
        if (config.DYNAMIC_TASK_RESPAWN and
                all(tk.status == 'completed' for tk in tasks if not tk.is_dummy)):
            print(f"  [RESPAWN] All tasks completed at t={t}. "
                  f"Spawning {config.N_RESPAWN_TASKS} new tasks.")
            for k in range(config.N_RESPAWN_TASKS):
                new_id = max(tk.task_id for tk in tasks) + 1 + k
                new_pos = [random.uniform(50, 950), random.uniform(50, 950)]
                new_task = Task(task_id=new_id, position=new_pos,
                               priority_weight=random.uniform(0.5, 1.0),
                               arrival_order=new_id)
                tasks.append(new_task)
            consensus.mt = min(len(amvs), config.N_RESPAWN_TASKS)
            consensus.run_auction_round(amvs, tasks, comms, current_timestep=t)
            for amv in amvs:
                if (amv.assigned_task is not None
                        and not amv.assigned_task.is_dummy
                        and amv.fsm_state == config.FSM_ASSIGNMENT):
                    amv.enter_reaching()

        # 4c — Forced patrol for stuck AMVs (idle/assignment >8 steps)
        for amv in amvs:
            if amv.fsm_state in (config.FSM_IDLE, config.FSM_ASSIGNMENT) and amv.assigned_task is None:
                amv_idle_counter[amv.amv_id] += 1
            else:
                amv_idle_counter[amv.amv_id] = 0

            if amv_idle_counter[amv.amv_id] > 8:
                amv.enter_patrol(all_tasks=tasks)
                amv_idle_counter[amv.amv_id] = 0

        # 5 — Deliver queued messages
        comms.deliver_messages(t)

        # 6 — Every FAULT_UPDATE_INTERVAL: fault detection, availability, graph rebuild
        if t % config.FAULT_UPDATE_INTERVAL == 0:
            for amv in amvs:
                if config.STRESS_SCENARIO == 'mass_fault' and t >= config.STRESS_START_TIMESTEP and amv.amv_id in (0, 1, 2):
                    amv.fault_state = 'actuator_degraded_severe'
                    amv.compute_availability()
                else:
                    amv.update_fault_state(classifier, scaler, device)

                # ── Misclassification injection ────────────────────────────
                if (config.INJECT_MISCLASSIFICATION
                        and amv.amv_id == config.MISCLASSIFICATION_TARGET_AMV
                        and amv._current_csv_class == 'actuator_degraded_severe'):
                    amv.fault_state = 'normal'
                    misclass_override_count += 1
                    print(f"  [MISCLASSIFY] t={t} AMV{amv.amv_id} "
                          f"true=actuator_degraded_severe → overridden to normal")

                # ── Monkey-patch CNN softmax probabilities for Rule 4 ──────
                if len(amv.sensor_buffer) >= config.WINDOW_SIZE:
                    _window = np.array(list(amv.sensor_buffer), dtype=np.float32)
                    _window = (_window - scaler["mean"]) / scaler["std"]
                    _x = torch.from_numpy(_window).permute(1, 0).unsqueeze(0).to(device)
                    with torch.no_grad():
                        _logits = classifier(_x)
                        _probs = torch.softmax(_logits, dim=1).squeeze().detach().cpu().numpy()
                    amv._last_fault_probs = _probs

                    # ── CNN Confidence logging ─────────────────────────────
                    max_prob = float(np.max(_probs))
                    classified_class = config.INDEX_TO_LABEL[int(np.argmax(_probs))]
                    confidence_log.append({
                        'timestep': t,
                        'amv_id': amv.amv_id,
                        'max_prob': max_prob,
                        'class': classified_class,
                    })

                amv.compute_availability()
                amv.maybe_switch_csv(t, csv_switch_log=csv_switch_log)

                # ── Symbolic: post-fault evaluation (Rules 1 & 2) ──────────
                post_verdicts = rule_engine.evaluate_post_fault(amv)
                for v in post_verdicts:
                    log_verdict(v, t, amv.amv_id)
                if config.ALLOCATOR_MODE != "vanilla_auction":
                    amv_speed_caps[amv.amv_id] = rule_engine.get_speed_cap(amv)
                else:
                    amv_speed_caps[amv.amv_id] = 5.0

            # ── Symbolic: fleet-wide audit (Rules 7 & 8) ──────────────────
            fleet_verdicts = rule_engine.evaluate_fleet(amvs)
            for v in fleet_verdicts:
                log_verdict(v, t, -1)

            amv_positions = {a.amv_id: tuple(a.position) for a in amvs}
            amv_depths = {a.amv_id: a.depth for a in amvs}
            comms.rebuild_graph(amv_positions, amv_depths)

            # Apply comm_blackout override immediately if active
            if config.STRESS_SCENARIO == 'comm_blackout' and config.STRESS_START_TIMESTEP <= t <= config.STRESS_END_TIMESTEP:
                for u, v in comms.graph.edges():
                    comms.graph.edges[u, v]['packet_loss_prob'] = 0.90
                    comms.graph.edges[u, v]['weight'] = 0.10

            # Check local deadlock (fault-based) for Reaching AMVs
            for amv in amvs:
                if amv.check_local_deadlock():
                    pass  # state transitions handled inside

            # Run EDMC deadlock detection
            if config.ALLOCATOR_MODE == "auction":
                # Check for confirmed-lost vehicles
                lost_amv_ids = {a.amv_id for a in amvs if a.energy <= 0.0}
                lost_needs_realloc = False
                if lost_amv_ids:
                    # Clear prices of the tasks held by lost vehicles and trigger global alert immediately (fast path)
                    for amv in amvs:
                        if amv.energy <= 0.0 and amv.amv_id not in consensus.handled_lost_amvs:
                            consensus.handled_lost_amvs.add(amv.amv_id)
                            curr_assign = consensus.local_assignments.get(amv.amv_id)
                            if curr_assign is not None:
                                tid = curr_assign[0]
                                for aid in consensus.local_prices:
                                    if tid in consensus.local_prices[aid]:
                                        del consensus.local_prices[aid][tid]
                                consensus.local_assignments[amv.amv_id] = None
                                lost_needs_realloc = True
                                print(f"  [FAST PATH] t={t}: Cleared local prices for T{tid} previously held by lost AMV{amv.amv_id}")
                
                alerted_amvs = []
                if lost_needs_realloc:
                    global_deadlock = True
                    alerted_amvs = [a.amv_id for a in amvs if a.energy > 0.0]
                    print(f"  [FAST PATH] t={t}: Confirmed-lost AMV detected. Skipping EDMC and triggering deadlock alert.")
                else:
                    global_deadlock, alerted_amvs = consensus.run_edmc(amvs, comms, t)
                
                if global_deadlock:
                    consensus.handle_global_deadlock(amvs, tasks, comms, t)
                    auction_ran_this_step = True
                
                # Process the merged alerts immediately at the end of the step!
                if alerted_amvs:
                    paused_ids = consensus.run_pausing_algorithm(amvs, tasks, comms, t)
                    for amv_id in alerted_amvs:
                        if amv_id in paused_ids:
                            continue
                        amv = next((a for a in amvs if a.amv_id == amv_id), None)
                        if amv is not None and amv.fsm_state in (config.FSM_REACHING, config.FSM_DEADLOCK):
                            if amv.assigned_task is not None:
                                amv.assigned_task.status = "unassigned"
                                amv.assigned_task.assigned_to = None
                                amv.assigned_task = None
                            amv.enter_assignment()
                            print(f"  [IMMEDIATE RESET] t={t}: AMV{amv.amv_id} reset to Assignment due to merged alert")
            elif config.ALLOCATOR_MODE == "cbba":
                consensus.run_auction_round(amvs, tasks, comms, t)
                auction_ran_this_step = True

        # ── Stress scenario injection ──────────────────────────────────────
        if config.STRESS_SCENARIO == 'amv_loss' and t == config.STRESS_START_TIMESTEP:
            print(f"  [STRESS] AMV loss injected at t={t}")
            for amv in amvs:
                if amv.amv_id in (0, 1):
                    before_energy = amv.energy
                    amv.energy = 0.0
                    if amv.assigned_task is not None:
                        amv.assigned_task.status = 'unassigned'
                        amv.assigned_task.assigned_to = None
                        amv.assigned_task = None
                    amv.enter_idle()
                    print(f"  [ASSERT STRESS] t={t}: AMV{amv.amv_id} energy overridden: before={before_energy:.1f}% -> after=0.0%")
            stress_fired = True

        if config.STRESS_SCENARIO == 'comm_blackout':
            if config.STRESS_START_TIMESTEP <= t <= config.STRESS_END_TIMESTEP:
                # Override all edge packet loss to 0.90
                for u, v in comms.graph.edges():
                    before_plp = comms.graph.edges[u, v]['packet_loss_prob']
                    comms.graph.edges[u, v]['packet_loss_prob'] = 0.90
                    comms.graph.edges[u, v]['weight'] = 0.10
                    if t == config.STRESS_START_TIMESTEP:
                        print(f"  [DEBUG OVERRIDE] t={t}: link ({u}, {v}) packet_loss_prob overridden: before={before_plp:.4f} -> after={comms.graph.edges[u, v]['packet_loss_prob']:.2f}")
                if t % 50 == 0 or t == config.STRESS_START_TIMESTEP:
                    print(f"  [STRESS] Communication blackout active t={t}")
                comm_blackout_active = True
                stress_fired = True
            elif comm_blackout_active and t == config.STRESS_END_TIMESTEP + 1:
                # Restore normal packet loss by rebuilding graph
                amv_positions = {a.amv_id: tuple(a.position) for a in amvs}
                amv_depths = {a.amv_id: a.depth for a in amvs}
                comms.rebuild_graph(amv_positions, amv_depths)
                comm_blackout_active = False
                print(f"  [STRESS] Communication blackout ended at t={t}")

        if config.STRESS_SCENARIO == 'mass_fault' and t == config.STRESS_START_TIMESTEP:
            print(f"  [STRESS] Mass fault injected at t={t}")
            for amv in amvs:
                if amv.amv_id in (0, 1, 2):
                    before_state = amv.fault_state
                    amv.fault_state = 'actuator_degraded_severe'
                    amv.compute_availability()
                    print(f"  [ASSERT STRESS] t={t}: AMV{amv.amv_id} fault state overridden: before={before_state} -> after={amv.fault_state}")
            stress_fired = True

        # ── Track misclassification stats ──────────────────────────────────
        if config.INJECT_MISCLASSIFICATION:
            target_amv = next((a for a in amvs
                              if a.amv_id == config.MISCLASSIFICATION_TARGET_AMV), None)
            if (target_amv is not None
                    and target_amv._current_csv_class == 'actuator_degraded_severe'
                    and target_amv.fault_state == 'normal'
                    and target_amv.assigned_task is not None):
                misclass_tasks_assigned_while_bad += 1

        # 7 — Check reallocation (fault/energy)
        for amv in amvs:
            if amv.should_reallocate() and amv.assigned_task is not None:
                reason = "fault" if amv.fault_state in (
                    "actuator_degraded_severe", "sensor_failure") else "energy"
                consensus.trigger_reallocation(amv, tasks, t, reason=reason)
                realloc_events_this_step += 1
                # Fix A: record per-AMV reallocation
                reallocation_events_by_amv[amv.amv_id].append(t)

        if realloc_events_this_step > 0:
            for amv in amvs:
                amv.compute_availability()
            
            # ── Symbolic: Pre-auction screening (Bug 3 Part A) ──────────
            blocked_pairs = {a.amv_id: set() for a in amvs}
            if config.ALLOCATOR_MODE != "vanilla_auction" and not getattr(rule_engine, "fleet_audit_strikes", 0) >= 3:  # Only screen if not escalated
                unassigned_tasks = [tk for tk in tasks if tk.status == 'unassigned' and not tk.is_dummy]
                active_tasks = len([tk for tk in tasks if tk.status == 'active'])
                remaining_tasks = len(unassigned_tasks) + active_tasks
                for amv in amvs:
                    if getattr(amv, "fsm_state", "") in (config.FSM_IDLE, config.FSM_ASSIGNMENT, config.FSM_PATROL):
                        for task in unassigned_tasks:
                            if not rule_engine.is_assignment_safe(amv, task, amvs, remaining_tasks):
                                blocked_pairs[amv.amv_id].add(task.task_id)
                                print(f"  [SCREENED] AMV{amv.amv_id} blocked from T{task.task_id} pre-auction")

            consensus.run_auction_round(amvs, tasks, comms, current_timestep=t)

            # ── Symbolic: Post-auction safety net (Bug 3 Part B) ─────────
            for amv in amvs:
                if amv.assigned_task is not None and getattr(amv, "fsm_state", "") == config.FSM_REACHING:
                    # AMV just got a task, check if it was blocked
                    # Note: We check REACHING here because later the block forces REACHING. Wait, the auction assigns tasks but doesn't change FSM state automatically here. Let's just check if it has a task.
                    pass
                if amv.assigned_task is not None and amv.assigned_task.task_id in blocked_pairs[amv.amv_id]:
                    # Release the task
                    released_tid = amv.assigned_task.task_id
                    amv.assigned_task.status = 'unassigned'
                    amv.assigned_task.assigned_to = None
                    amv.assigned_task = None
                    amv.enter_assignment()
                    print(f"  [UNASSIGNED] AMV{amv.amv_id} stripped of T{released_tid} post-auction")

            auction_ran_this_step = True

        # Fix 4 — Keep mt aligned with remaining tasks
        unassigned = len([tk for tk in tasks
                          if tk.status == 'unassigned' and not tk.is_dummy])
        active_tasks = len([tk for tk in tasks if tk.status == 'active'])
        remaining = unassigned + active_tasks
        if remaining > 0:
            healthy_count = len([a for a in amvs if a.energy > 0])
            consensus.mt = max(consensus.mt, min(remaining, healthy_count))

        # Periodic auction every 5 timesteps — ensures idle AMVs get assignments
        if t % 5 == 0 and not auction_ran_this_step:
            # Fix 2 — Wake all idle and patrol AMVs before auction
            for amv in amvs:
                if getattr(amv, 'paused_until_timestep', 0) > t:
                    continue
                if (amv.assigned_task is None and
                        amv.fsm_state in (config.FSM_IDLE,
                                          config.FSM_PATROL,
                                          config.FSM_ASSIGNMENT)):
                    amv.enter_assignment()

            # ── Symbolic: Pre-auction screening (Bug 3 Part A) ──────────
            blocked_pairs = {a.amv_id: set() for a in amvs}
            if config.ALLOCATOR_MODE != "vanilla_auction" and not getattr(rule_engine, "fleet_audit_strikes", 0) >= 3:
                unassigned_tasks = [tk for tk in tasks if tk.status == 'unassigned' and not tk.is_dummy]
                active_tasks = len([tk for tk in tasks if tk.status == 'active'])
                remaining_tasks = len(unassigned_tasks) + active_tasks
                for amv in amvs:
                    if getattr(amv, "fsm_state", "") in (config.FSM_IDLE, config.FSM_ASSIGNMENT, config.FSM_PATROL):
                        for task in unassigned_tasks:
                            if not rule_engine.is_assignment_safe(amv, task, amvs, remaining_tasks):
                                blocked_pairs[amv.amv_id].add(task.task_id)
                                print(f"  [SCREENED] AMV{amv.amv_id} blocked from T{task.task_id} pre-auction")

            consensus.run_auction_round(amvs, tasks, comms, current_timestep=t)

            # ── Symbolic: Post-auction safety net (Bug 3 Part B) ─────────
            for amv in amvs:
                if amv.assigned_task is not None and amv.assigned_task.task_id in blocked_pairs[amv.amv_id]:
                    # Release the task
                    released_tid = amv.assigned_task.task_id
                    amv.assigned_task.status = 'unassigned'
                    amv.assigned_task.assigned_to = None
                    amv.assigned_task = None
                    amv.enter_assignment()  # Return to assignment-seeking state
                    print(f"  [UNASSIGNED] AMV{amv.amv_id} stripped of T{released_tid} post-auction")

            # Force reaching for any AMV that just got assigned
            for amv in amvs:
                if (amv.assigned_task is not None
                        and not amv.assigned_task.is_dummy
                        and amv.fsm_state == config.FSM_ASSIGNMENT):
                    amv.enter_reaching()
            auction_ran_this_step = True

        # Fix 3 — Hard force-assignment safety net every 10 timesteps
        if t % 10 == 0:
            unassigned_tasks = [tk for tk in tasks
                                if tk.status == 'unassigned' and not tk.is_dummy]
            for amv in amvs:
                if (amv.assigned_task is None
                        and amv.fsm_state in (config.FSM_IDLE, config.FSM_ASSIGNMENT,
                                              config.FSM_PATROL)
                        and amv.availability > config.BID_AVAILABILITY_THRESHOLD
                        and getattr(amv, 'trust_score', 1.0) >= config.TRUST_THRESHOLD
                        and amv.energy > config.ENERGY_REALLOC_THRESHOLD
                        and unassigned_tasks):
                    nearest = min(unassigned_tasks,
                                  key=lambda tk: np.linalg.norm(
                                      amv.position - tk.position))

                    # ── Symbolic: safety gate before force-assignment ──────
                    # Need remaining tasks count for energy floor logic
                    active_for_force = len([tk for tk in tasks if tk.status == 'active'])
                    remain_for_force = len(unassigned_tasks) + active_for_force

                    if config.ALLOCATOR_MODE != "vanilla_auction" and not rule_engine.is_assignment_safe(amv, nearest, amvs, remain_for_force):
                        print(f"  [VETOED] AMV{amv.amv_id} ✗ T{nearest.task_id} "
                              f"(symbolic rule vetoed assignment)")
                        continue

                    nearest.status = 'active'
                    nearest.assigned_to = amv.amv_id
                    amv.assigned_task = nearest
                    amv.enter_reaching()
                    unassigned_tasks.remove(nearest)
                    print(f"  [FORCED] AMV{amv.amv_id} → T{nearest.task_id} "
                          f"(energy={amv.energy:.0f}% avail={amv.availability:.2f})")

            # 3b — Mesh animation snapshot every 10 timesteps
            mesh_animation_log.append({
                'timestep': t,
                'amv_positions': {a.amv_id: a.position.copy() for a in amvs},
                'amv_states': {a.amv_id: a.fsm_state for a in amvs},
                'amv_depths': {a.amv_id: a.depth for a in amvs},
                'task_statuses': {tk.task_id: (tk.position.copy(), tk.status)
                                  for tk in tasks if not tk.is_dummy},
                'edges': [(u, v, data.get('packet_loss_prob', 0.5))
                          for u, v, data in comms.graph.edges(data=True)],
            })

        # 8 — Deadlock AMVs → back to Assignment on reassignment trigger
        for amv in amvs:
            if amv.fsm_state == config.FSM_DEADLOCK and amv.assigned_task is None:
                amv.enter_assignment()
                
                # ── Symbolic: Pre-auction screening (Bug 3) ──────────
                blocked_pairs = {a.amv_id: set() for a in amvs}
                if not getattr(rule_engine, "fleet_audit_strikes", 0) >= 3:
                    unassigned_tasks = [tk for tk in tasks if tk.status == 'unassigned' and not tk.is_dummy]
                    active_tasks = len([tk for tk in tasks if tk.status == 'active'])
                    remaining_tasks = len(unassigned_tasks) + active_tasks
                    for a in amvs:
                        if getattr(a, "fsm_state", "") in (config.FSM_IDLE, config.FSM_ASSIGNMENT, config.FSM_PATROL):
                            for task in unassigned_tasks:
                                if not rule_engine.is_assignment_safe(a, task, amvs, remaining_tasks):
                                    blocked_pairs[a.amv_id].add(task.task_id)
                                    print(f"  [SCREENED] AMV{a.amv_id} blocked from T{task.task_id} pre-auction")

                consensus.run_auction_round(amvs, tasks, comms, current_timestep=t)

                # ── Symbolic: Post-auction safety net (Bug 3) ─────────
                for a in amvs:
                    if a.assigned_task is not None and a.assigned_task.task_id in blocked_pairs[a.amv_id]:
                        released_tid = a.assigned_task.task_id
                        a.assigned_task.status = 'unassigned'
                        a.assigned_task.assigned_to = None
                        a.assigned_task = None
                        a.enter_assignment()
                        print(f"  [UNASSIGNED] AMV{a.amv_id} stripped of T{released_tid} post-auction")

                auction_ran_this_step = True

        # 9 — Fix 4: update benefit snapshot only when an auction fires
        if auction_ran_this_step:
            last_auction_benefit = consensus.compute_total_benefit(amvs, tasks)
        benefit_snapshot_log.append((t, last_auction_benefit))

        # 10 — Log proposals and mt
        for amv in amvs:
            amv.compute_proposal(consensus.mt)
            proposal_log[amv.amv_id].append((t, amv.m_p_i))
        mt_log.append((t, consensus.mt))

        # 11 — Fix 6: record trajectory positions
        for amv in amvs:
            trajectory_log[amv.amv_id].append(
                (amv.position[0], amv.position[1]))

        # 12 — Fix 9: detect FSM deadlock entry events
        for amv in amvs:
            prev = prev_fsm_states.get(amv.amv_id)
            if amv.fsm_state == config.FSM_DEADLOCK and prev != config.FSM_DEADLOCK:
                fsm_deadlock_events[amv.amv_id].append(t)
            prev_fsm_states[amv.amv_id] = amv.fsm_state

        # 12b — Log FSM state every timestep (for FSM timeline plot)
        for amv in amvs:
            fsm_state_log[amv.amv_id].append((t, amv.fsm_state))

        # 12c — TrustScore update
        for amv in amvs:
            if not hasattr(amv, 'fsm_history'):
                amv.fsm_history = [amv.fsm_state]
            amv.fsm_history.append(amv.fsm_state)
            
            task_pos = amv.assigned_task.position.copy() if amv.assigned_task is not None else None
            if not hasattr(amv, 'task_pos_history'):
                amv.task_pos_history = [task_pos]
            amv.task_pos_history.append(task_pos)
            
        if t % config.TRUST_UPDATE_INTERVAL == 0:
            from security.trust import TrustScoreTracker
            tracker = TrustScoreTracker(config.N_AMVS)
            tracker.update_trust_scores(amvs, trajectory_log, t)

        # 13 — Physics logging
        for amv in amvs:
            physics_log[amv.amv_id].append({
                't': t,
                'depth': amv.depth,
                'temp': ocean_env.temperature(amv.depth),
                'pressure': ocean_env.pressure(amv.depth),
                'sound_speed': ocean_env.sound_speed(amv.depth),
                'buoyancy': ocean_env.buoyancy(config.AMV_VOLUME, config.AMV_MASS, amv.depth),
                'dvl_drift': amv.total_dvl_drift,
            })

        # 14 — Completion timestamps
        for entry in consensus.task_completion_log:
            tid = entry['task_id']
            if tid not in completion_timestamps:
                completion_timestamps[tid] = entry['timestep']

        # 15 — Connectivity logging
        connectivity_log.append(comms.algebraic_connectivity())

        # 16 — Standard logging
        tasks_completed_so_far = sum(1 for tk in tasks
                                      if tk.status == "completed")
        pkt = comms.log_packet_stats()

        for amv in amvs:
            availability_log[amv.amv_id].append((t, amv.availability))
            energy_log[amv.amv_id].append((t, amv.energy))
            fault_log[amv.amv_id].append((t, amv.fault_state))

        # Track stalled AMV-timesteps
        stalled_amvs_this_step = 0
        for amv in amvs:
            if amv.energy > 0 and amv.assigned_task is not None and not amv.assigned_task.is_dummy:
                if amv.fsm_state in (config.FSM_REACHING, config.FSM_DEADLOCK):
                    is_stalled = False
                    if config.ALLOCATOR_MODE == "auction":
                        # For auction, it is stalled if it is in the DEADLOCK state
                        if amv.fsm_state == config.FSM_DEADLOCK:
                            is_stalled = True
                    elif config.ALLOCATOR_MODE == "vanilla_auction":
                        if amv.fsm_state == config.FSM_DEADLOCK or amv.availability < config.BID_AVAILABILITY_THRESHOLD:
                            is_stalled = True
                        elif amv.fault_state == "sensor_failure" and amv.depth > config.THERMOCLINE_DEPTH * 0.9:
                            is_stalled = True
                        else:
                            # Blocked by a dead or severely degraded vehicle holding a conflicting task
                            task_id = amv.assigned_task.task_id
                            conflict_stalled = False
                            for other in amvs:
                                if other.amv_id != amv.amv_id and other.assigned_task is not None and other.assigned_task.task_id == task_id:
                                    if other.energy <= 0 or other.fault_state in ("actuator_degraded_severe", "sensor_failure"):
                                        conflict_stalled = True
                                        break
                            if conflict_stalled:
                                is_stalled = True
                    elif config.ALLOCATOR_MODE == "cbba":
                        # For CBBA, it is stalled if availability is low or physically blocked by rule or dead vehicle
                        if amv.fsm_state == config.FSM_DEADLOCK or amv.availability < config.BID_AVAILABILITY_THRESHOLD:
                            is_stalled = True
                        elif amv.fault_state == "sensor_failure" and amv.depth > config.THERMOCLINE_DEPTH * 0.9:
                            is_stalled = True
                        else:
                            # Blocked by a dead or severely degraded vehicle holding a conflicting task
                            task_id = amv.assigned_task.task_id
                            winner_id = consensus.z[amv.amv_id].get(task_id)
                            if winner_id is not None and winner_id != amv.amv_id:
                                winner_amv = next((a for a in amvs if a.amv_id == winner_id), None)
                                if winner_amv is not None and (winner_amv.energy <= 0 or winner_amv.fault_state in ("actuator_degraded_severe", "sensor_failure")):
                                    is_stalled = True
                    
                    if is_stalled:
                        stalled_amvs_this_step += 1
        stalled_amv_timesteps += stalled_amvs_this_step

        # Track active task delays (time spent in active state without being completed)
        for task in tasks:
            if not task.is_dummy and task.status == "active":
                task_active_delay[task.task_id] += 1

        log_rows.append({
            "timestep": t,
            "tasks_completed": tasks_completed_so_far,
            "realloc_events": realloc_events_this_step,
            "packet_drop_rate": pkt["drop_rate"],
            "stalled_amvs": stalled_amvs_this_step,
            "deadlocks": len(consensus.deadlock_log),
        })

        telemetry_log.append({
            "timestep": t,
            "packet_loss_rate": float(pkt["drop_rate"]),
            "amvs": [
                {
                    "amv_id": amv.amv_id,
                    "position": [float(amv.position[0]), float(amv.position[1]), float(amv.depth)],
                    "fsm_state": amv.fsm_state,
                    "assigned_task_id": amv.assigned_task.task_id if amv.assigned_task is not None else None,
                    "energy": float(amv.energy)
                }
                for amv in amvs
            ]
        })

        # Rolling graph snapshots (kept every 10 timesteps to save memory)
        if t % 10 == 0 or t == 1:
            all_graph_snapshots[t] = comms.get_graph_snapshot()
            all_energy_snapshots[t] = {a.amv_id: a.energy for a in amvs}

        # 17 — Live 3D visualization update
        if live_viz is not None:
            deadlock_count = len(consensus.deadlock_log)
            live_viz.update(t, amvs, tasks, comms, consensus.mt, deadlock_count)

        # ── Early stop when all real tasks complete ───────────────────────────
        real_tasks = [tk for tk in tasks if not tk.is_dummy]
        if all(tk.status == 'completed' for tk in real_tasks):
            print(f"\n  All {len(real_tasks)} tasks completed at t={t}.")
            print(f"  Stopping simulation early.")
            break

        # Progress
        if t % 50 == 0:
            print(f"  t={t:3d}  tasks_done={tasks_completed_so_far}/{config.N_TASKS}  "
                  f"mt={consensus.mt}  reallocs={realloc_events_this_step}  "
                  f"deadlocks={len(consensus.deadlock_log)}  "
                  f"pkt_drop={pkt['drop_rate']:.3f}")
            for amv in amvs:
                if amv.assigned_task is not None:
                    dist = np.linalg.norm(amv.position - amv.assigned_task.position)
                    task_info = f"T{amv.assigned_task.task_id}(d={dist:.0f}m)"
                else:
                    task_info = "None"
                print(f"  AMV{amv.amv_id} | {amv.fsm_state:12} | {task_info:22} "
                      f"| done={amv.tasks_done} | E={amv.energy:.0f}%")
            unassigned = [t_.task_id for t_ in tasks
                          if t_.status == 'unassigned' and not t_.is_dummy]
            active = [t_.task_id for t_ in tasks if t_.status == 'active']
            completed = [t_.task_id for t_ in tasks if t_.status == 'completed']
            print(f"  Tasks — unassigned:{unassigned} active:{active} completed:{completed}")

    # ── Close live viz & switch to Agg ─────────────────────────────────────
    if live_viz is not None:
        live_viz.close()
        print("Live 3D visualization closed.")

    # ── Summary ─────────────────────────────────────────────────────────────
    log_df = pd.DataFrame(log_rows)
    total_completed = sum(1 for tk in tasks if tk.status == "completed")
    total_reallocs = len(consensus.reallocation_log)
    total_deadlocks = len(consensus.deadlock_log)
    pkt = comms.log_packet_stats()

    print(f"\n{'='*60}")
    print("SIMULATION SUMMARY (Miele et al. Upgrade)")
    print(f"{'='*60}")
    print(f"Tasks completed: {total_completed} / {config.N_TASKS}")
    print(f"Total reallocation events: {total_reallocs}")
    print(f"Total EDMC global deadlocks: {total_deadlocks}")
    print(f"Final mt: {consensus.mt}")
    print(f"Packet stats — sent: {pkt['total_sent']}, dropped: {pkt['total_dropped']}, "
          f"drop rate: {pkt['drop_rate']:.4f}, "
          f"congestion drops: {pkt.get('congestion_drops', 0)}")
    print()

    for amv in amvs:
        fault_states_seen = set(s for _, s in fault_log[amv.amv_id])
        print(f"AMV {amv.amv_id} [{amv.fsm_state}]:  dist={amv.distance_traveled:.1f}m  "
              f"tasks_done={len(amv.tasks_completed)}  "
              f"energy={amv.energy:.1f}  depth={amv.depth:.1f}m  "
              f"faults_seen={fault_states_seen}")

    if consensus.deadlock_log:
        print(f"\nDeadlock events:")
        for dl in consensus.deadlock_log:
            print(f"  t={dl['timestep']}: mt {dl['mt_before']}→{dl['mt_after']}, "
                  f"idled AMV {dl['idled_amv']}")

    # ── Metrics report ────────────────────────────────────────────────────────
    sim_metrics.print_report(
        tasks=tasks,
        completion_timestamps=completion_timestamps,
        total_timesteps=config.SIMULATION_TIMESTEPS,
        availability_log=availability_log,
        fault_log=fault_log,
        deadlock_log=consensus.deadlock_log,
        total_sent=pkt['total_sent'],
        total_dropped=pkt['total_dropped'],
        energy_log=energy_log,
        tasks_completed_count=total_completed,
        auction_iterations_log=consensus.auction_iteration_log,
        connectivity_log=connectivity_log,
        physics_log=physics_log,
        thermocline_messages=pkt.get('thermocline_messages', 0),
        congestion_drops=pkt.get('congestion_drops', 0),
    )

    # ── Build dynamic comm graph snapshots (start / middle / end) ────────────
    actual_end = max(all_graph_snapshots.keys())
    mid_t = actual_end // 2
    # Find closest captured timestep to midpoint
    mid_t = min(all_graph_snapshots.keys(), key=lambda k: abs(k - mid_t))
    graph_snapshots = {
        0: all_graph_snapshots[0],
        mid_t: all_graph_snapshots[mid_t],
        actual_end: all_graph_snapshots[actual_end],
    }
    energy_snapshots = {
        0: all_energy_snapshots[0],
        mid_t: all_energy_snapshots.get(mid_t, {}),
        actual_end: all_energy_snapshots.get(actual_end, {}),
    }

    # ── Visualizations (one call per plot) ───────────────────────────────────
    if getattr(config, "SAVE_PLOTS", True):
        print(f"\n{'='*60}")
        print("Generating plots...")
        print(f"  DEBUG: deadlock_events has {len(deadlock_events)} entries "
              f"(same obj as consensus.deadlock_log: {deadlock_events is consensus.deadlock_log})")
        print(f"{'='*60}\n")

        initial_graph = graph_snapshots.get(0)

        plot_mission_space(amvs, tasks, initial_positions, consensus.reallocation_log,
                           initial_graph, trajectory_log=trajectory_log)
        plot_task_coverage(log_df, consensus.reallocation_log,
                           consensus.deadlock_log, consensus.task_completion_log)
        plot_availability(availability_log, fault_log)
        plot_fault_gantt(fault_log)
        plot_comm_graph_snapshots(graph_snapshots, energy_snapshots)
        plot_energy(energy_log, reallocation_events_by_amv,
                    fsm_deadlock_events=fsm_deadlock_events)
        plot_total_benefit(benefit_snapshot_log, consensus.deadlock_log,
                           consensus.task_completion_log)
        plot_edmc_proposals(proposal_log, mt_log, consensus.deadlock_log,
                            consensus.task_completion_log)

        import visualize
        visualize.plot_3d_mission_space(
            trajectory_log=trajectory_log,
            task_positions=[(t.position[0], t.position[1]) for t in tasks],
            completed_tasks=set(t.task_id for t in tasks if t.status == 'completed'),
            amv_colors=visualize.AMV_COLORS,
            n_timesteps=config.SIMULATION_TIMESTEPS,
        )

        plot_physics_dashboard(physics_log, fault_log=fault_log)

        # New visualisations
        visualize.plot_mesh_animation(mesh_animation_log,
                                      filename='mesh_animation.gif')
        visualize.plot_fsm_timeline(fsm_state_log, consensus.deadlock_log,
                                    consensus.task_completion_log,
                                    filename='plot_fsm_timeline.png')
        visualize.plot_fsm_diagram(filename='plot_fsm_diagram.png')

        # ── Symbolic Rule Engine Summary ─────────────────────────────────────────
        rule_summary = rule_engine.get_rule_log_summary()
        print(f"\n{'='*60}")
        print("SYMBOLIC RULE ENGINE SUMMARY")
        print(f"{'='*60}")
        print(f"  Total rules fired:    {rule_summary['total_rules_fired']}")
        print(f"  Vetoes:               {rule_summary['vetoes']}")
        print(f"  Modifications:        {rule_summary['modifications']}")
        print(f"  Escalation strikes:   {rule_summary['escalation_strikes']}")
        print(f"  By rule:")
        for rule_name, count in rule_summary['by_rule'].items():
            print(f"    {rule_name:25s}  {count}")
        print(f"{'='*60}")

        # ── CNN Confidence Histogram ──────────────────────────────────────────
        plot_confidence_histogram(confidence_log)

    # ── Stress Scenario Summary ──────────────────────────────────────────
    if config.STRESS_SCENARIO != 'none':
        print(f"\n{'='*60}")
        print("STRESS SCENARIO SUMMARY")
        print(f"{'='*60}")
        print(f"  Scenario:            {config.STRESS_SCENARIO}")
        print(f"  Start timestep:      {config.STRESS_START_TIMESTEP}")
        if config.STRESS_SCENARIO == 'comm_blackout':
            print(f"  End timestep:        {config.STRESS_END_TIMESTEP}")
        print(f"  Fired:               {'Yes' if stress_fired else 'No'}")
        print(f"  Task Completion:     {total_completed} / {config.N_TASKS} "
              f"({total_completed/config.N_TASKS:.0%})")
        print(f"  Total Deadlocks:     {total_deadlocks}")
        print(f"  Packet Drop Rate:    {pkt['drop_rate']:.4f}")
        print(f"  Congestion Drops:    {pkt.get('congestion_drops', 0)}")
        for amv in amvs:
            print(f"  AMV{amv.amv_id} — energy={amv.energy:.1f}% "
                  f"tasks_done={len(amv.tasks_completed)} "
                  f"fault={amv.fault_state}")
        print(f"{'='*60}")

    # ── Misclassification Injection Summary ───────────────────────────────
    if config.INJECT_MISCLASSIFICATION:
        target_amv = next((a for a in amvs
                          if a.amv_id == config.MISCLASSIFICATION_TARGET_AMV), None)
        target_energy = target_amv.energy if target_amv else -1
        target_ran_out = target_energy <= 0.0 if target_amv else False

        print(f"\n{'='*60}")
        print("MISCLASSIFICATION INJECTION SUMMARY")
        print(f"{'='*60}")
        print(f"  Target AMV:                    {config.MISCLASSIFICATION_TARGET_AMV}")
        print(f"  Timesteps overridden:          {misclass_override_count}")
        print(f"  Tasks assigned while misclass: {misclass_tasks_assigned_while_bad}")
        print(f"  Target AMV ran out of energy:  {target_ran_out}")
        print(f"  Target AMV final energy:       {target_energy:.1f}%")
        print(f"  Task completion rate:          "
              f"{total_completed}/{config.N_TASKS} ({total_completed/config.N_TASKS:.0%})")
        print(f"{'='*60}")

    # Calculate task delay metrics
    real_task_delays = [delay for tid, delay in task_active_delay.items()]
    mean_task_delay = float(np.mean(real_task_delays)) if real_task_delays else 0.0
    max_task_delay = float(np.max(real_task_delays)) if real_task_delays else 0.0
    never_completed_tasks_count = sum(1 for t in tasks if not t.is_dummy and t.status != "completed")

    print(f"\nTask active delay metrics:")
    print(f"  Mean task delay: {mean_task_delay:.2f} ts")
    print(f"  Max task delay:  {max_task_delay:.2f} ts")
    print(f"  Never completed: {never_completed_tasks_count} tasks")

    import comms as comms_module
    print(f"  [DEBUG CONGESTION] raw comms.congestion_drops = {comms.congestion_drops}")
    print(f"  [DEBUG CONGESTION] module-level comms.RAW_CONGESTION_DROPS = {comms_module.RAW_CONGESTION_DROPS}")
    print("\nAll done!")

    if getattr(config, "TELEMETRY_LOG_PATH", None) is not None:
        with open(config.TELEMETRY_LOG_PATH, "w") as f:
            json.dump(telemetry_log, f, indent=2)
        print(f"Saved telemetry log to {config.TELEMETRY_LOG_PATH}")

    results = {
        "log_df": log_df,
        "tasks": tasks,
        "completion_timestamps": completion_timestamps,
        "availability_log": availability_log,
        "fault_log": fault_log,
        "deadlock_log": consensus.deadlock_log,
        "total_sent": pkt['total_sent'],
        "total_dropped": pkt['total_dropped'],
        "energy_log": energy_log,
        "tasks_completed_count": total_completed,
        "auction_iterations_log": consensus.auction_iteration_log,
        "connectivity_log": connectivity_log,
        "physics_log": physics_log,
        "thermocline_messages": pkt.get('thermocline_messages', 0),
        "congestion_drops": pkt.get('congestion_drops', 0),
        "stalled_amv_timesteps": stalled_amv_timesteps,
        "mean_task_delay": mean_task_delay,
        "max_task_delay": max_task_delay,
        "never_completed_tasks": never_completed_tasks_count,
        "task_active_delay": task_active_delay,
        "telemetry_log": telemetry_log,
        "deadlock_timeout_fires": deadlock_timeout_fires,
        "amvs": amvs,
    }

    # ── Archive run results for dashboard ────────────────────────────────────
    try:
        import run_archiver
        run_archiver.archive_run(results, seed)
    except Exception as e:
        print(f"[WARNING] Run archiving failed: {e}")

    return results


if __name__ == "__main__":
    main()

