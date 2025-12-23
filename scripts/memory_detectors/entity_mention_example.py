"""
Entity Mention Detector - Example Usage

Demonstrates how to use the EntityMentionDetector with actual MCP memory client.

Author: Context-Aware Memory System
Date: 2025-12-23
"""

import sys
from pathlib import Path
from typing import Dict, Any

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_detectors.entity_mention_detector import EntityMentionDetector
from memory_cache import MemoryCache


def example_with_mock_client():
    """Example using a mock client (for testing without MCP)"""
    from unittest.mock import Mock

    print("=" * 70)
    print("Entity Mention Detector - Mock Client Example")
    print("=" * 70)

    # Create mock client
    mock_client = Mock()
    mock_client.read_graph.return_value = {
        'entities': [
            {'name': 'SessionManager', 'type': 'class'},
            {'name': 'PaymentProcessor', 'type': 'service'},
            {'name': 'API Gateway', 'type': 'infrastructure'},
            {'name': 'Database', 'type': 'infrastructure'},
            {'name': 'UserProfile', 'type': 'entity'}
        ]
    }

    # Create detector
    config = {
        'enabled': True,
        'priority': 3,
        'min_entity_length': 2,
        'partial_match_threshold': 0.7
    }

    detector = EntityMentionDetector(config)
    detector.set_memory_client(mock_client)

    print(f"\n[INFO] Detector created: {detector.name}")
    print(f"[INFO] Priority: {detector.priority}")
    print(f"[INFO] Enabled: {detector.enabled}")

    # Load entities into cache
    entities = detector.cache.get_entity_names(mock_client)
    print(f"\n[INFO] Loaded {len(entities)} entities into cache:")
    for entity in entities:
        print(f"  - {entity}")

    # Test cases
    test_prompts = [
        "How does SessionManager handle authentication?",
        "What is the payment processor doing?",
        "Tell me about the API Gateway configuration",
        "Can you explain the UserProfile structure?",
        "How do SessionManager and Database interact?",
        "What is the weather today?",  # Should not match
    ]

    print("\n" + "=" * 70)
    print("Testing Entity Detection")
    print("=" * 70)

    for i, prompt in enumerate(test_prompts, 1):
        print(f"\n[Test {i}] Prompt: \"{prompt}\"")

        # Evaluate
        context: Dict[str, Any] = {}
        result = detector.evaluate(prompt, context)

        if result:
            print(f"  [MATCH] Triggered: {result.triggered}")
            print(f"  Confidence: {result.confidence:.2f}")
            print(f"  Entities: {', '.join(result.query_params['names'])}")
            print(f"  Reason: {result.reason}")
            print(f"  Estimated tokens: {result.estimated_tokens}")
            print(f"  Query type: {result.query_type}")
        else:
            print("  [NO MATCH] No entities detected")

    # Cache statistics
    print("\n" + "=" * 70)
    print("Cache Statistics")
    print("=" * 70)

    stats = detector.cache.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")


def example_with_real_client():
    """Example using real MCP client"""
    try:
        # This would require actual MCP setup
        # For demonstration, we show the structure

        print("=" * 70)
        print("Entity Mention Detector - Real MCP Client Example")
        print("=" * 70)
        print("\n[INFO] This example requires MCP client setup")
        print("[INFO] See MCP documentation for setup instructions\n")

        # Example structure (would need actual MCP client)
        example_code = """
# Initialize MCP client
from mcp_client import MCPClient

client = MCPClient()

# Create detector
config = {
    'enabled': True,
    'priority': 3,
    'min_entity_length': 2,
    'partial_match_threshold': 0.7
}

detector = EntityMentionDetector(config)
detector.set_memory_client(client)

# Use in conversation loop
while True:
    user_prompt = input("User: ")

    # Check for entity mentions
    result = detector.evaluate(user_prompt, {})

    if result:
        # Query memory graph
        entity_names = result.query_params['names']
        entity_details = client.open_nodes(names=entity_names)

        # Use entity details in response
        print(f"Found entities: {entity_names}")
        print(f"Details: {entity_details}")

    # Continue with normal processing...
"""

        print("Example code structure:")
        print(example_code)

    except Exception as e:
        print(f"[ERROR] {e}")


