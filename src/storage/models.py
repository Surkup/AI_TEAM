"""
Storage Models — Pydantic and SQLAlchemy models for AI_TEAM Storage.

Based on: STORAGE_SPEC_v1.1.md

This module provides:
- ArtifactManifest (Pydantic) — validation and serialization
- ArtifactModel (SQLAlchemy) — database persistence
- Helper functions for ID generation

Ready-Made Solutions:
- Pydantic v2 for validation
- SQLAlchemy for ORM
- uuid for unique IDs
"""

import enum
import hashlib
import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, DateTime, Enum, Integer, JSON, String, Text
from sqlalchemy.ext.declarative import declarative_base

# =============================================================================
# Pydantic Models (for validation and API)
# =============================================================================


class ModelParams(BaseModel):
    """LLM model parameters for reproducibility."""
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)


class ArtifactContext(BaseModel):
    """AI-context for artifact creation (for reproducibility)."""

    model_config = {"protected_namespaces": ()}

    prompt_version: Optional[str] = Field(None, description="Agent prompt version")
    model_name: Optional[str] = Field(None, description="LLM model name")
    model_params: Optional[ModelParams] = Field(None, description="Generation parameters")
    input_artifacts: List[str] = Field(
        default_factory=list,
        description="Input artifact IDs (dependencies)"
    )
    execution_time_ms: Optional[int] = Field(None, ge=0, description="Execution time in ms")


class ArtifactManifest(BaseModel):
    """
    Artifact Manifest v1.1 — SSOT for artifact metadata.

    Based on: STORAGE_SPEC_v1.1.md Section 3.

    Invariant 8: artifact_id MUST contain UUID to prevent collisions.
    """

    # === Identification ===
    id: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^art_[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$",
        description="Unique artifact ID (art_ + UUID4)"
    )
    version: int = Field(ge=1, default=1, description="Artifact version")
    supersedes: Optional[str] = Field(None, description="ID of previous version")

    # === Process link ===
    trace_id: str = Field(min_length=1, description="Process trace ID")
    step_id: Optional[str] = Field(None, description="Process step ID")
    created_by: str = Field(min_length=1, description="Creator node_id")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")

    # === Typing ===
    artifact_type: str = Field(min_length=1, description="Artifact type")
    content_type: str = Field(
        default="application/json",
        description="MIME type"
    )

    # === Location ===
    uri: str = Field(min_length=1, description="File URI")
    size_bytes: int = Field(ge=0, description="Size in bytes")
    checksum: str = Field(
        min_length=1,
        pattern=r"^sha256:[a-f0-9]{64}$",
        description="SHA256 checksum"
    )

    # === Lifecycle ===
    status: Literal["uploading", "completed", "failed"] = Field(
        default="uploading",
        description="Artifact status"
    )
    retention: str = Field(default="infinite", description="Retention policy")

    # === Security ===
    owner: str = Field(min_length=1, description="Artifact owner")
    visibility: Literal["trace", "private", "public"] = Field(
        default="trace",
        description="Visibility level"
    )

    # === AI Context ===
    context: Optional[ArtifactContext] = Field(
        None,
        description="Creation context for reproducibility"
    )

    @field_validator('id')
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        """Validate artifact ID format (art_ + UUID4)."""
        if not v.startswith("art_"):
            raise ValueError("Artifact ID must start with 'art_'")
        return v

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "id": "art_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "version": 1,
                    "trace_id": "trace_xyz",
                    "step_id": "research",
                    "created_by": "agent.researcher.001",
                    "created_at": "2025-12-19T10:00:00Z",
                    "artifact_type": "research_report",
                    "content_type": "application/json",
                    "uri": "file:///.data/artifacts/trace_xyz/research_v1.json",
                    "size_bytes": 15234,
                    "checksum": "sha256:abc123def456789012345678901234567890123456789012345678901234abcd",
                    "status": "completed",
                    "retention": "infinite",
                    "owner": "agent.researcher.001",
                    "visibility": "trace",
                    "context": {
                        "model_name": "gpt-4o-mini",
                        "execution_time_ms": 3500
                    }
                }
            ]
        }


# =============================================================================
# SQLAlchemy Models (for database persistence)
# =============================================================================

