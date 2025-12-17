"""
Enhanced Status Bar - Shows logs, CPU and GPU usage

Displays:
- Latest log message (left)
- CPU usage (right, aggregated across all app processes)
- GPU usage (right, shows active workload type)

WHY aggregate: Main app spawns subprocesses for separation and beat detection.
User should see total resource usage, not just main process.
"""

from __future__ import annotations

from PySide6.QtWidgets import QStatusBar, QLabel
from PySide6.QtCore import QTimer
from typing import Dict, Set
import psutil
import os


class EnhancedStatusBar(QStatusBar):
    """Status bar with log monitoring and resource usage"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Status message (left side)
        self._status_label = QLabel("Bereit")
        self._status_label.setStyleSheet("padding: 0 8px;")
        self.addWidget(self._status_label, 1)  # Stretch factor 1

        # Separator
        sep1 = QLabel("|")
        sep1.setStyleSheet("color: #555; padding: 0 4px;")
        self.addPermanentWidget(sep1)

        # CPU usage (right side)
        self._cpu_label = QLabel("CPU: --")
        self._cpu_label.setStyleSheet("padding: 0 8px;")
        self.addPermanentWidget(self._cpu_label)

        # Separator
        sep2 = QLabel("|")
        sep2.setStyleSheet("color: #555; padding: 0 4px;")
        self.addPermanentWidget(sep2)

        # GPU usage (right side)
        self._gpu_label = QLabel("GPU: --")
        self._gpu_label.setStyleSheet("padding: 0 8px;")
        self.addPermanentWidget(self._gpu_label)

        # Get PID for monitoring
        self._pid = os.getpid()
        self._process = psutil.Process(self._pid)

        # Track known processes for CPU calculation
        # WHY: psutil.cpu_percent() needs prior call to establish baseline
        self._known_processes: Dict[int, psutil.Process] = {self._pid: self._process}

        # Log file monitoring
        self._log_file = None
        self._log_position = 0
        self._find_log_file()

        # Update timer (every 1 second)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_stats)
        self._timer.start(1000)  # 1 second

        # Initial update (primes CPU measurement)
        self._update_stats()

    def _find_log_file(self):
        """Find the application log file"""
        try:
            from config import LOG_FILE

            if LOG_FILE.exists():
                self._log_file = LOG_FILE
                # Start reading from end
                self._log_position = LOG_FILE.stat().st_size
        except Exception:
            pass

    def _update_stats(self):
        """Update CPU, GPU and log info"""
        try:
            # Get aggregated CPU and active workload info
            total_cpu, active_workload = self._get_aggregated_usage()
            self._cpu_label.setText(f"CPU: {total_cpu:.0f}%")

            # Update GPU indicator based on active workload
            if active_workload:
                self._gpu_label.setText(f"GPU: {active_workload}")
            else:
                self._gpu_label.setText("GPU: --")

            # Update log message
            self._update_log_message()

        except Exception:
            # Process might have been terminated
            pass

    def _get_aggregated_usage(self) -> tuple[float, str]:
        """
        Get total CPU usage across all app processes and detect active workload.

        Returns:
            Tuple of (total_cpu_percent, active_workload_name)
            active_workload_name is "BeatNet", "Separation", or "" if idle

        WHY: User should see total resource usage, not just main process.
        Subprocesses (separation, beatnet) can use significant CPU/GPU.
        """
        total_cpu = 0.0
        active_workload = ""
        current_pids: Set[int] = set()

        try:
            # 1. Main process CPU
            try:
                total_cpu += self._process.cpu_percent(interval=0)
                current_pids.add(self._pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            # 2. Child processes (separation subprocesses, spawned workers)
            try:
                for child in self._process.children(recursive=True):
                    try:
                        pid = child.pid
                        current_pids.add(pid)

                        # Track process for future measurements
                        if pid not in self._known_processes:
                            self._known_processes[pid] = child
                            # First call primes the measurement, returns 0
                            child.cpu_percent(interval=0)
                        else:
                            cpu = child.cpu_percent(interval=0)
                            total_cpu += cpu

                            # Detect workload type from command line
                            cmdline = child.cmdline()
                            cmdline_str = " ".join(cmdline) if cmdline else ""

                            if "--separation-subprocess" in cmdline_str:
                                if not active_workload or cpu > 10:
                                    active_workload = "Separation"
                            elif "beatnet-service" in cmdline_str:
                                if not active_workload or cpu > 10:
                                    active_workload = "BeatNet"

                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            # 3. External beatnet-service processes (may not be direct children)
            # WHY: beatnet-service is a standalone binary, might be orphaned
            try:
                for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                    try:
                        pid = proc.info["pid"]
                        name = proc.info["name"] or ""
                        cmdline = proc.info["cmdline"] or []

                        # Check if it's a beatnet-service process
                        is_beatnet = "beatnet-service" in name or any(
                            "beatnet-service" in arg for arg in cmdline
                        )

                        if is_beatnet and pid not in current_pids:
                            current_pids.add(pid)

                            if pid not in self._known_processes:
                                self._known_processes[pid] = psutil.Process(pid)
                                # Prime the measurement
                                self._known_processes[pid].cpu_percent(interval=0)
                            else:
                                cpu = self._known_processes[pid].cpu_percent(interval=0)
                                total_cpu += cpu
                                if cpu > 5:  # Only show if actually doing work
                                    active_workload = "BeatNet"

                    except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError):
                        pass
            except Exception:
                pass

            # 4. Clean up stale process references
            stale_pids = set(self._known_processes.keys()) - current_pids - {self._pid}
            for stale_pid in stale_pids:
                self._known_processes.pop(stale_pid, None)

        except Exception:
            pass

        return total_cpu, active_workload

    def _update_log_message(self):
        """Read latest log line and display it"""
        if not self._log_file or not self._log_file.exists():
            return

        try:
            # Check if file has grown
            current_size = self._log_file.stat().st_size

            if current_size > self._log_position:
                # Read new content
                with open(self._log_file, "r", encoding="utf-8") as f:
                    f.seek(self._log_position)
                    new_lines = f.readlines()
                    self._log_position = current_size

                    # Get last non-empty line
                    for line in reversed(new_lines):
                        line = line.strip()
                        if line:
                            # Extract just the message part (after log prefix)
                            # Format: "2025-12-05 10:30:45 - StemSeparator - INFO - file.py:line - message"
                            parts = line.split(" - ")
                            if len(parts) >= 5:
                                message = " - ".join(parts[4:])
                            else:
                                message = line

                            # Truncate if too long
                            if len(message) > 100:
                                message = message[:97] + "..."

                            self._status_label.setText(message)
                            break

        except Exception as e:
            pass

    def showMessage(self, message: str, timeout: int = 0):
        """Override to update our custom status label"""
        self._status_label.setText(message)
        if timeout > 0:
            QTimer.singleShot(timeout, lambda: self._status_label.setText("Bereit"))
