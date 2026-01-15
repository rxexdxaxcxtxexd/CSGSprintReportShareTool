"""
Session State Manager for Task-Oriented Context System

Manages session state including current task, recent tasks, decisions,
context switches, and pending work with token budget enforcement.

Usage:
    python session_state_manager.py show
    python session_state_manager.py update-task "Investigating X"
    python session_state_manager.py add-decision "Fixed API endpoint" "Deprecated"
    python session_state_manager.py complete-task "Successfully resolved"
    python session_state_manager.py set-mode task
"""

import json
import os
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Literal
import tempfile
import shutil


# Token budget limits
MAX_TOTAL_TOKENS = 1000
MAX_RECENT_TASKS = 5
MAX_DECISIONS = 10
MAX_CONTEXT_SWITCHES = 5

# Rough token estimation (4 chars ≈ 1 token)
CHARS_PER_TOKEN = 4


@dataclass
class CurrentTask:
    """Current active task being worked on."""
    description: str
    started: str  # ISO 8601 timestamp
    status: Literal["in_progress", "blocked", "waiting"]
    tools_used: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass
class RecentTask:
    """Completed task from recent history."""
    description: str
    started: str
    completed: str
    outcome: str

    def to_dict(self):
        return asdict(self)


@dataclass
class Decision:
    """Decision made during session."""
    decision: str
    rationale: str
    timestamp: str

    def to_dict(self):
        return asdict(self)


@dataclass
class ContextSwitch:
    """Context switch event."""
    from_context: str
    to_context: str
    trigger: str
    timestamp: str

    def to_dict(self):
        return asdict(self)


