"""
MindBus Message Models — Pydantic schemas from SSOT MESSAGE_FORMAT v1.1.2

This module defines the data structures for all 5 message types in AI_TEAM system.
All models are derived from docs/SSOT/MESSAGE_FORMAT_v1.1.md specification.

IMPORTANT: These models validate the 'data' field of CloudEvents messages.
CloudEvents envelope is handled separately by the cloudevents library.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# =============================================================================
# Common Types
# =============================================================================

# Standard error codes from google.rpc.Code (gRPC error model)
ErrorCode = Literal[
    "OK",
    "CANCELLED",
    "UNKNOWN",
    "INVALID_ARGUMENT",
    "DEADLINE_EXCEEDED",
    "NOT_FOUND",
    "ALREADY_EXISTS",
    "PERMISSION_DENIED",
    "RESOURCE_EXHAUSTED",
    "FAILED_PRECONDITION",
    "ABORTED",
    "OUT_OF_RANGE",
    "UNIMPLEMENTED",
    "INTERNAL",
    "UNAVAILABLE",
    "DATA_LOSS",
    "UNAUTHENTICATED",
]

# Event severity levels
Severity = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]

# Control signal types
ControlType = Literal["stop", "pause", "resume", "shutdown", "config"]


# =============================================================================
# COMMAND — Task assignment from Orchestrator to Agent
# =============================================================================

class RetryPolicy(BaseModel):
    """Retry policy for command execution."""

    max_attempts: int = Field(
        ge=1,
        le=10,
        description="Maximum retry attempts"
    )
    retry_delay_seconds: int = Field(
        ge=1,
        description="Delay between retries in seconds"
    )
    backoff_multiplier: float = Field(
        ge=1.0,
        le=5.0,
        default=1.0,
        description="Exponential backoff multiplier"
    )


class CommandRequirements(BaseModel):
    """Requirements for the executing node (v1.1)."""

    capabilities: List[str] = Field(
        default_factory=list,
        description="Required node capabilities (from NODE_PASSPORT)"
    )
    constraints: Optional[Dict[str, Any]] = Field(
        None,
        description="Execution constraints (sandbox, memory_limit, etc.)"
    )


class CommandContext(BaseModel):
    """Business context for command execution (v1.1)."""

    model_config = {"extra": "allow"}  # Allow additional context fields

    process_id: Optional[str] = Field(
        None,
        description="Process ID (from PROCESS_CARD)"
    )
    step: Optional[str] = Field(
        None,
        description="Step within process"
    )
    parent_task_id: Optional[str] = Field(
        None,
        description="Parent task ID for nested tasks"
    )


class CommandData(BaseModel):
    """
    Data field structure for COMMAND messages (ai.team.command).

    COMMAND is a task assignment from Orchestrator to Agent.
    """

    action: str = Field(
        min_length=1,
        max_length=100,
        description="Action to execute (e.g., 'generate_article', 'review_code')"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Action parameters (structure depends on action)"
    )
    requirements: Optional[CommandRequirements] = Field(
        None,
        description="Requirements for the executing node (v1.1)"
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="Business context (process_id, step, etc.)"
    )
    timeout_seconds: Optional[int] = Field(
        None,
        ge=1,
        le=3600,
        description="Execution timeout in seconds"
    )
    idempotency_key: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Idempotency key for safe retries (Stripe API pattern)"
    )
    retry_policy: Optional[RetryPolicy] = Field(
        None,
        description="Retry policy for failures"
    )


# =============================================================================
# RESULT — Successful execution result from Agent
# =============================================================================

class ResultData(BaseModel):
    """
    Data field structure for RESULT messages (ai.team.result).

    RESULT contains ONLY successful executions (status=SUCCESS).
    Errors are sent as separate ERROR type messages.
    """

    status: Literal["SUCCESS"] = Field(
        default="SUCCESS",
        description="Execution status (only SUCCESS; errors → ERROR type)"
    )
    output: Optional[Dict[str, Any]] = Field(
        None,
        description="Execution result (structure depends on action)"
    )
    execution_time_ms: int = Field(
        ge=0,
        description="Actual execution time in milliseconds"
    )
    metrics: Optional[Dict[str, Any]] = Field(
        None,
        description="Execution metrics (model, tokens, cost, etc.)"
    )


# =============================================================================
# ERROR — Error response (v1.1 separate type)
# =============================================================================

class ErrorInfo(BaseModel):
    """Error information following RFC 7807 + gRPC error model."""

    code: ErrorCode = Field(
        description="Standard error code (google.rpc.Code)"
    )
    message: str = Field(
        min_length=1,
        description="Human-readable error description"
    )
    retryable: bool = Field(
        description="Whether the operation can be safely retried"
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details (domain-specific)"
    )


class ErrorData(BaseModel):
    """
    Data field structure for ERROR messages (ai.team.error).

    ERROR is a separate message type for error responses (v1.1).
    This follows RFC 7807 Problem Details pattern.
    """

    error: ErrorInfo = Field(
        description="Error information"
    )
    execution_time_ms: Optional[int] = Field(
        None,
        ge=0,
        description="Time until error occurred (if applicable)"
    )


# =============================================================================
# EVENT — System event notification (Pub/Sub)
# =============================================================================

class EventData(BaseModel):
    """
    Data field structure for EVENT messages (ai.team.event).

    EVENT is a notification about system events (Pub/Sub pattern).
    """

    event_type: str = Field(
        min_length=1,
        max_length=100,
        description="Event type (format: source.action, e.g., 'task.completed')"
    )
    event_data: Dict[str, Any] = Field(
        description="Event data (structure depends on event_type)"
    )
    severity: Optional[Severity] = Field(
        "INFO",
        description="Event severity level"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Tags for filtering and categorization"
    )


# =============================================================================
# CONTROL — Management signals
# =============================================================================

class ControlData(BaseModel):
    """
    Data field structure for CONTROL messages (ai.team.control).

    CONTROL signals are urgent management commands (STOP, PAUSE, etc.).
    Priority: 255 (maximum).
    """

    control_type: ControlType = Field(
        description="Type of control signal"
    )
    reason: Optional[str] = Field(
        None,
        description="Reason for the control signal"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional control parameters"
    )


# =============================================================================
# CloudEvents Envelope (for reference and validation)
# =============================================================================

class CloudEventEnvelope(BaseModel):
    """
    CloudEvents v1.0 envelope structure.

    Note: This is for reference. In practice, use the cloudevents library
    for envelope handling. This model is used for validation and testing.
    """

    specversion: Literal["1.0"] = Field(
        default="1.0",
        description="CloudEvents specification version"
    )
    type: Literal[
        "ai.team.command",
        "ai.team.result",
        "ai.team.error",
        "ai.team.event",
        "ai.team.control"
    ] = Field(
        description="Event type (determines data structure)"
    )
    source: str = Field(
        min_length=1,
        description="Event source (e.g., 'orchestrator-core', 'agent.writer.001')"
    )
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique event ID"
    )
    time: Optional[str] = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
        description="Event timestamp (ISO 8601)"
    )
    subject: Optional[str] = Field(
        None,
        description="Event subject (e.g., task ID)"
    )
    datacontenttype: Optional[str] = Field(
        "application/json",
        description="Content type of data field"
    )
    traceparent: Optional[str] = Field(
        None,
        description="W3C Trace Context traceparent header"
    )
    data: Dict[str, Any] = Field(
        description="Event data (validated by type-specific models)"
    )


# =============================================================================
# Type mapping for validation
# =============================================================================

MESSAGE_TYPE_TO_MODEL = {
    "ai.team.command": CommandData,
    "ai.team.result": ResultData,
    "ai.team.error": ErrorData,
    "ai.team.event": EventData,
    "ai.team.control": ControlData,
}


def validate_message_data(event_type: str, data: Dict[str, Any]) -> BaseModel:
    """
    Validate message data against the appropriate SSOT schema.

    Args:
        event_type: CloudEvents type (e.g., 'ai.team.command')
        data: The data field content to validate

    Returns:
        Validated Pydantic model instance

    Raises:
        ValueError: If event_type is unknown
        ValidationError: If data doesn't match schema
    """
    model_class = MESSAGE_TYPE_TO_MODEL.get(event_type)
    if model_class is None:
        raise ValueError(f"Unknown event type: {event_type}")
    return model_class(**data)
