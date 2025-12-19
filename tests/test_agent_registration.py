"""
Tests for Agent Registration functionality.

Tests that BaseAgent correctly:
- Builds NODE_PASSPORT from config
- Sends node.registered EVENT on start
- Sends node.heartbeat EVENTs periodically
- Sends node.deregistered EVENT on stop

See: docs/SSOT/NODE_PASSPORT_SPEC_v1.0.md
"""

import pytest
import time
import threading
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.base_agent import BaseAgent
from src.registry.models import (
    NodePassport,
    NodeType,
    NodePhase,
    ConditionStatus,
)


# =============================================================================
# Test Agent Implementation
# =============================================================================

class TestAgent(BaseAgent):
    """Minimal test agent for registration tests."""

    def execute(self, action, params, context=None):
        return {"action": action, "status": "ok"}


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def test_config_path(tmp_path):
    """Create a temporary config file for testing."""
    config_content = """
test_agent:
  name: "test.registration.agent"
  type: "test"
  version: "1.0.0"

  capabilities:
    - "test.echo"
    - name: "analyze"
      version: "2.0"
      parameters:
        max_size: 1000

  labels:
    environment: "test"
    team: "qa"

  registry:
    enabled: true
    heartbeat_interval_seconds: 1
"""
    config_file = tmp_path / "test_agent.yaml"
    config_file.write_text(config_content)
    return str(config_file)


@pytest.fixture
def disabled_registry_config(tmp_path):
    """Config with registration disabled."""
    config_content = """
test_agent:
  name: "test.no.registration"
  type: "test"
  capabilities: []

  registry:
    enabled: false
"""
    config_file = tmp_path / "disabled_agent.yaml"
    config_file.write_text(config_content)
    return str(config_file)


# =============================================================================
# Test: Passport Building
# =============================================================================

class TestPassportBuilding:
    """Tests for _build_passport() method."""

    def test_build_passport_creates_valid_passport(self, test_config_path):
        """Test that _build_passport creates a valid NodePassport."""
        with patch.object(BaseAgent, '_load_config') as mock_load:
            mock_load.return_value = {
                "name": "test.agent",
                "type": "test",
                "version": "1.0.0",
                "capabilities": ["cap1", "cap2"],
                "labels": {"env": "test"},
                "registry": {"enabled": True, "heartbeat_interval_seconds": 10},
            }

            # Mock MindBus to avoid connection
            with patch('src.agents.base_agent.MindBus'):
                agent = TestAgent(test_config_path)
                passport = agent._build_passport()

        assert isinstance(passport, NodePassport)
        assert passport.metadata.name == "test.agent"
        assert passport.metadata.node_type == NodeType.AGENT
        assert passport.metadata.version == "1.0.0"

    def test_passport_has_capabilities(self, test_config_path):
        """Test that capabilities are correctly parsed."""
        with patch.object(BaseAgent, '_load_config') as mock_load:
            mock_load.return_value = {
                "name": "test.agent",
                "type": "test",
                "capabilities": [
                    "simple_cap",
                    {"name": "complex_cap", "version": "2.0", "parameters": {"max": 100}}
                ],
                "registry": {"enabled": True},
            }

            with patch('src.agents.base_agent.MindBus'):
                agent = TestAgent(test_config_path)
                passport = agent._build_passport()

        assert len(passport.spec.capabilities) == 2

        # Simple capability
        cap1 = passport.spec.capabilities[0]
        assert cap1.name == "simple_cap"
        assert cap1.version == "1.0"

        # Complex capability
        cap2 = passport.spec.capabilities[1]
        assert cap2.name == "complex_cap"
        assert cap2.version == "2.0"
        assert cap2.parameters.get("max") == 100

    def test_passport_has_labels(self, test_config_path):
        """Test that labels include type and capabilities."""
        with patch.object(BaseAgent, '_load_config') as mock_load:
            mock_load.return_value = {
                "name": "test.agent",
                "type": "worker",
                "capabilities": ["analyze"],
                "labels": {"custom": "value"},
                "registry": {"enabled": True},
            }

            with patch('src.agents.base_agent.MindBus'):
                agent = TestAgent(test_config_path)
                passport = agent._build_passport()

        labels = passport.metadata.labels
        assert labels.get("node.type") == "worker"
        assert labels.get("capability.analyze") == "true"
        assert labels.get("custom") == "value"

    def test_passport_has_ready_status(self, test_config_path):
        """Test that new passport has Running phase and Ready condition."""
        with patch.object(BaseAgent, '_load_config') as mock_load:
            mock_load.return_value = {
                "name": "test.agent",
                "type": "test",
                "capabilities": [],
                "registry": {"enabled": True, "heartbeat_interval_seconds": 10},
            }

            with patch('src.agents.base_agent.MindBus'):
                agent = TestAgent(test_config_path)
                passport = agent._build_passport()

        assert passport.status.phase == NodePhase.RUNNING
        assert len(passport.status.conditions) == 1
        assert passport.status.conditions[0].type == "Ready"
        assert passport.status.conditions[0].status == ConditionStatus.TRUE

    def test_passport_uid_is_persistent(self, test_config_path):
        """Test that UID stays the same across multiple passport builds."""
        with patch.object(BaseAgent, '_load_config') as mock_load:
            mock_load.return_value = {
                "name": "test.agent",
                "type": "test",
                "capabilities": [],
                "registry": {"enabled": True},
            }

            with patch('src.agents.base_agent.MindBus'):
                agent = TestAgent(test_config_path)
                passport1 = agent._build_passport()
                passport2 = agent._build_passport()

        assert passport1.metadata.uid == passport2.metadata.uid

    def test_passport_has_endpoint(self, test_config_path):
        """Test that passport has correct endpoint configuration."""
        with patch.object(BaseAgent, '_load_config') as mock_load:
            mock_load.return_value = {
                "name": "test.agent",
                "type": "test",
                "capabilities": [],
                "registry": {"enabled": True},
            }

            with patch('src.agents.base_agent.MindBus'):
                agent = TestAgent(test_config_path)
                passport = agent._build_passport()

        assert passport.spec.endpoint.protocol == "amqp"
        assert "test_agent" in passport.spec.endpoint.queue


