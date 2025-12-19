"""
Web Search Tool for AI_TEAM Agents.

Ready-Made First approach:
- Primary: DuckDuckGo Search (free, no API key required)
- Alternative: Tavily (requires API key, better quality)

Based on AGENT_SPEC_v1.0 Section 4.2.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool, ToolResult, ToolSecurityLevel

logger = logging.getLogger(__name__)

# Try to import search libraries
try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    logger.warning("duckduckgo-search not installed. Run: pip install duckduckgo-search")

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    logger.debug("tavily-python not installed (optional)")


class WebSearchTool(BaseTool):
    """
    Web Search Tool using DuckDuckGo or Tavily.

    Searches the internet for information on a given query.
    Returns structured results with titles, URLs, and snippets.

    Security Level: SAFE (no sensitive operations)

    Example:
        tool = WebSearchTool()
        result = tool.execute(query="AI trends 2025", max_results=5)
        if result.success:
            for item in result.data:
                print(f"- {item['title']}: {item['url']}")
    """

    name = "web_search"
    description = (
        "Search the internet for information on a given query. "
        "Returns a list of relevant web pages with titles, URLs, and snippets. "
        "Use this tool when you need to find current information, facts, or research topics."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find information about"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (1-10)",
                "default": 5,
                "minimum": 1,
                "maximum": 10
            },
            "region": {
                "type": "string",
                "description": "Region for search results (e.g., 'ru-ru', 'en-us')",
                "default": "ru-ru"
            }
        },
        "required": ["query"]
    }
    security_level = ToolSecurityLevel.SAFE

    def __init__(
        self,
        provider: str = "duckduckgo",
        tavily_api_key: Optional[str] = None
    ):
        """
        Initialize WebSearchTool.

        Args:
            provider: Search provider ("duckduckgo" or "tavily")
            tavily_api_key: API key for Tavily (optional)
        """
        super().__init__()
        self.provider = provider
        self.tavily_api_key = tavily_api_key

        # Validate provider availability
        if provider == "duckduckgo" and not DDGS_AVAILABLE:
            logger.warning("DuckDuckGo not available, will fail on execute")
        elif provider == "tavily" and not TAVILY_AVAILABLE:
            logger.warning("Tavily not available, will fail on execute")

    def execute(
        self,
        query: str,
        max_results: int = 5,
        region: str = "ru-ru",
        **kwargs
    ) -> ToolResult:
        """
        Execute web search.

        Args:
            query: Search query
            max_results: Maximum results to return (1-10)
            region: Region for results

        Returns:
            ToolResult with list of search results
        """
        start_time = time.time()

        # Validate
        if not query or not query.strip():
            return ToolResult(
                success=False,
                error="Query cannot be empty"
            )

        max_results = min(max(1, max_results), 10)  # Clamp to 1-10

        try:
            if self.provider == "tavily" and TAVILY_AVAILABLE and self.tavily_api_key:
                results = self._search_tavily(query, max_results)
            elif DDGS_AVAILABLE:
                results = self._search_duckduckgo(query, max_results, region)
            else:
                return ToolResult(
                    success=False,
                    error="No search provider available. Install duckduckgo-search: pip install duckduckgo-search"
                )

            execution_time = time.time() - start_time

            return ToolResult(
                success=True,
                data=results,
                metadata={
                    "query": query,
                    "provider": self.provider if self.provider == "tavily" else "duckduckgo",
                    "results_count": len(results),
                    "execution_time_ms": round(execution_time * 1000, 2)
                }
            )

        except Exception as e:
            logger.error(f"WebSearchTool failed: {e}")
            return ToolResult(
                success=False,
                error=f"Search failed: {str(e)}"
            )

    def _search_duckduckgo(
        self,
        query: str,
        max_results: int,
        region: str
    ) -> List[Dict[str, Any]]:
        """Search using DuckDuckGo."""
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(
                query,
                region=region,
                max_results=max_results
            ))

        # Normalize results format
        results = []
        for r in raw_results:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", r.get("link", "")),
                "snippet": r.get("body", r.get("snippet", "")),
                "source": "duckduckgo"
            })

        return results

    def _search_tavily(
        self,
        query: str,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Search using Tavily."""
        client = TavilyClient(api_key=self.tavily_api_key)
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic"
        )

        # Normalize results format
        results = []
        for r in response.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
                "score": r.get("score"),
                "source": "tavily"
            })

        return results

    async def aexecute(
        self,
        query: str,
        max_results: int = 5,
        region: str = "ru-ru",
        **kwargs
    ) -> ToolResult:
        """
        Async web search.

        Currently wraps sync version. Could be optimized with aiohttp.
        """
        # For MVP, use sync version
        # TODO: Implement true async with aiohttp
        return self.execute(query=query, max_results=max_results, region=region, **kwargs)


class WebFetchTool(BaseTool):
    """
    Web Fetch Tool - fetches content from a URL.

    Downloads and extracts text content from web pages.

    Security Level: SAFE (read-only operation)
    """

    name = "web_fetch"
    description = (
        "Fetch and extract text content from a web page URL. "
        "Returns the main text content of the page. "
        "Use this when you need to read the full content of a specific web page."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the web page to fetch"
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum length of extracted text (characters)",
                "default": 10000
            }
        },
        "required": ["url"]
    }
    security_level = ToolSecurityLevel.SAFE

    def __init__(self, timeout: int = 30):
        """
        Initialize WebFetchTool.

        Args:
            timeout: Request timeout in seconds
        """
        super().__init__()
        self.timeout = timeout

    def execute(
        self,
        url: str,
        max_length: int = 10000,
        **kwargs
    ) -> ToolResult:
        """
        Fetch content from URL.

        Args:
            url: Web page URL
            max_length: Maximum text length to return

        Returns:
            ToolResult with extracted text content
        """
        start_time = time.time()

        # Validate URL
        if not url or not url.strip():
            return ToolResult(
                success=False,
                error="URL cannot be empty"
            )

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            import requests
            from bs4 import BeautifulSoup

            # Fetch page
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; AI_TEAM Bot/1.0)"
            }
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()

            # Extract text
            text = soup.get_text(separator="\n", strip=True)

            # Clean up whitespace
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            text = "\n".join(lines)

            # Truncate if needed
            if len(text) > max_length:
                text = text[:max_length] + "... [truncated]"

            execution_time = time.time() - start_time

            return ToolResult(
                success=True,
                data={
                    "url": url,
                    "title": soup.title.string if soup.title else "",
                    "content": text,
                    "content_length": len(text)
                },
                metadata={
                    "status_code": response.status_code,
                    "execution_time_ms": round(execution_time * 1000, 2)
                }
            )

        except ImportError:
            return ToolResult(
                success=False,
                error="Required libraries not installed. Run: pip install requests beautifulsoup4"
            )
        except requests.RequestException as e:
            return ToolResult(
                success=False,
                error=f"Failed to fetch URL: {str(e)}"
            )
        except Exception as e:
            logger.error(f"WebFetchTool failed: {e}")
            return ToolResult(
                success=False,
                error=f"Failed to process page: {str(e)}"
            )
