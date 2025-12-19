"""
Pydantic models for Process Card according to SSOT specification.

Based on: docs/SSOT/PROCESS_CARD_SPEC_v1.0.md
Philosophy: "Dumb Card, Smart Orchestrator"
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
import uuid


# =============================================================================
# Enums
# =============================================================================

class StepType(str, Enum):
    """Type of process step."""
    EXECUTE = "execute"      # Execute action via agent
    CONDITION = "condition"  # Conditional branching
    COMPLETE = "complete"    # Process completion
    WAIT = "wait"            # Wait for event/time
    HUMAN = "human_checkpoint"  # Human approval


class ProcessStatus(str, Enum):
    """Status of process execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_HUMAN = "waiting_human"


class StepStatus(str, Enum):
    """Status of step execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# =============================================================================
# Process Metadata
# =============================================================================

class ProcessMetadata(BaseModel):
    """
    Process Card metadata — identification.

    Required fields: id, name, version
    """
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID (UUID)"
    )
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable name")
    version: str = Field(default="1.0", description="Version (semver)")
    description: str = Field(default="", description="Process description")
    author: str = Field(default="", description="Author")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp"
    )


# =============================================================================
# Retry Policy
# =============================================================================

class RetryPolicy(BaseModel):
    """Retry policy for step execution."""
    max_attempts: int = Field(default=3, ge=1, le=10, description="Max retry attempts")
    delay_seconds: float = Field(default=5.0, ge=0, description="Delay between retries")
    on_failure: str = Field(
        default="abort",
        description="Action on failure: abort, continue, escalate"
    )

    @field_validator("on_failure")
    @classmethod
    def validate_on_failure(cls, v):
        allowed = {"abort", "continue", "escalate"}
        if v not in allowed:
            raise ValueError(f"on_failure must be one of {allowed}")
        return v


# =============================================================================
# Step Specification
# =============================================================================

class StepSpec(BaseModel):
    """
    Process step specification.

    A step can be:
    - Execute action (action field)
    - Condition (condition field)
    - Complete (type="complete")
    - Wait (type="wait")
    """
    id: str = Field(..., min_length=1, max_length=50, description="Step ID (unique)")

    # Step type (inferred from fields if not explicit)
    type: Optional[StepType] = Field(None, description="Step type")

    # Execute action step
    action: Optional[str] = Field(None, description="Action name (capability)")
    params: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    output: Optional[str] = Field(None, description="Variable name to store result")

    # Retry policy
    retry: Optional[RetryPolicy] = Field(None, description="Retry policy")

    # Timeout
    timeout_seconds: int = Field(default=300, ge=1, le=3600, description="Step timeout")

    # Condition step
    condition: Optional[str] = Field(None, description="Condition expression")
    then: Optional[str] = Field(None, description="Step ID if condition is true")
    else_step: Optional[str] = Field(None, alias="else", description="Step ID if condition is false")

    # Next step (explicit)
    next: Optional[str] = Field(None, description="Next step ID")

    # Complete step
    status: Optional[str] = Field(None, description="Completion status")
    result: Optional[Any] = Field(None, description="Result variable or structure")

    # Wait step
    event: Optional[str] = Field(None, description="Event to wait for")
    duration: Optional[str] = Field(None, description="Duration to wait")

    # Human checkpoint
    message: Optional[str] = Field(None, description="Message for human")

    def get_type(self) -> StepType:
        """Infer step type from fields."""
        if self.type:
            return self.type
        if self.condition is not None:
            return StepType.CONDITION
        if self.action is not None:
            return StepType.EXECUTE
        if self.event is not None or self.duration is not None:
            return StepType.WAIT
        return StepType.COMPLETE


# =============================================================================
# Process Spec
# =============================================================================

class ProcessSpec(BaseModel):
    """Process specification — steps and variables."""
    variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Process variables"
    )
    steps: List[StepSpec] = Field(
        ...,
        min_length=1,
        description="Process steps (at least 1)"
    )

    @field_validator("steps")
    @classmethod
    def validate_unique_step_ids(cls, steps):
        """Ensure all step IDs are unique."""
        ids = [step.id for step in steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Step IDs must be unique")
        return steps


# =============================================================================
# Process Card (Complete)
# =============================================================================

class ProcessCard(BaseModel):
    """
    Complete Process Card according to SSOT specification.

    Structure:
        - metadata: WHO (identification)
        - spec: WHAT (steps and variables)

    Based on: docs/SSOT/PROCESS_CARD_SPEC_v1.0.md
    """
    metadata: ProcessMetadata = Field(..., description="Process identification")
    spec: ProcessSpec = Field(..., description="Process specification")

    def get_step(self, step_id: str) -> Optional[StepSpec]:
        """Get step by ID."""
        for step in self.spec.steps:
            if step.id == step_id:
                return step
        return None

    def get_first_step(self) -> Optional[StepSpec]:
        """Get first step."""
        if self.spec.steps:
            return self.spec.steps[0]
        return None

    def get_step_ids(self) -> List[str]:
        """Get all step IDs."""
        return [step.id for step in self.spec.steps]

    def validate_references(self) -> List[str]:
        """
        Validate that all step references (then, else, next) point to existing steps.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        step_ids = set(self.get_step_ids())

        for step in self.spec.steps:
            if step.then and step.then not in step_ids and step.then != "complete":
                errors.append(f"Step '{step.id}': 'then' references non-existent step '{step.then}'")
            if step.else_step and step.else_step not in step_ids and step.else_step != "complete":
                errors.append(f"Step '{step.id}': 'else' references non-existent step '{step.else_step}'")
            if step.next and step.next not in step_ids and step.next != "complete":
                errors.append(f"Step '{step.id}': 'next' references non-existent step '{step.next}'")

        return errors


# =============================================================================
# Process Instance (Runtime state)
# =============================================================================

class StepResult(BaseModel):
    """Result of a step execution."""
    step_id: str
    status: StepStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output: Optional[Any] = None
    error: Optional[str] = None
    attempts: int = 0


class ProcessInstance(BaseModel):
    """
    Runtime instance of a process.

    Created when a ProcessCard is executed.
    """
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Process instance ID"
    )
    card_id: str = Field(..., description="Process Card ID")
    card_name: str = Field(..., description="Process Card name")

    status: ProcessStatus = Field(default=ProcessStatus.PENDING)

    # Input parameters
    input_params: Dict[str, Any] = Field(default_factory=dict)

    # Runtime variables
    variables: Dict[str, Any] = Field(default_factory=dict)

    # Current step
    current_step_id: Optional[str] = None

    # Step results
    step_results: List[StepResult] = Field(default_factory=list)

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Final result
    result: Optional[Any] = None
    error: Optional[str] = None

    # Tracing
    trace_id: Optional[str] = None

    def get_step_result(self, step_id: str) -> Optional[StepResult]:
        """Get result for a specific step."""
        for result in self.step_results:
            if result.step_id == step_id:
                return result
        return None

    def add_step_result(self, result: StepResult) -> None:
        """Add or update step result."""
        for i, existing in enumerate(self.step_results):
            if existing.step_id == result.step_id:
                self.step_results[i] = result
                return
        self.step_results.append(result)

    def duration_seconds(self) -> Optional[float]:
        """Calculate process duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
