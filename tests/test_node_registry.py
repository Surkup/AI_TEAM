#!/usr/bin/env python3
"""
Tests for Node Registry.

Tests cover:
1. Node registration and deregistration
2. Heartbeat and TTL
3. Label selector matching
4. Capability-based discovery
5. Cleanup of dead nodes
"""

import sys
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from registry.models import (
    NodePassport,
    NodeMetadata,
    NodeSpec,
    NodeStatus,
    NodeType,
    NodePhase,
    ConditionStatus,
    HealthState,
    Capability,
    Condition,
    Lease,
    Endpoint,
)
from registry.node_registry import NodeRegistry


# =============================================================================
# Helper Functions
# =============================================================================

def create_test_passport(
    name: str,
    node_type: NodeType = NodeType.AGENT,
    capabilities: list = None,
    labels: dict = None,
) -> NodePassport:
    """Create a test NodePassport."""
    if capabilities is None:
        capabilities = [Capability(name="test_capability", version="1.0")]
    if labels is None:
        labels = {}

    # Add capability labels
    for cap in capabilities:
        labels[f"capability.{cap.name}"] = "true"

    return NodePassport(
        metadata=NodeMetadata(
            name=name,
            node_type=node_type,
            labels=labels,
        ),
        spec=NodeSpec(
            node_type=node_type,
            capabilities=capabilities,
            endpoint=Endpoint(protocol="amqp", queue=f"{name}.tasks"),
        ),
        status=NodeStatus(
            phase=NodePhase.RUNNING,
            conditions=[
                Condition(
                    type="Ready",
                    status=ConditionStatus.TRUE,
                    reason="AgentHealthy",
                    message="Agent is ready",
                )
            ],
            lease=Lease(holder_identity=name),
        ),
    )


# =============================================================================
# Test Results Tracking
# =============================================================================

class TestResults:
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
            return 1


results = TestResults()


# =============================================================================
# 1. Registration Tests
# =============================================================================

def test_registration():
    results.set_category("1. REGISTRATION TESTS")

    registry = NodeRegistry()

    # Test 1.1: Register node
    try:
        passport = create_test_passport("agent-001")
        node_id = registry.register_node(passport)
        results.add("Register node", node_id is not None and len(node_id) > 0)
    except Exception as e:
        results.add("Register node", False, str(e))

    # Test 1.2: Get registered node
    try:
        retrieved = registry.get_node(node_id)
        results.add("Get node by ID", retrieved is not None and retrieved.metadata.name == "agent-001")
    except Exception as e:
        results.add("Get node by ID", False, str(e))

    # Test 1.3: Get node by name
    try:
        retrieved = registry.get_node_by_name("agent-001")
        results.add("Get node by name", retrieved is not None)
    except Exception as e:
        results.add("Get node by name", False, str(e))

    # Test 1.4: Duplicate UID rejection
    try:
        registry.register_node(passport)  # Same passport (same UID)
        results.add("Reject duplicate UID", False, "Should have raised")
    except ValueError as e:
        results.add("Reject duplicate UID", "already registered" in str(e))

    # Test 1.5: Duplicate name rejection
    try:
        passport2 = create_test_passport("agent-001")  # New UID, same name
        registry.register_node(passport2)
        results.add("Reject duplicate name", False, "Should have raised")
    except ValueError as e:
        results.add("Reject duplicate name", "already registered" in str(e))

    # Test 1.6: Deregister node
    try:
        success = registry.deregister_node(node_id)
        results.add("Deregister node", success)
    except Exception as e:
        results.add("Deregister node", False, str(e))

    # Test 1.7: Deregister non-existent node
    try:
        success = registry.deregister_node("non-existent-id")
        results.add("Deregister non-existent returns False", not success)
    except Exception as e:
        results.add("Deregister non-existent returns False", False, str(e))


# =============================================================================
# 2. Heartbeat Tests
# =============================================================================

