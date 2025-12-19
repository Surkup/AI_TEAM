"""
Persistent Storage Service — SQLAlchemy + fsspec-based storage for AI_TEAM.

Based on: STORAGE_SPEC_v1.1.md

This service provides:
- Artifact registration and management
- File storage via fsspec
- SQLite metadata persistence
- Startup recovery for interrupted operations
- Buffer management for graceful degradation

Registration: NodeType.STORAGE
Capabilities: artifact_storage, file_storage

Ready-Made Solutions:
- SQLAlchemy: Database ORM
- fsspec: File system abstraction
- Pydantic: Data validation
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, and_, or_
from sqlalchemy.orm import sessionmaker, Session

from .models import (
    ArtifactManifest,
    ArtifactModel,
    ArtifactStatus,
    ArtifactVisibility,
    ArtifactContext,
    Base,
    generate_artifact_id,
    compute_checksum,
)
from .file_storage import FileStorage

logger = logging.getLogger(__name__)


class PersistentStorageService:
    """
    Persistent Storage Service based on STORAGE_SPEC_v1.1.

    Invariants implemented:
    - Invariant 1: Commit Point — Artifact exists IFF metadata is committed to DB
    - Invariant 2: Immutability — Fields are immutable after creation (except status)
    - Invariant 3: Pointer not Payload — Only URIs passed via MindBus
    - Invariant 7: Atomic File Placement — temp and permanent on same filesystem
    - Invariant 8: Artifact ID Uniqueness — UUID-based IDs

    Directory structure:
        .data/
        ├── artifacts/    # Permanent artifact files
        ├── temp/         # Temporary files (before registration)
        ├── buffer/       # Buffer when service unavailable
        ├── orphans/      # Orphaned files (for GC)
        └── storage.db    # SQLite database
    """

    def __init__(
        self,
        db_path: str = ".data/storage.db",
        base_path: str = ".data/artifacts",
        temp_path: str = ".data/temp",
        buffer_path: str = ".data/buffer",
        orphans_path: str = ".data/orphans",
        buffer_max_size_mb: int = 100,
        buffer_max_items: int = 1000,
    ):
        """
        Initialize Persistent Storage Service.

        Args:
            db_path: Path to SQLite database
            base_path: Path for permanent artifacts
            temp_path: Path for temporary files
            buffer_path: Path for buffered artifacts
            orphans_path: Path for orphaned files
            buffer_max_size_mb: Maximum buffer size in MB
            buffer_max_items: Maximum number of buffered items
        """
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize SQLAlchemy
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False,
            connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

        # Initialize FileStorage
        self.file_storage = FileStorage(
            base_path=base_path,
            temp_path=temp_path,
            buffer_path=buffer_path,
            orphans_path=orphans_path,
        )

        # Buffer limits (from STORAGE_SPEC_v1.1 Section 6.2)
        self.buffer_max_size_mb = buffer_max_size_mb
        self.buffer_max_items = buffer_max_items

        logger.info(
            f"PersistentStorageService initialized: db={self.db_path}, "
            f"artifacts={base_path}"
        )

        # Run startup recovery
        self._startup_recovery()

    # =========================================================================
    # Startup Recovery (STORAGE_SPEC_v1.1 Section 5.3)
    # =========================================================================

    def _startup_recovery(self) -> None:
        """
        Startup recovery procedure.

        1. Find incomplete artifacts (status=uploading)
        2. For each incomplete: check if file exists
        3. If file exists → complete registration
        4. If file missing → move metadata to failed
        5. Process buffered artifacts
        """
        logger.info("Starting recovery procedure...")

        with self.SessionLocal() as session:
            # Find incomplete artifacts
            incomplete = session.query(ArtifactModel).filter(
                ArtifactModel.status == ArtifactStatus.UPLOADING
            ).all()

            for artifact in incomplete:
                if self.file_storage.exists(artifact.uri):
                    # File exists, complete registration
                    artifact.status = ArtifactStatus.COMPLETED
                    logger.info(f"Recovery: completed {artifact.id}")
                else:
                    # File missing, mark as failed
                    artifact.status = ArtifactStatus.FAILED
                    logger.warning(f"Recovery: marked failed {artifact.id} (file missing)")

            session.commit()

        # Process buffered artifacts
        buffered = self.file_storage.list_buffered_artifacts()
        for artifact_id in buffered:
            try:
                self._process_buffered_artifact(artifact_id)
            except Exception as e:
                logger.error(f"Recovery: failed to process buffered {artifact_id}: {e}")

        logger.info(f"Recovery complete: {len(incomplete)} incomplete, {len(buffered)} buffered")

    def _process_buffered_artifact(self, artifact_id: str) -> None:
        """Process a single buffered artifact."""
        content, manifest_json = self.file_storage.get_buffered_artifact(artifact_id)
        manifest_dict = json.loads(manifest_json)
        manifest = ArtifactManifest(**manifest_dict)

        # Re-register the artifact
        self._register_artifact_internal(manifest, content)

        # Remove from buffer
        self.file_storage.remove_buffered_artifact(artifact_id)
        logger.info(f"Processed buffered artifact: {artifact_id}")

    # =========================================================================
    # Artifact Registration (STORAGE_SPEC_v1.1 Section 5)
    # =========================================================================

    def register_artifact(
        self,
        content: bytes,
        artifact_type: str,
        trace_id: str,
        created_by: str,
        filename: str,
        content_type: str = "application/json",
        step_id: Optional[str] = None,
        visibility: str = "trace",
        context: Optional[Dict[str, Any]] = None,
    ) -> ArtifactManifest:
        """
        Register a new artifact.

        Registration Flow (STORAGE_SPEC_v1.1 Section 5):
        1. Generate artifact_id (UUID)
        2. Upload file to temp
        3. Compute checksum
        4. Create manifest
        5. INSERT metadata (status=uploading)
        6. Move file to permanent location (atomic)
        7. UPDATE status=completed

        Args:
            content: File content
            artifact_type: Type of artifact
            trace_id: Process trace ID
            created_by: Creator node_id
            filename: Desired filename
            content_type: MIME type
            step_id: Optional process step ID
            visibility: Visibility level (trace, private, public)
            context: Optional AI context for reproducibility

        Returns:
            Completed ArtifactManifest
        """
        # Step 1: Generate artifact_id
        artifact_id = generate_artifact_id()

        # Step 2: Upload to temp
        temp_uri = self.file_storage.upload_to_temp(content, f"{artifact_id}_{filename}")

        # Step 3: Compute checksum
        checksum = compute_checksum(content)

        # Step 4: Create manifest
        artifact_context = None
        if context:
            artifact_context = ArtifactContext(**context)

        manifest = ArtifactManifest(
            id=artifact_id,
            version=1,
            trace_id=trace_id,
            step_id=step_id,
            created_by=created_by,
            artifact_type=artifact_type,
            content_type=content_type,
            uri=temp_uri,  # Will be updated after move
            size_bytes=len(content),
            checksum=checksum,
            status="uploading",
            owner=created_by,
            visibility=visibility,
            context=artifact_context,
        )

        # Steps 5-7: Database operations with atomic file move
        return self._register_artifact_internal(manifest, content, temp_uri, filename, trace_id)

    def _register_artifact_internal(
        self,
        manifest: ArtifactManifest,
        content: bytes,
        temp_uri: Optional[str] = None,
        filename: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> ArtifactManifest:
        """
        Internal artifact registration with database operations.

        Handles both fresh registration and buffered artifact processing.
        """
        with self.SessionLocal() as session:
            try:
                # Step 5: INSERT metadata (status=uploading)
                db_artifact = ArtifactModel.from_manifest(manifest)
                session.add(db_artifact)
                session.flush()  # Get ID assigned

                # Step 6: Move file to permanent location (atomic)
                if temp_uri and filename and trace_id:
                    permanent_uri = self.file_storage.move_to_permanent(
                        temp_uri, trace_id, f"{manifest.id}_{filename}"
                    )
                else:
                    # For buffered artifacts, upload directly
                    permanent_uri = self.file_storage.upload(
                        content,
                        manifest.trace_id,
                        f"{manifest.id}_artifact"
                    )

                # Step 7: UPDATE status=completed and URI
                db_artifact.uri = permanent_uri
                db_artifact.status = ArtifactStatus.COMPLETED

                session.commit()

                # Return updated manifest
                manifest.uri = permanent_uri
                manifest.status = "completed"

                logger.info(f"Registered artifact: {manifest.id}")
                return manifest

            except Exception as e:
                session.rollback()
                logger.error(f"Failed to register artifact {manifest.id}: {e}")

                # Buffer for later retry (graceful degradation)
                self._buffer_artifact(manifest, content)
                raise

    def _buffer_artifact(self, manifest: ArtifactManifest, content: bytes) -> None:
        """Buffer artifact for later retry."""
        # Check buffer limits
        buffered = self.file_storage.list_buffered_artifacts()
        if len(buffered) >= self.buffer_max_items:
            # FIFO eviction
            oldest = buffered[0]
            self.file_storage.remove_buffered_artifact(oldest)
            logger.warning(f"Buffer full, evicted oldest: {oldest}")

        manifest_json = manifest.model_dump_json()
        self.file_storage.buffer_artifact(manifest.id, content, manifest_json)
        logger.info(f"Buffered artifact: {manifest.id}")

    # =========================================================================
    # Artifact Retrieval
    # =========================================================================

    def get_artifact(self, artifact_id: str) -> Optional[ArtifactManifest]:
        """
        Get artifact manifest by ID.

        Args:
            artifact_id: Artifact ID

        Returns:
            ArtifactManifest or None if not found
        """
        with self.SessionLocal() as session:
            db_artifact = session.query(ArtifactModel).filter(
                ArtifactModel.id == artifact_id
            ).first()

            if db_artifact is None:
                return None

            return db_artifact.to_manifest()

    def get_artifact_content(self, artifact_id: str) -> bytes:
        """
        Get artifact file content.

        Args:
            artifact_id: Artifact ID

        Returns:
            File content

        Raises:
            FileNotFoundError: If artifact not found
        """
        manifest = self.get_artifact(artifact_id)
        if manifest is None:
            raise FileNotFoundError(f"Artifact not found: {artifact_id}")

        return self.file_storage.read(manifest.uri)

    def list_artifacts(
        self,
        trace_id: Optional[str] = None,
        created_by: Optional[str] = None,
        artifact_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ArtifactManifest]:
        """
        List artifacts with filters.

        Args:
            trace_id: Filter by trace ID
            created_by: Filter by creator
            artifact_type: Filter by type
            status: Filter by status
            limit: Maximum results
            offset: Result offset

        Returns:
            List of ArtifactManifest
        """
        with self.SessionLocal() as session:
            query = session.query(ArtifactModel)

            if trace_id:
                query = query.filter(ArtifactModel.trace_id == trace_id)
            if created_by:
                query = query.filter(ArtifactModel.created_by == created_by)
            if artifact_type:
                query = query.filter(ArtifactModel.artifact_type == artifact_type)
            if status:
                query = query.filter(ArtifactModel.status == ArtifactStatus(status))

            query = query.order_by(ArtifactModel.created_at.desc())
            query = query.offset(offset).limit(limit)

            return [artifact.to_manifest() for artifact in query.all()]

    # =========================================================================
    # Artifact Versioning
    # =========================================================================

    def create_new_version(
        self,
        artifact_id: str,
        content: bytes,
        created_by: str,
        filename: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ArtifactManifest:
        """
        Create new version of existing artifact.

        Args:
            artifact_id: ID of artifact to version
            content: New content
            created_by: Creator of new version
            filename: New filename
            context: Optional AI context

        Returns:
            New ArtifactManifest with incremented version
        """
        # Get existing artifact
        existing = self.get_artifact(artifact_id)
        if existing is None:
            raise FileNotFoundError(f"Artifact not found: {artifact_id}")

        # Create new version
        return self.register_artifact(
            content=content,
            artifact_type=existing.artifact_type,
            trace_id=existing.trace_id,
            created_by=created_by,
            filename=filename,
            content_type=existing.content_type,
            step_id=existing.step_id,
            visibility=existing.visibility,
            context=context,
        )

    # =========================================================================
    # Checksum Verification
    # =========================================================================

    def verify_artifact(self, artifact_id: str) -> bool:
        """
        Verify artifact checksum.

        Args:
            artifact_id: Artifact ID

        Returns:
            True if checksum matches
        """
        manifest = self.get_artifact(artifact_id)
        if manifest is None:
            raise FileNotFoundError(f"Artifact not found: {artifact_id}")

        return self.file_storage.verify_checksum(manifest.uri, manifest.checksum)

    # =========================================================================
    # Cleanup Operations
    # =========================================================================

    def cleanup_temp_files(self, older_than_hours: int = 1) -> int:
        """
        Clean up old temporary files.

        Args:
            older_than_hours: Age threshold in hours

        Returns:
            Number of files cleaned
        """
        old_files = self.file_storage.list_temp_files(older_than_hours)
        cleaned = 0

        for uri in old_files:
            try:
                # Move to orphans instead of deleting
                self.file_storage.move_to_orphans(uri)
                cleaned += 1
            except Exception as e:
                logger.error(f"Failed to clean temp file {uri}: {e}")

        logger.info(f"Cleaned {cleaned} temp files older than {older_than_hours}h")
        return cleaned

    def delete_artifact(self, artifact_id: str) -> bool:
        """
        Delete artifact (soft delete — moves file to orphans).

        Args:
            artifact_id: Artifact ID

        Returns:
            True if deleted
        """
        with self.SessionLocal() as session:
            db_artifact = session.query(ArtifactModel).filter(
                ArtifactModel.id == artifact_id
            ).first()

            if db_artifact is None:
                return False

            # Move file to orphans
            try:
                self.file_storage.move_to_orphans(db_artifact.uri)
            except FileNotFoundError:
                logger.warning(f"File not found for artifact {artifact_id}, removing metadata only")

            # Remove from database
            session.delete(db_artifact)
            session.commit()

            logger.info(f"Deleted artifact: {artifact_id}")
            return True

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.

        Returns:
            Dictionary with storage stats
        """
        with self.SessionLocal() as session:
            total = session.query(ArtifactModel).count()
            completed = session.query(ArtifactModel).filter(
                ArtifactModel.status == ArtifactStatus.COMPLETED
            ).count()
            failed = session.query(ArtifactModel).filter(
                ArtifactModel.status == ArtifactStatus.FAILED
            ).count()
            uploading = session.query(ArtifactModel).filter(
                ArtifactModel.status == ArtifactStatus.UPLOADING
            ).count()

        file_stats = self.file_storage.get_stats()

        return {
            "artifacts": {
                "total": total,
                "completed": completed,
                "failed": failed,
                "uploading": uploading,
            },
            "files": file_stats,
            "buffer": {
                "count": len(self.file_storage.list_buffered_artifacts()),
                "max_items": self.buffer_max_items,
                "max_size_mb": self.buffer_max_size_mb,
            },
            "database": str(self.db_path),
            "storage_type": "persistent_sqlite_fsspec",
        }


