#!/usr/bin/env python3
"""
Checkpoint Coordinator - Coordinate checkpoints across multiple sessions

This module ensures only one checkpoint runs at a time and prevents
duplicate checkpoints across multiple Claude Code windows.
"""

import json
import os
import time
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

# Platform-specific imports for file locking
if sys.platform == 'win32':
    import msvcrt  # Windows file locking
else:
    import fcntl  # Unix file locking


@dataclass
class CheckpointState:
    """State of checkpoints for a session"""
    session_id: str
    project_path: str
    last_checkpoint_time: Optional[str]
    checkpoint_count: int = 0
    last_checkpoint_reason: str = ""


class CheckpointCoordinator:
    """Coordinate checkpoints across multiple sessions"""

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize checkpoint coordinator

        Args:
            base_dir: Base directory (default: user home)
        """
        if base_dir is None:
            base_dir = Path.home()

        self.base_dir = Path(base_dir)
        self.claude_dir = self.base_dir / '.claude'
        self.claude_dir.mkdir(parents=True, exist_ok=True)

        self.lock_file = self.claude_dir / 'checkpoint.lock'
        self.state_file = self.claude_dir / 'monitor-state.json'

        # Minimum time between checkpoints for same session (minutes)
        self.min_checkpoint_interval = 30

    def acquire_lock(self, timeout: int = 300) -> bool:
        """
        Acquire exclusive checkpoint lock

        Args:
            timeout: Maximum time to wait in seconds (default: 5 minutes)

        Returns:
            True if lock acquired, False if timeout
        """
        start_time = time.time()

        # Try to acquire lock with timeout
        while time.time() - start_time < timeout:
            try:
                # Try to create lock file exclusively
                # On Windows, os.O_EXCL works differently, so we use a simple approach
                if not self.lock_file.exists():
                    # Create lock file with our PID
                    with open(self.lock_file, 'w') as f:
                        f.write(str(os.getpid()))
                    return True
                else:
                    # Lock exists, check if it's stale
                    if self._is_lock_stale():
                        # Remove stale lock and try again
                        try:
                            self.lock_file.unlink()
                        except FileNotFoundError:
                            pass
                        continue

                    # Wait and retry
                    time.sleep(1)

            except Exception:
                # On error, wait and retry
                time.sleep(1)

        return False

    def release_lock(self):
        """Release checkpoint lock"""
        try:
            self.lock_file.unlink()
        except FileNotFoundError:
            pass

    def _is_lock_stale(self) -> bool:
        """
        Check if lock file is stale (process no longer exists)

        Returns:
            True if lock is stale
        """
        try:
            if not self.lock_file.exists():
                return True

            # Check lock file age
            age = time.time() - self.lock_file.stat().st_mtime
            if age > 600:  # 10 minutes = definitely stale
                return True

            # Try to read PID
            with open(self.lock_file, 'r') as f:
                pid_str = f.read().strip()
                if not pid_str:
                    return True

                try:
                    pid = int(pid_str)

                    # Check if process exists (Windows and Unix compatible)
                    try:
                        os.kill(pid, 0)
                        return False  # Process exists
                    except OSError:
                        return True  # Process doesn't exist

                except ValueError:
                    return True

        except Exception:
            return True

    def can_checkpoint(self, session_id: str, project_path: str) -> bool:
        """
        Check if checkpoint is allowed for this session

        Args:
            session_id: Session ID
            project_path: Project path

        Returns:
            True if checkpoint allowed
        """
        state = self.get_session_state(session_id, project_path)

        if not state.last_checkpoint_time:
            return True  # Never checkpointed before

        try:
            # Parse last checkpoint time
            last_time = datetime.fromisoformat(state.last_checkpoint_time)
            now = datetime.now()

            # Check minimum interval
            delta = now - last_time
            if delta < timedelta(minutes=self.min_checkpoint_interval):
                return False

        except Exception:
            # If we can't parse time, allow checkpoint
            pass

        return True

    def get_session_state(self, session_id: str, project_path: str) -> CheckpointState:
        """
        Get checkpoint state for a session

        Args:
            session_id: Session ID
            project_path: Project path

        Returns:
            CheckpointState object
        """
        state_data = self._load_state()

        key = f"{project_path}:{session_id}"
        if key in state_data:
            return CheckpointState(**state_data[key])

        return CheckpointState(
            session_id=session_id,
            project_path=project_path,
            last_checkpoint_time=None
        )

    def update_session_state(self, session_id: str, project_path: str, reason: str = ""):
        """
        Update session state after checkpoint

        Args:
            session_id: Session ID
            project_path: Project path
            reason: Reason for checkpoint
        """
        state_data = self._load_state()

        key = f"{project_path}:{session_id}"
        if key in state_data:
            state = CheckpointState(**state_data[key])
            state.checkpoint_count += 1
        else:
            state = CheckpointState(
                session_id=session_id,
                project_path=project_path,
                last_checkpoint_time=None,
                checkpoint_count=1
            )

        state.last_checkpoint_time = datetime.now().isoformat()
        state.last_checkpoint_reason = reason

        state_data[key] = asdict(state)
        self._save_state(state_data)

    def _load_state(self) -> Dict[str, Any]:
        """Load state from file"""
        if not self.state_file.exists():
            return {}

        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_state(self, state_data: Dict[str, Any]):
        """Save state to file"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2)
        except Exception:
            pass

    def get_all_session_states(self) -> Dict[str, CheckpointState]:
        """
        Get all session states

        Returns:
            Dictionary of session key -> CheckpointState
        """
        state_data = self._load_state()
        return {
            key: CheckpointState(**value)
            for key, value in state_data.items()
        }

    def clear_old_states(self, max_age_days: int = 7):
        """
        Clear old session states

        Args:
            max_age_days: Maximum age in days to keep
        """
        state_data = self._load_state()
        cutoff = datetime.now() - timedelta(days=max_age_days)

        # Filter out old states
        new_state_data = {}
        for key, value in state_data.items():
            try:
                state = CheckpointState(**value)
                if state.last_checkpoint_time:
                    last_time = datetime.fromisoformat(state.last_checkpoint_time)
                    if last_time > cutoff:
                        new_state_data[key] = value
            except Exception:
                # Keep state if we can't parse it
                new_state_data[key] = value

        self._save_state(new_state_data)


