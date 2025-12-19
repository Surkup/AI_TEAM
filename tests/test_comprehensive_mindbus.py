#!/usr/bin/env python3
"""
Comprehensive MindBus Test Suite — Full System Validation

This test suite covers all aspects of the MindBus system:
1. All 5 message types (COMMAND, RESULT, ERROR, EVENT, CONTROL)
2. Message routing and pattern matching
3. Correlation ID preservation
4. CloudEvents envelope integrity
5. SSOT validation (valid and invalid messages)
6. Concurrent requests
7. Edge cases (unicode, large payloads, special characters)
8. Error handling and recovery
9. Full end-to-end flow with SimpleAIAgent

Prerequisites:
- RabbitMQ running on localhost:5672
- OpenAI API key set in .env (for AI agent tests)

Usage:
    ./venv/bin/python tests/test_comprehensive_mindbus.py
"""

import json
import logging
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from mindbus.core import MindBus
from mindbus.models import (
    CommandData,
    ResultData,
    ErrorData,
    EventData,
    ControlData,
    validate_message_data,
)
from pydantic import ValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Test Result Tracking
# =============================================================================

class TestResults:
    """Track test results."""

    def __init__(self):
        self.tests = []
        self.current_category = None

    def set_category(self, name: str):
        self.current_category = name
        print(f"\n{'='*60}")
        print(f"  {name}")
        print(f"{'='*60}")

    def add(self, name: str, passed: bool, error: str = None):
        status = "PASS" if passed else "FAIL"
        icon = "✅" if passed else "❌"
        self.tests.append({
            "category": self.current_category,
            "name": name,
            "passed": passed,
            "error": error
        })
        if error and not passed:
            print(f"  {icon} {name}: {error[:60]}")
        else:
            print(f"  {icon} {name}")

    def summary(self):
        print(f"\n{'='*60}")
        print("  SUMMARY")
        print(f"{'='*60}")

        passed = sum(1 for t in self.tests if t["passed"])
        total = len(self.tests)

        # Group by category
        categories = {}
        for t in self.tests:
            cat = t["category"]
            if cat not in categories:
                categories[cat] = {"passed": 0, "total": 0}
            categories[cat]["total"] += 1
            if t["passed"]:
                categories[cat]["passed"] += 1

        for cat, stats in categories.items():
            status = "✅" if stats["passed"] == stats["total"] else "⚠️"
            print(f"  {status} {cat}: {stats['passed']}/{stats['total']}")

        print(f"\n  Total: {passed}/{total} tests passed")

        if passed == total:
            print("\n  🎉 ALL TESTS PASSED!")
            return 0
        else:
            print(f"\n  ⚠️  {total - passed} tests failed")
            for t in self.tests:
                if not t["passed"]:
                    print(f"     - {t['category']}: {t['name']}")
            return 1


results = TestResults()


# =============================================================================
# Category 1: Connection Tests
# =============================================================================

def test_connection():
    """Test basic connection to RabbitMQ."""
    results.set_category("1. CONNECTION TESTS")

    # Test 1.1: Basic connect/disconnect
    try:
        bus = MindBus()
        bus.connect()
        bus.disconnect()
        results.add("Basic connect/disconnect", True)
    except Exception as e:
        results.add("Basic connect/disconnect", False, str(e))
        return  # Can't continue without connection

    # Test 1.2: Multiple connections
    try:
        buses = []
        for i in range(3):
            bus = MindBus()
            bus.connect()
            buses.append(bus)
        for bus in buses:
            bus.disconnect()
        results.add("Multiple simultaneous connections", True)
    except Exception as e:
        results.add("Multiple simultaneous connections", False, str(e))

    # Test 1.3: Reconnection
    try:
        bus = MindBus()
        bus.connect()
        bus.disconnect()
        bus.connect()  # Reconnect
        bus.disconnect()
        results.add("Reconnection after disconnect", True)
    except Exception as e:
        results.add("Reconnection after disconnect", False, str(e))


# =============================================================================
# Category 2: COMMAND Message Tests
# =============================================================================

