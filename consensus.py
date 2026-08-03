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
    from security.byzantine import ByzantineContext
    with ByzantineContext(amv, task):
        if config.ALLOCATOR_MODE not in ("auction", "vanilla_auction"):
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
            prio_factor = task.priority_weight if (config.COMPROMISED_AMVS or config.BYZANTINE_MODE) else 1.0
            beta_p = float(m_active - task.arrival_order + 1) * prio_factor
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
        benefit = beta_raw * amv.availability
        
        # Apply trust discounting if active and score drops below threshold
        trust_score = getattr(amv, "trust_score", 1.0)
        if trust_score < config.TRUST_THRESHOLD:
            benefit = benefit * trust_score
            
        return benefit


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

        # Persistent belief states
        self.local_prices = {i: {} for i in range(n_amvs)}
        self.local_assignments = {i: None for i in range(n_amvs)}
        self.local_rankings = {i: {} for i in range(n_amvs)}
        self.pending_deadlock_alerts = []
        self.handled_lost_amvs = set()

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

    def run_auction_round(self, amvs, tasks, comms_mesh, current_timestep):
        """
        Distributed price-based auction from Zavlanos et al. [12].
        Serving AMVs bid on their current task.
        """
        # Clean completed tasks from state (keep state in sync with physical completions)
        completed_task_ids = {t.task_id for t in tasks if t.status == "completed"}
        for i in range(len(amvs)):
            # Clean local prices
            for tid in list(self.local_prices[i].keys()):
                if tid in completed_task_ids:
                    del self.local_prices[i][tid]
            # Clean local assignments
            curr_assign = self.local_assignments[i]
            if curr_assign is not None:
                tid, _, _ = curr_assign
                if tid in completed_task_ids:
                    self.local_assignments[i] = None

        # Synchronize local_assignments with physical amv.assigned_task
        for amv in amvs:
            if amv.assigned_task is None:
                self.local_assignments[amv.amv_id] = None

        # For vanilla_auction, if an AMV has been assigned to a task for > 30 timesteps, lock it
        if config.ALLOCATOR_MODE == "vanilla_auction":
            for amv in amvs:
                if amv.assigned_task is not None and not amv.assigned_task.is_dummy:
                    if getattr(amv, 'task_assigned_duration', 0) > 30:
                        tid = amv.assigned_task.task_id
                        for aid in self.local_prices:
                            self.local_prices[aid][tid] = 1e9
                        self.local_assignments[amv.amv_id] = (tid, 1e9, 1e9)

        # Wake idle/patrol AMVs to Assignment before bidding
        for amv in amvs:
            if getattr(amv, 'paused_until_timestep', 0) > current_timestep:
                continue
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

        # Initialize persistent prices for all auction tasks if not present
        for a in amvs:
            for t in auction_tasks:
                if t.task_id not in self.local_prices[a.amv_id]:
                    self.local_prices[a.amv_id][t.task_id] = 0.0

        # Serving AMVs automatically lock their task at infinity price in all local states
        for amv in amvs:
            if amv.fsm_state == config.FSM_SERVING and amv.assigned_task is not None:
                tid = amv.assigned_task.task_id
                for aid in self.local_prices:
                    self.local_prices[aid][tid] = 1e9
                self.local_assignments[amv.amv_id] = (tid, 1e9, 1e9)

        amv_map = {a.amv_id: a for a in amvs}

        # Auction iterations
        iteration = 0
        for iteration in range(config.MAX_AUCTION_ITERATIONS):
            # Print debug print if STRESS_SCENARIO == 'comm_blackout'
            if config.STRESS_SCENARIO == 'comm_blackout' and config.STRESS_START_TIMESTEP <= current_timestep <= config.STRESS_END_TIMESTEP and config.ALLOCATOR_MODE == 'auction' and iteration == 0:
                plps = []
                for u, v in comms_mesh.graph.edges():
                    plps.append(comms_mesh.graph.edges[u, v].get('packet_loss_prob', 0.0))
                if plps:
                    avg_plp = sum(plps) / len(plps)
                    print(f"  [DEBUG AUCTION BLACKOUT] t={current_timestep}: Auction bid broadcast active with avg edge packet loss prob = {avg_plp:.2f}")

            # 1. Bidding Phase: each available AMV selects task maximizing benefit - local price
            new_bids_this_iter = {}  # {amv_id: (task_id, bid_value, benefit)}
            
            for amv in available_amvs:
                # If currently assigned to something, check if outbid in local prices
                curr_assign = self.local_assignments[amv.amv_id]
                if curr_assign is not None:
                    tid, bid, benefit = curr_assign
                    if self.local_prices[amv.amv_id].get(tid, 0.0) <= bid:
                        continue
                    else:
                        self.local_assignments[amv.amv_id] = None

                # Find best task to bid on
                best_val, best_task, best_benefit = -float("inf"), None, 0.0
                for task in auction_tasks:
                    benefit = compute_benefit(amv, task, tasks, amvs=amvs)
                    net_value = benefit - self.local_prices[amv.amv_id].get(task.task_id, 0.0)
                    if net_value > best_val:
                        best_val = net_value
                        best_task = task
                        best_benefit = benefit

                if best_task is not None and best_benefit > 0:
                    new_bid = self.local_prices[amv.amv_id].get(best_task.task_id, 0.0) + config.BENEFIT_EPSILON_A
                    new_bids_this_iter[amv.amv_id] = (best_task.task_id, new_bid, best_benefit)
                    self.local_assignments[amv.amv_id] = (best_task.task_id, new_bid, best_benefit)
                    self.local_prices[amv.amv_id][best_task.task_id] = new_bid
                elif best_task is not None and best_task.is_dummy:
                    new_bids_this_iter[amv.amv_id] = (best_task.task_id, 0.0, 0.0)
                    self.local_assignments[amv.amv_id] = (best_task.task_id, 0.0, 0.0)
                    self.local_prices[amv.amv_id][best_task.task_id] = 0.0

            # 2. Communication Phase: Broadcast new bids to neighbors
            for amv_id, bid_info in new_bids_this_iter.items():
                task_id, bid_value, _ = bid_info
                payload = {
                    "type": "auction",
                    "amv_id": amv_id,
                    "task_id": task_id,
                    "bid_value": bid_value,
                }
                for neighbor_id in comms_mesh.graph.neighbors(amv_id):
                    comms_mesh.send_message(
                        amv_id, neighbor_id, payload, current_timestep,
                    )

            # Deliver messages
            delivered = comms_mesh.deliver_messages(current_timestep)

            # 3. Consensus Phase: Update local prices based on received messages
            any_price_updated = False
            for receiver_id, payloads in delivered.items():
                for msg in payloads:
                    if msg.get("type") != "auction":
                        continue
                    tid = msg["task_id"]
                    bid_val = msg["bid_value"]
                    if tid in self.local_prices[receiver_id]:
                        if bid_val > self.local_prices[receiver_id][tid]:
                            self.local_prices[receiver_id][tid] = bid_val
                            any_price_updated = True

            # Deconflict: check if local assignments are outbid based on updated local prices
            for amv in available_amvs:
                curr_assign = self.local_assignments[amv.amv_id]
                if curr_assign is not None:
                    tid, bid, benefit = curr_assign
                    if self.local_prices[amv.amv_id].get(tid, 0.0) > bid:
                        self.local_assignments[amv.amv_id] = None
                        any_price_updated = True

            # If no new bids and no prices updated, converged
            if not new_bids_this_iter and not any_price_updated:
                break

        # Log iteration count
        self.auction_iteration_log.append(iteration + 1)

        # Check if local prices converged across all available AMVs
        consensus_converged = True
        if len(available_amvs) > 1:
            first_prices = self.local_prices[available_amvs[0].amv_id]
            for amv in available_amvs[1:]:
                if self.local_prices[amv.amv_id] != first_prices:
                    consensus_converged = False
                    break

        # Assign winning tasks based on local assignments for available AMVs
        task_map = {t.task_id: t for t in tasks}
        for d in dummy_tasks:
            task_map[d.task_id] = d

        for amv in available_amvs:
            assign = self.local_assignments.get(amv.amv_id)
            if assign is None:
                amv.assigned_task = None
                amv.enter_idle()
                continue

            task_id, bid, benefit = assign
            task = task_map.get(task_id)
            if task is None:
                continue

            if task.is_dummy:
                amv.assigned_task = None
                amv.enter_idle()
            else:
                if consensus_converged:
                    existing_assigned_amv_id = task.assigned_to
                    if existing_assigned_amv_id is not None and existing_assigned_amv_id != amv.amv_id:
                        # Conflict! Resolve by comparing bids
                        other_assign = self.local_assignments.get(existing_assigned_amv_id)
                        other_bid = other_assign[1] if other_assign else 0.0
                        if bid > other_bid:
                            # We outbid the existing one! Send outbid message via comms
                            payload = {
                                "type": "outbid",
                                "task_id": task.task_id,
                                "winner_id": amv.amv_id,
                                "bid_value": bid,
                            }
                            comms_mesh.send_message(
                                amv.amv_id, existing_assigned_amv_id, payload, current_timestep,
                            )
                            # Update locally
                            task.assigned_to = amv.amv_id
                            amv.assigned_task = task
                            amv.enter_reaching()
                        else:
                            amv.assigned_task = None
                            amv.enter_idle()
                    else:
                        task.status = "active"
                        task.assigned_to = amv.amv_id
                        amv.assigned_task = task
                        amv.enter_reaching()
                else:
                    # Consensus did not converge (e.g. comm_blackout)!
                    # Assign to task anyway without checking or resolving conflicts centrally
                    task.status = "active"
                    task.assigned_to = amv.amv_id
                    amv.assigned_task = task
                    amv.enter_reaching()

        # R5F2: Fallback — unassigned AMVs still in Assignment -> Idle
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

    def run_pausing_algorithm(self, amvs, tasks, comms_mesh, current_timestep):
        """
        Unilateral local pausing decision under deadlock.
        Each agent decides locally whether to soft-pause based on its own state.
        No broadcasts or rankings merging required.
        """
        paused_ids = []
        for amv in amvs:
            # Skip if already idle or serving or dead
            if amv.fsm_state in (config.FSM_IDLE, config.FSM_SERVING) or amv.energy <= 0:
                continue

            # Unilateral decision: pause self if degraded or faulted
            if amv.availability < config.BID_AVAILABILITY_THRESHOLD or amv.fault_state != "normal":
                if amv.assigned_task is not None:
                    amv.assigned_task.status = "unassigned"
                    amv.assigned_task.assigned_to = None
                    amv.assigned_task = None
                amv.enter_idle()
                amv.paused_until_timestep = current_timestep + 10
                paused_ids.append(amv.amv_id)
                print(f"  [LOCAL PAUSE] t={current_timestep}: AMV{amv.amv_id} unilaterally paused due to degradation under deadlock")

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

        # Initialize alert tracking
        has_alert = {amv.amv_id: (amv.fsm_state == config.FSM_DEADLOCK) for amv in amvs}

        # n iterations of max-consensus
        for l in range(1, n + 1):
            # Exchange via comms
            for amv in amvs:
                payload = {
                    "type": "edmc",
                    "amv_id": amv.amv_id,
                    "mb_prev": mb[amv.amv_id][l - 1],
                }
                if has_alert[amv.amv_id]:
                    payload["deadlock_alert"] = {
                        "type": "deadlock_alert",
                        "mt_before": self.mt,
                    }
                    payload["message_priority"] = "critical"
                
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
                        if "deadlock_alert" in msg:
                            has_alert[amv.amv_id] = True
                mb[amv.amv_id][l] = max_val

        # In a distributed system, a global deadlock is detected if the active AMVs reach consensus that max proposal is mt - 1
        active_amvs = [a for a in amvs if a.energy > 0]
        if not active_amvs:
            return False, []
            
        consensus_vals = [mb[a.amv_id][n] for a in active_amvs]
        all_equal = all(val == consensus_vals[0] for val in consensus_vals)
        
        global_deadlock = False
        if all_equal and consensus_vals[0] == self.mt - 1 and self.mt > 0:
            global_deadlock = True
            # Mark all active agents as alerted if consensus is reached
            for a in active_amvs:
                has_alert[a.amv_id] = True

        alerted_amvs = [amv_id for amv_id, val in has_alert.items() if val]
        return global_deadlock, alerted_amvs

    def handle_global_deadlock(self, amvs, tasks, comms_mesh, current_timestep):
        """
        On global deadlock: broadcast deadlock alert message to all agents.
        """
        mt_before = self.mt
        self.mt = max(0, self.mt - 1)

        # Queue deadlock alert to everyone with 3 retries (gossip-style)
        payload = {
            "type": "deadlock_alert",
            "mt_before": mt_before,
        }
        for sender in amvs:
            if sender.energy > 0:
                for receiver in amvs:
                    if receiver.amv_id != sender.amv_id:
                        self.pending_deadlock_alerts.append({
                            "sender_id": sender.amv_id,
                            "receiver_id": receiver.amv_id,
                            "payload": payload,
                            "retries_remaining": 3,
                            "last_sent_timestep": current_timestep
                        })

        # Log it
        self.deadlock_log.append({
            "timestep": current_timestep,
            "mt_before": mt_before,
            "mt_after": self.mt,
            "idled_amv": "alerted_gossip",
        })
        return None

    def process_pending_alerts(self, comms_mesh, current_timestep):
        """
        Retransmit pending deadlock alerts to neighbors (gossip-style retry).
        """
        still_pending = []
        for alert in self.pending_deadlock_alerts:
            # Attempt to send message
            comms_mesh.send_message(
                alert["sender_id"], alert["receiver_id"],
                alert["payload"], current_timestep
            )
            rem = alert["retries_remaining"] - 1
            if rem > 0:
                still_pending.append({
                    "sender_id": alert["sender_id"],
                    "receiver_id": alert["receiver_id"],
                    "payload": alert["payload"],
                    "retries_remaining": rem,
                    "last_sent_timestep": current_timestep
                })
        self.pending_deadlock_alerts = still_pending

    # ── Task completion handler ─────────────────────────────────────────────

    def handle_task_completion(self, amvs, tasks, comms_mesh, current_timestep,
                               completed_task_id, completing_amv_id):
        """
        After task completion: mt = min(mt+1, m, n), trigger reassignment.
        """
        m = len([t for t in tasks if t.status != "completed" and not t.is_dummy])
        n = len([a for a in amvs if a.energy > 0])
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
