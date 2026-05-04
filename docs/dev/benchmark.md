# Benchmark Results

## End-to-end test run times (with network I/O)

> **Disclaimer:** These durations include live network calls. They are **not** pure code performance benchmarks.  
> The internet connection speed, latency, and server response times directly affect the numbers.  
> A dedicated code‑performance benchmark (mocking network) is planned but not yet implemented.

### test_quick_flow.py

| Version       | Tests Passed | Duration (s) | Duration (mm:ss) | 🇩🇪 Germany (Nuremberg, ~1500km)       | 🇳🇱 Netherlands (Amsterdam)            |
|---------------|--------------|--------------|------------------|--------------------------------------|---------------------------------------|
| v2.5.1-alpha  | 4            | 154.57       | 02:34            | Unknown | Unknown|
| Unreleased    | 4            | 76.49        | 01:16            | ↓61.8 Mbps / 🕐44.0ms / ⊞1.42ms      | ↓85.1 Mbps / 🕐57.0ms / ⊞1.93ms      |

### test_full_flow.py

| Version       | Tests Passed | Duration (s) | Duration (mm:ss) | 🇩🇪 Germany (Nuremberg, ~1500km)       | 🇳🇱 Netherlands (Amsterdam)            |
|---------------|--------------|--------------|------------------|--------------------------------------|---------------------------------------|
| v2.5.1-alpha  | 4            | 443.34       | 07:23            | Unknown | Unknown |
| Unreleased    | 4            | 305.09       | 05:05            | ↓61.8 Mbps / 🕐44.0ms / ⊞1.42ms      | ↓85.1 Mbps / 🕐57.0ms / ⊞1.93ms      |

### test_update_all_flow.py

| Version       | Tests Passed | Duration (s) | Duration (mm:ss) | 🇩🇪 Germany (Nuremberg, ~1500km)       | 🇳🇱 Netherlands (Amsterdam)            |
|---------------|--------------|--------------|------------------|--------------------------------------|---------------------------------------|
| v2.5.1-alpha  | 4            | 129.81       | Unknown          | Unknown | Unknown |
| Unreleased    | 4            | 129.81       | 02:09            | ↓61.8 Mbps / 🕐44.0ms / ⊞1.42ms      | ↓85.1 Mbps / 🕐57.0ms / ⊞1.93ms      |