class SessionState:
    """Manages session state with token budget enforcement."""

    def __init__(self, session_dir: Optional[Path] = None):
        """
        Initialize session state manager.

        Args:
            session_dir: Directory for session files (default: ~/.claude-sessions)
        """
        if session_dir is None:
            session_dir = Path.home() / ".claude-sessions"

        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(exist_ok=True)
        self.state_file = self.session_dir / "session-state.json"

        # Initialize state
        self.session_id: str = ""
        self.last_updated: str = ""
        self.mode: Literal["task", "file", "mixed"] = "task"
        self.current_task: Optional[CurrentTask] = None
        self.recent_tasks: List[RecentTask] = []
        self.decisions: List[Decision] = []
        self.context_switches: List[ContextSwitch] = []
        self.pending_work: List[str] = []

        # Load existing state if available
        if self.state_file.exists():
            self.load()
        else:
            # Generate new session ID
            self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.last_updated = datetime.now().isoformat()

    def update_current_task(self, description: str, tools_used: Optional[List[str]] = None):
        """
        Update or create current task.

        Args:
            description: Task description
            tools_used: List of tools used (optional, appends to existing)
        """
        if self.current_task is None:
            self.current_task = CurrentTask(
                description=description,
                started=datetime.now().isoformat(),
                status="in_progress",
                tools_used=tools_used or []
            )
        else:
            self.current_task.description = description
            if tools_used:
                # Append new tools, avoiding duplicates
                for tool in tools_used:
                    if tool not in self.current_task.tools_used:
                        self.current_task.tools_used.append(tool)

        self.last_updated = datetime.now().isoformat()
        self._enforce_token_budget()
        self.save()

    def complete_task(self, outcome: str):
        """
        Complete current task and move to recent tasks.

        Args:
            outcome: Task outcome description
        """
        if self.current_task is None:
            print("Error: No current task to complete", file=sys.stderr)
            return

        # Move to recent tasks
        recent = RecentTask(
            description=self.current_task.description,
            started=self.current_task.started,
            completed=datetime.now().isoformat(),
            outcome=outcome
        )
        self.recent_tasks.insert(0, recent)

        # Keep only last N tasks
        self.recent_tasks = self.recent_tasks[:MAX_RECENT_TASKS]

        # Clear current task
        self.current_task = None

        self.last_updated = datetime.now().isoformat()
        self._enforce_token_budget()
        self.save()

    def add_decision(self, decision: str, rationale: str):
        """
        Add decision to history.

        Args:
            decision: Decision made
            rationale: Reasoning behind decision
        """
        dec = Decision(
            decision=decision,
            rationale=rationale,
            timestamp=datetime.now().isoformat()
        )
        self.decisions.insert(0, dec)

        # Keep only last N decisions
        self.decisions = self.decisions[:MAX_DECISIONS]

        self.last_updated = datetime.now().isoformat()
        self._enforce_token_budget()
        self.save()

    def log_context_switch(self, from_context: str, to_context: str, trigger: str):
        """
        Log context switch event.

        Args:
            from_context: Previous context
            to_context: New context
            trigger: What triggered the switch
        """
        switch = ContextSwitch(
            from_context=from_context,
            to_context=to_context,
            trigger=trigger,
            timestamp=datetime.now().isoformat()
        )
        self.context_switches.insert(0, switch)

        # Keep only last N switches
        self.context_switches = self.context_switches[:MAX_CONTEXT_SWITCHES]

        self.last_updated = datetime.now().isoformat()
        self._enforce_token_budget()
        self.save()

    def set_mode(self, mode: Literal["task", "file", "mixed"]):
        """
        Set session mode.

        Args:
            mode: Session mode (task/file/mixed)
        """
        if mode not in ["task", "file", "mixed"]:
            raise ValueError(f"Invalid mode: {mode}. Must be task/file/mixed")

        self.mode = mode
        self.last_updated = datetime.now().isoformat()
        self.save()

    def add_pending_work(self, item: str):
        """Add item to pending work list."""
        if item not in self.pending_work:
            self.pending_work.append(item)
            self.last_updated = datetime.now().isoformat()
            self._enforce_token_budget()
            self.save()

    def remove_pending_work(self, item: str):
        """Remove item from pending work list."""
        if item in self.pending_work:
            self.pending_work.remove(item)
            self.last_updated = datetime.now().isoformat()
            self.save()

    def _enforce_token_budget(self):
        """Enforce token budget by pruning oldest entries."""
        # Already enforced per-collection limits in individual methods
        # This ensures total stays under budget
        total_tokens = self._estimate_tokens()

        if total_tokens > MAX_TOTAL_TOKENS:
            # Prune in order: context_switches, decisions, recent_tasks
            if len(self.context_switches) > 3:
                self.context_switches = self.context_switches[:3]

            total_tokens = self._estimate_tokens()
            if total_tokens > MAX_TOTAL_TOKENS and len(self.decisions) > 5:
                self.decisions = self.decisions[:5]

            total_tokens = self._estimate_tokens()
            if total_tokens > MAX_TOTAL_TOKENS and len(self.recent_tasks) > 3:
                self.recent_tasks = self.recent_tasks[:3]

            # If still over, prune pending work
            total_tokens = self._estimate_tokens()
            if total_tokens > MAX_TOTAL_TOKENS:
                chars_to_remove = (total_tokens - MAX_TOTAL_TOKENS) * CHARS_PER_TOKEN
                while chars_to_remove > 0 and self.pending_work:
                    removed = self.pending_work.pop()
                    chars_to_remove -= len(removed)

    def _estimate_tokens(self) -> int:
        """Estimate token count for current state."""
        json_str = json.dumps(self._to_dict(), indent=2)
        return len(json_str) // CHARS_PER_TOKEN

    def _to_dict(self) -> dict:
        """Convert state to dictionary."""
        return {
            "session_id": self.session_id,
            "last_updated": self.last_updated,
            "mode": self.mode,
            "current_task": self.current_task.to_dict() if self.current_task else None,
            "recent_tasks": [t.to_dict() for t in self.recent_tasks],
            "decisions": [d.to_dict() for d in self.decisions],
            "context_switches": [s.to_dict() for s in self.context_switches],
            "pending_work": self.pending_work
        }

    def save(self):
        """Save state to file atomically."""
        data = self._to_dict()

        # Atomic write using temp file
        with tempfile.NamedTemporaryFile(
            mode='w',
            dir=self.session_dir,
            delete=False,
            suffix='.tmp'
        ) as tmp_file:
            json.dump(data, tmp_file, indent=2)
            tmp_path = tmp_file.name

        # Replace original file
        shutil.move(tmp_path, self.state_file)

    def load(self):
        """Load state from file."""
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)

            self.session_id = data.get("session_id", "")
            self.last_updated = data.get("last_updated", "")
            self.mode = data.get("mode", "task")

            # Load current task
            current = data.get("current_task")
            if current:
                self.current_task = CurrentTask(**current)
            else:
                self.current_task = None

            # Load recent tasks
            self.recent_tasks = [
                RecentTask(**t) for t in data.get("recent_tasks", [])
            ]

            # Load decisions
            self.decisions = [
                Decision(**d) for d in data.get("decisions", [])
            ]

            # Load context switches
            self.context_switches = [
                ContextSwitch(**s) for s in data.get("context_switches", [])
            ]

            # Load pending work
            self.pending_work = data.get("pending_work", [])

        except Exception as e:
            print(f"Error loading state: {e}", file=sys.stderr)

    def display(self):
        """Display state in human-readable format."""
        print(f"\n{'='*60}")
        print(f"SESSION STATE - {self.session_id}")
        print(f"{'='*60}")
        print(f"Mode: {self.mode}")
        print(f"Last Updated: {self.last_updated}")
        print(f"Estimated Tokens: {self._estimate_tokens()}/{MAX_TOTAL_TOKENS}")

        # Current task
        print(f"\n{'-'*60}")
        print("CURRENT TASK:")
        print(f"{'-'*60}")
        if self.current_task:
            print(f"Description: {self.current_task.description}")
            print(f"Started: {self.current_task.started}")
            print(f"Status: {self.current_task.status}")
            if self.current_task.tools_used:
                print(f"Tools: {', '.join(self.current_task.tools_used)}")
        else:
            print("No active task")

        # Recent tasks
        if self.recent_tasks:
            print(f"\n{'-'*60}")
            print(f"RECENT TASKS ({len(self.recent_tasks)}):")
            print(f"{'-'*60}")
            for i, task in enumerate(self.recent_tasks, 1):
                print(f"{i}. {task.description}")
                print(f"   Completed: {task.completed}")
                print(f"   Outcome: {task.outcome}")

        # Decisions
        if self.decisions:
            print(f"\n{'-'*60}")
            print(f"DECISIONS ({len(self.decisions)}):")
            print(f"{'-'*60}")
            for i, dec in enumerate(self.decisions, 1):
                print(f"{i}. {dec.decision}")
                print(f"   Rationale: {dec.rationale}")
                print(f"   Timestamp: {dec.timestamp}")

        # Context switches
        if self.context_switches:
            print(f"\n{'-'*60}")
            print(f"CONTEXT SWITCHES ({len(self.context_switches)}):")
            print(f"{'-'*60}")
            for i, switch in enumerate(self.context_switches, 1):
                print(f"{i}. {switch.from_context} → {switch.to_context}")
                print(f"   Trigger: {switch.trigger}")
                print(f"   Timestamp: {switch.timestamp}")

        # Pending work
        if self.pending_work:
            print(f"\n{'-'*60}")
            print(f"PENDING WORK ({len(self.pending_work)}):")
            print(f"{'-'*60}")
            for i, item in enumerate(self.pending_work, 1):
                print(f"{i}. {item}")

        print(f"\n{'='*60}\n")


