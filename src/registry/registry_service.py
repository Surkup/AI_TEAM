"""
Registry Service — Listens to node.* events and manages NodeRegistry.

This service:
- Subscribes to evt.node.* events via MindBus
- Processes node.registered → adds node to registry
- Processes node.heartbeat → updates last_seen
- Processes node.deregistered → removes node from registry
- Runs cleanup thread for TTL-based node removal

See: docs/SSOT/NODE_REGISTRY_SPEC_v1.0.md
"""

import logging
import signal
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.mindbus.core import MindBus
from src.registry.node_registry import NodeRegistry
from src.registry.models import NodePassport

logger = logging.getLogger(__name__)


class RegistryService:
    """
    Registry Service that bridges MindBus events to NodeRegistry.

    Subscribes to:
    - evt.node.registered → register_node()
    - evt.node.heartbeat → update_heartbeat()
    - evt.node.deregistered → deregister_node()
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize Registry Service.

        Args:
            config_path: Path to registry.yaml config file.
        """
        self.config = self._load_config(config_path)
        self.registry = NodeRegistry(config_path)
        self.bus = MindBus()

        self._running = False
        self._start_time: Optional[datetime] = None

        # Statistics
        self._events_processed = 0
        self._registrations = 0
        self._heartbeats = 0
        self._deregistrations = 0

        logger.info("RegistryService initialized")

    def _load_config(self, config_path: Optional[str]) -> dict:
        """Load configuration from YAML file."""
        defaults = {
            "service_name": "registry-service",
            "log_level": "INFO",
        }

        if config_path is None:
            config_path = str(Path(__file__).parent.parent.parent / "config" / "registry.yaml")

        if Path(config_path).exists():
            try:
                with open(config_path) as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        defaults.update(file_config.get("service", {}))
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")

        return defaults

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def _on_node_registered(self, event: dict, data: dict) -> None:
        """
        Handle node.registered event.

        Expected data:
            - passport: Full NodePassport dict
            - node_id: Node UID
            - name: Node name
        """
        self._events_processed += 1

        try:
            passport_data = data.get("passport")
            if not passport_data:
                logger.warning("node.registered event missing passport data")
                return

            # Parse passport from dict
            passport = NodePassport.model_validate(passport_data)

            # Register in registry
            try:
                node_id = self.registry.register_node(passport)
                self._registrations += 1
                logger.info(
                    f"Node registered via event: {passport.metadata.name} "
                    f"(uid={node_id[:8]}...)"
                )
            except ValueError as e:
                # Node already registered - update instead
                logger.warning(f"Node already registered: {e}")

        except Exception as e:
            logger.error(f"Error processing node.registered event: {e}")

    def _on_node_heartbeat(self, event: dict, data: dict) -> None:
        """
        Handle node.heartbeat event.

        Expected data:
            - node_id: Node UID
            - name: Node name (for logging)
            - renew_time: ISO timestamp
        """
        self._events_processed += 1

        try:
            node_id = data.get("node_id")
            if not node_id:
                logger.warning("node.heartbeat event missing node_id")
                return

            # Update heartbeat in registry
            if self.registry.update_heartbeat(node_id):
                self._heartbeats += 1
                logger.debug(f"Heartbeat updated for node {node_id[:8]}...")
            else:
                # Node not in registry - might have been cleaned up
                logger.warning(f"Heartbeat for unknown node: {node_id[:8]}...")

        except Exception as e:
            logger.error(f"Error processing node.heartbeat event: {e}")

    def _on_node_deregistered(self, event: dict, data: dict) -> None:
        """
        Handle node.deregistered event.

        Expected data:
            - node_id: Node UID
            - name: Node name
            - reason: Deregistration reason
        """
        self._events_processed += 1

        try:
            node_id = data.get("node_id")
            reason = data.get("reason", "Unknown")

            if not node_id:
                logger.warning("node.deregistered event missing node_id")
                return

            # Deregister from registry
            if self.registry.deregister_node(node_id, reason):
                self._deregistrations += 1
                logger.info(
                    f"Node deregistered via event: {data.get('name', 'unknown')} "
                    f"(reason={reason})"
                )
            else:
                logger.warning(f"Deregister for unknown node: {node_id[:8]}...")

        except Exception as e:
            logger.error(f"Error processing node.deregistered event: {e}")

    # =========================================================================
    # Service Lifecycle
    # =========================================================================

    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown on Ctrl+C."""
        def signal_handler(sig, frame):
            logger.info("Received shutdown signal")
            self.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def start(self) -> None:
        """Start the Registry Service."""
        print("\n📋 Starting Registry Service...")

        # Connect to MindBus
        self.bus.connect()
        print("   ✓ Connected to MindBus")

        self._setup_signal_handlers()

        # Subscribe to node events
        # Pattern: evt.node.* (all node-related events)
        self.bus.subscribe("evt.node.registered", self._on_node_registered)
        self.bus.subscribe("evt.node.heartbeat", self._on_node_heartbeat)
        self.bus.subscribe("evt.node.deregistered", self._on_node_deregistered)
        print("   ✓ Subscribed to evt.node.* events")

        # Start registry cleanup thread
        self.registry.start_cleanup_thread()
        print("   ✓ Started cleanup thread")

        self._running = True
        self._start_time = datetime.now()

        print("\n   Waiting for node events... (Ctrl+C to stop)\n")

        try:
            self.bus.start_consuming()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the Registry Service."""
        if not self._running:
            return

        self._running = False

        # Stop cleanup thread
        self.registry.stop_cleanup_thread()

        # Disconnect from MindBus
        try:
            self.bus.stop_consuming()
        except Exception:
            pass

        self.bus.disconnect()

        # Print stats
        uptime = ""
        if self._start_time:
            uptime = f" (uptime: {datetime.now() - self._start_time})"

        print(f"\n🛑 Registry Service stopped{uptime}")
        print(f"   Events processed: {self._events_processed}")
        print(f"   - Registrations: {self._registrations}")
        print(f"   - Heartbeats: {self._heartbeats}")
        print(f"   - Deregistrations: {self._deregistrations}")
        print(f"   Nodes in registry: {len(self.registry.get_all_nodes())}")

    # =========================================================================
    # Public API
    # =========================================================================

    def get_registry(self) -> NodeRegistry:
        """Get the underlying NodeRegistry instance."""
        return self.registry

    def get_stats(self) -> dict:
        """Get service statistics."""
        registry_stats = self.registry.get_stats()
        return {
            "service": {
                "running": self._running,
                "start_time": self._start_time.isoformat() if self._start_time else None,
                "events_processed": self._events_processed,
                "registrations": self._registrations,
                "heartbeats": self._heartbeats,
                "deregistrations": self._deregistrations,
            },
            "registry": registry_stats,
        }


def main():
    """Run the Registry Service."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    )

    service = RegistryService()
    service.start()


if __name__ == "__main__":
    main()
