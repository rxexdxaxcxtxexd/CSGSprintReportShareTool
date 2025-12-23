"""
Simple integration test for all 4 detectors

Tests that all detectors can be imported and instantiated.
"""

import sys
from pathlib import Path

# Add scripts to path
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

print("=" * 60)
print("Testing Phase 2 Detector Integration")
print("=" * 60)

# Test 1: Import all detectors
print("\n[Test 1] Importing all detector modules...")
try:
    from memory_detectors.project_switch_detector import ProjectSwitchDetector
    print("  [OK] ProjectSwitchDetector imported")
except Exception as e:
    print(f"  [FAIL] ProjectSwitchDetector failed: {e}")
    sys.exit(1)

try:
    from memory_detectors.keyword_detector import KeywordDetector
    print("  [OK] KeywordDetector imported")
except Exception as e:
    print(f"  [FAIL] KeywordDetector failed: {e}")
    sys.exit(1)

try:
    from memory_detectors.entity_mention_detector import EntityMentionDetector
    print("  [OK] EntityMentionDetector imported")
except Exception as e:
    print(f"  [FAIL] EntityMentionDetector failed: {e}")
    sys.exit(1)

try:
    from memory_detectors.token_threshold_detector import TokenThresholdDetector
    print("  [OK] TokenThresholdDetector imported")
except Exception as e:
    print(f"  [FAIL] TokenThresholdDetector failed: {e}")
    sys.exit(1)

# Test 2: Import memory cache
print("\n[Test 2] Importing memory cache...")
try:
    from memory_cache import MemoryCache
    print("  [OK] MemoryCache imported")
except Exception as e:
    print(f"  [FAIL] MemoryCache failed: {e}")
    sys.exit(1)

# Test 3: Instantiate detectors
print("\n[Test 3] Instantiating detectors...")

try:
    detector1 = ProjectSwitchDetector({'priority': 1, 'enabled': True})
    print(f"  [OK] ProjectSwitchDetector created (name: {detector1.name}, priority: {detector1.priority})")
except Exception as e:
    print(f"  [FAIL] ProjectSwitchDetector instantiation failed: {e}")
    sys.exit(1)

try:
    detector2 = KeywordDetector({'priority': 2, 'enabled': True})
    print(f"  [OK] KeywordDetector created (name: {detector2.name}, priority: {detector2.priority})")
except Exception as e:
    print(f"  [FAIL] KeywordDetector instantiation failed: {e}")
    sys.exit(1)

try:
    detector3 = EntityMentionDetector({'priority': 3, 'enabled': True})
    print(f"  [OK] EntityMentionDetector created (name: {detector3.name}, priority: {detector3.priority})")
except Exception as e:
    print(f"  [FAIL] EntityMentionDetector instantiation failed: {e}")
    sys.exit(1)

try:
    detector4 = TokenThresholdDetector({'priority': 4, 'enabled': True})
    print(f"  [OK] TokenThresholdDetector created (name: {detector4.name}, priority: {detector4.priority})")
except Exception as e:
    print(f"  [FAIL] TokenThresholdDetector instantiation failed: {e}")
    sys.exit(1)

# Test 4: Verify priority ordering
print("\n[Test 4] Verifying priority ordering...")
detectors = [detector1, detector2, detector3, detector4]
priorities = [d.priority for d in detectors]

if priorities == [1, 2, 3, 4]:
    print(f"  [OK] Priorities correct: {priorities}")
else:
    print(f"  [FAIL] Priorities incorrect: {priorities} (expected [1, 2, 3, 4])")
    sys.exit(1)

# Test 5: Test detector registry
print("\n[Test 5] Testing detector registry...")
try:
    from memory_detectors import DetectorRegistry
    registry = DetectorRegistry()

    # Register all detectors
    for detector in detectors:
        registry.register(detector)

    enabled = registry.get_enabled_detectors()
    print(f"  [OK] Registry created with {len(enabled)} enabled detectors")

    # Verify order
    enabled_names = [d.name for d in enabled]
    expected_names = ['project_switch_detector', 'keyword_detector', 'entity_mention_detector', 'token_threshold_detector']

    if enabled_names == expected_names:
        print(f"  [OK] Detector order correct: {enabled_names}")
    else:
        print(f"  [FAIL] Detector order incorrect: {enabled_names}")
        print(f"     Expected: {expected_names}")
        sys.exit(1)

except Exception as e:
    print(f"  [FAIL] Registry test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("[SUCCESS] All integration tests PASSED!")
print("=" * 60)
print("\nSummary:")
print("  - All 4 detectors import successfully")
print("  - All 4 detectors instantiate correctly")
print("  - Priority ordering is correct (1->2->3->4)")
print("  - Detector registry works properly")
print("\n[COMPLETE] Phase 2 integration complete!")
