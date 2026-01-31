#!/usr/bin/env python3
"""Benchmark system for my-unicorn test framework.

This package provides performance metrics collection, analysis, and reporting
for tracking optimization improvements over time.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "BenchmarkCollector",
    "BenchmarkReport",
    "BenchmarkTimer",
    "ComparisonReport",
    "Metric",
    "generate_json_report",
    "generate_markdown_report",
]


@dataclass
class Metric:
    """Individual performance metric for an operation.

    Attributes:
        operation_name: Name of the operation being measured
        total_time_ms: Total execution time in milliseconds
        network_time_ms: Estimated network time in milliseconds
        core_time_ms: Core processing time (total - network)
        breakdown: Component-level timing breakdown
        network: Network-specific metadata (bytes, speed)
        metadata: Additional operation metadata
    """

    operation_name: str
    total_time_ms: float
    network_time_ms: float = 0.0
    core_time_ms: float = 0.0
    breakdown: dict[str, float] = field(default_factory=dict)
    network: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Calculate core time if not provided."""
        if self.core_time_ms == 0.0:
            self.core_time_ms = self.total_time_ms - self.network_time_ms


@dataclass
class ComparisonReport:
    """Comparison report between two benchmark versions.

    Attributes:
        current_version: Version being tested
        compare_version: Baseline version for comparison
        core_time_diff_ms: Total core time difference
        improvements: List of improved operations
        regressions: List of regressed operations
        operation_comparisons: Detailed per-operation comparisons
    """

    current_version: str
    compare_version: str
    core_time_diff_ms: float
    improvements: list[str] = field(default_factory=list)
    regressions: list[str] = field(default_factory=list)
    operation_comparisons: dict[str, dict[str, Any]] = field(
        default_factory=dict
    )


@dataclass
class BenchmarkReport:
    """Complete benchmark report for a test run.

    Attributes:
        version: my-unicorn version being tested
        prod_version: Production version (for comparison)
        timestamp: ISO 8601 timestamp of test run
        environment: System environment info (OS, Python, CPU)
        resources: Resource usage metrics (CPU, memory, disk I/O)
        operations: Per-operation performance metrics
        comparisons: Version-to-version comparisons
    """

    version: str
    prod_version: str
    timestamp: str
    environment: dict[str, Any]
    resources: dict[str, Any]
    operations: dict[str, dict[str, Any]]
    comparisons: dict[str, dict[str, Any]] = field(default_factory=dict)


# Import collector and reporter components
from benchmark.collector import (  # noqa: E402
    BenchmarkCollector,
    BenchmarkTimer,
)
from benchmark.reporter import (  # noqa: E402
    generate_json_report,
    generate_markdown_report,
)
