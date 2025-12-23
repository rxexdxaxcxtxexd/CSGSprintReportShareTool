"""
Example usage of memory_cache.py for Context-Aware Memory Trigger System

This demonstrates how to use the caching module in practice.
"""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from memory_cache import MemoryCache, get_cache


def example_basic_usage():
    """Basic cache operations"""
    print("Example 1: Basic Cache Operations")
    print("-" * 50)

    # Create cache instance
    cache = MemoryCache()

    # Cache entity names
    entities = ["User", "Project", "Task", "Comment", "Team"]
    cache.cache_entity_names(entities)
    print(f"Cached {len(entities)} entity names")

    # Retrieve entity names (no memory client needed if cached)
    retrieved = cache.get_entity_names(None)
    print(f"Retrieved: {retrieved}")

    # Cache a query result
    query = "find all projects related to user authentication"
    result = {
        "nodes": [
            {"name": "AuthService", "type": "service"},
            {"name": "UserAuth", "type": "component"}
        ]
    }
    cache.cache_query_result(query, result)
    print(f"\nCached query: '{query}'")

    # Retrieve cached query
    cached = cache.get_cached_query(query)
    print(f"Retrieved result: {cached}")

    print()


def example_ttl_and_expiration():
    """Demonstrate TTL and expiration"""
    print("Example 2: TTL and Expiration")
    print("-" * 50)

    cache = MemoryCache()

    # Cache with custom TTL
    query = "temporary query"
    result = {"data": "temporary"}
    cache.cache_query_result(query, result, ttl_seconds=2)
    print(f"Cached query with 2-second TTL")

    # Immediate retrieval works
    cached = cache.get_cached_query(query)
    print(f"Immediate retrieval: {cached}")

    # Wait and try again
    import time
    print("Waiting 3 seconds...")
    time.sleep(3)

    expired = cache.get_cached_query(query)
    print(f"After expiration: {expired}")

    print()


def example_lru_eviction():
    """Demonstrate LRU eviction"""
    print("Example 3: LRU Eviction")
    print("-" * 50)

    cache = MemoryCache()

    # Temporarily reduce cache size for demonstration
    original_max = cache.MAX_QUERY_CACHE_SIZE
    cache.MAX_QUERY_CACHE_SIZE = 3

    print(f"Cache max size: {cache.MAX_QUERY_CACHE_SIZE}")

    # Add queries
    for i in range(5):
        query = f"query number {i}"
        result = {"query_id": i}
        cache.cache_query_result(query, result)
        print(f"  Cached: {query}")

    # Check what's still cached
    print("\nChecking cache after LRU eviction:")
    for i in range(5):
        query = f"query number {i}"
        cached = cache.get_cached_query(query)
        status = "CACHED" if cached else "EVICTED"
        print(f"  query {i}: {status}")

    # Restore original size
    cache.MAX_QUERY_CACHE_SIZE = original_max

    print()


def example_statistics():
    """Show cache statistics"""
    print("Example 4: Cache Statistics")
    print("-" * 50)

    cache = get_cache()  # Use singleton

    stats = cache.get_stats()
    print("Current cache statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print()


def example_with_memory_client():
    """Demonstrate integration with memory client (simulated)"""
    print("Example 5: Integration with Memory Client")
    print("-" * 50)

    cache = MemoryCache()

    # Simulate a memory client
    class MockMemoryClient:
        def read_graph(self):
            return {
                "entities": [
                    {"name": "Project"},
                    {"name": "User"},
                    {"name": "Task"}
                ]
            }

    mock_client = MockMemoryClient()

    # First call - will fetch from client
    print("First call (will fetch from mock client):")
    entities = cache.get_entity_names(mock_client)
    print(f"  Retrieved: {entities}")

    # Second call - will use cache
    print("\nSecond call (will use cache):")
    entities = cache.get_entity_names(mock_client)
    print(f"  Retrieved: {entities}")

    # Force refresh
    print("\nForced refresh (will fetch from mock client):")
    entities = cache.get_entity_names(mock_client, force_refresh=True)
    print(f"  Retrieved: {entities}")

    print()


def example_clear_operations():
    """Demonstrate cache clearing"""
    print("Example 6: Clear Operations")
    print("-" * 50)

    cache = MemoryCache()

    # Add some data
    cache.cache_entity_names(["Entity1", "Entity2"])
    cache.cache_query_result("query1", {"data": 1})
    cache.cache_query_result("query2", {"data": 2})

    print("Before clear:")
    stats = cache.get_stats()
    print(f"  Entity names: {stats['entity_names_count']}")
    print(f"  Query cache: {stats['query_cache_count']}")

    # Clear expired (none yet)
    removed = cache.clear_expired()
    print(f"\nCleared {removed} expired entries")

    # Clear all
    cache.clear_all()
    print("\nAfter clear_all():")
    stats = cache.get_stats()
    print(f"  Entity names: {stats['entity_names_count']}")
    print(f"  Query cache: {stats['query_cache_count']}")

    print()


if __name__ == "__main__":
    print("=" * 50)
    print("Memory Cache Module - Usage Examples")
    print("=" * 50)
    print()

    example_basic_usage()
    example_ttl_and_expiration()
    example_lru_eviction()
    example_statistics()
    example_with_memory_client()
    example_clear_operations()

    print("=" * 50)
    print("All examples completed!")
    print("=" * 50)