# =============================================================================
# Test: Registration Events
# =============================================================================

class TestRegistrationEvents:
    """Tests for registration event sending."""

    def test_send_registration_event(self, test_config_path):
        """Test that registration event is sent with correct data."""
        with patch.object(BaseAgent, '_load_config') as mock_load:
            mock_load.return_value = {
                "name": "test.agent",
                "type": "test",
                "capabilities": ["cap1"],
                "registry": {"enabled": True},
            }

            mock_bus = MagicMock()
            with patch('src.agents.base_agent.MindBus', return_value=mock_bus):
                agent = TestAgent(test_config_path)
                agent._send_registration_event()

        # Verify send_event was called
        mock_bus.send_event.assert_called_once()
        call_args = mock_bus.send_event.call_args

        assert call_args.kwargs["event_type_name"] == "node.registered"
        assert call_args.kwargs["source"] == "test.agent"
        assert "registration" in call_args.kwargs["tags"]

        event_data = call_args.kwargs["event_data"]
        assert event_data["name"] == "test.agent"
        assert event_data["node_type"] == "agent"
        assert "cap1" in event_data["capabilities"]
        assert "passport" in event_data

    def test_registration_disabled(self, disabled_registry_config):
        """Test that no event is sent when registration is disabled."""
        with patch.object(BaseAgent, '_load_config') as mock_load:
            mock_load.return_value = {
                "name": "test.agent",
                "type": "test",
                "capabilities": [],
                "registry": {"enabled": False},
            }

            mock_bus = MagicMock()
            with patch('src.agents.base_agent.MindBus', return_value=mock_bus):
                agent = TestAgent(disabled_registry_config)
                agent._send_registration_event()

        mock_bus.send_event.assert_not_called()


# =============================================================================
# Test: Heartbeat Events
# =============================================================================

