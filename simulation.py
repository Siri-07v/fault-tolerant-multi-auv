"""
simulation.py — AMV and Task classes for the AUV swarm simulation.
Upgraded with 6-state LFSM from Miele, Lippi & Gasparri (IEEE TASE 2025).
"""
import os
import pickle
import random
from collections import deque
import numpy as np
import pandas as pd
import torch

import config


# ─── Task ───────────────────────────────────────────────────────────────────────

class Task:
    def __init__(self, task_id, position, priority_weight, arrival_order=None):
        self.task_id = task_id
        self.position = np.array(position, dtype=np.float64)
        self.priority_weight = priority_weight
        self.status = "unassigned"        # unassigned / active / completed
        self.assigned_to = None           # AMV id or None
        self.waiting_time = 0             # timesteps unserved
        self.arrival_order = arrival_order if arrival_order is not None else task_id
        self.is_dummy = False             # dummy tasks for n > m case

    def increment_waiting(self):
        """Increment waiting time if task is still unassigned."""
        if self.status == "unassigned":
            self.waiting_time += 1

    def __repr__(self):
        return (f"Task(id={self.task_id}, pos=({self.position[0]:.0f},{self.position[1]:.0f}), "
                f"prio={self.priority_weight:.2f}, status={self.status}, "
                f"wait={self.waiting_time})")


# ─── AMV ────────────────────────────────────────────────────────────────────────

