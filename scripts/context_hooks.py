#!/usr/bin/env python3
"""
Context Hooks - Automatic task tracking through tool execution monitoring.

Monitors Claude Code tool usage and automatically updates task state without
requiring manual intervention. Integrates with TaskStack, SessionState, and
ModeDetector for intelligent auto-save behavior.

Usage:
    python context_hooks.py monitor          # Start monitoring (testing)
    python context_hooks.py test-todo        # Simulate TodoWrite
    python context_hooks.py test-autosave    # Simulate auto-save trigger
"""

import json
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Deque
import logging

# Import existing modules
try:
    from task_stack import TaskStack
    from session_state_manager import SessionState
    from mode_detector import ModeDetector
except ImportError:
    print("Error: Required modules not found. Ensure task_stack.py, session_state_manager.py, "
          "and mode_detector.py are in the same directory.", file=sys.stderr)
    sys.exit(1)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ToolMonitor:
    """Monitors tool execution and triggers automatic state updates."""

    # Tool execution history size
    HISTORY_SIZE = 50

    # Auto-save thresholds (tools since last save)
    AUTOSAVE_TASK_MODE = 10
    AUTOSAVE_MIXED_MODE = 15
    AUTOSAVE_FILE_MODE = 20

    # Time-based auto-save (minutes)
    AUTOSAVE_TIME_TASK = 15
    AUTOSAVE_TIME_MIXED = 20
    AUTOSAVE_TIME_FILE = 30

    # Context switch detection window
    CONTEXT_WINDOW = 10

    def __init__(self, session_dir: Optional[Path] = None):
        """
        Initialize tool monitor.

        Args:
            session_dir: Directory for session files (default: ~/.claude-sessions)
        """
        if session_dir is None:
            session_dir = Path.home() / ".claude-sessions"

        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(exist_ok=True)

        # Initialize components
        self.task_stack = TaskStack()
        self.session_state = SessionState(session_dir=self.session_dir)
        self.mode_detector = ModeDetector(session_dir=self.session_dir)

        # Tool execution tracking
        self.tool_history: Deque[Dict[str, Any]] = deque(maxlen=self.HISTORY_SIZE)
        self.tool_count = 0
        self.last_save_time = datetime.now(timezone.utc)
        self.last_save_count = 0

        # Current context tracking
        self.current_context: Optional[str] = None

        logger.info("ToolMonitor initialized")

    def on_tool_executed(self, tool_name: str, success: bool = True,
                        metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Called after every tool execution.

        Args:
            tool_name: Name of the tool that was executed
            success: Whether the tool executed successfully
            metadata: Additional metadata about the execution
        """
        # Record tool execution
        timestamp = datetime.now(timezone.utc)

        tool_event = {
            "tool": tool_name,
            "success": success,
            "timestamp": timestamp.isoformat(),
            "metadata": metadata or {}
        }

        self.tool_history.append(tool_event)
        self.tool_count += 1

        logger.debug(f"Tool executed: {tool_name} (success={success})")

        # Update session state with tool usage
        if self.session_state.current_task:
            current_tools = self.session_state.current_task.tools_used or []
            if tool_name not in current_tools:
                self.session_state.update_current_task(
                    description=self.session_state.current_task.description,
                    tools_used=[tool_name]
                )

        # Check for context switch
        context_switch = self.detect_context_switch()
        if context_switch:
            self._handle_context_switch(context_switch)

        # Check auto-save triggers
        if self.should_auto_save():
            self._trigger_auto_save("Tool count threshold reached")

    def on_todo_write(self, todos: List[Dict[str, Any]]) -> None:
        """
        Called when TodoWrite tool executes.

        Extracts the current in_progress task and updates task stack and session state.

        Args:
            todos: List of todo items from TodoWrite tool
        """
        logger.info(f"TodoWrite detected with {len(todos)} todos")

        # Find current in_progress task
        current_task = None
        for todo in todos:
            if todo.get("status") == "in_progress":
                current_task = todo.get("content")
                break

        if current_task:
            logger.info(f"Current task detected: {current_task}")

            # Update task stack (only if different from current)
            if self.task_stack.current() != current_task:
                self.task_stack.push(current_task)
                logger.info(f"Task stack updated: {current_task}")

            # Update session state
            self.session_state.update_current_task(
                description=current_task,
                tools_used=["TodoWrite"]
            )

            # Check if auto-save should trigger
            if self.should_auto_save():
                self._trigger_auto_save("TodoWrite detected")
        else:
            logger.debug("No in_progress task found in TodoWrite")

    def should_auto_save(self) -> bool:
        """
        Check if auto-save should trigger based on current mode.

        Returns:
            True if auto-save should be triggered
        """
        # Get current mode
        tool_names = [event["tool"] for event in self.tool_history]
        mode = self.mode_detector.detect_mode(tool_names)

        # Check tool count threshold
        tools_since_save = self.tool_count - self.last_save_count

        if mode == "task" and tools_since_save >= self.AUTOSAVE_TASK_MODE:
            return True
        elif mode == "mixed" and tools_since_save >= self.AUTOSAVE_MIXED_MODE:
            return True
        elif mode == "file" and tools_since_save >= self.AUTOSAVE_FILE_MODE:
            return True

        # Check time threshold
        time_since_save = (datetime.now(timezone.utc) - self.last_save_time).total_seconds() / 60

        if mode == "task" and time_since_save >= self.AUTOSAVE_TIME_TASK:
            return True
        elif mode == "mixed" and time_since_save >= self.AUTOSAVE_TIME_MIXED:
            return True
        elif mode == "file" and time_since_save >= self.AUTOSAVE_TIME_FILE:
            return True

        return False

    def detect_context_switch(self) -> Optional[Dict[str, str]]:
        """
        Detect if context has switched based on tool patterns.

        Compares recent tools vs previous tools to identify dramatic shifts.

        Returns:
            Dictionary with switch info if detected, None otherwise
        """
        if len(self.tool_history) < self.CONTEXT_WINDOW * 2:
            return None

        # Get recent and previous windows
        all_tools = list(self.tool_history)
        recent_window = all_tools[-self.CONTEXT_WINDOW:]
        previous_window = all_tools[-self.CONTEXT_WINDOW*2:-self.CONTEXT_WINDOW]

        # Calculate tool category distributions
        recent_dist = self._calculate_tool_distribution(recent_window)
        previous_dist = self._calculate_tool_distribution(previous_window)

        # Detect significant shift (>50% change in dominant category)
        recent_dominant = max(recent_dist, key=recent_dist.get)
        previous_dominant = max(previous_dist, key=previous_dist.get)

        if recent_dominant != previous_dominant:
            # Calculate shift magnitude
            shift_magnitude = abs(
                recent_dist[recent_dominant] - previous_dist.get(recent_dominant, 0)
            )

            if shift_magnitude > 0.3:  # 30% shift threshold
                from_context = self._describe_context(previous_dist)
                to_context = self._describe_context(recent_dist)

                # Only report if this is a new context
                if self.current_context != to_context:
                    self.current_context = to_context

                    return {
                        "from_context": from_context,
                        "to_context": to_context,
                        "trigger": f"Tool pattern shift: {previous_dominant} → {recent_dominant}",
                        "magnitude": round(shift_magnitude, 2)
                    }

        return None

    def _calculate_tool_distribution(self, tool_events: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate distribution of tool categories in events list."""
        if not tool_events:
            return {"neutral": 1.0}

        total = len(tool_events)
        counts = {"file": 0, "task": 0, "neutral": 0}

        for event in tool_events:
            tool = event["tool"]
            if tool in self.mode_detector.FILE_TOOLS:
                counts["file"] += 1
            elif tool in self.mode_detector.TASK_TOOLS:
                counts["task"] += 1
            else:
                counts["neutral"] += 1

        return {k: v / total for k, v in counts.items()}

    def _describe_context(self, distribution: Dict[str, float]) -> str:
        """Generate human-readable context description from distribution."""
        dominant = max(distribution, key=distribution.get)
        ratio = distribution[dominant]

        if dominant == "file" and ratio > 0.5:
            return "Heavy coding/editing"
        elif dominant == "task" and ratio > 0.5:
            return "Investigation/research"
        else:
            return "Mixed activity"

    def _handle_context_switch(self, switch_info: Dict[str, str]) -> None:
        """Handle detected context switch."""
        logger.info(f"Context switch detected: {switch_info['from_context']} → {switch_info['to_context']}")

        # Log to session state
        self.session_state.log_context_switch(
            from_context=switch_info["from_context"],
            to_context=switch_info["to_context"],
            trigger=switch_info["trigger"]
        )

        # Trigger auto-save on context switch
        self._trigger_auto_save(f"Context switch: {switch_info['trigger']}")

    def _trigger_auto_save(self, reason: str) -> None:
        """Trigger auto-save of task stack and session state."""
        logger.info(f"Auto-save triggered: {reason}")

        # Save task stack (already saved automatically)
        # Save session state (already saved automatically)

        # Update counters
        self.last_save_time = datetime.now(timezone.utc)
        self.last_save_count = self.tool_count

        # Log to console (Windows-safe)
        check_mark = "[OK]" if sys.platform.startswith('win') else "✓"
        print(f"{check_mark} Auto-save: {reason} (tools={self.tool_count})")

    def prepare_for_compact(self) -> None:
        """
        Called before auto-compact/memory compression.

        Forces save of all state before context window compression.
        """
        logger.warning("Context limit approaching - saving state before compact")

        # Force save task stack
        self.task_stack.save()

        # Force save session state
        self.session_state.save()

        # Log summary
        tool_names = [event["tool"] for event in self.tool_history]
        mode = self.mode_detector.detect_mode(tool_names)

        # Windows-safe warning symbol
        warning = "[!]" if sys.platform.startswith('win') else "⚠️"

        print("\n" + "=" * 60)
        print(f"{warning}  CONTEXT LIMIT APPROACHING - STATE SAVED")
        print("=" * 60)
        print(f"Mode: {mode}")
        print(f"Tools executed: {self.tool_count}")
        print(f"Current task: {self.task_stack.current() or 'None'}")
        print(f"Task stack depth: {len(self.task_stack.stack)}")
        print("=" * 60 + "\n")

    def get_status(self) -> Dict[str, Any]:
        """Get current monitor status."""
        tool_names = [event["tool"] for event in self.tool_history]
        mode = self.mode_detector.detect_mode(tool_names)
        config = self.mode_detector.get_config(mode)

        tools_since_save = self.tool_count - self.last_save_count
        time_since_save = (datetime.now(timezone.utc) - self.last_save_time).total_seconds() / 60

        return {
            "mode": mode,
            "tool_count": self.tool_count,
            "tools_since_save": tools_since_save,
            "time_since_save_minutes": round(time_since_save, 1),
            "current_task": self.task_stack.current(),
            "task_stack_depth": len(self.task_stack.stack),
            "current_context": self.current_context,
            "config": {
                "checkpoint_trigger": config.checkpoint_trigger,
                "auto_save_interval": config.auto_save_interval
            }
        }


def monitor_loop(monitor: ToolMonitor, duration_seconds: int = 60) -> None:
    """
    Run monitoring loop for testing (simulates tool execution).

    Args:
        monitor: ToolMonitor instance
        duration_seconds: How long to run the test
    """
    print(f"\nStarting monitor test for {duration_seconds} seconds...")
    print("Simulating tool execution patterns...\n")

    # Simulate tool patterns
    test_patterns = [
        ("Read", True), ("Grep", True), ("Read", True),  # Investigation
        ("Edit", True), ("Write", True), ("Edit", True),  # Coding
        ("Read", True), ("Bash", True), ("Read", True),   # Mixed
    ]

    start_time = time.time()
    iteration = 0

    while time.time() - start_time < duration_seconds:
        tool_name, success = test_patterns[iteration % len(test_patterns)]

        print(f"[{iteration+1}] Executing: {tool_name}")
        monitor.on_tool_executed(tool_name, success)

        # Print status every 5 tools
        if (iteration + 1) % 5 == 0:
            status = monitor.get_status()
            print(f"\n  Status: mode={status['mode']}, "
                  f"tools_since_save={status['tools_since_save']}, "
                  f"current_task={status['current_task']}\n")

        iteration += 1
        time.sleep(2)  # Wait 2 seconds between tools

    print("\nMonitor test complete!")
    print("\nFinal status:")
    print(json.dumps(monitor.get_status(), indent=2))


def test_todo_write(monitor: ToolMonitor) -> None:
    """Test TodoWrite integration."""
    print("\n" + "=" * 60)
    print("Testing TodoWrite Integration")
    print("=" * 60 + "\n")

    # Simulate TodoWrite with multiple todos
    test_todos = [
        {"content": "Review API documentation", "status": "completed", "activeForm": "Reviewing API documentation"},
        {"content": "Implement user authentication", "status": "in_progress", "activeForm": "Implementing user authentication"},
        {"content": "Write unit tests", "status": "pending", "activeForm": "Writing unit tests"}
    ]

    print("Simulating TodoWrite with todos:")
    for todo in test_todos:
        print(f"  • [{todo['status']}] {todo['content']}")
    print()

    # Process TodoWrite
    monitor.on_todo_write(test_todos)

    # Show results
    print("\nResults:")
    print(f"  Current task: {monitor.task_stack.current()}")
    print(f"  Task stack depth: {len(monitor.task_stack.stack)}")

    if monitor.session_state.current_task:
        print(f"  Session task: {monitor.session_state.current_task.description}")

    print("\n" + "=" * 60)


def test_auto_save(monitor: ToolMonitor) -> None:
    """Test auto-save trigger."""
    print("\n" + "=" * 60)
    print("Testing Auto-Save Trigger")
    print("=" * 60 + "\n")

    # Simulate task mode (investigation)
    print("Simulating TASK mode (investigation)...")
    for i in range(12):  # Exceeds AUTOSAVE_TASK_MODE threshold
        monitor.on_tool_executed("Read", True)
        print(f"  Tool {i+1}/12 executed")

    status = monitor.get_status()
    print(f"\nStatus after {status['tool_count']} tools:")
    print(f"  Mode: {status['mode']}")
    print(f"  Tools since save: {status['tools_since_save']}")
    print(f"  Should auto-save: {monitor.should_auto_save()}")

    print("\n" + "=" * 60)


def main() -> int:
    """CLI interface for context hooks."""
    if len(sys.argv) < 2:
        print("Usage: python context_hooks.py <command>")
        print("\nCommands:")
        print("  monitor           - Start monitoring loop (testing)")
        print("  test-todo         - Test TodoWrite integration")
        print("  test-autosave     - Test auto-save trigger")
        print("  status            - Show current monitor status")
        print("  prepare-compact   - Simulate pre-compact save")
        return 1

    command = sys.argv[1].lower()

    try:
        monitor = ToolMonitor()

        if command == "monitor":
            duration = int(sys.argv[2]) if len(sys.argv) > 2 else 60
            monitor_loop(monitor, duration)

        elif command == "test-todo":
            test_todo_write(monitor)

        elif command == "test-autosave":
            test_auto_save(monitor)

        elif command == "status":
            status = monitor.get_status()
            print("\n" + "=" * 60)
            print("TOOL MONITOR STATUS")
            print("=" * 60)
            print(json.dumps(status, indent=2))
            print("=" * 60 + "\n")

        elif command == "prepare-compact":
            monitor.prepare_for_compact()

        else:
            print(f"Error: Unknown command '{command}'", file=sys.stderr)
            return 1

        return 0

    except Exception as e:
        logger.exception(f"Error: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
