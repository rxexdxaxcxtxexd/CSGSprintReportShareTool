"""
Memory Cache Module for Context-Aware Memory Trigger System

Provides two-tier caching:
1. Entity Names Cache - TTL: 5 minutes (300 seconds)
2. Query Results Cache - TTL: 10 minutes (600 seconds), LRU eviction

Thread-safe operations with persistent storage to ~/.claude/memory-cache.json
"""

import json
import hashlib
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any
from collections import OrderedDict


class MemoryCache:
    """
    Thread-safe cache manager for MCP memory operations.

    Features:
    - Entity names caching with 5-minute TTL
    - Query result caching with 10-minute TTL and LRU eviction
    - Persistent storage across sessions
    - Automatic expiration cleanup
    """

    # Cache configuration
    ENTITY_NAMES_TTL = 300  # 5 minutes
    QUERY_CACHE_TTL = 600   # 10 minutes
    MAX_QUERY_CACHE_SIZE = 100  # LRU eviction after this size

    def __init__(self, cache_path: Optional[Path] = None):
        """
        Initialize memory cache.

        Args:
            cache_path: Custom cache file path (default: ~/.claude/memory-cache.json)
        """
        self.lock = threading.Lock()

        # Set cache file path
        if cache_path:
            self.cache_path = Path(cache_path)
        else:
            self.cache_path = Path.home() / ".claude" / "memory-cache.json"

        # Ensure cache directory exists
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize cache structure
        self.cache_data = {
            "entity_names": {
                "data": [],
                "last_refresh": None,
                "ttl_seconds": self.ENTITY_NAMES_TTL
            },
            "query_cache": OrderedDict()
        }

        # Load existing cache
        self._load_cache()

    def get_entity_names(self, memory_client: Any, force_refresh: bool = False) -> List[str]:
        """
        Get cached entity names, refreshing if expired or forced.

        Args:
            memory_client: MCP memory client (used if refresh needed)
            force_refresh: Force cache refresh even if valid

        Returns:
            List of entity names
        """
        with self.lock:
            entity_cache = self.cache_data["entity_names"]

            # Check if refresh needed
            needs_refresh = force_refresh or not entity_cache["last_refresh"]

            if not needs_refresh and entity_cache["last_refresh"]:
                # Parse timestamp and check TTL
                last_refresh = datetime.fromisoformat(entity_cache["last_refresh"])
                ttl_delta = timedelta(seconds=entity_cache["ttl_seconds"])

                if datetime.now() > last_refresh + ttl_delta:
                    needs_refresh = True

            # Refresh if needed and client provided
            if needs_refresh and memory_client:
                try:
                    # Fetch fresh entity names from memory client
                    graph = memory_client.read_graph()
                    entity_names = [entity["name"] for entity in graph.get("entities", [])]
                    self.cache_entity_names(entity_names)
                except Exception as e:
                    # If refresh fails but we have cached data, use it
                    if entity_cache["data"]:
                        return entity_cache["data"]
                    raise e

            return entity_cache["data"]

    def cache_entity_names(self, names: List[str]) -> None:
        """
        Store entity names in cache with current timestamp.

        Args:
            names: List of entity names to cache
        """
        with self.lock:
            self.cache_data["entity_names"] = {
                "data": names,
                "last_refresh": datetime.now().isoformat(),
                "ttl_seconds": self.ENTITY_NAMES_TTL
            }
            self._save_cache()

    def cache_query_result(self, query: str, result: Dict, ttl_seconds: Optional[int] = None) -> None:
        """
        Cache a query result with TTL and LRU eviction.

        Args:
            query: Query string to use as cache key
            result: Query result to cache
            ttl_seconds: Custom TTL (default: 600 seconds)
        """
        if ttl_seconds is None:
            ttl_seconds = self.QUERY_CACHE_TTL

        with self.lock:
            # Generate cache key from query
            cache_key = self._hash_query(query)

            # Store result with metadata
            cache_entry = {
                "result": result,
                "timestamp": datetime.now().isoformat(),
                "ttl_seconds": ttl_seconds,
                "query": query  # Store original query for debugging
            }

            # If key exists, remove it first (for LRU ordering)
            if cache_key in self.cache_data["query_cache"]:
                del self.cache_data["query_cache"][cache_key]

            # Add to end (most recently used)
            self.cache_data["query_cache"][cache_key] = cache_entry

            # Enforce LRU eviction
            while len(self.cache_data["query_cache"]) > self.MAX_QUERY_CACHE_SIZE:
                # Remove oldest (first) item
                self.cache_data["query_cache"].popitem(last=False)

            self._save_cache()

    def get_cached_query(self, query: str) -> Optional[Dict]:
        """
        Retrieve cached query result if valid and not expired.

        Args:
            query: Query string to look up

        Returns:
            Cached result or None if not found/expired
        """
        with self.lock:
            cache_key = self._hash_query(query)

            if cache_key not in self.cache_data["query_cache"]:
                return None

            cache_entry = self.cache_data["query_cache"][cache_key]

            # Check if expired
            timestamp = datetime.fromisoformat(cache_entry["timestamp"])
            ttl_delta = timedelta(seconds=cache_entry["ttl_seconds"])

            if datetime.now() > timestamp + ttl_delta:
                # Expired - remove it
                del self.cache_data["query_cache"][cache_key]
                self._save_cache()
                return None

            # Move to end (most recently used) for LRU
            self.cache_data["query_cache"].move_to_end(cache_key)

            return cache_entry["result"]

    def clear_expired(self) -> int:
        """
        Remove all expired cache entries.

        Returns:
            Number of entries removed
        """
        with self.lock:
            removed_count = 0
            now = datetime.now()

            # Check entity names cache
            entity_cache = self.cache_data["entity_names"]
            if entity_cache["last_refresh"]:
                last_refresh = datetime.fromisoformat(entity_cache["last_refresh"])
                ttl_delta = timedelta(seconds=entity_cache["ttl_seconds"])

                if now > last_refresh + ttl_delta:
                    self.cache_data["entity_names"]["data"] = []
                    self.cache_data["entity_names"]["last_refresh"] = None
                    removed_count += 1

            # Check query cache
            expired_keys = []
            for cache_key, cache_entry in self.cache_data["query_cache"].items():
                timestamp = datetime.fromisoformat(cache_entry["timestamp"])
                ttl_delta = timedelta(seconds=cache_entry["ttl_seconds"])

                if now > timestamp + ttl_delta:
                    expired_keys.append(cache_key)

            # Remove expired queries
            for cache_key in expired_keys:
                del self.cache_data["query_cache"][cache_key]
                removed_count += 1

            if removed_count > 0:
                self._save_cache()

            return removed_count

    def clear_all(self) -> None:
        """Clear all cache entries."""
        with self.lock:
            self.cache_data = {
                "entity_names": {
                    "data": [],
                    "last_refresh": None,
                    "ttl_seconds": self.ENTITY_NAMES_TTL
                },
                "query_cache": OrderedDict()
            }
            self._save_cache()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        with self.lock:
            entity_cache = self.cache_data["entity_names"]
            entity_valid = False

            if entity_cache["last_refresh"]:
                last_refresh = datetime.fromisoformat(entity_cache["last_refresh"])
                ttl_delta = timedelta(seconds=entity_cache["ttl_seconds"])
                entity_valid = datetime.now() <= last_refresh + ttl_delta

            return {
                "entity_names_count": len(entity_cache["data"]),
                "entity_names_valid": entity_valid,
                "entity_names_last_refresh": entity_cache["last_refresh"],
                "query_cache_count": len(self.cache_data["query_cache"]),
                "query_cache_max_size": self.MAX_QUERY_CACHE_SIZE,
                "cache_file": str(self.cache_path)
            }

    def _hash_query(self, query: str) -> str:
        """
        Generate hash for query string to use as cache key.

        Args:
            query: Query string

        Returns:
            SHA-256 hash of query
        """
        return hashlib.sha256(query.encode('utf-8')).hexdigest()

    def _load_cache(self) -> None:
        """Load cache from disk if it exists."""
        if not self.cache_path.exists():
            return

        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)

            # Restore entity names cache
            if "entity_names" in loaded_data:
                self.cache_data["entity_names"] = loaded_data["entity_names"]

            # Restore query cache with OrderedDict
            if "query_cache" in loaded_data:
                self.cache_data["query_cache"] = OrderedDict(loaded_data["query_cache"])

            # Clean up expired entries on load
            self.clear_expired()

        except Exception as e:
            # If cache file is corrupt, start fresh
            print(f"Warning: Could not load cache file: {e}")
            self.cache_data = {
                "entity_names": {
                    "data": [],
                    "last_refresh": None,
                    "ttl_seconds": self.ENTITY_NAMES_TTL
                },
                "query_cache": OrderedDict()
            }

    def _save_cache(self) -> None:
        """Save cache to disk."""
        try:
            # Convert OrderedDict to regular dict for JSON serialization
            save_data = {
                "entity_names": self.cache_data["entity_names"],
                "query_cache": dict(self.cache_data["query_cache"])
            }

            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"Warning: Could not save cache file: {e}")


