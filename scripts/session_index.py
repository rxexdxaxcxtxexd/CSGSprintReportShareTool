#!/usr/bin/env python3
"""
Session Index - Central registry for multi-project checkpoints

This module provides functionality to:
1. Maintain a central index of all projects and their checkpoints
2. Enable fast lookup of checkpoints by project
3. Support cross-project checkpoint queries
4. Track checkpoint metadata for filtering and search
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict


@dataclass
class CheckpointIndexEntry:
    """Represents a checkpoint entry in the index"""
    checkpoint_id: str  # e.g., "checkpoint-20251117-143000"
    checkpoint_path: str  # Full path to checkpoint file
    project_path: str  # Project absolute path
    project_name: str  # Project name
    git_remote_url: Optional[str]  # Git remote (if applicable)
    git_branch: Optional[str]  # Git branch
    session_id: str  # Session ID
    timestamp: str  # ISO format timestamp
    description: Optional[str]  # Session description
    file_change_count: int  # Number of files changed
    task_count: int  # Number of tasks completed


class SessionIndex:
    """Manages the central session index"""

    def __init__(self):
        """Initialize the session index"""
        self.home_dir = Path.home()
        self.claude_dir = self.home_dir / ".claude"
        self.index_file = self.claude_dir / "session-index.json"

        # Ensure .claude directory exists
        self.claude_dir.mkdir(parents=True, exist_ok=True)

        # Load existing index
        self.index = self._load_index()

    def _load_index(self) -> Dict[str, Any]:
        """
        Load the session index from disk.

        Returns:
            Dict with structure:
            {
              "version": "1.0",
              "last_updated": "2025-11-17T14:30:00",
              "projects": {
                "project-absolute-path": {
                  "project_name": "...",
                  "git_remote_url": "...",
                  "last_checkpoint": "...",
                  "checkpoint_count": 42,
                  "checkpoints": [
                    { CheckpointIndexEntry as dict }
                  ]
                }
              }
            }
        """
        if not self.index_file.exists():
            return {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "projects": {}
            }

        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load session index: {e}")
            # Return fresh index on error
            return {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "projects": {}
            }

    def _save_index(self):
        """Save the session index to disk"""
        self.index["last_updated"] = datetime.now().isoformat()

        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Warning: Could not save session index: {e}")

    def register_checkpoint(self, checkpoint_path: str, checkpoint_data: Dict[str, Any]):
        """
        Register a checkpoint in the central index.

        Args:
            checkpoint_path: Full path to the checkpoint JSON file
            checkpoint_data: The loaded checkpoint data (SessionCheckpoint as dict)
        """
        # Extract project metadata
        project_info = checkpoint_data.get('project')
        if not project_info:
            print("Warning: Checkpoint missing project metadata, cannot index")
            return

        project_path = project_info.get('absolute_path')
        if not project_path:
            print("Warning: Checkpoint missing project path, cannot index")
            return

        # Create checkpoint entry
        entry = CheckpointIndexEntry(
            checkpoint_id=Path(checkpoint_path).stem,  # e.g., "checkpoint-20251117-143000"
            checkpoint_path=str(checkpoint_path),
            project_path=project_path,
            project_name=project_info.get('name', 'Unknown'),
            git_remote_url=project_info.get('git_remote_url'),
            git_branch=project_info.get('git_branch'),
            session_id=checkpoint_data.get('session_id', 'unknown'),
            timestamp=checkpoint_data.get('timestamp', datetime.now().isoformat()),
            description=checkpoint_data.get('context', {}).get('description'),
            file_change_count=len(checkpoint_data.get('file_changes', [])),
            task_count=len(checkpoint_data.get('completed_tasks', []))
        )

        # Get or create project entry
        projects = self.index.setdefault('projects', {})
        project_entry = projects.setdefault(project_path, {
            "project_name": entry.project_name,
            "git_remote_url": entry.git_remote_url,
            "last_checkpoint": None,
            "checkpoint_count": 0,
            "checkpoints": []
        })

        # Update project metadata
        project_entry["project_name"] = entry.project_name
        project_entry["git_remote_url"] = entry.git_remote_url
        project_entry["last_checkpoint"] = entry.timestamp
        project_entry["checkpoint_count"] = project_entry.get("checkpoint_count", 0) + 1

        # Add checkpoint to list (keep last 50 per project)
        checkpoints = project_entry.setdefault("checkpoints", [])
        checkpoints.append(asdict(entry))

        # Trim to last 50 checkpoints per project
        if len(checkpoints) > 50:
            checkpoints[:] = checkpoints[-50:]
            project_entry["checkpoint_count"] = len(checkpoints)

        # Save updated index
        self._save_index()

        print(f"SUCCESS: Checkpoint registered in session index")

    def get_project_checkpoints(self, project_path: str,
                               limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all checkpoints for a specific project.

        Args:
            project_path: Absolute path to project
            limit: Maximum number of checkpoints to return (most recent first)

        Returns:
            List of checkpoint entries (as dicts), sorted by timestamp descending
        """
        projects = self.index.get('projects', {})
        project_entry = projects.get(project_path)

        if not project_entry:
            return []

        checkpoints = project_entry.get('checkpoints', [])

        # Sort by timestamp (most recent first)
        sorted_checkpoints = sorted(
            checkpoints,
            key=lambda c: c.get('timestamp', ''),
            reverse=True
        )

        if limit:
            return sorted_checkpoints[:limit]

        return sorted_checkpoints

    def list_all_projects(self) -> List[Dict[str, Any]]:
        """
        Get a list of all tracked projects.

        Returns:
            List of project summaries with:
            - project_path
            - project_name
            - git_remote_url
            - last_checkpoint
            - checkpoint_count
        """
        projects = self.index.get('projects', {})

        project_list = []
        for path, info in projects.items():
            project_list.append({
                'project_path': path,
                'project_name': info.get('project_name', 'Unknown'),
                'git_remote_url': info.get('git_remote_url'),
                'last_checkpoint': info.get('last_checkpoint'),
                'checkpoint_count': info.get('checkpoint_count', 0)
            })

        # Sort by last checkpoint (most recent first)
        project_list.sort(
            key=lambda p: p.get('last_checkpoint', ''),
            reverse=True
        )

        return project_list

    def query_checkpoints(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Query checkpoints across all projects with filters.

        Args:
            filters: Dict with optional keys:
                - project_name: str (partial match)
                - git_remote_url: str (partial match)
                - session_id: str (exact match)
                - date_from: str (ISO format, inclusive)
                - date_to: str (ISO format, inclusive)
                - min_file_changes: int
                - min_tasks: int

        Returns:
            List of matching checkpoint entries, sorted by timestamp descending
        """
        all_checkpoints = []

        # Collect all checkpoints from all projects
        projects = self.index.get('projects', {})
        for project_path, project_info in projects.items():
            checkpoints = project_info.get('checkpoints', [])
            all_checkpoints.extend(checkpoints)

        # Apply filters
        filtered = all_checkpoints

        if filters.get('project_name'):
            project_name = filters['project_name'].lower()
            filtered = [c for c in filtered
                       if project_name in c.get('project_name', '').lower()]

        if filters.get('git_remote_url'):
            remote_url = filters['git_remote_url'].lower()
            filtered = [c for c in filtered
                       if remote_url in (c.get('git_remote_url') or '').lower()]

        if filters.get('session_id'):
            session_id = filters['session_id']
            filtered = [c for c in filtered
                       if c.get('session_id') == session_id]

        if filters.get('date_from'):
            date_from = filters['date_from']
            filtered = [c for c in filtered
                       if c.get('timestamp', '') >= date_from]

        if filters.get('date_to'):
            date_to = filters['date_to']
            filtered = [c for c in filtered
                       if c.get('timestamp', '') <= date_to]

        if filters.get('min_file_changes'):
            min_files = filters['min_file_changes']
            filtered = [c for c in filtered
                       if c.get('file_change_count', 0) >= min_files]

        if filters.get('min_tasks'):
            min_tasks = filters['min_tasks']
            filtered = [c for c in filtered
                       if c.get('task_count', 0) >= min_tasks]

        # Sort by timestamp (most recent first)
        filtered.sort(key=lambda c: c.get('timestamp', ''), reverse=True)

        return filtered

    def get_latest_checkpoint(self, project_path: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent checkpoint for a project.

        Args:
            project_path: Absolute path to project

        Returns:
            Checkpoint entry dict, or None if no checkpoints
        """
        checkpoints = self.get_project_checkpoints(project_path, limit=1)
        return checkpoints[0] if checkpoints else None

    def rebuild_index(self, checkpoints_dir: Path) -> int:
        """
        Rebuild the entire index by scanning checkpoint files.

        Args:
            checkpoints_dir: Directory containing checkpoint JSON files

        Returns:
            Number of checkpoints indexed
        """
        # Clear existing index
        self.index = {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "projects": {}
        }

        count = 0

        # Scan all checkpoint files
        if not checkpoints_dir.exists():
            print(f"Checkpoints directory does not exist: {checkpoints_dir}")
            return 0

        checkpoint_files = sorted(checkpoints_dir.glob("checkpoint-*.json"))

        print(f"Rebuilding index from {len(checkpoint_files)} checkpoint file(s)...")

        for checkpoint_file in checkpoint_files:
            try:
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    checkpoint_data = json.load(f)

                self.register_checkpoint(str(checkpoint_file), checkpoint_data)
                count += 1

            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load {checkpoint_file.name}: {e}")
                continue

        print(f"SUCCESS: Index rebuilt - {count} checkpoint(s) indexed across {len(self.index['projects'])} project(s)")

        return count


# Convenience functions for easy importing
def register_checkpoint(checkpoint_path: str, checkpoint_data: Dict[str, Any]):
    """Register a checkpoint (convenience wrapper)"""
    index = SessionIndex()
    index.register_checkpoint(checkpoint_path, checkpoint_data)


def get_project_checkpoints(project_path: str, limit: Optional[int] = None) -> List[Dict]:
    """Get project checkpoints (convenience wrapper)"""
    index = SessionIndex()
    return index.get_project_checkpoints(project_path, limit)


def list_all_projects() -> List[Dict]:
    """List all projects (convenience wrapper)"""
    index = SessionIndex()
    return index.list_all_projects()


if __name__ == "__main__":
    # Simple CLI for testing/debugging
    import sys

    index = SessionIndex()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "list":
            # List all projects
            projects = index.list_all_projects()
            if projects:
                print(f"\n{'='*70}")
                print(f"TRACKED PROJECTS ({len(projects)})")
                print(f"{'='*70}")
                for proj in projects:
                    print(f"\nProject: {proj['project_name']}")
                    print(f"  Path: {proj['project_path']}")
                    if proj['git_remote_url']:
                        print(f"  Remote: {proj['git_remote_url']}")
                    print(f"  Checkpoints: {proj['checkpoint_count']}")
                    print(f"  Last: {proj['last_checkpoint']}")
            else:
                print("No projects tracked yet")

        elif command == "rebuild":
            # Rebuild index
            checkpoints_dir = Path.home() / ".claude-sessions" / "checkpoints"
            count = index.rebuild_index(checkpoints_dir)
            print(f"\nIndex rebuilt: {count} checkpoints")

        elif command == "show":
            # Show index structure
            print(json.dumps(index.index, indent=2))

        else:
            print(f"Unknown command: {command}")
            print("Usage: python session_index.py [list|rebuild|show]")
    else:
        # Default: show summary
        projects = index.list_all_projects()
        print(f"\nSession Index Summary:")
        print(f"  Projects tracked: {len(projects)}")
        total_checkpoints = sum(p['checkpoint_count'] for p in projects)
        print(f"  Total checkpoints: {total_checkpoints}")
        print(f"  Last updated: {index.index.get('last_updated', 'unknown')}")
        print(f"\nRun 'python session_index.py list' to see all projects")