class AMV:
    def __init__(self, amv_id, position, energy, replay_csv_path,
                 ocean_env=None, csv_pool=None):
        self.amv_id = amv_id
        self.position = np.array(position, dtype=np.float64)
        self.energy = float(energy)
        self.fault_state = "normal"
        self.availability = 1.0
        self.assigned_task = None  # Task object or None
        self.sensor_buffer = deque(maxlen=config.WINDOW_SIZE)

        # ── FSM state (Miele et al. LFSM) ──────────────────────────────────
        self.fsm_state = config.FSM_HOMING
        self.dwell_timer = 0              # counts down in Serving state

        # ── EDMC proposal ───────────────────────────────────────────────────
        self.m_p_i = -1                   # proposal value for EDMC

        # Fault injection: replay sensor data from a CSV
        self._replay_data = pd.read_csv(replay_csv_path)[config.SENSOR_COLUMNS].values
        self._replay_idx = 0
        self._csv_pool = csv_pool or {}   # {fault_class: [csv_path, ...]}
        self._current_csv_class = "normal"

        # Trajectory tracking
        self.trajectory = [self.position.copy()]
        self.tasks_completed = []
        self.fault_history = []  # list of (timestep, fault_state)
        self.distance_traveled = 0.0

        # ── Depth & physics ─────────────────────────────────────────────────
        self.depth = random.uniform(config.DEPTH_MIN, config.DEPTH_MAX)
        self.ocean_env = ocean_env
        self._depth_phase = random.uniform(0, 2 * 3.14159)  # random phase

        # ── DVL dead reckoning drift ───────────────────────────────────────
        self.estimated_position = self.position.copy()
        self.dvl_drift_error = np.array([0.0, 0.0])
        self.total_dvl_drift = 0.0

    # ── Properties ──────────────────────────────────────────────────────────

    @property
    def tasks_done(self):
        return len(self.tasks_completed)

    @property
    def speed(self):
        return config.SPEED.get(self.fault_state, 5.0)

    # ── FSM transitions ─────────────────────────────────────────────────────

    def transition_to(self, new_state):
        """Transition to a new FSM state."""
        self.fsm_state = new_state

    def enter_assignment(self):
        """Transition into Assignment state and reset EDMC if configured."""
        self.fsm_state = config.FSM_ASSIGNMENT
        if config.EDMC_RESET_ON_ASSIGNMENT:
            self.m_p_i = -1

    def enter_reaching(self):
        """Assignment → Reaching (task has been assigned)."""
        self.fsm_state = config.FSM_REACHING

    def enter_serving(self):
        """Reaching → Serving (position reached, start dwell timer)."""
        self.fsm_state = config.FSM_SERVING
        self.dwell_timer = config.TASK_DWELL_TIME

    def enter_idle(self):
        """Enter Idle state (dummy task or paused by Algorithm 1)."""
        self.fsm_state = config.FSM_IDLE

    def enter_patrol(self, all_tasks=None, tasks=None):
        """Enter Patrol state — move toward unassigned tasks."""
        self.fsm_state = config.FSM_PATROL
        # Support both kwarg names for backwards compat
        task_list = all_tasks or tasks or []
        self._patrol_tasks = task_list
        if task_list:
            unassigned = [t for t in task_list
                          if t.status == 'unassigned' and not t.is_dummy]
            if unassigned:
                nearest = min(unassigned,
                             key=lambda t: np.linalg.norm(self.position - t.position))
                self.patrol_target = nearest.position.copy()
            else:
                self.patrol_target = np.array([500.0, 500.0])
        else:
            self.patrol_target = np.array([500.0, 500.0])

    def enter_deadlock(self):
        """Reaching → Deadlock (fault-based local deadlock proxy)."""
        self.fsm_state = config.FSM_DEADLOCK

    def update_dvl_drift(self, distance_moved):
        """
        Accumulate DVL dead reckoning error proportional to distance traveled.
        Sensor failure fault multiplies drift rate.
        Surfacing resets drift via simulated GPS fix.
        """
        import math
        # Reset drift if near surface — simulated GPS fix
        if config.DVL_RESET_ON_SURFACE and self.depth < 10.0:
            self.dvl_drift_error = np.array([0.0, 0.0])
            self.estimated_position = self.position.copy()
            return

        # Drift rate depends on fault state
        if self.fault_state == 'sensor_failure':
            drift_rate = config.DVL_DRIFT_RATE * config.DVL_FAULT_DRIFT_MULTIPLIER
        else:
            drift_rate = config.DVL_DRIFT_RATE

        # Random walk drift
        drift_magnitude = distance_moved * drift_rate
        drift_angle = random.uniform(0, 2 * math.pi)
        new_drift = drift_magnitude * np.array([math.cos(drift_angle),
                                                 math.sin(drift_angle)])
        self.dvl_drift_error += new_drift
        self.estimated_position = self.position + self.dvl_drift_error
        self.total_dvl_drift = float(np.linalg.norm(self.dvl_drift_error))

    # ── Sensor replay ──────────────────────────────────────────────────────

    def push_sensor_reading(self):
        """Push the next row from the replay CSV into sensor_buffer."""
        row = self._replay_data[self._replay_idx]
        self.sensor_buffer.append(row)
        self._replay_idx = (self._replay_idx + 1) % len(self._replay_data)

    # ── Availability ────────────────────────────────────────────────────────

    def compute_availability(self):
        base = config.AVAILABILITY.get(self.fault_state, 1.0)
        self.availability = base * (self.energy / 100.0)
        return self.availability

    # ── Fault detection ─────────────────────────────────────────────────────

    def update_fault_state(self, classifier, scaler, device=None):
        """Run classifier inference + depth-coupled fault escalation."""
        if len(self.sensor_buffer) < config.WINDOW_SIZE:
            return  # not enough data yet

        if device is None:
            device = torch.device("cpu")

        window = np.array(list(self.sensor_buffer), dtype=np.float32)  # (50, 7)

        # Apply z-score scaler
        window = (window - scaler["mean"]) / scaler["std"]

        # Model expects (batch, 7, 50) — channels first
        x = torch.from_numpy(window).permute(1, 0).unsqueeze(0).to(device)  # (1, 7, 50)

        classifier.eval()
        with torch.no_grad():
            logits = classifier(x)
            pred_idx = logits.argmax(dim=1).item()

        self.fault_state = config.INDEX_TO_LABEL[pred_idx]

        # Depth-coupled fault escalation
        if self.ocean_env is not None:
            modifier = self.ocean_env.fault_modifier(self.depth)
            if (modifier > 2.0
                    and self.fault_state == "normal"
                    and random.random() < config.DEPTH_FAULT_ESCALATION_PROB):
                self.fault_state = "actuator_degraded_mild"

    # ── Dynamic CSV switching (R4F4) ─────────────────────────────────────────

    def maybe_switch_csv(self, current_timestep, csv_switch_log=None):
        """
        Every 10 timesteps, decide which CSV fault class to pull from
        based on the physics fault modifier at current depth.
        """
        if current_timestep % 10 != 0:
            return
        if not self._csv_pool:
            return
        if self.ocean_env is None:
            return

        modifier = self.ocean_env.fault_modifier(self.depth)

        # Weighted class selection
        if modifier < 1.3:
            weights = {"normal": 0.95, "actuator_degraded_mild": 0.0,
                       "actuator_degraded_severe": 0.0, "sensor_failure": 0.0,
                       "load_fault": 0.05}
        elif modifier < 1.8:
            weights = {"normal": 0.60, "actuator_degraded_mild": 0.25,
                       "actuator_degraded_severe": 0.0, "sensor_failure": 0.0,
                       "load_fault": 0.15}
        else:
            weights = {"normal": 0.20, "actuator_degraded_mild": 0.30,
                       "actuator_degraded_severe": 0.25, "sensor_failure": 0.15,
                       "load_fault": 0.10}

        # Filter to classes that exist in the pool
        available = [(cls, w) for cls, w in weights.items()
                     if cls in self._csv_pool and self._csv_pool[cls]]
        if not available:
            return

        classes, probs = zip(*available)
        total = sum(probs)
        if total < 1e-8:
            return
        probs = [p / total for p in probs]

        target_class = random.choices(classes, weights=probs, k=1)[0]

        if target_class != self._current_csv_class:
            csv_path = random.choice(self._csv_pool[target_class])
            self._replay_data = pd.read_csv(csv_path)[config.SENSOR_COLUMNS].values
            self._replay_idx = 0
            old_class = self._current_csv_class
            self._current_csv_class = target_class

            if csv_switch_log is not None:
                csv_switch_log.append({
                    "timestep": current_timestep,
                    "amv_id": self.amv_id,
                    "from_class": old_class,
                    "to_class": target_class,
                    "modifier": modifier,
                })

    # ── Movement (FSM-aware) ─────────────────────────────────────────────────

    def move_toward_task(self, current_timestep=0):
        """
        Move one step toward assigned task — ONLY in Reaching state.
        Physics-aware: ocean current drag + pressure-scaled energy cost.
        Also handles Patrol state movement.
        """
        # ── Homing guard — immediately transition to Assignment ─────────────
        if self.fsm_state == config.FSM_HOMING:
            self.enter_assignment()
            return

        # ── Patrol movement ─────────────────────────────────────────────────
        if self.fsm_state == config.FSM_PATROL:
            self._move_patrol(current_timestep)
            return

        if self.fsm_state != config.FSM_REACHING:
            return

        if self.assigned_task is None or self.assigned_task.status == "completed":
            return

        direction = self.assigned_task.position - self.position
        dist = np.linalg.norm(direction)
        if dist < 1e-6:
            return

        step_size = min(self.speed, dist)   # never move further than remaining distance
        move_vec = (direction / dist) * step_size

        # Ocean current drag nudges path
        if self.ocean_env is not None:
            drag = self.ocean_env.current_drag(current_timestep)
            move_vec = move_vec + drag * config.DRAG_INFLUENCE

        # After drag, re-cap total movement to prevent drag pushing past task
        total_move = np.linalg.norm(move_vec)
        if total_move > dist:
            move_vec = move_vec * (dist / total_move)

        distance_moved = float(np.linalg.norm(move_vec))
        self.position += move_vec
        self.distance_traveled += distance_moved
        self.update_dvl_drift(distance_moved)

        # Pressure-scaled energy cost
        if self.ocean_env is not None:
            pressure = self.ocean_env.pressure(self.depth)
            cost = config.ENERGY_MOVE_COST * (1.0 + pressure / 10.0)
        else:
            cost = config.ENERGY_MOVE_COST
        self.energy = max(0.0, self.energy - cost)

        # Slowly vary depth (sinusoidal oscillation simulating dive ops)
        import math
        self.depth = config.DEPTH_MIN + (config.DEPTH_MAX - config.DEPTH_MIN) * (
            0.5 + 0.5 * math.sin(self._depth_phase + current_timestep / 80.0))
        self.depth = max(config.DEPTH_MIN, min(config.DEPTH_MAX, self.depth))

        self.trajectory.append(self.position.copy())

    def _move_patrol(self, current_timestep):
        """Patrol movement: head toward patrol_target, re-target at 30m."""
        import math
        patrol_speed = self.speed * config.PATROL_SPEED_FRACTION

        target = getattr(self, 'patrol_target', np.array([500.0, 500.0]))
        direction = target - self.position
        dist = np.linalg.norm(direction)

        # When within 30m of target, pick a new unassigned task
        if dist < 30.0:
            tasks = getattr(self, '_patrol_tasks', [])
            unassigned = [t for t in tasks
                          if hasattr(t, 'status') and t.status == 'unassigned'
                          and not t.is_dummy]
            if unassigned:
                nearest = min(unassigned,
                             key=lambda t: np.linalg.norm(self.position - t.position))
                self.patrol_target = nearest.position.copy()
                target = self.patrol_target
                direction = target - self.position
                dist = np.linalg.norm(direction)
            else:
                # All tasks assigned — orbit center
                self._patrol_angle = getattr(self, '_patrol_angle', 0.0) + 0.05
                center = np.array([500.0, 500.0])
                target = center + config.PATROL_RADIUS * np.array([
                    math.cos(self._patrol_angle),
                    math.sin(self._patrol_angle),
                ])
                direction = target - self.position
                dist = np.linalg.norm(direction)

        if dist > 1e-6:
            step = min(patrol_speed, dist)
            move_vec = (direction / dist) * step
            self.position += move_vec
            self.distance_traveled += step

        # Still drain energy at base idle rate
        self.energy = max(0.0, self.energy - config.ENERGY_MOVE_COST * 0.3)

        # Depth oscillation
        self.depth = config.DEPTH_MIN + (config.DEPTH_MAX - config.DEPTH_MIN) * (
            0.5 + 0.5 * math.sin(self._depth_phase + current_timestep / 80.0))
        self.depth = max(config.DEPTH_MIN, min(config.DEPTH_MAX, self.depth))

        self.trajectory.append(self.position.copy())

    # ── Task completion (FSM-aware) ──────────────────────────────────────────

    def check_task_reached(self):
        """
        In Reaching state: check if AMV has arrived at task.
        If so, transition to Serving and start dwell timer. Returns True.
        """
        if self.fsm_state != config.FSM_REACHING:
            return False
        if self.assigned_task is None or self.assigned_task.status == "completed":
            return False

        # True arrival check — uses real position
        true_dist = np.linalg.norm(self.position - self.assigned_task.position)
        if true_dist < config.TASK_COMPLETION_RADIUS:
            print(f"  [ARRIVED] AMV{self.amv_id} reached T{self.assigned_task.task_id} "
                  f"true_dist={true_dist:.1f}m "
                  f"dvl_error={self.total_dvl_drift:.1f}m")
            self.enter_serving()
            return True

        # Navigation: AMV thinks it has arrived via DVL estimate
        estimated_dist = np.linalg.norm(self.estimated_position - self.assigned_task.position)
        if estimated_dist < config.TASK_COMPLETION_RADIUS and true_dist < config.TASK_COMPLETION_RADIUS * 3:
            print(f"  [ARRIVED-DVL] AMV{self.amv_id} T{self.assigned_task.task_id} "
                  f"est_dist={estimated_dist:.1f}m true_dist={true_dist:.1f}m "
                  f"dvl_error={self.total_dvl_drift:.1f}m")
            self.enter_serving()
            return True
        return False

    def tick_serving(self):
        """
        In Serving state: decrement dwell timer.
        When timer hits 0, mark task completed and transition to Assignment.
        Returns True if task was just completed.
        """
        if self.fsm_state != config.FSM_SERVING:
            return False

        self.dwell_timer -= 1
        if self.dwell_timer <= 0:
            if self.assigned_task is not None:
                self.assigned_task.status = "completed"
                self.assigned_task.assigned_to = self.amv_id
                self.energy = max(0.0, self.energy - config.ENERGY_TASK_COST)
                self.tasks_completed.append(self.assigned_task.task_id)
                self.assigned_task = None
            self.enter_assignment()
            return True
        return False

    # ── Deadlock check (fault-based local proxy) ─────────────────────────────

    def check_local_deadlock(self):
        """
        In Reaching state: enter Deadlock if availability drops below threshold.
        This replaces the paper's connectivity-based deadlock with fault-based.
        """
        if self.fsm_state != config.FSM_REACHING:
            return False
        if self.availability < config.BID_AVAILABILITY_THRESHOLD:
            self.enter_deadlock()
            return True
        return False

    # ── EDMC proposal computation ──────────────────────────────────────────

    def compute_proposal(self, mt):
        """
        Compute m_p_i based on current FSM state and mt.
        """
        if self.fsm_state == config.FSM_REACHING:
            self.m_p_i = mt
        elif self.fsm_state == config.FSM_DEADLOCK:
            self.m_p_i = mt - 1
        else:  # Idle, Serving, Assignment, Homing
            self.m_p_i = -1
        return self.m_p_i

    # ── Reallocation check (legacy, still used) ──────────────────────────────

    def should_reallocate(self):
        return (
            self.fault_state in ("actuator_degraded_severe", "sensor_failure")
            or self.energy < config.ENERGY_REALLOC_THRESHOLD
        )

    def __repr__(self):
        task_id = self.assigned_task.task_id if self.assigned_task else None
        return (f"AMV(id={self.amv_id}, fsm={self.fsm_state}, "
                f"pos=({self.position[0]:.0f},{self.position[1]:.0f}), "
                f"energy={self.energy:.1f}, fault={self.fault_state}, "
                f"avail={self.availability:.2f}, task={task_id})")
