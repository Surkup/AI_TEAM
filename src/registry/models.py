"""
Pydantic models for NODE_PASSPORT according to SSOT specification.

Based on: docs/SSOT/NODE_PASSPORT_SPEC_v1.0.md
Pattern: Kubernetes API Object Model (metadata/spec/status)
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


# =============================================================================
# Enums
# =============================================================================

class NodeType(str, Enum):
    """Type of node in the system."""
    AGENT = "agent"
    ORCHESTRATOR = "orchestrator"
    STORAGE = "storage"
    GATEWAY = "gateway"


class NodePhase(str, Enum):
    """Phase of node lifecycle."""
    PENDING = "Pending"
    RUNNING = "Running"
    TERMINATING = "Terminating"
    FAILED = "Failed"


class ConditionStatus(str, Enum):
    """Status of a condition."""
    TRUE = "True"
    FALSE = "False"
    UNKNOWN = "Unknown"


class HealthState(str, Enum):
    """Health state of a node in registry."""
    ALIVE = "ALIVE"
    NOT_READY = "NOT_READY"
    OFFLINE = "OFFLINE"


# =============================================================================
# Capability
# =============================================================================

class Capability(BaseModel):
    """
    Capability of a node.

    Example:
        {
            "name": "generate_text",
            "version": "1.0",
            "parameters": {
                "models": ["gpt-4o-mini"],
                "max_tokens": 4000
            }
        }
    """
    name: str = Field(..., min_length=1, max_length=100, description="Capability name")
    version: str = Field(default="1.0", description="Capability version (semver)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Capability parameters")


# =============================================================================
# Metadata
# =============================================================================

class NodeMetadata(BaseModel):
    """
    Node metadata — WHO AM I (identification).

    Contains immutable or rarely changing information about the node.
    """
    uid: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier (UUID)"
    )
    name: str = Field(..., min_length=1, max_length=63, description="Human-readable name (unique)")
    node_type: NodeType = Field(..., description="Type of node")
    labels: Dict[str, str] = Field(
        default_factory=dict,
        description="Labels for selectors (key-value pairs)"
    )
    annotations: Dict[str, str] = Field(
        default_factory=dict,
        description="Arbitrary metadata (not for selectors)"
    )
    creation_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation time"
    )
    version: str = Field(default="1.0.0", description="Node version (semver)")


# =============================================================================
# Resources
# =============================================================================

class ResourceRequirements(BaseModel):
    """Resource requests and limits."""
    cpu: Optional[str] = Field(None, description="CPU (e.g., '500m', '2000m')")
    memory: Optional[str] = Field(None, description="Memory (e.g., '2Gi', '512Mi')")
    concurrent_tasks: Optional[int] = Field(None, ge=1, description="Max concurrent tasks")
    api_tokens: Optional[Dict[str, int]] = Field(None, description="API token limits")


class Resources(BaseModel):
    """Node resources (requests and limits)."""
    requests: Optional[ResourceRequirements] = None
    limits: Optional[ResourceRequirements] = None


# =============================================================================
# Endpoint
# =============================================================================

class Endpoint(BaseModel):
    """How to communicate with the node."""
    protocol: str = Field(default="amqp", description="Protocol: amqp, http, grpc")
    queue: Optional[str] = Field(None, description="AMQP queue name for tasks")
    reply_queue: Optional[str] = Field(None, description="AMQP queue for replies")
    exchange_name: Optional[str] = Field(None, description="AMQP exchange name")
    routing_key: Optional[str] = Field(None, description="AMQP routing key")
    url: Optional[str] = Field(None, description="HTTP/gRPC URL")


# =============================================================================
# Spec
# =============================================================================

class NodeSpec(BaseModel):
    """
    Node spec — WHAT I CAN DO (capabilities declaration).

    Contains the desired state and capabilities of the node.
    """
    node_type: NodeType = Field(..., description="Type of node")
    capabilities: List[Capability] = Field(
        default_factory=list,
        description="List of node capabilities"
    )
    resources: Optional[Resources] = Field(None, description="Resource requirements")
    endpoint: Endpoint = Field(..., description="How to communicate with the node")
    configuration: Dict[str, Any] = Field(
        default_factory=dict,
        description="Node configuration"
    )


# =============================================================================
# Condition
# =============================================================================

class Condition(BaseModel):
    """
    Condition describes the state of a node at a certain point.

    Pattern from Kubernetes API.
    """
    type: str = Field(..., description="Condition type (e.g., 'Ready', 'APIAvailable')")
    status: ConditionStatus = Field(..., description="Status: True, False, Unknown")
    last_transition_time: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last time status changed"
    )
    reason: str = Field(default="", description="Machine-readable reason (CamelCase)")
    message: str = Field(default="", description="Human-readable message")


# =============================================================================
# Lease
# =============================================================================

class Lease(BaseModel):
    """
    Lease for heartbeat mechanism.

    Based on Kubernetes Lease API.
    """
    holder_identity: str = Field(..., description="ID of lease holder (usually node name)")
    acquire_time: datetime = Field(
        default_factory=datetime.utcnow,
        description="When lease was first acquired"
    )
    renew_time: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last renewal time (heartbeat)"
    )
    lease_duration_seconds: int = Field(
        default=30,
        ge=1,
        description="Lease duration in seconds"
    )


# =============================================================================
# Status
# =============================================================================

class NodeStatus(BaseModel):
    """
    Node status — MY CURRENT STATE (runtime state).

    Contains dynamic information that changes frequently.
    """
    phase: NodePhase = Field(default=NodePhase.PENDING, description="Lifecycle phase")
    conditions: List[Condition] = Field(
        default_factory=list,
        description="Detailed status conditions"
    )
    lease: Lease = Field(..., description="Heartbeat lease")
    current_tasks: int = Field(default=0, ge=0, description="Current tasks in progress")
    total_tasks_processed: int = Field(default=0, ge=0, description="Total tasks processed")
    last_activity_time: Optional[datetime] = Field(None, description="Last activity time")
    uptime: Optional[str] = Field(None, description="Uptime (human-readable)")


# =============================================================================
# NODE PASSPORT (Complete)
# =============================================================================

class NodePassport(BaseModel):
    """
    Complete NODE PASSPORT according to SSOT specification.

    Structure:
        - metadata: WHO AM I (identification)
        - spec: WHAT I CAN DO (capabilities)
        - status: MY CURRENT STATE (runtime)

    Based on: docs/SSOT/NODE_PASSPORT_SPEC_v1.0.md
    """
    metadata: NodeMetadata = Field(..., description="Node identification")
    spec: NodeSpec = Field(..., description="Node capabilities")
    status: NodeStatus = Field(..., description="Node runtime status")

    def is_ready(self) -> bool:
        """Check if node is ready to accept tasks."""
        if self.status.phase != NodePhase.RUNNING:
            return False
        for condition in self.status.conditions:
            if condition.type == "Ready" and condition.status == ConditionStatus.TRUE:
                return True
        return False

    def has_capability(self, capability_name: str) -> bool:
        """Check if node has a specific capability."""
        return any(cap.name == capability_name for cap in self.spec.capabilities)

    def matches_labels(self, selector: Dict[str, str]) -> bool:
        """Check if node labels match the selector (AND logic)."""
        for key, value in selector.items():
            if self.metadata.labels.get(key) != value:
                return False
        return True


# =============================================================================
# Registry Entry (internal model for registry storage)
# =============================================================================

class RegistryEntry(BaseModel):
    """
    Internal model for storing node in registry.

    Adds registry-specific metadata to NodePassport.
    """
    node_id: str = Field(..., description="Node UID from metadata")
    node_type: NodeType = Field(..., description="Node type")
    passport: NodePassport = Field(..., description="Full node passport")
    last_seen: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last heartbeat time"
    )
    health_state: HealthState = Field(
        default=HealthState.ALIVE,
        description="Health state"
    )
    registered_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Registration time"
    )