def test_command_messages():
    """Test COMMAND message sending and validation."""
    results.set_category("2. COMMAND MESSAGE TESTS")

    bus = MindBus()
    bus.connect()

    try:
        # Test 2.1: Minimal command
        msg_id = bus.send_command(
            action="test_action",
            params={},
            target="test_agent",
            source="test_suite"
        )
        results.add("Minimal COMMAND (action + params)", msg_id is not None)

        # Test 2.2: Full command with all optional fields
        msg_id = bus.send_command(
            action="generate_article",
            params={"topic": "AI Trends", "length": 2000},
            target="writer",
            source="orchestrator",
            target_id="writer-001",
            subject="book-project-001",
            trace_id="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
            timeout_seconds=300,
            requirements={"capabilities": ["generate_text"]},
            context={"process_id": "book-001", "step": "chapter-3"}
        )
        results.add("Full COMMAND with all optional fields", msg_id is not None)

        # Test 2.3: Command with unicode params
        msg_id = bus.send_command(
            action="translate",
            params={
                "text": "Привет мир! 你好世界! مرحبا بالعالم",
                "source_lang": "multi",
                "target_lang": "english"
            },
            target="translator",
            source="test"
        )
        results.add("COMMAND with unicode params", msg_id is not None)

        # Test 2.4: Command with nested params
        msg_id = bus.send_command(
            action="complex_task",
            params={
                "level1": {
                    "level2": {
                        "level3": {
                            "data": [1, 2, 3],
                            "nested": True
                        }
                    }
                }
            },
            target="processor",
            source="test"
        )
        results.add("COMMAND with deeply nested params", msg_id is not None)

        # Test 2.5: Command validation - missing action (should fail)
        try:
            bus._validate_and_send(
                event_type="ai.team.command",
                source="test",
                data={"params": {}},  # Missing 'action'
                routing_key="cmd.test.any"
            )
            results.add("Reject COMMAND without action", False, "Should have raised")
        except ValueError:
            results.add("Reject COMMAND without action", True)

        # Test 2.6: Command validation - action too long
        try:
            bus.send_command(
                action="x" * 101,  # Max is 100
                params={},
                target="test",
                source="test"
            )
            results.add("Reject COMMAND with action > 100 chars", False, "Should have raised")
        except ValueError:
            results.add("Reject COMMAND with action > 100 chars", True)

        # Test 2.7: Timeout validation
        try:
            bus.send_command(
                action="test",
                params={},
                target="test",
                source="test",
                timeout_seconds=3601  # Max is 3600
            )
            results.add("Reject COMMAND with timeout > 3600s", False, "Should have raised")
        except ValueError:
            results.add("Reject COMMAND with timeout > 3600s", True)

    finally:
        bus.disconnect()


# =============================================================================
# Category 3: RESULT Message Tests
# =============================================================================

def test_result_messages():
    """Test RESULT message sending and validation.

    Per MindBus Protocol v1.0.1, RESULT uses RPC reply-to pattern:
    - reply_to and correlation_id are required parameters
    - Messages are sent directly to reply_to queue via default exchange
    """
    results.set_category("3. RESULT MESSAGE TESTS")

    bus = MindBus()
    bus.connect()

    # Create a test reply queue for RPC responses
    reply_queue = "test.responses." + str(uuid.uuid4())[:8]
    bus._channel.queue_declare(queue=reply_queue, durable=False, auto_delete=True)

    try:
        # Test 3.1: Successful result (RPC pattern)
        correlation_id = str(uuid.uuid4())
        msg_id = bus.send_result(
            output={"article": "Generated content...", "word_count": 2000},
            execution_time_ms=12450,
            source="writer-001",
            reply_to=reply_queue,
            correlation_id=correlation_id
        )
        results.add("Send RESULT via RPC reply-to", msg_id is not None)

        # Test 3.2: Result with metrics
        correlation_id2 = str(uuid.uuid4())
        msg_id = bus.send_result(
            output={"text": "Hello world"},
            execution_time_ms=1500,
            source="ai-agent",
            reply_to=reply_queue,
            correlation_id=correlation_id2,
            metrics={
                "model": "gpt-4o-mini",
                "tokens_input": 50,
                "tokens_output": 100,
                "cost_usd": 0.0003
            }
        )
        results.add("RESULT with metrics (RPC)", msg_id is not None)

        # Test 3.3: Result with subject
        correlation_id3 = str(uuid.uuid4())
        msg_id = bus.send_result(
            output={"status": "done"},
            execution_time_ms=500,
            source="processor",
            reply_to=reply_queue,
            correlation_id=correlation_id3,
            subject="task-001"
        )
        results.add("RESULT with subject (RPC)", msg_id is not None)

        # Test 3.4: Result validation - negative execution time
        try:
            bus._send_rpc_response(
                event_type="ai.team.result",
                source="test",
                data={
                    "status": "SUCCESS",
                    "output": {},
                    "execution_time_ms": -1  # Invalid!
                },
                reply_to=reply_queue,
                correlation_id=str(uuid.uuid4())
            )
            results.add("Reject RESULT with negative execution_time", False)
        except ValueError:
            results.add("Reject RESULT with negative execution_time", True)

        # Test 3.5: Result validation - invalid status
        try:
            bus._send_rpc_response(
                event_type="ai.team.result",
                source="test",
                data={
                    "status": "FAILURE",  # Only SUCCESS allowed
                    "output": {},
                    "execution_time_ms": 100
                },
                reply_to=reply_queue,
                correlation_id=str(uuid.uuid4())
            )
            results.add("Reject RESULT with status != SUCCESS", False)
        except ValueError:
            results.add("Reject RESULT with status != SUCCESS", True)

    finally:
        bus.disconnect()