Base = declarative_base()


class ArtifactStatus(enum.Enum):
    """Artifact lifecycle status."""
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"


class ArtifactVisibility(enum.Enum):
    """Artifact visibility level."""
    TRACE = "trace"
    PRIVATE = "private"
    PUBLIC = "public"


class ArtifactModel(Base):
    """
    SQLAlchemy model for Artifact Manifest.

    Based on: STORAGE_SPEC_v1.1.md Section 8.

    Invariant 1: Artifact exists IFF this record is committed.
    Invariant 2: Fields are immutable after creation (except status).
    """
    __tablename__ = "artifacts"

    # Primary key
    id = Column(String(100), primary_key=True)
    version = Column(Integer, nullable=False, default=1)

    # Process link
    trace_id = Column(String(100), nullable=False, index=True)
    step_id = Column(String(100), nullable=True)
    created_by = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Type
    artifact_type = Column(String(50), nullable=False, index=True)
    content_type = Column(String(100), nullable=False, default="application/json")

    # Location
    uri = Column(Text, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    checksum = Column(String(100), nullable=False, unique=True)

    # Lifecycle
    status = Column(Enum(ArtifactStatus), nullable=False, default=ArtifactStatus.UPLOADING)
    retention = Column(String(50), nullable=False, default="infinite")

    # Security
    owner = Column(String(100), nullable=False)
    visibility = Column(Enum(ArtifactVisibility), nullable=False, default=ArtifactVisibility.TRACE)

    # AI Context (JSON field)
    context = Column(JSON, nullable=True)

    # Versioning
    supersedes = Column(String(100), nullable=True)

    def to_manifest(self) -> ArtifactManifest:
        """Convert SQLAlchemy model to Pydantic ArtifactManifest."""
        context_data = None
        if self.context:
            context_data = ArtifactContext(**self.context)

        return ArtifactManifest(
            id=self.id,
            version=self.version,
            supersedes=self.supersedes,
            trace_id=self.trace_id,
            step_id=self.step_id,
            created_by=self.created_by,
            created_at=self.created_at,
            artifact_type=self.artifact_type,
            content_type=self.content_type,
            uri=self.uri,
            size_bytes=self.size_bytes,
            checksum=self.checksum,
            status=self.status.value,
            retention=self.retention,
            owner=self.owner,
            visibility=self.visibility.value,
            context=context_data,
        )

    @classmethod
    def from_manifest(cls, manifest: ArtifactManifest) -> "ArtifactModel":
        """Create SQLAlchemy model from Pydantic ArtifactManifest."""
        context_dict = None
        if manifest.context:
            context_dict = manifest.context.model_dump(exclude_none=True)

        return cls(
            id=manifest.id,
            version=manifest.version,
            supersedes=manifest.supersedes,
            trace_id=manifest.trace_id,
            step_id=manifest.step_id,
            created_by=manifest.created_by,
            created_at=manifest.created_at,
            artifact_type=manifest.artifact_type,
            content_type=manifest.content_type,
            uri=manifest.uri,
            size_bytes=manifest.size_bytes,
            checksum=manifest.checksum,
            status=ArtifactStatus(manifest.status),
            retention=manifest.retention,
            owner=manifest.owner,
            visibility=ArtifactVisibility(manifest.visibility),
            context=context_dict,
        )


# =============================================================================
# Helper Functions
# =============================================================================


def generate_artifact_id() -> str:
    """
    Generate unique artifact ID.

    Format: art_{uuid4}
    Example: art_a1b2c3d4-e5f6-7890-abcd-ef1234567890

    Invariant 8: Artifact ID Uniqueness
    """
    return f"art_{uuid.uuid4()}"


def compute_checksum(content: bytes) -> str:
    """
    Compute SHA256 checksum.

    Format: sha256:{hex}
    Example: sha256:abc123...
    """
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


# Standard artifact types (from STORAGE_SPEC_v1.1.md Section 3.2)
ARTIFACT_TYPES = {
    "research_report": "Research result",
    "idea": "Generated idea",
    "critique": "Critical analysis",
    "draft": "Text draft",
    "edited_draft": "Edited draft",
    "final": "Final result",
    "log": "Execution log",
    "intermediate": "Intermediate result",
}
