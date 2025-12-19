"""
Node Registry — In-memory MVP implementation.

Based on: docs/SSOT/NODE_REGISTRY_SPEC_v1.0.md

This is an MVP implementation that stores nodes in memory.
For production, use etcd or Consul as backend.
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any

import yaml

from .models import (
    NodePassport,
    NodeMetadata,
    NodeSpec,
    NodeStatus,
    NodeType,
    NodePhase,
    HealthState,
    RegistryEntry,
    Condition,
    ConditionStatus,
    Lease,
)


logger = logging.getLogger(__name__)


class NodeRegistry:
    """
    In-memory Node Registry for AI_TEAM.

    Provides:
    - Node registration and deregistration
    - Heartbeat tracking (TTL-based liveness)
    - Capability-based node discovery (label selectors)
    - Automatic cleanup of dead nodes

    Thread-safe implementation using locks.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize Node Registry.

        Args:
            config_path: Path to registry.yaml config file.
                        If None, uses default values.
        """
        # Load config
        self.config = self._load_config(config_path)

        # Registry storage: node_id -> RegistryEntry
        self._nodes: Dict[str, RegistryEntry] = {}
        self._lock = threading.RLock()

        # Cleanup thread
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()

        # Event callbacks
        self._on_node_registered: List[Callable[[NodePassport], None]] = []
        self._on_node_deregistered: List[Callable[[str, str], None]] = []
        self._on_node_unhealthy: List[Callable[[str], None]] = []

        logger.info(
            f"NodeRegistry initialized: "
            f"heartbeat_interval={self.config['heartbeat_interval_seconds']}s, "
            f"ttl={self.config['ttl_seconds']}s"
        )

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration from YAML file or use defaults."""
        defaults = {
            "heartbeat_interval_seconds": 10,
            "ttl_seconds": 30,
            "cleanup_interval_seconds": 5,
        }

        if config_path is None:
            # Try default path
            default_path = Path(__file__).parent.parent.parent / "config" / "registry.yaml"
            if default_path.exists():
                config_path = str(default_path)

        if config_path and Path(config_path).exists():
            try:
                with open(config_path) as f:
                    file_config = yaml.safe_load(f)
                    if file_config and "registry" in file_config:
                        defaults.update(file_config["registry"])
                        logger.info(f"Loaded config from {config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")

        return defaults

    # =========================================================================
    # Registration
    # =========================================================================

    def register_node(self, passport: NodePassport) -> str:
        """
        Register a node in the registry.

        Args:
            passport: Complete NodePassport for the node.

        Returns:
            node_id (UID) of registered node.

        Raises:
            ValueError: If node with same UID or name already exists.
        """
        node_id = passport.metadata.uid
        node_name = passport.metadata.name

        with self._lock:
            # Check for duplicate UID
            if node_id in self._nodes:
                raise ValueError(f"Node with UID {node_id} already registered")

            # Check for duplicate name
            for entry in self._nodes.values():
                if entry.passport.metadata.name == node_name:
                    raise ValueError(f"Node with name '{node_name}' already registered")

            # Create registry entry
            entry = RegistryEntry(
                node_id=node_id,
                node_type=passport.metadata.node_type,
                passport=passport,
                last_seen=datetime.utcnow(),
                health_state=HealthState.ALIVE,
                registered_at=datetime.utcnow(),
            )

            self._nodes[node_id] = entry

            logger.info(
                f"Node registered: {node_name} (uid={node_id[:8]}..., "
                f"type={passport.metadata.node_type.value}, "
                f"capabilities={[c.name for c in passport.spec.capabilities]})"
            )

        # Fire callbacks
        for callback in self._on_node_registered:
            try:
                callback(passport)
            except Exception as e:
                logger.error(f"Error in on_node_registered callback: {e}")

        return node_id

    def deregister_node(self, node_id: str, reason: str = "GracefulShutdown") -> bool:
        """
        Remove a node from the registry.

        Args:
            node_id: UID of the node to remove.
            reason: Reason for deregistration.

        Returns:
            True if node was removed, False if not found.
        """
        with self._lock:
            if node_id not in self._nodes:
                logger.warning(f"Cannot deregister: node {node_id} not found")
                return False

            entry = self._nodes.pop(node_id)
            node_name = entry.passport.metadata.name

            logger.info(f"Node deregistered: {node_name} (reason={reason})")

        # Fire callbacks
        for callback in self._on_node_deregistered:
            try:
                callback(node_id, reason)
            except Exception as e:
                logger.error(f"Error in on_node_deregistered callback: {e}")

        return True

    # =========================================================================
    # Heartbeat
    # =========================================================================

    def update_heartbeat(self, node_id: str) -> bool:
        """
        Update heartbeat (last_seen) for a node.

        Args:
            node_id: UID of the node.

        Returns:
            True if updated, False if node not found.
        """
        with self._lock:
            if node_id not in self._nodes:
                logger.warning(f"Heartbeat for unknown node: {node_id}")
                return False

            entry = self._nodes[node_id]
            entry.last_seen = datetime.utcnow()
            entry.health_state = HealthState.ALIVE

            # Also update lease in passport
            entry.passport.status.lease.renew_time = datetime.utcnow()

            logger.debug(f"Heartbeat updated: {entry.passport.metadata.name}")
            return True

    # =========================================================================
    # Query / Discovery
    # =========================================================================

    def get_node(self, node_id: str) -> Optional[NodePassport]:
        """
        Get a node by its UID.

        Args:
            node_id: UID of the node.

        Returns:
            NodePassport if found, None otherwise.
        """
        with self._lock:
            entry = self._nodes.get(node_id)
            return entry.passport if entry else None

    def get_node_by_name(self, name: str) -> Optional[NodePassport]:
        """
        Get a node by its name.

        Args:
            name: Name of the node.

        Returns:
            NodePassport if found, None otherwise.
        """
        with self._lock:
            for entry in self._nodes.values():
                if entry.passport.metadata.name == name:
                    return entry.passport
            return None

    def get_all_nodes(self) -> List[NodePassport]:
        """
        Get all registered nodes.

        Returns:
            List of all NodePassports.
        """
        with self._lock:
            return [entry.passport for entry in self._nodes.values()]

    def get_alive_nodes(self) -> List[NodePassport]:
        """
        Get all nodes that are alive (within TTL).

        Returns:
            List of alive NodePassports.
        """
        with self._lock:
            return [
                entry.passport
                for entry in self._nodes.values()
                if entry.health_state == HealthState.ALIVE
            ]

    def find_nodes(
        self,
        selector: Optional[Dict[str, str]] = None,
        node_type: Optional[NodeType] = None,
        capability: Optional[str] = None,
        only_healthy: bool = True,
    ) -> List[NodePassport]:
        """
        Find nodes matching criteria.

        Args:
            selector: Label selector (all labels must match, AND logic).
            node_type: Filter by node type.
            capability: Filter by capability name.
            only_healthy: Only return healthy (ALIVE) nodes.

        Returns:
            List of matching NodePassports.
        """
        with self._lock:
            results = []

            for entry in self._nodes.values():
                passport = entry.passport

                # Filter by health
                if only_healthy and entry.health_state != HealthState.ALIVE:
                    continue

                # Filter by node type
                if node_type and passport.metadata.node_type != node_type:
                    continue

                # Filter by capability
                if capability and not passport.has_capability(capability):
                    continue

                # Filter by label selector
                if selector and not passport.matches_labels(selector):
                    continue

                results.append(passport)

            return results

    def find_nodes_by_capability(
        self,
        capability_name: str,
        only_healthy: bool = True
    ) -> List[NodePassport]:
        """
        Find nodes with a specific capability.

        Shorthand for find_nodes(capability=...).

        Args:
            capability_name: Name of the capability.
            only_healthy: Only return healthy nodes.

        Returns:
            List of matching NodePassports.
        """
        return self.find_nodes(capability=capability_name, only_healthy=only_healthy)

    # =========================================================================
    # Cleanup (TTL-based)
    # =========================================================================

    def remove_dead_nodes(self) -> List[str]:
        """
        Remove nodes that have exceeded TTL.

        Returns:
            List of removed node IDs.
        """
        ttl = timedelta(seconds=self.config["ttl_seconds"])
        now = datetime.utcnow()
        removed = []

        with self._lock:
            dead_nodes = []

            for node_id, entry in self._nodes.items():
                time_since_heartbeat = now - entry.last_seen

                if time_since_heartbeat > ttl:
                    dead_nodes.append(node_id)
                    logger.warning(
                        f"Node TTL expired: {entry.passport.metadata.name} "
                        f"(last_seen={entry.last_seen.isoformat()}, "
                        f"elapsed={time_since_heartbeat.total_seconds():.1f}s)"
                    )
                elif time_since_heartbeat > ttl / 2:
                    # Mark as NOT_READY if more than half TTL elapsed
                    if entry.health_state == HealthState.ALIVE:
                        entry.health_state = HealthState.NOT_READY
                        logger.warning(
                            f"Node becoming unhealthy: {entry.passport.metadata.name}"
                        )

            # Remove dead nodes
            for node_id in dead_nodes:
                entry = self._nodes.pop(node_id)
                entry.health_state = HealthState.OFFLINE
                removed.append(node_id)

                # Fire unhealthy callback
                for callback in self._on_node_unhealthy:
                    try:
                        callback(node_id)
                    except Exception as e:
                        logger.error(f"Error in on_node_unhealthy callback: {e}")

        return removed

    def start_cleanup_thread(self):
        """Start background thread for cleaning up dead nodes."""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            logger.warning("Cleanup thread already running")
            return

        self._stop_cleanup.clear()

        def cleanup_loop():
            interval = self.config["cleanup_interval_seconds"]
            logger.info(f"Cleanup thread started (interval={interval}s)")

            while not self._stop_cleanup.wait(timeout=interval):
                try:
                    removed = self.remove_dead_nodes()
                    if removed:
                        logger.info(f"Cleaned up {len(removed)} dead nodes")
                except Exception as e:
                    logger.error(f"Error in cleanup thread: {e}")

            logger.info("Cleanup thread stopped")

        self._cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def stop_cleanup_thread(self):
        """Stop the cleanup thread."""
        self._stop_cleanup.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5.0)
            self._cleanup_thread = None

    # =========================================================================
    # Event callbacks
    # =========================================================================

    def on_node_registered(self, callback: Callable[[NodePassport], None]):
        """Register callback for node registration events."""
        self._on_node_registered.append(callback)

    def on_node_deregistered(self, callback: Callable[[str, str], None]):
        """Register callback for node deregistration events."""
        self._on_node_deregistered.append(callback)

    def on_node_unhealthy(self, callback: Callable[[str], None]):
        """Register callback for node unhealthy events."""
        self._on_node_unhealthy.append(callback)

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Dict with statistics.
        """
        with self._lock:
            total = len(self._nodes)
            alive = sum(1 for e in self._nodes.values() if e.health_state == HealthState.ALIVE)
            not_ready = sum(1 for e in self._nodes.values() if e.health_state == HealthState.NOT_READY)

            by_type = {}
            for entry in self._nodes.values():
                node_type = entry.node_type.value
                by_type[node_type] = by_type.get(node_type, 0) + 1

            return {
                "total_nodes": total,
                "alive_nodes": alive,
                "not_ready_nodes": not_ready,
                "nodes_by_type": by_type,
                "config": self.config,
            }

    # =========================================================================
    # Context manager
    # =========================================================================

    def __enter__(self):
        """Start cleanup thread on enter."""
        self.start_cleanup_thread()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop cleanup thread on exit."""
        self.stop_cleanup_thread()
        return False
