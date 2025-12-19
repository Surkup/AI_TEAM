"""
Storage Service — In-memory file and artifact storage for AI_TEAM.

This service provides:
- file_storage: Save, read, list, delete files
- artifact_storage: Store task outputs and results

TODO: This is a TEMPORARY in-memory implementation.
      Future: Replace with persistent storage (S3, MinIO, local disk).

Registration: NodeType.STORAGE
Capabilities: file_storage, artifact_storage

See: docs/project/IMPLEMENTATION_ROADMAP.md Step 2.0.1
"""

import hashlib
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_service import BaseService
from src.registry.models import NodeType

logger = logging.getLogger(__name__)


class StorageService(BaseService):
    """
    In-memory Storage Service for AI_TEAM.

    Supported actions:
        - save_file: Store file content
        - read_file: Retrieve file content
        - list_files: List stored files
        - delete_file: Remove a file
        - file_exists: Check if file exists
        - get_file_info: Get file metadata
        - save_artifact: Store task artifact
        - get_artifact: Retrieve task artifact

    TODO: Replace with persistent storage backend.
    """

    def __init__(self, config_path: str = "config/services/storage.yaml"):
        super().__init__(config_path)

        # In-memory storage (TODO: replace with persistent backend)
        self._files: Dict[str, Dict[str, Any]] = {}  # path -> {content, metadata}
        self._artifacts: Dict[str, Dict[str, Any]] = {}  # artifact_id -> {data, metadata}

        # Storage configuration
        storage_config = self.config.get("storage", {})
        self._max_file_size = storage_config.get("max_file_size_bytes", 10 * 1024 * 1024)  # 10MB default
        self._max_files = storage_config.get("max_files", 10000)

        logger.info(
            f"StorageService initialized: max_file_size={self._max_file_size}, "
            f"max_files={self._max_files}"
        )

    @property
    def node_type(self) -> NodeType:
        """Return NodeType.STORAGE."""
        return NodeType.STORAGE

    def handle_command(
        self,
        action: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle storage commands.

        Args:
            action: Action to perform
            params: Action parameters
            context: Optional context

        Returns:
            Result dictionary
        """
        logger.info(f"Handling action: {action}")

        handlers = {
            "save_file": self._save_file,
            "read_file": self._read_file,
            "list_files": self._list_files,
            "delete_file": self._delete_file,
            "file_exists": self._file_exists,
            "get_file_info": self._get_file_info,
            "save_artifact": self._save_artifact,
            "get_artifact": self._get_artifact,
            "list_artifacts": self._list_artifacts,
            "get_stats": self._get_storage_stats,
        }

        handler = handlers.get(action)
        if handler is None:
            raise ValueError(f"Unknown action: {action}. Supported: {list(handlers.keys())}")

        return handler(params)

    # =========================================================================
    # File Operations
    # =========================================================================

    def _save_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save file to storage.

        Params:
            path: File path (virtual)
            content: File content (string or bytes as base64)
            content_type: MIME type (optional)
            overwrite: Allow overwriting existing file (default: True)
        """
        path = params.get("path")
        content = params.get("content")

        if not path:
            raise ValueError("Missing required parameter: path")
        if content is None:
            raise ValueError("Missing required parameter: content")

        # Check limits
        if len(self._files) >= self._max_files and path not in self._files:
            raise ValueError(f"Storage limit reached: max {self._max_files} files")

        content_size = len(content.encode("utf-8") if isinstance(content, str) else content)
        if content_size > self._max_file_size:
            raise ValueError(f"File too large: {content_size} > {self._max_file_size}")

        # Check overwrite
        overwrite = params.get("overwrite", True)
        if not overwrite and path in self._files:
            raise ValueError(f"File already exists: {path}")

        # Calculate hash
        content_bytes = content.encode("utf-8") if isinstance(content, str) else content
        content_hash = hashlib.sha256(content_bytes).hexdigest()

        # Store file
        now = datetime.utcnow()
        self._files[path] = {
            "content": content,
            "metadata": {
                "path": path,
                "size_bytes": content_size,
                "content_type": params.get("content_type", "text/plain"),
                "content_hash": content_hash,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        }

        logger.info(f"Saved file: {path} ({content_size} bytes)")

        return {
            "action": "save_file",
            "status": "completed",
            "path": path,
            "size_bytes": content_size,
            "content_hash": content_hash,
            "message": f"File saved: {path}",
        }

    def _read_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Read file from storage.

        Params:
            path: File path
        """
        path = params.get("path")
        if not path:
            raise ValueError("Missing required parameter: path")

        if path not in self._files:
            raise FileNotFoundError(f"File not found: {path}")

        file_data = self._files[path]

        return {
            "action": "read_file",
            "status": "completed",
            "path": path,
            "content": file_data["content"],
            "metadata": file_data["metadata"],
        }

    def _list_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        List files in storage.

        Params:
            prefix: Filter by path prefix (optional)
            limit: Max number of results (default: 100)
        """
        prefix = params.get("prefix", "")
        limit = params.get("limit", 100)

        files = []
        for path, file_data in self._files.items():
            if path.startswith(prefix):
                files.append(file_data["metadata"])
                if len(files) >= limit:
                    break

        return {
            "action": "list_files",
            "status": "completed",
            "prefix": prefix,
            "count": len(files),
            "files": files,
        }

    def _delete_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete file from storage.

        Params:
            path: File path
        """
        path = params.get("path")
        if not path:
            raise ValueError("Missing required parameter: path")

        if path not in self._files:
            raise FileNotFoundError(f"File not found: {path}")

        del self._files[path]

        logger.info(f"Deleted file: {path}")

        return {
            "action": "delete_file",
            "status": "completed",
            "path": path,
            "message": f"File deleted: {path}",
        }

    def _file_exists(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check if file exists."""
        path = params.get("path")
        if not path:
            raise ValueError("Missing required parameter: path")

        exists = path in self._files

        return {
            "action": "file_exists",
            "status": "completed",
            "path": path,
            "exists": exists,
        }

    def _get_file_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get file metadata without content."""
        path = params.get("path")
        if not path:
            raise ValueError("Missing required parameter: path")

        if path not in self._files:
            raise FileNotFoundError(f"File not found: {path}")

        return {
            "action": "get_file_info",
            "status": "completed",
            "path": path,
            "metadata": self._files[path]["metadata"],
        }

    # =========================================================================
    # Artifact Operations (for task results)
    # =========================================================================

    def _save_artifact(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save task artifact.

        Params:
            artifact_id: Unique artifact ID
            task_id: Related task ID (optional)
            process_id: Related process ID (optional)
            data: Artifact data (any JSON-serializable)
            artifact_type: Type of artifact (e.g., "result", "log", "intermediate")
        """
        artifact_id = params.get("artifact_id")
        if not artifact_id:
            raise ValueError("Missing required parameter: artifact_id")

        data = params.get("data")
        if data is None:
            raise ValueError("Missing required parameter: data")

        now = datetime.utcnow()
        self._artifacts[artifact_id] = {
            "data": data,
            "metadata": {
                "artifact_id": artifact_id,
                "task_id": params.get("task_id"),
                "process_id": params.get("process_id"),
                "artifact_type": params.get("artifact_type", "result"),
                "created_at": now.isoformat(),
            }
        }

        logger.info(f"Saved artifact: {artifact_id}")

        return {
            "action": "save_artifact",
            "status": "completed",
            "artifact_id": artifact_id,
            "message": f"Artifact saved: {artifact_id}",
        }

    def _get_artifact(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get artifact by ID.

        Params:
            artifact_id: Artifact ID
        """
        artifact_id = params.get("artifact_id")
        if not artifact_id:
            raise ValueError("Missing required parameter: artifact_id")

        if artifact_id not in self._artifacts:
            raise KeyError(f"Artifact not found: {artifact_id}")

        artifact = self._artifacts[artifact_id]

        return {
            "action": "get_artifact",
            "status": "completed",
            "artifact_id": artifact_id,
            "data": artifact["data"],
            "metadata": artifact["metadata"],
        }

    def _list_artifacts(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        List artifacts.

        Params:
            task_id: Filter by task ID (optional)
            process_id: Filter by process ID (optional)
            artifact_type: Filter by type (optional)
            limit: Max results (default: 100)
        """
        task_id = params.get("task_id")
        process_id = params.get("process_id")
        artifact_type = params.get("artifact_type")
        limit = params.get("limit", 100)

        artifacts = []
        for artifact_id, artifact in self._artifacts.items():
            meta = artifact["metadata"]

            # Apply filters
            if task_id and meta.get("task_id") != task_id:
                continue
            if process_id and meta.get("process_id") != process_id:
                continue
            if artifact_type and meta.get("artifact_type") != artifact_type:
                continue

            artifacts.append(meta)
            if len(artifacts) >= limit:
                break

        return {
            "action": "list_artifacts",
            "status": "completed",
            "count": len(artifacts),
            "artifacts": artifacts,
        }

    # =========================================================================
    # Stats
    # =========================================================================

    def _get_storage_stats(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get storage statistics."""
        total_file_size = sum(
            f["metadata"]["size_bytes"] for f in self._files.values()
        )

        return {
            "action": "get_stats",
            "status": "completed",
            "stats": {
                "files_count": len(self._files),
                "artifacts_count": len(self._artifacts),
                "total_file_size_bytes": total_file_size,
                "max_file_size_bytes": self._max_file_size,
                "max_files": self._max_files,
                "storage_type": "in-memory",  # TODO: Change when persistent
            },
            "message": "TODO: This is temporary in-memory storage",
        }


def main():
    """Run the Storage Service."""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    )

    service = StorageService()
    service.start()


if __name__ == "__main__":
    main()
