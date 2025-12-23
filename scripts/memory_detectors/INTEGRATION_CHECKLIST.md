# Token Threshold Detector - Integration Checklist

## Pre-Integration Verification

### Files Created ✓
- [x] `token_threshold_detector.py` - Core implementation (5.5 KB)
- [x] `test_token_threshold_detector.py` - Test suite (12 KB, 17 tests)
- [x] `example_usage.py` - Usage examples (4.8 KB)
- [x] `README_TOKEN_THRESHOLD.md` - Documentation (8.0 KB)
- [x] `IMPLEMENTATION_SUMMARY.md` - Implementation details
- [x] `INTEGRATION_CHECKLIST.md` - This file

### Requirements Validation ✓
- [x] Inherits from `MemoryDetector` base class
- [x] Implements `evaluate()` method correctly
- [x] Implements `name` property returning "token_threshold_detector"
- [x] Triggers at 100,000 tokens
- [x] Triggers at 150,000 tokens
- [x] Reads `token_count` from `context` parameter
- [x] Tracks triggered thresholds in instance state
- [x] Prevents duplicate triggers for same threshold
- [x] Priority set to 4
- [x] Estimated tokens set to 175
- [x] Query type set to "threshold_check"
- [x] Returns `TriggerResult` with proper structure
- [x] Query params include search terms for pending/incomplete items

### Test Coverage ✓
- [x] All 17 tests pass (100% pass rate)
- [x] Threshold detection at 100K tested
- [x] Threshold detection at 150K tested
- [x] Duplicate prevention tested
- [x] State reset tested
- [x] Edge cases tested (zero, negative, missing token_count)
- [x] Custom thresholds tested
- [x] Confidence scoring tested
- [x] Query parameter structure validated

### Example Verification ✓
- [x] Basic usage example works
- [x] Custom thresholds example works
- [x] DetectorRegistry integration example works
- [x] State management example works
- [x] Query parameters example works

## Integration Steps

### Step 1: Import the Detector
```python
from memory_detectors.token_threshold_detector import TokenThresholdDetector
```

### Step 2: Create and Configure
```python
config = {
    'priority': 4,              # Evaluation order (lower = earlier)
    'enabled': True,            # Enable/disable detector
    'thresholds': [100000, 150000]  # Optional: custom thresholds
}
detector = TokenThresholdDetector(config)
```

### Step 3: Register with Registry (if using)
```python
from memory_detectors import DetectorRegistry

registry = DetectorRegistry()
registry.register(detector)
```

### Step 4: Evaluate in Session Loop
```python
def on_user_message(message: str, session_context: dict):
    # Update session context with current token count
    session_context['token_count'] = calculate_token_count()

    # Evaluate detector
    result = detector.evaluate(message, session_context)

    # Handle trigger
    if result:
        handle_memory_trigger(result)
```

### Step 5: Implement Memory Query Handler
```python
def handle_memory_trigger(result: TriggerResult):
    """Handle token threshold trigger"""
    threshold = result.query_params['threshold']
    current = result.query_params['current_count']
    search_terms = result.query_params['search_terms']

    print(f"Token threshold {threshold:,} crossed at {current:,} tokens")
    print(f"Querying memory for: {', '.join(search_terms)}")

    # Query memory graph
    memory_results = query_memory_graph(search_terms)

    # Process results
    for item in memory_results:
        print(f"  - {item}")
```

### Step 6: Reset State on New Session
```python
def start_new_session():
    """Initialize new session"""
    # Reset detector state
    detector.reset_state()

    # Clear session context
    session_context = {
        'token_count': 0,
        'session_id': generate_session_id(),
        'timestamp': datetime.now().isoformat()
    }

    return session_context
```

## Testing Integration

### Unit Tests
```bash
cd /c/Users/layden/scripts
python -m pytest tests/test_token_threshold_detector.py -v
```

Expected: 17 passed in ~0.05s

### Integration Tests
```python
def test_integration():
    """Test full integration workflow"""
    detector = TokenThresholdDetector({'priority': 4})

    # Simulate session progression
    contexts = [
        {'token_count': 50000},   # No trigger
        {'token_count': 100000},  # Trigger 1
        {'token_count': 105000},  # No trigger (duplicate)
        {'token_count': 150000},  # Trigger 2
    ]

    results = []
    for ctx in contexts:
        result = detector.evaluate("test", ctx)
        results.append(result)

    assert results[0] is None          # No trigger at 50K
    assert results[1] is not None      # Trigger at 100K
    assert results[2] is None          # No duplicate at 105K
    assert results[3] is not None      # Trigger at 150K
```