class TestHeartbeatEvents:
    """Tests for heartbeat event sending."""

    def test_send_heartbeat_event(self, test_config_path):
        """Test that heartbeat event is sent with correct data."""
        with patch.object(BaseAgent, '_load_config') as mock_load:
            mock_load.return_value = {
                "name": "test.agent",
                "type": "test",
                "capabilities": [],
                "registry": {"enabled": True, "heartbeat_interval_seconds": 10},
            }

            mock_bus = MagicMock()
            with patch('src.agents.base_agent.MindBus', return_value=mock_bus):
                agent = TestAgent(test_config_path)
                agent._build_passport()  # Initialize passport
                agent._send_heartbeat_event()

        mock_bus.send_event.assert_called_once()
        call_args = mock_bus.send_event.call_args

        assert call_args.kwargs["event_type_name"] == "node.heartbeat"
        assert call_args.kwargs["source"] == "test.agent"
        assert "heartbeat" in call_args.kwargs["tags"]

        event_data = call_args.kwargs["event_data"]
        assert event_data["name"] == "test.agent"
        assert "renew_time" in event_data

    def test_heartbeat_not_sent_without_passport(self, test_config_path):
        """Test that heartbeat is not sent if passport not built."""
        with patch.object(BaseAgent, '_load_config') as mock_load:
            mock_load.return_value = {
                "name": "test.agent",
                "type": "test",
                "capabilities": [],
                "registry": {"enabled": True},
            }

            mock_bus = MagicMock()
            with patch('src.agents.base_agent.MindBus', return_value=mock_bus):
                agent = TestAgent(test_config_path)
                # Don't build passport
                agent._send_heartbeat_event()

        mock_bus.send_event.assert_not_called()

    def test_heartbeat_disabled(self, disabled_registry_config):
        """Test that heartbeat is not sent when registration disabled."""
        with patch.object(BaseAgent, '_load_config') as mock_load:
            mock_load.return_value = {
                "name": "test.agent",
                "type": "test",
                "capabilities": [],
                "registry": {"enabled": False},
            }

            mock_bus = MagicMock()
            with patch('src.agents.base_agent.MindBus', return_value=mock_bus):
                agent = TestAgent(disabled_registry_config)
                agent._passport = MagicMock()  # Fake passport
                agent._send_heartbeat_event()

        mock_bus.send_event.assert_not_called()


# =============================================================================
# Test: Deregistration Events
# =============================================================================

class TestDeregistrationEvents:
    """Tests for deregistration event sending."""

    def test_send_deregistration_event(self, test_config_path):
        """Test that deregistration event is sent with correct data."""
        with patch.object(BaseAgent, '_load_config') as mock_load:
            mock_load.return_value = {
                "name": "test.agent",
                "type": "test",
                "capabilities": [],
                "registry": {"enabled": True},
            }

            mock_bus = MagicMock()
            with patch('src.agents.base_agent.MindBus', return_value=mock_bus):
                agent = TestAgent(test_config_path)
                agent._node_uid = "test-uid-123"
                agent._tasks_processed = 42
                agent._send_deregistration_event(reason="TestShutdown")

        mock_bus.send_event.assert_called_once()
        call_args = mock_bus.send_event.call_args

        assert call_args.kwargs["event_type_name"] == "node.deregistered"
        assert call_args.kwargs["source"] == "test.agent"
        assert "deregistration" in call_args.kwargs["tags"]

        event_data = call_args.kwargs["event_data"]
        assert event_data["node_id"] == "test-uid-123"
        assert event_data["reason"] == "TestShutdown"
        assert event_data["total_tasks_processed"] == 42

    def test_deregistration_not_sent_without_uid(self, test_config_path):
        """Test that deregistration is not sent if no UID."""
        with patch.object(BaseAgent, '_load_config') as mock_load:
            mock_load.return_value = {
                "name": "test.agent",
                "type": "test",
                "capabilities": [],
                "registry": {"enabled": True},
            }

            mock_bus = MagicMock()
            with patch('src.agents.base_agent.MindBus', return_value=mock_bus):
                agent = TestAgent(test_config_path)
                # Don't set _node_uid
                agent._send_deregistration_event()

        mock_bus.send_event.assert_not_called()


# =============================================================================
# Test: Heartbeat Thread
# =============================================================================

