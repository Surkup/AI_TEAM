#!/usr/bin/env python3
"""
Integration test for MindBus with RabbitMQ.

This script tests:
1. Connection to RabbitMQ
2. Sending a COMMAND message
3. Receiving the message via subscription
4. SSOT validation works end-to-end

Prerequisites:
- RabbitMQ running on localhost:5672
- docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
"""

import sys
import time
import threading
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mindbus.core import MindBus


def test_mindbus_connection():
    """Test basic connection to RabbitMQ."""
    print("=" * 60)
    print("TEST 1: Connection to RabbitMQ")
    print("=" * 60)

    bus = MindBus()
    try:
        bus.connect()
        print("✅ Successfully connected to RabbitMQ!")
        bus.disconnect()
        print("✅ Successfully disconnected!")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


def test_send_command():
    """Test sending a COMMAND message."""
    print("\n" + "=" * 60)
    print("TEST 2: Send COMMAND message")
    print("=" * 60)

    bus = MindBus()
    try:
        bus.connect()

        # Send a command
        message_id = bus.send_command(
            action="generate_article",
            params={"topic": "AI trends 2025", "length": 2000},
            target="writer",
            source="test-script",
            subject="test-task-001",
            timeout_seconds=300
        )

        print(f"✅ COMMAND sent successfully!")
        print(f"   Message ID: {message_id}")
        print(f"   Action: generate_article")
        print(f"   Target: writer")

        bus.disconnect()
        return True
    except Exception as e:
        print(f"❌ Failed to send command: {e}")
        return False


def test_send_event():
    """Test sending an EVENT message."""
    print("\n" + "=" * 60)
    print("TEST 3: Send EVENT message")
    print("=" * 60)

    bus = MindBus()
    try:
        bus.connect()

        message_id = bus.send_event(
            event_type_name="task.started",
            event_data={"task_id": "test-001", "agent": "writer"},
            source="test-script",
            severity="INFO",
            tags=["test", "integration"]
        )

        print(f"✅ EVENT sent successfully!")
        print(f"   Message ID: {message_id}")
        print(f"   Event Type: task.started")

        bus.disconnect()
        return True
    except Exception as e:
        print(f"❌ Failed to send event: {e}")
        return False


def test_send_and_receive():
    """Test sending and receiving messages via subscription."""
    print("\n" + "=" * 60)
    print("TEST 4: Send and Receive (Pub/Sub)")
    print("=" * 60)

    received_messages = []
    message_received_event = threading.Event()

    def on_message(event, data):
        print(f"   📨 Received message!")
        print(f"      Type: {event['type']}")
        print(f"      Action: {data.get('action', 'N/A')}")
        received_messages.append(data)
        message_received_event.set()

    # Create two bus instances (publisher and subscriber)
    publisher = MindBus()
    subscriber = MindBus()

    try:
        publisher.connect()
        subscriber.connect()

        # Subscribe to commands
        queue_name = subscriber.subscribe("cmd.test.*", on_message)
        print(f"   Subscribed to: cmd.test.*")
        print(f"   Queue: {queue_name}")

        # Start consuming in a thread
        consume_thread = threading.Thread(target=subscriber.start_consuming, daemon=True)
        consume_thread.start()

        # Give subscriber time to start
        time.sleep(0.3)

        # Send a command
        message_id = publisher.send_command(
            action="test_action",
            params={"test": True},
            target="test",
            target_id="any",
            source="test-publisher"
        )
        print(f"   Sent command: {message_id}")

        # Wait for message to be received (with timeout)
        message_received = message_received_event.wait(timeout=3.0)

        # Gracefully close publisher first
        publisher.disconnect()

        # Check result before closing subscriber
        if received_messages:
            print(f"✅ Message received and validated!")
            result = True
        else:
            print("❌ No messages received")
            result = False

        # Note: we don't call stop_consuming() to avoid race condition
        # The daemon thread will be terminated when main thread exits
        return result

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_validation_rejection():
    """Test that invalid messages are rejected."""
    print("\n" + "=" * 60)
    print("TEST 5: SSOT Validation (reject invalid data)")
    print("=" * 60)

    bus = MindBus()
    try:
        bus.connect()

        # Try to send invalid command (missing action)
        try:
            bus._validate_and_send(
                event_type="ai.team.command",
                source="test",
                data={"params": {}},  # Missing 'action' field!
                routing_key="cmd.test.any"
            )
            print("❌ Should have rejected invalid message!")
            return False
        except ValueError as e:
            print(f"✅ Correctly rejected invalid message:")
            print(f"   Error: {str(e)[:80]}...")

        bus.disconnect()
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def main():
    """Run all integration tests."""
    print("\n" + "🐰" * 30)
    print("  MindBus Integration Tests")
    print("  RabbitMQ + CloudEvents + Pydantic")
    print("🐰" * 30 + "\n")

    results = []

    results.append(("Connection", test_mindbus_connection()))
    results.append(("Send COMMAND", test_send_command()))
    results.append(("Send EVENT", test_send_event()))
    results.append(("Pub/Sub", test_send_and_receive()))
    results.append(("Validation", test_validation_rejection()))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! MindBus is working correctly.")
        return 0
    else:
        print("\n⚠️  Some tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