def test_heartbeat():
    results.set_category("2. HEARTBEAT TESTS")

    # Use short TTL for testing
    registry = NodeRegistry()
    registry.config["ttl_seconds"] = 2
    registry.config["cleanup_interval_seconds"] = 1

    passport = create_test_passport("heartbeat-agent")
    node_id = registry.register_node(passport)

    # Test 2.1: Initial heartbeat
    try:
        entry = registry._nodes[node_id]
        results.add("Initial last_seen set", entry.last_seen is not None)
    except Exception as e:
        results.add("Initial last_seen set", False, str(e))

    # Test 2.2: Update heartbeat
    try:
        time.sleep(0.1)
        old_last_seen = registry._nodes[node_id].last_seen
        registry.update_heartbeat(node_id)
        new_last_seen = registry._nodes[node_id].last_seen
        results.add("Heartbeat updates last_seen", new_last_seen > old_last_seen)
    except Exception as e:
        results.add("Heartbeat updates last_seen", False, str(e))

    # Test 2.3: Heartbeat for unknown node
    try:
        success = registry.update_heartbeat("unknown-node-id")
        results.add("Heartbeat for unknown returns False", not success)
    except Exception as e:
        results.add("Heartbeat for unknown returns False", False, str(e))

    # Test 2.4: Node becomes NOT_READY after half TTL
    try:
        time.sleep(1.1)  # > TTL/2 (1s)
        registry.remove_dead_nodes()
        entry = registry._nodes.get(node_id)
        results.add("Node becomes NOT_READY after TTL/2",
                   entry and entry.health_state == HealthState.NOT_READY)
    except Exception as e:
        results.add("Node becomes NOT_READY after TTL/2", False, str(e))

    # Test 2.5: Node removed after full TTL
    try:
        time.sleep(1.1)  # Total > TTL (2s)
        registry.remove_dead_nodes()
        entry = registry._nodes.get(node_id)
        results.add("Node removed after TTL expired", entry is None)
    except Exception as e:
        results.add("Node removed after TTL expired", False, str(e))


# =============================================================================
# 3. Label Selector Tests
# =============================================================================

def test_label_selectors():
    results.set_category("3. LABEL SELECTOR TESTS")

    registry = NodeRegistry()

    # Register nodes with different labels
    agent1 = create_test_passport(
        "writer-agent",
        capabilities=[Capability(name="generate_text", version="1.0")],
        labels={"role": "writer", "zone": "eu-west-1"}
    )
    agent2 = create_test_passport(
        "coder-agent",
        capabilities=[Capability(name="generate_code", version="1.0")],
        labels={"role": "developer", "zone": "eu-west-1"}
    )
    agent3 = create_test_passport(
        "reviewer-agent",
        capabilities=[Capability(name="review_text", version="1.0")],
        labels={"role": "reviewer", "zone": "us-east-1"}
    )

    registry.register_node(agent1)
    registry.register_node(agent2)
    registry.register_node(agent3)

    # Test 3.1: Find by single label
    try:
        found = registry.find_nodes(selector={"role": "writer"})
        results.add("Find by single label", len(found) == 1 and found[0].metadata.name == "writer-agent")
    except Exception as e:
        results.add("Find by single label", False, str(e))

    # Test 3.2: Find by multiple labels (AND)
    try:
        found = registry.find_nodes(selector={"role": "developer", "zone": "eu-west-1"})
        results.add("Find by multiple labels (AND)", len(found) == 1 and found[0].metadata.name == "coder-agent")
    except Exception as e:
        results.add("Find by multiple labels (AND)", False, str(e))

    # Test 3.3: Find by zone
    try:
        found = registry.find_nodes(selector={"zone": "eu-west-1"})
        results.add("Find by zone label", len(found) == 2)
    except Exception as e:
        results.add("Find by zone label", False, str(e))

    # Test 3.4: No matches
    try:
        found = registry.find_nodes(selector={"role": "admin"})
        results.add("No matches returns empty list", len(found) == 0)
    except Exception as e:
        results.add("No matches returns empty list", False, str(e))

    # Test 3.5: Find by capability label
    try:
        found = registry.find_nodes(selector={"capability.generate_text": "true"})
        results.add("Find by capability label", len(found) == 1 and found[0].metadata.name == "writer-agent")
    except Exception as e:
        results.add("Find by capability label", False, str(e))


# =============================================================================
# 4. Capability Discovery Tests
# =============================================================================

