"""
consensus.py — Miele, Lippi & Gasparri (IEEE TASE 2025) distributed auction
with EDMC deadlock management and Algorithm 1 pausing.
"""
import math
import numpy as np

import config


# ─── Benefit Function (Equation 20) ────────────────────────────────────────────

def compute_benefit(amv, task, all_tasks, amvs=None):
    """
    β_ij = β_d + β_t + β_p + balance_bonus, scaled by availability.
    Returns 0 if AMV is below availability threshold.
    """
    if amv.availability < config.BID_AVAILABILITY_THRESHOLD:
        return 0.0

    if task.is_dummy:
        return 0.0

    # β_d: sigmoid of distance (uses estimated position for DVL realism)
    estimated_pos = getattr(amv, 'estimated_position', amv.position)
    d_ij = np.linalg.norm(estimated_pos - task.position)
    beta_d = 1.0 / (1.0 + math.exp(config.BENEFIT_A * (d_ij - config.BENEFIT_B)))

    # β_t: normalized waiting time
    active_tasks = [t for t in all_tasks if not t.is_dummy and t.status != "completed"]
    waiting_times = np.array([t.waiting_time for t in active_tasks], dtype=np.float64)
    norm_tw = np.linalg.norm(waiting_times)
    beta_t = task.waiting_time / norm_tw if norm_tw > 1e-8 else 0.0

    # β_p: priority term (activates when waiting > T_w)
    m_active = len(active_tasks)
    if task.waiting_time > config.BENEFIT_TW:
        beta_p = float(m_active - task.arrival_order + 1)
    else:
        beta_p = 0.0

    beta_raw = beta_d + beta_t + beta_p

    # Workload balance bonus — stronger to overcome proximity bias
    if amvs is not None:
        avg_done = sum(a.tasks_done for a in amvs) / len(amvs)
        max_done = max(a.tasks_done for a in amvs) if amvs else 1

        # Bonus for underutilized AMVs
        if amv.tasks_done < avg_done:
            balance_bonus = 1.5 * (1.0 - amv.tasks_done / max(max_done, 1))
        else:
            # Penalty for overutilized AMVs
            balance_bonus = -0.8 * (amv.tasks_done - avg_done) / max(max_done, 1)

        beta_raw += balance_bonus

    beta_raw = max(0.0, beta_raw)   # prevent negative benefit from balance penalty
    return beta_raw * amv.availability


# ─── Distributed Auction ───────────────────────────────────────────────────────

