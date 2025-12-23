"""
Simple test runner for Entity Mention Detector (no pytest required)

Author: Context-Aware Memory System
Date: 2025-12-23
"""

import sys
from pathlib import Path
from unittest.mock import Mock
from datetime import datetime, timedelta

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

from memory_detectors.entity_mention_detector import EntityMentionDetector
from memory_cache import MemoryCache


class TestRunner:
    """Simple test runner"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def test(self, name):
        """Decorator for test functions"""
        def decorator(func):
            self.tests.append((name, func))
            return func
        return decorator

    def run(self):
        """Run all tests"""
        print("=" * 70)
        print("Running Entity Mention Detector Tests")
        print("=" * 70)

        for name, func in self.tests:
            try:
                print(f"\n[TEST] {name}...", end=" ")
                func()
                print("PASS")
                self.passed += 1
            except AssertionError as e:
                print(f"FAIL\n  {e}")
                self.failed += 1
            except Exception as e:
                print(f"ERROR\n  {type(e).__name__}: {e}")
                self.failed += 1

        print("\n" + "=" * 70)
        print(f"Results: {self.passed} passed, {self.failed} failed")
        print("=" * 70)

        return self.failed == 0


def create_mock_client():
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


def create_detector():
    """Create test detector instance"""
    config = {
        'enabled': True,
        'priority': 3,
        'min_entity_length': 2,
        'partial_match_threshold': 0.7
    }
    return EntityMentionDetector(config)


# Initialize test runner
runner = TestRunner()


@runner.test("Detector initialization")
def test_init():
    detector = create_detector()
    assert detector.name == "entity_mention_detector", "Wrong name"
    assert detector.enabled is True, "Should be enabled"
    assert detector.priority == 3, "Wrong priority"
    assert detector.min_entity_length == 2, "Wrong min_entity_length"


@runner.test("Exact match - case insensitive")
def test_exact_match():
    detector = create_detector()
    client = create_mock_client()
    detector.set_memory_client(client)

    test_cases = [
        "How does UserManager work?",
        "What is the usermanager doing?",
        "Tell me about USERMANAGER"
    ]

    for prompt in test_cases:
        result = detector.evaluate(prompt, {})
        assert result is not None, f"Failed to match in: {prompt}"
        assert result.triggered is True, "Should trigger"
        assert 'UserManager' in result.query_params['names'], "UserManager not in results"
        assert result.query_type == "entity_details", "Wrong query type"


@runner.test("Multiple entity mentions")
def test_multiple_entities():
    detector = create_detector()
    client = create_mock_client()
    detector.set_memory_client(client)

    prompt = "How does UserManager interact with PaymentService and Database?"
    result = detector.evaluate(prompt, {})

    assert result is not None, "Should match"
    assert len(result.query_params['names']) >= 3, "Should find at least 3 entities"
    assert 'UserManager' in result.query_params['names'], "Missing UserManager"
    assert 'PaymentService' in result.query_params['names'], "Missing PaymentService"
    assert 'Database' in result.query_params['names'], "Missing Database"


@runner.test("Partial fuzzy matching")
def test_fuzzy_match():
    detector = create_detector()
    client = create_mock_client()
    detector.set_memory_client(client)

    test_cases = [
        ("How does the payment service work?", "PaymentService"),
        ("Check the user manager code", "UserManager"),
        ("API gateway issues", "API Gateway"),
    ]

    for prompt, expected in test_cases:
        result = detector.evaluate(prompt, {})
        assert result is not None, f"Failed to match '{expected}' in: {prompt}"
        assert expected in result.query_params['names'], f"Missing {expected}"


@runner.test("Cache refresh after expiration")
def test_cache_refresh():
    detector = create_detector()
    client = create_mock_client()
    detector.set_memory_client(client)

    # First call - fetches from client
    result1 = detector.evaluate("What is UserManager?", {})
    assert result1 is not None, "First call should match"
    first_call_count = client.read_graph.call_count

    # Second call - uses cache
    result2 = detector.evaluate("What is UserManager?", {})
    assert result2 is not None, "Second call should match"
    assert client.read_graph.call_count == first_call_count, "Should use cache"

    # Simulate expiration
    detector.cache.cache_data['entity_names']['last_refresh'] = (
        datetime.now() - timedelta(seconds=301)
    ).isoformat()

    # Third call - refreshes cache
    result3 = detector.evaluate("What is UserManager?", {})
    assert result3 is not None, "Third call should match"
    assert client.read_graph.call_count > first_call_count, "Should refresh cache"


@runner.test("Entity name caching")
def test_entity_caching():
    detector = create_detector()
    client = create_mock_client()
    detector.set_memory_client(client)

    entity_names = detector.cache.get_entity_names(client)

    assert len(entity_names) == 6, f"Expected 6 entities, got {len(entity_names)}"
    assert 'UserManager' in entity_names, "Missing UserManager"
    assert 'PaymentService' in entity_names, "Missing PaymentService"
    assert 'API Gateway' in entity_names, "Missing API Gateway"

    stats = detector.cache.get_stats()
    assert stats['entity_names_count'] == 6, "Wrong cache count"
    assert stats['entity_names_valid'] is True, "Cache should be valid"


@runner.test("No match returns None")
def test_no_match():
    detector = create_detector()
    client = create_mock_client()
    detector.set_memory_client(client)

    prompts = [
        "Tell me about something completely unrelated",
        "What is the weather today?",
        "Random text with no entities"
    ]

    for prompt in prompts:
        result = detector.evaluate(prompt, {})
        assert result is None, f"Should not match: {prompt}"


@runner.test("Empty cache returns None")
def test_empty_cache():
    detector = create_detector()
    # Don't set memory client - cache will be empty

    result = detector.evaluate("What is UserManager?", {})
    assert result is None, "Empty cache should return None"


@runner.test("Short prompts skipped")
def test_short_prompts():
    detector = create_detector()
    client = create_mock_client()
    detector.set_memory_client(client)

    short_prompts = ["hi", "ok", "no"]

    for prompt in short_prompts:
        result = detector.evaluate(prompt, {})
        assert result is None, f"Should skip short prompt: {prompt}"


@runner.test("Code blocks skipped")
def test_code_blocks():
    detector = create_detector()
    client = create_mock_client()
    detector.set_memory_client(client)

    code_prompts = [
        "```python\nclass UserManager:\n    pass\n```",
        "    def user_manager():\n        return None"
    ]

    for prompt in code_prompts:
        result = detector.evaluate(prompt, {})
        assert result is None, f"Should skip code block: {prompt[:30]}"


@runner.test("TriggerResult structure")
def test_result_structure():
    detector = create_detector()
    client = create_mock_client()
    detector.set_memory_client(client)

    result = detector.evaluate("How does UserManager work?", {})

    assert result is not None, "Should match"
    assert result.triggered is True, "Should trigger"
    assert 0.0 <= result.confidence <= 1.0, f"Confidence {result.confidence} out of range"
    assert result.estimated_tokens == 100, "Wrong token estimate"
    assert result.query_type == "entity_details", "Wrong query type"
    assert 'names' in result.query_params, "Missing names param"
    assert isinstance(result.query_params['names'], list), "Names should be list"
    assert len(result.reason) > 0, "Reason should not be empty"


@runner.test("Confidence calculation")
def test_confidence():
    detector = create_detector()
    client = create_mock_client()
    detector.set_memory_client(client)

    # Exact match
    exact_result = detector.evaluate("What is UserManager?", {})
    assert exact_result is not None, "Exact match should work"

    # Partial match
    partial_result = detector.evaluate("Tell me about user management", {})

    if partial_result is not None:
        # If partial matches, exact should have higher or equal confidence
        assert exact_result.confidence >= partial_result.confidence, \
            "Exact match should have higher confidence"


@runner.test("Question mark boosts confidence")
def test_question_boost():
    detector = create_detector()
    client = create_mock_client()
    detector.set_memory_client(client)

    statement = "UserManager handles authentication"
    question = "What does UserManager handle?"

    result_statement = detector.evaluate(statement, {})
    result_question = detector.evaluate(question, {})

    assert result_statement is not None, "Statement should match"
    assert result_question is not None, "Question should match"
    # Question should have equal or higher confidence
    assert result_question.confidence >= result_statement.confidence, \
        "Question should boost confidence"


@runner.test("Entity with spaces")
def test_entity_spaces():
    detector = create_detector()
    client = create_mock_client()
    detector.set_memory_client(client)

    result = detector.evaluate("What is the API Gateway configuration?", {})

    assert result is not None, "Should match"
    assert 'API Gateway' in result.query_params['names'], "Missing API Gateway"


@runner.test("Fuzzy match scoring")
def test_fuzzy_scoring():
    detector = create_detector()

    # Exact word match
    score1 = detector._fuzzy_match('user', ['user', 'manager'])
    assert score1 == 1.0, f"Expected 1.0, got {score1}"

    # Substring match
    score2 = detector._fuzzy_match('user', ['username', 'other'])
    assert 0.5 <= score2 <= 1.0, f"Score {score2} out of expected range"

    # No match
    score3 = detector._fuzzy_match('user', ['other', 'words'])
    assert score3 < 0.7, f"Score {score3} should be low"


@runner.test("Word boundary matching")
def test_word_boundaries():
    detector = create_detector()
    client = Mock()
    client.read_graph.return_value = {
        'entities': [{'name': 'Session'}]
    }
    detector.set_memory_client(client)

    result = detector.evaluate("What is Session?", {})
    assert result is not None, "Should match Session"
    assert 'Session' in result.query_params['names'], "Missing Session"


@runner.test("Reason string format")
def test_reason_format():
    detector = create_detector()
    client = create_mock_client()
    detector.set_memory_client(client)

    result = detector.evaluate("What is UserManager?", {})

    assert result is not None, "Should match"
    assert "Mentioned" in result.reason, "Reason should contain 'Mentioned'"
    assert "entity" in result.reason.lower(), "Reason should mention entity"
    assert "UserManager" in result.reason, "Reason should include entity name"


if __name__ == "__main__":
    success = runner.run()
    sys.exit(0 if success else 1)