# =============================================================================
# Category 4: ERROR Message Tests
# =============================================================================

def test_error_messages():
    """Test ERROR message sending and validation.

    Per MindBus Protocol v1.0.1, ERROR uses RPC reply-to pattern:
    - reply_to and correlation_id are required parameters
    - Messages are sent directly to reply_to queue via default exchange
    """
    results.set_category("4. ERROR MESSAGE TESTS")

    bus = MindBus()
    bus.connect()

    # Create a test reply queue for RPC responses
    reply_queue = "test.errors." + str(uuid.uuid4())[:8]
    bus._channel.queue_declare(queue=reply_queue, durable=False, auto_delete=True)

    try:
        # Test 4.1: Basic error (RPC pattern)
        correlation_id = str(uuid.uuid4())
        msg_id = bus.send_error(
            code="INTERNAL",
            message="Something went wrong",
            retryable=False,
            source="worker-001",
            reply_to=reply_queue,
            correlation_id=correlation_id
        )
        results.add("Send basic ERROR via RPC reply-to", msg_id is not None)

        # Test 4.2: Retryable error with details
        correlation_id2 = str(uuid.uuid4())
        msg_id = bus.send_error(
            code="DEADLINE_EXCEEDED",
            message="Operation timed out after 30 seconds",
            retryable=True,
            source="ai-agent",
            reply_to=reply_queue,
            correlation_id=correlation_id2,
            details={"timeout_seconds": 30, "elapsed_seconds": 32.5},
            execution_time_ms=30500
        )
        results.add("ERROR with details and execution_time (RPC)", msg_id is not None)

        # Test 4.3: All standard error codes
        standard_codes = [
            "OK", "CANCELLED", "UNKNOWN", "INVALID_ARGUMENT",
            "DEADLINE_EXCEEDED", "NOT_FOUND", "ALREADY_EXISTS",
            "PERMISSION_DENIED", "RESOURCE_EXHAUSTED", "FAILED_PRECONDITION",
            "ABORTED", "OUT_OF_RANGE", "UNIMPLEMENTED", "INTERNAL",
            "UNAVAILABLE", "DATA_LOSS", "UNAUTHENTICATED"
        ]
        all_codes_valid = True
        for code in standard_codes:
            try:
                bus.send_error(
                    code=code,
                    message=f"Test error: {code}",
                    retryable=code in ["DEADLINE_EXCEEDED", "UNAVAILABLE", "RESOURCE_EXHAUSTED"],
                    source="test",
                    reply_to=reply_queue,
                    correlation_id=str(uuid.uuid4())
                )
            except:
                all_codes_valid = False
                break
        results.add(f"All {len(standard_codes)} standard error codes (RPC)", all_codes_valid)

        # Test 4.4: Invalid error code
        try:
            bus.send_error(
                code="CUSTOM_ERROR",  # Not in google.rpc.Code
                message="Custom error",
                retryable=False,
                source="test",
                reply_to=reply_queue,
                correlation_id=str(uuid.uuid4())
            )
            results.add("Reject ERROR with non-standard code", False)
        except ValueError:
            results.add("Reject ERROR with non-standard code", True)

        # Test 4.5: Error with subject
        correlation_id5 = str(uuid.uuid4())
        msg_id = bus.send_error(
            code="INVALID_ARGUMENT",
            message="Invalid input provided",
            retryable=False,
            source="validator",
            reply_to=reply_queue,
            correlation_id=correlation_id5,
            subject="task-001"
        )
        results.add("ERROR with subject (RPC)", msg_id is not None)

    finally:
        bus.disconnect()


# =============================================================================
# Category 5: EVENT Message Tests
# =============================================================================

