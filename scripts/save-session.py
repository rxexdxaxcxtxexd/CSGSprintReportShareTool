#!/usr/bin/env python3
"""
Automated Session Saver - Intelligently collect and save session data

This script automatically detects what happened during a Claude Code session by:
1. Analyzing git changes (if git repo)
2. Scanning directory for modified files
3. Parsing completed todo items
4. Inferring session metadata from changes

Usage:
    python save-session.py                    # Interactive mode
    python save-session.py --quick            # Quick save with auto-detection
    python save-session.py --dry-run          # Preview without saving
    python save-session.py --description "..." # Custom description
"""

import os
import sys
import json
import subprocess
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import re

# Import session logger
import importlib.util
spec = importlib.util.spec_from_file_location("session_logger",
    os.path.join(os.path.dirname(__file__), "session-logger.py"))
session_logger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session_logger)
SessionLogger = session_logger.SessionLogger


class SessionSaver:
    """Intelligently collect and save session data"""

    def __init__(self, base_dir: str = None):
        """Initialize the session saver"""
        if base_dir is None:
            base_dir = Path.home()

        self.base_dir = Path(base_dir)
        self.session_start_time = None
        self.is_git_repo = self._check_git_repo()

        # Directories to exclude from scanning
        self.exclude_dirs = {
            '.git', '.claude-sessions', '__pycache__', 'node_modules',
            '.venv', 'venv', 'env', '.tox', '.pytest_cache',
            'dist', 'build', '.eggs', '*.egg-info',
            '.mypy_cache', '.coverage', 'htmlcov'
        }

        # File patterns to exclude
        self.exclude_patterns = {
            '*.pyc', '*.pyo', '*.pyd', '.DS_Store', '*.swp', '*.swo',
            '*.log', '*.tmp', '*.temp', '*.cache', '*.bak', '*.backup',
            'thumbs.db', '*.class', '*.o', '*.so', '*.dylib', '*.dll'
        }

    def _check_git_repo(self) -> bool:
        """Check if current directory is a git repository"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--is-inside-work-tree'],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _should_exclude_path(self, path: Path) -> bool:
        """Check if path should be excluded from scanning"""
        path_str = str(path)

        # Check if any parent directory is in exclude list
        for part in path.parts:
            if part in self.exclude_dirs:
                return True

        # Check file patterns
        for pattern in self.exclude_patterns:
            if path.match(pattern):
                return True

        return False

    def collect_git_changes(self) -> List[Dict]:
        """Collect file changes using git"""
        if not self.is_git_repo:
            return []

        changes = []

        try:
            # Get staged and unstaged changes
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.base_dir,
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
                if self._should_exclude_path(Path(filepath)):
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

    def collect_file_changes(self, since_minutes: int = 240, max_depth: int = 3) -> List[Dict]:
        """Collect file changes based on modification time"""
        changes = []
        cutoff_time = datetime.now() - timedelta(minutes=since_minutes)
        max_files = 100  # Limit to prevent excessive scanning

        try:
            for root, dirs, files in os.walk(self.base_dir):
                # Calculate current depth
                depth = len(Path(root).relative_to(self.base_dir).parts)

                # Stop if too deep
                if depth >= max_depth:
                    dirs[:] = []  # Don't recurse deeper
                    continue

                # Filter out excluded directories
                dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

                for file in files:
                    # Stop if we've found enough files
                    if len(changes) >= max_files:
                        break

                    filepath = Path(root) / file

                    # Skip excluded paths
                    if self._should_exclude_path(filepath):
                        continue

                    try:
                        # Check modification time
                        mtime = datetime.fromtimestamp(filepath.stat().st_mtime)

                        if mtime > cutoff_time:
                            # Determine if created or modified
                            ctime = datetime.fromtimestamp(filepath.stat().st_ctime)
                            action = 'created' if ctime > cutoff_time else 'modified'

                            relative_path = filepath.relative_to(self.base_dir)

                            changes.append({
                                'file_path': str(relative_path),
                                'action': action,
                                'source': 'filesystem',
                                'modified': mtime.isoformat()
                            })
                    except (OSError, ValueError):
                        continue

                # Stop if we've found enough files
                if len(changes) >= max_files:
                    break

        except Exception as e:
            print(f"Warning: Error scanning filesystem: {e}")

        return changes

    def merge_changes(self, git_changes: List[Dict], fs_changes: List[Dict]) -> List[Dict]:
        """Merge and deduplicate changes from git and filesystem"""
        # Use git changes as primary source
        merged = {change['file_path']: change for change in git_changes}

        # Add filesystem changes that aren't in git
        for change in fs_changes:
            filepath = change['file_path']
            if filepath not in merged:
                merged[filepath] = change

        return list(merged.values())

    def parse_todo_items(self) -> List[Dict]:
        """Extract completed todo items from the session"""
        # This would integrate with Claude Code's todo system
        # For now, return empty list as placeholder
        # TODO: Implement actual todo parsing from Claude's internal state
        return []

    def infer_session_description(self, changes: List[Dict]) -> str:
        """Generate session description from file changes"""
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

    def suggest_resume_points(self, changes: List[Dict]) -> List[str]:
        """Suggest resume points based on changes"""
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
            most_recent = max(changes, key=lambda c: c.get('modified', ''))
            points.append(f"Continue work on {most_recent['file_path']}")

        return points if points else ["Resume from last modification"]

    def suggest_next_steps(self, changes: List[Dict]) -> List[str]:
        """Suggest next steps based on changes"""
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

    def interactive_save(self, auto_detected_data: Dict) -> Dict:
        """Interactive mode - prompt user for input"""
        print("\n" + "="*70)
        print("SESSION SAVER - Interactive Mode")
        print("="*70)

        # Session description
        default_desc = auto_detected_data['description']
        print(f"\nAuto-detected description: {default_desc}")
        user_desc = input("Enter session description (or press Enter to use auto-detected): ").strip()
        description = user_desc if user_desc else default_desc

        # Show detected changes
        changes = auto_detected_data['changes']
        print(f"\nDetected {len(changes)} file change(s):")
        for i, change in enumerate(changes[:10], 1):  # Show first 10
            print(f"  {i}. [{change['action']}] {change['file_path']}")
        if len(changes) > 10:
            print(f"  ... and {len(changes) - 10} more")

        # Resume points
        print(f"\nAuto-suggested resume points:")
        resume_points = auto_detected_data['resume_points']
        for i, point in enumerate(resume_points, 1):
            print(f"  {i}. {point}")

        add_more = input("\nAdd custom resume point? (y/n): ").strip().lower()
        if add_more == 'y':
            custom_point = input("Enter resume point: ").strip()
            if custom_point:
                resume_points.append(custom_point)

        # Next steps
        print(f"\nAuto-suggested next steps:")
        next_steps = auto_detected_data['next_steps']
        for i, step in enumerate(next_steps, 1):
            print(f"  {i}. {step}")

        add_step = input("\nAdd custom next step? (y/n): ").strip().lower()
        if add_step == 'y':
            custom_step = input("Enter next step: ").strip()
            if custom_step:
                next_steps.append(custom_step)

        # Problems encountered
        print("\nWere there any problems or blockers during this session?")
        problems = []
        while True:
            problem = input("Enter problem (or press Enter to skip): ").strip()
            if not problem:
                break
            problems.append(problem)

        # Decisions made
        print("\nWere any important decisions made during this session?")
        decisions = []
        while True:
            add_decision = input("Add a decision? (y/n): ").strip().lower()
            if add_decision != 'y':
                break

            question = input("  Question/Choice: ").strip()
            if not question:
                break

            decision = input("  Decision: ").strip()
            rationale = input("  Rationale: ").strip()

            decisions.append({
                'question': question,
                'decision': decision,
                'rationale': rationale
            })

        return {
            'description': description,
            'changes': changes,
            'resume_points': resume_points,
            'next_steps': next_steps,
            'problems': problems,
            'decisions': decisions
        }

    def quick_save(self, auto_detected_data: Dict) -> Dict:
        """Quick mode - use all auto-detected data"""
        print("\n" + "="*70)
        print("SESSION SAVER - Quick Save Mode")
        print("="*70)
        print(f"\nDescription: {auto_detected_data['description']}")
        print(f"Changes: {len(auto_detected_data['changes'])} file(s)")
        print(f"Resume points: {len(auto_detected_data['resume_points'])}")
        print(f"Next steps: {len(auto_detected_data['next_steps'])}")

        return auto_detected_data

    def save_session(self, session_data: Dict, dry_run: bool = False):
        """Save session using SessionLogger"""
        print("\n" + "="*70)
        if dry_run:
            print("DRY RUN - No files will be created")
        else:
            print("Saving session...")
        print("="*70)

        if dry_run:
            print("\nWould create checkpoint with:")
            print(f"  Description: {session_data['description']}")
            print(f"  File changes: {len(session_data['changes'])}")
            print(f"  Resume points: {len(session_data['resume_points'])}")
            print(f"  Next steps: {len(session_data['next_steps'])}")
            print(f"  Problems: {len(session_data.get('problems', []))}")
            print(f"  Decisions: {len(session_data.get('decisions', []))}")
            print("\nNo files created (dry run mode)")
            return

        # Initialize logger
        logger = SessionLogger()

        # Start session
        logger.start_session(
            session_data['description'],
            context={'auto_collected': True, 'tool': 'save-session.py'}
        )

        # Add file changes
        for change in session_data['changes']:
            logger.log_file_change(
                change['file_path'],
                change['action'],
                f"Auto-detected via {change.get('source', 'unknown')}"
            )

        # Add problems
        for problem in session_data.get('problems', []):
            logger.add_problem(problem)

        # Add decisions
        for decision in session_data.get('decisions', []):
            logger.log_decision(
                decision['question'],
                decision['decision'],
                decision['rationale'],
                decision.get('alternatives', [])
            )

        # Add resume points
        for point in session_data['resume_points']:
            logger.add_resume_point(point)

        # Add next steps
        for step in session_data['next_steps']:
            logger.add_next_step(step)

        # End session
        checkpoint_file, log_file = logger.end_session()

        # Update CLAUDE.md
        print("\nUpdating CLAUDE.md...")
        try:
            update_script = os.path.join(os.path.dirname(__file__), "update-session-state.py")
            result = subprocess.run(
                [sys.executable, update_script, 'update'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                print("[OK] CLAUDE.md updated successfully")
            else:
                print(f"Warning: CLAUDE.md update failed: {result.stderr}")
        except Exception as e:
            print(f"Warning: Could not update CLAUDE.md: {e}")

        print("\n" + "="*70)
        print("SESSION SAVED SUCCESSFULLY")
        print("="*70)
        print(f"\nCheckpoint: {checkpoint_file}")
        print(f"Log: {log_file}")
        print("\nTo resume in a new session:")
        print("  python scripts/resume-session.py")
        print("="*70)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Automatically collect and save Claude Code session data"
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick save with auto-detected data (no prompts)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be saved without creating files'
    )
    parser.add_argument(
        '--description',
        type=str,
        help='Custom session description'
    )
    parser.add_argument(
        '--since-minutes',
        type=int,
        default=240,
        help='Look for changes in the last N minutes (default: 240)'
    )

    args = parser.parse_args()

    # Initialize saver
    saver = SessionSaver()

    print("Collecting session data...")

    # Collect changes
    git_changes = saver.collect_git_changes()
    fs_changes = saver.collect_file_changes(since_minutes=args.since_minutes)
    all_changes = saver.merge_changes(git_changes, fs_changes)

    print(f"  Found {len(all_changes)} file change(s)")
    if saver.is_git_repo:
        print(f"    - {len(git_changes)} from git")
    print(f"    - {len(fs_changes)} from filesystem scan")

    # Generate auto-detected data
    auto_detected = {
        'description': args.description if args.description else saver.infer_session_description(all_changes),
        'changes': all_changes,
        'resume_points': saver.suggest_resume_points(all_changes),
        'next_steps': saver.suggest_next_steps(all_changes),
        'problems': [],
        'decisions': []
    }

    # Determine mode
    if args.quick or args.dry_run:
        session_data = saver.quick_save(auto_detected)
    else:
        session_data = saver.interactive_save(auto_detected)

    # Save session
    saver.save_session(session_data, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
