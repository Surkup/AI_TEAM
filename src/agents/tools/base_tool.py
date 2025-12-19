"""
Base Tool class for AI_TEAM Agents.

Implements Tool Interface from AGENT_SPEC_v1.0 Section 4.4.

Ready-Made First: Uses OpenAI Function Calling format.
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ToolSecurityLevel(str, Enum):
    """Security levels for tools (AGENT_SPEC Section 4.5)."""
    SAFE = "safe"              # No restrictions (web_search, memory_*)
    MODERATE = "moderate"      # Requires whitelist (file_read)
    RESTRICTED = "restricted"  # Requires explicit permission (file_write, api_call)
    CRITICAL = "critical"      # Requires human-in-the-loop (code_execute, shell)


class ToolResult(BaseModel):
    """
    Result of tool execution.

    Standardized format for all tool outputs.
    """
    success: bool = Field(..., description="Whether the tool executed successfully")
    data: Any = Field(default=None, description="Result data from the tool")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (execution_time, source, etc.)"
    )

    def __str__(self) -> str:
        if self.success:
            return f"ToolResult(success=True, data={str(self.data)[:100]}...)"
        return f"ToolResult(success=False, error={self.error})"


class BaseTool(ABC):
    """
    Base class for all Tools.

    Implements Tool Interface from AGENT_SPEC_v1.0 Section 4.4.

    Subclasses must implement:
        - execute(**kwargs) -> ToolResult

    Attributes:
        name: Tool name (for LLM function calling)
        description: Tool description (for LLM)
        parameters_schema: JSON Schema for parameters
        security_level: Security classification
    """

    name: str
    description: str
    parameters_schema: Dict[str, Any]
    security_level: ToolSecurityLevel = ToolSecurityLevel.SAFE

    def __init__(self):
        """Initialize the tool."""
        self._validate_schema()

    def _validate_schema(self) -> None:
        """Validate that tool has required attributes."""
        required = ["name", "description", "parameters_schema"]
        for attr in required:
            if not hasattr(self, attr) or getattr(self, attr) is None:
                raise ValueError(f"Tool must have '{attr}' attribute defined")

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult with success/failure and data
        """
        pass

    async def aexecute(self, **kwargs) -> ToolResult:
        """
        Async version of execute.

        Default implementation calls sync execute.
        Override for true async behavior.
        """
        return self.execute(**kwargs)

    def to_openai_schema(self) -> Dict[str, Any]:
        """
        Convert to OpenAI Function Calling format.

        Returns:
            Dict compatible with OpenAI tools parameter
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema
            }
        }

    def to_anthropic_schema(self) -> Dict[str, Any]:
        """
        Convert to Anthropic Tool Use format.

        Returns:
            Dict compatible with Anthropic tools parameter
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters_schema
        }

    def validate_params(self, **kwargs) -> bool:
        """
        Validate parameters against schema.

        Basic validation - checks required fields.
        """
        schema = self.parameters_schema
        required = schema.get("required", [])

        for field in required:
            if field not in kwargs:
                logger.warning(f"Tool {self.name}: missing required field '{field}'")
                return False

        return True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}', security={self.security_level.value})>"


class ToolRegistry:
    """
    Registry for managing available tools.

    Provides:
    - Tool registration and lookup
    - Security filtering
    - Schema generation for LLM
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered, overwriting")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} (security={tool.security_level.value})")

    def unregister(self, name: str) -> None:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool: {name}")

    def get(self, name: str) -> Optional[BaseTool]:
        """Get tool by name."""
        return self._tools.get(name)

    def get_all(self) -> List[BaseTool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_by_security_level(
        self,
        max_level: ToolSecurityLevel = ToolSecurityLevel.MODERATE
    ) -> List[BaseTool]:
        """
        Get tools up to specified security level.

        Args:
            max_level: Maximum security level to include

        Returns:
            List of tools with security level <= max_level
        """
        level_order = [
            ToolSecurityLevel.SAFE,
            ToolSecurityLevel.MODERATE,
            ToolSecurityLevel.RESTRICTED,
            ToolSecurityLevel.CRITICAL
        ]

        max_index = level_order.index(max_level)
        allowed_levels = set(level_order[:max_index + 1])

        return [
            tool for tool in self._tools.values()
            if tool.security_level in allowed_levels
        ]

    def get_openai_schemas(
        self,
        tool_names: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get OpenAI schemas for specified tools (or all).

        Args:
            tool_names: List of tool names, or None for all

        Returns:
            List of OpenAI function schemas
        """
        if tool_names is None:
            tools = self._tools.values()
        else:
            tools = [self._tools[n] for n in tool_names if n in self._tools]

        return [tool.to_openai_schema() for tool in tools]

    def execute(self, name: str, **kwargs) -> ToolResult:
        """
        Execute a tool by name.

        Args:
            name: Tool name
            **kwargs: Tool parameters

        Returns:
            ToolResult
        """
        tool = self.get(name)
        if tool is None:
            return ToolResult(
                success=False,
                error=f"Tool '{name}' not found"
            )

        try:
            return tool.execute(**kwargs)
        except Exception as e:
            logger.error(f"Tool {name} execution failed: {e}")
            return ToolResult(
                success=False,
                error=str(e)
            )

    async def aexecute(self, name: str, **kwargs) -> ToolResult:
        """
        Async execute a tool by name.
        """
        tool = self.get(name)
        if tool is None:
            return ToolResult(
                success=False,
                error=f"Tool '{name}' not found"
            )

        try:
            return await tool.aexecute(**kwargs)
        except Exception as e:
            logger.error(f"Tool {name} async execution failed: {e}")
            return ToolResult(
                success=False,
                error=str(e)
            )

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __repr__(self) -> str:
        return f"<ToolRegistry(tools={list(self._tools.keys())})>"