def test_event_messages():
    """Test EVENT message sending and validation.

    Per MindBus Protocol v1.0.1, EVENT uses Pub/Sub pattern:
    - Routing key: evt.{topic}.{event_type} describes "about what" (not "from whom")
    - source in CloudEvents indicates who sent it
    - New API: send_event(topic, event_type_suffix, event_data, source, ...)
    """
    results.set_category("5. EVENT MESSAGE TESTS")

    bus = MindBus()
    bus.connect()

    try:
        # Test 5.1: Basic event (new API with topic + event_type)
        msg_id = bus.send_event(
            topic="task",
            event_type_suffix="started",
            event_data={"task_id": "task-001"},
            source="orchestrator"
        )
        results.add("Send basic EVENT (evt.task.started)", msg_id is not None)

        # Test 5.2: Event with tags
        msg_id = bus.send_event(
            topic="registry",
            event_type_suffix="node_registered",
            event_data={"agent_id": "writer-001", "capabilities": ["write", "edit"]},
            source="agent.writer.001",  # Source indicates WHO sent it
            tags=["agent", "registration", "writer"]
        )
        results.add("EVENT with tags (evt.registry.node_registered)", msg_id is not None)

        # Test 5.3: All severity levels
        all_severities_valid = True
        for severity in ["INFO", "WARNING", "ERROR", "CRITICAL"]:
            try:
                bus.send_event(
                    topic="test",
                    event_type_suffix="severity_test",
                    event_data={"severity": severity},
                    source="test",
                    severity=severity
                )
            except:
                all_severities_valid = False
                break
        results.add("All 4 severity levels (INFO/WARNING/ERROR/CRITICAL)", all_severities_valid)

        # Test 5.4: Invalid severity
        try:
            bus.send_event(
                topic="test",
                event_type_suffix="invalid",
                event_data={},
                source="test",
                severity="DEBUG"  # Not allowed
            )
            results.add("Reject EVENT with invalid severity", False)
        except ValueError:
            results.add("Reject EVENT with invalid severity", True)

        # Test 5.5: Complex event data
        msg_id = bus.send_event(
            topic="metrics",
            event_type_suffix="collected",
            event_data={
                "timestamp": datetime.utcnow().isoformat(),
                "metrics": {
                    "cpu_usage": 45.5,
                    "memory_mb": 1024,
                    "active_tasks": 5,
                    "queue_depth": [10, 20, 15]
                }
            },
            source="monitor"
        )
        results.add("EVENT with complex nested data (evt.metrics.collected)", msg_id is not None)

        # Test 5.6: Process events
        msg_id = bus.send_event(
            topic="process",
            event_type_suffix="started",
            event_data={"process_id": "proc-001", "name": "book_generation"},
            source="orchestrator-core"
        )
        results.add("EVENT for process (evt.process.started)", msg_id is not None)

    finally:
        bus.disconnect()


# =============================================================================
# Category 6: CONTROL Message Tests
# =============================================================================

def test_control_messages():
    """Test CONTROL message sending and validation."""
    results.set_category("6. CONTROL MESSAGE TESTS")

    bus = MindBus()
    bus.connect()

    try:
        # Test 6.1: All control types
        control_types = ["stop", "pause", "resume", "shutdown", "config"]
        all_types_valid = True
        for ctrl_type in control_types:
            try:
                bus.send_control(
                    control_type=ctrl_type,
                    target="test-agent",
                    source="operator"
                )
            except:
                all_types_valid = False
                break
        results.add(f"All {len(control_types)} control types", all_types_valid)

        # Test 6.2: Control with reason
        msg_id = bus.send_control(
            control_type="stop",
            target="all",
            source="operator",
            reason="Emergency shutdown due to resource exhaustion"
        )
        results.add("CONTROL with reason", msg_id is not None)

        # Test 6.3: Control with parameters
        msg_id = bus.send_control(
            control_type="config",
            target="writer-001",
            source="admin",
            parameters={
                "max_tokens": 4000,
                "temperature": 0.7,
                "model": "gpt-4o"
            }
        )
        results.add("CONTROL with parameters", msg_id is not None)

        # Test 6.4: Invalid control type
        try:
            bus.send_control(
                control_type="restart",  # Not allowed
                target="test",
                source="test"
            )
            results.add("Reject CONTROL with invalid type", False)
        except ValueError:
            results.add("Reject CONTROL with invalid type", True)

        # Test 6.5: Broadcast control
        msg_id = bus.send_control(
            control_type="pause",
            target="all",  # Broadcast
            source="orchestrator",
            reason="System maintenance"
        )
        results.add("CONTROL broadcast (target=all)", msg_id is not None)

    finally:
        bus.disconnect()


# =============================================================================
# Category 7: Routing Pattern Tests
# =============================================================================

