#!/usr/bin/env python3
"""
Project Tracker - Detect and manage project switches

This module provides functionality to:
1. Track the currently active project
2. Detect when user switches to a different project
3. Determine if uncommitted work exists
4. Store/retrieve active project state
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple, Any


class ProjectTracker:
    """Tracks active project and detects switches"""

    def __init__(self):
        """Initialize the project tracker"""
        self.home_dir = Path.home()
        self.claude_dir = self.home_dir / ".claude"
        self.active_project_file = self.claude_dir / "active-project.json"

        # Ensure .claude directory exists
        self.claude_dir.mkdir(parents=True, exist_ok=True)

    def get_active_project(self) -> Optional[Dict[str, Any]]:
        """
        Load the currently active project state.

        Returns:
            Dict with project metadata and state, or None if no active project
        """
        if not self.active_project_file.exists():
            return None

        try:
            with open(self.active_project_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load active project state: {e}")
            return None

    def set_active_project(self, project_metadata: Dict[str, Any],
                          has_uncommitted: bool = False,
                          last_checkpoint: Optional[str] = None):
        """
        Set the currently active project.

        Args:
            project_metadata: Project identification (from _collect_project_metadata)
            has_uncommitted: Whether there are uncommitted changes
            last_checkpoint: ISO timestamp of last checkpoint
        """
        state = {
            'project': project_metadata,
            'has_uncommitted_changes': has_uncommitted,
            'last_checkpoint': last_checkpoint or datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }

        try:
            with open(self.active_project_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Warning: Could not save active project state: {e}")

    def clear_active_project(self):
        """Clear the active project state (clean slate)"""
        if self.active_project_file.exists():
            try:
                self.active_project_file.unlink()
            except OSError as e:
                print(f"Warning: Could not clear active project state: {e}")

    def projects_match(self, project_a: Dict[str, Any],
                      project_b: Dict[str, Any]) -> bool:
        """
        Determine if two projects are the same.

        Matching logic:
        1. Primary: Match by git_remote_url (if both have it)
        2. Fallback: Match by absolute_path
        3. Edge case: Warn if paths match but remote differs (remote changed)

        Args:
            project_a: First project metadata
            project_b: Second project metadata

        Returns:
            True if projects match, False otherwise
        """
        # Primary: Git remote URL match
        remote_a = project_a.get('git_remote_url')
        remote_b = project_b.get('git_remote_url')

        if remote_a and remote_b:
            # Normalize URLs (remove .git suffix, handle http vs https)
            remote_a_clean = remote_a.rstrip('.git').replace('http://', 'https://')
            remote_b_clean = remote_b.rstrip('.git').replace('http://', 'https://')

            if remote_a_clean == remote_b_clean:
                return True

            # If remotes differ but paths match, it's a remote change (still same project)
            if project_a.get('absolute_path') == project_b.get('absolute_path'):
                print(f"\nℹ️ Note: Git remote URL changed for this project")
                print(f"  Old: {remote_a}")
                print(f"  New: {remote_b}")
                return True  # Still same project, just remote changed

            return False

        # Fallback: Absolute path match (for local-only repos)
        path_a = project_a.get('absolute_path')
        path_b = project_b.get('absolute_path')

        if path_a and path_b:
            # Normalize paths (resolve symlinks, handle case sensitivity)
            path_a_resolved = str(Path(path_a).resolve())
            path_b_resolved = str(Path(path_b).resolve())
            return path_a_resolved == path_b_resolved

        # If we can't determine, assume different
        return False

    def detect_switch(self, current_project: Dict[str, Any]) -> Tuple[bool, Optional[Dict]]:
        """
        Detect if user has switched to a different project.

        Args:
            current_project: Current project metadata

        Returns:
            Tuple of (has_switched, active_project_state)
            - has_switched: True if project changed
            - active_project_state: Previous active project (if exists)
        """
        active_state = self.get_active_project()

        if not active_state:
            # No active project tracked yet
            return False, None

        active_project = active_state.get('project')
        if not active_project:
            # Malformed state
            return False, None

        # Compare projects
        if self.projects_match(current_project, active_project):
            # Same project
            return False, active_state
        else:
            # Different project - SWITCH DETECTED
            return True, active_state

    def has_uncommitted_changes(self, base_dir: Path) -> bool:
        """
        Check if the given directory has uncommitted git changes.

        Args:
            base_dir: Project directory to check

        Returns:
            True if there are uncommitted changes (staged or unstaged)
        """
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=base_dir,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                # If output is not empty, there are changes
                return bool(result.stdout.strip())

            return False
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            # If git command fails, assume no changes
            return False

    def get_project_summary(self, project_metadata: Dict[str, Any]) -> str:
        """
        Generate a human-readable summary of a project.

        Args:
            project_metadata: Project identification dict

        Returns:
            String summary like "project-name (github.com/user/repo, branch: main)"
        """
        name = project_metadata.get('name', 'Unknown')
        branch = project_metadata.get('git_branch', 'unknown')

        remote = project_metadata.get('git_remote_url', '')
        if remote:
            # Shorten GitHub URLs
            if 'github.com' in remote:
                import re
                match = re.search(r'github\.com[:/](.+?)(?:\.git)?$', remote)
                if match:
                    remote = f"github.com/{match.group(1)}"
        else:
            remote = project_metadata.get('absolute_path', 'local')

        return f"{name} ({remote}, branch: {branch})"

    def format_time_ago(self, iso_timestamp: str) -> str:
        """
        Format ISO timestamp as relative time (e.g., '2 hours ago').

        Args:
            iso_timestamp: ISO format timestamp string

        Returns:
            Human-readable relative time string
        """
        try:
            timestamp = datetime.fromisoformat(iso_timestamp)
            now = datetime.now()
            delta = now - timestamp

            if delta.total_seconds() < 60:
                return "just now"
            elif delta.total_seconds() < 3600:
                minutes = int(delta.total_seconds() / 60)
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            elif delta.total_seconds() < 86400:
                hours = int(delta.total_seconds() / 3600)
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            else:
                days = int(delta.total_seconds() / 86400)
                return f"{days} day{'s' if days != 1 else ''} ago"
        except (ValueError, TypeError):
            return "unknown"


# Convenience functions for easy importing
def get_active_project() -> Optional[Dict[str, Any]]:
    """Get the currently active project (convenience wrapper)"""
    tracker = ProjectTracker()
    return tracker.get_active_project()


def detect_project_switch(current_project: Dict[str, Any]) -> Tuple[bool, Optional[Dict]]:
    """Detect project switch (convenience wrapper)"""
    tracker = ProjectTracker()
    return tracker.detect_switch(current_project)


def update_active_project(project_metadata: Dict[str, Any],
                          has_uncommitted: bool = False,
                          last_checkpoint: Optional[str] = None):
    """Update active project state (convenience wrapper)"""
    tracker = ProjectTracker()
    tracker.set_active_project(project_metadata, has_uncommitted, last_checkpoint)


if __name__ == "__main__":
    # Simple CLI for testing/debugging
    import sys

    tracker = ProjectTracker()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "show":
            state = tracker.get_active_project()
            if state:
                print(json.dumps(state, indent=2))
            else:
                print("No active project")

        elif command == "clear":
            tracker.clear_active_project()
            print("Active project cleared")

        else:
            print(f"Unknown command: {command}")
            print("Usage: python project_tracker.py [show|clear]")
    else:
        state = tracker.get_active_project()
        if state:
            project = state['project']
            print(f"Active: {tracker.get_project_summary(project)}")
            print(f"Updated: {tracker.format_time_ago(state['updated_at'])}")
            if state.get('has_uncommitted_changes'):
                print("⚠️ Has uncommitted changes")
        else:
            print("No active project tracked")