def test_capability_discovery():
    results.set_category("4. CAPABILITY DISCOVERY TESTS")

    registry = NodeRegistry()

    # Register nodes with capabilities
    agent1 = create_test_passport(
        "text-agent",
        capabilities=[
            Capability(name="generate_text", version="1.0"),
            Capability(name="translate_text", version="1.0"),
        ]
    )
    agent2 = create_test_passport(
        "code-agent",
        capabilities=[
            Capability(name="generate_code", version="1.0"),
            Capability(name="review_code", version="1.0"),
        ]
    )

    registry.register_node(agent1)
    registry.register_node(agent2)

    # Test 4.1: Find by capability name
    try:
        found = registry.find_nodes_by_capability("generate_text")
        results.add("Find by capability", len(found) == 1 and found[0].metadata.name == "text-agent")
    except Exception as e:
        results.add("Find by capability", False, str(e))

    # Test 4.2: Find multiple capabilities
    try:
        found = registry.find_nodes(capability="generate_code")
        results.add("Find code capability", len(found) == 1 and found[0].metadata.name == "code-agent")
    except Exception as e:
        results.add("Find code capability", False, str(e))

    # Test 4.3: Capability not found
    try:
        found = registry.find_nodes_by_capability("non_existent_capability")
        results.add("Capability not found returns empty", len(found) == 0)
    except Exception as e:
        results.add("Capability not found returns empty", False, str(e))

    # Test 4.4: has_capability method
    try:
        passport = registry.get_node_by_name("text-agent")
        has_text = passport.has_capability("generate_text")
        has_code = passport.has_capability("generate_code")
        results.add("has_capability method", has_text and not has_code)
    except Exception as e:
        results.add("has_capability method", False, str(e))


# =============================================================================
# 5. Node Type Filter Tests
# =============================================================================

def test_node_type_filter():
    results.set_category("5. NODE TYPE FILTER TESTS")

    registry = NodeRegistry()

    # Register different node types
    agent = create_test_passport("test-agent", node_type=NodeType.AGENT)
    orchestrator = create_test_passport("test-orchestrator", node_type=NodeType.ORCHESTRATOR)
    storage = create_test_passport("test-storage", node_type=NodeType.STORAGE)

    registry.register_node(agent)
    registry.register_node(orchestrator)
    registry.register_node(storage)

    # Test 5.1: Filter by AGENT type
    try:
        found = registry.find_nodes(node_type=NodeType.AGENT)
        results.add("Filter by AGENT type", len(found) == 1 and found[0].metadata.name == "test-agent")
    except Exception as e:
        results.add("Filter by AGENT type", False, str(e))

    # Test 5.2: Filter by ORCHESTRATOR type
    try:
        found = registry.find_nodes(node_type=NodeType.ORCHESTRATOR)
        results.add("Filter by ORCHESTRATOR type", len(found) == 1)
    except Exception as e:
        results.add("Filter by ORCHESTRATOR type", False, str(e))

    # Test 5.3: Get all nodes
    try:
        all_nodes = registry.get_all_nodes()
        results.add("Get all nodes", len(all_nodes) == 3)
    except Exception as e:
        results.add("Get all nodes", False, str(e))


# =============================================================================
# 6. Cleanup Thread Tests
# =============================================================================

def test_cleanup_thread():
    results.set_category("6. CLEANUP THREAD TESTS")

    registry = NodeRegistry()
    registry.config["ttl_seconds"] = 1
    registry.config["cleanup_interval_seconds"] = 0.5

    # Test 6.1: Start cleanup thread
    try:
        registry.start_cleanup_thread()
        results.add("Start cleanup thread", registry._cleanup_thread is not None and registry._cleanup_thread.is_alive())
    except Exception as e:
        results.add("Start cleanup thread", False, str(e))

    # Test 6.2: Automatic cleanup
    try:
        passport = create_test_passport("auto-cleanup-agent")
        node_id = registry.register_node(passport)

        # Wait for TTL + cleanup interval
        time.sleep(1.8)

        # Check node was removed
        node = registry.get_node(node_id)
        results.add("Automatic cleanup removes dead node", node is None)
    except Exception as e:
        results.add("Automatic cleanup removes dead node", False, str(e))

    # Test 6.3: Stop cleanup thread
    try:
        registry.stop_cleanup_thread()
        time.sleep(0.1)
        results.add("Stop cleanup thread", registry._cleanup_thread is None or not registry._cleanup_thread.is_alive())
    except Exception as e:
        results.add("Stop cleanup thread", False, str(e))


