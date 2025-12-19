"""
FileStorage — fsspec-based file storage abstraction for AI_TEAM.

Based on: STORAGE_SPEC_v1.1.md Section 7.

Ready-Made Solutions:
- fsspec: File system abstraction (local, S3, GCS, etc.)
- hashlib: SHA256 checksums

Invariants:
- Invariant 3: Pointer not Payload — files stored directly, only URIs via MindBus
- Invariant 7: Atomic File Placement — temp and permanent on same filesystem
"""

import hashlib
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import fsspec

logger = logging.getLogger(__name__)


class FileStorage:
    """
    File storage abstraction using fsspec.

    MVP: Local filesystem
    Production: MinIO/S3 via fsspec

    Directory structure:
        .data/
        ├── artifacts/    # Registered artifacts (permanent)
        ├── temp/         # Temporary files (before registration)
        ├── buffer/       # Buffer when Storage Service is down
        └── orphans/      # Orphaned files (for GC)
    """

    def __init__(
        self,
        base_path: str = ".data/artifacts",
        temp_path: str = ".data/temp",
        buffer_path: str = ".data/buffer",
        orphans_path: str = ".data/orphans",
    ):
        """
        Initialize FileStorage.

        Args:
            base_path: Path for permanent artifacts
            temp_path: Path for temporary files
            buffer_path: Path for buffered artifacts
            orphans_path: Path for orphaned files
        """
        self.base_path = Path(base_path).resolve()
        self.temp_path = Path(temp_path).resolve()
        self.buffer_path = Path(buffer_path).resolve()
        self.orphans_path = Path(orphans_path).resolve()

        # MVP: local filesystem
        self.fs = fsspec.filesystem("file")

        # Ensure directories exist
        self._ensure_directories()

        # Invariant 7: Verify same filesystem for atomic moves
        self._verify_same_filesystem()

        logger.info(
            f"FileStorage initialized: base={self.base_path}, temp={self.temp_path}"
        )

    def _ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        for path in [self.base_path, self.temp_path, self.buffer_path, self.orphans_path]:
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory: {path}")

    def _verify_same_filesystem(self) -> None:
        """
        Verify that temp and base paths are on the same filesystem.

        Invariant 7: Atomic File Placement
        os.rename() is atomic only within the same filesystem.
        """
        temp_stat = os.stat(self.temp_path)
        base_stat = os.stat(self.base_path)

        if temp_stat.st_dev != base_stat.st_dev:
            logger.warning(
                f"WARNING: temp ({self.temp_path}) and base ({self.base_path}) "
                "are on different filesystems. Atomic moves not guaranteed!"
            )

    # =========================================================================
    # Core Operations
    # =========================================================================

    def upload_to_temp(self, content: bytes, filename: str) -> str:
        """
        Upload file to temporary storage.

        Args:
            content: File content
            filename: Desired filename

        Returns:
            Temporary file URI
        """
        temp_file = self.temp_path / filename
        temp_file.parent.mkdir(parents=True, exist_ok=True)

        with self.fs.open(str(temp_file), "wb") as f:
            f.write(content)

        uri = f"file://{temp_file}"
        logger.debug(f"Uploaded to temp: {uri} ({len(content)} bytes)")
        return uri

    def move_to_permanent(self, temp_uri: str, trace_id: str, filename: str) -> str:
        """
        Move file from temp to permanent storage.

        Invariant 7: Uses os.rename() for atomic operation on same filesystem.

        Args:
            temp_uri: Temporary file URI
            trace_id: Process trace ID (used for directory structure)
            filename: Final filename

        Returns:
            Permanent file URI
        """
        temp_path = Path(temp_uri.replace("file://", ""))

        if not temp_path.exists():
            raise FileNotFoundError(f"Temp file not found: {temp_uri}")

        # Create permanent path: .data/artifacts/{trace_id}/{filename}
        permanent_dir = self.base_path / trace_id
        permanent_dir.mkdir(parents=True, exist_ok=True)
        permanent_path = permanent_dir / filename

        # Atomic move (same filesystem)
        os.rename(temp_path, permanent_path)

        uri = f"file://{permanent_path}"
        logger.debug(f"Moved to permanent: {uri}")
        return uri

    def upload(self, content: bytes, trace_id: str, filename: str) -> str:
        """
        Upload file directly to permanent storage.

        Args:
            content: File content
            trace_id: Process trace ID
            filename: Filename

        Returns:
            File URI
        """
        permanent_dir = self.base_path / trace_id
        permanent_dir.mkdir(parents=True, exist_ok=True)
        path = permanent_dir / filename

        with self.fs.open(str(path), "wb") as f:
            f.write(content)

        uri = f"file://{path}"
        logger.debug(f"Uploaded: {uri} ({len(content)} bytes)")
        return uri

    def read(self, uri: str) -> bytes:
        """
        Read file content.

        Args:
            uri: File URI

        Returns:
            File content
        """
        path = uri.replace("file://", "")

        if not self.fs.exists(path):
            raise FileNotFoundError(f"File not found: {uri}")

        with self.fs.open(path, "rb") as f:
            return f.read()

    def exists(self, uri: str) -> bool:
        """
        Check if file exists.

        Args:
            uri: File URI

        Returns:
            True if file exists
        """
        path = uri.replace("file://", "")
        return self.fs.exists(path)

    def delete(self, uri: str) -> bool:
        """
        Delete file.

        Args:
            uri: File URI

        Returns:
            True if deleted, False if not found
        """
        path = uri.replace("file://", "")

        if not self.fs.exists(path):
            return False

        self.fs.rm(path)
        logger.debug(f"Deleted: {uri}")
        return True

    def get_size(self, uri: str) -> int:
        """
        Get file size in bytes.

        Args:
            uri: File URI

        Returns:
            Size in bytes
        """
        path = uri.replace("file://", "")
        return self.fs.size(path)

    # =========================================================================
    # Checksum
    # =========================================================================

    @staticmethod
    def compute_checksum(content: bytes) -> str:
        """
        Compute SHA256 checksum.

        Format: sha256:{hex}

        Args:
            content: File content

        Returns:
            Checksum string
        """
        return f"sha256:{hashlib.sha256(content).hexdigest()}"

    def verify_checksum(self, uri: str, expected_checksum: str) -> bool:
        """
        Verify file checksum.

        Args:
            uri: File URI
            expected_checksum: Expected checksum

        Returns:
            True if checksums match
        """
        content = self.read(uri)
        actual_checksum = self.compute_checksum(content)
        return actual_checksum == expected_checksum

    # =========================================================================
    # Buffer Operations (for graceful degradation)
    # =========================================================================

    def buffer_artifact(self, artifact_id: str, content: bytes, manifest_json: str) -> str:
        """
        Buffer artifact when Storage Service is unavailable.

        Args:
            artifact_id: Artifact ID
            content: File content
            manifest_json: Manifest as JSON string

        Returns:
            Buffer file URI
        """
        buffer_dir = self.buffer_path / artifact_id
        buffer_dir.mkdir(parents=True, exist_ok=True)

        # Save content
        content_path = buffer_dir / "content.bin"
        with self.fs.open(str(content_path), "wb") as f:
            f.write(content)

        # Save manifest
        manifest_path = buffer_dir / "manifest.json"
        with self.fs.open(str(manifest_path), "w") as f:
            f.write(manifest_json)

        uri = f"file://{buffer_dir}"
        logger.info(f"Buffered artifact: {artifact_id}")
        return uri

    def list_buffered_artifacts(self) -> List[str]:
        """
        List buffered artifact IDs.

        Returns:
            List of artifact IDs in buffer
        """
        if not self.buffer_path.exists():
            return []

        return [d.name for d in self.buffer_path.iterdir() if d.is_dir()]

    def get_buffered_artifact(self, artifact_id: str) -> tuple:
        """
        Get buffered artifact content and manifest.

        Args:
            artifact_id: Artifact ID

        Returns:
            Tuple of (content bytes, manifest json string)
        """
        buffer_dir = self.buffer_path / artifact_id

        content_path = buffer_dir / "content.bin"
        manifest_path = buffer_dir / "manifest.json"

        if not content_path.exists() or not manifest_path.exists():
            raise FileNotFoundError(f"Buffered artifact not found: {artifact_id}")

        with self.fs.open(str(content_path), "rb") as f:
            content = f.read()

        with self.fs.open(str(manifest_path), "r") as f:
            manifest_json = f.read()

        return content, manifest_json

    def remove_buffered_artifact(self, artifact_id: str) -> bool:
        """
        Remove buffered artifact after successful registration.

        Args:
            artifact_id: Artifact ID

        Returns:
            True if removed
        """
        buffer_dir = self.buffer_path / artifact_id

        if not buffer_dir.exists():
            return False

        shutil.rmtree(buffer_dir)
        logger.debug(f"Removed buffered artifact: {artifact_id}")
        return True

    # =========================================================================
    # Orphan Handling
    # =========================================================================

    def move_to_orphans(self, uri: str) -> str:
        """
        Move file to orphans directory.

        Args:
            uri: File URI

        Returns:
            New URI in orphans directory
        """
        path = Path(uri.replace("file://", ""))

        if not path.exists():
            raise FileNotFoundError(f"File not found: {uri}")

        timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
        orphan_name = f"orphan_{timestamp}_{path.name}"
        orphan_path = self.orphans_path / orphan_name

        os.rename(path, orphan_path)

        new_uri = f"file://{orphan_path}"
        logger.info(f"Moved to orphans: {uri} -> {new_uri}")
        return new_uri

    def list_temp_files(self, older_than_hours: int = 1) -> List[str]:
        """
        List temporary files older than specified hours.

        Args:
            older_than_hours: Age threshold in hours

        Returns:
            List of temp file URIs
        """
        cutoff = datetime.utcnow().timestamp() - (older_than_hours * 3600)
        old_files = []

        for root, dirs, files in os.walk(self.temp_path):
            for file in files:
                path = Path(root) / file
                if path.stat().st_mtime < cutoff:
                    old_files.append(f"file://{path}")

        return old_files

    # =========================================================================
    # Stats
    # =========================================================================

    def get_stats(self) -> dict:
        """
        Get storage statistics.

        Returns:
            Dictionary with storage stats
        """
        def count_files_and_size(path: Path) -> tuple:
            if not path.exists():
                return 0, 0
            total_size = 0
            count = 0
            for root, dirs, files in os.walk(path):
                for file in files:
                    file_path = Path(root) / file
                    total_size += file_path.stat().st_size
                    count += 1
            return count, total_size

        artifacts_count, artifacts_size = count_files_and_size(self.base_path)
        temp_count, temp_size = count_files_and_size(self.temp_path)
        buffer_count, buffer_size = count_files_and_size(self.buffer_path)
        orphans_count, orphans_size = count_files_and_size(self.orphans_path)

        return {
            "artifacts": {"count": artifacts_count, "size_bytes": artifacts_size},
            "temp": {"count": temp_count, "size_bytes": temp_size},
            "buffer": {"count": buffer_count, "size_bytes": buffer_size},
            "orphans": {"count": orphans_count, "size_bytes": orphans_size},
            "base_path": str(self.base_path),
            "storage_type": "local_filesystem",
        }
