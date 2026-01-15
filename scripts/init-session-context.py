"""
Session Context Initialization Script

Initializes the task-oriented context system at session start.

INTEGRATION WITH CLAUDE CODE:
Add to .claude/settings.json:

{
  "hooks": {
    "sessionStart": "python scripts/init-session-context.py"
  }
}

Or manually run at session start:
    python scripts/init-session-context.py

MANUAL USAGE:
    python scripts/init-session-context.py          # Initialize
    python scripts/init-session-context.py --status # Show state
    python scripts/init-session-context.py --reset  # Reset

WORKFLOW:
1. Load existing task stack and session state
2. Detect workflow mode (interactive/batch/planning)
3. Display welcome banner with current context
4. Initialize monitoring infrastructure
5. Save initial state for session tracking

AUTHOR: Claude Code Session Continuity System
DATE: 2026-01-15
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import platform

# Add scripts directory to path for imports
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

# Check for Windows console compatibility
IS_WINDOWS = platform.system() == "Windows"
USE_EMOJI = not IS_WINDOWS


def print_welcome_banner(task_stack: Any, session_state: Any) -> None:
    """
    Display session context at startup.

    Args:
        task_stack: Current task stack instance
        session_state: Current session state instance
    """
    emoji_map = {
        'task': '📋' if USE_EMOJI else '[Task]',
        'mode': '🔧' if USE_EMOJI else '[Mode]',
        'stats': '📊' if USE_EMOJI else '[Stats]',
        'log': '📝' if USE_EMOJI else '[Log]',
        'switch': '🔄' if USE_EMOJI else '[Switch]',
        'tip': '💡' if USE_EMOJI else '[Tip]'
    }

    print("\n" + "=" * 70)
    print(" " * 20 + "SESSION CONTEXT INITIALIZED")
    print("=" * 70)

    # Current task
    try:
        current = task_stack.current()
        if current:
            print(f"\n{emoji_map['task']} Current Task: {current}")
        else:
            print(f"\n{emoji_map['task']} No active task - starting fresh!")
    except Exception as e:
        print(f"\n{emoji_map['task']} Task stack unavailable: {e}")

    # Session mode
    try:
        mode = getattr(session_state, 'mode', None) or "unknown"
        print(f"{emoji_map['mode']} Session Mode: {mode}")
    except Exception as e:
        print(f"{emoji_map['mode']} Mode detection failed: {e}")

    # Quick stats
    try:
        recent_tasks = getattr(session_state, 'recent_tasks', [])
        decisions = getattr(session_state, 'decisions', [])
        context_switches = getattr(session_state, 'context_switches', [])

        print(f"{emoji_map['stats']} Recent Tasks: {len(recent_tasks)}")
        print(f"{emoji_map['log']} Decisions Logged: {len(decisions)}")
        print(f"{emoji_map['switch']} Context Switches: {len(context_switches)}")
    except Exception as e:
        print(f"{emoji_map['stats']} Stats unavailable: {e}")

    print(f"\n{emoji_map['tip']} Tip: Use 'python scripts/task_stack.py show' to see task history")
    print("=" * 70 + "\n")


def initialize_session_context() -> Dict[str, Any]:
    """
    Initialize task context for new session.

    Workflow:
    1. Load existing state (task stack and session state)
    2. Detect workflow mode (interactive/batch/planning)
    3. Display welcome banner
    4. Initialize monitoring infrastructure
    5. Save initial state

    Returns:
        Dictionary containing:
        - task_stack: TaskStack instance
        - session_state: SessionState instance
        - mode: Detected workflow mode
        - success: Whether initialization succeeded
        - error: Error message if failed
    """
    result = {
        'task_stack': None,
        'session_state': None,
        'mode': None,
        'success': False,
        'error': None
    }

    try:
        # Step 1: Load existing state
        print("Loading session state...")

        try:
            from task_stack import TaskStack
            task_stack = TaskStack()
            task_stack.load()
            result['task_stack'] = task_stack
            print(f"  - Task stack loaded: {len(task_stack.stack)} task(s)")
        except ImportError:
            print("  - Warning: task_stack.py not available")
            result['error'] = "TaskStack module not found"
        except Exception as e:
            print(f"  - Warning: Could not load task stack: {e}")
            result['error'] = f"TaskStack load failed: {e}"

        try:
            from session_state import SessionState
            session_state = SessionState()
            session_state.load()
            result['session_state'] = session_state
            print(f"  - Session state loaded")
        except ImportError:
            print("  - Warning: session_state.py not available")
            if not result['error']:
                result['error'] = "SessionState module not found"
        except Exception as e:
            print(f"  - Warning: Could not load session state: {e}")
            if not result['error']:
                result['error'] = f"SessionState load failed: {e}"

        # Step 2: Detect workflow mode
        print("\nDetecting workflow mode...")

        try:
            from mode_detector import ModeDetector
            detector = ModeDetector()
            mode = detector.analyze_session()

            if result['session_state']:
                result['session_state'].set_mode(mode)

            result['mode'] = mode
            print(f"  - Mode detected: {mode}")
        except ImportError:
            print("  - Warning: mode_detector.py not available")
            result['mode'] = "unknown"
        except Exception as e:
            print(f"  - Warning: Could not detect mode: {e}")
            result['mode'] = "unknown"

        # Step 3: Display welcome banner
        print()
        if result['task_stack'] and result['session_state']:
            print_welcome_banner(result['task_stack'], result['session_state'])
        else:
            print("=" * 70)
            print("SESSION CONTEXT - LIMITED MODE")
            print("=" * 70)
            print("\nSome context modules are unavailable.")
            print("Session will continue with reduced functionality.")
            print("=" * 70 + "\n")

        # Step 4: Initialize monitoring
        print("Initializing monitoring...")

        try:
            from tool_monitor import ToolMonitor
            monitor = ToolMonitor()
            print("  - Tool monitor ready (requires hook integration)")
        except ImportError:
            print("  - Warning: tool_monitor.py not available")
        except Exception as e:
            print(f"  - Warning: Could not initialize monitor: {e}")

        # Step 5: Save initial state
        print("\nSaving initial state...")

        try:
            if result['session_state']:
                result['session_state'].save()
                print("  - Session state saved")
        except Exception as e:
            print(f"  - Warning: Could not save session state: {e}")

        result['success'] = True
        print("\n" + "✓" if USE_EMOJI else "[OK]" + " Session context initialized successfully!\n")

    except Exception as e:
        result['error'] = str(e)
        result['success'] = False
        print(f"\n[ERROR] Session initialization failed: {e}\n")

    return result


def show_status() -> None:
    """
    Display current session context status.

    Shows:
    - Task stack contents
    - Session state summary
    - Recent activity
    - System health
    """
    print("\n" + "=" * 70)
    print(" " * 25 + "SESSION STATUS")
    print("=" * 70 + "\n")

    # Task stack status
    try:
        from task_stack import TaskStack
        task_stack = TaskStack()
        task_stack.load()

        print("TASK STACK:")
        if task_stack.stack:
            for i, task in enumerate(task_stack.stack, 1):
                marker = " <-- Current" if i == len(task_stack.stack) else ""
                print(f"  {i}. {task}{marker}")
        else:
            print("  (empty)")
        print()
    except Exception as e:
        print(f"TASK STACK: Unavailable ({e})\n")

    # Session state status
    try:
        from session_state import SessionState
        session_state = SessionState()
        session_state.load()

        print("SESSION STATE:")
        print(f"  Mode: {getattr(session_state, 'mode', 'unknown')}")
        print(f"  Recent Tasks: {len(getattr(session_state, 'recent_tasks', []))}")
        print(f"  Decisions: {len(getattr(session_state, 'decisions', []))}")
        print(f"  Context Switches: {len(getattr(session_state, 'context_switches', []))}")
        print()
    except Exception as e:
        print(f"SESSION STATE: Unavailable ({e})\n")

    # System health
    print("SYSTEM HEALTH:")
    modules = {
        'task_stack': 'Task Stack',
        'session_state': 'Session State',
        'mode_detector': 'Mode Detector',
        'tool_monitor': 'Tool Monitor'
    }

    for module_name, display_name in modules.items():
        try:
            __import__(module_name)
            status = "OK" if USE_EMOJI else "[OK]"
            print(f"  {status} {display_name}")
        except ImportError:
            status = "X" if USE_EMOJI else "[MISSING]"
            print(f"  {status} {display_name}")

    print("\n" + "=" * 70 + "\n")


def reset_state() -> None:
    """
    Reset all session state to clean slate.

    WARNING: This removes all task history and session state.
    """
    print("\n" + "!" * 70)
    print(" " * 25 + "RESET WARNING")
    print("!" * 70)
    print("\nThis will delete:")
    print("  - Task stack history")
    print("  - Session state data")
    print("  - Mode detection cache")
    print()

    response = input("Are you sure you want to reset? (yes/no): ").strip().lower()

    if response != 'yes':
        print("\nReset cancelled.\n")
        return

    print("\nResetting session state...")

    # Reset task stack
    try:
        from task_stack import TaskStack
        task_stack = TaskStack()
        task_stack.stack = []
        task_stack.save()
        print("  - Task stack cleared")
    except Exception as e:
        print(f"  - Warning: Could not reset task stack: {e}")

    # Reset session state
    try:
        from session_state import SessionState
        session_state = SessionState()
        # Reset to defaults
        session_state.mode = None
        session_state.recent_tasks = []
        session_state.decisions = []
        session_state.context_switches = []
        session_state.save()
        print("  - Session state cleared")
    except Exception as e:
        print(f"  - Warning: Could not reset session state: {e}")

    print("\n" + "✓" if USE_EMOJI else "[OK]" + " Reset complete!\n")


def main() -> int:
    """
    Main entry point for session initialization script.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description='Initialize session context for Claude Code',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/init-session-context.py          # Initialize session
  python scripts/init-session-context.py --status # Show current state
  python scripts/init-session-context.py --reset  # Reset all state

Integration:
  Add to .claude/settings.json:
  {
    "hooks": {
      "sessionStart": "python scripts/init-session-context.py"
    }
  }
        """
    )

    parser.add_argument(
        '--status',
        action='store_true',
        help='Show current session context status'
    )

    parser.add_argument(
        '--reset',
        action='store_true',
        help='Reset all session state (requires confirmation)'
    )

    args = parser.parse_args()

    try:
        if args.status:
            show_status()
            return 0

        if args.reset:
            reset_state()
            return 0

        # Default: Initialize session
        result = initialize_session_context()
        return 0 if result['success'] else 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.\n")
        return 1
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())