def main():
    """CLI interface."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python session_state_manager.py show")
        print("  python session_state_manager.py update-task <description>")
        print("  python session_state_manager.py complete-task <outcome>")
        print("  python session_state_manager.py add-decision <decision> <rationale>")
        print("  python session_state_manager.py set-mode <task|file|mixed>")
        print("  python session_state_manager.py add-pending <item>")
        print("  python session_state_manager.py remove-pending <item>")
        sys.exit(1)

    state = SessionState()
    command = sys.argv[1]

    if command == "show":
        state.display()

    elif command == "update-task":
        if len(sys.argv) < 3:
            print("Error: update-task requires description", file=sys.stderr)
            sys.exit(1)
        description = " ".join(sys.argv[2:])
        state.update_current_task(description)
        print(f"Updated task: {description}")

    elif command == "complete-task":
        if len(sys.argv) < 3:
            print("Error: complete-task requires outcome", file=sys.stderr)
            sys.exit(1)
        outcome = " ".join(sys.argv[2:])
        state.complete_task(outcome)
        print(f"Completed task with outcome: {outcome}")

    elif command == "add-decision":
        if len(sys.argv) < 4:
            print("Error: add-decision requires decision and rationale", file=sys.stderr)
            sys.exit(1)
        decision = sys.argv[2]
        rationale = " ".join(sys.argv[3:])
        state.add_decision(decision, rationale)
        print(f"Added decision: {decision}")

    elif command == "set-mode":
        if len(sys.argv) < 3:
            print("Error: set-mode requires mode (task/file/mixed)", file=sys.stderr)
            sys.exit(1)
        mode = sys.argv[2]
        state.set_mode(mode)
        print(f"Set mode to: {mode}")

    elif command == "add-pending":
        if len(sys.argv) < 3:
            print("Error: add-pending requires item", file=sys.stderr)
            sys.exit(1)
        item = " ".join(sys.argv[2:])
        state.add_pending_work(item)
        print(f"Added pending work: {item}")

    elif command == "remove-pending":
        if len(sys.argv) < 3:
            print("Error: remove-pending requires item", file=sys.stderr)
            sys.exit(1)
        item = " ".join(sys.argv[2:])
        state.remove_pending_work(item)
        print(f"Removed pending work: {item}")

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
