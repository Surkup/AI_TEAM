"""
Storage module for AI_TEAM.

Based on: STORAGE_SPEC_v1.1.md

Components:
- models: Pydantic and SQLAlchemy models for artifacts
- file_storage: fsspec-based file operations
- storage_service: Persistent Storage Service

Ready-Made Solutions:
- fsspec: File system abstraction
- SQLAlchemy: Database ORM
- Pydantic: Data validation
"""

from .models import (
    ArtifactManifest,
    ArtifactContext,
    ArtifactModel,
    ArtifactStatus,
    ArtifactVisibility,
    ModelParams,
    generate_artifact_id,
    compute_checksum,
    ARTIFACT_TYPES,
)
from .file_storage import FileStorage
from .storage_service import PersistentStorageService, StorageServiceHandler

__all__ = [
    # Models
    "ArtifactManifest",
    "ArtifactContext",
    "ArtifactModel",
    "ArtifactStatus",
    "ArtifactVisibility",
    "ModelParams",
    "generate_artifact_id",
    "compute_checksum",
    "ARTIFACT_TYPES",
    # File Storage
    "FileStorage",
    # Storage Service
    "PersistentStorageService",
    "StorageServiceHandler",
]
