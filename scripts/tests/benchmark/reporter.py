#!/usr/bin/env python3
"""Benchmark report generation for my-unicorn test framework.

This module handles generation of benchmark reports in JSON and Markdown
formats, including multi-version comparison and regression detection.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

from pathlib import Path
from typing import Any

from benchmark import BenchmarkReport
from utils import ensure_directory, load_json, save_json


def generate_json_report(
    report: BenchmarkReport,
    output_path: Path,
    compare_with: list[str] | None = None,
) -> None:
    """Generate JSON benchmark report with optional version comparisons.

    Args:
        report: BenchmarkReport to export
        output_path: Path to save JSON report
        compare_with: Optional list of version IDs to compare against
    """
    # Ensure output directory exists
    ensure_directory(output_path.parent)

    # Load existing multi-version JSON if it exists
    if output_path.exists():
        try:
            existing = load_json(output_path)
        except Exception:  # noqa: BLE001
            existing = {"versions": {}}  # Start fresh if JSON is corrupted
    else:
        existing = {"versions": {}}

    # Generate version key
    version_key = f"{report.version}_{report.timestamp}"

    # Convert report to dict
    report_data = {
        "version": report.version,
        "prod_version": report.prod_version,
        "timestamp": report.timestamp,
        "environment": report.environment,
        "resources": report.resources,
        "operations": report.operations,
        "comparisons": report.comparisons,
    }

    # Add to versions
    existing["versions"][version_key] = report_data

    # Generate comparisons if requested
    if compare_with:
        comparisons = {}
        for compare_version_key in compare_with:
            if compare_version_key in existing["versions"]:
                comparison = _generate_comparison(
                    report_data, existing["versions"][compare_version_key]
                )
                comparisons[compare_version_key] = comparison

        report_data["comparisons"] = comparisons
        existing["versions"][version_key]["comparisons"] = comparisons

    # Save updated multi-version JSON
    save_json(output_path, existing)


def generate_markdown_report(
    report: BenchmarkReport,
    output_path: Path,
    include_comparisons: bool = True,
) -> None:
    """Generate Markdown benchmark report.

    Args:
        report: BenchmarkReport to export
        output_path: Path to save Markdown report
        include_comparisons: Whether to include comparison tables
    """
    # Ensure output directory exists
    ensure_directory(output_path.parent)

    lines = []

    # Header
    lines.append(f"# Benchmark Report: {report.version}")
    lines.append("")
    lines.append(f"**Timestamp:** {report.timestamp}")
    lines.append(f"**Production Version:** {report.prod_version}")
    lines.append("")

    # Environment
    lines.append("## Environment")
    lines.append("")
    lines.append(f"- **OS:** {report.environment.get('os', 'Unknown')}")
    lines.append(
        f"- **OS Version:** {report.environment.get('os_version', 'Unknown')}"
    )
    lines.append(
        f"- **Python:** {report.environment.get('python_version', 'Unknown')}"
    )
    lines.append(
        f"- **CPU Cores:** {report.environment.get('cpu_count', 'Unknown')}"
    )
    lines.append(
        f"- **Total Memory:** {report.environment.get('total_memory_mb', 0):.1f} MB"
    )
    lines.append("")

    # Resources
    lines.append("## Resource Usage")
    lines.append("")
    lines.append(
        f"- **Peak CPU:** {report.resources.get('cpu_peak_percent', 0):.1f}%"
    )
    lines.append(
        f"- **Memory Delta:** {report.resources.get('memory_delta_mb', 0):.2f} MB"
    )
    lines.append(
        f"- **Peak Memory:** {report.resources.get('memory_peak_mb', 0):.2f} MB"
    )
    lines.append(
        f"- **Disk Reads:** {report.resources.get('disk_reads', 0) / 1024 / 1024:.2f} MB"
    )
    lines.append(
        f"- **Disk Writes:** {report.resources.get('disk_writes', 0) / 1024 / 1024:.2f} MB"
    )
    lines.append(
        f"- **Efficiency Score:** {report.resources.get('efficiency_score', 0):.1f}/100"
    )
    lines.append("")

    # Operations table
    lines.append("## Performance Metrics")
    lines.append("")
    lines.append("| Operation | Total Time | Network Time | Core Time |")
    lines.append("|-----------|------------|--------------|-----------|")

    for op_name, op_data in sorted(report.operations.items()):
        total = op_data.get("total_time_ms", 0)
        network = op_data.get("network_time_ms", 0)
        core = op_data.get("core_time_ms", 0)

        lines.append(
            f"| {op_name} | {total:.2f}ms | {network:.2f}ms | {core:.2f}ms |"
        )

    lines.append("")

    # Network statistics
    lines.append("## Network Statistics")
    lines.append("")
    lines.append("| Operation | Downloaded | Speed |")
    lines.append("|-----------|------------|-------|")

    for op_name, op_data in sorted(report.operations.items()):
        network_data = op_data.get("network", {})
        bytes_dl = network_data.get("bytes_downloaded", 0)
        speed = network_data.get("download_speed_mbps", 0)

        if bytes_dl > 0:
            lines.append(
                f"| {op_name} | {bytes_dl / 1024 / 1024:.2f} MB | {speed:.2f} MB/s |"
            )

    lines.append("")

    # Comparisons
    if include_comparisons and report.comparisons:
        lines.append("## Version Comparisons")
        lines.append("")

        for compare_version, comparison_data in report.comparisons.items():
            lines.append(f"### vs {compare_version}")
            lines.append("")

            core_diff = comparison_data.get("core_time_diff_ms", 0)
            if core_diff < 0:
                lines.append(
                    f"**Overall:** ⚡ {abs(core_diff):.2f}ms faster (improvement)"
                )
            elif core_diff > 0:
                lines.append(
                    f"**Overall:** 🐌 {core_diff:.2f}ms slower (regression)"
                )
            else:
                lines.append("**Overall:** No change")

            lines.append("")

            # Improvements
            improvements = comparison_data.get("improvements", [])
            if improvements:
                lines.append("**Improvements:**")
                for improvement in improvements:
                    lines.append(f"- ✅ {improvement}")
                lines.append("")

            # Regressions
            regressions = comparison_data.get("regressions", [])
            if regressions:
                lines.append("**Regressions:**")
                for regression in regressions:
                    lines.append(f"- ⚠️ {regression}")
                lines.append("")

    # Write to file
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _generate_comparison(
    current: dict[str, Any], baseline: dict[str, Any]
) -> dict[str, Any]:
    """Generate comparison between two benchmark reports.

    Args:
        current: Current version report data
        baseline: Baseline version report data

    Returns:
        Comparison data dictionary
    """
    current_ops = current.get("operations", {})
    baseline_ops = baseline.get("operations", {})

    # Calculate total core time difference
    current_core = sum(
        op.get("core_time_ms", 0) for op in current_ops.values()
    )
    baseline_core = sum(
        op.get("core_time_ms", 0) for op in baseline_ops.values()
    )
    core_time_diff_ms = current_core - baseline_core

    improvements = []
    regressions = []
    operation_comparisons = {}

    # Per-operation comparison
    for op_name in set(current_ops.keys()) | set(baseline_ops.keys()):
        current_op = current_ops.get(op_name, {})
        baseline_op = baseline_ops.get(op_name, {})

        current_core_time = current_op.get("core_time_ms", 0)
        baseline_core_time = baseline_op.get("core_time_ms", 0)

        if baseline_core_time > 0:
            diff_ms = current_core_time - baseline_core_time
            diff_percent = (diff_ms / baseline_core_time) * 100

            operation_comparisons[op_name] = {
                "current_ms": current_core_time,
                "baseline_ms": baseline_core_time,
                "diff_ms": diff_ms,
                "diff_percent": diff_percent,
            }

            # Track improvements and regressions (>5% threshold)
            if diff_percent < -5:
                improvements.append(
                    f"{op_name}: {abs(diff_ms):.2f}ms faster ({abs(diff_percent):.1f}% improvement)"
                )
            elif diff_percent > 5:
                regressions.append(
                    f"{op_name}: {diff_ms:.2f}ms slower ({diff_percent:.1f}% regression)"
                )

    return {
        "current_version": current.get("version"),
        "compare_version": baseline.get("version"),
        "core_time_diff_ms": core_time_diff_ms,
        "improvements": improvements,
        "regressions": regressions,
        "operation_comparisons": operation_comparisons,
    }


def load_benchmark_history(benchmark_dir: Path) -> dict[str, Any]:
    """Load benchmark history from JSON file.

    Args:
        benchmark_dir: Directory containing benchmark files

    Returns:
        Multi-version benchmark data
    """
    json_path = benchmark_dir / "benchmarks.json"
    if json_path.exists():
        return load_json(json_path)
    return {"versions": {}}


def get_latest_version(
    benchmark_dir: Path, version: str | None = None
) -> str | None:
    """Get the latest benchmark version key.

    Args:
        benchmark_dir: Directory containing benchmark files
        version: Optional specific version to filter by

    Returns:
        Latest version key or None if not found
    """
    history = load_benchmark_history(benchmark_dir)
    versions = history.get("versions", {})

    if not versions:
        return None

    # Filter by version if specified
    if version:
        matching = [k for k in versions if k.startswith(f"{version}_")]
        if matching:
            return max(matching)  # Latest timestamp
        return None

    # Return overall latest
    return max(versions.keys())
