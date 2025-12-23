# Entity Mention Detector

## Overview

The Entity Mention Detector identifies when users mention known entities from the memory graph in their prompts and triggers entity detail queries.

## Key Features

- **Entity Name Caching**: Caches entity names with 5-minute TTL for performance
- **Case-Insensitive Matching**: Matches entities regardless of case
- **Fuzzy/Partial Matching**: Catches partial entity names and variations
- **Smart Scoring**: Confidence scores based on match quality
- **Code Block Filtering**: Skips code blocks to avoid false matches

## Configuration

```python
{
    'enabled': True,
    'priority': 3,
    'min_entity_length': 2,           # Minimum entity name length to consider
    'partial_match_threshold': 0.7    # Minimum score for partial matches
}
```

## How It Works

### 1. Entity Name Caching

Entities are cached using `MemoryCache` with a 5-minute TTL:

```python
# On first use or after expiration
entities = detector.cache.get_entity_names(memory_client)
# Returns: ['UserManager', 'PaymentService', 'API Gateway', ...]
```

### 2. Matching Algorithm

The detector uses a two-strategy fuzzy matching approach:

**Strategy 1: Substring Matching**
- Checks if prompt words contain entity words or vice versa
- Calculates similarity based on length ratios

**Strategy 2: Word Overlap**
- Extracts words from both entity name and prompt
- Calculates overlap ratio

**Final Score**: Uses the maximum score from both strategies

### 3. Match Types

- **Exact Match** (confidence: 0.8-0.9)
  - Entity name appears as complete word in prompt
  - Case-insensitive
  - Example: "UserManager" matches "What is usermanager?"

- **Partial Match** (confidence: 0.6-0.8)
  - Entity words partially match prompt words
  - Example: "PaymentService" matches "payment service"
  - Requires score >= `partial_match_threshold` (default: 0.7)

### 4. Confidence Calculation

Base confidence:
- Exact matches: 0.8 base
- Multiple exact matches: 0.9 base
- Partial matches: 0.6 base

Boosts:
- +0.05 for questions (contains '?')
- +0.05 for longer prompts (>50 chars)
- Multiplied by average match score

## Examples

### Example 1: Exact Match

**Prompt**: "How does UserManager work?"

**Result**:
```python
TriggerResult(
    triggered=True,
    confidence=0.85,
    estimated_tokens=100,
    query_type="entity_details",
    query_params={'names': ['UserManager']},
    reason="Mentioned 1 known entity(ies): 'UserManager'"
)
```

### Example 2: Multiple Entities

**Prompt**: "How does UserManager interact with PaymentService and Database?"

**Result**:
```python
TriggerResult(
    triggered=True,
    confidence=0.9,
    estimated_tokens=100,
    query_type="entity_details",
    query_params={'names': ['UserManager', 'PaymentService', 'Database']},
    reason="Mentioned 3 known entity(ies): 'UserManager', 'PaymentService', 'Database'"
)
```

### Example 3: Partial Match

**Prompt**: "Tell me about the payment service"

**Result**:
```python
TriggerResult(
    triggered=True,
    confidence=0.75,
    estimated_tokens=100,
    query_type="entity_details",
    query_params={'names': ['PaymentService']},
    reason="Mentioned 1 known entity(ies): 'PaymentService'"
)
```

### Example 4: Entity with Spaces

**Prompt**: "What is the API Gateway configuration?"

**Result**:
```python
TriggerResult(
    triggered=True,
    confidence=0.8,
    estimated_tokens=100,
    query_type="entity_details",
    query_params={'names': ['API Gateway']},
    reason="Mentioned 1 known entity(ies): 'API Gateway'"
)
```

## Filtering Rules

### Prompts That Are Skipped

1. **Too Short**: Less than 3 characters
2. **Code Blocks**: Contains ``` or high density of special characters
3. **No Entities**: No entities currently in cache

### Entities That Are Skipped

1. **Too Short**: Length < `min_entity_length` (default: 2)
2. **Low Match Score**: Partial match score < `partial_match_threshold` (default: 0.7)

## Cache Management

### Entity Names Cache

- **TTL**: 5 minutes (300 seconds)
- **Storage**: `~/.claude/memory-cache.json`
- **Refresh**: Automatic when expired, or force refresh available
- **Thread-Safe**: Uses locking for concurrent access

### Cache Statistics

```python
stats = detector.cache.get_stats()
# Returns:
# {
#     'entity_names_count': 6,
#     'entity_names_valid': True,
#     'entity_names_last_refresh': '2025-12-23T12:30:00',
#     'query_cache_count': 15,
#     'query_cache_max_size': 100,
#     'cache_file': '~/.claude/memory-cache.json'
# }
```

## Integration

### Setup

```python
from memory_detectors.entity_mention_detector import EntityMentionDetector

