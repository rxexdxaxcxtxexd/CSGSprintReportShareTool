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

    # File size and type limits
    MAX_FILE_SIZE = 1_000_000  # 1MB
    BINARY_EXTENSIONS = {
        '.exe', '.dll', '.so', '.dylib', '.bin',
        '.zip', '.tar', '.gz', '.rar', '.7z',
        '.mp4', '.avi', '.mov', '.mp3', '.wav',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.db', '.sqlite', '.sqlite3',
        '.whl', '.egg'
    }

    def __init__(self, base_dir: str = None):
        """Initialize the session saver"""
        if base_dir is None:
            base_dir = Path.home()

        self.base_dir = Path(base_dir)
        self.session_start_time = None
        self.is_git_repo = self._check_git_repo()
        self.skipped_files = {'large': 0, 'binary': 0}  # Track skipped files
        self.history_path = Path.home() / '.claude' / 'history.jsonl'

        # Directories to exclude from scanning
        self.exclude_dirs = {
            '.git', '.claude-sessions', '.claude', '__pycache__', 'node_modules',
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

    def detect_session_boundary(self, gap_minutes: int = 60) -> Optional[datetime]:
        """Detect session start by finding gaps in history.jsonl

        Args:
            gap_minutes: Minimum gap size to consider a session boundary (default: 60)

        Returns:
            Session start time, or None if can't detect
        """
        if not self.history_path.exists():
            return None

        try:
            # Read history entries (last 200 to keep it fast)
            entries = []
            with open(self.history_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        if 'timestamp' in entry:
                            entries.append(entry)
                    except json.JSONDecodeError:
                        continue

            if not entries:
                return None

            # Get recent entries (last 200)
            recent_entries = entries[-200:]

            # Find the most recent gap > gap_minutes
            gap_threshold = timedelta(minutes=gap_minutes)
            session_start = None

            for i in range(len(recent_entries) - 1, 0, -1):
                current_ts = datetime.fromtimestamp(recent_entries[i]['timestamp'] / 1000)
                prev_ts = datetime.fromtimestamp(recent_entries[i-1]['timestamp'] / 1000)

                gap = current_ts - prev_ts

                if gap > gap_threshold:
                    # Found a gap - session starts after this gap
                    session_start = current_ts
                    break

            # If no gap found, use the earliest entry in recent history
            if session_start is None and recent_entries:
                session_start = datetime.fromtimestamp(recent_entries[0]['timestamp'] / 1000)

            return session_start

        except Exception as e:
            print(f"Warning: Could not detect session boundary: {e}")
            return None

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
        """Collect file changes based on modification time

        Uses session_start_time if available, otherwise falls back to since_minutes
        """
        changes = []

        # Use session_start_time if detected, otherwise use since_minutes
        if self.session_start_time:
            cutoff_time = self.session_start_time
        else:
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
                        # Check file stats
                        file_stats = filepath.stat()

                        # Skip binary files
                        if filepath.suffix.lower() in self.BINARY_EXTENSIONS:
                            self.skipped_files['binary'] += 1
                            continue

                        # Skip large files
                        if file_stats.st_size > self.MAX_FILE_SIZE:
                            self.skipped_files['large'] += 1
                            continue

                        # Check modification time
                        mtime = datetime.fromtimestamp(file_stats.st_mtime)

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

    def _analyze_python_file(self, filepath: Path) -> List[str]:
        """Analyze Python file for incomplete work using AST

        Returns list of specific resume points found in the file
        """
        points = []

        try:
            import ast

            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse AST
            try:
                tree = ast.parse(content, filename=str(filepath))
            except SyntaxError:
                # If there's a syntax error, that's definitely incomplete work!
                points.append(f"Fix syntax error in {filepath}")
                return points

            # Find incomplete functions (only has pass or docstring)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check if function body is just pass or docstring
                    body = node.body
                    if len(body) == 1:
                        if isinstance(body[0], ast.Pass):
                            points.append(f"Implement {node.name}() in {filepath}:{node.lineno}")
                        elif isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Str):
                            # Just a docstring, no implementation
                            points.append(f"Implement {node.name}() in {filepath}:{node.lineno}")

                    # Check for TODO/FIXME/HACK in function
                    if len(body) > 0 and isinstance(body[0], ast.Expr):
                        if isinstance(body[0].value, (ast.Str, ast.Constant)):
                            docstring = ast.get_docstring(node) or ""
                            if any(marker in docstring.upper() for marker in ['TODO', 'FIXME', 'HACK', 'XXX']):
                                points.append(f"Address TODO in {node.name}() at {filepath}:{node.lineno}")

        except Exception:
            # Silently fail - not critical
            pass

        return points

    def _find_todo_comments(self, filepath: Path) -> List[str]:
        """Find TODO/FIXME/HACK comments in file

        Returns list of resume points for TODO items
        """
        points = []
        todo_pattern = re.compile(r'#\s*(TODO|FIXME|HACK|XXX|NOTE|OPTIMIZE):?\s*(.+)', re.IGNORECASE)

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    match = todo_pattern.search(line)
                    if match:
                        marker = match.group(1).upper()
                        description = match.group(2).strip()[:50]  # Limit length
                        points.append(f"[{marker}] {description} ({filepath}:{line_num})")

        except Exception:
            pass

        return points

    def suggest_resume_points(self, changes: List[Dict]) -> List[str]:
        """Suggest smart resume points based on changes

        Enhanced with:
        - Python AST parsing for incomplete functions
        - TODO/FIXME comment detection
        - File-type-specific suggestions
        - Work-in-progress indicators
        """
        points = []

        # Analyze recently modified files (limit to 10 most recent)
        recent_changes = sorted(
            changes,
            key=lambda c: c.get('modified', ''),
            reverse=True
        )[:10]

        for change in recent_changes:
            filepath_str = change['file_path']
            filepath = self.base_dir / filepath_str

            if not filepath.exists():
                continue

            # Skip if too large or binary
            if filepath.suffix.lower() in self.BINARY_EXTENSIONS:
                continue

            try:
                if filepath.stat().st_size > self.MAX_FILE_SIZE:
                    continue
            except OSError:
                continue

            # Python-specific analysis
            if filepath.suffix == '.py':
                py_points = self._analyze_python_file(filepath)
                points.extend(py_points)

                # Find TODO comments
                todo_points = self._find_todo_comments(filepath)
                points.extend(todo_points)

            # File-type-specific suggestions
            elif filepath.suffix in ['.js', '.ts', '.jsx', '.tsx']:
                # JavaScript/TypeScript - look for console.log (debugging) or TODO
                todo_points = self._find_todo_comments(filepath)
                points.extend(todo_points)

                # Check for debugging code
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if 'console.log' in content or 'debugger;' in content:
                            points.append(f"Remove debugging code from {filepath_str}")
                except Exception:
                    pass

            # Test files
            if 'test' in filepath_str.lower():
                points.append(f"Run and verify tests in {filepath_str}")

            # Configuration files that were modified
            elif filepath.suffix in ['.json', '.yaml', '.yml', '.toml', '.ini', '.cfg']:
                points.append(f"Verify configuration changes in {filepath_str}")

        # Check for newly created files
        created_files = [c for c in changes if c['action'] == 'created']
        if created_files:
            points.append(f"Review {len(created_files)} newly created file(s) for completeness")

        # Generic resume point from most recent change
        if recent_changes and not points:
            most_recent = recent_changes[0]
            points.append(f"Continue work on {most_recent['file_path']}")

        # Deduplicate and limit
        points = list(dict.fromkeys(points))  # Remove duplicates while preserving order
        points = points[:15]  # Limit to top 15

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

    # Detect session boundary
    session_start = saver.detect_session_boundary()
    if session_start:
        saver.session_start_time = session_start
        minutes_ago = (datetime.now() - session_start).total_seconds() / 60
        print(f"Detected session start: {session_start.strftime('%Y-%m-%d %H:%M:%S')} ({minutes_ago:.0f} minutes ago)")
    else:
        print(f"Using fallback: last {args.since_minutes} minutes")

    print("Collecting session data...")

    # Collect changes
    git_changes = saver.collect_git_changes()
    fs_changes = saver.collect_file_changes(since_minutes=args.since_minutes)
    all_changes = saver.merge_changes(git_changes, fs_changes)

    print(f"  Found {len(all_changes)} file change(s)")
    if saver.is_git_repo:
        print(f"    - {len(git_changes)} from git")
    print(f"    - {len(fs_changes)} from filesystem scan")

    # Report skipped files
    if saver.skipped_files['binary'] > 0 or saver.skipped_files['large'] > 0:
        print(f"  Skipped:")
        if saver.skipped_files['binary'] > 0:
            print(f"    - {saver.skipped_files['binary']} binary file(s)")
        if saver.skipped_files['large'] > 0:
            print(f"    - {saver.skipped_files['large']} large file(s) (>{saver.MAX_FILE_SIZE:,} bytes)")

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
