"""
Memory Trigger Detector Base Classes

This module defines the abstract base class and data structures for all
memory trigger detectors. Each detector evaluates whether a memory graph
query should be triggered based on specific conditions.

Author: Context-Aware Memory System
Date: 2025-12-23
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class TriggerResult:
    """Result from a trigger detector evaluation"""

    triggered: bool
    """Whether this detector triggered"""

    confidence: float
    """Confidence score 0.0-1.0 (higher = more certain this trigger is relevant)"""

    estimated_tokens: int
    """Estimated token cost of the memory query"""

    query_type: str
    """Type of query: 'project_context', 'keyword_search', 'entity_details', 'threshold_check'"""

    query_params: Dict[str, Any]
    """Parameters for the memory query (query string, entity names, etc.)"""

    reason: str
    """Human-readable explanation of why this triggered"""

    def __str__(self) -> str:
        """String representation for logging"""
        return (f"TriggerResult(triggered={self.triggered}, "
                f"confidence={self.confidence:.2f}, "
                f"tokens={self.estimated_tokens}, "
                f"type={self.query_type}, "
                f"reason='{self.reason}')")


class MemoryDetector(ABC):
    """
    Abstract base class for all memory trigger detectors

    Each detector implements a specific trigger condition (e.g., keyword matching,
    project switching, entity mentions). Detectors are evaluated in priority order
    by the trigger engine.

    Usage:
        class MyDetector(MemoryDetector):
            def evaluate(self, prompt, context):
                if some_condition:
                    return TriggerResult(
                        triggered=True,
                        confidence=0.9,
                        estimated_tokens=150,
                        query_type="my_query",
                        query_params={"query": "search term"},
                        reason="Detected my condition"
                    )
                return None

            @property
            def name(self):
                return "my_detector"
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize detector with configuration

        Args:
            config: Detector-specific configuration dict
        """
        self.config = config
        self.enabled = config.get('enabled', True)
        self.priority = config.get('priority', 999)

    @abstractmethod
    def evaluate(self, prompt: str, context: Dict[str, Any]) -> Optional[TriggerResult]:
        """
        Evaluate if this detector should trigger

        Args:
            prompt: User's message text
            context: Session context dict with keys:
                - current_project: dict with project metadata
                - token_count: int, estimated tokens used this session
                - session_id: str, unique session identifier
                - cwd: str, current working directory
                - timestamp: str, ISO format timestamp

        Returns:
            TriggerResult if triggered, None otherwise
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique detector identifier

        Returns:
            Snake-case detector name (e.g., "keyword_detector")
        """
        pass

    def is_enabled(self) -> bool:
        """Check if this detector is enabled"""
        return self.enabled

    def __repr__(self) -> str:
        """String representation for debugging"""
        return f"{self.__class__.__name__}(name={self.name}, enabled={self.enabled}, priority={self.priority})"


class DetectorRegistry:
    """
    Registry for managing detector instances

    Provides methods to register, retrieve, and list detectors.
    Detectors are sorted by priority (lower number = higher priority).
    """

    def __init__(self):
        """Initialize empty registry"""
        self._detectors: List[MemoryDetector] = []

    def register(self, detector: MemoryDetector) -> None:
        """
        Register a detector

        Args:
            detector: MemoryDetector instance
        """
        self._detectors.append(detector)
        # Sort by priority (lower number = higher priority)
        self._detectors.sort(key=lambda d: d.priority)

    def get_enabled_detectors(self) -> List[MemoryDetector]:
        """
        Get all enabled detectors in priority order

        Returns:
            List of enabled MemoryDetector instances
        """
        return [d for d in self._detectors if d.is_enabled()]

    def get_detector(self, name: str) -> Optional[MemoryDetector]:
        """
        Get detector by name

        Args:
            name: Detector name

        Returns:
            MemoryDetector instance or None if not found
        """
        for detector in self._detectors:
            if detector.name == name:
                return detector
        return None

    def list_detectors(self) -> List[str]:
        """
        List all registered detector names

        Returns:
            List of detector names in priority order
        """
        return [d.name for d in self._detectors]

    def clear(self) -> None:
        """Clear all registered detectors"""
        self._detectors.clear()

    def __len__(self) -> int:
        """Number of registered detectors"""
        return len(self._detectors)

    def __repr__(self) -> str:
        """String representation"""
        return f"DetectorRegistry(count={len(self)}, detectors={self.list_detectors()})"


# Export public API
__all__ = [
    'MemoryDetector',
    'TriggerResult',
    'DetectorRegistry',
]
