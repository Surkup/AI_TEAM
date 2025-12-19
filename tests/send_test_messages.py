#!/usr/bin/env python3
"""
Test script to send sample messages for Monitor testing.

Run Monitor in one terminal:
    ./venv/bin/python -m src.monitor.monitor

Then run this script in another terminal:
    ./venv/bin/python tests/send_test_messages.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mindbus.core import MindBus


def main():
    print("Sending test messages to MindBus...")
    print("=" * 50)

    bus = MindBus()
    bus.connect()

    # 1. Send COMMAND
    print("\n1. Sending COMMAND...")
    cmd_id = bus.send_command(
        action="generate_article",
        params={"topic": "AI trends 2025", "length": 2000},
        target="writer",
        source="test-orchestrator",
        subject="task-001",
        timeout_seconds=300
    )
    print(f"   ✓ COMMAND sent: {cmd_id[:8]}...")
    time.sleep(0.5)

    # 2. Send RESULT
    print("\n2. Sending RESULT...")
    result_id = bus.send_result(
        output={"article": "AI is transforming...", "word_count": 2000},
        execution_time_ms=12500,
        source="agent.writer.001",
        subject="task-001",
        correlation_id=cmd_id,
        metrics={"model": "gpt-4", "tokens": 3500, "cost_usd": 0.15}
    )
    print(f"   ✓ RESULT sent: {result_id[:8]}...")
    time.sleep(0.5)

    # 3. Send ERROR
    print("\n3. Sending ERROR...")
    error_id = bus.send_error(
        code="DEADLINE_EXCEEDED",
        message="LLM API request timed out after 30 seconds",
        retryable=True,
        source="agent.researcher.002",
        subject="task-002",
        details={"timeout_seconds": 30, "provider": "openai"},
        execution_time_ms=30500
    )
    print(f"   ✓ ERROR sent: {error_id[:8]}...")
    time.sleep(0.5)

    # 4. Send EVENT
    print("\n4. Sending EVENT...")
    event_id = bus.send_event(
        event_type_name="task.completed",
        event_data={
            "task_id": "task-001",
            "status": "SUCCESS",
            "duration_seconds": 125
        },
        source="orchestrator-core",
        subject="task-001",
        severity="INFO",
        tags=["task", "completion"]
    )
    print(f"   ✓ EVENT sent: {event_id[:8]}...")
    time.sleep(0.5)

    # 5. Send CONTROL
    print("\n5. Sending CONTROL...")
    control_id = bus.send_control(
        control_type="pause",
        target="writer",
        source="human-operator",
        reason="Maintenance window starting",
        parameters={"grace_period_seconds": 60}
    )
    print(f"   ✓ CONTROL sent: {control_id[:8]}...")

    bus.disconnect()

    print("\n" + "=" * 50)
    print("All 5 test messages sent!")
    print("Check Monitor output to see them displayed.")


if __name__ == "__main__":
    main()