def example_cache_management():
    """Example showing cache management features"""

    print("=" * 70)
    print("Entity Mention Detector - Cache Management")
    print("=" * 70)

    # Create cache instance
    cache = MemoryCache()

    # Manual entity caching (normally done automatically)
    test_entities = ['User', 'Project', 'Task', 'Comment', 'Tag']

    print(f"\n[INFO] Caching {len(test_entities)} entities...")
    cache.cache_entity_names(test_entities)

    # Retrieve cached entities
    cached = cache.get_entity_names(None)
    print(f"[INFO] Cached entities: {cached}")

    # Get statistics
    stats = cache.get_stats()
    print(f"\n[INFO] Cache Statistics:")
    print(f"  Entity count: {stats['entity_names_count']}")
    print(f"  Valid: {stats['entity_names_valid']}")
    print(f"  Last refresh: {stats['entity_names_last_refresh']}")

    # Clear expired entries
    print(f"\n[INFO] Clearing expired entries...")
    removed = cache.clear_expired()
    print(f"[INFO] Removed {removed} expired entries")

    # Clear all cache
    print(f"\n[INFO] Clearing all cache...")
    cache.clear_all()
    stats = cache.get_stats()
    print(f"[INFO] Entity count after clear: {stats['entity_names_count']}")


def example_fuzzy_matching():
    """Example demonstrating fuzzy matching capabilities"""

    from unittest.mock import Mock

    print("=" * 70)
    print("Entity Mention Detector - Fuzzy Matching Demo")
    print("=" * 70)

    # Create detector
    config = {
        'enabled': True,
        'priority': 3,
        'min_entity_length': 2,
        'partial_match_threshold': 0.7
    }

    detector = EntityMentionDetector(config)

    # Mock client with various entity names
    mock_client = Mock()
    mock_client.read_graph.return_value = {
        'entities': [
            {'name': 'UserAuthenticationService'},
            {'name': 'PaymentGateway'},
            {'name': 'EmailNotificationQueue'},
        ]
    }

    detector.set_memory_client(mock_client)

    # Test fuzzy matching
    test_cases = [
        # (prompt, should_match_entity)
        ("How does user authentication work?", "UserAuthenticationService"),
        ("Tell me about the payment gateway", "PaymentGateway"),
        ("What is in the email notification queue?", "EmailNotificationQueue"),
        ("How does auth service work?", "UserAuthenticationService"),
        ("Payment processing system", "PaymentGateway"),
    ]

    print("\n[INFO] Testing fuzzy matching:\n")

    for prompt, expected in test_cases:
        result = detector.evaluate(prompt, {})

        status = "[PASS]" if result and expected in result.query_params['names'] else "[FAIL]"

        print(f"{status} Prompt: \"{prompt}\"")
        if result:
            print(f"       Matched: {', '.join(result.query_params['names'])}")
            print(f"       Confidence: {result.confidence:.2f}")
        else:
            print(f"       No match (expected: {expected})")
        print()


def main():
    """Run all examples"""

    examples = [
        ("Mock Client Example", example_with_mock_client),
        ("Cache Management", example_cache_management),
        ("Fuzzy Matching Demo", example_fuzzy_matching),
        ("Real MCP Client (structure only)", example_with_real_client),
    ]

    print("\n\n")
    print("=" * 70)
    print(" Entity Mention Detector - Examples")
    print("=" * 70)
    print("\nChoose an example to run:")

    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")

    print(f"  {len(examples) + 1}. Run all examples")
    print("  0. Exit")

    choice = input("\nEnter choice (0-{}): ".format(len(examples) + 1))

    try:
        choice = int(choice)

        if choice == 0:
            print("Exiting...")
            return

        if choice == len(examples) + 1:
            # Run all
            for name, func in examples:
                print("\n\n")
                func()
                print("\n" + "=" * 70)
                print("Press Enter to continue...")
                input()
        elif 1 <= choice <= len(examples):
            # Run selected
            name, func = examples[choice - 1]
            func()
        else:
            print("Invalid choice")

    except ValueError:
        print("Invalid input")
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