# =============================================================================
# 7. Event Callbacks Tests
# =============================================================================

def test_event_callbacks():
    results.set_category("7. EVENT CALLBACKS TESTS")

    registry = NodeRegistry()

    registered_nodes = []
    deregistered_nodes = []

    def on_registered(passport):
        registered_nodes.append(passport.metadata.name)

    def on_deregistered(node_id, reason):
        deregistered_nodes.append((node_id, reason))

    registry.on_node_registered(on_registered)
    registry.on_node_deregistered(on_deregistered)

    # Test 7.1: Registration callback
    try:
        passport = create_test_passport("callback-agent")
        node_id = registry.register_node(passport)
        results.add("Registration callback fired", "callback-agent" in registered_nodes)
    except Exception as e:
        results.add("Registration callback fired", False, str(e))

    # Test 7.2: Deregistration callback
    try:
        registry.deregister_node(node_id, reason="TestReason")
        results.add("Deregistration callback fired", len(deregistered_nodes) > 0 and deregistered_nodes[-1][1] == "TestReason")
    except Exception as e:
        results.add("Deregistration callback fired", False, str(e))


# =============================================================================
# 8. Statistics Tests
# =============================================================================

def test_statistics():
    results.set_category("8. STATISTICS TESTS")

    registry = NodeRegistry()

    agent1 = create_test_passport("stats-agent-1", node_type=NodeType.AGENT)
    agent2 = create_test_passport("stats-agent-2", node_type=NodeType.AGENT)
    orch = create_test_passport("stats-orchestrator", node_type=NodeType.ORCHESTRATOR)

    registry.register_node(agent1)
    registry.register_node(agent2)
    registry.register_node(orch)

    # Test 8.1: Get statistics
    try:
        stats = registry.get_stats()
        results.add("Get statistics", stats["total_nodes"] == 3)
    except Exception as e:
        results.add("Get statistics", False, str(e))

    # Test 8.2: Stats by type
    try:
        stats = registry.get_stats()
        by_type = stats["nodes_by_type"]
        results.add("Stats by type", by_type.get("agent") == 2 and by_type.get("orchestrator") == 1)
    except Exception as e:
        results.add("Stats by type", False, str(e))


# =============================================================================
# 9. Model Validation Tests
# =============================================================================

def test_model_validation():
    results.set_category("9. MODEL VALIDATION TESTS")

    # Test 9.1: Create valid NodePassport
    try:
        passport = create_test_passport("valid-agent")
        results.add("Create valid NodePassport", passport is not None)
    except Exception as e:
        results.add("Create valid NodePassport", False, str(e))

    # Test 9.2: is_ready method
    try:
        passport = create_test_passport("ready-agent")
        results.add("is_ready returns True for running agent", passport.is_ready())
    except Exception as e:
        results.add("is_ready returns True for running agent", False, str(e))

    # Test 9.3: is_ready for pending agent
    try:
        passport = create_test_passport("pending-agent")
        passport.status.phase = NodePhase.PENDING
        results.add("is_ready returns False for pending agent", not passport.is_ready())
    except Exception as e:
        results.add("is_ready returns False for pending agent", False, str(e))

    # Test 9.4: matches_labels method
    try:
        passport = create_test_passport("label-agent", labels={"env": "prod", "team": "ai"})
        matches = passport.matches_labels({"env": "prod"})
        not_matches = passport.matches_labels({"env": "dev"})
        results.add("matches_labels method", matches and not not_matches)
    except Exception as e:
        results.add("matches_labels method", False, str(e))


# =============================================================================
# Main
# =============================================================================

def main():
    print("\n" + "🧪" * 30)
    print("  NODE REGISTRY TEST SUITE")
    print("🧪" * 30)

    test_registration()
    test_heartbeat()
    test_label_selectors()
    test_capability_discovery()
    test_node_type_filter()
    test_cleanup_thread()
    test_event_callbacks()
    test_statistics()
    test_model_validation()

    return results.summary()


if __name__ == "__main__":
    sys.exit(main())
