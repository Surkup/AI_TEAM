"""
Tools Framework for AI_TEAM Agents.

Provides standard tools that agents can use to interact with the world.
Based on AGENT_SPEC_v1.0 (docs/SSOT/AGENT_SPEC_v1.0.md).

Ready-Made First: Uses OpenAI Function Calling format for tool schemas.

Available Tools:
- WebSearchTool: Search the internet (Tavily/DuckDuckGo)
- WebFetchTool: Fetch content from URLs
- MemoryReadTool: Read from agent's working memory
- MemoryWriteTool: Write to agent's working memory

Usage:
    from src.agents.tools import WebSearchTool, ToolRegistry

    # Create tool
    search_tool = WebSearchTool()

    # Execute
    result = await search_tool.execute(query="AI trends 2025")

    # Get OpenAI schema for LLM
    schema = search_tool.to_openai_schema()
"""

from .base_tool import BaseTool, ToolResult, ToolRegistry, ToolSecurityLevel
from .web_search import WebSearchTool, WebFetchTool
from .memory_tools import (
    MemoryReadTool,
    MemoryWriteTool,
    MemoryListTool,
    MemoryDeleteTool,
    WorkingMemory,
    get_working_memory,
    set_working_memory,
)

__all__ = [
    # Base
    "BaseTool",
    "ToolResult",
    "ToolRegistry",
    "ToolSecurityLevel",
    # Web Tools
    "WebSearchTool",
    "WebFetchTool",
    # Memory Tools
    "MemoryReadTool",
    "MemoryWriteTool",
    "MemoryListTool",
    "MemoryDeleteTool",
    "WorkingMemory",
    "get_working_memory",
    "set_working_memory",
]
