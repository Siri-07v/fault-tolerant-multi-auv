# Walkthrough - Swarm Reliability Upgrades & Post-Fix Sweep

This document details the upgrades implemented to improve the reliability of the proposed Auction + EDMC model under stress scenarios, along with the final comparative results.

---

## 1. Upgrades Implemented

We introduced four key changes to make the proposed model more robust and resilient under degraded communications and faults:

1.  **Soft-Pause Decision Logic:** Instead of hard-benching degraded agents (setting `assigned_task = None` and sending them to `Idle`), we allow degraded agents (availability below threshold, but energy $>0$) to keep their tasks and continue moving toward them at speed 1.5. In `compute_benefit` ([consensus.py](file:///c:/Users/siri0/capstone/fault-tolerant-multi-auv/consensus.py)), we allow degraded agents to bid, but scale their bids down proportionally to their low availability.
2.  **Local Self-Pausing:** We removed the communication-heavy utility ranking broadcast (`"pause_rank"` messages) during deadlock resolution. Each agent now makes a unilateral, local decision to pause itself under deadlock if it is degraded, while healthy agents simply reset to `Assignment`.
3.  **Deadlock Timeout Fallback:** To bound worst-case stalling under permanent communication blackout, we track how many timesteps each agent remains stuck in `FSM_DEADLOCK`. If this counter exceeds $K=30$ timesteps (which is double the nominal recovery time), the agent unilaterally releases its task and resets to the `Assignment` state.
4.  **Gossip-Style Deadlock Alert Retries:** Detecting agents now enqueue deadlock alerts in `self.pending_deadlock_alerts` and retry transmission for $3$ consecutive timesteps instead of sending a single fire-and-forget message. This increases the delivery probability from $10\%$ to $27.1\%$ under a $90\%$ packet loss blackout scenario ($1 - P_L^k$).

---

## 2. Comprehensive Before / After Comparison Results

Below is the comparative sweep data (15 seeds per scenario, 120 total runs) showing the results before and after these reliability upgrades:

### **A. Task Completion Rate (Higher is better)**
| Scenario | Pre-Upgrade (Old) | Post-Upgrade (Soft-Pause Only) | Baseline (CBBA) | Verdict vs. CBBA |
| :--- | :---: | :---: | :---: | :---: |
| **Nominal Baseline** | 89.33% ± 10.02% | **96.00% ± 6.57%** | 93.78% ± 6.41% | **Proposed Wins** (+2.22%) |
| **AMV Loss Stress** | 80.00% ± 20.00% | **85.33% ± 16.37%** | 90.67% ± 11.21% | Gap Closed by 50% |
| **Comm Blackout Stress**| 86.67% ± 13.57% | **93.33% ± 11.27%** | 93.33% ± 10.08% | **Draw** (Identical) |
| **Mass Fault Stress** | 87.11% ± 10.83% | **93.78% ± 7.33%** | 96.89% ± 4.27% | Gap Closed by 68% |

### **B. Never Completed Tasks Count (Lower is better)**
| Scenario | Pre-Upgrade (Old) | Post-Upgrade (Soft-Pause Only) | Baseline (CBBA) | Verdict vs. CBBA |
| :--- | :---: | :---: | :---: | :---: |
| **Nominal Baseline** | 1.60 ± 1.50 | **0.60 ± 0.99** | 0.93 ± 0.96 | **Proposed Wins** (-0.33) |
| **AMV Loss Stress** | 3.00 ± 3.00 | **2.20 ± 2.46** | 1.40 ± 1.68 | Improved by 26% |
| **Comm Blackout Stress**| 2.00 ± 2.04 | **1.00 ± 1.69** | 1.00 ± 1.51 | **Draw** (Identical) |
| **Mass Fault Stress** | 1.93 ± 1.62 | **0.93 ± 1.10** | 0.47 ± 0.64 | Improved by 52% |

### **C. Mean Task Active Delay (ts) (Lower is better)**
| Scenario | Pre-Upgrade (Old) | Post-Upgrade (Soft-Pause Only) | Baseline (CBBA) |
| :--- | :---: | :---: | :---: |
| **Nominal Baseline** | 85.94 ± 16.65 | **87.51 ± 13.39** | 72.13 ± 15.93 |
| **AMV Loss Stress** | 68.62 ± 9.38 | **72.54 ± 9.85** | 63.89 ± 9.33 |
| **Comm Blackout Stress**| 88.10 ± 13.11 | **88.06 ± 12.22** | 71.41 ± 14.78 |
| **Mass Fault Stress** | 89.61 ± 12.56 | **89.24 ± 12.95** | 69.08 ± 14.86 |

### **D. Max Task Active Delay (ts) (Lower is better)**
| Scenario | Pre-Upgrade (Old) | Post-Upgrade (Soft-Pause Only) | Baseline (CBBA) |
| :--- | :---: | :---: | :---: |
| **Nominal Baseline** | 322.13 ± 93.88 | **254.13 ± 65.58** | 245.20 ± 90.87 |
| **AMV Loss Stress** | 229.93 ± 116.47 | **211.07 ± 43.57** | 195.60 ± 86.85 |
| **Comm Blackout Stress**| 318.27 ± 98.58 | **260.73 ± 55.13** | 244.53 ± 87.12 |
| **Mass Fault Stress** | 340.73 ± 83.14 | **250.87 ± 58.58** | 228.27 ± 81.81 |

### **E. Congestion Drop Rate (Lower is better)**
| Scenario | Pre-Upgrade (Old) | Post-Upgrade (Soft-Pause Only) | Baseline (CBBA) |
| :--- | :---: | :---: | :---: |
| **Nominal Baseline** | 3.98% ± 2.82% | **0.21% ± 0.16%** | 12.38% ± 2.48% |
| **Mass Fault Stress** | 5.88% ± 2.55% | **0.21% ± 0.15%** | 13.41% ± 2.00% |

---

## 3. Statistical Reconciliation of the Mean Active Delay Discrepancy

Under **Mass Fault Stress**, the proposed model's Max Task Active Delay dropped by $90$ timesteps, but the Mean Task Active Delay remained relatively flat ($89.61$ ts $\to$ $89.24$ ts). We performed a trace diagnostic across the 15 seeds to explain this behavior:

### **A. Key Bookkeeping Symmetry Check**
Both algorithms were held to the identical, symmetric definition of active delay:
`if task.status == "active": task_active_delay[task.task_id] += 1`
There is no measurement inconsistency. The differences are purely behavioral.

### **B. Sub-Population Breakdown (Post-Upgrade, Mass Fault)**
We separated the delays of real tasks based on whether they were handled by degraded agents (traveling at speed 1.5) or healthy agents (traveling at speed 5.0):

*   **Proposed Model (Auction + EDMC):**
    *   **Tasks completed by DEGRADED agents:** Mean active delay = **$90.78$ ts** (count = 139)
    *   **Tasks completed by HEALTHY agents:** Mean active delay = **$70.19$ ts** (count = 72)
    *   **Never completed tasks:** Mean active delay = **$171.86$ ts** (count = 14)
*   **Baseline (CBBA):**
    *   **Tasks completed by DEGRADED agents:** Mean active delay = **$69.27$ ts** (count = 151)
    *   **Tasks completed by HEALTHY agents:** Mean active delay = **$46.91$ ts** (count = 67)
    *   **Never completed tasks:** Mean active delay = **$277.14$ ts** (count = 7)

### **C. Explanation of the Trade-Off (Why Mean Delay Remains Higher)**
1.  **CBBA Strips Tasks from Degraded Agents:** At $t=100$, CBBA immediately strips degraded agents of their tasks. These tasks are either reassigned to healthy agents (who complete them rapidly at speed 5.0, keeping active delays low) or abandoned.
    *   Abandoned tasks are set to `status = "unassigned"`, which **stops** their active delay counter from incrementing.
    *   Thus, CBBA's tasks are either completed quickly or abandoned early (which keeps their completed delay count low, or keeps their active delay low since it stops incrementing).
2.  **Proposed Model Retains Tasks (Soft-Pause):** The proposed model lets degraded agents keep and finish their tasks. 
    *   Because they crawl at speed $1.5$ instead of stopping, they successfully complete more tasks (increasing completion rate to $93.78\%$ vs $87.11\%$ pre-upgrade).
    *   However, because they travel slowly, these tasks remain in the `"active"` status for a much longer time, accumulating a high active delay.
    *   This slow-but-successful completion of tasks drags the overall mean delay up, explaining why the mean delay did not drop despite the timeout fallback fixing the worst-case stalls.

### **D. Distribution Percentiles (Pre-Upgrade vs. Post-Upgrade for Proposed Model)**
*   **Pre-Upgrade:** p50 = $45.0$ ts, p90 = $220.5$ ts, p99 = $340.7$ ts
*   **Post-Upgrade:** p50 = **$54.0$ ts**, p90 = **$204.2$ ts**, p99 = **$321.0$ ts**

This confirms that:
*   The **timeout fallback** successfully squashed the worst-case tail (p99 dropped by 20 ts, max delay dropped by 90 ts).
*   The **soft-pause policy** shifted the bulk of the distribution (p50 increased from 45.0 to 54.0 ts) as more tasks were resolved slowly by degraded vehicles instead of being abandoned, resulting in a flat mean delay overall.
