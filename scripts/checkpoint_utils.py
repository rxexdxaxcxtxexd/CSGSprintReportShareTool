#!/usr/bin/env python3
"""
Checkpoint Utilities - Reusable functions for checkpoint creation

This module provides utility functions for creating and managing checkpoints
that can be used by both save-session.py and the git post-commit hook.

Functions:
- collect_git_changes() - Get file changes from git status
- collect_git_commit_changes() - Get files from a specific commit
- generate_resume_points() - Auto-generate resume points from changes
- generate_next_steps() - Auto-generate next steps from changes
- infer_session_description() - Generate description from file changes
- update_checkpoint_with_git_info() - Add git metadata to checkpoint
- get_git_branch() - Get current git branch
- get_git_remote_url() - Get git remote URL
- get_git_commit_hash() - Get current HEAD commit hash
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


# Directories to exclude from scanning
EXCLUDE_DIRS = {
    '.git', '.claude-sessions', '__pycache__', 'node_modules',
    '.venv', 'venv', 'env', '.tox', '.pytest_cache',
    'dist', 'build', '.eggs', '*.egg-info',
    '.mypy_cache', '.coverage', 'htmlcov',
    # Home directory user folders (extra safety)
    'AppData', 'Documents', 'Downloads', 'Pictures', 'Music',
    'Videos', 'Desktop', 'OneDrive', 'Favorites', 'Links',
    'Searches', 'Saved Games', 'Contacts', 'IntelGraphicsProfiles'
}

# File patterns to exclude
EXCLUDE_PATTERNS = {
    '*.pyc', '*.pyo', '*.pyd', '.DS_Store', '*.swp', '*.swo',
    '*.log', '*.tmp', '*.temp', '*.cache', '*.bak', '*.backup',
    'thumbs.db', '*.class', '*.o', '*.so', '*.dylib', '*.dll',
    # System files
    'NTUSER.*', '*.lnk', 'ntuser.*'
}


def _should_exclude_path(path: Path) -> bool:
    """Check if path should be excluded from scanning"""
    # Check if any parent directory is in exclude list
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return True

    # Check file patterns
    for pattern in EXCLUDE_PATTERNS:
        if path.match(pattern):
            return True

    return False


def collect_git_changes(base_dir: Path) -> List[Dict]:
    """
    Collect file changes using git status (staged and unstaged).

    Args:
        base_dir: Base directory of git repository

    Returns:
        List of file change dicts with 'file_path', 'action', 'source'
    """
    changes = []

    try:
        # Get staged and unstaged changes
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=base_dir,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return []

        # Parse git status output
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue

            status = line[:2]
            filepath = line[3:].strip()

            # Skip excluded paths
            if _should_exclude_path(Path(filepath)):
                continue

            # Determine action
            action = 'modified'
            if '??' in status:
                action = 'created'
            elif 'D' in status:
                action = 'deleted'
            elif 'A' in status:
                action = 'created'
            elif 'M' in status:
                action = 'modified'

            changes.append({
                'file_path': filepath,
                'action': action,
                'source': 'git'
            })

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return changes


def collect_git_commit_changes(base_dir: Path, commit_hash: Optional[str] = None) -> List[Dict]:
    """
    Collect file changes from a specific git commit.

    Args:
        base_dir: Base directory of git repository
        commit_hash: Commit hash (defaults to HEAD)

    Returns:
        List of file change dicts with 'file_path', 'action', 'source'
    """
    changes = []

    try:
        commit = commit_hash or 'HEAD'

        # Get files changed in commit
        result = subprocess.run(
            ['git', 'diff-tree', '--no-commit-tree', '--name-status', '-r', commit],
            cwd=base_dir,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return []

        # Parse diff-tree output
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue

            parts = line.split('\t')
            if len(parts) < 2:
                continue

            status = parts[0]
            filepath = parts[1]

            # Skip excluded paths
            if _should_exclude_path(Path(filepath)):
                continue

            # Determine action
            action = 'modified'
            if status.startswith('A'):
                action = 'created'
            elif status.startswith('D'):
                action = 'deleted'
            elif status.startswith('M'):
                action = 'modified'

            changes.append({
                'file_path': filepath,
                'action': action,
                'source': 'git-commit'
            })

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return changes


def infer_session_description(changes: List[Dict]) -> str:
    """
    Generate session description from file changes.

    Args:
        changes: List of file change dicts

    Returns:
        Human-readable session description
    """
    if not changes:
        return "Work session"

    # Analyze file types and patterns
    file_types = {}
    directories = set()

    for change in changes:
        filepath = Path(change['file_path'])
        ext = filepath.suffix.lower()
        directory = filepath.parent

        file_types[ext] = file_types.get(ext, 0) + 1
        if directory != Path('.'):
            directories.add(str(directory))

    # Generate description based on patterns
    descriptions = []

    # Check for specific patterns
    if any('test' in change['file_path'].lower() for change in changes):
        descriptions.append("test development")

    if any('README' in change['file_path'] or '.md' in change['file_path'] for change in changes):
        descriptions.append("documentation updates")

    if '.py' in file_types:
        descriptions.append(f"Python development ({file_types['.py']} files)")

    if '.js' in file_types or '.ts' in file_types or '.jsx' in file_types or '.tsx' in file_types:
        count = sum(file_types.get(ext, 0) for ext in ['.js', '.ts', '.jsx', '.tsx'])
        descriptions.append(f"JavaScript/TypeScript development ({count} files)")

    if any('config' in change['file_path'].lower() or 'setup' in change['file_path'].lower() for change in changes):
        descriptions.append("configuration changes")

    # If we found patterns, use them
    if descriptions:
        return "Work on " + ", ".join(descriptions)

    # Fallback: use directory names
    if directories:
        dir_list = list(directories)[:2]
        return f"Changes in {', '.join(dir_list)}"

    return f"Modified {len(changes)} file(s)"


def generate_resume_points(changes: List[Dict]) -> List[str]:
    """
    Suggest resume points based on file changes.

    Args:
        changes: List of file change dicts

    Returns:
        List of resume point strings
    """
    points = []

    # Check for incomplete work indicators
    for change in changes:
        filepath = change['file_path']

        if 'test' in filepath.lower() and change['action'] == 'created':
            points.append(f"Run and verify tests in {filepath}")

        if 'TODO' in filepath or 'FIXME' in filepath:
            points.append(f"Complete TODO items in {filepath}")

    # Generic resume point
    if changes:
        # Use first file as resume point
        points.append(f"Continue work on {changes[0]['file_path']}")

    return points if points else ["Resume from last modification"]


def generate_next_steps(changes: List[Dict]) -> List[str]:
    """
    Suggest next steps based on file changes.

    Args:
        changes: List of file change dicts

    Returns:
        List of next step strings
    """
    steps = []

    # Analyze patterns
    has_tests = any('test' in c['file_path'].lower() for c in changes)
    has_docs = any('.md' in c['file_path'].lower() for c in changes)
    has_code = any('.py' in c['file_path'] or '.js' in c['file_path'] or '.ts' in c['file_path'] for c in changes)

    if has_code and not has_tests:
        steps.append("Write tests for new/modified code")

    if has_code and not has_docs:
        steps.append("Update documentation to reflect code changes")

    if has_tests:
        steps.append("Run full test suite to ensure no regressions")

    if any(c['action'] == 'created' for c in changes):
        steps.append("Review newly created files for completeness")

    # Generic next step
    steps.append("Verify all changes work as expected")

    return steps


def get_git_remote_url(base_dir: Path) -> str:
    """
    Get git remote URL.

    Args:
        base_dir: Base directory of git repository

    Returns:
        Remote URL string, or "No remote" if not found
    """
    try:
        result = subprocess.run(
            ['git', 'config', '--get', 'remote.origin.url'],
            cwd=base_dir,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return "No remote"
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return "Unknown"


def get_git_branch(base_dir: Path) -> str:
    """
    Get current git branch.

    Args:
        base_dir: Base directory of git repository

    Returns:
        Branch name, or "unknown" if not found
    """
    try:
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            cwd=base_dir,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return "unknown"
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return "unknown"


def get_git_commit_hash(base_dir: Path) -> Optional[str]:
    """
    Get current HEAD commit hash.

    Args:
        base_dir: Base directory of git repository

    Returns:
        Commit hash, or None if not found
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=base_dir,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return None