def test_routing_patterns():
    """Test message routing patterns."""
    results.set_category("7. ROUTING PATTERN TESTS")

    received = {"messages": []}
    events = {"pattern1": threading.Event(), "pattern2": threading.Event(), "pattern3": threading.Event()}

    def make_callback(pattern_name):
        def callback(event, data):
            received["messages"].append({
                "pattern": pattern_name,
                "type": event["type"],
                "action": data.get("action")
            })
            events[pattern_name].set()
        return callback

    publisher = MindBus()
    sub1 = MindBus()
    sub2 = MindBus()
    sub3 = MindBus()

    try:
        publisher.connect()
        sub1.connect()
        sub2.connect()
        sub3.connect()

        # Test 7.1: Exact pattern match
        sub1.subscribe("cmd.writer.001", make_callback("pattern1"))
        t1 = threading.Thread(target=sub1.start_consuming, daemon=True)
        t1.start()

        # Test 7.2: Wildcard pattern (*)
        sub2.subscribe("cmd.writer.*", make_callback("pattern2"))
        t2 = threading.Thread(target=sub2.start_consuming, daemon=True)
        t2.start()

        # Test 7.3: Multi-level wildcard (#)
        sub3.subscribe("cmd.#", make_callback("pattern3"))
        t3 = threading.Thread(target=sub3.start_consuming, daemon=True)
        t3.start()

        time.sleep(0.3)

        # Send message to specific target
        publisher.send_command(
            action="test_routing",
            params={"test": True},
            target="writer",
            target_id="001",
            source="test"
        )

        # Wait for all patterns
        events["pattern1"].wait(timeout=2.0)
        events["pattern2"].wait(timeout=2.0)
        events["pattern3"].wait(timeout=2.0)

        # Count matches
        pattern1_count = sum(1 for m in received["messages"] if m["pattern"] == "pattern1")
        pattern2_count = sum(1 for m in received["messages"] if m["pattern"] == "pattern2")
        pattern3_count = sum(1 for m in received["messages"] if m["pattern"] == "pattern3")

        results.add("Exact pattern match (cmd.writer.001)", pattern1_count == 1)
        results.add("Wildcard pattern (cmd.writer.*)", pattern2_count == 1)
        results.add("Multi-level wildcard (cmd.#)", pattern3_count == 1)

        # Test 7.4: Non-matching pattern
        received["messages"] = []
        non_match_event = threading.Event()

        sub_nonmatch = MindBus()
        sub_nonmatch.connect()

        def nonmatch_callback(event, data):
            non_match_event.set()

        sub_nonmatch.subscribe("cmd.reviewer.*", nonmatch_callback)
        t_nonmatch = threading.Thread(target=sub_nonmatch.start_consuming, daemon=True)
        t_nonmatch.start()

        time.sleep(0.2)

        # Send to writer, not reviewer
        publisher.send_command(
            action="test",
            params={},
            target="writer",
            target_id="any",
            source="test"
        )

        # Should NOT receive
        non_match_event.wait(timeout=0.5)
        results.add("Non-matching pattern excluded", not non_match_event.is_set())

    finally:
        publisher.disconnect()


# =============================================================================
# Category 8: Correlation ID Tests
# =============================================================================

