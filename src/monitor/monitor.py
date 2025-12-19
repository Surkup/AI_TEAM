#!/usr/bin/env python3
"""
Monitor v0.2 — Real-time message observer for MindBus

The Monitor subscribes to ALL messages in the bus and displays them
with color-coded output for easy visual tracking.

Features:
- Subscribes to all message types (COMMAND, RESULT, ERROR, EVENT, CONTROL)
- Color-coded console output by message type
- Optional file logging (JSON Lines format)
- Shows validation errors when messages are rejected
- Special formatting for task.progress events (AGENT_SPEC v1.0.3)

Usage:
    python -m src.monitor.monitor

See: docs/project/IMPLEMENTATION_ROADMAP.md Step 1.3
See: docs/SSOT/AGENT_SPEC_v1.0.md Section 14.5 (Progress Heartbeat)
"""

import json
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.mindbus.core import MindBus


# =============================================================================
# ANSI Color Codes
# =============================================================================

class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Message type colors (from IMPLEMENTATION_ROADMAP)
    COMMAND = "\033[94m"    # Blue
    RESULT = "\033[92m"     # Green
    ERROR = "\033[91m"      # Red
    EVENT = "\033[93m"      # Yellow
    CONTROL = "\033[95m"    # Magenta/Purple

    # Additional
    GRAY = "\033[90m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"   # Same as RESULT
    YELLOW = "\033[93m"  # Same as EVENT


# Mapping from CloudEvents type to color
TYPE_COLORS = {
    "ai.team.command": Colors.COMMAND,
    "ai.team.result": Colors.RESULT,
    "ai.team.error": Colors.ERROR,
    "ai.team.event": Colors.EVENT,
    "ai.team.control": Colors.CONTROL,
}

TYPE_LABELS = {
    "ai.team.command": "COMMAND",
    "ai.team.result": "RESULT",
    "ai.team.error": "ERROR",
    "ai.team.event": "EVENT",
    "ai.team.control": "CONTROL",
}


# =============================================================================
# Monitor Configuration
# =============================================================================

class MonitorConfig:
    """Configuration for Monitor."""

    def __init__(self, config_path: str = "config/monitor.yaml"):
        try:
            with open(config_path) as f:
                self._config = yaml.safe_load(f)
        except FileNotFoundError:
            self._config = {}

        self._monitor = self._config.get("monitor", {})

    @property
    def log_to_file(self) -> bool:
        return self._monitor.get("log_to_file", False)

    @property
    def log_file_path(self) -> str:
        return self._monitor.get("log_file_path", "logs/monitor.jsonl")

    @property
    def show_message_body(self) -> bool:
        return self._monitor.get("show_message_body", True)

    @property
    def show_trace_id(self) -> bool:
        return self._monitor.get("show_trace_id", True)

    @property
    def compact_mode(self) -> bool:
        return self._monitor.get("compact_mode", False)


# =============================================================================
# Monitor
# =============================================================================

