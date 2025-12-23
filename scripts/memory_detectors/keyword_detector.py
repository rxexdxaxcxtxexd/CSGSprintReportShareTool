"""
Keyword Detector - Memory Trigger

Detects memory-related keywords in user prompts and triggers
contextual memory queries.

Supported keyword categories:
- Memory: "remember", "recall", "previously"
- Decisions: "why did we", "decided", "chose"
- Architecture: "architecture", "design", "pattern"
- Problems: "issue", "bug", "error", "blocker"

Author: Context-Aware Memory System
Date: 2025-12-23
"""

import re
from typing import Dict, List, Optional, Any

from . import MemoryDetector, TriggerResult


class KeywordDetector(MemoryDetector):
    """
    Detector for memory-related keywords in user prompts

    Triggers when user uses language suggesting they want to recall
    previous context, decisions, or patterns.
    """

    # Default keyword patterns
    DEFAULT_KEYWORDS = {
        "memory": [
            r"\b(remember|recall|previously|earlier|last\s+time)\b",
            r"\b(we\s+discussed|we\s+talked\s+about)\b",
            r"\b(from\s+before|mentioned\s+earlier)\b"
        ],
        "decision": [
            r"\b(why\s+did\s+we|how\s+did\s+we|when\s+did\s+we)\b",
            r"\b(decided|chose|selected|picked)\b",
            r"\b(decision|rationale|reasoning)\b"
        ],
        "architecture": [
            r"\b(architecture|architectural|design)\b",
            r"\b(pattern|approach|structure)\b",
            r"\b(implementation|strategy)\b"
        ],
        "problem": [
            r"\b(issue|problem|bug|error)\b",
            r"\b(blocker|challenge|difficulty)\b",
            r"\b(fix|resolve|solution)\b"
        ]
    }

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize keyword detector

        Args:
            config: Configuration dict with optional keys:
                - keywords: Dict[str, List[str]] - Custom keyword patterns
                - priority: int - Detector priority (default: 2)
                - enabled: bool - Whether detector is enabled
        """
        super().__init__(config)

        # Load keyword patterns
        if 'keywords' in config and isinstance(config['keywords'], dict):
            self.keywords = config['keywords']
        else:
            self.keywords = self.DEFAULT_KEYWORDS

        # Compile regex patterns
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        for category, patterns in self.keywords.items():
            self._compiled_patterns[category] = [
                re.compile(pattern, re.IGNORECASE)
                for pattern in patterns
            ]

    @property
    def name(self) -> str:
        """Detector name"""
        return "keyword_detector"

    def evaluate(self, prompt: str, context: Dict[str, Any]) -> Optional[TriggerResult]:
        """
        Evaluate if prompt contains memory-related keywords

        Args:
            prompt: User's message text
            context: Session context

        Returns:
            TriggerResult if keywords matched, None otherwise
        """
        # Skip if prompt is too short
        if len(prompt.strip()) < 5:
            return None

        # Check if prompt is inside code blocks (ignore those)
        if self._is_code_block(prompt):
            return None

        # Check each keyword category
        for category, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                match = pattern.search(prompt)
                if match:
                    # Extract context around the match
                    query_terms = self._extract_query_terms(prompt, match)

                    # Build query string
                    query = " ".join(query_terms)

                    # Determine confidence based on category
                    confidence = self._calculate_confidence(category, match, prompt)

                    return TriggerResult(
                        triggered=True,
                        confidence=confidence,
                        estimated_tokens=150,  # Conservative estimate
                        query_type="keyword_search",
                        query_params={
                            'query': query,
                            'category': category,
                            'matched_pattern': match.group(0)
                        },
                        reason=f"Keyword match: '{match.group(0)}' (category: {category})"
                    )

        return None

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

    def _extract_query_terms(self, prompt: str, match: re.Match) -> List[str]:
        """
        Extract query terms from prompt around the keyword match

        Args:
            prompt: Full prompt text
            match: Regex match object

        Returns:
            List of query terms
        """
        query_terms = []

        # Get words before and after the match
        start = max(0, match.start() - 50)
        end = min(len(prompt), match.end() + 50)
        context = prompt[start:end]

        # Extract quoted terms
        quoted = re.findall(r'"([^"]+)"', context)
        query_terms.extend(quoted)
        quoted = re.findall(r"'([^']+)'", context)
        query_terms.extend(quoted)

        # Extract technical terms (camelCase, snake_case, kebab-case)
        technical = re.findall(r'\b[a-z]+[A-Z][a-zA-Z]*\b', context)  # camelCase
        query_terms.extend(technical)
        technical = re.findall(r'\b[a-z]+_[a-z_]+\b', context)  # snake_case
        query_terms.extend(technical)

        # Extract capitalized words (potential entity names)
        capitalized = re.findall(r'\b[A-Z][a-z]+\b', context)
        query_terms.extend(capitalized[:3])  # Limit to 3

        # If no terms found, use words near the match
        if not query_terms:
            words = context.split()
            # Get words around the matched keyword
            match_words = match.group(0).split()
            for i, word in enumerate(words):
                if any(mw in word for mw in match_words):
                    # Get surrounding words
                    start_idx = max(0, i - 2)
                    end_idx = min(len(words), i + 3)
                    query_terms = words[start_idx:end_idx]
                    break

        # Remove duplicates, limit length
        seen = set()
        unique_terms = []
        for term in query_terms:
            if term.lower() not in seen:
                seen.add(term.lower())
                unique_terms.append(term)

        return unique_terms[:5]  # Limit to 5 terms

    def _calculate_confidence(self, category: str, match: re.Match, prompt: str) -> float:
        """
        Calculate confidence score for this trigger

        Args:
            category: Keyword category that matched
            match: Regex match object
            prompt: Full prompt text

        Returns:
            Confidence score 0.0-1.0
        """
        confidence = 0.7  # Base confidence

        # Higher confidence for explicit memory keywords
        if category == "memory":
            confidence = 0.9

        # Higher confidence for decision queries
        elif category == "decision":
            confidence = 0.85

        # Moderate confidence for architecture/problem queries
        elif category in ["architecture", "problem"]:
            confidence = 0.75

        # Boost confidence if prompt is a question
        if '?' in prompt:
            confidence = min(1.0, confidence + 0.1)

        # Boost confidence for longer, more specific prompts
        if len(prompt) > 50:
            confidence = min(1.0, confidence + 0.05)

        return confidence


# Export
__all__ = ['KeywordDetector']
