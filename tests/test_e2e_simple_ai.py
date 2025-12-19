#!/usr/bin/env python3
"""
End-to-End Test — Full system integration test with SimpleAIAgent.

This test verifies the complete message flow with a real LLM:
1. RabbitMQ is running
2. MindBus Core sends/receives messages
3. Monitor observes all messages
4. SimpleAIAgent processes COMMAND and calls real LLM
5. RESULT contains generated text and metrics

Scenario:
    User → COMMAND (generate_text) → SimpleAIAgent → LLM API → RESULT → User

See: docs/project/IMPLEMENTATION_ROADMAP.md Step 1.6
"""

import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mindbus.core import MindBus
from agents.simple_ai_agent import SimpleAIAgent


class E2ESimpleAITestRunner:
    """End-to-End test runner for SimpleAIAgent."""

    def __init__(self):
        self.observed_messages: List[Dict[str, Any]] = []
        self.results_received: List[Dict[str, Any]] = []
        self.errors_received: List[Dict[str, Any]] = []
        self.test_trace_id = f"00-e2eai{int(time.time())}-span001-01"

    def monitor_callback(self, event: dict, data: dict) -> None:
        """Callback for Monitor — observes all messages."""
        msg_type = event.get("type", "unknown")
        self.observed_messages.append({
            "type": msg_type,
            "source": event.get("source"),
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
        """Run the E2E test with SimpleAIAgent."""
        print("\n" + "=" * 70)
        print("AI_TEAM E2E Test — SimpleAIAgent with Real LLM")
        print("=" * 70)

        # ─────────────────────────────────────────────────────────────────
        # Step 1: Check RabbitMQ
        # ─────────────────────────────────────────────────────────────────
        print("\n Step 1: Check RabbitMQ connection")
        try:
            test_bus = MindBus()
            test_bus.connect()
            test_bus.disconnect()
            print("   RabbitMQ is running")
        except Exception as e:
            print(f"   RabbitMQ connection failed: {e}")
            print("   Run: docker start rabbitmq")
            return False

        # ─────────────────────────────────────────────────────────────────
        # Step 2: Check API Key
        # ─────────────────────────────────────────────────────────────────
        print("\n Step 2: Check LLM API Key")
        import os
        from dotenv import load_dotenv
        load_dotenv()

        openai_key = os.getenv("OPENAI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")

        if openai_key and not openai_key.startswith("sk-your"):
            print("   OpenAI API key found")
            provider = "openai"
        elif anthropic_key and not anthropic_key.startswith("sk-ant-your"):
            print("   Anthropic API key found")
            provider = "anthropic"
        else:
            print("   No valid API key found!")
            print("   Please set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env file")
            print("   Copy .env.example to .env and add your key")
            return False

        # ─────────────────────────────────────────────────────────────────
        # Step 3: Start Monitor (observer)
        # ─────────────────────────────────────────────────────────────────
        print("\n Step 3: Start Monitor (message observer)")
        monitor_bus = MindBus()
        monitor_bus.connect()

        for pattern in ["cmd.#", "result.#", "error.#"]:
            monitor_bus.subscribe(pattern, self.monitor_callback)

        monitor_thread = threading.Thread(
            target=monitor_bus.start_consuming,
            daemon=True
        )
        monitor_thread.start()
        print("   Monitor started")

        # ─────────────────────────────────────────────────────────────────
        # Step 4: Start SimpleAIAgent
        # ─────────────────────────────────────────────────────────────────
        print("\n Step 4: Start SimpleAIAgent")
        try:
            agent = SimpleAIAgent()
            agent.bus.connect()
            agent.bus.subscribe("cmd.simple_ai_agent.*", agent._on_command)
            agent.bus.subscribe("cmd.ai_agent.*", agent._on_command)

            agent_thread = threading.Thread(
                target=agent.bus.start_consuming,
                daemon=True
            )
            agent_thread.start()
            print(f"   SimpleAIAgent started: {agent.name}")
            print(f"   Provider: {agent.provider}, Model: {agent.model}")
        except Exception as e:
            print(f"   Failed to start SimpleAIAgent: {e}")
            return False

        # ─────────────────────────────────────────────────────────────────
        # Step 5: Setup result listener
        # ─────────────────────────────────────────────────────────────────
        print("\n Step 5: Setup result listener")
        result_bus = MindBus()
        result_bus.connect()
        result_bus.subscribe("result.#", self.result_callback)
        result_bus.subscribe("error.#", self.error_callback)

        result_thread = threading.Thread(
            target=result_bus.start_consuming,
            daemon=True
        )
        result_thread.start()
        print("   Result listener ready")

        time.sleep(0.5)

        # ─────────────────────────────────────────────────────────────────
        # Step 6: Send COMMAND to SimpleAIAgent
        # ─────────────────────────────────────────────────────────────────
        print("\n Step 6: Send COMMAND to SimpleAIAgent")
        sender_bus = MindBus()
        sender_bus.connect()

        prompt = "Write exactly one sentence about why teamwork is important."

        command_id = sender_bus.send_command(
            action="generate_text",
            params={
                "prompt": prompt,
                "max_tokens": 50
            },
            target="simple_ai_agent",
            source="e2e-test-runner",
            subject="e2e-ai-test-001",
            trace_id=self.test_trace_id,
            timeout_seconds=60
        )
        print(f"   COMMAND sent")
        print(f"   ID: {command_id[:8]}...")
        print(f"   Prompt: {prompt}")

        # ─────────────────────────────────────────────────────────────────
        # Step 7: Wait for RESULT
        # ─────────────────────────────────────────────────────────────────
        print("\n Step 7: Wait for RESULT (max 30 seconds)")
        wait_start = time.time()
        timeout = 30.0

        while time.time() - wait_start < timeout:
            if self.results_received or self.errors_received:
                break
            time.sleep(0.1)

        elapsed = time.time() - wait_start
        sender_bus.disconnect()

        # ─────────────────────────────────────────────────────────────────
        # Step 8: Verify results
        # ─────────────────────────────────────────────────────────────────
        print("\n Step 8: Verify results")

        success = True

        if self.results_received:
            result = self.results_received[0]
            result_data = result["data"]
            output = result_data.get("output", {})

            print(f"   RESULT received ({elapsed:.2f}s)")
            print(f"   Status: {result_data.get('status')}")
            print(f"   Execution time: {result_data.get('execution_time_ms')}ms")

            # Show generated text
            generated_text = output.get("text", "N/A")
            print(f"\n   Generated text:")
            print("   " + "-" * 50)
            print(f"   {generated_text}")
            print("   " + "-" * 50)

            # Show metrics
            metrics = output.get("metrics", {})
            if metrics:
                print(f"\n   LLM Metrics:")
                print(f"      Model: {metrics.get('model')}")
                print(f"      Provider: {metrics.get('provider')}")
                print(f"      Tokens: {metrics.get('tokens_total')}")
                print(f"      Cost: ${metrics.get('cost_usd', 0):.6f}")

        elif self.errors_received:
            error = self.errors_received[0]
            error_data = error["data"].get("error", {})
            print(f"   ERROR received instead of RESULT")
            print(f"   Code: {error_data.get('code')}")
            print(f"   Message: {error_data.get('message')}")
            success = False
        else:
            print(f"   No RESULT received within {timeout}s")
            success = False

        # Monitor stats
        print(f"\n   Monitor observed {len(self.observed_messages)} messages")

        # ─────────────────────────────────────────────────────────────────
        # Summary
        # ─────────────────────────────────────────────────────────────────
        print("\n" + "=" * 70)
        if success:
            print("E2E TEST PASSED!")
            print("   Real LLM integration works correctly:")
            print("   User -> COMMAND -> SimpleAIAgent -> LLM API -> RESULT -> User")
        else:
            print("E2E TEST FAILED!")
            print("   Check the logs above for details.")
        print("=" * 70 + "\n")

        return success


def main():
    """Run the E2E test."""
    runner = E2ESimpleAITestRunner()
    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
