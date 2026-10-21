# Threat Model Document: Cyber-Physical Security for Multi-AUV Swarms

This document outlines the formal cyber-physical threat model for the decentralized multi-AUV task allocation framework. It establishes the security boundaries, adversary capabilities, attack surface mapping, and current mitigations, and documents residual risks.

---

## 1. Adversary Capabilities & Threat Actors

The framework is evaluated against three distinct threat actors:

1. **External Acoustic Intruder (Outsider Threat)**
   - **Access:** Direct access to the acoustic underwater transmission medium.
   - **Capabilities:** Can capture acoustic packets, inject arbitrary messages (e.g., falsified bids, fake consensus claims, or spoofed deadlock alerts), and attempt replay or spoofing attacks.
   - **Limitations:** Does not possess valid cryptographic keys or credentials. Cannot access internal vehicle hardware.

2. **Compromised Swarm Vehicle (Insider Threat)**
   - **Access:** Legitimate member of the swarm (e.g., AMV1) with valid cryptographic keys and active communication links.
   - **Capabilities:** Can manipulate internal software states, state labels, and sensor telemetry. Can broadcast falsified bid values, state declarations, or task priorities to exploit the bidding consensus protocol.
   - **Limitations:** Physical performance is bound by its hardware state (e.g., degraded actuators physically restrict speed). Cannot rewrite the cryptographic modules of neighboring agents.

3. **GPS Surface Spoofer (Outsider Threat)**
   - **Access:** Direct transmission of RF signals over GPS channels.
   - **Capabilities:** Can transmit forged GPS coordinate fixes with arbitrary offsets (e.g., 50m, 200m) to surfacing AUVs.
   - **Limitations:** Only effective when vehicles ascend to the surface layer ($<10$m depth). Cannot intercept internal acoustic messages.

---

## 2. 5-Layer Cyber-Physical Attack Surface Mapping

The vulnerabilities of the multi-AUV swarm are categorized into five layers:

```
+--------------------------------------------------------+
| 5. Coordination Layer (Consensus Hijacking / Bid Fraud)|
+--------------------------+-----------------------------+
                           |
+--------------------------v-----------------------------+
| 4. Network Layer      (Acoustic Injection / Tampering) |
+--------------------------+-----------------------------+
                           |
+--------------------------v-----------------------------+
| 3. Control Layer      (FSM Hijacking / Fault Masking)  |
+--------------------------+-----------------------------+
                           |
+--------------------------v-----------------------------+
| 2. Sensor Layer       (DVL Drift / GPS Spoofing)       |
+--------------------------+-----------------------------+
                           |
+--------------------------v-----------------------------+
| 1. Physical Layer     (Actuator Wear / Load Injection) |
+--------------------------------------------------------+
```

### 2.1 Physical Layer
- **Description:** Structural AUV hardware and environment.
- **Attacks/Faults:** Mechanical actuator degradation (propeller damage), physical hull loading (weight accumulation), and environmental disturbances (thermocline boundary crossing, drag).

### 2.2 Sensor Layer
- **Description:** Doppler Velocity Log (DVL), pressure depth sensors, and GPS receivers.
- **Attacks/Faults:** legitimate DVL dead-reckoning drift over long dives; adversarial GPS signal spoofing at surfacing boundaries injecting static offsets.

### 2.3 Computation & Control Layer
- **Description:** Finite State Machine (FSM) control loop and 1D-CNN fault classifier.
- **Attacks/Faults:** Local fault classifier evasion; Byzantine software overriding declared states (e.g., masking severe degradation as normal).

### 2.4 Network & Communications Layer
- **Description:** Acoustic transceivers and packet queues.
- **Attacks/Faults:** Packet tampering, bid injection, and alert forgery.

### 2.5 Coordination & Application Layer
- **Description:** Bidding consensus (CBBA or Price Auction) and EDMC deadlock resolution.
- **Attacks/Faults:** Consensus hijacking via falsified bids; artificial deadlock alerts; task monopoly by compromised nodes.

---

## 3. Mitigation Mapping

The security layer maps specific defense mechanisms to the attack surfaces:

| Threat Vector | Affected Layer | Primary Mitigation | Secondary Mitigation |
| :--- | :--- | :--- | :--- |
| **External Injection** | Network (4) | **HMAC-SHA256 Signatures:** Dropped immediately on checksum failure. | *None* (crypto drop) |
| **Fault Masking** | Coordination (5) | **TrustScore Tracker:** Decays reputation on speed-to-declared mismatch. | **Rule 3 (Energy Floor):** Rejection of task bids exceeding capacity. |
| **Task Monopolization** | Control (3) | **Rule 1 (Speed Cap):** Enforces limits matching physical state. | **Rule 6 (Priority Override):** Relieves idle lockouts. |
| **GPS Spoofing** | Sensor (2) | **DVL-GPS Cross-Check:** Rejects GPS fixes exceeding drift threshold. | **Rule 3 (Energy Floor):** Safety veto on corrupted position estimate. |

---

## 4. Residual and Untested Risks

Several threat vectors remain outside the scope of current mitigations:

1. **Collusive Consensus Manipulation:** Multiple compromised insider nodes coordinate bids to bypass TrustScore and monopoly rules.
2. **Acoustic Denial of Service (DoS):** Jamming the acoustic channel, preventing max-consensus vector convergence in EDMC.
3. **Sybil Attacks:** A compromised agent fabricates virtual nodes to distort consensus and capture a disproportionate share of tasks.
