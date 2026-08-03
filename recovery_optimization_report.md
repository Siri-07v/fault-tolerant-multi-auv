# Deadlock Recovery Optimization and Evaluation Report

This report evaluates the performance of the accelerated Proposed Model under different deadlock timeout fallbacks ($K = 15, 20, 30$) against the Vanilla Auction and CBBA baselines.

| Metric / KPI | Scenario | Proposed (K=15) | Proposed (K=20) | Proposed (K=30) | Vanilla Auction | CBBA |
| --- | --- | --- | --- | --- | --- | --- |
| Task Completion Rate | Nominal Baseline | 95.1% ± 8.5% | 95.1% ± 8.5% | 95.1% ± 8.5% | 98.2% ± 3.1% | 95.1% ± 6.4% |
| Task Completion Rate | AMV Loss Stress | 89.8% ± 9.0% | 89.8% ± 9.0% | 89.8% ± 9.0% | 84.4% ± 7.0% | 93.3% ± 8.0% |
| Task Completion Rate | Comm Blackout Stress | 96.0% ± 8.7% | 96.0% ± 8.7% | 96.0% ± 8.7% | 98.2% ± 3.1% | 96.4% ± 7.1% |
| Task Completion Rate | Mass Fault Stress | 94.2% ± 8.7% | 94.2% ± 8.7% | 94.2% ± 8.7% | 98.2% ± 3.1% | 96.9% ± 5.0% |
| Never-Completed Tasks Count | Nominal Baseline | 0.73 ± 1.28 | 0.73 ± 1.28 | 0.73 ± 1.28 | 0.27 ± 0.46 | 0.73 ± 0.96 |
| Never-Completed Tasks Count | AMV Loss Stress | 1.53 ± 1.36 | 1.53 ± 1.36 | 1.53 ± 1.36 | 2.33 ± 1.05 | 1.00 ± 1.20 |
| Never-Completed Tasks Count | Comm Blackout Stress | 0.60 ± 1.30 | 0.60 ± 1.30 | 0.60 ± 1.30 | 0.27 ± 0.46 | 0.53 ± 1.06 |
| Never-Completed Tasks Count | Mass Fault Stress | 0.87 ± 1.30 | 0.87 ± 1.30 | 0.87 ± 1.30 | 0.27 ± 0.46 | 0.47 ± 0.74 |
| Mean Task Active Delay (ts) | Nominal Baseline | 72.68 ± 13.41 | 72.68 ± 13.41 | 72.68 ± 13.41 | 79.92 ± 10.30 | 68.92 ± 17.15 |
| Mean Task Active Delay (ts) | AMV Loss Stress | 67.44 ± 8.00 | 67.44 ± 8.00 | 67.44 ± 8.00 | 114.28 ± 14.69 | 61.90 ± 10.14 |
| Mean Task Active Delay (ts) | Comm Blackout Stress | 72.70 ± 11.89 | 72.70 ± 11.89 | 72.70 ± 11.89 | 79.92 ± 10.30 | 64.00 ± 14.25 |
| Mean Task Active Delay (ts) | Mass Fault Stress | 72.63 ± 13.43 | 72.63 ± 13.43 | 72.63 ± 13.43 | 81.29 ± 10.13 | 67.34 ± 15.80 |
| Max Task Active Delay (ts) | Nominal Baseline | 191.07 ± 46.92 | 191.07 ± 46.92 | 191.07 ± 46.92 | 222.07 ± 60.83 | 231.47 ± 98.40 |
| Max Task Active Delay (ts) | AMV Loss Stress | 209.13 ± 52.50 | 209.13 ± 52.50 | 209.13 ± 52.50 | 441.80 ± 19.40 | 203.87 ± 88.66 |
| Max Task Active Delay (ts) | Comm Blackout Stress | 188.80 ± 31.88 | 188.80 ± 31.88 | 188.80 ± 31.88 | 222.07 ± 60.83 | 197.93 ± 83.07 |
| Max Task Active Delay (ts) | Mass Fault Stress | 205.07 ± 47.32 | 205.07 ± 47.32 | 205.07 ± 47.32 | 233.27 ± 79.02 | 217.00 ± 80.05 |
| Congestion Drop Rate | Nominal Baseline | 0.9% ± 0.5% | 0.9% ± 0.5% | 0.9% ± 0.5% | 0.0% ± 0.0% | 11.8% ± 2.0% |
| Congestion Drop Rate | AMV Loss Stress | 0.4% ± 0.3% | 0.4% ± 0.3% | 0.4% ± 0.3% | 0.0% ± 0.0% | 11.0% ± 2.6% |
| Congestion Drop Rate | Comm Blackout Stress | 0.9% ± 0.4% | 0.9% ± 0.4% | 0.9% ± 0.4% | 0.0% ± 0.0% | 11.7% ± 1.9% |
| Congestion Drop Rate | Mass Fault Stress | 1.0% ± 0.4% | 1.0% ± 0.4% | 1.0% ± 0.4% | 0.0% ± 0.0% | 13.4% ± 2.0% |
| Mean Task Completion Time (ts) | Nominal Baseline | 144.13 ± 39.31 | 144.13 ± 39.31 | 144.13 ± 39.31 | 125.39 ± 27.32 | 145.01 ± 32.80 |
| Mean Task Completion Time (ts) | AMV Loss Stress | 141.29 ± 37.82 | 141.29 ± 37.82 | 141.29 ± 37.82 | 112.62 ± 30.08 | 150.71 ± 36.21 |
| Mean Task Completion Time (ts) | Comm Blackout Stress | 142.15 ± 39.78 | 142.15 ± 39.78 | 142.15 ± 39.78 | 125.39 ± 27.32 | 142.65 ± 25.40 |
| Mean Task Completion Time (ts) | Mass Fault Stress | 138.94 ± 40.52 | 138.94 ± 40.52 | 138.94 ± 40.52 | 126.77 ± 26.46 | 145.70 ± 24.54 |
| Deadlock Timeout Fallback Fires | Nominal Baseline | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Deadlock Timeout Fallback Fires | AMV Loss Stress | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Deadlock Timeout Fallback Fires | Comm Blackout Stress | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Deadlock Timeout Fallback Fires | Mass Fault Stress | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |