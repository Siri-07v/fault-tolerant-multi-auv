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

RAW_CONGESTION_DROPS = 0


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
        self._message_queue = []  # list of (delivery_timestep, sender_id, receiver_id, payload)
        self._total_sent = 0
        self._total_dropped = 0
        self._thermocline_messages = 0     # messages subject to thermocline penalty
        self._ocean_env = ocean_env
        self._amv_depths = amv_depths or {}

        # Acoustic bandwidth constraint — per-link message budget
        self._per_link_counts = {}     # {(sender, receiver): count} per timestep
        self.congestion_drops = 0      # total messages dropped due to bandwidth

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

                    # Spatially variable thermocline
                    if self._ocean_env is not None:
                        thermo = self._ocean_env.local_thermocline(
                            (pa[0] + pb[0]) / 2.0, (pa[1] + pb[1]) / 2.0)
                    else:
                        thermo = config.THERMOCLINE_DEPTH
                    if (da < thermo and db > thermo) or (da > thermo and db < thermo):
                        plp = min(1.0, plp + config.THERMOCLINE_PENALTY)

                    self.graph.add_edge(
                        a, b,
                        distance=dist_3d,
                        latency_ms=self._latency_ms(dist_3d, avg_depth),
                        packet_loss_prob=plp,
                        thermocline_cross=((da < thermo) != (db < thermo)),
                        weight=1.0 - plp,
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

        # Acoustic bandwidth constraint — per-link message budget
        link_key = (sender_id, receiver_id)
        current_count = self._per_link_counts.get(link_key, 0)
        if current_count >= config.MAX_MESSAGES_PER_LINK:
            global RAW_CONGESTION_DROPS
            RAW_CONGESTION_DROPS += 1
            self.congestion_drops += 1
            self._total_dropped += 1
            return False
        self._per_link_counts[link_key] = current_count + 1

        edge = self.graph.edges[sender_id, receiver_id]
        plp = edge["packet_loss_prob"]

        # Track thermocline crossings
        if edge.get("thermocline_cross", False):
            self._thermocline_messages += 1

        # Bernoulli: success with prob (1 - plp)
        if config.ALLOCATOR_MODE in ("auction", "vanilla_auction"):
            is_critical = (isinstance(payload, dict) and 
                           (payload.get("type") in ("deadlock_alert", "outbid", "edmc") 
                            or payload.get("message_priority") == "critical"))
            if is_critical:
                # Extra retransmission attempt for critical recovery messages
                success = random.random() >= plp
                if not success:
                    success = random.random() >= plp
                if not success:
                    self._total_dropped += 1
                    return False
            else:
                if random.random() < plp:
                    self._total_dropped += 1
                    return False
        else:
            if random.random() < plp:
                self._total_dropped += 1
                return False

        latency = edge["latency_ms"]
        # Consensus/negotiation messages must be delivered synchronously within the same timestep
        msg_type = payload.get("type") if isinstance(payload, dict) else None
        if msg_type in ("auction", "pause_rank", "edmc", "cbba"):
            delivery_ts = current_timestep
        else:
            delivery_ts = current_timestep + math.ceil(latency / config.TIMESTEP_DURATION_MS)
        # Checksum / Tampering Logic
        if isinstance(payload, dict):
            # Determine if this message should be spoofed
            should_spoof = False
            msg_type = payload.get("type")
            spoof_messages = getattr(config, "SPOOF_MESSAGES", [])
            if msg_type in spoof_messages:
                should_spoof = True
            elif (sender_id, receiver_id) in spoof_messages or (receiver_id, sender_id) in spoof_messages:
                should_spoof = True
                
            from security.message_integrity import MessageIntegrityVerifier
            if should_spoof:
                spoof_mode = getattr(config, "SPOOF_MODE", None)
                if spoof_mode == "corrupt_payload":
                    payload = payload.copy()
                    if payload.get("type") == "auction" and sender_id == 1:
                        payload["bid_value"] = 999.0
                        spoofed_tid = getattr(config, "SPOOFED_TASK_ID", None)
                        if spoofed_tid is not None:
                            payload["task_id"] = spoofed_tid
                    payload["checksum"] = MessageIntegrityVerifier.generate_checksum(payload)
                elif spoof_mode == "bypass_checksum":
                    payload = payload.copy()
                    payload["checksum"] = MessageIntegrityVerifier.generate_checksum(payload)
                    if payload.get("type") == "auction" and sender_id == 1:
                        payload["bid_value"] = 999.0
                        spoofed_tid = getattr(config, "SPOOFED_TASK_ID", None)
                        if spoofed_tid is not None:
                            payload["task_id"] = spoofed_tid
            else:
                payload = payload.copy()
                payload["checksum"] = MessageIntegrityVerifier.generate_checksum(payload)

        self._message_queue.append((delivery_ts, sender_id, receiver_id, payload))
        return True

    def deliver_messages(self, current_timestep):
        """
        Return {receiver_id: [payloads]} for all messages ready for delivery.
        """
        # Reset per-link bandwidth counts once per simulation timestep
        if getattr(self, "_last_reset_timestep", -1) != current_timestep:
            self._per_link_counts = {}
            self._last_reset_timestep = current_timestep

        ready = defaultdict(list)
        remaining = []
        for delivery_ts, sender_id, receiver_id, payload in self._message_queue:
            if delivery_ts <= current_timestep:
                from security.message_integrity import MessageIntegrityVerifier
                is_valid = True
                if isinstance(payload, dict):
                    is_valid = MessageIntegrityVerifier.verify_checksum(payload)
                    if not is_valid:
                        print(f"  [CHECKSUM FAILURE] t={current_timestep}: Message from AMV{sender_id} to AMV{receiver_id} failed integrity verification! Dropping payload: {payload}")
                
                if is_valid:
                    ready[receiver_id].append(payload)
                else:
                    self._total_dropped += 1
            else:
                remaining.append((delivery_ts, sender_id, receiver_id, payload))
        self._message_queue = remaining

        # Priority sorting: place critical messages at the front of the per-timestep queue
        if config.ALLOCATOR_MODE in ("auction", "vanilla_auction"):
            for receiver_id in ready:
                ready[receiver_id].sort(
                    key=lambda msg: 0 if (isinstance(msg, dict) and 
                                          (msg.get("type") in ("deadlock_alert", "outbid", "edmc") 
                                           or msg.get("message_priority") == "critical")) else 1
                )

        return dict(ready)

    def get_graph_snapshot(self):
        """Return a copy of the current graph for visualization."""
        return self.graph.copy()

    def log_packet_stats(self):
        """Return total sent, total dropped, drop rate, thermocline count, and congestion."""
        drop_rate = self._total_dropped / max(self._total_sent, 1)
        return {
            "total_sent": self._total_sent,
            "total_dropped": self._total_dropped,
            "drop_rate": drop_rate,
            "thermocline_messages": self._thermocline_messages,
            "congestion_drops": self.congestion_drops,
        }

    def algebraic_connectivity(self):
        """Estimate algebraic connectivity (λ₂) of the current graph."""
        if self.graph.number_of_nodes() < 2:
            return 0.0
        
        # Create a filtered copy of the graph keeping only reliable links
        reliable_graph = nx.Graph()
        reliable_graph.add_nodes_from(self.graph.nodes())
        for u, v, d in self.graph.edges(data=True):
            w = d.get('weight', 1.0)
            # Link is reliable if packet loss probability is below 85%
            if w >= 0.15:
                reliable_graph.add_edge(u, v, weight=w)
                
        if not nx.is_connected(reliable_graph):
            return 0.0
        try:
            # Construct dense Laplacian manually for speed
            nodes = sorted(list(reliable_graph.nodes()))
            n = len(nodes)
            node_to_idx = {node: idx for idx, node in enumerate(nodes)}
            L = np.zeros((n, n))
            for u, v, d in reliable_graph.edges(data=True):
                w = d.get('weight', 1.0)
                ui = node_to_idx[u]
                vi = node_to_idx[v]
                L[ui, vi] = -w
                L[vi, ui] = -w
                L[ui, ui] += w
                L[vi, vi] += w
            
            # Compute eigenvalues (sorted ascending)
            eigenvalues = np.linalg.eigvalsh(L)
            if len(eigenvalues) >= 2:
                return float(eigenvalues[1])
            return 0.0
        except Exception:
            return 0.0
