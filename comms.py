"""
comms.py — Depth-aware underwater acoustic communication mesh.
Physics-based: depth-dependent range, latency via Mackenzie sound speed,
thermocline packet loss penalty, message queuing.
"""
import math
from collections import defaultdict
import random
import networkx as nx
import numpy as np

import config


class CommsMesh:
    """Dynamic acoustic communication graph for AMV swarm."""

    def __init__(self, amv_positions: dict, amv_depths: dict = None,
                 ocean_env=None):
        """
        Args:
            amv_positions: {amv_id: (x, y)}
            amv_depths:    {amv_id: depth_m}  — optional, default 0
            ocean_env:     OceanEnvironment instance — optional
        """
        self.graph = nx.Graph()
        self._message_queue = []  # list of (delivery_timestep, receiver_id, payload)
        self._total_sent = 0
        self._total_dropped = 0
        self._thermocline_messages = 0     # messages subject to thermocline penalty
        self._ocean_env = ocean_env
        self._amv_depths = amv_depths or {}
        self.rebuild_graph(amv_positions, amv_depths)

    # ── Graph construction ──────────────────────────────────────────────────

    @staticmethod
    def _packet_loss_prob(distance, effective_range=None):
        """Sigmoid packet loss: near 0 below 70% range, rises steeply beyond."""
        rng = effective_range or config.ACOUSTIC_RANGE
        exponent = -(distance - 0.7 * rng) / 300.0
        return 1.0 / (1.0 + math.exp(exponent))

    def _latency_ms(self, distance_3d, avg_depth=0.0):
        """Latency from 3D distance / depth-dependent sound speed."""
        if self._ocean_env is not None:
            ss = self._ocean_env.sound_speed(avg_depth)
        else:
            ss = config.SOUND_SPEED
        return (distance_3d / ss) * 1000.0

    def _effective_range(self, avg_depth):
        """Interpolated acoustic range: surface → deep."""
        if self._ocean_env is not None:
            return self._ocean_env.effective_acoustic_range(avg_depth)
        return config.ACOUSTIC_RANGE

    def rebuild_graph(self, amv_positions: dict, amv_depths: dict = None):
        """Rebuild the full communication graph from current AMV positions."""
        self.graph.clear()
        if amv_depths is not None:
            self._amv_depths = amv_depths
        ids = list(amv_positions.keys())
        for aid in ids:
            self.graph.add_node(aid, pos=amv_positions[aid])

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                pa = np.array(amv_positions[a])
                pb = np.array(amv_positions[b])
                dist_2d = float(np.linalg.norm(pa - pb))

                # 3D distance including depth
                da = self._amv_depths.get(a, 0.0)
                db = self._amv_depths.get(b, 0.0)
                dist_3d = math.sqrt(dist_2d**2 + (da - db)**2)
                avg_depth = (da + db) / 2.0

                eff_range = self._effective_range(avg_depth)
                if dist_3d < eff_range:
                    plp = self._packet_loss_prob(dist_3d, eff_range)

                    # Thermocline penalty
                    thermo = config.THERMOCLINE_DEPTH
                    if (da < thermo and db > thermo) or (da > thermo and db < thermo):
                        plp = min(1.0, plp + config.THERMOCLINE_PENALTY)

                    self.graph.add_edge(
                        a, b,
                        distance=dist_3d,
                        latency_ms=self._latency_ms(dist_3d, avg_depth),
                        packet_loss_prob=plp,
                        thermocline_cross=((da < thermo) != (db < thermo)),
                    )

    # ── Messaging ───────────────────────────────────────────────────────────

    def send_message(self, sender_id, receiver_id, payload, current_timestep):
        """
        Attempt to send a message.  Returns True if queued, False if dropped.
        """
        self._total_sent += 1

        if not self.graph.has_edge(sender_id, receiver_id):
            self._total_dropped += 1
            return False

        edge = self.graph.edges[sender_id, receiver_id]
        plp = edge["packet_loss_prob"]

        # Track thermocline crossings
        if edge.get("thermocline_cross", False):
            self._thermocline_messages += 1

        # Bernoulli: success with prob (1 - plp)
        if random.random() < plp:
            self._total_dropped += 1
            return False

        latency = edge["latency_ms"]
        delivery_ts = current_timestep + math.ceil(latency / config.TIMESTEP_DURATION_MS)
        self._message_queue.append((delivery_ts, receiver_id, payload))
        return True

    def deliver_messages(self, current_timestep):
        """
        Return {receiver_id: [payloads]} for all messages ready for delivery.
        """
        ready = defaultdict(list)
        remaining = []
        for delivery_ts, receiver_id, payload in self._message_queue:
            if delivery_ts <= current_timestep:
                ready[receiver_id].append(payload)
            else:
                remaining.append((delivery_ts, receiver_id, payload))
        self._message_queue = remaining
        return dict(ready)

    def get_graph_snapshot(self):
        """Return a copy of the current graph for visualization."""
        return self.graph.copy()

    def log_packet_stats(self):
        """Return total sent, total dropped, drop rate, and thermocline count."""
        drop_rate = self._total_dropped / max(self._total_sent, 1)
        return {
            "total_sent": self._total_sent,
            "total_dropped": self._total_dropped,
            "drop_rate": drop_rate,
            "thermocline_messages": self._thermocline_messages,
        }

    def algebraic_connectivity(self):
        """Estimate algebraic connectivity (λ₂) of the current graph."""
        if self.graph.number_of_nodes() < 2:
            return 0.0
        if not nx.is_connected(self.graph):
            return 0.0
        try:
            return float(nx.algebraic_connectivity(self.graph))
        except Exception:
            return 0.0
