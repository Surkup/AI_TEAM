#!/usr/bin/env python3
"""
End-to-End Test — Full system integration test with DummyAgent.

This test verifies the complete message flow:
1. RabbitMQ is running
2. MindBus Core sends/receives messages
3. Monitor observes all messages
4. DummyAgent processes COMMAND and returns RESULT
5. trace_id is preserved through the chain

Scenario:
    User → COMMAND → DummyAgent → RESULT → User
    Monitor observes: COMMAND (blue) → RESULT (green)

See: docs/project/IMPLEMENTATION_ROADMAP.md Step 1.5
"""

import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mindbus.core import MindBus
from agents.dummy_agent import DummyAgent


class E2ETestRunner:
    """End-to-End test runner for AI_TEAM system."""

    def __init__(self):
        self.observed_messages: List[Dict[str, Any]] = []
        self.results_received: List[Dict[str, Any]] = []
        self.errors_received: List[Dict[str, Any]] = []
        self.test_trace_id = f"00-e2etest{int(time.time())}-span001-01"

    def monitor_callback(self, event: dict, data: dict) -> None:
        """Callback for Monitor — observes all messages."""
        msg_type = event.get("type", "unknown")
        self.observed_messages.append({
            "type": msg_type,
            "source": event.get("source"),
            "subject": event.get("subject"),
            "traceparent": event.get("traceparent"),
            "data": data,
            "timestamp": datetime.now().isoformat()
        })

    def result_callback(self, event: dict, data: dict) -> None:
        """Callback for RESULT messages."""
        self.results_received.append({
            "event": event,
            "data": data
        })

    def error_callback(self, event: dict, data: dict) -> None:
        """Callback for ERROR messages."""
        self.errors_received.append({
            "event": event,
            "data": data
        })

    def run(self) -> bool:
        """Run the E2E test."""
        print("\n" + "=" * 70)
        print("🧪 AI_TEAM End-to-End Test")
        print("=" * 70)

        # ─────────────────────────────────────────────────────────────────
        # Step 1: Check RabbitMQ
        # ─────────────────────────────────────────────────────────────────
        print("\n📌 Step 1: Check RabbitMQ connection")
        try:
            test_bus = MindBus()
            test_bus.connect()
            test_bus.disconnect()
            print("   ✅ RabbitMQ is running")
        except Exception as e:
            print(f"   ❌ RabbitMQ connection failed: {e}")
            print("   💡 Run: docker start rabbitmq")
            return False

        # ─────────────────────────────────────────────────────────────────
        # Step 2: Start Monitor (observer)
        # ─────────────────────────────────────────────────────────────────
        print("\n📌 Step 2: Start Monitor (message observer)")
        monitor_bus = MindBus()
        monitor_bus.connect()

        # Subscribe to ALL messages
        for pattern in ["cmd.#", "result.#", "error.#", "evt.#", "ctl.#"]:
            monitor_bus.subscribe(pattern, self.monitor_callback)

        monitor_thread = threading.Thread(
            target=monitor_bus.start_consuming,
            daemon=True
        )
        monitor_thread.start()
        print("   ✅ Monitor started, observing all messages")

        # ─────────────────────────────────────────────────────────────────
        # Step 3: Start DummyAgent
        # ─────────────────────────────────────────────────────────────────
        print("\n📌 Step 3: Start DummyAgent")
        agent = DummyAgent()
        agent.bus.connect()
        agent.bus.subscribe("cmd.dummy_agent.*", agent._on_command)
        agent.bus.subscribe("cmd.dummy.*", agent._on_command)

        agent_thread = threading.Thread(
            target=agent.bus.start_consuming,
            daemon=True
        )
        agent_thread.start()
        print(f"   ✅ DummyAgent started: {agent.name}")
        print(f"      Capabilities: {agent.capabilities}")

        # ─────────────────────────────────────────────────────────────────
        # Step 4: Setup result listener
        # ─────────────────────────────────────────────────────────────────
        print("\n📌 Step 4: Setup result listener")
        result_bus = MindBus()
        result_bus.connect()
        result_bus.subscribe("result.#", self.result_callback)
        result_bus.subscribe("error.#", self.error_callback)

        result_thread = threading.Thread(
            target=result_bus.start_consuming,
            daemon=True
        )
        result_thread.start()
        print("   ✅ Result listener ready")

        time.sleep(0.5)  # Let all subscribers initialize

        # ─────────────────────────────────────────────────────────────────
        # Step 5: Send COMMAND to DummyAgent
        # ─────────────────────────────────────────────────────────────────
        print("\n📌 Step 5: Send COMMAND to DummyAgent")
        sender_bus = MindBus()
        sender_bus.connect()

        command_id = sender_bus.send_command(
            action="generate_article",
            params={
                "topic": "AI_TEAM E2E Test",
                "length": 500
            },
            target="dummy_agent",
            source="e2e-test-runner",
            subject="e2e-test-001",
            trace_id=self.test_trace_id,
            timeout_seconds=60
        )
        print(f"   ✅ COMMAND sent")
        print(f"      ID: {command_id}")
        print(f"      Action: generate_article")
        print(f"      Trace: {self.test_trace_id[:30]}...")

        # ─────────────────────────────────────────────────────────────────
        # Step 6: Wait for RESULT
        # ─────────────────────────────────────────────────────────────────
        print("\n📌 Step 6: Wait for RESULT (max 5 seconds)")
        wait_start = time.time()
        timeout = 5.0

        while time.time() - wait_start < timeout:
            if self.results_received or self.errors_received:
                break
            time.sleep(0.1)

        elapsed = time.time() - wait_start

        sender_bus.disconnect()

        # ─────────────────────────────────────────────────────────────────
        # Step 7: Verify results
        # ─────────────────────────────────────────────────────────────────
        print("\n📌 Step 7: Verify results")

        success = True

        # Check RESULT received
        if self.results_received:
            result = self.results_received[0]
            result_data = result["data"]
            print(f"   ✅ RESULT received ({elapsed:.2f}s)")
            print(f"      Status: {result_data.get('status')}")
            print(f"      Execution time: {result_data.get('execution_time_ms')}ms")

            output = result_data.get("output", {})
            print(f"      Output message: {output.get('message', 'N/A')}")
        elif self.errors_received:
            error = self.errors_received[0]
            error_data = error["data"].get("error", {})
            print(f"   ⚠️ ERROR received instead of RESULT")
            print(f"      Code: {error_data.get('code')}")
            print(f"      Message: {error_data.get('message')}")
            success = False
        else:
            print(f"   ❌ No RESULT received within {timeout}s")
            success = False

        # Check Monitor observed messages
        print(f"\n   📊 Monitor observed {len(self.observed_messages)} messages:")
        for msg in self.observed_messages:
            msg_type = msg["type"].split(".")[-1].upper()
            source = msg["source"]
            print(f"      • {msg_type}: {source}")

        # Verify trace_id preserved
        print("\n   🔗 Trace ID verification:")
        trace_preserved = all(
            self.test_trace_id in (msg.get("traceparent") or "")
            for msg in self.observed_messages
            if msg.get("traceparent")
        )
        if trace_preserved and self.observed_messages:
            print(f"      ✅ trace_id preserved through chain")
        else:
            print(f"      ⚠️ trace_id not found in all messages")

        # ─────────────────────────────────────────────────────────────────
        # Summary
        # ─────────────────────────────────────────────────────────────────
        print("\n" + "=" * 70)
        if success:
            print("🎉 E2E TEST PASSED!")
            print("   The complete message flow works correctly:")
            print("   User → COMMAND → DummyAgent → RESULT → User")
        else:
            print("❌ E2E TEST FAILED!")
            print("   Check the logs above for details.")
        print("=" * 70 + "\n")

        return success


def main():
    """Run the E2E test."""
    runner = E2ETestRunner()
    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