class TestHeartbeatThread:
    """Tests for heartbeat background thread."""

    def test_heartbeat_thread_starts_and_stops(self, test_config_path):
        """Test that heartbeat thread can be started and stopped."""
        with patch.object(BaseAgent, '_load_config') as mock_load:
            mock_load.return_value = {
                "name": "test.agent",
                "type": "test",
                "capabilities": [],
                "registry": {"enabled": True, "heartbeat_interval_seconds": 0.1},
            }

            mock_bus = MagicMock()
            with patch('src.agents.base_agent.MindBus', return_value=mock_bus):
                agent = TestAgent(test_config_path)
                # Manually set heartbeat interval for test (since _load_config is mocked
                # after __init__ reads the interval)
                agent._heartbeat_interval = 0.1
                agent._build_passport()

                # Start heartbeat thread
                agent._start_heartbeat_thread()
                assert agent._heartbeat_thread is not None
                assert agent._heartbeat_thread.is_alive()

                # Wait for at least one heartbeat
                time.sleep(0.25)

                # Stop thread
                agent._stop_heartbeat_thread()
                assert agent._heartbeat_thread is None or not agent._heartbeat_thread.is_alive()

        # Verify heartbeats were sent
        heartbeat_calls = [
            c for c in mock_bus.send_event.call_args_list
            if c.kwargs.get("event_type_name") == "node.heartbeat"
        ]
        assert len(heartbeat_calls) >= 1

    def test_heartbeat_thread_not_started_when_disabled(self, disabled_registry_config):
        """Test that heartbeat thread is not started when registration disabled."""
        with patch.object(BaseAgent, '_load_config') as mock_load:
            mock_load.return_value = {
                "name": "test.agent",
                "type": "test",
                "capabilities": [],
                "registry": {"enabled": False},
            }

            mock_bus = MagicMock()
            with patch('src.agents.base_agent.MindBus', return_value=mock_bus):
                agent = TestAgent(disabled_registry_config)
                agent._start_heartbeat_thread()

        assert agent._heartbeat_thread is None


# =============================================================================
# Test: Get Passport
# =============================================================================

class TestGetPassport:
    """Tests for get_passport() method."""

    def test_get_passport_returns_none_before_build(self, test_config_path):
        """Test that get_passport returns None before building."""
        with patch.object(BaseAgent, '_load_config') as mock_load:
            mock_load.return_value = {
                "name": "test.agent",
                "type": "test",
                "capabilities": [],
                "registry": {"enabled": True},
            }

            with patch('src.agents.base_agent.MindBus'):
                agent = TestAgent(test_config_path)

        assert agent.get_passport() is None

    def test_get_passport_returns_passport_after_build(self, test_config_path):
        """Test that get_passport returns passport after building."""
        with patch.object(BaseAgent, '_load_config') as mock_load:
            mock_load.return_value = {
                "name": "test.agent",
                "type": "test",
                "capabilities": [],
                "registry": {"enabled": True},
            }

            with patch('src.agents.base_agent.MindBus'):
                agent = TestAgent(test_config_path)
                agent._build_passport()

        passport = agent.get_passport()
        assert passport is not None
        assert isinstance(passport, NodePassport)


# =============================================================================
# Test: Integration with DummyAgent Config
# =============================================================================

class TestWithDummyAgentConfig:
    """Tests using actual dummy_agent.yaml config."""

    def test_dummy_agent_builds_passport(self):
        """Test that DummyAgent can build a valid passport."""
        config_path = Path(__file__).parent.parent / "config" / "agents" / "dummy_agent.yaml"

        if not config_path.exists():
            pytest.skip("dummy_agent.yaml not found")

        mock_bus = MagicMock()
        with patch('src.agents.base_agent.MindBus', return_value=mock_bus):
            from src.agents.dummy_agent import DummyAgent
            agent = DummyAgent(str(config_path))
            passport = agent._build_passport()

        assert passport.metadata.name == "dummy_agent"
        assert passport.metadata.node_type == NodeType.AGENT
        assert passport.has_capability("test.echo")
        assert passport.has_capability("generate_article")
