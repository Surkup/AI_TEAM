#!/usr/bin/env python3
"""
Send a test COMMAND to DummyAgent.

Run DummyAgent in one terminal:
    ./venv/bin/python -m src.agents.dummy_agent

Then run this script in another terminal:
    ./venv/bin/python tests/send_command_to_dummy.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mindbus.core import MindBus


def main():
    print("Sending COMMAND to DummyAgent...")
    print("=" * 50)

    bus = MindBus()
    bus.connect()

    # Send COMMAND to dummy_agent
    print("\nSending: generate_article")
    cmd_id = bus.send_command(
        action="generate_article",
        params={
            "topic": "AI trends 2025",
            "length": 2000,
            "style": "professional"
        },
        target="dummy_agent",
        target_id="any",
        source="test-script",
        subject="test-task-001",
        timeout_seconds=60
    )

    print(f"✓ COMMAND sent: {cmd_id}")
    print("\nCheck DummyAgent terminal for execution.")
    print("Check Monitor terminal for RESULT message.")

    bus.disconnect()


if __name__ == "__main__":
    main()
