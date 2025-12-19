"""
Base Service — Abstract base class for all AI_TEAM infrastructure services.

Services (Storage, State, Scheduler) are similar to agents but:
- Have different NodeType (storage, gateway, etc. instead of agent)
- Handle different message patterns
- May provide HTTP endpoints in addition to AMQP

This class handles:
- Connection to MindBus
- Node registration (NODE_PASSPORT)
- Heartbeat to Registry
- Graceful shutdown

See: docs/project/IMPLEMENTATION_ROADMAP.md Step 2.0.1
"""

import logging
import signal
import threading
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.mindbus.core import MindBus
from src.registry.models import (
    NodePassport,
    NodeMetadata,
    NodeSpec,
    NodeStatus,
    NodeType,
    NodePhase,
    ConditionStatus,
    Capability,
    Condition,
    Lease,
    Endpoint,
)

logger = logging.getLogger(__name__)


class BaseService(ABC):
    """
    Abstract base class for AI_TEAM infrastructure services.

    Subclasses must implement:
    - handle_command(action, params, context) -> dict
    - node_type property -> NodeType

    The base class handles MindBus communication and registration.
    """

    def __init__(self, config_path: str):
        """
        Initialize service with configuration.

        Args:
            config_path: Path to service's YAML config file
        """
        self.config = self._load_config(config_path)
        self.name = self.config.get("name", "unknown-service")
        self.service_type = self.config.get("type", "service")
        self.capabilities = self.config.get("capabilities", [])

        # Registry configuration (from config or defaults)
        registry_config = self.config.get("registry", {})
        self._heartbeat_interval = registry_config.get("heartbeat_interval_seconds", 10)
        self._enable_registration = registry_config.get("enabled", True)

        self.bus = MindBus()
        self._running = False
        self._start_time: Optional[datetime] = None
        self._requests_processed = 0

        # Registration state
        self._node_uid: Optional[str] = None
        self._passport: Optional[NodePassport] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._stop_heartbeat = threading.Event()

    def _load_config(self, config_path: str) -> dict:
        """Load service configuration from YAML file."""
        with open(config_path) as f:
            config = yaml.safe_load(f)
        # Extract service-specific config (file may have nested structure)
        if len(config) == 1:
            return list(config.values())[0]
        return config

    @property
    @abstractmethod
    def node_type(self) -> NodeType:
        """
        Return the NodeType for this service.

        Returns:
            NodeType enum value (e.g., NodeType.STORAGE)
        """
        pass

    @abstractmethod
    def handle_command(
        self,
        action: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle incoming command/request.

        Args:
            action: The action to perform (e.g., "save_file", "read_file")
            params: Action parameters
            context: Optional execution context

        Returns:
            Result dictionary to be sent in response

        Raises:
            Exception: Any error will be caught and sent as ERROR message
        """
        pass

    def _on_command(self, event: dict, data: dict) -> None:
        """
        Handle incoming COMMAND message from MindBus.
        """
        start_time = time.time()

        action = data.get("action", "unknown")
        params = data.get("params", {})
        context = data.get("context")

        # Extract message metadata for response
        command_id = event.get("id")
        subject = event.get("subject")
        traceparent = event.get("traceparent")

        logger.info(f"[{self.name}] Received COMMAND: action={action}")

        try:
            result = self.handle_command(action, params, context)

            execution_time_ms = int((time.time() - start_time) * 1000)

            self.bus.send_result(
                output=result,
                execution_time_ms=execution_time_ms,
                source=self.name,
                subject=subject,
                trace_id=traceparent,
                correlation_id=command_id,
                metrics=self._get_metrics()
            )

            self._requests_processed += 1
            logger.info(f"[{self.name}] Sent RESULT for action={action} ({execution_time_ms}ms)")

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)

            error_code = self._get_error_code(e)
            retryable = self._is_retryable(e)

            self.bus.send_error(
                code=error_code,
                message=str(e),
                retryable=retryable,
                source=self.name,
                subject=subject,
                trace_id=traceparent,
                correlation_id=command_id,
                details={"exception_type": type(e).__name__},
                execution_time_ms=execution_time_ms
            )

            logger.error(f"[{self.name}] Sent ERROR for action={action}: {e}")

    def _get_error_code(self, error: Exception) -> str:
        """Map exception to google.rpc.Code."""
        mapping = {
            "ValueError": "INVALID_ARGUMENT",
            "TypeError": "INVALID_ARGUMENT",
            "KeyError": "NOT_FOUND",
            "FileNotFoundError": "NOT_FOUND",
            "PermissionError": "PERMISSION_DENIED",
            "TimeoutError": "DEADLINE_EXCEEDED",
            "ConnectionError": "UNAVAILABLE",
            "NotImplementedError": "UNIMPLEMENTED",
        }
        return mapping.get(type(error).__name__, "INTERNAL")

    def _is_retryable(self, error: Exception) -> bool:
        """Determine if error is retryable."""
        retryable_types = {"TimeoutError", "ConnectionError", "OSError"}
        return type(error).__name__ in retryable_types

    def _get_metrics(self) -> Dict[str, Any]:
        """Get service metrics for response."""
        return {
            "service": self.name,
            "type": self.service_type,
            "requests_processed": self._requests_processed,
        }

    # =========================================================================
    # Node Registration (NODE_PASSPORT)
    # =========================================================================

    def _build_passport(self) -> NodePassport:
        """Build NODE_PASSPORT from service configuration."""
        if self._node_uid is None:
            self._node_uid = str(uuid.uuid4())

        # Build capabilities from config
        capabilities = []
        labels = {"node.type": self.service_type}

        for cap in self.capabilities:
            if isinstance(cap, str):
                capabilities.append(Capability(name=cap, version="1.0"))
                labels[f"capability.{cap}"] = "true"
            elif isinstance(cap, dict):
                capabilities.append(Capability(
                    name=cap.get("name", "unknown"),
                    version=cap.get("version", "1.0"),
                    parameters=cap.get("parameters", {})
                ))
                labels[f"capability.{cap.get('name', 'unknown')}"] = "true"

        # Add custom labels from config
        config_labels = self.config.get("labels", {})
        labels.update(config_labels)

        # Determine endpoint configuration
        endpoint_config = self.config.get("endpoint", {})
        protocol = endpoint_config.get("protocol", "amqp")

        if protocol == "amqp":
            endpoint = Endpoint(
                protocol="amqp",
                queue=f"cmd.{self.name.replace('.', '_')}.*",
            )
        else:
            endpoint = Endpoint(
                protocol=protocol,
                url=endpoint_config.get("url"),
            )

        passport = NodePassport(
            metadata=NodeMetadata(
                uid=self._node_uid,
                name=self.name,
                node_type=self.node_type,
                labels=labels,
                version=self.config.get("version", "1.0.0"),
            ),
            spec=NodeSpec(
                node_type=self.node_type,
                capabilities=capabilities,
                endpoint=endpoint,
                configuration=self.config.get("configuration", {})
            ),
            status=NodeStatus(
                phase=NodePhase.RUNNING,
                conditions=[
                    Condition(
                        type="Ready",
                        status=ConditionStatus.TRUE,
                        reason="ServiceStarted",
                        message=f"Service {self.name} is ready",
                    )
                ],
                lease=Lease(
                    holder_identity=self.name,
                    lease_duration_seconds=max(1, int(self._heartbeat_interval * 3)),
                ),
                current_tasks=0,
                total_tasks_processed=self._requests_processed,
            ),
        )

        self._passport = passport
        return passport

    def _send_registration_event(self) -> None:
        """Send node.registered EVENT to MindBus."""
        if not self._enable_registration:
            return

        passport = self._build_passport()

        self.bus.send_event(
            event_type_name="node.registered",
            event_data={
                "node_id": passport.metadata.uid,
                "name": passport.metadata.name,
                "node_type": passport.metadata.node_type.value,
                "capabilities": [cap.name for cap in passport.spec.capabilities],
                "labels": passport.metadata.labels,
                "passport": passport.model_dump(mode="json"),
            },
            source=self.name,
            tags=["registration", "node", "service"],
        )

        logger.info(f"[{self.name}] Sent node.registered event (uid={self._node_uid[:8]}...)")

    def _send_heartbeat_event(self) -> None:
        """Send node.heartbeat EVENT to MindBus."""
        if not self._enable_registration or self._passport is None:
            return

        self._passport.status.lease.renew_time = datetime.utcnow()
        self._passport.status.total_tasks_processed = self._requests_processed

        self.bus.send_event(
            event_type_name="node.heartbeat",
            event_data={
                "node_id": self._node_uid,
                "name": self.name,
                "renew_time": self._passport.status.lease.renew_time.isoformat(),
                "current_tasks": self._passport.status.current_tasks,
                "total_tasks_processed": self._requests_processed,
            },
            source=self.name,
            tags=["heartbeat", "node", "service"],
        )

        logger.debug(f"[{self.name}] Sent heartbeat")

    def _send_deregistration_event(self, reason: str = "GracefulShutdown") -> None:
        """Send node.deregistered EVENT to MindBus."""
        if not self._enable_registration or self._node_uid is None:
            return

        self.bus.send_event(
            event_type_name="node.deregistered",
            event_data={
                "node_id": self._node_uid,
                "name": self.name,
                "reason": reason,
                "total_tasks_processed": self._requests_processed,
            },
            source=self.name,
            tags=["deregistration", "node", "service"],
        )

        logger.info(f"[{self.name}] Sent node.deregistered event (reason={reason})")

    def _start_heartbeat_thread(self) -> None:
        """Start background thread for sending heartbeats."""
        if not self._enable_registration:
            return

        self._stop_heartbeat.clear()

        def heartbeat_loop():
            logger.info(f"[{self.name}] Heartbeat thread started (interval={self._heartbeat_interval}s)")

            while not self._stop_heartbeat.wait(timeout=self._heartbeat_interval):
                try:
                    self._send_heartbeat_event()
                except Exception as e:
                    logger.error(f"[{self.name}] Error sending heartbeat: {e}")

            logger.info(f"[{self.name}] Heartbeat thread stopped")

        self._heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _stop_heartbeat_thread(self) -> None:
        """Stop the heartbeat thread."""
        self._stop_heartbeat.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=2.0)
            self._heartbeat_thread = None

    def get_passport(self) -> Optional[NodePassport]:
        """Get current NODE_PASSPORT."""
        return self._passport

    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown on Ctrl+C."""
        def signal_handler(sig, frame):
            logger.info(f"[{self.name}] Received shutdown signal")
            self._running = False
            self.bus.stop_consuming()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def start(self) -> None:
        """Start the service and begin processing requests."""
        print(f"\n📦 Starting {self.name}...")
        print(f"   Type: {self.service_type}")
        print(f"   NodeType: {self.node_type.value}")
        print(f"   Capabilities: {', '.join(str(c) for c in self.capabilities)}")

        self.bus.connect()
        print(f"   ✓ Connected to MindBus")

        self._setup_signal_handlers()

        # Subscribe to commands for this service
        routing_pattern = f"cmd.{self.name.replace('.', '_')}.*"
        self.bus.subscribe(routing_pattern, self._on_command)
        print(f"   ✓ Subscribed to: {routing_pattern}")

        # Also subscribe to service-type commands
        type_pattern = f"cmd.{self.service_type}.*"
        if type_pattern != routing_pattern:
            self.bus.subscribe(type_pattern, self._on_command)
            print(f"   ✓ Subscribed to: {type_pattern}")

        self._running = True
        self._start_time = datetime.now()

        # Register with Node Registry
        if self._enable_registration:
            self._send_registration_event()
            self._start_heartbeat_thread()
            print(f"   ✓ Registered with Node Registry (heartbeat every {self._heartbeat_interval}s)")

        print(f"\n   Waiting for requests... (Ctrl+C to stop)\n")

        try:
            self.bus.start_consuming()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the service and cleanup."""
        self._running = False

        if self._enable_registration:
            self._stop_heartbeat_thread()
            try:
                self._send_deregistration_event()
            except Exception as e:
                logger.warning(f"[{self.name}] Failed to send deregistration: {e}")

        self.bus.disconnect()

        uptime = ""
        if self._start_time:
            uptime = f" (uptime: {datetime.now() - self._start_time})"

        print(f"\n🛑 {self.name} stopped{uptime}")
        print(f"   Requests processed: {self._requests_processed}")