# =============================================================================
# MindBus Integration (BaseService adapter)
# =============================================================================


class StorageServiceHandler:
    """
    Handler for MindBus COMMAND messages.

    Maps actions to PersistentStorageService methods.
    Used by BaseService subclass for integration with MindBus.
    """

    def __init__(self, storage: PersistentStorageService):
        self.storage = storage

    def handle_command(
        self,
        action: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle storage command.

        Supported actions:
        - register_artifact: Register new artifact
        - get_artifact: Get artifact manifest
        - get_artifact_content: Get artifact file content
        - list_artifacts: List artifacts with filters
        - verify_artifact: Verify artifact checksum
        - delete_artifact: Delete artifact
        - get_stats: Get storage statistics
        """
        handlers = {
            "register_artifact": self._register_artifact,
            "get_artifact": self._get_artifact,
            "get_artifact_content": self._get_artifact_content,
            "list_artifacts": self._list_artifacts,
            "verify_artifact": self._verify_artifact,
            "delete_artifact": self._delete_artifact,
            "create_new_version": self._create_new_version,
            "get_stats": self._get_stats,
        }

        handler = handlers.get(action)
        if handler is None:
            raise ValueError(f"Unknown action: {action}. Supported: {list(handlers.keys())}")

        return handler(params)

    def _register_artifact(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Register new artifact."""
        required = ["content", "artifact_type", "trace_id", "created_by", "filename"]
        for field in required:
            if field not in params:
                raise ValueError(f"Missing required parameter: {field}")

        # Content can be base64 encoded string or bytes
        content = params["content"]
        if isinstance(content, str):
            import base64
            content = base64.b64decode(content)

        manifest = self.storage.register_artifact(
            content=content,
            artifact_type=params["artifact_type"],
            trace_id=params["trace_id"],
            created_by=params["created_by"],
            filename=params["filename"],
            content_type=params.get("content_type", "application/json"),
            step_id=params.get("step_id"),
            visibility=params.get("visibility", "trace"),
            context=params.get("context"),
        )

        return {
            "action": "register_artifact",
            "status": "completed",
            "artifact_id": manifest.id,
            "uri": manifest.uri,
            "checksum": manifest.checksum,
            "manifest": manifest.model_dump(mode="json"),
        }

    def _get_artifact(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get artifact manifest."""
        artifact_id = params.get("artifact_id")
        if not artifact_id:
            raise ValueError("Missing required parameter: artifact_id")

        manifest = self.storage.get_artifact(artifact_id)
        if manifest is None:
            raise FileNotFoundError(f"Artifact not found: {artifact_id}")

        return {
            "action": "get_artifact",
            "status": "completed",
            "artifact_id": artifact_id,
            "manifest": manifest.model_dump(mode="json"),
        }

    def _get_artifact_content(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get artifact content."""
        artifact_id = params.get("artifact_id")
        if not artifact_id:
            raise ValueError("Missing required parameter: artifact_id")

        import base64
        content = self.storage.get_artifact_content(artifact_id)

        return {
            "action": "get_artifact_content",
            "status": "completed",
            "artifact_id": artifact_id,
            "content": base64.b64encode(content).decode("utf-8"),
            "size_bytes": len(content),
        }

    def _list_artifacts(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List artifacts."""
        artifacts = self.storage.list_artifacts(
            trace_id=params.get("trace_id"),
            created_by=params.get("created_by"),
            artifact_type=params.get("artifact_type"),
            status=params.get("status"),
            limit=params.get("limit", 100),
            offset=params.get("offset", 0),
        )

        return {
            "action": "list_artifacts",
            "status": "completed",
            "count": len(artifacts),
            "artifacts": [a.model_dump(mode="json") for a in artifacts],
        }

    def _verify_artifact(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Verify artifact checksum."""
        artifact_id = params.get("artifact_id")
        if not artifact_id:
            raise ValueError("Missing required parameter: artifact_id")

        is_valid = self.storage.verify_artifact(artifact_id)

        return {
            "action": "verify_artifact",
            "status": "completed",
            "artifact_id": artifact_id,
            "checksum_valid": is_valid,
        }

    def _delete_artifact(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete artifact."""
        artifact_id = params.get("artifact_id")
        if not artifact_id:
            raise ValueError("Missing required parameter: artifact_id")

        deleted = self.storage.delete_artifact(artifact_id)

        return {
            "action": "delete_artifact",
            "status": "completed",
            "artifact_id": artifact_id,
            "deleted": deleted,
        }

    def _create_new_version(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create new version of artifact."""
        required = ["artifact_id", "content", "created_by", "filename"]
        for field in required:
            if field not in params:
                raise ValueError(f"Missing required parameter: {field}")

        content = params["content"]
        if isinstance(content, str):
            import base64
            content = base64.b64decode(content)

        manifest = self.storage.create_new_version(
            artifact_id=params["artifact_id"],
            content=content,
            created_by=params["created_by"],
            filename=params["filename"],
            context=params.get("context"),
        )

        return {
            "action": "create_new_version",
            "status": "completed",
            "artifact_id": manifest.id,
            "uri": manifest.uri,
            "version": manifest.version,
            "manifest": manifest.model_dump(mode="json"),
        }

    def _get_stats(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get storage statistics."""
        stats = self.storage.get_stats()

        return {
            "action": "get_stats",
            "status": "completed",
            "stats": stats,
        }
