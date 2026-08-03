"""
cbba.py — Consensus-Based Bundle Algorithm (Choi, Brunet & How 2009)
distributed task allocation baseline comparison.
"""
import math
import copy
import numpy as np
import config


class CBBAAllocator:
    """
    CBBA task allocator with:
      - Bundle building phase (Phase 1)
      - Consensus/deconfliction phase (Phase 2)
      - Dynamic task lock for active reaching/serving vehicles
      - Duck-typed interface matching MieleConsensus
    """

    def __init__(self, n_amvs, n_tasks, deadlock_events=None):
        self.n_amvs = n_amvs
        self.n_tasks = n_tasks
        self.deadlock_log = deadlock_events if deadlock_events is not None else []
        self.task_completion_log = []
        self.auction_iteration_log = []
        self.reallocation_log = []
        self.mt = min(n_amvs, n_tasks)

        # CBBA state lists
        self.bundles = {i: [] for i in range(n_amvs)}
        self.paths = {i: [] for i in range(n_amvs)}
        self.y = {i: {} for i in range(n_amvs)}  # winning bid list: {amv_id: {task_id: bid}}
        self.z = {i: {} for i in range(n_amvs)}  # winning agent list: {amv_id: {task_id: winner_amv_id}}
        self.s = {i: {j: 0 for j in range(n_amvs)} for i in range(n_amvs)}  # timestamp table: {amv_id: {neighbor_id: timestep}}

    # ── Path-dependent Benefit ───────────────────────────────────────────────

    def compute_cbba_benefit(self, amv, task, all_tasks, amvs, start_pos):
        """
        Calculates benefit of task path-dependently.
        Matches compute_benefit from consensus.py but takes start_pos.
        """
        from security.byzantine import ByzantineContext
        with ByzantineContext(amv, task):
            if amv.availability < config.BID_AVAILABILITY_THRESHOLD:
                return 0.0

            if task.is_dummy:
                return 0.0

            d_ij = np.linalg.norm(start_pos - task.position)
            beta_d = 1.0 / (1.0 + math.exp(config.BENEFIT_A * (d_ij - config.BENEFIT_B)))

            active_tasks = [t for t in all_tasks if not t.is_dummy and t.status != "completed"]
            waiting_times = np.array([t.waiting_time for t in active_tasks], dtype=np.float64)
            norm_tw = np.linalg.norm(waiting_times)
            beta_t = task.waiting_time / norm_tw if norm_tw > 1e-8 else 0.0

            m_active = len(active_tasks)
            if task.waiting_time > config.BENEFIT_TW:
                prio_factor = task.priority_weight if (config.COMPROMISED_AMVS or config.BYZANTINE_MODE) else 1.0
                beta_p = float(m_active - task.arrival_order + 1) * prio_factor
            else:
                beta_p = 0.0

            beta_raw = beta_d + beta_t + beta_p

            # Workload balance bonus
            if amvs is not None:
                avg_done = sum(a.tasks_done for a in amvs) / len(amvs)
                max_done = max(a.tasks_done for a in amvs) if amvs else 1

                if amv.tasks_done < avg_done:
                    balance_bonus = 1.5 * (1.0 - amv.tasks_done / max(max_done, 1))
                else:
                    balance_bonus = -0.8 * (amv.tasks_done - avg_done) / max(max_done, 1)

                beta_raw += balance_bonus

            beta_raw = max(0.0, beta_raw)
            benefit = beta_raw * amv.availability
            
            # Apply trust discounting if active and score drops below threshold
            trust_score = getattr(amv, "trust_score", 1.0)
            if trust_score < config.TRUST_THRESHOLD:
                benefit = benefit * trust_score
                
            return benefit

    def compute_path_score(self, amv, path, tasks, amvs):
        """Sum of marginal path-dependent task benefits."""
        S = 0.0
        pos = getattr(amv, 'estimated_position', amv.position).copy()
        for tid in path:
            task_obj = next((t for t in tasks if t.task_id == tid), None)
            if task_obj is None:
                continue
            b = self.compute_cbba_benefit(amv, task_obj, tasks, amvs, pos)
            S += b
            pos = task_obj.position.copy()
        return S

    # ── CBBA Round Execution ──────────────────────────────────────────────────

    def run_auction_round(self, amvs, tasks, comms_mesh, current_timestep):
        """Auction interface mapping directly to run_cbba_round."""
        self.run_cbba_round(amvs, tasks, comms_mesh, current_timestep)

    def run_cbba_round(self, amvs, tasks, comms_mesh, current_timestep):
        """
        Runs classic CBBA deconfliction (consensus) and bundle construction
        over MAX_CONSENSUS_ITERATIONS iterations.
        """
        amv_map = {a.amv_id: a for a in amvs}
        task_map = {t.task_id: t for t in tasks}

        # 1. Clean completed tasks from state (keep bundles/paths in sync)
        completed_task_ids = {t.task_id for t in tasks if t.status == "completed"}
        for i in range(self.n_amvs):
            self.bundles[i] = [tid for tid in self.bundles[i] if tid not in completed_task_ids]
            self.paths[i] = [tid for tid in self.paths[i] if tid not in completed_task_ids]
            for tid in completed_task_ids:
                self.z[i][tid] = None
                self.y[i][tid] = 0.0

        # 2. Setup active task locks
        # Any task currently assigned to a reaching/serving AMV is locked.
        for amv in amvs:
            if amv.assigned_task is not None and not amv.assigned_task.is_dummy:
                tid = amv.assigned_task.task_id
                # Enforce lock in state
                if tid not in self.bundles[amv.amv_id]:
                    self.bundles[amv.amv_id] = [tid] + [x for x in self.bundles[amv.amv_id] if x != tid]
                if tid not in self.paths[amv.amv_id]:
                    self.paths[amv.amv_id] = [tid] + [x for x in self.paths[amv.amv_id] if x != tid]
                self.z[amv.amv_id][tid] = amv.amv_id
                self.y[amv.amv_id][tid] = 1e9  # Set high bid to prevent outbidding

        # 3. Iteration loop
        iteration = 0
        for iteration in range(config.MAX_CONSENSUS_ITERATIONS):
            # Track convergence snapshot
            z_snapshot = copy.deepcopy(self.z)
            paths_snapshot = copy.deepcopy(self.paths)

            # A. Phase 2: Consensus / Deconfliction
            delivered = comms_mesh.deliver_messages(current_timestep)
            for i in range(self.n_amvs):
                payloads = delivered.get(i, [])
                for payload in payloads:
                    if payload.get("type") != "cbba":
                        continue
                    k = payload["amv_id"]
                    y_recv = payload["y"]
                    z_recv = payload["z"]
                    s_recv = payload["s"]
                    t_msg = payload["timestamp"]

                    # Update timestamps
                    for m in range(self.n_amvs):
                        if m == k:
                            self.s[i][k] = max(self.s[i][k], t_msg)
                        else:
                            self.s[i][m] = max(self.s[i][m], s_recv.get(str(m), s_recv.get(m, 0)))

                    # Update winning bids and agents
                    all_tids = set(self.y[i].keys()) | set(y_recv.keys())
                    for tid in all_tids:
                        # Convert keys to int if they came via json stringification
                        tid_key = int(tid) if isinstance(tid, str) else tid
                        
                        # Lock guard: do not release own locked task
                        amv_i = amv_map.get(i)
                        if amv_i is not None and amv_i.assigned_task is not None and not amv_i.assigned_task.is_dummy:
                            if tid_key == amv_i.assigned_task.task_id:
                                continue

                        z_i_j = self.z[i].get(tid_key, None)
                        y_i_j = self.y[i].get(tid_key, 0.0)
                        
                        z_k_j = z_recv.get(str(tid_key), z_recv.get(tid_key, None))
                        y_k_j = y_recv.get(str(tid_key), y_recv.get(tid_key, 0.0))

                        action = "leave"

                        if z_k_j == k:
                            if z_i_j == i:
                                if y_k_j > y_i_j:
                                    action = "update"
                                elif y_k_j < y_i_j:
                                    action = "leave"
                                else:
                                    action = "update" if k < i else "leave"
                            elif z_i_j == k:
                                action = "update"
                            elif z_i_j is not None and z_i_j != i and z_i_j != k:
                                m_winner = z_i_j
                                s_km = s_recv.get(str(m_winner), s_recv.get(m_winner, 0))
                                s_im = self.s[i].get(m_winner, 0)
                                if s_km >= s_im or y_k_j > y_i_j:
                                    action = "update"
                                else:
                                    action = "leave"
                            elif z_i_j is None:
                                action = "update"

                        elif z_k_j == i:
                            if z_i_j == i:
                                action = "leave"
                            elif z_i_j == k:
                                action = "reset"
                            elif z_i_j is not None and z_i_j != i and z_i_j != k:
                                m_winner = z_i_j
                                s_km = s_recv.get(str(m_winner), s_recv.get(m_winner, 0))
                                s_im = self.s[i].get(m_winner, 0)
                                if s_km >= s_im:
                                    action = "reset"
                                else:
                                    action = "leave"
                            elif z_i_j is None:
                                action = "leave"

                        elif z_k_j is not None and z_k_j != i and z_k_j != k:
                            m_winner = z_k_j
                            s_km = s_recv.get(str(m_winner), s_recv.get(m_winner, 0))
                            s_im = self.s[i].get(m_winner, 0)
                            if z_i_j == i:
                                if s_km >= s_im:
                                    if y_k_j > y_i_j:
                                        action = "update"
                                    elif y_k_j < y_i_j:
                                        action = "leave"
                                    else:
                                        action = "update" if m_winner < i else "leave"
                                else:
                                    action = "leave"
                            elif z_i_j == k:
                                if s_km >= s_im:
                                    action = "update"
                                else:
                                    action = "reset"
                            elif z_i_j == m_winner:
                                if s_km >= s_im:
                                    action = "update"
                                else:
                                    action = "leave"
                            elif z_i_j is not None and z_i_j != i and z_i_j != k and z_i_j != m_winner:
                                n_winner = z_i_j
                                s_kn = s_recv.get(str(n_winner), s_recv.get(n_winner, 0))
                                s_in = self.s[i].get(n_winner, 0)
                                if s_km >= s_im and s_kn >= s_in:
                                    if y_k_j > y_i_j:
                                        action = "update"
                                    elif y_k_j < y_i_j:
                                        action = "leave"
                                    else:
                                        action = "update" if m_winner < n_winner else "leave"
                                elif s_km >= s_im and s_kn < s_in:
                                    action = "update"
                                elif s_km < s_im and s_kn >= s_in:
                                    action = "leave"
                                elif s_km < s_im and s_kn < s_in:
                                    action = "leave"
                            elif z_i_j is None:
                                if s_km >= s_im:
                                    action = "update"
                                else:
                                    action = "leave"

                        elif z_k_j is None:
                            if z_i_j == i:
                                action = "leave"
                            elif z_i_j == k:
                                action = "update"
                            elif z_i_j is not None and z_i_j != i and z_i_j != k:
                                m_winner = z_i_j
                                s_km = s_recv.get(str(m_winner), s_recv.get(m_winner, 0))
                                s_im = self.s[i].get(m_winner, 0)
                                if s_km >= s_im:
                                    action = "update"
                                else:
                                    action = "leave"
                            elif z_i_j is None:
                                action = "leave"

                        # Apply deconfliction action
                        if action == "update":
                            self.z[i][tid_key] = z_k_j
                            self.y[i][tid_key] = y_k_j
                        elif action == "reset":
                            self.z[i][tid_key] = None
                            self.y[i][tid_key] = 0.0

                # Truncate bundle if any task was outbid/reset
                trunc_idx = None
                for idx, tid in enumerate(self.bundles[i]):
                    if self.z[i].get(tid) != i:
                        trunc_idx = idx
                        break
                if trunc_idx is not None:
                    released = self.bundles[i][trunc_idx:]
                    for tid in released:
                        if self.z[i].get(tid) == i:
                            self.z[i][tid] = None
                            self.y[i][tid] = 0.0
                    self.bundles[i] = self.bundles[i][:trunc_idx]
                    self.paths[i] = [tid for tid in self.paths[i] if tid not in released]

            # B. Phase 1: Bundle Building
            # Compute remaining tasks for symbolic rules
            unassigned_real = [tk for tk in tasks if tk.status == 'unassigned' and not tk.is_dummy]
            active_real = len([tk for tk in tasks if tk.status == 'active'])
            remaining_tasks_count = len(unassigned_real) + active_real

            from main import SymbolicRuleEngine
            rule_engine = getattr(comms_mesh, 'rule_engine', None)
            if rule_engine is None:
                rule_engine = SymbolicRuleEngine()

            for i in range(self.n_amvs):
                amv = amv_map[i]
                if amv.energy <= 0 or amv.availability < config.BID_AVAILABILITY_THRESHOLD:
                    continue

                # Lock index constraint: cannot insert before the locked active task
                has_lock = amv.assigned_task is not None and not amv.assigned_task.is_dummy
                min_insert_idx = 1 if has_lock else 0

                while len(self.bundles[i]) < config.N_TASKS:
                    best_tid = None
                    best_pos = -1
                    best_bid_val = -1.0
                    best_path = []

                    # Current path score
                    s_curr = self.compute_path_score(amv, self.paths[i], tasks, amvs)

                    for task in tasks:
                        if task.is_dummy or task.status == "completed":
                            continue
                        if task.task_id in self.bundles[i]:
                            continue

                        # Check safety gate
                        if not rule_engine.is_assignment_safe(amv, task, amvs, remaining_tasks_count):
                            continue

                        # Find best insertion position in path
                        best_ins_pos = -1
                        max_ins_score = -1.0
                        best_ins_path = []

                        # Try all positions from min_insert_idx to end
                        path_len = len(self.paths[i])
                        for pos_idx in range(min_insert_idx, path_len + 1):
                            cand_path = self.paths[i][:pos_idx] + [task.task_id] + self.paths[i][pos_idx:]
                            score = self.compute_path_score(amv, cand_path, tasks, amvs)
                            if score > max_ins_score:
                                max_ins_score = score
                                best_ins_pos = pos_idx
                                best_ins_path = cand_path

                        marginal_gain = max_ins_score - s_curr
                        local_winning_bid = self.y[i].get(task.task_id, 0.0)

                        if marginal_gain > local_winning_bid + 1e-6:
                            if marginal_gain > best_bid_val:
                                best_bid_val = marginal_gain
                                best_tid = task.task_id
                                best_pos = best_ins_pos
                                best_path = best_ins_path

                    if best_tid is not None:
                        self.bundles[i].append(best_tid)
                        self.paths[i] = best_path
                        self.y[i][best_tid] = best_bid_val
                        self.z[i][best_tid] = i
                    else:
                        break

            # C. Broadcast States
            for i in range(self.n_amvs):
                payload = {
                    "type": "cbba",
                    "amv_id": i,
                    "y": self.y[i].copy(),
                    "z": self.z[i].copy(),
                    "s": self.s[i].copy(),
                    "timestamp": current_timestep,
                }
                for neighbor_id in comms_mesh.graph.neighbors(i):
                    comms_mesh.send_message(i, neighbor_id, payload, current_timestep)

            # Check convergence
            converged = True
            for i in range(self.n_amvs):
                if self.z[i] != z_snapshot[i] or self.paths[i] != paths_snapshot[i]:
                    converged = False
                    break
            if converged:
                break

        # Log iteration count
        self.auction_iteration_log.append(iteration + 1)

        # 4. Enforce assignments back to AMVs and Tasks
        for i in range(self.n_amvs):
            amv = amv_map[i]
            path_i = self.paths[i]
            if path_i:
                target_tid = path_i[0]
                task = task_map.get(target_tid)
                if task is not None:
                    # Update assignment
                    if amv.assigned_task is None:
                        task.status = "active"
                        task.assigned_to = i
                        amv.assigned_task = task
                        if amv.fsm_state in (config.FSM_ASSIGNMENT, config.FSM_IDLE, config.FSM_PATROL):
                            amv.enter_reaching()
                    elif amv.assigned_task.task_id != target_tid:
                        # Release old task
                        old_task = amv.assigned_task
                        if old_task.status == "active":
                            old_task.status = "unassigned"
                            old_task.assigned_to = None
                        task.status = "active"
                        task.assigned_to = i
                        amv.assigned_task = task
                        if amv.fsm_state in (config.FSM_ASSIGNMENT, config.FSM_IDLE, config.FSM_PATROL):
                            amv.enter_reaching()
            else:
                if amv.assigned_task is not None:
                    old_task = amv.assigned_task
                    if old_task.status == "active":
                        old_task.status = "unassigned"
                        old_task.assigned_to = None
                    amv.assigned_task = None
                if amv.fsm_state == config.FSM_ASSIGNMENT:
                    amv.enter_idle()

    # ── Task completion handler ──────────────────────────────────────────────

    def handle_task_completion(self, amvs, tasks, comms_mesh, current_timestep,
                                completed_task_id, completing_amv_id):
        """Remove completed task from state and re-trigger CBBA allocation."""
        m = len([t for t in tasks if t.status != "completed" and not t.is_dummy])
        n = len(amvs)
        self.mt = min(self.mt + 1, m, n)

        self.task_completion_log.append({
            "timestep": current_timestep,
            "task_id": completed_task_id,
            "amv_id": completing_amv_id,
        })

        # Wake Idle AMVs back to Assignment
        for amv in amvs:
            if amv.fsm_state == config.FSM_IDLE:
                amv.enter_assignment()

        # Remove completed task from this AMV's bundle & path
        if completed_task_id in self.bundles[completing_amv_id]:
            self.bundles[completing_amv_id].remove(completed_task_id)
        if completed_task_id in self.paths[completing_amv_id]:
            self.paths[completing_amv_id].remove(completed_task_id)
        self.z[completing_amv_id][completed_task_id] = completing_amv_id
        self.y[completing_amv_id][completed_task_id] = 0.0

        # Run CBBA round
        self.run_cbba_round(amvs, tasks, comms_mesh, current_timestep)

        # Force reaching for assigned AMVs still in Assignment
        for amv in amvs:
            if (amv.assigned_task is not None
                    and not amv.assigned_task.is_dummy
                    and amv.fsm_state == config.FSM_ASSIGNMENT):
                amv.enter_reaching()

    # ── Reallocation (fault/energy) ─────────────────────────────────────────

    def trigger_reallocation(self, amv, tasks, current_timestep, reason="fault"):
        """Release AMV's current task, log event, clear bundle and path."""
        released_task = amv.assigned_task
        if released_task is not None and not released_task.is_dummy:
            released_task.status = "unassigned"
            released_task.assigned_to = None

            self.reallocation_log.append({
                "timestep": current_timestep,
                "amv_id": amv.amv_id,
                "reason": reason,
                "task_id": released_task.task_id,
            })

            # Clear state for this AMV
            amv_id = amv.amv_id
            for tid in list(self.bundles[amv_id]):
                if self.z[amv_id].get(tid) == amv_id:
                    self.z[amv_id][tid] = None
                    self.y[amv_id][tid] = 0.0
            self.bundles[amv_id] = []
            self.paths[amv_id] = []

        amv.assigned_task = None
        amv.enter_assignment()
        return released_task

    # ── Total benefit tracking ──────────────────────────────────────────────

    def compute_total_benefit(self, amvs, tasks):
        """Sum of β_ij_effective for all active (AMV, task) pairs."""
        total = 0.0
        from consensus import compute_benefit
        for amv in amvs:
            if (amv.assigned_task is not None
                    and not amv.assigned_task.is_dummy
                    and amv.assigned_task.status != "completed"):
                total += compute_benefit(amv, amv.assigned_task, tasks, amvs=amvs)
        return total