def get_git_commit_message(base_dir: Path, commit_hash: Optional[str] = None) -> str:
    """
    Get commit message for a specific commit.

    Args:
        base_dir: Base directory of git repository
        commit_hash: Commit hash (defaults to HEAD)

    Returns:
        Commit message, or empty string if not found
    """
    try:
        commit = commit_hash or 'HEAD'
        result = subprocess.run(
            ['git', 'log', '-1', '--pretty=%B', commit],
            cwd=base_dir,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return ""
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return ""


def update_checkpoint_with_git_info(checkpoint_path: Path, commit_hash: str,
                                    branch: str, remote_url: str) -> bool:
    """
    Update an existing checkpoint file with git commit information.

    Args:
        checkpoint_path: Path to checkpoint JSON file
        commit_hash: Git commit hash
        branch: Git branch name
        remote_url: Git remote URL

    Returns:
        True if successful, False otherwise
    """
    try:
        # Read checkpoint
        with open(checkpoint_path, 'r', encoding='utf-8') as f:
            checkpoint_data = json.load(f)

        # Add git info
        checkpoint_data['git_commit_hash'] = commit_hash
        checkpoint_data['git_branch'] = branch
        checkpoint_data['git_remote_url'] = remote_url

        # Write back
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)

        return True

    except Exception as e:
        print(f"Warning: Could not update checkpoint with git info: {e}")
        return False


if __name__ == "__main__":
    # Simple test when run directly
    import sys

    if len(sys.argv) < 2:
        print("Usage: python checkpoint_utils.py <git-repo-path>")
        sys.exit(1)

    repo_path = Path(sys.argv[1])

    if not repo_path.exists():
        print(f"Path does not exist: {repo_path}")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"CHECKPOINT UTILITIES TEST")
    print(f"{'='*70}")
    print(f"Repository: {repo_path}")
    print()

    # Test git info collection
    print(f"Branch: {get_git_branch(repo_path)}")
    print(f"Remote: {get_git_remote_url(repo_path)}")
    print(f"Commit: {get_git_commit_hash(repo_path)}")
    print()

    # Test file changes collection
    changes = collect_git_changes(repo_path)
    print(f"Changes (git status): {len(changes)}")
    for change in changes[:5]:
        print(f"  {change['action']:8} {change['file_path']}")
    if len(changes) > 5:
        print(f"  ... and {len(changes) - 5} more")
    print()

    # Test description generation
    description = infer_session_description(changes)
    print(f"Description: {description}")
    print()

    # Test resume points
    resume_points = generate_resume_points(changes)
    print(f"Resume Points:")
    for point in resume_points:
        print(f"  - {point}")
    print()

    # Test next steps
    next_steps = generate_next_steps(changes)
    print(f"Next Steps:")
    for step in next_steps:
        print(f"  - {step}")

    print(f"{'='*70}")
