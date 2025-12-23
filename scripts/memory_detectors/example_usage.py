"""
Example Usage: Token Threshold Detector

Demonstrates how to use the TokenThresholdDetector in a session monitoring system.

Author: Context-Aware Memory System
Date: 2025-12-23
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_detectors.token_threshold_detector import TokenThresholdDetector
from memory_detectors import DetectorRegistry


def example_basic_usage():
    """Basic usage example"""
    print("=== Basic Usage Example ===\n")

    # Create detector with default thresholds (100K, 150K)
    config = {
        'priority': 4,
        'enabled': True
    }
    detector = TokenThresholdDetector(config)

    # Simulate session progression
    token_counts = [50000, 100000, 105000, 150000, 160000]

    for count in token_counts:
        context = {'token_count': count}
        result = detector.evaluate("User message...", context)

        print(f"Token count: {count:,}")
        if result:
            print(f"  TRIGGERED: {result.reason}")
            print(f"  Confidence: {result.confidence:.2f}")
            print(f"  Query type: {result.query_type}")
            print(f"  Search terms: {result.query_params['search_terms']}")
        else:
            print(f"  No trigger")
        print()

    print(f"Triggered thresholds: {detector.get_triggered_thresholds()}\n")


def example_custom_thresholds():
    """Example with custom thresholds"""
    print("=== Custom Thresholds Example ===\n")

    # Create detector with custom thresholds
    config = {
        'priority': 4,
        'enabled': True,
        'thresholds': [25000, 50000, 75000, 100000]
    }
    detector = TokenThresholdDetector(config)

    print(f"Configured thresholds: {detector.thresholds}\n")

    # Simulate reaching high token count
    context = {'token_count': 100000}

    for i in range(5):
        result = detector.evaluate(f"Message {i+1}", context)
        if result:
            threshold = result.query_params['threshold']
            print(f"Trigger #{i+1}: Crossed {threshold:,} tokens")
        else:
            print(f"Trigger #{i+1}: No more thresholds to cross")

    print()


def example_with_registry():
    """Example using detector registry"""
    print("=== Detector Registry Example ===\n")

    # Create registry
    registry = DetectorRegistry()

    # Register token threshold detector
    config = {
        'priority': 4,
        'enabled': True,
        'thresholds': [100000, 150000]
    }
    detector = TokenThresholdDetector(config)
    registry.register(detector)

    print(f"Registered detectors: {registry.list_detectors()}")
    print(f"Detector priority: {detector.priority}\n")

    # Get enabled detectors and evaluate
    enabled = registry.get_enabled_detectors()
    context = {'token_count': 100000}

    for det in enabled:
        result = det.evaluate("Check memory", context)
        if result:
            print(f"Detector '{det.name}' triggered:")
            print(f"  {result.reason}")
            print(f"  Estimated token cost: {result.estimated_tokens}")
            print()


def example_state_management():
    """Example showing state management and reset"""
    print("=== State Management Example ===\n")

    config = {'priority': 4}
    detector = TokenThresholdDetector(config)

    # Session 1
    print("Session 1:")
    context = {'token_count': 100000}
    result = detector.evaluate("Message", context)
    print(f"  Triggered: {result is not None}")
    print(f"  Triggered thresholds: {detector.get_triggered_thresholds()}")

    # Reset for new session
    print("\nResetting state for new session...")
    detector.reset_state()

    # Session 2
    print("\nSession 2:")
    result = detector.evaluate("Message", context)
    print(f"  Triggered: {result is not None}")
    print(f"  Triggered thresholds: {detector.get_triggered_thresholds()}")
    print()


def example_query_params():
    """Example showing query parameter details"""
    print("=== Query Parameters Example ===\n")

    config = {'priority': 4}
    detector = TokenThresholdDetector(config)

    context = {'token_count': 100000}
    result = detector.evaluate("Check pending work", context)

    if result:
        print(f"Query Type: {result.query_type}")
        print(f"Estimated Tokens: {result.estimated_tokens}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"\nQuery Parameters:")
        for key, value in result.query_params.items():
            print(f"  {key}: {value}")
        print()


if __name__ == '__main__':
    example_basic_usage()
    example_custom_thresholds()
    example_with_registry()
    example_state_management()
    example_query_params()
