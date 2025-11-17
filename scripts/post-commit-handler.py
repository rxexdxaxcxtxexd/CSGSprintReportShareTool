#!/usr/bin/env python3
"""
Post-Commit Handler - Automatically create checkpoints after git commits

This script is invoked by the git post-commit hook to automatically
create session checkpoints for every commit.

Flow:
1. Get current commit information (hash, branch, remote, message, files)
2. Collect project metadata
3. Generate checkpoint content from commit
4. Create checkpoint using SessionLogger
5. Update checkpoint with git commit info
6. Register in session index
7. Update active project state

Usage:
  Called automatically by .git/hooks/post-commit
  Can also be run manually: python post-commit-handler.py
"""

import os
import sys
import json
import importlib.util
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


# Import utilities
def import_module(module_name: str, file_path: str):
    """Dynamically import a module from file path"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Determine script directory
SCRIPT_DIR = Path(__file__).parent

# Import checkpoint utilities
checkpoint_utils = import_module("checkpoint_utils", str(SCRIPT_DIR / "checkpoint_utils.py"))

# Import session logger
session_logger_mod = import_module("session_logger", str(SCRIPT_DIR / "session-logger.py"))
SessionLogger = session_logger_mod.SessionLogger

# Import session index
session_index_mod = import_module("session_index", str(SCRIPT_DIR / "session_index.py"))
SessionIndex = session_index_mod.SessionIndex

# Import project tracker
project_tracker_mod = import_module("project_tracker", str(SCRIPT_DIR / "project_tracker.py"))
ProjectTracker = project_tracker_mod.ProjectTracker


class PostCommitHandler:
    """Handle automatic checkpoint creation after git commits"""

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize the post-commit handler.

        Args:
            base_dir: Base directory (defaults to current working directory)
        """
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()

    def get_project_metadata(self) -> Dict[str, Any]:
        """
        Collect project metadata for the current directory.

        Returns:
            Project metadata dict
        """
        metadata = {
            'absolute_path': str(self.base_dir.resolve()),
            'name': self.base_dir.name
        }

        # Add git info
        metadata['git_remote_url'] = checkpoint_utils.get_git_remote_url(self.base_dir)
        metadata['git_branch'] = checkpoint_utils.get_git_branch(self.base_dir)
        metadata['git_head_hash'] = checkpoint_utils.get_git_commit_hash(self.base_dir)

        return metadata

    def create_checkpoint_for_commit(self) -> Optional[str]:
        """
        Create a checkpoint for the current HEAD commit.

        Returns:
            Checkpoint file path, or None if failed
        """
        try:
            # Get commit information
            commit_hash = checkpoint_utils.get_git_commit_hash(self.base_dir)
            if not commit_hash:
                print("Error: Could not get commit hash", file=sys.stderr)
                return None

            commit_message = checkpoint_utils.get_git_commit_message(self.base_dir, commit_hash)
            branch = checkpoint_utils.get_git_branch(self.base_dir)
            remote_url = checkpoint_utils.get_git_remote_url(self.base_dir)

            # Collect file changes from commit
            changes = checkpoint_utils.collect_git_commit_changes(self.base_dir, commit_hash)

            # Generate checkpoint content
            # Use commit message as description, or generate from changes
            if commit_message and not commit_message.startswith("Merge") and len(commit_message) > 5:
                # Use first line of commit message
                description = commit_message.split('\n')[0]
            else:
                description = checkpoint_utils.infer_session_description(changes)

            resume_points = checkpoint_utils.generate_resume_points(changes)
            next_steps = checkpoint_utils.generate_next_steps(changes)

            # Collect project metadata
            project_metadata = self.get_project_metadata()

            # Initialize session logger
            logger = SessionLogger(base_dir=str(self.base_dir))

            # Start session with context
            logger.start_session(
                description,
                context={
                    'auto_collected': True,
                    'tool': 'post-commit-hook',
                    'commit_hash': commit_hash,
                    'commit_message': commit_message,
                    'project': project_metadata
                }
            )

            # Log file changes
            for change in changes:
                logger.log_file_change(
                    change['file_path'],
                    change['action'],
                    description=f"From commit {commit_hash[:8]}"
                )

            # Add resume points
            for point in resume_points:
                logger.add_resume_point(point)

            # Add next steps
            for step in next_steps:
                logger.add_next_step(step)

            # Create checkpoint
            checkpoint_file = logger.create_checkpoint()

            if not checkpoint_file:
                print("Error: Checkpoint creation failed", file=sys.stderr)
                return None

            # Update checkpoint with git commit info
            checkpoint_path = Path(checkpoint_file)
            success = checkpoint_utils.update_checkpoint_with_git_info(
                checkpoint_path,
                commit_hash,
                branch,
                remote_url
            )

            if not success:
                print("Warning: Could not update checkpoint with git info", file=sys.stderr)

            # Register in session index
            try:
                with open(checkpoint_path, 'r', encoding='utf-8') as f:
                    checkpoint_data = json.load(f)

                index = SessionIndex()
                index.register_checkpoint(str(checkpoint_path), checkpoint_data)
            except Exception as e:
                print(f"Warning: Could not register checkpoint in index: {e}", file=sys.stderr)

            # Update active project state
            try:
                tracker = ProjectTracker()
                tracker.set_active_project(
                    project_metadata,
                    has_uncommitted=False,  # Just committed
                    last_checkpoint=datetime.now().isoformat()
                )
            except Exception as e:
                print(f"Warning: Could not update active project state: {e}", file=sys.stderr)

            return checkpoint_file

        except Exception as e:
            print(f"Error creating checkpoint: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return None

    def run(self):
        """
        Main entry point for post-commit hook.

        Returns:
            Exit code (0 for success, 1 for failure)
        """
        try:
            # Create checkpoint for current commit
            checkpoint_file = self.create_checkpoint_for_commit()

            if checkpoint_file:
                print(f"\nSUCCESS: Session checkpoint created: {Path(checkpoint_file).name}")
                return 0
            else:
                # Don't fail the commit even if checkpoint creation fails
                print("\nWARNING: Checkpoint creation failed (commit succeeded)", file=sys.stderr)
                return 0  # Return 0 to not break git workflow

        except Exception as e:
            # Catch all exceptions to prevent breaking git workflow
            print(f"\nWARNING: Post-commit hook error: {e}", file=sys.stderr)
            return 0  # Return 0 to not break git workflow


def main():
    """Command-line interface for testing"""
    handler = PostCommitHandler()
    exit_code = handler.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
