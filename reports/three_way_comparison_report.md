# Three-Way Comparative Evaluation

This report presents a three-way comparative sweep analyzing the performance of:
1. **Proposed Model (Auction + EDMC)**: Single-task price auction with EDMC, soft-pausing, timeouts, and gossip retries.
2. **Vanilla Auction**: Single-task price auction with core bidding logic but all fault-handling and deadlock management disabled (uses minimal task-lock fallback).
3. **Baseline (CBBA)**: Multi-task bundle planning algorithm with legacy lock-in behavior.

The experiments were conducted across 4 scenarios (Nominal, AMV Loss, Comm Blackout, and Mass Fault) using 15 random seeds each (total of 180 runs).

| Metric / KPI | Scenario | Proposed (Auction + EDMC) | Vanilla Auction Baseline | Baseline (CBBA) |
| --- | --- | --- | --- | --- |
| Task Completion Rate | Nominal Baseline | 96.0% ± 6.6% | 98.2% ± 3.1% | 95.1% ± 6.4% |
| Task Completion Rate | AMV Loss Stress | 85.3% ± 16.4% | 84.4% ± 7.0% | 93.3% ± 8.0% |
| Task Completion Rate | Comm Blackout Stress | 93.3% ± 11.3% | 98.2% ± 3.1% | 96.4% ± 7.1% |
| Task Completion Rate | Mass Fault Stress | 93.8% ± 7.3% | 98.2% ± 3.1% | 96.9% ± 5.0% |
| Never-Completed Tasks Count | Nominal Baseline | 0.60 ± 0.99 | 0.27 ± 0.46 | 0.73 ± 0.96 |
| Never-Completed Tasks Count | AMV Loss Stress | 2.20 ± 2.46 | 2.33 ± 1.05 | 1.00 ± 1.20 |
| Never-Completed Tasks Count | Comm Blackout Stress | 1.00 ± 1.69 | 0.27 ± 0.46 | 0.53 ± 1.06 |
| Never-Completed Tasks Count | Mass Fault Stress | 0.93 ± 1.10 | 0.27 ± 0.46 | 0.47 ± 0.74 |
| Mean Task Active Delay (ts) | Nominal Baseline | 87.51 ± 13.39 | 79.92 ± 10.30 | 68.92 ± 17.15 |
| Mean Task Active Delay (ts) | AMV Loss Stress | 72.54 ± 9.85 | 114.28 ± 14.69 | 61.90 ± 10.14 |
| Mean Task Active Delay (ts) | Comm Blackout Stress | 88.06 ± 12.22 | 79.92 ± 10.30 | 64.00 ± 14.25 |
| Mean Task Active Delay (ts) | Mass Fault Stress | 89.24 ± 12.95 | 81.29 ± 10.13 | 67.34 ± 15.80 |
| Max Task Active Delay (ts) | Nominal Baseline | 254.13 ± 65.58 | 222.07 ± 60.83 | 231.47 ± 98.40 |
| Max Task Active Delay (ts) | AMV Loss Stress | 211.07 ± 43.57 | 441.80 ± 19.40 | 203.87 ± 88.66 |
| Max Task Active Delay (ts) | Comm Blackout Stress | 260.73 ± 55.13 | 222.07 ± 60.83 | 197.93 ± 83.07 |
| Max Task Active Delay (ts) | Mass Fault Stress | 250.87 ± 58.58 | 233.27 ± 79.02 | 217.00 ± 80.05 |
| Congestion Drop Rate | Nominal Baseline | 0.2% ± 0.2% | 0.0% ± 0.0% | 11.8% ± 2.0% |
| Congestion Drop Rate | AMV Loss Stress | 0.1% ± 0.1% | 0.0% ± 0.0% | 11.0% ± 2.6% |
| Congestion Drop Rate | Comm Blackout Stress | 0.1% ± 0.1% | 0.0% ± 0.0% | 11.7% ± 1.9% |
| Congestion Drop Rate | Mass Fault Stress | 0.2% ± 0.2% | 0.0% ± 0.0% | 13.4% ± 2.0% |
| Mean Task Completion Time (ts) | Nominal Baseline | 154.27 ± 52.35 | 125.39 ± 27.32 | 145.01 ± 32.80 |
| Mean Task Completion Time (ts) | AMV Loss Stress | 142.69 ± 40.91 | 112.62 ± 30.08 | 150.71 ± 36.21 |
| Mean Task Completion Time (ts) | Comm Blackout Stress | 146.54 ± 39.25 | 125.39 ± 27.32 | 142.65 ± 25.40 |
| Mean Task Completion Time (ts) | Mass Fault Stress | 152.65 ± 47.83 | 126.77 ± 26.46 | 145.70 ± 24.54 |