### Manual Smoke Test
```bash
cd /c/Users/layden/scripts
python memory_detectors/example_usage.py
```

Expected: All 5 examples run without errors

## Production Deployment

### Configuration
Add to your detector configuration file:
```json
{
  "detectors": [
    {
      "name": "token_threshold_detector",
      "enabled": true,
      "priority": 4,
      "config": {
        "thresholds": [100000, 150000]
      }
    }
  ]
}
```

### Monitoring
Track these metrics:
- [ ] Number of threshold triggers per session
- [ ] Average token count at trigger time
- [ ] Time between triggers
- [ ] Memory query success rate
- [ ] False positive rate (triggers without useful results)

### Performance Benchmarks
Expected performance:
- Evaluation time: < 1ms
- Memory usage: < 1 KB per detector instance
- CPU usage: Negligible (simple threshold comparisons)

## Troubleshooting

### Issue: Detector Not Triggering
**Check:**
- [ ] Detector is enabled (`detector.enabled == True`)
- [ ] Context contains `token_count` key
- [ ] Token count is > 0 and >= threshold
- [ ] Threshold hasn't already been triggered

**Solution:**
```python
print(f"Enabled: {detector.enabled}")
print(f"Token count: {context.get('token_count', 'MISSING')}")
print(f"Triggered: {detector.get_triggered_thresholds()}")
```

### Issue: Duplicate Triggers
**Check:**
- [ ] Not resetting state too frequently
- [ ] Using same detector instance across evaluations
- [ ] State tracking is working (`_triggered` set is populated)

**Solution:**
```python
# Check state
print(f"Triggered thresholds: {detector.get_triggered_thresholds()}")

# Reset if needed
detector.reset_state()
```

### Issue: Wrong Threshold Triggered
**Check:**
- [ ] Thresholds are in ascending order
- [ ] Sequential evaluation is working correctly
- [ ] Previous thresholds haven't been skipped

**Solution:**
```python
# Verify threshold order
print(f"Thresholds: {detector.thresholds}")
print(f"Already triggered: {detector.get_triggered_thresholds()}")
```

## Rollback Plan

If integration fails:
1. Disable detector: `config['enabled'] = False`
2. Remove from registry: `registry.clear()`
3. Restore previous detector configuration
4. Report issues with test results

## Post-Integration Validation

### Week 1
- [ ] Monitor trigger frequency
- [ ] Validate memory query results
- [ ] Check for false positives
- [ ] Review performance metrics

### Week 2
- [ ] Analyze threshold effectiveness
- [ ] Adjust thresholds if needed
- [ ] Review user feedback
- [ ] Document lessons learned

### Week 3
- [ ] Optimize configuration
- [ ] Update documentation
- [ ] Train team on usage
- [ ] Create runbook

## Success Criteria

Integration is successful when:
- [x] All tests pass
- [ ] Detector triggers at correct thresholds
- [ ] No duplicate triggers observed
- [ ] Memory queries return useful results
- [ ] Performance meets benchmarks
- [ ] No errors in production logs
- [ ] Team is trained and comfortable with system

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | Claude Sonnet 4.5 | 2025-12-23 | ✓ |
| QA | - | - | - |
| Tech Lead | - | - | - |
| Product Owner | - | - | - |

## Next Steps

After integration:
1. Monitor production usage for 1 week
2. Gather metrics and feedback
3. Optimize thresholds based on data
4. Document best practices
5. Consider additional detectors:
   - Context window percentage detector
   - Session duration detector
   - Activity-based detector

## Resources

- Implementation: `C:\Users\layden\scripts\memory_detectors\token_threshold_detector.py`
- Tests: `C:\Users\layden\scripts\tests\test_token_threshold_detector.py`
- Documentation: `C:\Users\layden\scripts\memory_detectors\README_TOKEN_THRESHOLD.md`
- Examples: `C:\Users\layden\scripts\memory_detectors\example_usage.py`

---

**Status**: Ready for Integration
**Version**: 1.0.0
**Last Updated**: 2025-12-23
