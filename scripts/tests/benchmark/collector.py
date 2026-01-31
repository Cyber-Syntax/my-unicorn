#!/usr/bin/env python3
"""Benchmark metrics collector for my-unicorn test framework.

This module handles real-time collection of performance metrics during
test operations, including timing, resource usage, and network statistics.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

import platform
import time
from datetime import UTC, datetime
from typing import Any

import psutil
from benchmark import BenchmarkReport, Metric


class BenchmarkCollector:
    """Collect performance metrics during test execution.

    Tracks operation timing, resource usage (CPU, memory, disk I/O),
    and network statistics with accurate core vs network time separation.

    Attributes:
        version: my-unicorn version being benchmarked
        prod_version: Production version for comparison
        metrics: Collected metrics organized by operation name
        active_operations: Currently active operation contexts
        start_time: Benchmark session start time
        process: Current process handle for resource monitoring
    """

    def __init__(self, version: str, prod_version: str) -> None:
        """Initialize benchmark collector.

        Args:
            version: Development version being benchmarked
            prod_version: Production version
        """
        self.version = version
        self.prod_version = prod_version
        self.metrics: dict[str, list[Metric]] = {}
        self.active_operations: dict[str, dict[str, Any]] = {}
        self.start_time = time.perf_counter()

        # Resource tracking
        self.process = psutil.Process()
        self.memory_start = self.process.memory_info().rss / 1024 / 1024  # MB
        self.memory_peak = self.memory_start
        self.cpu_peak_percent = 0.0
        self.disk_io_start = psutil.disk_io_counters()
        self.disk_reads = 0
        self.disk_writes = 0

    def start_operation(
        self, operation_name: str, metadata: dict[str, Any] | None = None
    ) -> str:
        """Start timing an operation.

        Args:
            operation_name: Name of the operation
            metadata: Optional metadata

        Returns:
            Context ID for this operation
        """
        context_id = f"{operation_name}_{time.perf_counter()}"
        self.active_operations[context_id] = {
            "name": operation_name,
            "start_time": time.perf_counter(),
            "metadata": metadata or {},
            "network_time": 0.0,
            "breakdown": {},
            "network": {},
        }
        return context_id

    def end_operation(
        self, context_id: str, metadata: dict[str, Any] | None = None
    ) -> Metric:
        """End timing and record metrics.

        Args:
            context_id: Context ID from start_operation
            metadata: Optional additional metadata

        Returns:
            Metric object with timing data
        """
        if context_id not in self.active_operations:
            msg = f"Unknown context ID: {context_id}"
            raise ValueError(msg)

        op = self.active_operations.pop(context_id)
        total_time = (time.perf_counter() - op["start_time"]) * 1000  # ms

        # FIXED: Properly preserve network time
        network_time = op.get("network_time", 0.0)

        # Update resource tracking
        self._update_resource_tracking()

        metric = Metric(
            operation_name=op["name"],
            total_time_ms=total_time,
            network_time_ms=network_time,
            breakdown=op["breakdown"],
            network=op.get("network", {}),
            metadata={**op["metadata"], **(metadata or {})},
        )

        # Store metric
        if op["name"] not in self.metrics:
            self.metrics[op["name"]] = []
        self.metrics[op["name"]].append(metric)

        return metric

    def record_network_time(
        self,
        context_id: str,
        time_ms: float,
        bytes_downloaded: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record network-related time to exclude from core metrics.

        Args:
            context_id: Context ID from start_operation
            time_ms: Network time in milliseconds
            bytes_downloaded: Number of bytes downloaded
            metadata: Optional network metadata
        """
        if context_id in self.active_operations:
            # FIXED: Accumulate network time properly
            self.active_operations[context_id]["network_time"] += time_ms

            if "network" not in self.active_operations[context_id]:
                self.active_operations[context_id]["network"] = {}

            # Merge network metadata
            self.active_operations[context_id]["network"].update(
                metadata or {}
            )

            # Track bytes if provided
            if bytes_downloaded > 0:
                current_bytes = self.active_operations[context_id][
                    "network"
                ].get("bytes_downloaded", 0)
                self.active_operations[context_id]["network"][
                    "bytes_downloaded"
                ] = current_bytes + bytes_downloaded

    def record_breakdown(
        self, context_id: str, component: str, time_ms: float
    ) -> None:
        """Record component-level timing breakdown.

        Args:
            context_id: Context ID from start_operation
            component: Component name
            time_ms: Time in milliseconds
        """
        if context_id in self.active_operations:
            breakdown = self.active_operations[context_id]["breakdown"]
            breakdown[component] = breakdown.get(component, 0) + time_ms

    def _update_resource_tracking(self) -> None:
        """Update resource usage metrics."""
        # Memory tracking
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.memory_peak = max(self.memory_peak, current_memory)

        # CPU tracking
        try:
            cpu_percent = self.process.cpu_percent(interval=0.01)
            self.cpu_peak_percent = max(self.cpu_peak_percent, cpu_percent)
        except Exception:  # noqa: BLE001, S110
            pass  # Resource tracking is best-effort, failures are non-critical

        # Disk I/O tracking
        try:
            disk_io_end = psutil.disk_io_counters()
            if disk_io_end and self.disk_io_start:
                self.disk_reads = (
                    disk_io_end.read_bytes - self.disk_io_start.read_bytes
                )
                self.disk_writes = (
                    disk_io_end.write_bytes - self.disk_io_start.write_bytes
                )
        except Exception:  # noqa: BLE001, S110
            pass  # Resource tracking is best-effort, failures are non-critical

    def generate_report(self) -> BenchmarkReport:
        """Generate comprehensive benchmark report.

        Returns:
            BenchmarkReport with all collected metrics
        """
        # Environment information
        environment = {
            "os": platform.system(),
            "os_version": platform.release(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "total_memory_mb": psutil.virtual_memory().total / 1024 / 1024,
        }

        # Calculate efficiency score (lower memory and CPU is better)
        memory_delta = self.memory_peak - self.memory_start
        efficiency_score = max(
            0, 100 - (self.cpu_peak_percent * 0.5 + memory_delta * 0.5)
        )

        resources = {
            "cpu_peak_percent": self.cpu_peak_percent,
            "memory_delta_mb": memory_delta,
            "memory_peak_mb": self.memory_peak,
            "disk_reads": self.disk_reads,
            "disk_writes": self.disk_writes,
            "efficiency_score": efficiency_score,
        }

        # Aggregate operations
        operations = {}
        for op_name, metrics in self.metrics.items():
            total_time = sum(m.total_time_ms for m in metrics)
            network_time = sum(m.network_time_ms for m in metrics)
            core_time = sum(m.core_time_ms for m in metrics)

            # Aggregate breakdowns
            breakdown = {}
            for metric in metrics:
                for component, time_ms in metric.breakdown.items():
                    breakdown[component] = (
                        breakdown.get(component, 0) + time_ms
                    )

            # Aggregate network stats
            network = {}
            total_bytes = sum(
                m.network.get("bytes_downloaded", 0) for m in metrics
            )
            if total_bytes > 0:
                network["bytes_downloaded"] = total_bytes
                # FIXED: Calculate download speed only if network_time > 0
                if network_time > 0:
                    network["download_speed_mbps"] = (
                        total_bytes / 1024 / 1024
                    ) / (network_time / 1000)
                else:
                    network["download_speed_mbps"] = 0

            operations[op_name] = {
                "total_time_ms": total_time,
                "network_time_ms": network_time,
                "core_time_ms": core_time,
                "breakdown": breakdown,
                "network": network,
            }

        return BenchmarkReport(
            version=self.version,
            prod_version=self.prod_version,
            timestamp=datetime.now(tz=UTC).isoformat(),
            environment=environment,
            resources=resources,
            operations=operations,
        )


class BenchmarkTimer:
    """Context manager for timing operations with optional breakdowns.

    Usage:
        with BenchmarkTimer(collector, "install_app") as timer:
            # Do work
            timer.record_network(network_time_ms, bytes_downloaded)
            timer.record_breakdown("validation", validation_time_ms)
    """

    def __init__(
        self, collector: BenchmarkCollector, operation_name: str
    ) -> None:
        """Initialize timer.

        Args:
            collector: BenchmarkCollector instance
            operation_name: Name of the operation
        """
        self.collector = collector
        self.operation_name = operation_name
        self.context_id: str | None = None

    def __enter__(self) -> "BenchmarkTimer":
        """Start timing."""
        self.context_id = self.collector.start_operation(self.operation_name)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """End timing."""
        if self.context_id:
            self.collector.end_operation(self.context_id)

    def record_network(
        self, time_ms: float, bytes_downloaded: int = 0
    ) -> None:
        """Record network time within this operation.

        Args:
            time_ms: Network time in milliseconds
            bytes_downloaded: Number of bytes downloaded
        """
        if self.context_id:
            self.collector.record_network_time(
                self.context_id, time_ms, bytes_downloaded
            )

    def record_breakdown(self, component: str, time_ms: float) -> None:
        """Record breakdown timing.

        Args:
            component: Component name
            time_ms: Time in milliseconds
        """
        if self.context_id:
            self.collector.record_breakdown(
                self.context_id, component, time_ms
            )