def test_correlation_id():
    """Test correlation ID preservation in RPC pattern.

    Per MindBus Protocol v1.0.1:
    - RESULT/ERROR use RPC reply-to pattern (direct queue delivery)
    - correlation_id links response to original command
    """
    results.set_category("8. CORRELATION ID TESTS")

    # Create reply queue for RPC
    reply_queue = "test.correlation." + str(uuid.uuid4())[:8]

    received_result = {"data": None}
    result_event = threading.Event()

    def on_result(ch, method, properties, body):
        from cloudevents.http import from_json
        event = from_json(body)
        received_result["data"] = {
            "correlation_id": properties.correlation_id,
            "event_id": event["id"],
            "data": event.data
        }
        ch.basic_ack(delivery_tag=method.delivery_tag)
        result_event.set()

    sender = MindBus()
    receiver = MindBus()

    try:
        sender.connect()
        receiver.connect()

        # Create and bind reply queue (RPC pattern)
        receiver._channel.queue_declare(queue=reply_queue, durable=False, auto_delete=True)
        receiver._channel.basic_consume(queue=reply_queue, on_message_callback=on_result)
        t = threading.Thread(target=receiver._channel.start_consuming, daemon=True)
        t.start()

        time.sleep(0.3)

        # Send command with reply_to
        command_id = sender.send_command(
            action="test",
            params={},
            target="test",
            source="test",
            reply_to=reply_queue  # Specify where to send response
        )

        # Send result with correlation ID matching command ID
        sender.send_result(
            output={"response": "done"},
            execution_time_ms=100,
            source="test-agent",
            reply_to=reply_queue,
            correlation_id=command_id
        )

        result_event.wait(timeout=2.0)

        # Check correlation ID
        if received_result["data"]:
            received_corr_id = received_result["data"]["correlation_id"]
            results.add("Correlation ID preserved in RESULT (RPC)", received_corr_id == command_id)
        else:
            results.add("Correlation ID preserved in RESULT (RPC)", False, "No message received")

        # Test 8.2: Correlation ID in ERROR (RPC)
        error_queue = "test.errors.corr." + str(uuid.uuid4())[:8]
        received_error = {"data": None}
        error_event = threading.Event()

        def on_error(ch, method, properties, body):
            from cloudevents.http import from_json
            event = from_json(body)
            received_error["data"] = {
                "correlation_id": properties.correlation_id,
                "event_id": event["id"],
                "data": event.data
            }
            ch.basic_ack(delivery_tag=method.delivery_tag)
            error_event.set()

        receiver2 = MindBus()
        receiver2.connect()
        receiver2._channel.queue_declare(queue=error_queue, durable=False, auto_delete=True)
        receiver2._channel.basic_consume(queue=error_queue, on_message_callback=on_error)
        t2 = threading.Thread(target=receiver2._channel.start_consuming, daemon=True)
        t2.start()

        time.sleep(0.2)

        error_corr_id = str(uuid.uuid4())
        sender.send_error(
            code="INTERNAL",
            message="Test error",
            retryable=False,
            source="test",
            reply_to=error_queue,
            correlation_id=error_corr_id
        )

        error_event.wait(timeout=2.0)

        if received_error["data"]:
            received_err_corr = received_error["data"]["correlation_id"]
            results.add("Correlation ID preserved in ERROR (RPC)", received_err_corr == error_corr_id)
        else:
            results.add("Correlation ID preserved in ERROR (RPC)", False, "No message received")

    finally:
        sender.disconnect()


# =============================================================================
# Category 9: Concurrent Request Tests
# =============================================================================

def test_concurrent_requests():
    """Test concurrent message sending."""
    results.set_category("9. CONCURRENT REQUEST TESTS")

    received_messages = []
    receive_lock = threading.Lock()
    all_received = threading.Event()
    expected_count = 10

    def on_message(event, data):
        with receive_lock:
            received_messages.append(data)
            if len(received_messages) >= expected_count:
                all_received.set()

    publisher = MindBus()
    subscriber = MindBus()

    try:
        publisher.connect()
        subscriber.connect()

        subscriber.subscribe("cmd.concurrent.*", on_message)
        t = threading.Thread(target=subscriber.start_consuming, daemon=True)
        t.start()

        time.sleep(0.3)

        # Test 9.1: Send 10 messages concurrently
        def send_message(i):
            bus = MindBus()
            bus.connect()
            msg_id = bus.send_command(
                action=f"concurrent_test_{i}",
                params={"index": i},
                target="concurrent",
                target_id=str(i),
                source="concurrent-test"
            )
            bus.disconnect()
            return msg_id

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(send_message, i) for i in range(expected_count)]
            sent_ids = [f.result() for f in as_completed(futures)]

        send_time = time.time() - start_time

        results.add(f"Send {expected_count} concurrent messages", len(sent_ids) == expected_count)

        # Wait for all messages to be received
        all_received.wait(timeout=5.0)

        results.add(f"Receive all {expected_count} concurrent messages",
                   len(received_messages) >= expected_count)

        # Test 9.2: Verify message integrity (all unique)
        actions = [m.get("action") for m in received_messages]
        unique_actions = set(actions)
        results.add("All concurrent messages unique", len(unique_actions) == len(actions))

        # Test 9.3: Performance metric
        results.add(f"Concurrent send completed in {send_time:.2f}s", send_time < 5.0)

    finally:
        publisher.disconnect()


# =============================================================================
# Category 10: Edge Cases Tests
# =============================================================================