# Singleton instance for module-level usage
_cache_instance: Optional[MemoryCache] = None


def get_cache() -> MemoryCache:
    """
    Get or create singleton cache instance.

    Returns:
        Shared MemoryCache instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = MemoryCache()
    return _cache_instance


# Example usage and testing
if __name__ == "__main__":
    print("Memory Cache Module - Testing")
    print("=" * 50)

    # Create cache instance
    cache = MemoryCache()

    # Test 1: Entity names caching
    print("\n[Test 1: Entity Names Cache]")
    test_entities = ["User", "Project", "Task", "Comment"]
    cache.cache_entity_names(test_entities)
    retrieved = cache.get_entity_names(None)
    print(f"Cached: {test_entities}")
    print(f"Retrieved: {retrieved}")
    assert retrieved == test_entities, "Entity names mismatch!"
    print("[PASS] Entity names cache working")

    # Test 2: Query result caching
    print("\n[Test 2: Query Results Cache]")
    test_query = "search for project management"
    test_result = {"nodes": [{"name": "Project", "type": "entity"}]}
    cache.cache_query_result(test_query, test_result)
    cached_result = cache.get_cached_query(test_query)
    print(f"Query: {test_query}")
    print(f"Cached result: {cached_result}")
    assert cached_result == test_result, "Query result mismatch!"
    print("[PASS] Query cache working")

    # Test 3: Cache miss
    print("\n[Test 3: Cache Miss]")
    miss_result = cache.get_cached_query("nonexistent query")
    print(f"Result for nonexistent query: {miss_result}")
    assert miss_result is None, "Should return None for cache miss!"
    print("[PASS] Cache miss handling working")

    # Test 4: LRU eviction (add more than MAX_QUERY_CACHE_SIZE)
    print("\n[Test 4: LRU Eviction]")
    original_max = cache.MAX_QUERY_CACHE_SIZE
    cache.MAX_QUERY_CACHE_SIZE = 3  # Set low limit for testing

    for i in range(5):
        cache.cache_query_result(f"query_{i}", {"result": i})

    stats = cache.get_stats()
    print(f"Query cache count: {stats['query_cache_count']}")
    print(f"Max size: {cache.MAX_QUERY_CACHE_SIZE}")
    assert stats["query_cache_count"] <= 3, "LRU eviction not working!"

    # Should have queries 2, 3, 4 (oldest 0, 1 evicted)
    assert cache.get_cached_query("query_0") is None, "Query 0 should be evicted"
    assert cache.get_cached_query("query_4") is not None, "Query 4 should exist"
    print("[PASS] LRU eviction working")

    cache.MAX_QUERY_CACHE_SIZE = original_max  # Restore

    # Test 5: Statistics
    print("\n[Test 5: Cache Statistics]")
    stats = cache.get_stats()
    print(f"Entity names count: {stats['entity_names_count']}")
    print(f"Entity names valid: {stats['entity_names_valid']}")
    print(f"Query cache count: {stats['query_cache_count']}")
    print(f"Cache file: {stats['cache_file']}")
    print("[PASS] Statistics working")

    # Test 6: Persistence
    print("\n[Test 6: Persistence]")
    cache_path = cache.cache_path
    print(f"Cache file exists: {cache_path.exists()}")
    assert cache_path.exists(), "Cache file not created!"

    # Create new instance and verify data persisted
    cache2 = MemoryCache()
    retrieved2 = cache2.get_entity_names(None)
    print(f"Retrieved from new instance: {retrieved2}")
    assert retrieved2 == test_entities, "Persistence not working!"
    print("[PASS] Persistence working")

    # Test 7: Clear expired (with short TTL)
    print("\n[Test 7: Expiration]")
    cache.cache_query_result("short_ttl_query", {"data": "test"}, ttl_seconds=0)
    import time
    time.sleep(1)
    removed = cache.clear_expired()
    print(f"Removed {removed} expired entries")
    result = cache.get_cached_query("short_ttl_query")
    assert result is None, "Expired entry not removed!"
    print("[PASS] Expiration working")

    print("\n" + "=" * 50)
    print("All tests passed!")
    print("\nFinal cache statistics:")
    final_stats = cache.get_stats()
    for key, value in final_stats.items():
        print(f"  {key}: {value}")
