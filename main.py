"""
main.py — Simulation loop with Miele et al. distributed auction, EDMC, and FSM.
Run train.py first to produce fault_classifier_best.pt and scaler.pkl.
"""
import os
import sys
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
)
import metrics as sim_metrics


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
    consensus = MieleConsensus(n_amvs=config.N_AMVS, n_tasks=config.N_TASKS,
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

    # ── Simulation loop ─────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"Running simulation for {config.SIMULATION_TIMESTEPS} timesteps...")
    print(f"{'='*60}\n")

    for t in range(1, config.SIMULATION_TIMESTEPS + 1):
        realloc_events_this_step = 0
        auction_ran_this_step = False

        # 1 — Push sensor readings & increment task waiting times
        for amv in amvs:
            amv.push_sensor_reading()
        for task in tasks:
            task.increment_waiting()

        # 1b — Fix 8: Idle energy drain for all AMVs (onboard systems)
        for amv in amvs:
            amv.energy = max(0.0, amv.energy - config.IDLE_ENERGY_DRAIN)

        # 2 — Move toward assigned tasks (physics-aware)
        for amv in amvs:
            amv.move_toward_task(current_timestep=t)

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
                amv.update_fault_state(classifier, scaler, device)
                amv.compute_availability()
                amv.maybe_switch_csv(t, csv_switch_log=csv_switch_log)

            amv_positions = {a.amv_id: tuple(a.position) for a in amvs}
            amv_depths = {a.amv_id: a.depth for a in amvs}
            comms.rebuild_graph(amv_positions, amv_depths)

            # Check local deadlock (fault-based) for Reaching AMVs
            for amv in amvs:
                if amv.check_local_deadlock():
                    pass  # state transitions handled inside

            # Run EDMC deadlock detection
            global_deadlock = consensus.run_edmc(amvs, comms, t)
            if global_deadlock:
                consensus.handle_global_deadlock(amvs, tasks, comms, t)
                auction_ran_this_step = True

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
            consensus.run_auction_round(amvs, tasks, comms, current_timestep=t)
            auction_ran_this_step = True

        # Fix 4 — Keep mt aligned with remaining tasks
        unassigned = len([tk for tk in tasks
                          if tk.status == 'unassigned' and not tk.is_dummy])
        active_tasks = len([tk for tk in tasks if tk.status == 'active'])
        remaining = unassigned + active_tasks
        if remaining > 0:
            consensus.mt = max(consensus.mt, min(remaining, config.N_AMVS))

        # Periodic auction every 5 timesteps — ensures idle AMVs get assignments
        if t % 5 == 0 and not auction_ran_this_step:
            # Fix 2 — Wake all idle and patrol AMVs before auction
            for amv in amvs:
                if (amv.assigned_task is None and
                        amv.fsm_state in (config.FSM_IDLE,
                                          config.FSM_PATROL,
                                          config.FSM_ASSIGNMENT)):
                    amv.enter_assignment()

            consensus.run_auction_round(amvs, tasks, comms, current_timestep=t)
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
                        and amv.energy > config.ENERGY_REALLOC_THRESHOLD
                        and unassigned_tasks):
                    nearest = min(unassigned_tasks,
                                  key=lambda tk: np.linalg.norm(
                                      amv.position - tk.position))
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
                consensus.run_auction_round(amvs, tasks, comms, current_timestep=t)
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

        log_rows.append({
            "timestep": t,
            "tasks_completed": tasks_completed_so_far,
            "realloc_events": realloc_events_this_step,
            "packet_drop_rate": pkt["drop_rate"],
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
          f"drop rate: {pkt['drop_rate']:.4f}")
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

    print("\nAll done!")


if __name__ == "__main__":
    main()

