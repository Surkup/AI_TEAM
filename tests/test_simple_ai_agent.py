#!/usr/bin/env python3
"""
Test script for SimpleAIAgent with real LLM.

This test sends a COMMAND to SimpleAIAgent and verifies the RESULT.

Usage:
    # First, start the agent in another terminal:
    ./venv/bin/python -m src.agents.simple_ai_agent

    # Then run this test:
    ./venv/bin/python tests/test_simple_ai_agent.py

See: docs/project/IMPLEMENTATION_ROADMAP.md Step 1.6
"""

import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mindbus.core import MindBus


def main():
    print("\n" + "=" * 70)
    print("Test: SimpleAIAgent with real LLM")
    print("=" * 70)

    results_received = []
    errors_received = []
    result_event = threading.Event()

    def on_result(event, data):
        print("\n   Received RESULT!")
        results_received.append({"event": event, "data": data})
        result_event.set()

    def on_error(event, data):
        print("\n   Received ERROR!")
        errors_received.append({"event": event, "data": data})
        result_event.set()

    # Setup result listener
    print("\n1. Setting up result listener...")
    listener = MindBus()
    listener.connect()
    listener.subscribe("result.#", on_result)
    listener.subscribe("error.#", on_error)

    listener_thread = threading.Thread(
        target=listener.start_consuming,
        daemon=True
    )
    listener_thread.start()
    print("   Listener ready")

    time.sleep(0.5)

    # Send command to SimpleAIAgent
    print("\n2. Sending COMMAND to simple_ai_agent...")
    sender = MindBus()
    sender.connect()

    command_id = sender.send_command(
        action="generate_text",
        params={
            "prompt": "Write a haiku about artificial intelligence in exactly 3 lines.",
            "max_tokens": 100
        },
        target="simple_ai_agent",
        source="test-client",
        subject="test-generate-001",
        timeout_seconds=60
    )
    print(f"   COMMAND sent: {command_id[:8]}...")
    print("   Action: generate_text")
    print("   Prompt: Write a haiku about AI...")

    # Wait for response
    print("\n3. Waiting for RESULT (max 30 seconds)...")
    result_event.wait(timeout=30.0)

    sender.disconnect()

    # Check results
    print("\n4. Results:")
    print("-" * 50)

    if results_received:
        result = results_received[0]
        data = result["data"]
        output = data.get("output", {})

        print(f"   Status: {data.get('status', 'N/A')}")
        print(f"   Execution time: {data.get('execution_time_ms', 'N/A')}ms")

        if "text" in output:
            print(f"\n   Generated text:")
            print("   " + "-" * 40)
            for line in output["text"].strip().split("\n"):
                print(f"   {line}")
            print("   " + "-" * 40)

        metrics = output.get("metrics", {})
        if metrics:
            print(f"\n   Metrics:")
            print(f"      Model: {metrics.get('model', 'N/A')}")
            print(f"      Provider: {metrics.get('provider', 'N/A')}")
            print(f"      Tokens: {metrics.get('tokens_total', 'N/A')}")
            print(f"      Cost: ${metrics.get('cost_usd', 0):.6f}")
            print(f"      Generation time: {metrics.get('generation_time_seconds', 'N/A')}s")

        print("\n" + "=" * 70)
        print("TEST PASSED!")
        print("=" * 70)
        return True

    elif errors_received:
        error = errors_received[0]
        error_data = error["data"].get("error", {})
        print(f"   ERROR received:")
        print(f"      Code: {error_data.get('code', 'N/A')}")
        print(f"      Message: {error_data.get('message', 'N/A')}")

        print("\n" + "=" * 70)
        print("TEST FAILED (with ERROR)")
        print("=" * 70)
        return False

    else:
        print("   No response received within timeout")
        print("\n   Make sure SimpleAIAgent is running:")
        print("   ./venv/bin/python -m src.agents.simple_ai_agent")

        print("\n" + "=" * 70)
        print("TEST FAILED (timeout)")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