# Create detector
config = {
    'enabled': True,
    'priority': 3,
    'min_entity_length': 2,
    'partial_match_threshold': 0.7
}
detector = EntityMentionDetector(config)

# Set memory client (for cache refresh)
detector.set_memory_client(memory_client)
```

### Usage in Trigger Engine

```python
# Evaluate prompt
result = detector.evaluate(prompt, context)

if result and result.triggered:
    # Query memory graph for entity details
    entity_names = result.query_params['names']
    entity_details = memory_client.open_nodes(names=entity_names)

    # Add to context
    context.add_memory(entity_details)
```

## Performance

- **Cache Hit**: ~1ms (no MCP call)
- **Cache Miss**: ~50-100ms (MCP read_graph call)
- **Evaluation**: ~1-3ms per prompt
- **Entity Limit**: Top 10 matches returned

## Testing

### Test Coverage

- Entity name caching
- Case-insensitive matching
- Partial/fuzzy matching
- Cache refresh logic
- Confidence calculation
- Multiple entity detection
- Entities with spaces
- Word boundary matching
- Code block filtering
- Short prompt filtering

### Running Tests

```bash
# With pytest (if installed)
cd scripts
pytest tests/test_entity_mention_detector.py -v

# Without pytest
cd scripts
python tests/run_entity_mention_tests.py

# Simple standalone test
cd scripts
python test_entity_detector_simple.py
```

## Troubleshooting

### No Entities Found

**Problem**: Detector returns None even when entities are mentioned

**Solutions**:
1. Check if memory client is set: `detector.set_memory_client(client)`
2. Verify entities exist: `detector.cache.get_entity_names(client)`
3. Check cache validity: `detector.cache.get_stats()`
4. Force cache refresh: `detector.cache.get_entity_names(client, force_refresh=True)`

### Too Many False Positives

**Problem**: Detector triggers for unrelated terms

**Solutions**:
1. Increase `partial_match_threshold` (default: 0.7, try 0.8-0.9)
2. Increase `min_entity_length` (default: 2, try 3-4)
3. Check entity names for overly generic terms

### Cache Not Refreshing

**Problem**: Old entities still appearing after updates

**Solutions**:
1. Check cache TTL hasn't been modified
2. Verify system time is correct
3. Clear cache manually: `detector.cache.clear_all()`
4. Force refresh: `detector.cache.get_entity_names(client, force_refresh=True)`

## API Reference

### EntityMentionDetector

```python
class EntityMentionDetector(MemoryDetector):
    """Detects entity mentions in prompts"""

    def __init__(self, config: Dict[str, Any])
    def set_memory_client(self, client: Any) -> None
    def evaluate(self, prompt: str, context: Dict[str, Any]) -> Optional[TriggerResult]

    # Internal methods
    def _find_entity_mentions(self, prompt: str, entity_names: List[str]) -> List[Dict]
    def _extract_words(self, text: str) -> List[str]
    def _contains_word(self, text: str, word: str) -> bool
    def _fuzzy_match(self, entity_name: str, prompt_words: List[str]) -> float
    def _calculate_confidence(self, matched_entities: List[Dict], prompt: str) -> float
    def _is_code_block(self, text: str) -> bool
```

## Design Decisions

### Why 5-Minute Cache TTL?

- Balances freshness vs. performance
- Most sessions don't add/remove many entities
- Reduces MCP calls significantly
- Can be overridden if needed

### Why Fuzzy Matching?

- Users don't always type exact entity names
- Natural language varies ("user manager" vs "UserManager")
- Catches typos and partial mentions
- Improves user experience

### Why Priority 3?

- Lower than project switch (1) - project context first
- Lower than keyword detector (2) - explicit keywords take precedence
- Higher than threshold detector (999) - specific entities before generic fallback

### Why Limit to 10 Entities?

- Prevents overwhelming context with too many entities
- Most prompts mention 1-3 entities
- Keeps token usage reasonable
- Sorted by match quality (best first)

## Future Enhancements

Potential improvements:

1. **Synonym Support**: Map entity aliases to canonical names
2. **Relationship Detection**: Detect entity relationships in prompts
3. **Context-Aware Scoring**: Boost confidence based on previous mentions
4. **Entity Type Filtering**: Filter by entity type (person, project, etc.)
5. **Configurable Cache TTL**: Per-detector cache settings
6. **Advanced Fuzzy Matching**: Levenshtein distance, phonetic matching

## Related Documentation

- [Memory Cache Module](../memory_cache.py)
- [Memory Detector Base Classes](../__init__.py)
- [Trigger Engine Integration](./INTEGRATION_CHECKLIST.md)
- [Keyword Detector](./keyword_detector.py)
- [Project Switch Detector](./project_switch_detector.py)
