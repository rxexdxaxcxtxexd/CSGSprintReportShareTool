"""
Simple standalone test for entity mention detector

Run with: python test_entity_detector_simple.py
"""

import sys
from pathlib import Path
from unittest.mock import Mock

# Ensure scripts directory is in path
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

print("Starting entity detector test...")
print("=" * 60)

try:
    # Import the detector
    from memory_detectors.entity_mention_detector import EntityMentionDetector
    print("[OK] EntityMentionDetector imported successfully")

    # Create detector
    config = {'enabled': True, 'priority': 3}
    detector = EntityMentionDetector(config)
    print(f"[OK] Detector created: {detector.name}")

    # Create mock client
    client = Mock()
    client.read_graph.return_value = {
        'entities': [
            {'name': 'UserManager'},
            {'name': 'PaymentService'},
            {'name': 'API Gateway'}
        ]
    }
    print("[OK] Mock client created")

    # Set client on detector
    detector.set_memory_client(client)
    print("[OK] Client set on detector")

    # Get entity names (should trigger cache load)
    entities = detector.cache.get_entity_names(client)
    print(f"[OK] Entities loaded from cache: {entities}")
    print(f"     Count: {len(entities)}")

    # Test 1: Exact match
    print("\n" + "-" * 60)
    print("Test 1: Exact match for 'UserManager'")
    prompt1 = "What is UserManager?"
    result1 = detector.evaluate(prompt1, {})

    if result1:
        print(f"[PASS] Match found")
        print(f"       Confidence: {result1.confidence}")
        print(f"       Entities: {result1.query_params['names']}")
        print(f"       Reason: {result1.reason}")
    else:
        print("[FAIL] No match found")
        # Debug
        print(f"       Cached entities: {detector.cache.get_entity_names(None)}")

    # Test 2: Case insensitive
    print("\n" + "-" * 60)
    print("Test 2: Case insensitive match")
    prompt2 = "Tell me about usermanager"
    result2 = detector.evaluate(prompt2, {})

    if result2:
        print(f"[PASS] Match found")
        print(f"       Entities: {result2.query_params['names']}")
    else:
        print("[FAIL] No match found")

    # Test 3: Partial match
    print("\n" + "-" * 60)
    print("Test 3: Partial/fuzzy match")
    prompt3 = "How does the payment service work?"
    result3 = detector.evaluate(prompt3, {})

    if result3:
        print(f"[PASS] Match found")
        print(f"       Entities: {result3.query_params['names']}")
    else:
        print("[FAIL] No match found")
        # Debug fuzzy matching
        words = detector._extract_words(prompt3.lower())
        print(f"       Extracted words: {words}")
        for entity in entities:
            score = detector._fuzzy_match(entity.lower(), words)
            print(f"       '{entity}' score: {score:.2f}")

    # Test 4: Entity with spaces
    print("\n" + "-" * 60)
    print("Test 4: Entity with spaces")
    prompt4 = "What is the API Gateway?"
    result4 = detector.evaluate(prompt4, {})

    if result4:
        print(f"[PASS] Match found")
        print(f"       Entities: {result4.query_params['names']}")
    else:
        print("[FAIL] No match found")

    # Test 5: No match
    print("\n" + "-" * 60)
    print("Test 5: No match expected")
    prompt5 = "What is the weather today?"
    result5 = detector.evaluate(prompt5, {})

    if result5 is None:
        print("[PASS] Correctly returned None")
    else:
        print(f"[FAIL] Should not match, but got: {result5.query_params['names']}")

    print("\n" + "=" * 60)
    print("Test complete!")

except Exception as e:
    print(f"\n[ERROR] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
