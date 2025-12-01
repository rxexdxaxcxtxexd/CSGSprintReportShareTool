#!/usr/bin/env python3
"""
Session Detector - Detect and track active Claude Code sessions

This module scans .claude/projects/ to find all active Claude Code sessions
and tracks their activity metrics.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
import subprocess


@dataclass
class ActivityMetrics:
    """Metrics about a session's activity"""
    messages_count: int = 0
    files_modified: int = 0
    last_activity: Optional[str] = None
    time_since_activity_minutes: Optional[int] = None
    estimated_context_tokens: int = 0


@dataclass
class SessionInfo:
    """Information about an active Claude Code session"""
    session_id: str
    project_path: str
    session_file_path: str
    last_activity: Optional[str]
    activity_metrics: ActivityMetrics
    last_checkpoint_time: Optional[str] = None
    uncommitted_changes: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        result['activity_metrics'] = asdict(self.activity_metrics)
        return result


class SessionDetector:
    """Detect all active Claude Code sessions"""

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize session detector

        Args:
            base_dir: Base directory (default: user home)
        """
        if base_dir is None:
            base_dir = Path.home()

        self.base_dir = Path(base_dir)
        self.claude_dir = self.base_dir / '.claude'
        self.projects_dir = self.claude_dir / 'projects'
        self.checkpoints_dir = self.base_dir / '.claude-sessions' / 'checkpoints'

    def find_active_sessions(self) -> List[SessionInfo]:
        """
        Find all active Claude Code sessions

        Returns:
            List of SessionInfo objects for active sessions
        """
        if not self.projects_dir.exists():
            return []

        sessions = []

        # Scan all project directories
        for project_dir in self.projects_dir.iterdir():
            if not project_dir.is_dir():
                continue

            # Find all session JSONL files in this project
            for session_file in project_dir.glob('*.jsonl'):
                try:
                    session_info = self._parse_session_file(session_file, project_dir)
                    if session_info:
                        sessions.append(session_info)
                except Exception as e:
                    # Skip invalid session files
                    continue

        return sessions

    def _parse_session_file(self, session_file: Path, project_dir: Path) -> Optional[SessionInfo]:
        """
        Parse a session JSONL file to extract session info

        Args:
            session_file: Path to session JSONL file
            project_dir: Project directory path

        Returns:
            SessionInfo object or None if invalid
        """
        if not session_file.exists() or session_file.stat().st_size == 0:
            return None

        session_id = session_file.stem
        project_path_encoded = project_dir.name

        # Decode project path (e.g., "C--Users-layden" -> "C:\Users\layden")
        project_path = self._decode_project_path(project_path_encoded)

        # Get activity metrics
        metrics = self.get_session_activity(session_file)

        # Get last checkpoint time
        last_checkpoint = self._get_last_checkpoint_time(project_path)

        # Check for uncommitted changes
        uncommitted = self._has_uncommitted_changes(project_path)

        return SessionInfo(
            session_id=session_id,
            project_path=project_path,
            session_file_path=str(session_file),
            last_activity=metrics.last_activity,
            activity_metrics=metrics,
            last_checkpoint_time=last_checkpoint,
            uncommitted_changes=uncommitted
        )

    def _decode_project_path(self, encoded: str) -> str:
        """
        Decode project path from directory name

        Args:
            encoded: Encoded path (e.g., "C--Users-layden")

        Returns:
            Decoded path (e.g., "C:\\Users\\layden")
        """
        # On Windows, replace -- with :\ and - with \
        if '--' in encoded:
            # First occurrence of -- is drive letter
            parts = encoded.split('--', 1)
            if len(parts) == 2:
                drive = parts[0]
                rest = parts[1].replace('-', '\\')
                return f"{drive}:\\{rest}"

        # Unix paths: just replace - with /
        return encoded.replace('-', '/')

    def get_session_activity(self, session_file: Path) -> ActivityMetrics:
        """
        Analyze session activity from JSONL file

        Args:
            session_file: Path to session JSONL file

        Returns:
            ActivityMetrics object
        """
        metrics = ActivityMetrics()

        try:
            # Read last 100 lines for efficiency
            lines = []
            with open(session_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Take last 100 lines
            recent_lines = lines[-100:] if len(lines) > 100 else lines

            metrics.messages_count = len(recent_lines)

            # Parse JSONL entries
            last_timestamp = None
            files_modified = set()

            for line in recent_lines:
                try:
                    entry = json.loads(line.strip())

                    # Extract timestamp
                    if 'timestamp' in entry:
                        last_timestamp = entry['timestamp']

                    # Count file modifications
                    if 'type' in entry and entry['type'] in ['tool_use', 'tool_result']:
                        if 'content' in entry:
                            content = entry['content']
                            if isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict) and 'name' in item:
                                        if item['name'] in ['Edit', 'Write', 'NotebookEdit']:
                                            if 'input' in item and 'file_path' in item['input']:
                                                files_modified.add(item['input']['file_path'])

                except json.JSONDecodeError:
                    continue

            metrics.files_modified = len(files_modified)
            metrics.last_activity = last_timestamp

            # Calculate time since activity
            if last_timestamp:
                try:
                    last_time = datetime.fromisoformat(last_timestamp.replace('Z', '+00:00'))
                    now = datetime.now(last_time.tzinfo)
                    delta = now - last_time
                    metrics.time_since_activity_minutes = int(delta.total_seconds() / 60)
                except Exception:
                    pass

            # Estimate context tokens (rough estimate: ~100 tokens per message)
            metrics.estimated_context_tokens = metrics.messages_count * 100

        except Exception as e:
            # Return default metrics on error
            pass

        return metrics

    def _get_last_checkpoint_time(self, project_path: str) -> Optional[str]:
        """
        Get the timestamp of the last checkpoint for this project

        Args:
            project_path: Path to project

        Returns:
            ISO timestamp of last checkpoint or None
        """
        if not self.checkpoints_dir.exists():
            return None

        try:
            # Find latest checkpoint file for this project
            checkpoints = sorted(self.checkpoints_dir.glob('checkpoint-*.json'),
                               key=lambda p: p.stat().st_mtime,
                               reverse=True)

            for checkpoint_file in checkpoints:
                try:
                    with open(checkpoint_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Check if this checkpoint is for our project
                    if 'project' in data and data['project']:
                        cp_project_path = data['project'].get('absolute_path', '')
                        if cp_project_path == project_path:
                            return data.get('timestamp')

                except Exception:
                    continue

        except Exception:
            pass

        return None

    def _has_uncommitted_changes(self, project_path: str) -> bool:
        """
        Check if project has uncommitted git changes

        Args:
            project_path: Path to project

        Returns:
            True if uncommitted changes exist
        """
        try:
            # Check if it's a git repo
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return False

            # Check for uncommitted changes
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5
            )

            return bool(result.stdout.strip())

        except Exception:
            return False

    def get_session_by_id(self, session_id: str) -> Optional[SessionInfo]:
        """
        Get session info by session ID

        Args:
            session_id: Session ID to find

        Returns:
            SessionInfo or None if not found
        """
        sessions = self.find_active_sessions()
        for session in sessions:
            if session.session_id == session_id:
                return session
        return None


def main():
    """Command-line interface for testing"""
    import sys

    detector = SessionDetector()
    sessions = detector.find_active_sessions()

    print(f"Found {len(sessions)} active session(s):\n")

    for i, session in enumerate(sessions, 1):
        print(f"Session {i}:")
        print(f"  ID: {session.session_id}")
        print(f"  Project: {session.project_path}")
        print(f"  Last Activity: {session.last_activity or 'Unknown'}")
        print(f"  Messages: {session.activity_metrics.messages_count}")
        print(f"  Files Modified: {session.activity_metrics.files_modified}")

        if session.activity_metrics.time_since_activity_minutes is not None:
            mins = session.activity_metrics.time_since_activity_minutes
            if mins < 60:
                print(f"  Idle Time: {mins} minute(s)")
            else:
                hours = mins // 60
                print(f"  Idle Time: {hours} hour(s) {mins % 60} minute(s)")

        if session.last_checkpoint_time:
            print(f"  Last Checkpoint: {session.last_checkpoint_time}")
        else:
            print(f"  Last Checkpoint: Never")

        if session.uncommitted_changes:
            print(f"  Uncommitted Changes: Yes")

        print()

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