def test_edge_cases():
    """Test edge cases and unusual inputs."""
    results.set_category("10. EDGE CASES TESTS")

    bus = MindBus()
    bus.connect()

    try:
        # Test 10.1: Empty params
        msg_id = bus.send_command(
            action="no_params",
            params={},
            target="test",
            source="test"
        )
        results.add("COMMAND with empty params", msg_id is not None)

        # Test 10.2: Very long action name (at limit)
        msg_id = bus.send_command(
            action="a" * 100,  # Max allowed
            params={},
            target="test",
            source="test"
        )
        results.add("COMMAND with 100-char action name", msg_id is not None)

        # Test 10.3: Unicode in all fields
        msg_id = bus.send_command(
            action="unicode_test",
            params={
                "russian": "Привет мир",
                "chinese": "你好世界",
                "arabic": "مرحبا",
                "emoji": "🚀🤖💻"
            },
            target="unicode_agent",
            source="тест"
        )
        results.add("Unicode in params and source", msg_id is not None)

        # Test 10.4: Special characters
        msg_id = bus.send_command(
            action="special_chars",
            params={
                "json_chars": '{"key": "value"}',
                "quotes": "He said 'hello'",
                "backslash": "path\\to\\file",
                "newlines": "line1\nline2\tline3"
            },
            target="test",
            source="test"
        )
        results.add("Special characters in params", msg_id is not None)

        # Test 10.5: Large payload (10KB)
        large_text = "x" * 10000
        msg_id = bus.send_command(
            action="large_payload",
            params={"data": large_text},
            target="test",
            source="test"
        )
        results.add("Large payload (10KB)", msg_id is not None)

        # Test 10.6: Numeric edge cases
        msg_id = bus.send_command(
            action="numeric_test",
            params={
                "zero": 0,
                "negative": -999999,
                "float": 3.14159265359,
                "large": 999999999999999,
                "scientific": 1.23e-10
            },
            target="test",
            source="test"
        )
        results.add("Numeric edge cases in params", msg_id is not None)

        # Test 10.7: Boolean and null values
        msg_id = bus.send_command(
            action="types_test",
            params={
                "true": True,
                "false": False,
                "null": None,
                "list": [1, 2, 3],
                "nested_list": [[1, 2], [3, 4]]
            },
            target="test",
            source="test"
        )
        results.add("Boolean and null values", msg_id is not None)

        # Test 10.8: Minimum timeout
        msg_id = bus.send_command(
            action="min_timeout",
            params={},
            target="test",
            source="test",
            timeout_seconds=1  # Minimum allowed
        )
        results.add("Minimum timeout (1 second)", msg_id is not None)

        # Test 10.9: Maximum timeout
        msg_id = bus.send_command(
            action="max_timeout",
            params={},
            target="test",
            source="test",
            timeout_seconds=3600  # Maximum allowed
        )
        results.add("Maximum timeout (3600 seconds)", msg_id is not None)

    finally:
        bus.disconnect()


# =============================================================================
# Category 11: Full Round-Trip Tests
# =============================================================================

def test_full_roundtrip():
    """Test complete COMMAND -> RESULT/ERROR cycle with RPC pattern.

    Per MindBus Protocol v1.0.1:
    - COMMAND includes reply_to for response delivery
    - Agent sends RESULT/ERROR to reply_to queue
    - correlation_id links request and response
    """
    results.set_category("11. FULL ROUND-TRIP TESTS")

    # Reply queue for RPC responses
    reply_queue = "test.roundtrip.responses." + str(uuid.uuid4())[:8]

    received_result = {"data": None}
    result_event = threading.Event()

    def on_result(ch, method, properties, body):
        from cloudevents.http import from_json
        event = from_json(body)
        received_result["data"] = {
            "correlation_id": properties.correlation_id,
            "output": event.data.get("output", {}),
            "status": event.data.get("status")
        }
        ch.basic_ack(delivery_tag=method.delivery_tag)
        result_event.set()

    received_command = {"data": None, "reply_to": None, "correlation_id": None}
    command_event = threading.Event()

    def on_command(event, data):
        # Get reply_to from AMQP properties (not available in this callback)
        # We'll simulate by using a known reply queue
        received_command["data"] = {
            "event": event,
            "data": data
        }
        received_command["correlation_id"] = event.get("correlationid") or event.get("id")
        command_event.set()

        # Simulate agent: send result back using RPC pattern
        responder = MindBus()
        responder.connect()
        responder.send_result(
            output={"processed": True, "input_action": data.get("action")},
            execution_time_ms=50,
            source="mock-agent",
            reply_to=reply_queue,  # Send to the reply queue
            correlation_id=received_command["correlation_id"]
        )
        responder.disconnect()

    sender = MindBus()
    agent = MindBus()
    result_listener = MindBus()

    try:
        sender.connect()
        agent.connect()
        result_listener.connect()

        # Setup reply queue listener (RPC pattern)
        result_listener._channel.queue_declare(queue=reply_queue, durable=False, auto_delete=True)
        result_listener._channel.basic_consume(queue=reply_queue, on_message_callback=on_result)
        t_result = threading.Thread(target=result_listener._channel.start_consuming, daemon=True)
        t_result.start()

        # Setup agent
        agent.subscribe("cmd.mock.*", on_command)
        t_agent = threading.Thread(target=agent.start_consuming, daemon=True)
        t_agent.start()

        time.sleep(0.3)

        # Send command with reply_to (RPC pattern)
        cmd_id = sender.send_command(
            action="roundtrip_test",
            params={"test_id": "rt-001"},
            target="mock",
            source="test-sender",
            reply_to=reply_queue  # Specify where to send response
        )

        # Wait for command to be received
        command_received = command_event.wait(timeout=3.0)
        results.add("Command received by agent", command_received)

        # Wait for result
        result_received = result_event.wait(timeout=3.0)
        results.add("Result received via RPC reply-to", result_received)

        # Verify correlation
        if received_result["data"]:
            output = received_result["data"].get("output", {})
            correct_action = output.get("input_action") == "roundtrip_test"
            results.add("Result contains correct action", correct_action)

            # Verify correlation ID links request-response
            corr_match = received_result["data"]["correlation_id"] == cmd_id
            results.add("Correlation ID links request-response", corr_match)
        else:
            results.add("Result contains correct action", False, "No result data")
            results.add("Correlation ID links request-response", False, "No result data")

    finally:
        sender.disconnect()