def main():
    """Command-line interface for testing"""
    import sys

    coordinator = CheckpointCoordinator()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == 'lock':
            print("Acquiring lock...")
            if coordinator.acquire_lock(timeout=10):
                print("Lock acquired!")
                print(f"Lock file: {coordinator.lock_file}")
                time.sleep(5)
                coordinator.release_lock()
                print("Lock released")
            else:
                print("Failed to acquire lock")
                return 1

        elif command == 'check':
            session_id = sys.argv[2] if len(sys.argv) > 2 else 'test-session'
            project_path = sys.argv[3] if len(sys.argv) > 3 else '/test/project'

            can_checkpoint = coordinator.can_checkpoint(session_id, project_path)
            print(f"Can checkpoint: {can_checkpoint}")

            state = coordinator.get_session_state(session_id, project_path)
            print(f"\nSession State:")
            print(f"  Last Checkpoint: {state.last_checkpoint_time or 'Never'}")
            print(f"  Checkpoint Count: {state.checkpoint_count}")

        elif command == 'update':
            session_id = sys.argv[2] if len(sys.argv) > 2 else 'test-session'
            project_path = sys.argv[3] if len(sys.argv) > 3 else '/test/project'
            reason = sys.argv[4] if len(sys.argv) > 4 else 'Manual test'

            coordinator.update_session_state(session_id, project_path, reason)
            print(f"Updated session state for {session_id}")

        elif command == 'list':
            states = coordinator.get_all_session_states()
            print(f"Found {len(states)} session state(s):\n")

            for key, state in states.items():
                print(f"{key}:")
                print(f"  Last Checkpoint: {state.last_checkpoint_time or 'Never'}")
                print(f"  Count: {state.checkpoint_count}")
                print(f"  Reason: {state.last_checkpoint_reason}")
                print()

        elif command == 'clean':
            print("Cleaning old states...")
            coordinator.clear_old_states(max_age_days=7)
            print("Done")

        else:
            print(f"Unknown command: {command}")
            return 1

    else:
        print("Usage:")
        print("  python checkpoint_coordinator.py lock")
        print("  python checkpoint_coordinator.py check [session_id] [project_path]")
        print("  python checkpoint_coordinator.py update [session_id] [project_path] [reason]")
        print("  python checkpoint_coordinator.py list")
        print("  python checkpoint_coordinator.py clean")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
