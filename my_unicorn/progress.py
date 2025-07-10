#!/usr/bin/env python3
"""AppImage download progress manager with fixed positioning.

This module provides a stable progress display for concurrent AppImage downloads
using fixed line positioning inspired by the working AsyncMultiFileProgressMeter example.
"""

import sys
import threading
import time
from typing import Any


def format_number(number: int) -> str:
    """Format number to human readable string with units."""
    if number <= 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(number)

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index > 0:
        return f"{size:.1f} {units[unit_index]}"
    else:
        return f"{int(size)} {units[unit_index]}"


def format_time(seconds: float | None) -> str:
    """Format time duration to MM:SS."""
    if seconds is None or seconds <= 0:
        return "--:--"
    minutes = int(seconds // 60)
    seconds_remainder = int(seconds % 60)
    return f"{minutes:02d}:{seconds_remainder:02d}"


class AppImageProgressMeter:
    """Fixed-position progress meter for AppImage downloads.

    Each download gets assigned a permanent line position and updates in place.
    This prevents display jumping issues during concurrent operations.
    """

    def __init__(self, fo=sys.stderr, update_period: float = 0.1):
        """Initialize the progress meter.

        Args:
            fo: File object for output
            update_period: Update interval for display updates

        """
        self.fo = fo
        self.update_period = update_period
        self.isatty = sys.stdout.isatty()

        # Download state - keyed by download ID
        self.downloads: dict[str, dict[str, Any]] = {}
        self.total_downloads = 0
        self.completed_downloads = 0
        self.download_counter = 0
        self.lock = threading.Lock()
        self.active = False
        self.start_line = 3  # Start rendering from line 3
        self.update_thread = None
        self.stop_event = threading.Event()
        self.last_update_time = 0.0

    def message(self, msg: str) -> None:
        """Write message to output."""
        if self.fo:
            self.fo.write(msg)
            self.fo.flush()

    def start(self, total_downloads: int) -> None:
        """Start the progress display.

        Args:
            total_downloads: Expected number of downloads

        """
        with self.lock:
            self.total_downloads = total_downloads
            self.completed_downloads = 0
            self.downloads = {}
            self.download_counter = 0
            self.active = True
            self.stop_event.clear()

        if self.isatty and total_downloads > 0:
            # Clear screen and show header like working example
            self.message("\033[2J\033[H")  # Clear screen and move to top
            self.message("Starting AppImage downloads...\n\n")

            # Start update thread for periodic refreshes
            self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
            self.update_thread.start()

    def add_download(
        self, download_id: str, filename: str, total_size: int, prefix: str = ""
    ) -> None:
        """Add a new download to track.

        Args:
            download_id: Unique identifier for the download
            filename: Name of the file being downloaded
            total_size: Total file size in bytes
            prefix: Prefix to display (e.g., "[1/3] ")

        """
        with self.lock:
            self.download_counter += 1
            self.downloads[download_id] = {
                "filename": filename,
                "status": "downloading",
                "progress": 0,
                "total": total_size,
                "start_time": time.time(),
                "end_time": None,
                "prefix": prefix,
                "line_number": self.download_counter,
                "error": None,
            }
            self._update_display()

    def update_progress(self, download_id: str, progress: int) -> None:
        """Update progress for a download.

        Args:
            download_id: Unique identifier for the download
            progress: Current progress in bytes

        """
        with self.lock:
            if download_id in self.downloads:
                self.downloads[download_id]["progress"] = min(
                    progress, self.downloads[download_id]["total"]
                )
                # No immediate update - let the timer thread handle it

    def complete_download(
        self, download_id: str, success: bool = True, error_msg: str = ""
    ) -> None:
        """Mark a download as completed.

        Args:
            download_id: Unique identifier for the download
            success: Whether the download was successful
            error_msg: Error message if download failed

        """
        with self.lock:
            if download_id in self.downloads:
                download = self.downloads[download_id]
                download["end_time"] = time.time()
                download["progress"] = download["total"]

                if success:
                    download["status"] = "completed"
                else:
                    download["status"] = "failed"
                    download["error"] = error_msg

                self.completed_downloads += 1
                # No immediate update - let the timer thread handle it

    def stop(self) -> None:
        """Stop the progress display and show final state."""
        # Stop the update thread
        if self.update_thread and self.update_thread.is_alive():
            self.stop_event.set()
            self.update_thread.join(timeout=1.0)

        with self.lock:
            if not self.active:
                return

            # Show final state briefly
            if self.downloads and self.isatty:
                self._update_display()
                # Add summary
                self._display_summary()
                time.sleep(0.5)  # Brief pause to show final state

            self.active = False

    def _update_loop(self) -> None:
        """Continuous update loop for display refresh."""
        while not self.stop_event.is_set():
            try:
                with self.lock:
                    self._update_display()
                time.sleep(self.update_period)
            except Exception:
                break

    def _update_display(self) -> None:
        """Update the entire progress display."""
        if not self.active or not self.isatty or not self.downloads:
            return

        # Move to start position
        self.message(f"\033[{self.start_line};1H")

        # Render each download in its assigned line position
        for download_id in sorted(
            self.downloads.keys(), key=lambda x: self.downloads[x]["line_number"]
        ):
            self._render_download_line(self.downloads[download_id])

        # Clear any remaining lines in our area
        self.message("\033[K")

    def _render_download_line(self, download: dict[str, Any]) -> None:
        """Render a single download's progress line.

        Args:
            download: Download information dictionary

        """
        filename = download["filename"]
        status = download["status"]
        progress = download["progress"]
        total = download["total"]
        prefix = download.get("prefix", "")
        start_time = download["start_time"]

        # Calculate progress percentage
        if total > 0:
            pct = min(int(progress * 100 / total), 100)
        else:
            pct = 0

        # Calculate speed and ETA
        now = time.time()
        elapsed = now - start_time

        if elapsed > 0 and progress > 0:
            speed = progress / elapsed
            if speed > 0 and total > progress and status == "downloading":
                eta = (total - progress) / speed
                eta_str = format_time(eta)
            else:
                eta_str = "00:00"
            speed_str = f"{format_number(int(speed))}/s"
        else:
            speed_str = "-- B/s"
            eta_str = "--:--"

        # Create progress bar
        bar_width = 40
        if pct > 0:
            filled = int(bar_width * pct / 100)
            bar = "=" * filled + "-" * (bar_width - filled)
        else:
            bar = "-" * bar_width

        # Status indicator and formatting
        if status == "completed":
            status_icon = "✓"
            status_color = "\033[32m"  # Green
            description = f"Downloaded {filename}"
        elif status == "failed":
            status_icon = "✗"
            status_color = "\033[31m"  # Red
            description = f"Failed {filename}"
        else:  # downloading
            status_icon = ""
            status_color = ""
            description = f"Downloading {filename}"

        reset_color = "\033[0m" if status_color else ""

        # Format size information
        size_info = f"{format_number(progress)}/{format_number(total)}"

        # Truncate filename if too long
        max_desc_length = 40
        if len(description) > max_desc_length:
            description = description[: max_desc_length - 3] + "..."

        # Build single line like the working example
        if status == "completed":
            line = f"{status_color}{prefix}{status_icon} {description:<40} [{bar}] {pct:3d}% {size_info:>12} {speed_str:>8} ETA {eta_str}{reset_color}"
        elif status == "failed":
            error_msg = download.get("error", "Unknown error")
            line = f"{status_color}{prefix}{status_icon} {description:<40} FAILED: {error_msg}{reset_color}"
        else:
            line = f"{prefix}{description:<40} [{bar}] {pct:3d}% {size_info:>12} {speed_str:>8} ETA {eta_str}"

        # Output single line with clear to end
        self.message(line + "\033[K\n")

    def _display_summary(self) -> None:
        """Display download summary."""
        if not self.downloads:
            return

        # Count by status
        completed = sum(1 for d in self.downloads.values() if d["status"] == "completed")
        failed = sum(1 for d in self.downloads.values() if d["status"] == "failed")
        downloading = sum(1 for d in self.downloads.values() if d["status"] == "downloading")

        # Calculate totals
        total_downloaded = sum(d["progress"] for d in self.downloads.values())
        total_size = sum(d["total"] for d in self.downloads.values())
        overall_pct = int(total_downloaded * 100 / total_size) if total_size > 0 else 0

        summary = f"\n{'─' * 80}\n"
        summary += f"Overall: {completed}/{len(self.downloads)} completed"
        if failed > 0:
            summary += f", {failed} failed"
        if downloading > 0:
            summary += f", {downloading} active"
        summary += f" | Total: {format_number(total_downloaded)}/{format_number(total_size)} ({overall_pct}%)\n"

        self.message(summary)

    def is_complete(self) -> bool:
        """Check if all downloads are complete.

        Returns:
            True if all downloads are finished (completed or failed)

        """
        with self.lock:
            return (
                bool(self.downloads)
                and self.completed_downloads >= len(self.downloads)
                and all(d["status"] in ["completed", "failed"] for d in self.downloads.values())
            )
