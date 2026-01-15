"""
Memory Trigger Engine - Core Orchestration

This module coordinates trigger detector evaluation and memory queries.
It enforces token budgets, manages state, and provides the main entry point
for trigger evaluation.

Author: Context-Aware Memory System
Date: 2025-12-23
"""

import json
import time
import uuid
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from memory_detectors import MemoryDetector, TriggerResult, DetectorRegistry
from memory_client import MemoryClient


class MemoryTriggerEngine:
    """
    Core orchestration engine for memory triggers

    Coordinates detector evaluation, memory queries, result ranking,
    and token budget enforcement.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize trigger engine

        Args:
            config_path: Path to configuration JSON file
                        Defaults to .claude/memory-trigger-config.json
        """
        # Determine paths
        self.home_dir = Path.home()
        self.claude_dir = self.home_dir / '.claude'
        self.config_path = config_path or (self.claude_dir / 'memory-trigger-config.json')
        self.state_path = self.claude_dir / 'memory-trigger-state.json'

        # Load configuration
        self.config = self._load_config()

        # Initialize components
        self.registry = DetectorRegistry()
        self.memory_client = MemoryClient(self.config.get('mcp', {}))

        # Load session state
        self.state = self._load_state()

        # Setup logging
        self._setup_logging()

        # Auto-register detectors from config
        self._initialize_detectors()

    def _setup_logging(self):
        """Configure rotating file logger for debugging and monitoring"""
        log_config = self.config.get('logging', {})
        log_level_name = log_config.get('level', 'INFO')
        log_level = getattr(logging, log_level_name, logging.INFO)
        log_file = Path.home() / log_config.get('file', '.claude/memory-trigger.log')
        max_bytes = log_config.get('max_size_mb', 10) * 1024 * 1024
        backup_count = log_config.get('backup_count', 3)

        # Create logger
        self.logger = logging.getLogger('memory_trigger')
        self.logger.setLevel(log_level)

        # Clear existing handlers to avoid duplicates
        self.logger.handlers = []

        # Rotating file handler
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )

        # Format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        self.logger.info("Memory trigger engine initialized")

    def register_detector(self, detector: MemoryDetector) -> None:
        """
        Register a detector

        Args:
            detector: MemoryDetector instance
        """
        self.registry.register(detector)

    def _initialize_detectors(self) -> None:
        """
        Auto-register detectors from configuration

        Dynamically loads and registers detectors based on config['detectors'].
        Handles import errors gracefully - missing detectors won't crash the engine.

        Special handling:
        - EntityMentionDetector: Requires set_memory_client() call after instantiation
        """
        detector_config = self.config.get('detectors', {})

        # Detector mapping: config_key -> (module_path, class_name, default_priority)
        DETECTOR_MAP = {
            'project_switch': ('memory_detectors.project_switch_detector', 'ProjectSwitchDetector', 1),
            'keyword': ('memory_detectors.keyword_detector', 'KeywordDetector', 2),
            'entity_mention': ('memory_detectors.entity_mention_detector', 'EntityMentionDetector', 3),
            'token_threshold': ('memory_detectors.token_threshold_detector', 'TokenThresholdDetector', 4),
        }

        registered_count = 0
        failed_count = 0

        for config_key, (module_path, class_name, default_priority) in DETECTOR_MAP.items():
            # Check if detector is enabled in config
            detector_settings = detector_config.get(config_key, {})
            if not detector_settings.get('enabled', False):
                self.logger.debug(f"Detector {config_key} is disabled, skipping")
                continue

            try:
                # Dynamic import
                module = __import__(module_path, fromlist=[class_name])
                detector_class = getattr(module, class_name)

                # Instantiate detector
                detector = detector_class(detector_settings)

                # Special handling for EntityMentionDetector
                if config_key == 'entity_mention' and hasattr(detector, 'set_memory_client'):
                    detector.set_memory_client(self.memory_client)
                    self.logger.debug(f"Set memory client for {detector.name}")

                # Register detector
                self.registry.register(detector)
                registered_count += 1
                self.logger.info(f"Auto-registered detector: {detector.name}")

            except ImportError as e:
                self.logger.warning(f"Could not import {class_name}: {e}")
                failed_count += 1
            except Exception as e:
                self.logger.error(f"Failed to initialize {class_name}: {e}")
                failed_count += 1

        self.logger.info(f"Detector auto-registration complete: {registered_count} registered, {failed_count} failed")

    def evaluate_triggers(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Optional[TriggerResult]:
        """
        Evaluate all registered detectors and return first trigger

        Detectors are evaluated in priority order. Returns immediately
        when a detector triggers (short-circuit evaluation).

        Args:
            prompt: User's message text
            context: Optional session context dict

        Returns:
            TriggerResult from first triggered detector, or None
        """
        self.logger.debug(f"Evaluating triggers for prompt: {prompt[:50]}...")

        # Build context
        if context is None:
            context = self._build_context()

        # Check token budget first
        if not self._check_budget():
            msg = f"Token budget exhausted ({self.state['tokens_used']}/{self.config['budget']['max_tokens_per_session']})"
            self.logger.warning(msg)
            print(f"[WARNING] {msg}")
            return None

        # Evaluate detectors in priority order
        detectors = self.registry.get_enabled_detectors()

        for detector in detectors:
            try:
                result = detector.evaluate(prompt, context)

                if result and result.triggered:
                    # Check if this specific trigger fits within budget
                    if not self._check_budget(result.estimated_tokens):
                        msg = f"Trigger {detector.name} would exceed budget, skipping"
                        self.logger.warning(msg)
                        print(f"[WARNING] {msg}")
                        continue

                    self.logger.info(f"Trigger fired: {result.query_type} (confidence: {result.confidence})")
                    return result

            except Exception as e:
                self.logger.error(f"Detector {detector.name} failed: {type(e).__name__}: {e}")
                if self.logger.level == logging.DEBUG:
                    import traceback
                    self.logger.debug(traceback.format_exc())
                print(f"[ERROR] Detector {detector.name} failed: {e}")
                continue

        self.logger.debug("No triggers fired")
        return None

    def query_memory(self, trigger_result: TriggerResult) -> Optional[Dict[str, Any]]:
        """
        Query memory server based on trigger result

        Args:
            trigger_result: TriggerResult from detector

        Returns:
            Memory query result dict or None on error
        """
        self.logger.debug(f"Querying memory: {trigger_result.query_type}")

        if not self.memory_client.is_available():
            self.logger.warning("MCP memory server unavailable")
            print("[WARNING] MCP memory server unavailable")
            return None

        query_type = trigger_result.query_type
        query_params = trigger_result.query_params

        try:
            # Route to appropriate query method
            if query_type == 'keyword_search':
                result = self.memory_client.search_nodes(query_params.get('query', ''))
            elif query_type == 'entity_details':
                result = self.memory_client.open_nodes(query_params.get('names', []))
            elif query_type == 'project_context':
                # Search for project-related entities
                project_name = query_params.get('project', '')
                result = self.memory_client.search_nodes(f"project:{project_name}")
            elif query_type == 'threshold_check':
                # Search for pending/incomplete items
                result = self.memory_client.search_nodes("status:pending OR status:incomplete")
            else:
                msg = f"Unknown query type: {query_type}"
                self.logger.warning(msg)
                print(f"[WARNING] {msg}")
                result = None

            # Update token usage
            if result:
                actual_tokens = self.memory_client.estimate_tokens(result)
                self._record_trigger(trigger_result, actual_tokens)
                self.logger.info(f"Memory query returned {len(result.get('entities', []))} entities")
            else:
                self.logger.warning("Memory query returned no results")

            return result

        except Exception as e:
            self.logger.error(f"Memory query failed: {type(e).__name__}: {e}")
            if self.logger.level == logging.DEBUG:
                import traceback
                self.logger.debug(traceback.format_exc())
            print(f"[ERROR] Memory query failed: {e}")
            return None

    def format_result(self, trigger_result: TriggerResult, memory_result: Optional[Dict[str, Any]]) -> str:
        """
        Format memory query result for display

        Args:
            trigger_result: Original trigger result
            memory_result: Memory query result

        Returns:
            Formatted string for user display
        """
        if not memory_result or not memory_result.get('entities'):
            return f"[{trigger_result.query_type.upper()}] No relevant memory found"

        # Build output
        lines = [
            f"[{trigger_result.query_type.upper()} TRIGGER]",
            f"Reason: {trigger_result.reason}",
            "",
            "Relevant Memory:"
        ]

        # Format entities
        entities = memory_result.get('entities', [])[:5]  # Limit to 5 most relevant

        for entity in entities:
            name = entity.get('name', 'Unknown')
            entity_type = entity.get('entityType', 'unknown')
            observations = entity.get('observations', [])

            lines.append(f"\n- [{entity_type}] {name}")
            for obs in observations[:3]:  # Limit to 3 observations per entity
                lines.append(f"  • {obs}")

        # Add token usage
        tokens = trigger_result.estimated_tokens
        lines.append(f"\n[Token cost: ~{tokens}]")

        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get current session statistics

        Returns:
            Dict with token usage, trigger counts, etc.
        """
        return {
            'session_id': self.state.get('session_id'),
            'session_start': self.state.get('session_start'),
            'tokens_used': self.state.get('tokens_used', 0),
            'tokens_budget': self.config['budget']['max_tokens_per_session'],
            'tokens_remaining': self.config['budget']['max_tokens_per_session'] - self.state.get('tokens_used', 0),
            'triggers_fired': len(self.state.get('triggers_fired', [])),
            'detectors_registered': len(self.registry),
            'detectors_enabled': len(self.registry.get_enabled_detectors()),
        }

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or use defaults"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARNING] Failed to load config: {e}, using defaults")

        # Default configuration
        return {
            "detectors": {
                "project_switch": {
                    "enabled": True,
                    "priority": 1,
                    "detect_branch_switch": True,
                    "major_branches": ["main", "master", "develop", "development"]
                },
                "keyword": {
                    "enabled": True,
                    "priority": 2
                }
            },
            "budget": {
                "max_tokens_per_session": 5000,
                "max_tokens_per_trigger": 500
            },
            "mcp": {
                "connection_timeout_seconds": 5,
                "query_timeout_seconds": 3
            }
        }

    def _load_state(self) -> Dict[str, Any]:
        """Load session state from file or create new"""
        if self.state_path.exists():
            try:
                with open(self.state_path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass

        # New session state
        return {
            "session_id": str(uuid.uuid4()),
            "session_start": datetime.now().isoformat(),
            "tokens_used": 0,
            "triggers_fired": []
        }

    def _save_state(self) -> None:
        """Save session state to file"""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_path, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"[WARNING] Failed to save state: {e}")

    def _build_context(self) -> Dict[str, Any]:
        """Build context dict for detectors"""
        return {
            'session_id': self.state['session_id'],
            'token_count': self.state.get('tokens_used', 0),
            'timestamp': datetime.now().isoformat(),
            'cwd': str(Path.cwd())
        }

    def _check_budget(self, additional_tokens: int = 0) -> bool:
        """
        Check if we have budget for additional tokens

        Args:
            additional_tokens: Tokens needed for next operation

        Returns:
            True if within budget, False otherwise
        """
        max_tokens = self.config['budget']['max_tokens_per_session']
        max_tokens_per_trigger = self.config['budget'].get('max_tokens_per_trigger')
        current_usage = self.state.get('tokens_used', 0)

        if max_tokens_per_trigger is not None and additional_tokens > max_tokens_per_trigger:
            return False

        return (current_usage + additional_tokens) <= max_tokens

    def _record_trigger(self, trigger_result: TriggerResult, actual_tokens: int) -> None:
        """
        Record a trigger event in state

        Args:
            trigger_result: TriggerResult that fired
            actual_tokens: Actual token cost
        """
        self.state['tokens_used'] = self.state.get('tokens_used', 0) + actual_tokens
        self.state['triggers_fired'].append({
            'timestamp': datetime.now().isoformat(),
            'detector': trigger_result.query_type,
            'tokens': actual_tokens,
            'reason': trigger_result.reason
        })
        self._save_state()


# Export public API
__all__ = ['MemoryTriggerEngine']
