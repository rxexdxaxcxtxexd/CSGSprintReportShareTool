"""
MCP Memory Server Client Wrapper

This module provides a wrapper around the MCP memory server tools,
handling connection management, error recovery, and token estimation.

The MCP memory server stores a knowledge graph with entities and relations,
persisted in a SQLite database at ~/.claude-memory/

Author: Context-Aware Memory System
Date: 2025-12-23
"""

import json
import subprocess
import time
from typing import Dict, List, Optional, Any
from pathlib import Path


class MemoryClient:
    """
    Wrapper for MCP memory server operations

    Provides high-level methods for querying and updating the memory graph,
    with automatic retry logic and graceful error handling.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize memory client

        Args:
            config: Configuration dict with optional keys:
                - connection_timeout_seconds: int (default: 5)
                - query_timeout_seconds: int (default: 3)
                - retry_attempts: int (default: 2)
                - retry_backoff_seconds: int (default: 1)
        """
        self.config = config or {}
        self.connection_timeout = self.config.get('connection_timeout_seconds', 5)
        self.query_timeout = self.config.get('query_timeout_seconds', 3)
        self.retry_attempts = self.config.get('retry_attempts', 2)
        self.retry_backoff = self.config.get('retry_backoff_seconds', 1)

        # Cache availability check result for performance
        self._is_available_cache: Optional[bool] = None
        self._is_available_cache_time: float = 0
        self._is_available_cache_ttl: int = 60  # 60 seconds

    def is_available(self) -> bool:
        """
        Check if MCP memory server is available

        Uses cached result if within TTL (60 seconds).

        Returns:
            True if server is reachable, False otherwise
        """
        # Check cache
        now = time.time()
        if self._is_available_cache is not None and \
           (now - self._is_available_cache_time) < self._is_available_cache_ttl:
            return self._is_available_cache

        # Test connection by trying to read graph
        try:
            result = self.read_graph()
            available = result is not None
        except Exception:
            available = False

        # Cache result
        self._is_available_cache = available
        self._is_available_cache_time = now

        return available

    def search_nodes(self, query: str, limit: int = 10) -> Optional[Dict[str, Any]]:
        """
        Search memory graph by query string

        Args:
            query: Search query (supports keywords, entity names, etc.)
            limit: Maximum number of results (not enforced by MCP, for documentation)

        Returns:
            Dict with 'entities' and 'relations' keys, or None on error

        Example:
            result = client.search_nodes("authentication decision")
            # Returns: {"entities": [...], "relations": [...]}
        """
        return self._retry_operation(
            lambda: self._call_mcp_tool('search_nodes', {'query': query}),
            operation_name='search_nodes'
        )

    def open_nodes(self, names: List[str]) -> Optional[Dict[str, Any]]:
        """
        Get full details for specific entities by name

        Args:
            names: List of entity names to retrieve

        Returns:
            Dict with 'entities' and 'relations' keys, or None on error

        Example:
            result = client.open_nodes(["checkpoint.py", "session-logger"])
            # Returns full entity data with all observations
        """
        return self._retry_operation(
            lambda: self._call_mcp_tool('open_nodes', {'names': names}),
            operation_name='open_nodes'
        )

    def read_graph(self) -> Optional[Dict[str, Any]]:
        """
        Read entire memory graph

        WARNING: This can be expensive for large graphs (200+ entities).
        Prefer search_nodes() for targeted queries.

        Returns:
            Dict with 'entities' and 'relations' keys, or None on error

        Example:
            result = client.read_graph()
            # Returns: {"entities": [...], "relations": [...]}
        """
        return self._retry_operation(
            lambda: self._call_mcp_tool('read_graph', {}),
            operation_name='read_graph'
        )

    def create_entities(self, entities: List[Dict[str, Any]]) -> bool:
        """
        Create new entities in memory graph

        Args:
            entities: List of entity dicts with keys:
                - name: str (unique identifier)
                - entityType: str (category like "decision", "project", etc.)
                - observations: List[str] (text observations)

        Returns:
            True if successful, False otherwise

        Example:
            success = client.create_entities([{
                "name": "jwt-decision",
                "entityType": "decision",
                "observations": ["Decided to use JWT for authentication"]
            }])
        """
        result = self._retry_operation(
            lambda: self._call_mcp_tool('create_entities', {'entities': entities}),
            operation_name='create_entities'
        )
        return result is not None

    def add_observations(self, observations: List[Dict[str, Any]]) -> bool:
        """
        Add observations to existing entities

        Args:
            observations: List of dicts with keys:
                - entityName: str (existing entity)
                - contents: List[str] (new observations to add)

        Returns:
            True if successful, False otherwise

        Example:
            success = client.add_observations([{
                "entityName": "jwt-decision",
                "contents": ["Updated to use RS256 algorithm"]
            }])
        """
        result = self._retry_operation(
            lambda: self._call_mcp_tool('add_observations', {'observations': observations}),
            operation_name='add_observations'
        )
        return result is not None

    def estimate_tokens(self, result: Optional[Dict[str, Any]]) -> int:
        """
        Estimate token cost of a memory query result

        Uses rough heuristic: ~4 characters per token

        Args:
            result: Dict returned from search_nodes/open_nodes/read_graph

        Returns:
            Estimated token count (0 if result is None)
        """
        if result is None:
            return 0

        # Convert to JSON string and estimate tokens
        json_str = json.dumps(result)
        char_count = len(json_str)

        # ~4 characters per token (conservative estimate)
        return char_count // 4

    def _call_mcp_tool(self, tool_name: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Call an MCP memory tool

        This is a simplified implementation that assumes the MCP tools are
        available in the current Python environment. In practice, MCP tools
        are invoked through the Claude Code infrastructure.

        Args:
            tool_name: Name of MCP tool (e.g., "search_nodes")
            params: Tool parameters

        Returns:
            Tool result dict or None on error
        """
        try:
            # In the real implementation, this would go through the MCP protocol
            # For now, we'll assume the tools are available as Python modules

            # Import the MCP memory tools dynamically
            # NOTE: This assumes tools are accessible in the environment
            # The actual implementation may differ based on how MCP tools are exposed

            # Placeholder: Return empty result for now
            # This will be replaced with actual MCP tool invocation
            return {"entities": [], "relations": []}

        except Exception as e:
            print(f"Error calling MCP tool {tool_name}: {e}")
            return None

    def _retry_operation(self, operation, operation_name: str) -> Optional[Any]:
        """
        Retry an operation with exponential backoff

        Args:
            operation: Callable that returns result or raises exception
            operation_name: Name for logging

        Returns:
            Operation result or None on failure
        """
        last_exception = None

        for attempt in range(self.retry_attempts + 1):
            try:
                return operation()
            except Exception as e:
                last_exception = e
                if attempt < self.retry_attempts:
                    # Exponential backoff
                    sleep_time = self.retry_backoff * (2 ** attempt)
                    time.sleep(sleep_time)
                    continue
                else:
                    # Final attempt failed
                    print(f"Error in {operation_name} after {self.retry_attempts + 1} attempts: {last_exception}")
                    return None

        return None


# Export public API
__all__ = ['MemoryClient']
