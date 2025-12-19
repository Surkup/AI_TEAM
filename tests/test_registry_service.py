"""
Tests for Registry Service.

Tests that RegistryService correctly:
- Handles node.registered events
- Handles node.heartbeat events
- Handles node.deregistered events
- Manages underlying NodeRegistry

See: docs/SSOT/NODE_REGISTRY_SPEC_v1.0.md
"""

import pytest
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.registry.registry_service import RegistryService
from src.registry.models import (
    NodePassport,
    NodeMetadata,
    NodeSpec,
    NodeStatus,
    NodeType,
    NodePhase,
    ConditionStatus,
    Condition,
    Lease,
    Endpoint,
    Capability,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_mindbus():
    """Create a mock MindBus."""
    with patch('src.registry.registry_service.MindBus') as mock:
        yield mock.return_value


@pytest.fixture
def service(mock_mindbus):
    """Create a RegistryService with mocked MindBus."""
    return RegistryService()


@pytest.fixture
def sample_passport():
    """Create a sample NodePassport for testing."""
    return NodePassport(
        metadata=NodeMetadata(
            uid="test-uid-12345",
            name="test.agent",
            node_type=NodeType.AGENT,
            labels={"env": "test"},
            version="1.0.0",
        ),
        spec=NodeSpec(
            node_type=NodeType.AGENT,
            capabilities=[Capability(name="test.cap", version="1.0")],
            endpoint=Endpoint(protocol="amqp", queue="cmd.test_agent.*"),
        ),
        status=NodeStatus(
            phase=NodePhase.RUNNING,
            conditions=[
                Condition(
                    type="Ready",
                    status=ConditionStatus.TRUE,
                    reason="Started",
                    message="Test agent ready",
                )
            ],
            lease=Lease(
                holder_identity="test.agent",
                lease_duration_seconds=30,
            ),
        ),
    )


# =============================================================================
# Test: Event Handlers
# =============================================================================

class TestNodeRegisteredHandler:
    """Tests for _on_node_registered handler."""

    def test_registers_node_from_event(self, service, sample_passport):
        """Test that node.registered event adds node to registry."""
        event = {"id": "evt-1", "type": "node.registered"}
        data = {
            "node_id": sample_passport.metadata.uid,
            "name": sample_passport.metadata.name,
            "passport": sample_passport.model_dump(mode="json"),
        }

        service._on_node_registered(event, data)

        # Check node is in registry
        node = service.registry.get_node(sample_passport.metadata.uid)
        assert node is not None
        assert node.metadata.name == "test.agent"
        assert service._registrations == 1
        assert service._events_processed == 1

    def test_handles_missing_passport(self, service):
        """Test that missing passport is handled gracefully."""
        event = {"id": "evt-1", "type": "node.registered"}
        data = {"node_id": "some-id", "name": "some-name"}  # No passport

        service._on_node_registered(event, data)

        # No node should be registered
        assert len(service.registry.get_all_nodes()) == 0
        assert service._registrations == 0
        assert service._events_processed == 1

    def test_handles_duplicate_registration(self, service, sample_passport):
        """Test that duplicate registration is handled."""
        event = {"id": "evt-1", "type": "node.registered"}
        data = {
            "node_id": sample_passport.metadata.uid,
            "name": sample_passport.metadata.name,
            "passport": sample_passport.model_dump(mode="json"),
        }

        # Register once
        service._on_node_registered(event, data)
        assert service._registrations == 1

        # Try to register again - should handle gracefully
        service._on_node_registered(event, data)
        assert service._registrations == 1  # Still 1
        assert service._events_processed == 2

    def test_handles_invalid_passport_data(self, service):
        """Test that invalid passport data is handled gracefully."""
        event = {"id": "evt-1", "type": "node.registered"}
        data = {
            "passport": {"invalid": "data"},  # Invalid passport structure
        }

        service._on_node_registered(event, data)

        # No node should be registered
        assert len(service.registry.get_all_nodes()) == 0
        assert service._events_processed == 1


class TestNodeHeartbeatHandler:
    """Tests for _on_node_heartbeat handler."""

    def test_updates_heartbeat(self, service, sample_passport):
        """Test that node.heartbeat event updates last_seen."""
        # First register the node
        service.registry.register_node(sample_passport)

        event = {"id": "evt-1", "type": "node.heartbeat"}
        data = {
            "node_id": sample_passport.metadata.uid,
            "name": sample_passport.metadata.name,
            "renew_time": datetime.utcnow().isoformat(),
        }

        # Small delay to ensure time difference
        time.sleep(0.01)

        service._on_node_heartbeat(event, data)

        assert service._heartbeats == 1
        assert service._events_processed == 1

    def test_handles_missing_node_id(self, service):
        """Test that missing node_id is handled gracefully."""
        event = {"id": "evt-1", "type": "node.heartbeat"}
        data = {"name": "some-name"}  # No node_id

        service._on_node_heartbeat(event, data)

        assert service._heartbeats == 0
        assert service._events_processed == 1

    def test_handles_unknown_node(self, service):
        """Test that heartbeat for unknown node is handled."""
        event = {"id": "evt-1", "type": "node.heartbeat"}
        data = {
            "node_id": "unknown-node-id",
            "name": "unknown.agent",
        }

        service._on_node_heartbeat(event, data)

        assert service._heartbeats == 0
        assert service._events_processed == 1


class TestNodeDeregisteredHandler:
    """Tests for _on_node_deregistered handler."""

    def test_deregisters_node(self, service, sample_passport):
        """Test that node.deregistered event removes node from registry."""
        # First register the node
        service.registry.register_node(sample_passport)
        assert len(service.registry.get_all_nodes()) == 1

        event = {"id": "evt-1", "type": "node.deregistered"}
        data = {
            "node_id": sample_passport.metadata.uid,
            "name": sample_passport.metadata.name,
            "reason": "GracefulShutdown",
        }

        service._on_node_deregistered(event, data)

        # Node should be removed
        assert len(service.registry.get_all_nodes()) == 0
        assert service._deregistrations == 1
        assert service._events_processed == 1

    def test_handles_missing_node_id(self, service):
        """Test that missing node_id is handled gracefully."""
        event = {"id": "evt-1", "type": "node.deregistered"}
        data = {"name": "some-name", "reason": "Test"}  # No node_id

        service._on_node_deregistered(event, data)

        assert service._deregistrations == 0
        assert service._events_processed == 1

    def test_handles_unknown_node(self, service):
        """Test that deregister for unknown node is handled."""
        event = {"id": "evt-1", "type": "node.deregistered"}
        data = {
            "node_id": "unknown-node-id",
            "name": "unknown.agent",
            "reason": "Unknown",
        }

        service._on_node_deregistered(event, data)

        assert service._deregistrations == 0
        assert service._events_processed == 1


# =============================================================================
# Test: Service API
# =============================================================================

class TestServiceAPI:
    """Tests for RegistryService public API."""

    def test_get_registry(self, service):
        """Test that get_registry returns the registry instance."""
        registry = service.get_registry()
        assert registry is not None
        assert registry is service.registry

    def test_get_stats_initial(self, service):
        """Test initial statistics."""
        stats = service.get_stats()

        assert stats["service"]["running"] is False
        assert stats["service"]["events_processed"] == 0
        assert stats["service"]["registrations"] == 0
        assert stats["service"]["heartbeats"] == 0
        assert stats["service"]["deregistrations"] == 0

        assert stats["registry"]["total_nodes"] == 0

    def test_get_stats_after_events(self, service, sample_passport):
        """Test statistics after processing events."""
        # Process some events
        event = {"id": "evt-1", "type": "node.registered"}
        data = {
            "node_id": sample_passport.metadata.uid,
            "passport": sample_passport.model_dump(mode="json"),
        }
        service._on_node_registered(event, data)

        # Heartbeat
        hb_event = {"id": "evt-2", "type": "node.heartbeat"}
        hb_data = {"node_id": sample_passport.metadata.uid}
        service._on_node_heartbeat(hb_event, hb_data)

        stats = service.get_stats()

        assert stats["service"]["events_processed"] == 2
        assert stats["service"]["registrations"] == 1
        assert stats["service"]["heartbeats"] == 1
        assert stats["registry"]["total_nodes"] == 1


# =============================================================================
# Test: Full Lifecycle
# =============================================================================

class TestLifecycle:
    """Tests for full registration lifecycle."""

    def test_register_heartbeat_deregister(self, service, sample_passport):
        """Test complete node lifecycle: register → heartbeat → deregister."""
        # 1. Register
        reg_event = {"id": "evt-1", "type": "node.registered"}
        reg_data = {
            "node_id": sample_passport.metadata.uid,
            "name": sample_passport.metadata.name,
            "passport": sample_passport.model_dump(mode="json"),
        }
        service._on_node_registered(reg_event, reg_data)

        assert len(service.registry.get_all_nodes()) == 1
        assert service._registrations == 1

        # 2. Heartbeat
        hb_event = {"id": "evt-2", "type": "node.heartbeat"}
        hb_data = {
            "node_id": sample_passport.metadata.uid,
            "name": sample_passport.metadata.name,
        }
        service._on_node_heartbeat(hb_event, hb_data)

        assert service._heartbeats == 1

        # 3. Deregister
        dereg_event = {"id": "evt-3", "type": "node.deregistered"}
        dereg_data = {
            "node_id": sample_passport.metadata.uid,
            "name": sample_passport.metadata.name,
            "reason": "GracefulShutdown",
        }
        service._on_node_deregistered(dereg_event, dereg_data)

        assert len(service.registry.get_all_nodes()) == 0
        assert service._deregistrations == 1
        assert service._events_processed == 3

    def test_multiple_nodes(self, service):
        """Test handling multiple nodes."""
        # Create multiple passports
        passports = []
        for i in range(3):
            passport = NodePassport(
                metadata=NodeMetadata(
                    uid=f"node-{i}",
                    name=f"agent.{i}",
                    node_type=NodeType.AGENT,
                ),
                spec=NodeSpec(
                    node_type=NodeType.AGENT,
                    capabilities=[],
                    endpoint=Endpoint(protocol="amqp", queue=f"cmd.agent_{i}.*"),
                ),
                status=NodeStatus(
                    phase=NodePhase.RUNNING,
                    conditions=[],
                    lease=Lease(holder_identity=f"agent.{i}", lease_duration_seconds=30),
                ),
            )
            passports.append(passport)

        # Register all
        for p in passports:
            event = {"id": f"evt-reg-{p.metadata.uid}"}
            data = {
                "node_id": p.metadata.uid,
                "passport": p.model_dump(mode="json"),
            }
            service._on_node_registered(event, data)

        assert len(service.registry.get_all_nodes()) == 3
        assert service._registrations == 3

        # Heartbeat for first two
        for i in range(2):
            event = {"id": f"evt-hb-{i}"}
            data = {"node_id": f"node-{i}"}
            service._on_node_heartbeat(event, data)

        assert service._heartbeats == 2

        # Deregister last one
        event = {"id": "evt-dereg"}
        data = {"node_id": "node-2", "reason": "Test"}
        service._on_node_deregistered(event, data)

        assert len(service.registry.get_all_nodes()) == 2
        assert service._deregistrations == 1


# =============================================================================
# Test: Import
# =============================================================================

class TestImport:
    """Test module imports."""

    def test_import_from_package(self):
        """Test that RegistryService can be imported from package."""
        from src.registry import RegistryService
        assert RegistryService is not None

    def test_import_direct(self):
        """Test direct import."""
        from src.registry.registry_service import RegistryService
        assert RegistryService is not None
