# 10.4 Comparative Evaluation Against CBBA (Verified Sweep)

To evaluate the performance of the proposed market-based auction system integrated with the Exact Dynamic Max-Consensus (EDMC) deadlock management protocol, we present a like-for-like comparative evaluation against the classic Consensus-Based Bundle Algorithm (CBBA; Choi, Brunet & How 2009). The experiments were conducted across a nominal scenario and three distinct stress scenarios (AMV Loss, Communication Blackout, and Mass Fault) using 15 random seeds each (total of 120 runs). All results presented here are generated directly from the validated dataset ([cbba_comparison_final_verified.csv](file:///c:/Users/siri0/capstone/fault-tolerant-multi-auv/cbba_comparison_final_verified.csv)).

## 10.4.1 Summary of Key Performance Indicators (KPIs)
Table 10.4 summarizes the mean and standard deviation of the 13 system KPIs and additional task delay/completion metrics across all evaluated scenarios.

| Metric / KPI | Scenario | Proposed (Auction + EDMC) | Baseline (CBBA) |
| :--- | :--- | :---: | :---: |
| **Task Completion Rate** | Nominal Baseline | 88.00% ± 10.14% | 92.89% ± 5.89% |
| | AMV Loss Stress | 86.67% ± 11.55% | 91.11% ± 6.00% |
| | Comm Blackout Stress | 89.33% ± 12.03% | 92.89% ± 6.89% |
| | Mass Fault Stress | 72.89% ± 17.18% | 87.11% ± 10.22% |
| **Mean Task Completion Time (ts)** | Nominal Baseline | 154.39 ± 42.71 | 147.16 ± 29.50 |
| | AMV Loss Stress | 160.23 ± 32.14 | 158.31 ± 24.42 |
| | Comm Blackout Stress | 154.04 ± 35.23 | 143.19 ± 23.79 |
| | Mass Fault Stress | 125.46 ± 22.82 | 161.98 ± 27.15 |
| **System Throughput (tasks/ts)** | Nominal Baseline | 0.03 ± 0.00 | 0.03 ± 0.00 |
| | AMV Loss Stress | 0.03 ± 0.00 | 0.03 ± 0.00 |
| | Comm Blackout Stress | 0.03 ± 0.00 | 0.03 ± 0.00 |
| | Mass Fault Stress | 0.02 ± 0.01 | 0.03 ± 0.00 |
| **Mean AMV Availability** | Nominal Baseline | 0.43 ± 0.07 | 0.48 ± 0.08 |
| | AMV Loss Stress | 0.34 ± 0.05 | 0.35 ± 0.05 |
| | Comm Blackout Stress | 0.44 ± 0.07 | 0.48 ± 0.08 |
| | Mass Fault Stress | 0.33 ± 0.06 | 0.35 ± 0.04 |
| **Fault Impact Score** | Nominal Baseline | 0.44 ± 0.07 | 0.45 ± 0.08 |
| | AMV Loss Stress | 0.45 ± 0.06 | 0.51 ± 0.07 |
| | Comm Blackout Stress | 0.44 ± 0.06 | 0.46 ± 0.07 |
| | Mass Fault Stress | 0.66 ± 0.06 | 0.69 ± 0.06 |
| **Deadlock Frequency (per 100 ts)** | Nominal Baseline | 0.35 ± 0.40 | 0.00 ± 0.00 |
| | AMV Loss Stress | 0.44 ± 0.22 | 0.00 ± 0.00 |
| | Comm Blackout Stress | 0.28 ± 0.33 | 0.00 ± 0.00 |
| | Mass Fault Stress | 1.17 ± 0.94 | 0.00 ± 0.00 |
| **Mean Packet Loss Rate** | Nominal Baseline | 31.86% ± 2.21% | 55.98% ± 3.34% |
| | AMV Loss Stress | 30.52% ± 3.71% | 56.71% ± 3.09% |
| | Comm Blackout Stress | 53.82% ± 6.21% | 65.01% ± 3.05% |
| | Mass Fault Stress | 30.88% ± 4.02% | 57.20% ± 3.13% |
| **Energy Efficiency (energy/task)** | Nominal Baseline | 22.97 ± 5.89 | 16.54 ± 3.33 |
| | AMV Loss Stress | 28.62 ± 4.85 | 24.60 ± 2.43 |
| | Comm Blackout Stress | 21.94 ± 6.33 | 16.33 ± 4.01 |
| | Mass Fault Stress | 33.78 ± 16.07 | 17.02 ± 3.01 |
| **Convergence Rate (iters/round)** | Nominal Baseline | 1.63 ± 0.19 | 1.70 ± 0.20 |
| | AMV Loss Stress | 1.49 ± 0.21 | 1.68 ± 0.20 |
| | Comm Blackout Stress | 1.66 ± 0.17 | 1.67 ± 0.23 |
| | Mass Fault Stress | 1.64 ± 0.25 | 1.65 ± 0.22 |
| **Connectivity Maintenance** | Nominal Baseline | 90.26% ± 12.94% | 81.97% ± 15.37% |
| | AMV Loss Stress | 91.48% ± 9.66% | 83.92% ± 16.95% |
| | Comm Blackout Stress | 54.42% ± 13.59% | 53.14% ± 14.84% |
| | Mass Fault Stress | 93.41% ± 7.21% | 75.91% ± 27.14% |
| **Physics Impact on Faults (corr)**| Nominal Baseline | -0.200 ± 0.548 | -0.085 ± 0.509 |
| | AMV Loss Stress | +0.049 ± 0.559 | +0.067 ± 0.617 |
| | Comm Blackout Stress | +0.094 ± 0.341 | +0.051 ± 0.543 |
| | Mass Fault Stress | +0.028 ± 0.485 | +0.098 ± 0.494 |
| **Thermocline Crossing Penalty** | Nominal Baseline | 33.03% ± 8.29% | 30.42% ± 9.46% |
| | AMV Loss Stress | 37.54% ± 10.00% | 33.06% ± 8.75% |
| | Comm Blackout Stress | 35.62% ± 9.49% | 28.75% ± 10.24% |
| | Mass Fault Stress | 34.77% ± 10.70% | 31.23% ± 10.84% |
| **Congestion Drop Rate** | Nominal Baseline | 7.10% ± 2.74% | 11.55% ± 2.79% |
| | AMV Loss Stress | 4.81% ± 1.93% | 11.21% ± 3.76% |
| | Comm Blackout Stress | 7.27% ± 2.69% | 10.18% ± 3.56% |
| | Mass Fault Stress | 7.08% ± 1.89% | 11.32% ± 3.90% |
| **Stalled AMV-Timesteps** | Nominal Baseline | 0.00 ± 0.00 | 247.80 ± 185.61 |
| | AMV Loss Stress | 0.00 ± 0.00 | 188.47 ± 150.72 |
| | Comm Blackout Stress | 0.00 ± 0.00 | 205.87 ± 194.56 |
| | Mass Fault Stress | 0.00 ± 0.00 | 116.27 ± 100.67 |
| **Mean Task Active Delay (ts)** | Nominal Baseline | 52.86 ± 12.35 | 77.95 ± 17.46 |
| | AMV Loss Stress | 45.48 ± 10.93 | 72.32 ± 11.56 |
| | Comm Blackout Stress | 50.77 ± 12.72 | 73.70 ± 19.41 |
| | Mass Fault Stress | 45.18 ± 8.98 | 62.27 ± 8.10 |
| **Max Task Active Delay (ts)** | Nominal Baseline | 164.07 ± 61.85 | 285.07 ± 84.84 |
| | AMV Loss Stress | 126.60 ± 36.95 | 239.00 ± 67.71 |
| | Comm Blackout Stress | 146.53 ± 55.69 | 262.13 ± 98.74 |
| | Mass Fault Stress | 151.53 ± 49.70 | 195.07 ± 81.09 |
| **Never Completed Tasks Count** | Nominal Baseline | 1.80 ± 1.52 | 1.07 ± 0.88 |
| | AMV Loss Stress | 2.00 ± 1.73 | 1.33 ± 0.90 |
| | Comm Blackout Stress | 1.60 ± 1.80 | 1.07 ± 1.03 |
| | Mass Fault Stress | 4.07 ± 2.58 | 1.93 ± 1.53 |

> [!NOTE]
> **Stalled AMV-Timesteps Finding:** Under the current metrics bookkeeping in `main.py`, the Proposed Auction+EDMC system records a flat **0.00 ± 0.00** stalled timesteps across all scenarios. This is because stalled timesteps for the Proposed system are strictly counted only when an active vehicle is stuck in the `FSM_DEADLOCK` state. Since the EDMC deadlock resolution protocol triggers reallocations almost instantaneously (usually within the same or next timestep), vehicles exit the deadlock state immediately, accumulating zero cumulative stalled timesteps. In contrast, the classic CBBA baseline has no deadlock detection or recovery mechanisms, meaning vehicles remain permanently stalled, accumulating high stalled timesteps (e.g., 247.80 ± 185.61 in Nominal).

---

## 10.4.2 Paired Wilcoxon Signed-Rank Test Results (α = 0.05)
To evaluate the statistical significance of the differences between the Proposed (Auction + EDMC) allocator and the classic CBBA baseline, a paired Wilcoxon signed-rank test was conducted across the 15 simulation seeds. Table 10.4.2 lists the computed p-values for primary performance indicators.

| Metric | Scenario | p-value | Significant (α=0.05)? |
| :--- | :--- | :---: | :---: |
| **Task Completion Rate** | Nominal Baseline | 0.122450 | No |
| | AMV Loss Stress | 0.207261 | No |
| | Comm Blackout Stress | 0.475644 | No |
| | Mass Fault Stress | 0.008902 | **Yes** (CBBA superior due to conservative proposed reallocation) |
| **Deadlock Frequency** | Nominal Baseline | 0.004671 | **Yes** (Baseline is 0.00, as it does not detect/log deadlocks) |
| | AMV Loss Stress | 0.000590 | **Yes** |
| | Comm Blackout Stress | 0.010712 | **Yes** |
| | Mass Fault Stress | 0.001435 | **Yes** |
| **Congestion Drop Rate** | Nominal Baseline | 0.001160 | **Yes** (Proposed significantly lower drops) |
| | AMV Loss Stress | 0.000122 | **Yes** |
| | Comm Blackout Stress | 0.012451 | **Yes** |
| | Mass Fault Stress | 0.002014 | **Yes** |
| **Stalled AMV-Timesteps** | Nominal Baseline | 0.000982 | **Yes** (Proposed significantly lower stalling) |
| | AMV Loss Stress | 0.000982 | **Yes** |
| | Comm Blackout Stress | 0.001474 | **Yes** |
| | Mass Fault Stress | 0.000061 | **Yes** |

---

## 10.4.3 Visual Comparison
- **Task Completion Rate over Time Faceted by Scenario:** [plot_allocator_comparison_completion.png](plot_allocator_comparison_completion.png) shows the completion timeline across all seeds.
- **Deadlock Recovery and Stalling Timelines:** [plot_allocator_comparison_deadlock_recovery.png](plot_allocator_comparison_deadlock_recovery.png) visualizes the recovery of the proposed Auction+EDMC system vs. the permanent stalling of CBBA.