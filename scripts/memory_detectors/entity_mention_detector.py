"""
Entity Mention Detector - Memory Trigger

Detects mentions of known entities in user prompts and triggers
entity detail queries from the memory graph.

Uses fuzzy matching to catch partial names and case-insensitive matching.
Caches entity names with 5-minute TTL for performance.

Author: Context-Aware Memory System
Date: 2025-12-23
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

from . import MemoryDetector, TriggerResult

try:
    from memory_cache import MemoryCache
except ImportError:
    # Try relative import if absolute fails
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from memory_cache import MemoryCache


class EntityMentionDetector(MemoryDetector):
    """
    Detector for entity mentions in user prompts

    Triggers when user mentions a known entity from the memory graph.
    Uses cached entity names with 5-minute refresh cycle.
    """

    # Cache refresh interval (5 minutes)
    CACHE_REFRESH_INTERVAL = 300  # seconds

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize entity mention detector

        Args:
            config: Configuration dict with optional keys:
                - priority: int - Detector priority (default: 3)
                - enabled: bool - Whether detector is enabled
                - min_entity_length: int - Minimum entity name length (default: 2)
                - partial_match_threshold: float - Min similarity for partial match (default: 0.7)
        """
        super().__init__(config)

        # Configuration
        self.min_entity_length = config.get('min_entity_length', 2)
        self.partial_match_threshold = config.get('partial_match_threshold', 0.7)

        # Initialize cache
        self.cache = MemoryCache()

        # Memory client (will be set by trigger engine)
        self._memory_client = None

    @property
    def name(self) -> str:
        """Detector name"""
        return "entity_mention_detector"

    def set_memory_client(self, client: Any) -> None:
        """
        Set the memory client for cache refresh

        Args:
            client: MCP memory client instance
        """
        self._memory_client = client

    def evaluate(self, prompt: str, context: Dict[str, Any]) -> Optional[TriggerResult]:
        """
        Evaluate if prompt mentions known entities

        Args:
            prompt: User's message text
            context: Session context

        Returns:
            TriggerResult if entities matched, None otherwise
        """
        # Skip if prompt is too short
        if len(prompt.strip()) < 3:
            return None

        # Skip if prompt is inside code blocks
        if self._is_code_block(prompt):
            return None

        # Get cached entity names (will auto-refresh if expired)
        entity_names = self.cache.get_entity_names(self._memory_client)

        if not entity_names:
            # No entities in cache - nothing to match
            return None

        # Find entity mentions in prompt
        matched_entities = self._find_entity_mentions(prompt, entity_names)

        if not matched_entities:
            return None

        # Calculate confidence based on match quality
        confidence = self._calculate_confidence(matched_entities, prompt)

        # Build reason string
        entity_list = ", ".join([f"'{e['name']}'" for e in matched_entities[:3]])
        if len(matched_entities) > 3:
            entity_list += f" (+{len(matched_entities) - 3} more)"

        reason = f"Mentioned {len(matched_entities)} known entity(ies): {entity_list}"

        return TriggerResult(
            triggered=True,
            confidence=confidence,
            estimated_tokens=100,  # Entity detail queries are relatively small
            query_type="entity_details",
            query_params={
                'names': [e['name'] for e in matched_entities]
            },
            reason=reason
        )

    def _find_entity_mentions(self, prompt: str, entity_names: List[str]) -> List[Dict[str, Any]]:
        """
        Find entity mentions in prompt using fuzzy matching

        Args:
            prompt: User's prompt text
            entity_names: List of known entity names

        Returns:
            List of matched entities with match info:
                - name: str - Entity name
                - match_type: str - 'exact' or 'partial'
                - match_score: float - Match quality 0.0-1.0
        """
        matches = []
        prompt_lower = prompt.lower()

        # Normalize prompt for matching (remove punctuation, split into words)
        prompt_words = self._extract_words(prompt_lower)

        for entity_name in entity_names:
            # Skip very short entity names
            if len(entity_name) < self.min_entity_length:
                continue

            entity_lower = entity_name.lower()

            # Try exact match first (case-insensitive)
            if self._contains_word(prompt_lower, entity_lower):
                matches.append({
                    'name': entity_name,
                    'match_type': 'exact',
                    'match_score': 1.0
                })
                continue

            # Try partial/fuzzy match
            partial_score = self._fuzzy_match(entity_lower, prompt_words)
            if partial_score >= self.partial_match_threshold:
                matches.append({
                    'name': entity_name,
                    'match_type': 'partial',
                    'match_score': partial_score
                })

        # Sort by match score (best first)
        matches.sort(key=lambda x: x['match_score'], reverse=True)

        # Limit to top 10 matches to avoid overwhelming
        return matches[:10]

    def _extract_words(self, text: str) -> List[str]:
        """
        Extract words from text, removing punctuation

        Args:
            text: Text to process

        Returns:
            List of words
        """
        # Remove punctuation and split
        words = re.findall(r'\b\w+\b', text)
        return [w for w in words if len(w) >= self.min_entity_length]

    def _contains_word(self, text: str, word: str) -> bool:
        """
        Check if text contains word as a complete word (not substring)

        Args:
            text: Text to search in
            word: Word to search for

        Returns:
            True if word found as complete word
        """
        # Use word boundary regex
        pattern = r'\b' + re.escape(word) + r'\b'
        return bool(re.search(pattern, text, re.IGNORECASE))

    def _fuzzy_match(self, entity_name: str, prompt_words: List[str]) -> float:
        """
        Calculate fuzzy match score between entity name and prompt words

        Uses simple substring and word overlap scoring.

        Args:
            entity_name: Entity name to match
            prompt_words: List of words from prompt

        Returns:
            Match score 0.0-1.0
        """
        entity_words = self._extract_words(entity_name)

        if not entity_words or not prompt_words:
            return 0.0

        # Strategy 1: Check if any prompt word contains entity word (or vice versa)
        max_substring_score = 0.0
        for entity_word in entity_words:
            for prompt_word in prompt_words:
                # Check substring match
                if entity_word in prompt_word or prompt_word in entity_word:
                    # Calculate similarity based on length ratio
                    similarity = min(len(entity_word), len(prompt_word)) / max(len(entity_word), len(prompt_word))
                    max_substring_score = max(max_substring_score, similarity)

        # Strategy 2: Calculate word overlap ratio
        entity_word_set = set(entity_words)
        prompt_word_set = set(prompt_words)
        overlap = len(entity_word_set.intersection(prompt_word_set))
        overlap_score = overlap / len(entity_word_set) if entity_word_set else 0.0

        # Use the best score from both strategies
        return max(max_substring_score, overlap_score)

    def _calculate_confidence(self, matched_entities: List[Dict[str, Any]], prompt: str) -> float:
        """
        Calculate confidence score for this trigger

        Args:
            matched_entities: List of matched entities
            prompt: Full prompt text

        Returns:
            Confidence score 0.0-1.0
        """
        # Base confidence on number and quality of matches
        confidence = 0.6  # Base confidence

        if not matched_entities:
            return 0.0

        # Boost for exact matches
        exact_matches = [e for e in matched_entities if e['match_type'] == 'exact']
        if exact_matches:
            confidence = 0.8
            # Higher boost for multiple exact matches
            if len(exact_matches) > 1:
                confidence = 0.9

        # Average match score
        avg_score = sum(e['match_score'] for e in matched_entities) / len(matched_entities)
        confidence = min(1.0, confidence * avg_score)

        # Boost if prompt is a question about the entity
        if '?' in prompt:
            confidence = min(1.0, confidence + 0.05)

        # Boost for longer, more context-rich prompts
        if len(prompt) > 50:
            confidence = min(1.0, confidence + 0.05)

        return round(confidence, 2)

    def _is_code_block(self, text: str) -> bool:
        """
        Check if text appears to be inside a code block

        Args:
            text: Text to check

        Returns:
            True if looks like code, False otherwise
        """
        # Simple heuristic: code blocks often have ``` or indentation
        if text.strip().startswith('```') or text.strip().startswith('    '):
            return True

        # Check for high density of special characters (code-like)
        special_chars = sum(1 for c in text if c in '(){}<>[];:,.')
        if len(text) > 0 and (special_chars / len(text)) > 0.3:
            return True

        return False


# Export
__all__ = ['EntityMentionDetector']
