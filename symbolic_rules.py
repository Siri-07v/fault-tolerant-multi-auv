"""
symbolic_rules.py — Neuro-symbolic reasoning layer for the AUV swarm simulation.
Implements 8 symbolic safety / operational rules that gate and modify AMV actions
based on fault state, energy, depth, CNN confidence, and fleet-wide health.

Usage:
    from symbolic_rules import SymbolicRuleEngine, RuleVerdict, log_verdict
"""
from dataclasses import dataclass, field
from typing import Any, List, Optional

import numpy as np

import config


# ─── Section 1: RuleVerdict Dataclass ──────────────────────────────────────────

@dataclass
class RuleVerdict:
    """Result of a single symbolic rule evaluation."""
    allowed: bool
    rule_name: str
    reason: str
    modification: dict = field(default_factory=dict)


# ─── Section 2: SymbolicRuleEngine ─────────────────────────────────────────────

class SymbolicRuleEngine:
    """
    Eight symbolic rules that wrap around the existing CNN + auction pipeline.
    Rules are pure functions of AMV / Task state and produce RuleVerdict objects.
    """

    def __init__(self) -> None:
        self.rule_log: List[dict] = []
        self.fleet_audit_strikes: int = 0
        self.audit_history: List[bool] = []

    # ── Rule 1 — Speed Cap ──────────────────────────────────────────────────

    def check_speed_cap(self, amv: Any) -> RuleVerdict:
        """Enforce hard speed limits based on fault state."""
        fault_to_max_speed = {
            "normal": 5.0,
            "load_fault": 4.0,
            "actuator_degraded_mild": 3.0,
            "actuator_degraded_severe": 1.5,
            "sensor_failure": 1.5,
        }
        fault = getattr(amv, "fault_state", "normal")
        limit = fault_to_max_speed.get(fault, 5.0)
        return RuleVerdict(
            allowed=True,
            rule_name="speed_cap",
            reason=f"Fault state {fault} enforces max speed {limit} m/timestep",
            modification={"max_speed": limit},
        )

    # ── Rule 2 — Depth Entry Veto ───────────────────────────────────────────

    def check_depth_entry_veto(self, amv: Any) -> RuleVerdict:
        """Block dangerous deep dives when sensors are compromised."""
        fault = getattr(amv, "fault_state", "normal")
        depth = getattr(amv, "depth", 0.0)
        threshold = config.THERMOCLINE_DEPTH * 0.9

        if fault == "sensor_failure" and depth > threshold:
            return RuleVerdict(
                allowed=False,
                rule_name="depth_entry_veto",
                reason=(
                    f"sensor_failure active: depth entry below thermocline "
                    f"blocked at depth {depth:.1f}m"
                ),
            )
        return RuleVerdict(
            allowed=True,
            rule_name="depth_entry_veto",
            reason=f"Depth {depth:.1f}m within safe limits for fault state {fault}",
        )

    # ── Rule 3 — Energy Floor ───────────────────────────────────────────────

    def check_energy_floor(self, amv: Any, task: Any, remaining_tasks: int = 15) -> RuleVerdict:
        """Veto task assignment if AMV cannot complete it with safe energy reserve."""
        ENERGY_PER_METER = 0.05
        # Relax reserve when near the end of the mission
        SAFE_RESERVE = 10.0 if remaining_tasks <= 3 else 20.0

        est_pos = getattr(amv, "estimated_position", None)
        amv_pos = getattr(amv, "position", None)
        task_pos = getattr(task, "position", None)

        # Use estimated position (DVL-aware), fallback to true position
        pos = est_pos if est_pos is not None else amv_pos
        if pos is None or task_pos is None:
            return RuleVerdict(
                allowed=True,
                rule_name="energy_floor",
                reason="Position data unavailable, allowing by default",
            )

        distance = float(np.linalg.norm(pos - task_pos))
        energy_needed = distance * ENERGY_PER_METER
        energy = getattr(amv, "energy", 100.0)

        if energy - energy_needed < SAFE_RESERVE:
            return RuleVerdict(
                allowed=False,
                rule_name="energy_floor",
                reason=(
                    f"Insufficient energy: need {energy_needed:.1f}%, "
                    f"have {energy:.1f}%, reserve {SAFE_RESERVE:.1f}%"
                ),
            )
        return RuleVerdict(
            allowed=True,
            rule_name="energy_floor",
            reason=(
                f"Energy OK: need {energy_needed:.1f}%, "
                f"have {energy:.1f}%, reserve {SAFE_RESERVE:.1f}%"
            ),
        )

    # ── Rule 4 — Confidence Gate ────────────────────────────────────────────

    def check_confidence_gate(self, amv: Any) -> RuleVerdict:
        """Suppress bidding when CNN classification confidence is low."""
        CONFIDENCE_THRESHOLD = 0.60

        probs = getattr(amv, "_last_fault_probs", None)
        confidence = float(np.max(probs)) if probs is not None else 1.0

        if confidence < CONFIDENCE_THRESHOLD:
            return RuleVerdict(
                allowed=False,
                rule_name="confidence_gate",
                reason=(
                    f"CNN confidence {confidence*100:.1f}% below threshold, "
                    f"bid suppressed for safety"
                ),
                modification={"suppress_bid": True},
            )
        return RuleVerdict(
            allowed=True,
            rule_name="confidence_gate",
            reason=f"CNN confidence {confidence*100:.1f}% above threshold",
        )

    # ── Rule 5 — Collision Radius ───────────────────────────────────────────

    def check_collision_radius(
        self, amv: Any, all_amvs: List[Any], task: Any
    ) -> RuleVerdict:
        """Prevent two AMVs from being assigned tasks within collision radius."""
        COLLISION_RADIUS = 50.0
        amv_id = getattr(amv, "amv_id", -1)
        task_pos = getattr(task, "position", None)
        task_id = getattr(task, "task_id", -1)

        if task_pos is None:
            return RuleVerdict(
                allowed=True,
                rule_name="collision_radius",
                reason="Task position unavailable, allowing by default",
            )

        for other in all_amvs:
            other_id = getattr(other, "amv_id", -1)
            if other_id == amv_id:
                continue
            other_task = getattr(other, "assigned_task", None)
            if other_task is None:
                continue
            other_task_id = getattr(other_task, "task_id", -1)
            if other_task_id == task_id:
                continue
            other_task_pos = getattr(other_task, "position", None)
            if other_task_pos is None:
                continue

            dist = float(np.linalg.norm(task_pos - other_task_pos))
            if dist < COLLISION_RADIUS:
                return RuleVerdict(
                    allowed=False,
                    rule_name="collision_radius",
                    reason=(
                        f"Task {task_id} within {dist:.1f}m collision radius "
                        f"of AMV {other_id}'s task {other_task_id}"
                    ),
                )

        return RuleVerdict(
            allowed=True,
            rule_name="collision_radius",
            reason=f"No collision conflict for task {task_id}",
        )

    # ── Rule 6 — Priority Override ──────────────────────────────────────────

    def check_priority_override(
        self, task: Any, amvs: List[Any]
    ) -> RuleVerdict:
        """Force highest-availability AMV to take critically waiting tasks."""
        CRITICAL_WAIT = 40

        wait = getattr(task, "waiting_time", 0)
        status = getattr(task, "status", "")
        task_id = getattr(task, "task_id", -1)

        if wait > CRITICAL_WAIT and status == "unassigned":
            # Find best AMV in Idle or Assignment state
            candidates = [
                a for a in amvs
                if getattr(a, "fsm_state", "") in ("Idle", "Assignment")
            ]
            if candidates:
                best = max(candidates, key=lambda a: getattr(a, "availability", 0.0))
                best_id = getattr(best, "amv_id", -1)
                return RuleVerdict(
                    allowed=True,
                    rule_name="priority_override",
                    reason=(
                        f"Task {task_id} waited {wait} timesteps, "
                        f"forcing assignment to AMV {best_id}"
                    ),
                    modification={"force_assign_to": best_id},
                )

        return RuleVerdict(
            allowed=True,
            rule_name="priority_override",
            reason=f"Task {task_id} wait {wait} within normal range",
        )

    # ── Rule 7 — Fleet Audit ────────────────────────────────────────────────

    def run_fleet_audit(self, all_amvs: List[Any]) -> RuleVerdict:
        """Detect fleet-wide degradation and halt new assignments if critical."""
        degraded_states = {"actuator_degraded_severe", "sensor_failure"}
        degraded_count = sum(
            1
            for a in all_amvs
            if getattr(a, "fault_state", "normal") in degraded_states
        )
        n = len(all_amvs)
        is_critical = degraded_count >= 3

        self.audit_history.append(is_critical)

        if is_critical:
            self.fleet_audit_strikes += 1
            return RuleVerdict(
                allowed=False,
                rule_name="fleet_audit",
                reason=(
                    f"Fleet critical: {degraded_count}/{n} AMVs degraded. "
                    f"Halting new assignments."
                ),
                modification={"halt_assignments": True},
            )
        else:
            self.fleet_audit_strikes = 0
            return RuleVerdict(
                allowed=True,
                rule_name="fleet_audit",
                reason=f"Fleet nominal: {degraded_count}/{n} AMVs degraded",
            )

    # ── Rule 8 — Escalation Flag ────────────────────────────────────────────

    def check_escalation(self) -> RuleVerdict:
        """Flag that human intervention is recommended after repeated crises."""
        ESCALATION_THRESHOLD = 3

        if self.fleet_audit_strikes >= ESCALATION_THRESHOLD:
            return RuleVerdict(
                allowed=False,
                rule_name="escalation_flag",
                reason=(
                    f"ESCALATION: Fleet audit failed {self.fleet_audit_strikes} "
                    f"consecutive times. Human intervention recommended."
                ),
                modification={"human_flag": True},
            )
        return RuleVerdict(
            allowed=True,
            rule_name="escalation_flag",
            reason=(
                f"Escalation not triggered "
                f"({self.fleet_audit_strikes} consecutive strikes)"
            ),
        )

    # ── Master Evaluation Methods ───────────────────────────────────────────

    def _log_verdict(
        self, verdict: RuleVerdict, amv_id: Optional[int] = None
    ) -> None:
        """Append a verdict to the internal rule_log."""
        self.rule_log.append({
            "timestep": None,
            "amv_id": amv_id,
            "rule": verdict.rule_name,
            "allowed": verdict.allowed,
            "reason": verdict.reason,
            "modification": verdict.modification,
        })

    def evaluate_pre_assignment(
        self, amv: Any, task: Any, all_amvs: List[Any], remaining_tasks: int = 15
    ) -> List[RuleVerdict]:
        """Run rules 2, 3, 4, 5, 6 before task assignment."""
        amv_id = getattr(amv, "amv_id", None)
        verdicts: List[RuleVerdict] = []

        for rule_fn in [
            lambda: self.check_depth_entry_veto(amv),
            lambda: self.check_energy_floor(amv, task, remaining_tasks),
            lambda: self.check_confidence_gate(amv),
            lambda: self.check_collision_radius(amv, all_amvs, task),
            lambda: self.check_priority_override(task, all_amvs),
        ]:
            v = rule_fn()
            self._log_verdict(v, amv_id)
            verdicts.append(v)

        return verdicts

    def evaluate_post_fault(self, amv: Any) -> List[RuleVerdict]:
        """Run rules 1 and 2 after fault detection."""
        amv_id = getattr(amv, "amv_id", None)
        verdicts: List[RuleVerdict] = []

        # Rule 1
        v1 = self.check_speed_cap(amv)
        self._log_verdict(v1, amv_id)
        verdicts.append(v1)

        # Rule 2 (only run if state is sensor_failure)
        if getattr(amv, "fault_state", "normal") == "sensor_failure":
            v2 = self.check_depth_entry_veto(amv)
            self._log_verdict(v2, amv_id)
            verdicts.append(v2)

        return verdicts

    def evaluate_fleet(self, all_amvs: List[Any]) -> List[RuleVerdict]:
        """Run rule 7 (fleet audit) then rule 8 (escalation)."""
        verdicts: List[RuleVerdict] = []

        v7 = self.run_fleet_audit(all_amvs)
        self._log_verdict(v7)
        verdicts.append(v7)

        v8 = self.check_escalation()
        self._log_verdict(v8)
        verdicts.append(v8)

        return verdicts

    def is_assignment_safe(
        self, amv: Any, task: Any, all_amvs: List[Any], remaining_tasks: int = 15
    ) -> bool:
        """Return True only if no pre-assignment rule issues a veto."""
        verdicts = self.evaluate_pre_assignment(amv, task, all_amvs, remaining_tasks)
        return all(v.allowed for v in verdicts)

    def get_speed_cap(self, amv: Any) -> float:
        """Return the speed cap for the given AMV based on its fault state."""
        verdict = self.check_speed_cap(amv)
        return verdict.modification.get("max_speed", 5.0)

    def get_rule_log_summary(self) -> dict:
        """Return aggregate statistics of all rules fired so far."""
        by_rule: dict = {}
        vetoes = 0
        modifications = 0

        for entry in self.rule_log:
            name = entry["rule"]
            by_rule[name] = by_rule.get(name, 0) + 1
            if not entry["allowed"]:
                vetoes += 1
            if entry["modification"]:
                modifications += 1

        return {
            "total_rules_fired": len(self.rule_log),
            "vetoes": vetoes,
            "modifications": modifications,
            "by_rule": by_rule,
            "escalation_strikes": self.fleet_audit_strikes,
        }


# ─── Section 3: Logging Utility ───────────────────────────────────────────────

def log_verdict(verdict: RuleVerdict, timestep: int, amv_id: int) -> None:
    """Print a formatted line for non-trivial verdicts (vetoes or modifications)."""
    if not verdict.allowed or verdict.modification:
        status = "VETO" if not verdict.allowed else "OK"
        print(
            f"[T={timestep}] AMV{amv_id} | Rule:{verdict.rule_name} | "
            f"{status} | {verdict.reason}"
        )
