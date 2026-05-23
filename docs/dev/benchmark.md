# Benchmark Results

## Line of code

### v2.6.0-alpha

```bash
cloc src/my_unicorn
     131 text files.
     130 unique files.
       1 file ignored.

github.com/AlDanial/cloc v 2.08  T=0.15 s (886.3 files/s, 191343.1 lines/s)
-------------------------------------------------------------------------------
Language                     files          blank        comment           code
-------------------------------------------------------------------------------
Python                          92           5110           7586          13281
JSON                            38              0              0           2089
-------------------------------------------------------------------------------
SUM:                           130           5110           7586          15370
-------------------------------------------------------------------------------
```

### v2.6.1-alpha

```bash
cloc src/my_unicorn
     121 text files.
     120 unique files.
     202 files ignored.

github.com/AlDanial/cloc v 2.08  T=0.16 s (770.1 files/s, 176625.0 lines/s)
-------------------------------------------------------------------------------
Language                     files          blank        comment           code
-------------------------------------------------------------------------------
Python                          82           4964           7361          13110
JSON                            38              0              0           2089
-------------------------------------------------------------------------------
SUM:                           120           4964           7361          15199
-------------------------------------------------------------------------------
```

### v2.7.0-alpha

```bash
cloc src/my_unicorn
     121 text files.
     120 unique files.
      83 files ignored.

github.com/AlDanial/cloc v 2.08  T=0.14 s (848.1 files/s, 195304.6 lines/s)
-------------------------------------------------------------------------------
Language                     files          blank        comment           code
-------------------------------------------------------------------------------
Python                          82           4979           7364          13203
JSON                            38              0              0           2089
-------------------------------------------------------------------------------
SUM:                           120           4979           7364          15292
-------------------------------------------------------------------------------
```

## End-to-end test run times (with network I/O)

> **Disclaimer:** These durations include live network calls. They are **not** pure code performance benchmarks.
> The internet connection speed, latency, and server response times directly affect the numbers.
> A dedicated code‑performance benchmark (mocking network) is planned but not yet implemented.

### test_quick_flow.py

| Version      | Tests Passed | Duration (s) | Duration (mm:ss) | 🇩🇪 Germany (Nuremberg, ~1500km) | 🇳🇱 Netherlands (Amsterdam)      |
| ------------ | ------------ | ------------ | ---------------- | ------------------------------- | ------------------------------- |
| v2.5.1-alpha | 4            | 154.57       | 02:34            | Unknown                         | Unknown                         |
| Unreleased   | 4            | 76.49        | 01:16            | ↓61.8 Mbps / 🕐44.0ms / ⊞1.42ms | ↓85.1 Mbps / 🕐57.0ms / ⊞1.93ms |

### test_full_flow.py

| Version      | Tests Passed | Duration (s) | Duration (mm:ss) | 🇩🇪 Germany (Nuremberg, ~1500km) | 🇳🇱 Netherlands (Amsterdam)      |
| ------------ | ------------ | ------------ | ---------------- | ------------------------------- | ------------------------------- |
| v2.5.1-alpha | 4            | 443.34       | 07:23            | Unknown                         | Unknown                         |
| Unreleased   | 4            | 305.09       | 05:05            | ↓61.8 Mbps / 🕐44.0ms / ⊞1.42ms | ↓85.1 Mbps / 🕐57.0ms / ⊞1.93ms |

### test_update_all_flow.py

| Version      | Tests Passed | Duration (s) | Duration (mm:ss) | 🇩🇪 Germany (Nuremberg, ~1500km) | 🇳🇱 Netherlands (Amsterdam)      |
| ------------ | ------------ | ------------ | ---------------- | ------------------------------- | ------------------------------- |
| v2.5.1-alpha | 4            | 129.81       | Unknown          | Unknown                         | Unknown                         |
| Unreleased   | 4            | 129.81       | 02:09            | ↓61.8 Mbps / 🕐44.0ms / ⊞1.42ms | ↓85.1 Mbps / 🕐57.0ms / ⊞1.93ms |
