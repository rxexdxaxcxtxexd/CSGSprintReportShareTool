"""
Token Threshold Detector - Memory Trigger

Detects when token count crosses predefined thresholds (100K, 150K)
and triggers memory queries to help prevent context overflow.

Tracks triggered thresholds in instance state to prevent duplicate triggers
for the same threshold within a session.

Author: Context-Aware Memory System
Date: 2025-12-23
"""

from typing import Dict, List, Optional, Any, Set

from . import MemoryDetector, TriggerResult


class TokenThresholdDetector(MemoryDetector):
    """
    Detector for token count threshold crossings

    Triggers when the session's token count crosses predefined thresholds
    (100K or 150K tokens), suggesting it's time to check memory for
    pending items before context fills up.

    State Management:
        - Tracks which thresholds have been triggered in self._triggered
        - Prevents duplicate triggers for the same threshold
        - State persists for the lifetime of the detector instance
        - Reset when detector is re-initialized (new session)
    """

    # Default thresholds for triggering
    DEFAULT_THRESHOLDS = [100000, 150000]

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize token threshold detector

        Args:
            config: Configuration dict with optional keys:
                - thresholds: List[int] - Token count thresholds (default: [100000, 150000])
                - priority: int - Detector priority (default: 4)
                - enabled: bool - Whether detector is enabled
        """
        super().__init__(config)

        # Load thresholds from config or use defaults
        if 'thresholds' in config and isinstance(config['thresholds'], list):
            self.thresholds = sorted(config['thresholds'])
        else:
            self.thresholds = self.DEFAULT_THRESHOLDS.copy()

        # Track which thresholds have been triggered (prevent duplicates)
        self._triggered: Set[int] = set()

    @property
    def name(self) -> str:
        """Detector name"""
        return "token_threshold_detector"

    def evaluate(self, prompt: str, context: Dict[str, Any]) -> Optional[TriggerResult]:
        """
        Evaluate if token count has crossed a threshold

        Args:
            prompt: User's message text (not used by this detector)
            context: Session context with required key:
                - token_count: int - Current session token count

        Returns:
            TriggerResult if threshold crossed, None otherwise
        """
        # Get current token count from context
        token_count = context.get('token_count', 0)

        if token_count <= 0:
            return None

        # Check each threshold in order
        for threshold in self.thresholds:
            # Skip if already triggered this threshold
            if threshold in self._triggered:
                continue

            # Check if we've crossed this threshold
            if token_count >= threshold:
                # Mark as triggered to prevent duplicates
                self._triggered.add(threshold)

                # Calculate confidence based on how close to limit
                # Higher confidence as we approach context limit (typically 200K)
                confidence = self._calculate_confidence(token_count, threshold)

                return TriggerResult(
                    triggered=True,
                    confidence=confidence,
                    estimated_tokens=175,  # Fixed estimate from requirements
                    query_type="threshold_check",
                    query_params={
                        'threshold': threshold,
                        'current_count': token_count,
                        'search_terms': ['pending', 'incomplete', 'TODO', 'in progress']
                    },
                    reason=f"Token count ({token_count:,}) crossed threshold {threshold:,}"
                )

        return None

    def _calculate_confidence(self, token_count: int, threshold: int) -> float:
        """
        Calculate confidence score based on token count and threshold

        Higher confidence for higher thresholds (more urgent to check memory).

        Args:
            token_count: Current token count
            threshold: Threshold that was crossed

        Returns:
            Confidence score 0.0-1.0
        """
        # Base confidence increases with threshold level
        if threshold >= 150000:
            confidence = 0.9  # Very high - approaching limit
        elif threshold >= 100000:
            confidence = 0.8  # High - should start checking
        else:
            confidence = 0.7  # Moderate

        # Boost confidence if we're well past the threshold
        overage = token_count - threshold
        if overage > 10000:
            confidence = min(1.0, confidence + 0.1)

        return confidence

    def reset_state(self) -> None:
        """
        Reset detector state (clear triggered thresholds)

        Call this when starting a new session to allow thresholds
        to trigger again.
        """
        self._triggered.clear()

    def get_triggered_thresholds(self) -> List[int]:
        """
        Get list of thresholds that have been triggered

        Returns:
            Sorted list of triggered threshold values
        """
        return sorted(self._triggered)


# Export
__all__ = ['TokenThresholdDetector']