class Monitor:
    """
    Real-time message observer for MindBus.

    Subscribes to all messages and displays them with color-coded output.
    """

    def __init__(self, config_path: str = "config/monitor.yaml"):
        self.config = MonitorConfig(config_path)
        self.bus = MindBus()
        self.message_count = 0
        self.log_file: Optional[object] = None
        self._running = False

    def _format_timestamp(self, iso_time: Optional[str]) -> str:
        """Format timestamp for display."""
        if not iso_time:
            return datetime.now().strftime("%H:%M:%S")
        try:
            # Parse ISO format and display HH:MM:SS
            dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
            return dt.strftime("%H:%M:%S")
        except Exception:
            return iso_time[:8] if len(iso_time) >= 8 else iso_time

    def _format_trace_id(self, traceparent: Optional[str]) -> str:
        """Extract short trace ID from W3C traceparent."""
        if not traceparent:
            return "no-trace"
        # traceparent format: 00-{trace_id}-{span_id}-{flags}
        parts = traceparent.split("-")
        if len(parts) >= 2:
            return parts[1][:8]  # First 8 chars of trace_id
        return traceparent[:8]

    def _get_summary(self, event_type: str, data: dict) -> str:
        """Get a short summary of the message content."""
        if event_type == "ai.team.command":
            action = data.get("action", "?")
            return f"action={action}"
        elif event_type == "ai.team.result":
            status = data.get("status", "?")
            time_ms = data.get("execution_time_ms", 0)
            return f"status={status} time={time_ms}ms"
        elif event_type == "ai.team.error":
            error = data.get("error", {})
            code = error.get("code", "?")
            retryable = "retry" if error.get("retryable") else "no-retry"
            return f"code={code} ({retryable})"
        elif event_type == "ai.team.event":
            evt_type = data.get("event_type", "?")
            severity = data.get("severity", "INFO")
            # Special handling for task.progress (AGENT_SPEC v1.0.3)
            if evt_type == "task.progress":
                event_data = data.get("event_data", {})
                state = event_data.get("state", "?")
                elapsed = event_data.get("elapsed_seconds", 0)
                phase = event_data.get("phase", "?")
                return f"type={evt_type} state={state} elapsed={elapsed}s phase={phase}"
            return f"type={evt_type} [{severity}]"
        elif event_type == "ai.team.control":
            ctrl_type = data.get("control_type", "?")
            return f"signal={ctrl_type}"
        return ""

    def _print_message(self, event: dict, data: dict) -> None:
        """Print a formatted message to console."""
        event_type = event.get("type", "unknown")
        source = event.get("source", "?")
        subject = event.get("subject", "-")
        time_str = self._format_timestamp(event.get("time"))
        trace_id = self._format_trace_id(event.get("traceparent"))

        # Get color and label
        color = TYPE_COLORS.get(event_type, Colors.RESET)
        label = TYPE_LABELS.get(event_type, event_type.split(".")[-1].upper())

        # Get summary
        summary = self._get_summary(event_type, data)

        # Build output line
        if self.config.compact_mode:
            # Compact: [HH:MM:SS] TYPE source→subject (summary)
            line = (
                f"{Colors.DIM}[{time_str}]{Colors.RESET} "
                f"{color}{Colors.BOLD}{label:8}{Colors.RESET} "
                f"{Colors.CYAN}{source}{Colors.RESET}→{subject} "
                f"{Colors.DIM}({summary}){Colors.RESET}"
            )
        else:
            # Full format
            line = (
                f"\n{Colors.DIM}{'─' * 60}{Colors.RESET}\n"
                f"{Colors.DIM}[{time_str}]{Colors.RESET} "
                f"{color}{Colors.BOLD}{label}{Colors.RESET}\n"
                f"  {Colors.GRAY}source:{Colors.RESET} {source}\n"
                f"  {Colors.GRAY}subject:{Colors.RESET} {subject}"
            )
            if self.config.show_trace_id:
                line += f"\n  {Colors.GRAY}trace:{Colors.RESET} {trace_id}"
            line += f"\n  {Colors.GRAY}summary:{Colors.RESET} {summary}"

            if self.config.show_message_body:
                # Pretty print data (indented)
                data_str = json.dumps(data, indent=2, ensure_ascii=False)
                data_lines = data_str.split("\n")
                if len(data_lines) > 10:
                    data_lines = data_lines[:10] + ["  ..."]
                data_preview = "\n".join(f"  {Colors.DIM}{l}{Colors.RESET}" for l in data_lines)
                line += f"\n  {Colors.GRAY}data:{Colors.RESET}\n{data_preview}"

        print(line)

    def _log_to_file(self, event: dict, data: dict) -> None:
        """Log message to file in JSON Lines format."""
        if not self.log_file:
            return

        record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": {
                "type": event.get("type"),
                "source": event.get("source"),
                "id": event.get("id"),
                "subject": event.get("subject"),
                "traceparent": event.get("traceparent"),
            },
            "data": data
        }
        self.log_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.log_file.flush()

    def _on_message(self, event: dict, data: dict) -> None:
        """Callback for received messages."""
        self.message_count += 1
        self._print_message(event, data)

        if self.config.log_to_file:
            self._log_to_file(event, data)

    def _setup_file_logging(self) -> None:
        """Setup file logging if enabled."""
        if self.config.log_to_file:
            log_path = Path(self.config.log_file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_file = open(log_path, "a", encoding="utf-8")
            print(f"{Colors.GRAY}Logging to: {log_path}{Colors.RESET}")

    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown on Ctrl+C."""
        def signal_handler(sig, frame):
            print(f"\n\n{Colors.YELLOW}Shutting down...{Colors.RESET}")
            self._running = False
            self.bus.stop_consuming()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def start(self) -> None:
        """Start monitoring all messages."""
        print(f"\n{Colors.BOLD}{'🔍 ' * 20}{Colors.RESET}")
        print(f"{Colors.BOLD}  MindBus Monitor v0.1{Colors.RESET}")
        print(f"{Colors.BOLD}{'🔍 ' * 20}{Colors.RESET}\n")

        print(f"{Colors.GRAY}Connecting to RabbitMQ...{Colors.RESET}")
        self.bus.connect()
        print(f"{Colors.GREEN}✓ Connected{Colors.RESET}\n")

        self._setup_file_logging()
        self._setup_signal_handlers()

        # Subscribe to ALL message types
        patterns = [
            "cmd.#",      # All commands
            "result.#",   # All results
            "error.#",    # All errors
            "evt.#",      # All events
            "ctl.#",      # All control signals
        ]

        for pattern in patterns:
            queue_name = self.bus.subscribe(pattern, self._on_message)
            print(f"{Colors.GRAY}  Subscribed to: {pattern}{Colors.RESET}")

        print(f"\n{Colors.CYAN}Waiting for messages... (Ctrl+C to stop){Colors.RESET}\n")

        self._running = True
        try:
            self.bus.start_consuming()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop monitoring and cleanup."""
        self._running = False

        if self.log_file:
            self.log_file.close()

        self.bus.disconnect()

        print(f"\n{Colors.GRAY}Total messages observed: {self.message_count}{Colors.RESET}")
        print(f"{Colors.GREEN}Monitor stopped.{Colors.RESET}\n")


# =============================================================================
# Main
# =============================================================================

def main():
    """Run the monitor."""
    monitor = Monitor()
    monitor.start()


if __name__ == "__main__":
    main()
