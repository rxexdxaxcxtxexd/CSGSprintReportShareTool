# Entity Mention Detector - Quick Start Guide

## 30-Second Setup

```python
from memory_detectors.entity_mention_detector import EntityMentionDetector

# 1. Create detector
detector = EntityMentionDetector({'enabled': True, 'priority': 3})

# 2. Set memory client
detector.set_memory_client(memory_client)

# 3. Use it
result = detector.evaluate("How does UserManager work?", {})

if result:
    entities = result.query_params['names']
    print(f"Found entities: {entities}")
```

## Quick Test

```bash
cd scripts
python test_entity_detector_simple.py
```

## Configuration Cheat Sheet

```python
config = {
    'enabled': True,              # Enable/disable detector
    'priority': 3,                # Lower = higher priority
    'min_entity_length': 2,       # Min chars for entity names
    'partial_match_threshold': 0.7 # Min score for fuzzy matches (0.0-1.0)
}
```

## Common Use Cases

### Use Case 1: Basic Detection
```python
result = detector.evaluate("What is PaymentService?", {})
# Result: Matches 'PaymentService' if in memory graph
```

### Use Case 2: Multiple Entities
```python
result = detector.evaluate("How do UserManager and Database interact?", {})
# Result: Matches both 'UserManager' and 'Database'
```

### Use Case 3: Fuzzy Match
```python
result = detector.evaluate("Tell me about the payment service", {})
# Result: Matches 'PaymentService' via fuzzy matching
```

## Cache Management

```python
# Get cached entities
entities = detector.cache.get_entity_names(memory_client)

# Force refresh
entities = detector.cache.get_entity_names(memory_client, force_refresh=True)

# Check cache stats
stats = detector.cache.get_stats()
print(f"Cached: {stats['entity_names_count']} entities")

# Clear cache
detector.cache.clear_all()
```

## TriggerResult Format

```python
TriggerResult(
    triggered=True,                          # Whether detector triggered
    confidence=0.85,                         # Score 0.0-1.0
    estimated_tokens=100,                    # Token cost estimate
    query_type="entity_details",             # Query type
    query_params={'names': ['UserManager']}, # Entity names to query
    reason="Mentioned 1 known entity..."     # Human-readable reason
)
```

## Confidence Levels

| Confidence | Match Type | Example |
|-----------|------------|---------|
| 0.9 | Multiple exact | "UserManager and PaymentService" |
| 0.8-0.85 | Single exact | "What is UserManager?" |
| 0.7-0.8 | Good fuzzy | "Tell me about user manager" |
| 0.6-0.7 | Weak fuzzy | "user management system" |
| < 0.6 | No match | - |

## Troubleshooting

### Problem: No matches found
```python
# Solution 1: Check if entities are cached
entities = detector.cache.get_entity_names(memory_client)
print(f"Cached entities: {entities}")

# Solution 2: Verify memory client is set
detector.set_memory_client(memory_client)

# Solution 3: Force cache refresh
detector.cache.get_entity_names(memory_client, force_refresh=True)
```

### Problem: Too many false positives
```python
# Solution: Increase match threshold
config = {
    'partial_match_threshold': 0.8,  # Default: 0.7
    'min_entity_length': 3,          # Default: 2
}
detector = EntityMentionDetector(config)
```

### Problem: Missing expected matches
```python
# Solution: Lower match threshold
config = {
    'partial_match_threshold': 0.6,  # Default: 0.7
}
detector = EntityMentionDetector(config)
```

## Performance Tips

1. **Cache hits are fast** (~1ms) - first query loads cache
2. **Cache refreshes every 5 minutes** - automatic
3. **Top 10 entities returned** - prevents overwhelming context
4. **Code blocks are skipped** - no false matches in code

## File Locations

```
scripts/
├── memory_detectors/
│   ├── entity_mention_detector.py        # Main implementation
│   ├── entity_mention_example.py         # Interactive examples
│   ├── ENTITY_MENTION_DETECTOR.md        # Full documentation
│   └── ENTITY_DETECTOR_IMPLEMENTATION.md # Implementation details
├── tests/
│   ├── test_entity_mention_detector.py   # Pytest tests
│   └── run_entity_mention_tests.py       # Standalone tests
└── test_entity_detector_simple.py        # Debug test
```

## Testing Commands

```bash
# Simple test (no dependencies)
python test_entity_detector_simple.py

# Full test suite (no pytest needed)
python tests/run_entity_mention_tests.py

# Interactive examples
python memory_detectors/entity_mention_example.py

# Pytest (if installed)
pytest tests/test_entity_mention_detector.py -v
```

## Integration Example

```python
# In your trigger engine
from memory_detectors.entity_mention_detector import EntityMentionDetector

# Initialize
detector = EntityMentionDetector({
    'enabled': True,
    'priority': 3,
})
detector.set_memory_client(memory_client)

# In conversation loop
user_prompt = get_user_input()

# Evaluate
result = detector.evaluate(user_prompt, session_context)

if result:
    # Query memory graph
    entity_names = result.query_params['names']
    entity_data = memory_client.open_nodes(names=entity_names)

    # Add to context
    context.add_memory(entity_data)

    # Log
    print(f"[TRIGGER] {result.reason}")
```

## API Quick Reference

```python
# EntityMentionDetector
detector = EntityMentionDetector(config)
detector.set_memory_client(client)
result = detector.evaluate(prompt, context)

# MemoryCache
cache = detector.cache
entities = cache.get_entity_names(client)
stats = cache.get_stats()
cache.clear_all()

# TriggerResult
result.triggered       # bool
result.confidence      # float 0.0-1.0
result.estimated_tokens # int
result.query_type      # str "entity_details"
result.query_params    # dict {'names': [...]}
result.reason          # str
```

## Next Steps

1. **Read full docs**: `ENTITY_MENTION_DETECTOR.md`
2. **Run examples**: `python memory_detectors/entity_mention_example.py`
3. **Review tests**: `tests/test_entity_mention_detector.py`
4. **Integrate**: Add to your trigger engine

## Support

- **Documentation**: `ENTITY_MENTION_DETECTOR.md`
- **Examples**: `entity_mention_example.py`
- **Debug**: `test_entity_detector_simple.py`
- **Tests**: `tests/test_entity_mention_detector.py`
