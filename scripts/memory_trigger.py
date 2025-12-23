#!/usr/bin/env python3
"""
Memory Trigger - CLI Entry Point

Command-line interface for the context-aware memory trigger system.
Can be called manually or from Claude Code hooks.

Usage:
    python memory_trigger.py --prompt "Remember our decision?"
    python memory_trigger.py --stdin  # Read from stdin JSON
    python memory_trigger.py --stats  # Show usage statistics
    python memory_trigger.py --test   # Test mode (no MCP calls)

Author: Context-Aware Memory System
Date: 2025-12-23
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional, Dict, Any

# Add scripts directory to path
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

from memory_trigger_engine import MemoryTriggerEngine
from memory_detectors import MemoryDetector, TriggerResult


def parse_stdin_json() -> Optional[str]:
    """
    Parse user prompt from stdin JSON (for hook integration)

    Expected format:
    {
      "user_prompt": "the prompt text",
      "session_id": "...",
      "cwd": "/path",
      ...
    }

    Returns:
        User prompt string or None
    """
    try:
        data = json.load(sys.stdin)
        return data.get('user_prompt', '')
    except Exception as e:
        print(f"[ERROR] Failed to parse stdin JSON: {e}", file=sys.stderr)
        return None


def load_detectors(engine: MemoryTriggerEngine, config: Dict[str, Any]) -> None:
    """
    Load and register detector modules

    Args:
        engine: MemoryTriggerEngine instance
        config: Configuration dict
    """
    detector_config = config.get('detectors', {})

    # Try to load project switch detector (Priority 1 - runs first)
    if detector_config.get('project_switch', {}).get('enabled', False):
        try:
            from memory_detectors.project_switch_detector import ProjectSwitchDetector
            detector = ProjectSwitchDetector(detector_config['project_switch'])
            engine.register_detector(detector)
            print(f"[DEBUG] Registered detector: {detector.name}")
        except ImportError as e:
            print(f"[WARNING] Could not load project_switch_detector: {e}")
        except Exception as e:
            print(f"[ERROR] Failed to initialize project_switch_detector: {e}")

    # Try to load keyword detector (Priority 2)
    if detector_config.get('keyword', {}).get('enabled', False):
        try:
            from memory_detectors.keyword_detector import KeywordDetector
            detector = KeywordDetector(detector_config['keyword'])
            engine.register_detector(detector)
            print(f"[DEBUG] Registered detector: {detector.name}")
        except ImportError as e:
            print(f"[WARNING] Could not load keyword_detector: {e}")
        except Exception as e:
            print(f"[ERROR] Failed to initialize keyword_detector: {e}")

    # Try to load entity mention detector (Priority 3)
    if detector_config.get('entity_mention', {}).get('enabled', False):
        try:
            from memory_detectors.entity_mention_detector import EntityMentionDetector
            detector = EntityMentionDetector(detector_config['entity_mention'])
            # Set memory client for cache refresh
            detector.set_memory_client(engine.memory_client)
            engine.register_detector(detector)
            print(f"[DEBUG] Registered detector: {detector.name}")
        except ImportError as e:
            print(f"[WARNING] Could not load entity_mention_detector: {e}")
        except Exception as e:
            print(f"[ERROR] Failed to initialize entity_mention_detector: {e}")

    # Try to load token threshold detector (Priority 4)
    if detector_config.get('token_threshold', {}).get('enabled', False):
        try:
            from memory_detectors.token_threshold_detector import TokenThresholdDetector
            detector = TokenThresholdDetector(detector_config['token_threshold'])
            engine.register_detector(detector)
            print(f"[DEBUG] Registered detector: {detector.name}")
        except ImportError as e:
            print(f"[WARNING] Could not load token_threshold_detector: {e}")
        except Exception as e:
            print(f"[ERROR] Failed to initialize token_threshold_detector: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Context-Aware Memory Trigger System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Trigger from prompt
  python memory_trigger.py --prompt "Remember our architecture decision?"

  # Read from stdin (for hooks)
  echo '{"user_prompt": "test"}' | python memory_trigger.py --stdin

  # Show statistics
  python memory_trigger.py --stats

  # Test mode (no MCP calls)
  python memory_trigger.py --prompt "test" --test
        """
    )

    parser.add_argument('--prompt', type=str, help='User prompt to evaluate')
    parser.add_argument('--stdin', action='store_true', help='Read prompt from stdin JSON')
    parser.add_argument('--stats', action='store_true', help='Show usage statistics')
    parser.add_argument('--test', action='store_true', help='Test mode (no MCP calls)')
    parser.add_argument('--config', type=Path, help='Path to config file')
    parser.add_argument('--context', type=str, help='Context hint (checkpoint, threshold, etc.)')

    args = parser.parse_args()

    # Initialize engine
    try:
        engine = MemoryTriggerEngine(config_path=args.config)
    except Exception as e:
        print(f"[ERROR] Failed to initialize engine: {e}", file=sys.stderr)
        sys.exit(1)

    # Handle stats mode
    if args.stats:
        stats = engine.get_stats()
        print("\n=== Memory Trigger Statistics ===")
        print(f"Session ID: {stats['session_id']}")
        print(f"Session Start: {stats['session_start']}")
        print(f"Tokens Used: {stats['tokens_used']} / {stats['tokens_budget']}")
        print(f"Tokens Remaining: {stats['tokens_remaining']}")
        print(f"Triggers Fired: {stats['triggers_fired']}")
        print(f"Detectors: {stats['detectors_enabled']} enabled / {stats['detectors_registered']} registered")
        sys.exit(0)

    # Handle test mode
    if args.test:
        print("[TEST MODE] Detector evaluation only, no MCP calls")

    # Determine prompt
    prompt = None
    if args.stdin:
        prompt = parse_stdin_json()
        if prompt is None:
            sys.exit(1)
    elif args.prompt:
        prompt = args.prompt
    else:
        parser.print_help()
        sys.exit(1)

    # Load detectors
    load_detectors(engine, engine.config)

    if engine.registry.get_enabled_detectors() == 0:
        print("[WARNING] No detectors registered")
        sys.exit(0)

    # Evaluate triggers
    try:
        trigger_result = engine.evaluate_triggers(prompt)

        if trigger_result is None:
            # No trigger fired
            if not args.test:
                # Only output something if explicitly testing
                pass
            else:
                print("[DEBUG] No trigger fired")
            sys.exit(0)

        # Trigger fired!
        print(f"[DEBUG] Trigger fired: {trigger_result}")

        if args.test:
            # Test mode - don't actually query MCP
            print("\n[TEST MODE] Would query MCP memory:")
            print(f"  Query type: {trigger_result.query_type}")
            print(f"  Query params: {trigger_result.query_params}")
            print(f"  Estimated tokens: {trigger_result.estimated_tokens}")
            sys.exit(0)

        # Query memory
        memory_result = engine.query_memory(trigger_result)

        # Format and output result
        output = engine.format_result(trigger_result, memory_result)
        print(output)

        # For hook integration, also output JSON
        if args.stdin:
            hook_output = {
                "systemMessage": output,
                "additionalContext": output,
                "continue": True
            }
            print(json.dumps(hook_output))

        sys.exit(0)

    except Exception as e:
        print(f"[ERROR] Trigger evaluation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
