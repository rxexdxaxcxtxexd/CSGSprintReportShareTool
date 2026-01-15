#!/usr/bin/env python3
"""
Task Stack Manager - Phase 1: Lightweight Task-Oriented Context System

Provides a simple stack-based task tracking system for Claude Code sessions.
Maintains task context across sessions with automatic persistence.

Usage:
    python task_stack.py push "New task description"
    python task_stack.py pop
    python task_stack.py show
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
import tempfile
import shutil


class TaskStack:
    """Lightweight task stack manager with automatic persistence."""

    STACK_LIMIT = 10  # Keep last 10 tasks for cost control

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize task stack.

        Args:
            storage_path: Path to JSON storage file. Defaults to ~/.claude-sessions/task-stack.json
        """
        if storage_path is None:
            sessions_dir = Path.home() / ".claude-sessions"
            sessions_dir.mkdir(exist_ok=True)
            storage_path = sessions_dir / "task-stack.json"

        self.storage_path = Path(storage_path)
        self.current_task: Optional[str] = None
        self.stack: List[str] = []
        self.last_updated: str = ""

        # Load existing state if available
        self.load()

    def push(self, task: str) -> None:
        """
        Add a new task to the stack, making it the current task.

        Args:
            task: Task description
        """
        if not task or not task.strip():
            raise ValueError("Task description cannot be empty")

        # Move current task to stack if it exists
        if self.current_task:
            self.stack.insert(0, self.current_task)

        # Trim stack to limit
        if len(self.stack) > self.STACK_LIMIT:
            self.stack = self.stack[:self.STACK_LIMIT]

        # Set new current task
        self.current_task = task.strip()
        self._update_timestamp()
        self.save()

    def pop(self) -> Optional[str]:
        """
        Complete the current task and restore the previous one.

        Returns:
            The completed task description, or None if stack was empty
        """
        completed_task = self.current_task

        if not completed_task:
            return None

        # Restore previous task from stack
        if self.stack:
            self.current_task = self.stack.pop(0)
        else:
            self.current_task = None

        self._update_timestamp()
        self.save()

        return completed_task

    def current(self) -> Optional[str]:
        """
        Get the current task.

        Returns:
            Current task description, or None if no active task
        """
        return self.current_task

    def display(self) -> str:
        """
        Generate a readable display of the task stack.

        Returns:
            Formatted string representation of the stack
        """
        # Use ASCII-safe characters for Windows compatibility
        is_windows = sys.platform.startswith('win')
        arrow = ">" if is_windows else "→"

        lines = []
        lines.append("=" * 60)
        lines.append("TASK STACK")
        lines.append("=" * 60)

        if self.current_task:
            lines.append(f"\n[CURRENT TASK]")
            lines.append(f"{arrow} {self.current_task}")
        else:
            lines.append("\n[NO ACTIVE TASK]")

        if self.stack:
            lines.append(f"\n[PREVIOUS TASKS] ({len(self.stack)} in stack)")
            for i, task in enumerate(self.stack, 1):
                lines.append(f"  {i}. {task}")
        else:
            lines.append("\n[NO PREVIOUS TASKS]")

        if self.last_updated:
            try:
                dt = datetime.fromisoformat(self.last_updated.replace('Z', '+00:00'))
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"\nLast updated: {formatted_time}")
            except (ValueError, AttributeError):
                lines.append(f"\nLast updated: {self.last_updated}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def save(self) -> None:
        """Persist task stack to JSON file using atomic write."""
        data: Dict[str, Any] = {
            "current": self.current_task,
            "stack": self.stack,
            "last_updated": self.last_updated
        }

        try:
            # Atomic write: write to temp file, then rename
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.storage_path.parent,
                prefix=".task-stack-",
                suffix=".tmp"
            )

            try:
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                # Atomic rename (overwrites existing file on Unix, best-effort on Windows)
                shutil.move(temp_path, self.storage_path)
            except Exception:
                # Clean up temp file on error
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                raise

        except Exception as e:
            print(f"Warning: Failed to save task stack: {e}", file=sys.stderr)

    def load(self) -> None:
        """Load task stack from JSON file. Creates empty stack if file doesn't exist."""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.current_task = data.get("current")
            self.stack = data.get("stack", [])
            self.last_updated = data.get("last_updated", "")

        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load task stack: {e}", file=sys.stderr)
            print("Starting with empty stack", file=sys.stderr)

    def _update_timestamp(self) -> None:
        """Update the last_updated timestamp to current UTC time."""
        self.last_updated = datetime.now(timezone.utc).isoformat()


def main() -> int:
    """CLI interface for task stack management."""
    # Handle Windows console encoding
    is_windows = sys.platform.startswith('win')
    check_mark = "[OK]" if is_windows else "✓"

    if len(sys.argv) < 2:
        print("Usage: python task_stack.py <command> [args]")
        print("\nCommands:")
        print("  push <task>  - Add a new task to the stack")
        print("  pop          - Complete current task and restore previous")
        print("  show         - Display current task stack")
        return 1

    command = sys.argv[1].lower()
    stack = TaskStack()

    try:
        if command == "push":
            if len(sys.argv) < 3:
                print("Error: push requires a task description", file=sys.stderr)
                return 1

            task = " ".join(sys.argv[2:])
            stack.push(task)
            print(f"{check_mark} Task added: {task}")
            print(f"\nStack depth: {len(stack.stack) + (1 if stack.current_task else 0)}")

        elif command == "pop":
            completed = stack.pop()
            if completed:
                print(f"{check_mark} Task completed: {completed}")
                if stack.current_task:
                    print(f"\nNow working on: {stack.current_task}")
                else:
                    print("\nNo more tasks in stack")
            else:
                print("No active task to complete")

        elif command == "show":
            print(stack.display())

        else:
            print(f"Error: Unknown command '{command}'", file=sys.stderr)
            print("\nValid commands: push, pop, show", file=sys.stderr)
            return 1

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
