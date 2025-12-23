# Token Threshold Detector

## Overview

The `TokenThresholdDetector` is a memory trigger detector that monitors session token usage and triggers memory queries when predefined thresholds are crossed. This helps prevent context overflow by prompting memory checks at strategic points during long sessions.

## Features

- **Automatic Threshold Detection**: Triggers at 100K and 150K tokens by default
- **Duplicate Prevention**: Tracks triggered thresholds to prevent redundant triggers
- **State Management**: Maintains state across evaluations, resettable for new sessions
- **Configurable Thresholds**: Supports custom threshold values
- **Smart Confidence Scoring**: Higher confidence for higher thresholds
- **Search Term Recommendations**: Suggests terms to query for pending/incomplete work

## Configuration

### Default Configuration

```python
config = {
    'priority': 4,              # Lower = higher priority
    'enabled': True,            # Enable/disable detector
    'thresholds': [100000, 150000]  # Default thresholds (optional)
}
```

### Custom Thresholds

```python
config = {
    'priority': 4,
    'enabled': True,
    'thresholds': [50000, 100000, 150000, 200000]  # Custom thresholds
}
```

## Usage

### Basic Usage

```python
from memory_detectors.token_threshold_detector import TokenThresholdDetector

# Create detector
config = {'priority': 4, 'enabled': True}
detector = TokenThresholdDetector(config)

# Evaluate during session
context = {'token_count': 100000}
result = detector.evaluate("User message", context)

if result:
    print(f"Triggered: {result.reason}")
    print(f"Confidence: {result.confidence}")
    print(f"Query type: {result.query_type}")
    print(f"Search terms: {result.query_params['search_terms']}")
```

### With Detector Registry

```python
from memory_detectors import DetectorRegistry
from memory_detectors.token_threshold_detector import TokenThresholdDetector

# Create and register detector
registry = DetectorRegistry()
config = {'priority': 4}
detector = TokenThresholdDetector(config)
registry.register(detector)

# Evaluate all enabled detectors
context = {'token_count': 100000}
for det in registry.get_enabled_detectors():
    result = det.evaluate("User message", context)
    if result:
        # Handle trigger
        pass
```

### State Management

```python
# Check triggered thresholds
triggered = detector.get_triggered_thresholds()
print(f"Triggered: {triggered}")  # [100000]

# Reset for new session
detector.reset_state()

# Triggers will fire again after reset
```

## Trigger Behavior

### Sequential Triggering

The detector evaluates thresholds in ascending order. If multiple thresholds have been crossed, it triggers the lowest untriggered threshold first.

**Example:**
```python
detector = TokenThresholdDetector({'priority': 4})

# At 150K tokens, triggers 100K first (if not triggered yet)
context = {'token_count': 150000}
result1 = detector.evaluate("msg", context)  # Triggers 100K

# Second call triggers 150K
result2 = detector.evaluate("msg", context)  # Triggers 150K

# No more triggers
result3 = detector.evaluate("msg", context)  # None
```

### Duplicate Prevention

Each threshold triggers only once per detector instance:

```python
detector = TokenThresholdDetector({'priority': 4})

# First trigger at 100K
context = {'token_count': 100000}
result1 = detector.evaluate("msg", context)  # Triggers

# No trigger at 105K (same threshold)
context = {'token_count': 105000}
result2 = detector.evaluate("msg", context)  # None

# Trigger at 150K (new threshold)
context = {'token_count': 150000}
result3 = detector.evaluate("msg", context)  # Triggers
```

## Trigger Result

When triggered, returns a `TriggerResult` with:

```python
TriggerResult(
    triggered=True,
    confidence=0.8,           # 0.8 at 100K, 0.9 at 150K
    estimated_tokens=175,     # Fixed estimate
    query_type="threshold_check",
    query_params={
        'threshold': 100000,
        'current_count': 105000,
        'search_terms': ['pending', 'incomplete', 'TODO', 'in progress']
    },
    reason="Token count (105,000) crossed threshold 100,000"
)
```

## Query Parameters

The `query_params` dict contains:

- **threshold** (int): The threshold value that was crossed
- **current_count** (int): Current session token count
- **search_terms** (list): Recommended search terms for memory query
  - Default: `['pending', 'incomplete', 'TODO', 'in progress']`

## Confidence Scoring

Confidence increases with threshold level and overage:

| Threshold | Base Confidence | With 10K+ Overage |
|-----------|----------------|-------------------|
| 100K      | 0.8            | 0.9              |
| 150K      | 0.9            | 1.0              |
| Custom    | 0.7+           | varies           |

## Context Requirements

The detector expects the following in the `context` dict:

```python
context = {
    'token_count': int,  # Required: current session token count
    # Other context fields ignored by this detector
}
```

If `token_count` is missing, zero, or negative, the detector returns `None` (no trigger).

## Testing

Comprehensive test suite included in `scripts/tests/test_token_threshold_detector.py`:

```bash
cd scripts
python -m pytest tests/test_token_threshold_detector.py -v
```

### Test Coverage

- Threshold detection at 100K and 150K
- Duplicate prevention
- State management and reset
- Custom threshold configurations
- Edge cases (zero, negative, missing token count)
- Confidence scoring
- Query parameter structure

## Integration Example

```python
# In your session monitoring system
from memory_detectors.token_threshold_detector import TokenThresholdDetector

class SessionMonitor:
    def __init__(self):
        self.token_detector = TokenThresholdDetector({
            'priority': 4,
            'enabled': True
        })
        self.token_count = 0

    def on_message(self, message: str):
        # Update token count
        self.token_count += estimate_tokens(message)

        # Check threshold detector
        context = {'token_count': self.token_count}
        result = self.token_detector.evaluate(message, context)

        if result:
            # Trigger memory query
            self.query_memory(result.query_params['search_terms'])

    def query_memory(self, search_terms: list):
        # Query memory graph for pending items
        print(f"Querying memory for: {search_terms}")
        # ... memory query implementation ...
```

## Implementation Details

### State Tracking

The detector maintains a set of triggered thresholds in `self._triggered`:

```python
self._triggered: Set[int] = set()
```

This prevents duplicate triggers within the same session.

### Threshold Ordering

Thresholds are automatically sorted in ascending order during initialization:

```python
self.thresholds = sorted(config['thresholds'])
```

This ensures proper sequential evaluation.

### Thread Safety

**Note**: This implementation is not thread-safe. If using in a multi-threaded environment, wrap detector calls in locks:

```python
import threading

detector_lock = threading.Lock()

def evaluate_with_lock(detector, prompt, context):
    with detector_lock:
        return detector.evaluate(prompt, context)
```

## Performance

- **Evaluation Time**: O(n) where n = number of thresholds
- **Memory Usage**: O(n) for threshold tracking
- **Typical Performance**: < 1ms per evaluation

## Version History

- **v1.0.0** (2025-12-23): Initial implementation
  - Default thresholds: 100K, 150K
  - Duplicate prevention
  - State management
  - Comprehensive test suite

## Author

Context-Aware Memory System
Date: 2025-12-23

## Related Documentation

- [Memory Detector Base Class](./README.md)
- [Keyword Detector](./keyword_detector.py)
- [Project Switch Detector](./project_switch_detector.py)
