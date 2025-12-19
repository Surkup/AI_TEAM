"""
Memory Tools for AI_TEAM Agents.

Provides tools for reading and writing to agent's working memory.
Based on AGENT_SPEC_v1.0 Section 5.

Working Memory is a key-value store that persists during task execution.
Useful for:
- Storing intermediate results
- Caching research findings
- Passing data between agent phases
"""

import logging
import time
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool, ToolResult, ToolSecurityLevel

logger = logging.getLogger(__name__)


class WorkingMemory:
    """
    In-memory key-value store for agent's working memory.

    Thread-safe storage for intermediate results during task execution.

    This is the Short-Term Memory implementation from AGENT_SPEC Section 5.1.
    """

    def __init__(self, max_entries: int = 100):
        """
        Initialize working memory.

        Args:
            max_entries: Maximum number of entries to store
        """
        self._store: Dict[str, Any] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self.max_entries = max_entries

    def write(self, key: str, value: Any, metadata: Optional[Dict] = None) -> bool:
        """
        Write a value to memory.

        Args:
            key: Unique key for the value
            value: Value to store (any JSON-serializable type)
            metadata: Optional metadata (source, timestamp, etc.)

        Returns:
            True if successful
        """
        # Enforce max entries (LRU-like: remove oldest if full)
        if len(self._store) >= self.max_entries and key not in self._store:
            oldest_key = next(iter(self._store))
            del self._store[oldest_key]
            if oldest_key in self._metadata:
                del self._metadata[oldest_key]

        self._store[key] = value
        self._metadata[key] = {
            "created_at": time.time(),
            "updated_at": time.time(),
            **(metadata or {})
        }

        return True

    def read(self, key: str) -> Optional[Any]:
        """
        Read a value from memory.

        Args:
            key: Key to read

        Returns:
            Stored value or None if not found
        """
        return self._store.get(key)

    def read_with_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Read value with its metadata.

        Returns:
            Dict with 'value' and 'metadata' keys, or None
        """
        if key not in self._store:
            return None

        return {
            "value": self._store[key],
            "metadata": self._metadata.get(key, {})
        }

    def delete(self, key: str) -> bool:
        """
        Delete a key from memory.

        Returns:
            True if key existed and was deleted
        """
        if key in self._store:
            del self._store[key]
            if key in self._metadata:
                del self._metadata[key]
            return True
        return False

    def list_keys(self) -> List[str]:
        """List all keys in memory."""
        return list(self._store.keys())

    def clear(self) -> None:
        """Clear all memory."""
        self._store.clear()
        self._metadata.clear()

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        return key in self._store


# Global working memory instance (per-process)
# In production, could be replaced with Redis
_global_memory = WorkingMemory()


def get_working_memory() -> WorkingMemory:
    """Get the global working memory instance."""
    return _global_memory


def set_working_memory(memory: WorkingMemory) -> None:
    """Set a custom working memory instance."""
    global _global_memory
    _global_memory = memory


class MemoryReadTool(BaseTool):
    """
    Tool for reading from agent's working memory.

    Security Level: SAFE (read-only operation)

    Example:
        tool = MemoryReadTool()
        result = tool.execute(key="research_results")
        if result.success:
            data = result.data["value"]
    """

    name = "memory_read"
    description = (
        "Read a value from the agent's working memory by key. "
        "Use this to retrieve previously stored intermediate results, "
        "research findings, or data from earlier steps."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "The key to read from memory"
            },
            "default": {
                "description": "Default value to return if key not found",
                "default": None
            }
        },
        "required": ["key"]
    }
    security_level = ToolSecurityLevel.SAFE

    def __init__(self, memory: Optional[WorkingMemory] = None):
        """
        Initialize MemoryReadTool.

        Args:
            memory: WorkingMemory instance (uses global if not provided)
        """
        super().__init__()
        self._memory = memory

    @property
    def memory(self) -> WorkingMemory:
        """Get memory instance."""
        return self._memory or get_working_memory()

    def execute(
        self,
        key: str,
        default: Any = None,
        **kwargs
    ) -> ToolResult:
        """
        Read value from memory.

        Args:
            key: Key to read
            default: Default value if not found

        Returns:
            ToolResult with value
        """
        if not key or not key.strip():
            return ToolResult(
                success=False,
                error="Key cannot be empty"
            )

        result = self.memory.read_with_metadata(key)

        if result is None:
            return ToolResult(
                success=True,
                data={
                    "key": key,
                    "value": default,
                    "found": False
                },
                metadata={"message": f"Key '{key}' not found, returned default"}
            )

        return ToolResult(
            success=True,
            data={
                "key": key,
                "value": result["value"],
                "found": True,
                "metadata": result["metadata"]
            }
        )


class MemoryWriteTool(BaseTool):
    """
    Tool for writing to agent's working memory.

    Security Level: SAFE (only writes to agent's own memory)

    Example:
        tool = MemoryWriteTool()
        result = tool.execute(
            key="research_results",
            value={"topic": "AI", "findings": [...]}
        )
    """

    name = "memory_write"
    description = (
        "Write a value to the agent's working memory with a key. "
        "Use this to store intermediate results, research findings, "
        "or data that needs to be used in later steps."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "The key to store the value under"
            },
            "value": {
                "description": "The value to store (can be string, number, object, or array)"
            },
            "description": {
                "type": "string",
                "description": "Optional description of what this value represents"
            }
        },
        "required": ["key", "value"]
    }
    security_level = ToolSecurityLevel.SAFE

    def __init__(self, memory: Optional[WorkingMemory] = None):
        """
        Initialize MemoryWriteTool.

        Args:
            memory: WorkingMemory instance (uses global if not provided)
        """
        super().__init__()
        self._memory = memory

    @property
    def memory(self) -> WorkingMemory:
        """Get memory instance."""
        return self._memory or get_working_memory()

    def execute(
        self,
        key: str,
        value: Any,
        description: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Write value to memory.

        Args:
            key: Key to write
            value: Value to store
            description: Optional description

        Returns:
            ToolResult confirming write
        """
        if not key or not key.strip():
            return ToolResult(
                success=False,
                error="Key cannot be empty"
            )

        metadata = {}
        if description:
            metadata["description"] = description

        self.memory.write(key, value, metadata)

        return ToolResult(
            success=True,
            data={
                "key": key,
                "stored": True,
                "memory_size": len(self.memory)
            },
            metadata={
                "message": f"Value stored under key '{key}'",
                "description": description
            }
        )


class MemoryListTool(BaseTool):
    """
    Tool for listing all keys in working memory.

    Security Level: SAFE
    """

    name = "memory_list"
    description = (
        "List all keys currently stored in the agent's working memory. "
        "Use this to see what data has been saved in previous steps."
    )
    parameters_schema = {
        "type": "object",
        "properties": {},
        "required": []
    }
    security_level = ToolSecurityLevel.SAFE

    def __init__(self, memory: Optional[WorkingMemory] = None):
        super().__init__()
        self._memory = memory

    @property
    def memory(self) -> WorkingMemory:
        return self._memory or get_working_memory()

    def execute(self, **kwargs) -> ToolResult:
        """List all keys in memory."""
        keys = self.memory.list_keys()

        return ToolResult(
            success=True,
            data={
                "keys": keys,
                "count": len(keys)
            }
        )


class MemoryDeleteTool(BaseTool):
    """
    Tool for deleting a key from working memory.

    Security Level: SAFE
    """

    name = "memory_delete"
    description = (
        "Delete a key from the agent's working memory. "
        "Use this to clean up data that is no longer needed."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "The key to delete from memory"
            }
        },
        "required": ["key"]
    }
    security_level = ToolSecurityLevel.SAFE

    def __init__(self, memory: Optional[WorkingMemory] = None):
        super().__init__()
        self._memory = memory

    @property
    def memory(self) -> WorkingMemory:
        return self._memory or get_working_memory()

    def execute(self, key: str, **kwargs) -> ToolResult:
        """Delete key from memory."""
        if not key or not key.strip():
            return ToolResult(
                success=False,
                error="Key cannot be empty"
            )

        deleted = self.memory.delete(key)

        return ToolResult(
            success=True,
            data={
                "key": key,
                "deleted": deleted
            },
            metadata={
                "message": f"Key '{key}' {'deleted' if deleted else 'not found'}"
            }
        )
