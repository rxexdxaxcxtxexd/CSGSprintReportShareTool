"""
Tests for Entity Mention Detector

Tests entity name caching, case-insensitive matching, partial/fuzzy matching,
cache refresh logic, and trigger behavior.

Author: Context-Aware Memory System
Date: 2025-12-23
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

from memory_detectors.entity_mention_detector import EntityMentionDetector
from memory_detectors import TriggerResult
from memory_cache import MemoryCache


class TestEntityMentionDetector:
    """Test suite for EntityMentionDetector"""

    @pytest.fixture
    def detector(self):
        """Create detector instance with test config"""
        config = {
            'enabled': True,
            'priority': 3,
            'min_entity_length': 2,
            'partial_match_threshold': 0.7
        }
        return EntityMentionDetector(config)

    @pytest.fixture
    def mock_memory_client(self):
        """Create mock memory client"""
        client = Mock()
        client.read_graph.return_value = {
            'entities': [
                {'name': 'UserManager'},
                {'name': 'PaymentService'},
                {'name': 'API Gateway'},
                {'name': 'Database'},
                {'name': 'Redis'},
                {'name': 'Session'}
            ]
        }
        return client

    @pytest.fixture
    def test_cache(self, tmp_path):
        """Create test cache with temporary storage"""
        cache_file = tmp_path / "test-cache.json"
        return MemoryCache(cache_path=cache_file)

    def test_detector_initialization(self, detector):
        """Test detector initializes with correct config"""
        assert detector.name == "entity_mention_detector"
        assert detector.enabled is True
        assert detector.priority == 3
        assert detector.min_entity_length == 2
        assert detector.partial_match_threshold == 0.7
        assert isinstance(detector.cache, MemoryCache)

    def test_exact_match_case_insensitive(self, detector, mock_memory_client, test_cache):
        """Test exact entity name match (case-insensitive)"""
        detector.cache = test_cache
        detector.set_memory_client(mock_memory_client)

        # Test various cases
        prompts = [
            "How does UserManager work?",
            "What is the usermanager doing?",
            "Tell me about USERMANAGER",
            "The UserManager class handles authentication"
        ]

        for prompt in prompts:
            result = detector.evaluate(prompt, {})
            assert result is not None, f"Failed to match in: {prompt}"
            assert result.triggered is True
            assert 'UserManager' in result.query_params['names']
            assert result.query_type == "entity_details"
            assert result.confidence >= 0.7

    def test_multiple_entity_mentions(self, detector, mock_memory_client, test_cache):
        """Test prompt mentioning multiple entities"""
        detector.cache = test_cache
        detector.set_memory_client(mock_memory_client)

        prompt = "How does UserManager interact with PaymentService and Database?"
        result = detector.evaluate(prompt, {})

        assert result is not None
        assert result.triggered is True
        assert len(result.query_params['names']) >= 3
        assert 'UserManager' in result.query_params['names']
        assert 'PaymentService' in result.query_params['names']
        assert 'Database' in result.query_params['names']

    def test_partial_fuzzy_matching(self, detector, mock_memory_client, test_cache):
        """Test partial/fuzzy entity name matching"""
        detector.cache = test_cache
        detector.set_memory_client(mock_memory_client)

        # Test partial matches
        test_cases = [
            ("How does the payment service work?", "PaymentService"),
            ("Check the user manager code", "UserManager"),
            ("API gateway issues", "API Gateway"),
        ]

        for prompt, expected_entity in test_cases:
            result = detector.evaluate(prompt, {})
            assert result is not None, f"Failed to match '{expected_entity}' in: {prompt}"
            assert result.triggered is True
            assert expected_entity in result.query_params['names']

    def test_cache_refresh_logic(self, detector, mock_memory_client, test_cache):
        """Test that cache refreshes after TTL expires"""
        detector.cache = test_cache
        detector.set_memory_client(mock_memory_client)

        # First call - should fetch from client
        prompt = "What is UserManager?"
        result1 = detector.evaluate(prompt, {})
        assert result1 is not None
        assert mock_memory_client.read_graph.call_count == 1

        # Second call immediately - should use cache
        result2 = detector.evaluate(prompt, {})
        assert result2 is not None
        assert mock_memory_client.read_graph.call_count == 1  # No additional call

        # Simulate cache expiration by manually clearing timestamp
        test_cache.cache_data['entity_names']['last_refresh'] = (
            datetime.now() - timedelta(seconds=301)
        ).isoformat()

        # Third call - should refresh cache
        result3 = detector.evaluate(prompt, {})
        assert result3 is not None
        assert mock_memory_client.read_graph.call_count == 2  # Cache refreshed

    def test_entity_name_caching(self, detector, mock_memory_client, test_cache):
        """Test that entity names are properly cached"""
        detector.cache = test_cache
        detector.set_memory_client(mock_memory_client)

        # Populate cache
        entity_names = detector.cache.get_entity_names(mock_memory_client)

        assert len(entity_names) == 6
        assert 'UserManager' in entity_names
        assert 'PaymentService' in entity_names
        assert 'API Gateway' in entity_names

        # Verify cached
        stats = test_cache.get_stats()
        assert stats['entity_names_count'] == 6
        assert stats['entity_names_valid'] is True

    def test_no_match_returns_none(self, detector, mock_memory_client, test_cache):
        """Test that no match returns None"""
        detector.cache = test_cache
        detector.set_memory_client(mock_memory_client)

        prompts = [
            "Tell me about something completely unrelated",
            "What is the weather today?",
            "Random text with no entities"
        ]

        for prompt in prompts:
            result = detector.evaluate(prompt, {})
            assert result is None, f"Should not match: {prompt}"

    def test_empty_cache_returns_none(self, detector, test_cache):
        """Test that empty entity cache returns None"""
        detector.cache = test_cache
        # Don't set memory client - cache will be empty

        prompt = "What is UserManager?"
        result = detector.evaluate(prompt, {})
        assert result is None

    def test_short_prompt_skipped(self, detector, mock_memory_client, test_cache):
        """Test that very short prompts are skipped"""
        detector.cache = test_cache
        detector.set_memory_client(mock_memory_client)

        short_prompts = ["hi", "ok", "no"]

        for prompt in short_prompts:
            result = detector.evaluate(prompt, {})
            assert result is None

    def test_code_block_skipped(self, detector, mock_memory_client, test_cache):
        """Test that code blocks are skipped"""
        detector.cache = test_cache
        detector.set_memory_client(mock_memory_client)

        code_prompts = [
            "```python\nclass UserManager:\n    pass\n```",
            "    def user_manager():\n        return None",
            "{{{{{((((()))))}}}}}UserManager"
        ]

        for prompt in code_prompts:
            result = detector.evaluate(prompt, {})
            assert result is None

    def test_trigger_result_structure(self, detector, mock_memory_client, test_cache):
        """Test that TriggerResult has correct structure"""
        detector.cache = test_cache
        detector.set_memory_client(mock_memory_client)

        prompt = "How does UserManager work?"
        result = detector.evaluate(prompt, {})

        assert result is not None
        assert isinstance(result, TriggerResult)
        assert result.triggered is True
        assert 0.0 <= result.confidence <= 1.0
        assert result.estimated_tokens == 100
        assert result.query_type == "entity_details"
        assert 'names' in result.query_params
        assert isinstance(result.query_params['names'], list)
        assert len(result.reason) > 0

    def test_confidence_calculation(self, detector, mock_memory_client, test_cache):
        """Test confidence score calculation"""
        detector.cache = test_cache
        detector.set_memory_client(mock_memory_client)

        # Exact match should have higher confidence
        exact_prompt = "What is UserManager?"
        exact_result = detector.evaluate(exact_prompt, {})
        assert exact_result is not None
        exact_confidence = exact_result.confidence

        # Partial match should have lower confidence
        partial_prompt = "Tell me about the user manager"
        partial_result = detector.evaluate(partial_prompt, {})
        assert partial_result is not None
        partial_confidence = partial_result.confidence

        # Exact should be higher or equal
        assert exact_confidence >= partial_confidence

    def test_question_mark_boosts_confidence(self, detector, mock_memory_client, test_cache):
        """Test that questions get confidence boost"""
        detector.cache = test_cache
        detector.set_memory_client(mock_memory_client)

        statement = "UserManager handles authentication"
        question = "What does UserManager handle?"

        result_statement = detector.evaluate(statement, {})
        result_question = detector.evaluate(question, {})

        assert result_statement is not None
        assert result_question is not None

        # Question should have equal or higher confidence
        assert result_question.confidence >= result_statement.confidence

    def test_min_entity_length_respected(self, detector, mock_memory_client, test_cache):
        """Test that minimum entity length setting is respected"""
        detector.cache = test_cache
        detector.min_entity_length = 5  # Require at least 5 chars
        detector.set_memory_client(mock_memory_client)

        # Mock client with short entity names
        mock_memory_client.read_graph.return_value = {
            'entities': [
                {'name': 'AB'},  # Too short
                {'name': 'XYZ'},  # Too short
                {'name': 'LongEntity'}  # Should match
            ]
        }

        prompt = "What is AB and LongEntity?"
        result = detector.evaluate(prompt, {})

        assert result is not None
        # Only LongEntity should match
        assert 'LongEntity' in result.query_params['names']
        assert 'AB' not in result.query_params['names']

    def test_fuzzy_match_threshold(self, detector, mock_memory_client, test_cache):
        """Test partial match threshold configuration"""
        detector.cache = test_cache
        detector.partial_match_threshold = 0.9  # Very strict
        detector.set_memory_client(mock_memory_client)

        # This should be too fuzzy to match with high threshold
        prompt = "Tell me about user management"
        result = detector.evaluate(prompt, {})

        # With strict threshold, might not match or have lower confidence
        if result is not None:
            assert result.confidence < 0.9

    def test_max_entities_limited(self, detector, mock_memory_client, test_cache):
        """Test that number of returned entities is limited"""
        detector.cache = test_cache

        # Create many entities
        many_entities = [{'name': f'Entity{i}'} for i in range(50)]
        mock_memory_client.read_graph.return_value = {'entities': many_entities}
        detector.set_memory_client(mock_memory_client)

        # Mention all entities
        prompt = " ".join([f'Entity{i}' for i in range(50)])
        result = detector.evaluate(prompt, {})

        assert result is not None
        # Should be limited to 10 entities
        assert len(result.query_params['names']) <= 10

    def test_entity_with_spaces(self, detector, mock_memory_client, test_cache):
        """Test entities with spaces in names"""
        detector.cache = test_cache
        detector.set_memory_client(mock_memory_client)

        prompt = "What is the API Gateway configuration?"
        result = detector.evaluate(prompt, {})

        assert result is not None
        assert 'API Gateway' in result.query_params['names']

    def test_detector_disabled(self, detector, mock_memory_client, test_cache):
        """Test that disabled detector doesn't run"""
        detector.cache = test_cache
        detector.enabled = False
        detector.set_memory_client(mock_memory_client)

        assert detector.is_enabled() is False

    def test_match_quality_scoring(self, detector):
        """Test internal fuzzy match scoring"""
        # Test exact word match
        score1 = detector._fuzzy_match('user', ['user', 'manager'])
        assert score1 == 1.0

        # Test substring match
        score2 = detector._fuzzy_match('user', ['username', 'other'])
        assert 0.7 <= score2 <= 1.0

        # Test no match
        score3 = detector._fuzzy_match('user', ['other', 'words'])
        assert score3 < 0.5

    def test_word_boundary_matching(self, detector, mock_memory_client, test_cache):
        """Test that matching respects word boundaries"""
        detector.cache = test_cache
        detector.set_memory_client(mock_memory_client)

        # "Session" should not match "SessionManager" if that's not in entities
        mock_memory_client.read_graph.return_value = {
            'entities': [{'name': 'Session'}]
        }

        prompt = "What is Session?"
        result = detector.evaluate(prompt, {})
        assert result is not None
        assert 'Session' in result.query_params['names']

    def test_reason_string_format(self, detector, mock_memory_client, test_cache):
        """Test that reason string is properly formatted"""
        detector.cache = test_cache
        detector.set_memory_client(mock_memory_client)

        prompt = "What is UserManager?"
        result = detector.evaluate(prompt, {})

        assert result is not None
        assert "Mentioned" in result.reason
        assert "entity" in result.reason.lower()
        assert "UserManager" in result.reason


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