class MieleConsensus:
    """
    Miele et al. distributed auction with:
      - Price-based bidding (Zavlanos et al.)
      - Dummy task handling (n > m)
      - Pausing algorithm (Algorithm 1)
      - Exact Dynamic Max-Consensus (EDMC) deadlock detection
    """

    def __init__(self, n_amvs, n_tasks, deadlock_events=None):
        self.reallocation_log = []
        # Shared deadlock list — caller can pass in their own list so both
        # sides reference the same object.
        self.deadlock_log = deadlock_events if deadlock_events is not None else []
        self.task_completion_log = []           # list of {timestep, task_id, amv_id}
        self.auction_iteration_log = []         # R3F2/R5F4: iterations per auction round

        # mt: max simultaneous servable tasks
        self.mt = min(n_amvs, n_tasks)

        # EDMC state vectors: {amv_id: [mb_0, mb_1, ..., mb_n]}
        self._edmc_state = {}

    # ── Dummy tasks ─────────────────────────────────────────────────────────

    @staticmethod
    def create_dummy_tasks(n_amvs, real_tasks):
        """Create dummy tasks if n > m."""
        m = len([t for t in real_tasks if t.status != "completed"])
        n_dummies = max(0, n_amvs - m)
        dummies = []
        from simulation import Task
        for i in range(n_dummies):
            dummy = Task(
                task_id=1000 + i,
                position=(-1, -1),
                priority_weight=0.0,
                arrival_order=9999,
            )
            dummy.is_dummy = True
            dummy.status = "unassigned"
            dummies.append(dummy)
        return dummies

    # ── Auction round ───────────────────────────────────────────────────────

    def run_auction_round(self, amvs, tasks, comms_mesh, current_timestep):
        """
        Distributed price-based auction from Zavlanos et al. [12].
        Serving AMVs bid ∞ on their current task.
        """
        # Wake idle/patrol AMVs to Assignment before bidding
        for amv in amvs:
            if amv.assigned_task is None and amv.fsm_state in (config.FSM_IDLE, config.FSM_PATROL):
                amv.enter_assignment()

        # Build combined task pool (real + dummy)
        real_unassigned = [t for t in tasks if t.status == "unassigned"]
        dummy_tasks = self.create_dummy_tasks(len(amvs), tasks)
        auction_tasks = real_unassigned + dummy_tasks

        if not auction_tasks:
            return

        # Participating AMVs: not in Serving state
        bidding_amvs = [a for a in amvs if a.assigned_task is None
                        or a.fsm_state not in (config.FSM_SERVING,)]

        # Serving AMVs automatically keep their task
        for amv in amvs:
            if amv.fsm_state == config.FSM_SERVING and amv.assigned_task is not None:
                # Remove their task from auction pool if present
                auction_tasks = [t for t in auction_tasks
                                 if t.task_id != amv.assigned_task.task_id]

        available_amvs = [
            a for a in amvs
            if a.assigned_task is None
            and a.fsm_state in (config.FSM_ASSIGNMENT, config.FSM_IDLE, config.FSM_PATROL)
        ]
        available_amvs = sorted(available_amvs, key=lambda a: a.tasks_done)
        if not available_amvs and not auction_tasks:
            return

        # Price vector: {task_id: current_price}
        prices = {t.task_id: 0.0 for t in auction_tasks}
        amv_map = {a.amv_id: a for a in amvs}

        # Auction iterations
        iteration = 0
        for iteration in range(config.MAX_AUCTION_ITERATIONS):
            amv_bids = {}  # {amv_id: (task_id, bid_value, benefit)}

            for amv in available_amvs:
                best_val, best_task, best_benefit = -float("inf"), None, 0.0

                for task in auction_tasks:
                    benefit = compute_benefit(amv, task, tasks, amvs=amvs)
                    net_value = benefit - prices.get(task.task_id, 0.0)
                    if net_value > best_val:
                        best_val = net_value
                        best_task = task
                        best_benefit = benefit

                if best_task is not None and best_benefit > 0:
                    new_bid = prices.get(best_task.task_id, 0.0) + config.BENEFIT_EPSILON_A
                    amv_bids[amv.amv_id] = (best_task.task_id, new_bid, best_benefit)
                elif best_task is not None and best_task.is_dummy:
                    # Accept dummy with zero bid
                    amv_bids[amv.amv_id] = (best_task.task_id, 0.0, 0.0)

            if not amv_bids:
                break

            # Broadcast bids via comms mesh
            for amv in available_amvs:
                if amv.amv_id not in amv_bids:
                    continue
                task_id, bid_value, _ = amv_bids[amv.amv_id]
                payload = {
                    "type": "auction",
                    "amv_id": amv.amv_id,
                    "task_id": task_id,
                    "bid_value": bid_value,
                }
                for neighbor_id in comms_mesh.graph.neighbors(amv.amv_id):
                    comms_mesh.send_message(
                        amv.amv_id, neighbor_id, payload, current_timestep,
                    )

            # Deliver messages
            delivered = comms_mesh.deliver_messages(current_timestep)

            # Update prices from received bids (filter to auction messages only)
            for receiver_id, payloads in delivered.items():
                for msg in payloads:
                    if msg.get("type") != "auction":
                        continue
                    tid = msg["task_id"]
                    if tid in prices:
                        prices[tid] = max(prices[tid], msg["bid_value"])

            # Resolve conflicts: group by task
            task_claims = {}
            for amv_id, (task_id, bid, benefit) in amv_bids.items():
                task_claims.setdefault(task_id, []).append((amv_id, bid, benefit))

            conflicts = False
            outbid_amvs = set()
            for task_id, claims in task_claims.items():
                if len(claims) > 1:
                    conflicts = True
                    claims.sort(key=lambda x: x[1], reverse=True)
                    winner_id = claims[0][0]
                    prices[task_id] = claims[0][1]
                    for loser_id, _, _ in claims[1:]:
                        outbid_amvs.add(loser_id)

            # Remove outbid AMVs from current bids (they'll rebid next iteration)
            for oid in outbid_amvs:
                if oid in amv_bids:
                    del amv_bids[oid]

            if not conflicts:
                break

            # R5F1: Outbid AMVs must rebid next iteration
            available_amvs = [amv_map[oid] for oid in outbid_amvs if oid in amv_map]
            if not available_amvs:
                break

        # Log iteration count (R3F2/R5F4)
        self.auction_iteration_log.append(iteration)

        # Assign winning tasks
        task_map = {t.task_id: t for t in tasks}
        # Also include dummies
        for d in dummy_tasks:
            task_map[d.task_id] = d

        # Deduplicate: one AMV per task
        final_assignments = {}
        for amv_id, (task_id, bid, benefit) in amv_bids.items():
            existing = final_assignments.get(task_id)
            if existing is None or bid > existing[1]:
                final_assignments[task_id] = (amv_id, bid)

        for task_id, (amv_id, bid) in final_assignments.items():
            task = task_map.get(task_id)
            amv = amv_map.get(amv_id)
            if task is None or amv is None:
                continue

            if task.is_dummy:
                # AMV assigned to dummy → Idle
                amv.assigned_task = None
                amv.enter_idle()
            elif task.status == "unassigned" and amv.assigned_task is None:
                task.status = "active"
                task.assigned_to = amv_id
                amv.assigned_task = task
                amv.enter_reaching()

        # R5F2: Fallback — unassigned AMVs still in Assignment → Idle
        for amv in amvs:
            if amv.assigned_task is None and amv.fsm_state == config.FSM_ASSIGNMENT:
                amv.enter_idle()

        # R4F1: Force enter_reaching for AMVs assigned to real tasks still in Assignment
        for amv in amvs:
            if amv.assigned_task is not None and not amv.assigned_task.is_dummy:
                if amv.fsm_state == config.FSM_ASSIGNMENT:
                    amv.enter_reaching()
            elif amv.assigned_task is None or amv.assigned_task.is_dummy:
                if amv.fsm_state == config.FSM_ASSIGNMENT:
                    amv.enter_idle()

    # ── Pausing Algorithm (Algorithm 1) ─────────────────────────────────────

    def run_pausing_algorithm(self, amvs, tasks, comms_mesh, current_timestep):
        """
        When mt < min(m, n): identify AMVs to pause based on lowest benefit.
        """
        # Guard: if enough unassigned tasks for all active AMVs, no pausing
        unassigned_count = len([t for t in tasks
                                if t.status == 'unassigned' and not t.is_dummy])
        active_amvs = len([a for a in amvs
                           if a.fsm_state not in (config.FSM_IDLE, config.FSM_SERVING)])
        if unassigned_count >= active_amvs:
            return []  # enough tasks for everyone — no pausing needed

        m = len([t for t in tasks if t.status != "completed" and not t.is_dummy])
        n = len(amvs)
        active_serving = len([a for a in amvs
                              if a.fsm_state in (config.FSM_REACHING, config.FSM_SERVING)])

        if active_serving <= self.mt:
            return []  # no pausing needed

        q = active_serving - self.mt

        # Each AMV computes its current assignment benefit
        rankings = []
        for amv in amvs:
            if amv.fsm_state == config.FSM_SERVING:
                beta_star = float("inf")
            elif amv.fsm_state == config.FSM_IDLE:
                beta_star = float("inf")  # already idle, don't re-pause
            elif amv.assigned_task is not None:
                beta_star = compute_benefit(amv, amv.assigned_task, tasks, amvs=amvs)
            else:
                beta_star = 0.0
            rankings.append((amv.amv_id, beta_star))

        # Broadcast rankings via comms
        for amv in amvs:
            for neighbor_id in comms_mesh.graph.neighbors(amv.amv_id):
                entry = next((r for r in rankings if r[0] == amv.amv_id), None)
                if entry:
                    comms_mesh.send_message(
                        amv.amv_id, neighbor_id,
                        {"type": "pause_rank", "amv_id": entry[0], "beta": entry[1]},
                        current_timestep,
                    )

        delivered = comms_mesh.deliver_messages(current_timestep)

        # Merge received rankings
        all_rankings = {r[0]: r[1] for r in rankings}
        for receiver_id, payloads in delivered.items():
            for msg in payloads:
                if msg.get("type") == "pause_rank":
                    aid = msg["amv_id"]
                    beta = msg["beta"]
                    if aid not in all_rankings or beta < all_rankings[aid]:
                        all_rankings[aid] = beta

        # Select q AMVs with lowest beta (excluding inf = Serving/Idle)
        finite_rankings = [(aid, b) for aid, b in all_rankings.items()
                           if b < float("inf")]
        finite_rankings.sort(key=lambda x: x[1])

        paused_ids = []
        amv_map = {a.amv_id: a for a in amvs}

        # R3F4: Fallback when no Reaching AMV found
        if not finite_rankings and q > 0:
            candidates = [a for a in amvs if a.fsm_state != config.FSM_SERVING]
            if candidates:
                amv_to_idle = min(candidates,
                                  key=lambda a: a.m_p_i if a.m_p_i > -1 else float('inf'))
                if amv_to_idle.assigned_task is not None:
                    amv_to_idle.assigned_task.status = "unassigned"
                    amv_to_idle.assigned_task.assigned_to = None
                    amv_to_idle.assigned_task = None
                amv_to_idle.enter_idle()
                paused_ids.append(amv_to_idle.amv_id)
            return paused_ids

        for aid, _ in finite_rankings[:q]:
            amv = amv_map[aid]
            if amv.assigned_task is not None:
                amv.assigned_task.status = "unassigned"
                amv.assigned_task.assigned_to = None
                amv.assigned_task = None
            amv.enter_idle()
            paused_ids.append(aid)

        return paused_ids

    # ── EDMC Deadlock Detection ─────────────────────────────────────────────

    def run_edmc(self, amvs, comms_mesh, current_timestep):
        """
        Exact Dynamic Max-Consensus (EDMC) protocol.
        Returns True if global deadlock detected.
        """
        n = len(amvs)

        # Each AMV computes proposal
        for amv in amvs:
            amv.compute_proposal(self.mt)

        # Initialize EDMC state: mb_i = [m_p_i, 0, ..., 0]
        mb = {}
        for amv in amvs:
            vec = [-999] * (n + 1)
            vec[0] = amv.m_p_i
            mb[amv.amv_id] = vec

        # n iterations of max-consensus
        for l in range(1, n + 1):
            # Exchange via comms
            for amv in amvs:
                payload = {
                    "type": "edmc",
                    "amv_id": amv.amv_id,
                    "mb_prev": mb[amv.amv_id][l - 1],
                }
                for neighbor_id in comms_mesh.graph.neighbors(amv.amv_id):
                    comms_mesh.send_message(
                        amv.amv_id, neighbor_id, payload, current_timestep,
                    )

            delivered = comms_mesh.deliver_messages(current_timestep)

            # Update: mb_l_i = max over neighbors of mb_{l-1}_j
            for amv in amvs:
                max_val = mb[amv.amv_id][l - 1]  # self value
                received = delivered.get(amv.amv_id, [])
                for msg in received:
                    if msg.get("type") == "edmc":
                        max_val = max(max_val, msg["mb_prev"])
                mb[amv.amv_id][l] = max_val

        # Check global deadlock: max proposal == mt - 1 (no AMV proposes mt)
        max_proposal = max(amv.m_p_i for amv in amvs)
        any_mt = any(amv.m_p_i == self.mt for amv in amvs)
        any_mt_minus_1 = any(amv.m_p_i == self.mt - 1 for amv in amvs)

        if not any_mt and any_mt_minus_1 and self.mt > 0:
            return True  # global deadlock
        return False

    def handle_global_deadlock(self, amvs, tasks, comms_mesh, current_timestep):
        """
        On global deadlock: decrement mt, trigger reassignment, pause one AMV.
        """
        mt_before = self.mt
        self.mt = max(0, self.mt - 1)

        # Send all Reaching and Deadlock AMVs back to Assignment
        for amv in amvs:
            if amv.fsm_state in (config.FSM_REACHING, config.FSM_DEADLOCK):
                if amv.assigned_task is not None:
                    amv.assigned_task.status = "unassigned"
                    amv.assigned_task.assigned_to = None
                    amv.assigned_task = None
                amv.enter_assignment()

        # Run auction
        self.run_auction_round(amvs, tasks, comms_mesh, current_timestep)

        # Run pausing to send one AMV to Idle
        paused = self.run_pausing_algorithm(amvs, tasks, comms_mesh, current_timestep)

        idled_id = paused[0] if paused else None
        self.deadlock_log.append({
            "timestep": current_timestep,
            "mt_before": mt_before,
            "mt_after": self.mt,
            "idled_amv": idled_id if idled_id is not None else 'none',
        })

        # R5F6: Force reaching for assigned AMVs still in Assignment
        for amv in amvs:
            if (amv.assigned_task is not None
                    and not amv.assigned_task.is_dummy
                    and amv.fsm_state == config.FSM_ASSIGNMENT):
                amv.enter_reaching()

        return idled_id

    # ── Task completion handler ─────────────────────────────────────────────

    def handle_task_completion(self, amvs, tasks, comms_mesh, current_timestep,
                               completed_task_id, completing_amv_id):
        """
        After task completion: mt = min(mt+1, m, n), trigger reassignment.
        """
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

        self.run_auction_round(amvs, tasks, comms_mesh, current_timestep)

        # R5F5: Force reaching for assigned AMVs still in Assignment
        for amv in amvs:
            if (amv.assigned_task is not None
                    and not amv.assigned_task.is_dummy
                    and amv.fsm_state == config.FSM_ASSIGNMENT):
                amv.enter_reaching()

    # ── Reallocation (fault/energy) ─────────────────────────────────────────

    def trigger_reallocation(self, amv, tasks, current_timestep, reason="fault"):
        """Release AMV's current task, log event."""
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

        amv.assigned_task = None
        amv.enter_assignment()
        return released_task

    # ── Total benefit tracking ──────────────────────────────────────────────

    @staticmethod
    def compute_total_benefit(amvs, tasks):
        """Sum of β_ij_effective for all active (AMV, task) pairs."""
        total = 0.0
        for amv in amvs:
            if (amv.assigned_task is not None
                    and not amv.assigned_task.is_dummy
                    and amv.assigned_task.status != "completed"):
                total += compute_benefit(amv, amv.assigned_task, tasks, amvs=amvs)
        return total
