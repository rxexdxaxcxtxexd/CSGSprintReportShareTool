"""
Tests for Token Threshold Detector

Tests threshold detection, duplicate prevention, state management,
and configuration handling.

Author: Context-Aware Memory System
Date: 2025-12-23
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from memory_detectors.token_threshold_detector import TokenThresholdDetector
from memory_detectors import TriggerResult


class TestTokenThresholdDetector:
    """Test suite for TokenThresholdDetector"""

    def test_initialization_with_defaults(self):
        """Test detector initializes with default configuration"""
        config = {'priority': 4, 'enabled': True}
        detector = TokenThresholdDetector(config)

        assert detector.name == "token_threshold_detector"
        assert detector.priority == 4
        assert detector.enabled is True
        assert detector.thresholds == [100000, 150000]
        assert len(detector.get_triggered_thresholds()) == 0

    def test_initialization_with_custom_thresholds(self):
        """Test detector can be initialized with custom thresholds"""
        config = {
            'priority': 4,
            'enabled': True,
            'thresholds': [50000, 100000, 200000]
        }
        detector = TokenThresholdDetector(config)

        assert detector.thresholds == [50000, 100000, 200000]

    def test_no_trigger_below_threshold(self):
        """Test detector does not trigger below thresholds"""
        config = {'priority': 4}
        detector = TokenThresholdDetector(config)

        context = {'token_count': 50000}
        result = detector.evaluate("any prompt", context)

        assert result is None

    def test_trigger_at_100k_threshold(self):
        """Test detector triggers at 100K token threshold"""
        config = {'priority': 4}
        detector = TokenThresholdDetector(config)

        context = {'token_count': 100000}
        result = detector.evaluate("any prompt", context)

        assert result is not None
        assert isinstance(result, TriggerResult)
        assert result.triggered is True
        assert result.query_type == "threshold_check"
        assert result.estimated_tokens == 175
        assert result.confidence >= 0.7
        assert result.query_params['threshold'] == 100000
        assert result.query_params['current_count'] == 100000
        assert 'pending' in result.query_params['search_terms']
        assert 'incomplete' in result.query_params['search_terms']
        assert '100,000' in result.reason
        assert 100000 in detector.get_triggered_thresholds()

    def test_trigger_at_150k_threshold(self):
        """Test detector triggers at 150K token threshold"""
        config = {'priority': 4}
        detector = TokenThresholdDetector(config)

        # At 150K, will trigger first threshold (100K) since none triggered yet
        context = {'token_count': 150000}
        result1 = detector.evaluate("any prompt", context)

        assert result1 is not None
        assert isinstance(result1, TriggerResult)
        assert result1.triggered is True
        assert result1.query_type == "threshold_check"
        assert result1.estimated_tokens == 175
        assert result1.query_params['threshold'] == 100000
        assert result1.query_params['current_count'] == 150000

        # Second evaluation should trigger 150K threshold
        result2 = detector.evaluate("any prompt", context)

        assert result2 is not None
        assert result2.query_params['threshold'] == 150000
        assert result2.query_params['current_count'] == 150000
        assert result2.confidence >= 0.8  # Higher confidence at 150K
        assert '150,000' in result2.reason
        assert 150000 in detector.get_triggered_thresholds()

    def test_no_duplicate_trigger_for_same_threshold(self):
        """Test detector prevents duplicate triggers for same threshold"""
        config = {'priority': 4}
        detector = TokenThresholdDetector(config)

        # First trigger at 100K
        context = {'token_count': 100000}
        result1 = detector.evaluate("prompt 1", context)
        assert result1 is not None
        assert result1.query_params['threshold'] == 100000

        # Second call at 105K should not trigger (same threshold)
        context = {'token_count': 105000}
        result2 = detector.evaluate("prompt 2", context)
        assert result2 is None

        # Third call at 110K should still not trigger (same threshold)
        context = {'token_count': 110000}
        result3 = detector.evaluate("prompt 3", context)
        assert result3 is None

        # Only one threshold should be tracked
        assert detector.get_triggered_thresholds() == [100000]

    def test_multiple_thresholds_triggered_sequentially(self):
        """Test detector triggers each threshold once as count increases"""
        config = {'priority': 4}
        detector = TokenThresholdDetector(config)

        # Trigger 100K
        context = {'token_count': 100000}
        result1 = detector.evaluate("prompt 1", context)
        assert result1 is not None
        assert result1.query_params['threshold'] == 100000

        # Trigger 150K
        context = {'token_count': 150000}
        result2 = detector.evaluate("prompt 2", context)
        assert result2 is not None
        assert result2.query_params['threshold'] == 150000

        # Both thresholds should be tracked
        assert detector.get_triggered_thresholds() == [100000, 150000]

        # No more triggers above 150K
        context = {'token_count': 200000}
        result3 = detector.evaluate("prompt 3", context)
        assert result3 is None

    def test_state_reset(self):
        """Test state reset clears triggered thresholds"""
        config = {'priority': 4}
        detector = TokenThresholdDetector(config)

        # Trigger 100K
        context = {'token_count': 100000}
        result1 = detector.evaluate("prompt 1", context)
        assert result1 is not None
        assert 100000 in detector.get_triggered_thresholds()

        # Reset state
        detector.reset_state()
        assert len(detector.get_triggered_thresholds()) == 0

        # Should be able to trigger again after reset
        context = {'token_count': 100000}
        result2 = detector.evaluate("prompt 2", context)
        assert result2 is not None
        assert result2.query_params['threshold'] == 100000

    def test_zero_token_count(self):
        """Test detector handles zero token count gracefully"""
        config = {'priority': 4}
        detector = TokenThresholdDetector(config)

        context = {'token_count': 0}
        result = detector.evaluate("any prompt", context)

        assert result is None

    def test_missing_token_count(self):
        """Test detector handles missing token_count in context"""
        config = {'priority': 4}
        detector = TokenThresholdDetector(config)

        context = {}  # No token_count key
        result = detector.evaluate("any prompt", context)

        assert result is None

    def test_negative_token_count(self):
        """Test detector handles negative token count gracefully"""
        config = {'priority': 4}
        detector = TokenThresholdDetector(config)

        context = {'token_count': -1000}
        result = detector.evaluate("any prompt", context)

        assert result is None

    def test_confidence_increases_with_threshold(self):
        """Test confidence score increases for higher thresholds"""
        config = {'priority': 4}

        # Test 100K threshold
        detector1 = TokenThresholdDetector(config)
        context1 = {'token_count': 100000}
        result1 = detector1.evaluate("prompt", context1)

        # Test 150K threshold
        detector2 = TokenThresholdDetector(config)
        context2 = {'token_count': 150000}
        result2 = detector2.evaluate("prompt", context2)

        assert result1 is not None
        assert result2 is not None
        assert result2.confidence > result1.confidence

    def test_confidence_boost_for_high_overage(self):
        """Test confidence increases when well past threshold"""
        config = {'priority': 4}
        detector = TokenThresholdDetector(config)

        # Just at threshold
        context1 = {'token_count': 100000}
        result1 = detector.evaluate("prompt", context1)

        # Reset and test well past threshold
        detector.reset_state()
        context2 = {'token_count': 115000}  # 15K over threshold
        result2 = detector.evaluate("prompt", context2)

        assert result1 is not None
        assert result2 is not None
        assert result2.confidence >= result1.confidence

    def test_custom_thresholds(self):
        """Test detector works with custom threshold values"""
        config = {
            'priority': 4,
            'thresholds': [25000, 75000, 125000]
        }
        detector = TokenThresholdDetector(config)

        # Trigger first custom threshold
        context = {'token_count': 25000}
        result1 = detector.evaluate("prompt", context)
        assert result1 is not None
        assert result1.query_params['threshold'] == 25000

        # Trigger second custom threshold
        context = {'token_count': 75000}
        result2 = detector.evaluate("prompt", context)
        assert result2 is not None
        assert result2.query_params['threshold'] == 75000

        # Trigger third custom threshold
        context = {'token_count': 125000}
        result3 = detector.evaluate("prompt", context)
        assert result3 is not None
        assert result3.query_params['threshold'] == 125000

        assert detector.get_triggered_thresholds() == [25000, 75000, 125000]

    def test_query_params_structure(self):
        """Test query_params contains expected fields"""
        config = {'priority': 4}
        detector = TokenThresholdDetector(config)

        context = {'token_count': 100000}
        result = detector.evaluate("any prompt", context)

        assert result is not None
        assert 'threshold' in result.query_params
        assert 'current_count' in result.query_params
        assert 'search_terms' in result.query_params
        assert isinstance(result.query_params['search_terms'], list)
        assert len(result.query_params['search_terms']) > 0

    def test_search_terms_include_pending_items(self):
        """Test search terms focus on pending/incomplete work"""
        config = {'priority': 4}
        detector = TokenThresholdDetector(config)

        context = {'token_count': 100000}
        result = detector.evaluate("any prompt", context)

        assert result is not None
        search_terms = result.query_params['search_terms']

        # Should include terms related to pending work
        assert any(term in search_terms for term in ['pending', 'incomplete', 'TODO', 'in progress'])

    def test_threshold_ordering(self):
        """Test thresholds are evaluated in ascending order"""
        config = {
            'priority': 4,
            'thresholds': [150000, 100000, 50000]  # Intentionally unsorted
        }
        detector = TokenThresholdDetector(config)

        # Should be sorted internally
        assert detector.thresholds == [50000, 100000, 150000]

        # At 150K, should trigger all three in order
        context = {'token_count': 150000}

        # First trigger should be lowest threshold
        result1 = detector.evaluate("prompt", context)
        assert result1 is not None
        assert result1.query_params['threshold'] == 50000


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v'])
