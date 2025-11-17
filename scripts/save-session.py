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

# Import project tracker
spec_tracker = importlib.util.spec_from_file_location("project_tracker",
    os.path.join(os.path.dirname(__file__), "project_tracker.py"))
project_tracker = importlib.util.module_from_spec(spec_tracker)
spec_tracker.loader.exec_module(project_tracker)
ProjectTracker = project_tracker.ProjectTracker

# Import session index
spec_index = importlib.util.spec_from_file_location("session_index",
    os.path.join(os.path.dirname(__file__), "session_index.py"))
session_index = importlib.util.module_from_spec(spec_index)
spec_index.loader.exec_module(session_index)
SessionIndex = session_index.SessionIndex

# Import checkpoint utilities
spec_utils = importlib.util.spec_from_file_location("checkpoint_utils",
    os.path.join(os.path.dirname(__file__), "checkpoint_utils.py"))
checkpoint_utils = importlib.util.module_from_spec(spec_utils)
spec_utils.loader.exec_module(checkpoint_utils)


# ============================================================================
# PROJECT DETECTION AND SELECTION
# ============================================================================

def get_git_info(directory: Path) -> Optional[Dict]:
    """Get git repository information for a directory"""
    try:
        # Check if it's a git repo
        result = subprocess.run(
            ['git', 'rev-parse', '--is-inside-work-tree'],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return None

        # Get remote URL
        remote_result = subprocess.run(
            ['git', 'config', '--get', 'remote.origin.url'],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=5
        )
        remote_url = remote_result.stdout.strip() if remote_result.returncode == 0 else "No remote"

        # Get current branch
        branch_result = subprocess.run(
            ['git', 'branch', '--show-current'],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=5
        )
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"

        # Format remote URL for display (shorten GitHub URLs)
        display_url = remote_url
        if 'github.com' in remote_url:
            # Extract repo name from URL
            match = re.search(r'github\.com[:/](.+?)(?:\.git)?$', remote_url)
            if match:
                display_url = f"github.com/{match.group(1)}"

        return {
            'remote_url': remote_url,
            'display_url': display_url,
            'branch': branch,
            'is_git_repo': True
        }
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return None


def discover_projects() -> List[Dict]:
    """Discover potential project directories"""
    projects = []
    home = Path.home()

    # Check current working directory
    cwd = Path.cwd()
    if cwd != home:
        git_info = get_git_info(cwd)
        if git_info:
            projects.append({
                'path': cwd,
                'name': cwd.name,
                'git_info': git_info,
                'source': 'current'
            })

    # Check common project locations
    project_dirs = [
        home / 'Projects',
        home / 'Codebases',
        home / 'projects',
        home / 'repos',
        home / 'code',
        home / 'dev'
    ]

    for project_dir in project_dirs:
        if not project_dir.exists():
            continue

        try:
            # Look for subdirectories with .git
            for subdir in project_dir.iterdir():
                if not subdir.is_dir():
                    continue

                # Skip hidden directories
                if subdir.name.startswith('.'):
                    continue

                git_info = get_git_info(subdir)
                if git_info:
                    # Skip if already added (e.g., from cwd)
                    if any(p['path'] == subdir for p in projects):
                        continue

                    projects.append({
                        'path': subdir,
                        'name': subdir.name,
                        'git_info': git_info,
                        'source': 'discovered'
                    })

                # Limit to avoid excessive scanning
                if len(projects) >= 20:
                    break
        except (PermissionError, OSError):
            continue

    return projects


def prompt_for_project_directory() -> Path:
    """Interactive prompt to select a project directory"""
    projects = discover_projects()

    if not projects:
        print("\n" + "="*70)
        print("ERROR: No git repositories found")
        print("="*70)
        print("\nSession tracking requires a git repository.")
        print("Please:")
        print("  1. Navigate to a project directory with git")
        print("  2. Or initialize git in your current directory:")
        print("     git init && git remote add origin <url>")
        print("="*70)
        sys.exit(1)

    print("\n" + "="*70)
    print("SELECT PROJECT DIRECTORY")
    print("="*70)
    print("\nAvailable projects:\n")

    for i, project in enumerate(projects, 1):
        git = project['git_info']
        marker = " (current)" if project['source'] == 'current' else ""
        print(f"  {i}. {project['name']}{marker}")
        print(f"     Path:   {project['path']}")
        print(f"     Git:    {git['display_url']}")
        print(f"     Branch: {git['branch']}")
        print()

    print(f"  0. Enter custom path")
    print()

    while True:
        try:
            choice = input("Select project (number): ").strip()

            if choice == '0':
                custom_path = input("Enter project directory path: ").strip()
                custom_path = Path(custom_path).expanduser().resolve()

                if not custom_path.exists():
                    print(f"Error: Directory does not exist: {custom_path}")
                    continue

                git_info = get_git_info(custom_path)
                if not git_info:
                    print(f"Error: Not a git repository: {custom_path}")
                    continue

                return custom_path

            choice_num = int(choice)
            if 1 <= choice_num <= len(projects):
                selected = projects[choice_num - 1]
                print(f"\n✓ Selected: {selected['name']}")
                print(f"  Path: {selected['path']}")
                print(f"  Git:  {selected['git_info']['display_url']}")
                print(f"  Branch: {selected['git_info']['branch']}")
                return selected['path']
            else:
                print(f"Error: Please enter a number between 0 and {len(projects)}")
        except ValueError:
            print("Error: Please enter a valid number")
        except KeyboardInterrupt:
            print("\n\nSession tracking cancelled.")
            sys.exit(0)


def print_project_context(base_dir: Path, is_git_repo: bool, auto_commit: bool = True):
    """Display project context information"""
    print("\n" + "="*70)
    print("PROJECT CONTEXT")
    print("="*70)

    print(f"  Directory: {base_dir}")

    if is_git_repo:
        git_info = get_git_info(base_dir)
        if git_info:
            print(f"  Git Repo:  {git_info['display_url']}")
            print(f"  Branch:    {git_info['branch']}")
            print(f"  Auto-commit: {'ENABLED' if auto_commit else 'DISABLED'}")
    else:
        print("  Git: Not a git repository")
        print("  Warning: Auto-commit disabled")

    print("="*70)


def handle_project_switch(current_project: Dict[str, Any],
                         active_state: Dict[str, Any]) -> str:
    """
    Prompt user when a project switch is detected.

    Args:
        current_project: Current project metadata
        active_state: Previous active project state

    Returns:
        User's choice: 'checkpoint', 'discard', or 'cancel'
    """
    tracker = ProjectTracker()
    active_project = active_state['project']

    print("\n" + "="*70)
    print("⚠️ PROJECT SWITCH DETECTED")
    print("="*70)

    print(f"\nPrevious project: {tracker.get_project_summary(active_project)}")
    print(f"Current project:  {tracker.get_project_summary(current_project)}")

    # Check if previous project has uncommitted work
    has_uncommitted = active_state.get('has_uncommitted_changes', False)

    if has_uncommitted:
        print(f"\n⚠️  WARNING: You have uncommitted work in the previous project!")
        print(f"   Last checkpoint: {tracker.format_time_ago(active_state.get('last_checkpoint', ''))}")

    print("\nWhat would you like to do?")
    print("  1. Create checkpoint for previous project first (recommended)")
    print("  2. Discard previous project changes and track current project")
    print("  3. Cancel (don't create any checkpoint)")
    print()

    while True:
        try:
            choice = input("Your choice (1-3): ").strip()

            if choice == '1':
                return 'checkpoint'
            elif choice == '2':
                confirm = input("⚠️  Confirm discard? Type 'yes' to confirm: ").strip().lower()
                if confirm == 'yes':
                    return 'discard'
                else:
                    print("Discard cancelled. Please choose again.")
                    continue
            elif choice == '3':
                return 'cancel'
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
        except (KeyboardInterrupt, EOFError):
            print("\n\nOperation cancelled.")
            return 'cancel'


class SessionSaver:
    """Intelligently collect and save session data"""

    def __init__(self, base_dir: str = None):
        """Initialize the session saver"""
        if base_dir is None:
            base_dir = Path.cwd()

        self.base_dir = Path(base_dir)

        # HOME DIRECTORY GUARD: Refuse to track from home directory
        if self.base_dir == Path.home():
            print("\n" + "="*70)
            print("ERROR: Cannot track session from home directory")
            print("="*70)
            print("\nSession tracking requires a project directory with git.")
            print("Your current directory is your home directory, which would")
            print("track personal files, system folders, and unrelated projects.\n")

            # Prompt for project selection
            self.base_dir = prompt_for_project_directory()

        self.session_start_time = None
        self.is_git_repo = self._check_git_repo()

        # CRITICAL: Hard block if home directory is a git repository
        if self.base_dir == Path.home() and self.is_git_repo:
            print("\n" + "="*70)
            print("CRITICAL ERROR: Home directory is a git repository")
            print("="*70)
            print("\nThis is EXTREMELY DANGEROUS and will track:")
            print("  • Personal files and documents")
            print("  • System configuration files")
            print("  • All your projects (mixed together)")
            print("  • Private data")
            print("\nRefusing to proceed.")
            print("\nTo fix this:")
            print("  1. Use a proper project directory for your work")
            print("  2. Or remove .git from your home directory:")
            print("     cd ~")
            print("     rm -rf .git")
            print("\nSession tracking ABORTED.")
            print("="*70)
            sys.exit(1)

        # Directories to exclude from scanning
        self.exclude_dirs = {
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
        self.exclude_patterns = {
            '*.pyc', '*.pyo', '*.pyd', '.DS_Store', '*.swp', '*.swo',
            '*.log', '*.tmp', '*.temp', '*.cache', '*.bak', '*.backup',
            'thumbs.db', '*.class', '*.o', '*.so', '*.dylib', '*.dll',
            # System files
            'NTUSER.*', '*.lnk', 'ntuser.*'
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

    def _get_git_remote_url(self) -> str:
        """Get git remote URL"""
        try:
            result = subprocess.run(
                ['git', 'config', '--get', 'remote.origin.url'],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return "No remote"
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return "Unknown"

    def _get_git_branch(self) -> str:
        """Get current git branch"""
        try:
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return "unknown"
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return "unknown"

    def _get_git_head_hash(self) -> Optional[str]:
        """Get current HEAD commit hash"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return None

    def _collect_project_metadata(self) -> Dict[str, Any]:
        """
        Collect comprehensive project identification metadata.

        Returns dict with:
        - git_remote_url: Primary identifier (portable across machines)
        - absolute_path: Fallback identifier (machine-specific)
        - name: Human-readable project name
        - git_head_hash: Current commit (state validation)
        - git_branch: Current branch
        """
        metadata = {
            'absolute_path': str(self.base_dir.resolve()),
            'name': self.base_dir.name,
        }

        # Add git information if available
        if self.is_git_repo:
            metadata['git_remote_url'] = self._get_git_remote_url()
            metadata['git_branch'] = self._get_git_branch()
            metadata['git_head_hash'] = self._get_git_head_hash()

        return metadata

    def has_uncommitted_changes(self, base_dir: Path) -> bool:
        """
        Check if there are uncommitted git changes.

        Args:
            base_dir: Directory to check

        Returns:
            True if there are uncommitted changes
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
                return bool(result.stdout.strip())

            return False
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return False

    def _git_add_files(self, files: List[str]) -> bool:
        """Stage files for commit"""
        try:
            result = subprocess.run(
                ['git', 'add'] + files,
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            print(f"Warning: Failed to stage files: {e}")
            return False

    def _git_commit(self, message: str) -> Optional[str]:
        """Create git commit and return commit hash"""
        try:
            result = subprocess.run(
                ['git', 'commit', '-m', message],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                # Check if it's because there's nothing to commit
                if 'nothing to commit' in result.stdout or 'nothing to commit' in result.stderr:
                    return None
                print(f"Warning: Git commit failed: {result.stderr}")
                return None

            # Get the commit hash
            hash_result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=5
            )

            if hash_result.returncode == 0:
                return hash_result.stdout.strip()

            return "unknown"
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            print(f"Warning: Git commit failed: {e}")
            return None

    def _format_commit_message(self, session_data: Dict, checkpoint_file: str) -> str:
        """Generate formatted commit message for session checkpoint"""
        description = session_data.get('description', 'Work session')
        changes = session_data.get('changes', [])

        # Start with session description
        message = f"Session checkpoint: {description}\n\n"

        # Add session metadata
        message += f"Session ID: {checkpoint_file.split('-')[1] if '-' in checkpoint_file else 'unknown'}\n"
        message += f"Timestamp: {datetime.now().isoformat()}\n"
        message += f"Files changed: {len(changes)}\n"
        message += f"Checkpoint: {os.path.basename(checkpoint_file)}\n\n"

        # Add change summary (limit to 10 files)
        if changes:
            message += "Changes:\n"
            for i, change in enumerate(changes[:10]):
                action = change.get('action', 'modified')
                filepath = change.get('file_path', 'unknown')
                message += f"- {filepath} ({action})\n"

            if len(changes) > 10:
                message += f"... and {len(changes) - 10} more files\n"

        # Add footer
        message += "\n🤖 Generated with Claude Code\n"
        message += "https://claude.com/claude-code\n\n"
        message += "Co-authored-by: Claude <noreply@anthropic.com>"

        return message


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
        return checkpoint_utils.infer_session_description(changes)

    def suggest_resume_points(self, changes: List[Dict]) -> List[str]:
        """Suggest resume points based on changes"""
        return checkpoint_utils.generate_resume_points(changes)

    def suggest_next_steps(self, changes: List[Dict]) -> List[str]:
        """Suggest next steps based on changes"""
        return checkpoint_utils.generate_next_steps(changes)

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

        # Initialize logger with project base directory
        logger = SessionLogger(base_dir=str(self.base_dir))

        # Collect project metadata
        project_metadata = self._collect_project_metadata()

        # Start session
        logger.start_session(
            session_data['description'],
            context={
                'auto_collected': True,
                'tool': 'save-session.py',
                'project': project_metadata
            }
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

        # Register checkpoint in session index
        print("\nRegistering in session index...")
        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)

            index = SessionIndex()
            index.register_checkpoint(checkpoint_file, checkpoint_data)
        except Exception as e:
            print(f"  Warning: Could not register checkpoint in index: {e}")

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
        print("SESSION CHECKPOINT CREATED")
        print("="*70)
        print(f"\nCheckpoint: {os.path.basename(checkpoint_file)}")
        print(f"Log:        {os.path.basename(log_file)}")

        print(f"\nFiles tracked: {len(session_data.get('changes', []))}")
        print(f"Resume points: {len(session_data.get('resume_points', []))}")
        print(f"Next steps:    {len(session_data.get('next_steps', []))}")

        # Instructions for manual commit (unified workflow)
        if self.is_git_repo:
            print("\n" + "-"*70)
            print("NEXT STEP: Create Git Commit")
            print("-"*70)
            print("\nTo finalize this checkpoint, commit your changes:")
            print(f"  git add .")
            print(f"  git commit -m \"Your commit message\"")
            print("\nThe post-commit hook will automatically link this checkpoint")
            print("to your commit and update it with commit information.")
            print()
            print("Need to install the hook? Run:")
            print("  python scripts/install-hooks.py")

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

    # PROJECT SWITCH DETECTION
    # Collect current project metadata
    current_project = saver._collect_project_metadata()

    # Check for project switch
    tracker = ProjectTracker()
    has_switched, active_state = tracker.detect_switch(current_project)

    if has_switched and active_state:
        # Project switch detected - prompt user
        choice = handle_project_switch(current_project, active_state)

        if choice == 'checkpoint':
            # User wants to checkpoint the previous project first
            print("\n📦 Creating checkpoint for previous project...")

            active_project = active_state['project']
            prev_base_dir = Path(active_project['absolute_path'])

            # Create new saver for previous project
            prev_saver = SessionSaver(base_dir=str(prev_base_dir))

            # Collect changes from previous project
            print(f"Collecting changes from {active_project['name']}...")
            prev_git_changes = prev_saver.collect_git_changes()
            prev_fs_changes = prev_saver.collect_file_changes(since_minutes=args.since_minutes)
            prev_all_changes = prev_saver.merge_changes(prev_git_changes, prev_fs_changes)

            print(f"  Found {len(prev_all_changes)} file change(s) in previous project")

            # Generate session data for previous project
            prev_session_data = {
                'description': f"[Auto-checkpoint before switch] {prev_saver.infer_session_description(prev_all_changes)}",
                'changes': prev_all_changes,
                'resume_points': prev_saver.suggest_resume_points(prev_all_changes),
                'next_steps': prev_saver.suggest_next_steps(prev_all_changes),
                'problems': [],
                'decisions': []
            }

            # Save previous project session
            prev_saver.save_session(prev_session_data, dry_run=False)

            print(f"\n✓ Previous project checkpointed successfully!")
            print(f"\nNow continuing with current project: {current_project['name']}\n")

        elif choice == 'discard':
            # User chose to discard previous project changes
            print(f"\n⚠️  Discarding changes from {active_state['project']['name']}")
            print(f"Continuing with current project: {current_project['name']}\n")

        elif choice == 'cancel':
            # User cancelled - exit without creating any checkpoint
            print("\nOperation cancelled. No checkpoint created.")
            sys.exit(0)

    # Update active project state (will be finalized after checkpoint)
    # For now, just note that we're tracking this project
    tracker.set_active_project(
        current_project,
        has_uncommitted=saver.has_uncommitted_changes(saver.base_dir),
        last_checkpoint=None  # Will be updated after save
    )

    # Display project context
    print_project_context(saver.base_dir, saver.is_git_repo, auto_commit=True)

    print("\nCollecting session data...")

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

    # Update active project state after successful save (if not dry-run)
    if not args.dry_run:
        tracker.set_active_project(
            current_project,
            has_uncommitted=False,  # Just checkpointed, so no uncommitted changes
            last_checkpoint=datetime.now().isoformat()
        )


if __name__ == "__main__":
    main()