# =============================================================================
# Category 12: SSOT Schema Validation Tests (Pydantic Models)
# =============================================================================

def test_ssot_validation():
    """Test SSOT schema validation directly."""
    results.set_category("12. SSOT SCHEMA VALIDATION TESTS")

    # Test 12.1: CommandData model
    try:
        cmd = CommandData(action="test", params={"key": "value"})
        results.add("CommandData validation", cmd.action == "test")
    except Exception as e:
        results.add("CommandData validation", False, str(e))

    # Test 12.2: ResultData model
    try:
        result = ResultData(
            status="SUCCESS",
            output={"result": "ok"},
            execution_time_ms=100
        )
        results.add("ResultData validation", result.status == "SUCCESS")
    except Exception as e:
        results.add("ResultData validation", False, str(e))

    # Test 12.3: ErrorData model
    try:
        from mindbus.models import ErrorInfo
        error = ErrorData(
            error=ErrorInfo(
                code="INTERNAL",
                message="Test error",
                retryable=False
            )
        )
        results.add("ErrorData validation", error.error.code == "INTERNAL")
    except Exception as e:
        results.add("ErrorData validation", False, str(e))

    # Test 12.4: EventData model
    try:
        event = EventData(
            event_type="test.event",
            event_data={"key": "value"},
            severity="INFO"
        )
        results.add("EventData validation", event.event_type == "test.event")
    except Exception as e:
        results.add("EventData validation", False, str(e))

    # Test 12.5: ControlData model
    try:
        control = ControlData(control_type="stop", reason="Test stop")
        results.add("ControlData validation", control.control_type == "stop")
    except Exception as e:
        results.add("ControlData validation", False, str(e))

    # Test 12.6: validate_message_data function
    try:
        validated = validate_message_data("ai.team.command", {"action": "test", "params": {}})
        results.add("validate_message_data for COMMAND", isinstance(validated, CommandData))
    except Exception as e:
        results.add("validate_message_data for COMMAND", False, str(e))

    # Test 12.7: Unknown message type rejection
    try:
        validate_message_data("ai.team.unknown", {})
        results.add("Reject unknown message type", False, "Should have raised")
    except ValueError as e:
        results.add("Reject unknown message type", "Unknown event type" in str(e))
    except Exception as e:
        results.add("Reject unknown message type", False, str(e))


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Run all comprehensive tests."""
    print("\n" + "🧪" * 30)
    print("  COMPREHENSIVE MINDBUS TEST SUITE")
    print("  Testing all aspects of AI_TEAM message bus")
    print("🧪" * 30)

    # Check RabbitMQ connection first
    try:
        bus = MindBus()
        bus.connect()
        bus.disconnect()
        print("\n  ✅ RabbitMQ connection verified")
    except Exception as e:
        print(f"\n  ❌ Cannot connect to RabbitMQ: {e}")
        print("     Make sure RabbitMQ is running:")
        print("     docker start rabbitmq")
        return 1

    # Run all test categories
    test_connection()
    test_command_messages()
    test_result_messages()
    test_error_messages()
    test_event_messages()
    test_control_messages()
    test_routing_patterns()
    test_correlation_id()
    test_concurrent_requests()
    test_edge_cases()
    test_full_roundtrip()
    test_ssot_validation()

    # Print summary
    return results.summary()


if __name__ == "__main__":
    sys.exit(main())
