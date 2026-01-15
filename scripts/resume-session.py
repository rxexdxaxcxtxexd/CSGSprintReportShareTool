#!/usr/bin/env python3
"""
Resume Session - Load and display previous session information

This script helps resume work in a new Claude Code session by:
1. Loading the latest checkpoint
2. Displaying session state in an easy-to-read format
3. Providing context for continuation
4. Suggesting next steps
"""

import json
import os
import sys
import importlib.util
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich import box

# Import session index
spec_index = importlib.util.spec_from_file_location("session_index",
    os.path.join(os.path.dirname(__file__), "session_index.py"))
session_index = importlib.util.module_from_spec(spec_index)
spec_index.loader.exec_module(session_index)
SessionIndex = session_index.SessionIndex

# Import task context modules
try:
    from task_stack import TaskStack
    from session_state_manager import SessionState
    from mode_detector import ModeDetector
    TASK_CONTEXT_AVAILABLE = True
except ImportError:
    TASK_CONTEXT_AVAILABLE = False


class SessionResumer:
    """Load and display previous session information"""

    def __init__(self, base_dir: str = None):
        """Initialize the session resumer"""
        if base_dir is None:
            base_dir = Path.cwd()  # Use current working directory, not home

        self.base_dir = Path(base_dir)
        self.checkpoints_dir = Path.home() / ".claude-sessions" / "checkpoints"
        self.logs_dir = Path.home() / ".claude-sessions" / "logs"

        # Try to use rich for pretty output, fall back to simple print
        # On Windows, rich can have encoding issues, so default to simple
        try:
            import sys
            import platform
            # Disable rich on Windows due to encoding issues
            if platform.system() == 'Windows':
                self.console = None
                self.use_rich = False
            else:
                self.console = Console()
                self.use_rich = True
        except Exception:
            self.console = None
            self.use_rich = False

    def _get_current_project_metadata(self) -> Optional[Dict[str, Any]]:
        """
        Get project metadata for the current working directory.

        Returns:
            Project metadata dict, or None if not in a project directory
        """
        try:
            import subprocess

            # Check if current directory is a git repo
            result = subprocess.run(
                ['git', 'rev-parse', '--is-inside-work-tree'],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return None

            metadata = {
                'absolute_path': str(self.base_dir.resolve()),
                'name': self.base_dir.name
            }

            # Get git info
            try:
                # Remote URL
                remote_result = subprocess.run(
                    ['git', 'config', '--get', 'remote.origin.url'],
                    cwd=self.base_dir,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if remote_result.returncode == 0:
                    metadata['git_remote_url'] = remote_result.stdout.strip()

                # Branch
                branch_result = subprocess.run(
                    ['git', 'branch', '--show-current'],
                    cwd=self.base_dir,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if branch_result.returncode == 0:
                    metadata['git_branch'] = branch_result.stdout.strip()
            except:
                pass

            return metadata

        except Exception:
            return None

    def _projects_match(self, project_a: Optional[Dict], project_b: Optional[Dict]) -> bool:
        """
        Check if two project metadata dicts represent the same project.

        Args:
            project_a: First project metadata
            project_b: Second project metadata

        Returns:
            True if projects match, False otherwise
        """
        if not project_a or not project_b:
            return False

        # Primary: Git remote URL match
        remote_a = project_a.get('git_remote_url')
        remote_b = project_b.get('git_remote_url')

        if remote_a and remote_b:
            # Normalize URLs
            remote_a_clean = remote_a.rstrip('.git').replace('http://', 'https://')
            remote_b_clean = remote_b.rstrip('.git').replace('http://', 'https://')
            if remote_a_clean == remote_b_clean:
                return True

        # Fallback: Absolute path match
        path_a = project_a.get('absolute_path')
        path_b = project_b.get('absolute_path')

        if path_a and path_b:
            return str(Path(path_a).resolve()) == str(Path(path_b).resolve())

        return False

    def validate_checkpoint_project(self, checkpoint: dict) -> Optional[str]:
        """
        Validate that checkpoint belongs to current project.

        Args:
            checkpoint: Checkpoint data

        Returns:
            Warning message if mismatch, None if OK
        """
        checkpoint_project = checkpoint.get('project')
        if not checkpoint_project:
            return "⚠️ Checkpoint has no project metadata (old checkpoint)"

        current_project = self._get_current_project_metadata()
        if not current_project:
            # Not in a git project directory
            return None

        if not self._projects_match(checkpoint_project, current_project):
            # Project mismatch!
            checkpoint_name = checkpoint_project.get('name', 'Unknown')
            current_name = current_project.get('name', 'Unknown')
            return (
                f"⚠️ PROJECT MISMATCH!\n"
                f"  Checkpoint from: {checkpoint_name}\n"
                f"  Current project: {current_name}\n"
                f"  This checkpoint may not apply to your current work."
            )

        return None

    def load_latest_checkpoint(self) -> Optional[dict]:
        """Load the most recent checkpoint"""
        if not self.checkpoints_dir.exists():
            return None

        checkpoint_files = sorted(self.checkpoints_dir.glob("checkpoint-*.json"), reverse=True)

        if not checkpoint_files:
            return None

        latest = checkpoint_files[0]

        with open(latest, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_checkpoint_by_id(self, session_id: str) -> Optional[dict]:
        """Load a specific checkpoint by session ID"""
        if not self.checkpoints_dir.exists():
            return None

        for checkpoint_file in self.checkpoints_dir.glob("checkpoint-*.json"):
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get('session_id') == session_id:
                    return data

        return None

    def load_task_context(self):
        """Load task stack and session state"""
        if not TASK_CONTEXT_AVAILABLE:
            return None

        try:
            task_stack = TaskStack()
            task_stack.load()

            session_state = SessionState()
            session_state.load()

            return {
                'task_stack': task_stack,
                'session_state': session_state,
                'current_task': task_stack.current()
            }
        except Exception as e:
            return None

    def list_checkpoints(self) -> List[dict]:
        """List all available checkpoints"""
        if not self.checkpoints_dir.exists():
            return []

        checkpoints = []
        for checkpoint_file in sorted(self.checkpoints_dir.glob("checkpoint-*.json"), reverse=True):
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                checkpoints.append({
                    'file': checkpoint_file.name,
                    'session_id': data.get('session_id'),
                    'timestamp': data.get('timestamp'),
                    'current_task': data.get('current_task'),
                    'completed_count': len(data.get('completed_tasks', [])),
                    'pending_count': len(data.get('pending_tasks', []))
                })

        return checkpoints

    def display_checkpoint_rich(self, checkpoint: dict):
        """Display checkpoint information using rich formatting"""
        # Header
        self.console.print(Panel.fit(
            f"[bold cyan]Session: {checkpoint['session_id']}[/bold cyan]\n"
            f"[dim]Started: {checkpoint['started_at']}[/dim]\n"
            f"[dim]Checkpoint: {checkpoint['timestamp']}[/dim]",
            title="📋 Session Checkpoint",
            border_style="cyan"
        ))

        # Project Information (if available)
        project = checkpoint.get('project')
        if project:
            self.console.print(f"\n[bold cyan]📂 Project:[/bold cyan]")
            self.console.print(f"  Name:   {project.get('name', 'Unknown')}")
            self.console.print(f"  Path:   {project.get('absolute_path', 'Unknown')}")
            if project.get('git_remote_url'):
                remote_url = project['git_remote_url']
                # Shorten GitHub URLs
                if 'github.com' in remote_url:
                    import re
                    match = re.search(r'github\.com[:/](.+?)(?:\.git)?$', remote_url)
                    if match:
                        remote_url = f"github.com/{match.group(1)}"
                self.console.print(f"  Remote: {remote_url}")
            if project.get('git_branch'):
                self.console.print(f"  Branch: {project['git_branch']}")
        else:
            self.console.print(f"\n[dim]⚠️ Project metadata not available (old checkpoint)[/dim]")

        # Context
        context = checkpoint.get('context', {})
        if context:
            self.console.print("\n[bold]📌 Session Context:[/bold]")
            if context.get('description'):
                self.console.print(f"  {context['description']}")
            for key, value in context.items():
                if key != 'description':
                    self.console.print(f"  • {key}: {value}")

        # Current Task
        current_task = checkpoint.get('current_task')
        if current_task:
            self.console.print(f"\n[bold green]🔄 Current Task:[/bold green]")
            self.console.print(f"  {current_task}")

        # Completed Tasks
        completed = checkpoint.get('completed_tasks', [])
        if completed:
            self.console.print(f"\n[bold green]✅ Completed Tasks ({len(completed)}):[/bold green]")
            for task in completed[-5:]:  # Show last 5
                self.console.print(f"  • {task['description']}")
                if task.get('notes'):
                    self.console.print(f"    [dim]{task['notes']}[/dim]")

        # Pending Tasks
        pending = checkpoint.get('pending_tasks', [])
        if pending:
            self.console.print(f"\n[bold yellow]⏸️ Pending Tasks ({len(pending)}):[/bold yellow]")
            for task in pending[:5]:  # Show first 5
                status = task.get('status', 'pending')
                emoji = "⏳" if status == "in_progress" else "⏸️"
                self.console.print(f"  {emoji} {task['description']}")

        # Decisions
        decisions = checkpoint.get('decisions', [])
        if decisions:
            self.console.print(f"\n[bold blue]💡 Decisions Made ({len(decisions)}):[/bold blue]")
            for dec in decisions[-3:]:  # Show last 3
                self.console.print(f"\n  [bold]{dec['question']}[/bold]")
                self.console.print(f"  → {dec['decision']}")
                self.console.print(f"  [dim]{dec['rationale']}[/dim]")

        # File Changes
        file_changes = checkpoint.get('file_changes', [])
        if file_changes:
            self.console.print(f"\n[bold magenta]📝 File Changes ({len(file_changes)}):[/bold magenta]")
            for change in file_changes[-5:]:  # Show last 5
                action = change['action']
                emoji = {"created": "➕", "modified": "✏️", "deleted": "❌"}.get(action, "📝")
                self.console.print(f"  {emoji} [{action}] {change['file_path']}")

        # Git Commit Information
        git_commit = checkpoint.get('git_commit_hash')
        if git_commit:
            self.console.print(f"\n[bold cyan]🔗 Git Commit:[/bold cyan]")
            self.console.print(f"  Hash:   {git_commit[:8]}")
            if checkpoint.get('git_branch'):
                self.console.print(f"  Branch: {checkpoint['git_branch']}")
            if checkpoint.get('git_remote_url'):
                remote_url = checkpoint['git_remote_url']
                # Shorten GitHub URLs
                if 'github.com' in remote_url:
                    import re
                    match = re.search(r'github\.com[:/](.+?)(?:\.git)?$', remote_url)
                    if match:
                        remote_url = f"github.com/{match.group(1)}"
                self.console.print(f"  Remote: {remote_url}")

        # Problems
        problems = checkpoint.get('problems_encountered', [])
        if problems:
            self.console.print(f"\n[bold red]⚠️ Problems Encountered:[/bold red]")
            for problem in problems:
                self.console.print(f"  • {problem}")

        # Resume Points
        resume_points = checkpoint.get('resume_points', [])
        if resume_points:
            self.console.print(Panel(
                "\n".join([f"{i}. {point}" for i, point in enumerate(resume_points, 1)]),
                title="🎯 Resume Points",
                border_style="green"
            ))

        # Next Steps
        next_steps = checkpoint.get('next_steps', [])
        if next_steps:
            self.console.print(Panel(
                "\n".join([f"[ ] {step}" for step in next_steps]),
                title="➡️ Next Steps",
                border_style="yellow"
            ))

    def display_task_context(self, task_context):
        """Display task stack and current session state"""
        if not task_context:
            return

        # Use simple print for Windows compatibility
        print("\n" + "=" * 70)
        print(" " * 25 + "TASK CONTEXT")
        print("=" * 70)

        task_stack = task_context['task_stack']
        session_state = task_context['session_state']

        # Show current task
        current = task_stack.current()
        if current:
            print(f"\nCurrent Task: {current}")

        # Show session mode
        if session_state.mode:
            print(f"Session Mode: {session_state.mode}")

        # Show pending work
        if session_state.pending_work:
            print(f"\nPending Work:")
            for item in session_state.pending_work[:5]:  # Show first 5
                print(f"  - {item}")

        # Show recent decisions
        if session_state.decisions:
            print(f"\nRecent Decisions:")
            for decision in session_state.decisions[-3:]:  # Last 3
                print(f"  - {decision.decision}")

        print("=" * 70)

    def display_checkpoint_simple(self, checkpoint: dict):
        """Display checkpoint information using simple text formatting"""
        print("\n" + "="*60)
        print(f"SESSION CHECKPOINT: {checkpoint['session_id']}")
        print("="*60)
        print(f"Started: {checkpoint['started_at']}")
        print(f"Checkpoint: {checkpoint['timestamp']}")

        # Project Information (if available)
        project = checkpoint.get('project')
        if project:
            print("\n[PROJECT]")
            print(f"  Name:   {project.get('name', 'Unknown')}")
            print(f"  Path:   {project.get('absolute_path', 'Unknown')}")
            if project.get('git_remote_url'):
                remote_url = project['git_remote_url']
                # Shorten GitHub URLs
                if 'github.com' in remote_url:
                    import re
                    match = re.search(r'github\.com[:/](.+?)(?:\.git)?$', remote_url)
                    if match:
                        remote_url = f"github.com/{match.group(1)}"
                print(f"  Remote: {remote_url}")
            if project.get('git_branch'):
                print(f"  Branch: {project['git_branch']}")
        else:
            print("\n[!] Project metadata not available (old checkpoint)")

        # Context
        context = checkpoint.get('context', {})
        if context:
            print("\n[SESSION CONTEXT]")
            if context.get('description'):
                print(f"  {context['description']}")
            for key, value in context.items():
                if key != 'description':
                    print(f"  - {key}: {value}")

        # Current Task
        current_task = checkpoint.get('current_task')
        if current_task:
            print(f"\n[CURRENT TASK]")
            print(f"  {current_task}")

        # Completed Tasks
        completed = checkpoint.get('completed_tasks', [])
        if completed:
            print(f"\n[COMPLETED TASKS] ({len(completed)})")
            for task in completed[-5:]:
                print(f"  + {task['description']}")

        # Pending Tasks
        pending = checkpoint.get('pending_tasks', [])
        if pending:
            print(f"\n[PENDING TASKS] ({len(pending)})")
            for task in pending[:5]:
                print(f"  - {task['description']}")

        # Decisions
        decisions = checkpoint.get('decisions', [])
        if decisions:
            print(f"\n[DECISIONS MADE] ({len(decisions)})")
            for dec in decisions[-3:]:
                print(f"\n  Q: {dec['question']}")
                print(f"  A: {dec['decision']}")
                print(f"     {dec['rationale']}")

        # File Changes
        file_changes = checkpoint.get('file_changes', [])
        if file_changes:
            print(f"\n[FILE CHANGES] ({len(file_changes)})")
            for change in file_changes[-5:]:
                action_symbol = {"created": "+", "modified": "*", "deleted": "-"}.get(change['action'], "~")
                print(f"  {action_symbol} {change['file_path']}")

        # Git Commit Information
        git_commit = checkpoint.get('git_commit_hash')
        if git_commit:
            print(f"\n[GIT COMMIT]")
            print(f"  Hash: {git_commit[:8]}")
            if checkpoint.get('git_branch'):
                print(f"  Branch: {checkpoint['git_branch']}")
            if checkpoint.get('git_remote_url'):
                remote_url = checkpoint['git_remote_url']
                # Shorten GitHub URLs
                if 'github.com' in remote_url:
                    import re
                    match = re.search(r'github\.com[:/](.+?)(?:\.git)?$', remote_url)
                    if match:
                        remote_url = f"github.com/{match.group(1)}"
                print(f"  Remote: {remote_url}")

        # Problems
        problems = checkpoint.get('problems_encountered', [])
        if problems:
            print(f"\n[PROBLEMS ENCOUNTERED]")
            for problem in problems:
                print(f"  ! {problem}")

        # Resume Points
        resume_points = checkpoint.get('resume_points', [])
        if resume_points:
            print("\n" + "-"*60)
            print("[RESUME POINTS]")
            print("-"*60)
            for i, point in enumerate(resume_points, 1):
                print(f"{i}. {point}")

        # Next Steps
        next_steps = checkpoint.get('next_steps', [])
        if next_steps:
            print("\n" + "-"*60)
            print("[NEXT STEPS]")
            print("-"*60)
            for step in next_steps:
                print(f"[ ] {step}")

        print("\n" + "="*60)

    def display_checkpoint(self, checkpoint: dict):
        """Display checkpoint information"""
        # Validate checkpoint project matches current directory
        validation_warning = self.validate_checkpoint_project(checkpoint)
        if validation_warning:
            print("\n" + "="*70)
            print(validation_warning)
            print("="*70)
            print()

        if self.use_rich and self.console:
            self.display_checkpoint_rich(checkpoint)
        else:
            self.display_checkpoint_simple(checkpoint)

    def resume(self, session_id: Optional[str] = None):
        """Main resume flow with task context integration"""
        # Load checkpoint
        if session_id:
            checkpoint = self.load_checkpoint_by_id(session_id)
        else:
            checkpoint = self.load_latest_checkpoint()

        if not checkpoint:
            print("No checkpoints found.")
            print("\nRun checkpoint.py to create a session checkpoint.")
            return

        # Display checkpoint information
        self.display_checkpoint(checkpoint)

        # Load and display task context
        task_context = self.load_task_context()
        if task_context:
            self.display_task_context(task_context)

    def display_checkpoint_list(self, checkpoints: List[dict]):
        """Display list of available checkpoints"""
        if not checkpoints:
            print("No checkpoints found.")
            return

        if self.use_rich and self.console:
            table = Table(title="Available Checkpoints", box=box.ROUNDED)
            table.add_column("Session ID", style="cyan")
            table.add_column("Timestamp", style="green")
            table.add_column("Current Task", style="yellow")
            table.add_column("Completed", justify="right", style="green")
            table.add_column("Pending", justify="right", style="yellow")

            for cp in checkpoints:
                table.add_row(
                    cp['session_id'],
                    cp['timestamp'][:19],
                    cp['current_task'][:40] if cp['current_task'] else "-",
                    str(cp['completed_count']),
                    str(cp['pending_count'])
                )

            self.console.print(table)
        else:
            print("\nAVAILABLE CHECKPOINTS:")
            print("-" * 80)
            for cp in checkpoints:
                print(f"Session: {cp['session_id']}")
                print(f"  Time: {cp['timestamp'][:19]}")
                print(f"  Task: {cp['current_task'][:60] if cp['current_task'] else '-'}")
                print(f"  Stats: {cp['completed_count']} completed, {cp['pending_count']} pending")
                print()

    def generate_resume_summary(self, checkpoint: dict) -> str:
        """Generate a concise summary for Claude to use when resuming"""
        lines = []
        lines.append(f"# Resuming Session: {checkpoint['session_id']}")
        lines.append(f"\n**Session started:** {checkpoint['started_at'][:19]}")

        context = checkpoint.get('context', {})
        if context.get('description'):
            lines.append(f"\n**Session goal:** {context['description']}")

        current_task = checkpoint.get('current_task')
        if current_task:
            lines.append(f"\n**Last working on:** {current_task}")

        completed = checkpoint.get('completed_tasks', [])
        if completed:
            lines.append(f"\n**Progress:** {len(completed)} tasks completed")

        resume_points = checkpoint.get('resume_points', [])
        if resume_points:
            lines.append("\n**Resume from:**")
            for point in resume_points:
                lines.append(f"- {point}")

        next_steps = checkpoint.get('next_steps', [])
        if next_steps:
            lines.append("\n**Next steps:**")
            for step in next_steps:
                lines.append(f"- {step}")

        return "\n".join(lines)


    def display_projects_index(self):
        """Display all projects tracked in the session index"""
        index = SessionIndex()
        projects = index.list_all_projects()

        if not projects:
            print("\nNo projects tracked yet.")
            print("Run save-session.py to create your first checkpoint.")
            return

        print("\n" + "="*70)
        print(f"TRACKED PROJECTS ({len(projects)})")
        print("="*70)

        for proj in projects:
            print(f"\nProject: {proj['project_name']}")
            print(f"  Path: {proj['project_path']}")
            if proj['git_remote_url']:
                remote_url = proj['git_remote_url']
                # Shorten GitHub URLs
                if 'github.com' in remote_url:
                    import re
                    match = re.search(r'github\.com[:/](.+?)(?:\.git)?$', remote_url)
                    if match:
                        remote_url = f"github.com/{match.group(1)}"
                print(f"  Remote: {remote_url}")
            print(f"  Checkpoints: {proj['checkpoint_count']}")
            if proj['last_checkpoint']:
                # Calculate time ago
                try:
                    last_time = datetime.fromisoformat(proj['last_checkpoint'])
                    now = datetime.now()
                    delta = now - last_time
                    if delta.total_seconds() < 3600:
                        time_ago = f"{int(delta.total_seconds() / 60)} minutes ago"
                    elif delta.total_seconds() < 86400:
                        time_ago = f"{int(delta.total_seconds() / 3600)} hours ago"
                    else:
                        time_ago = f"{int(delta.total_seconds() / 86400)} days ago"
                    print(f"  Last checkpoint: {time_ago}")
                except:
                    print(f"  Last checkpoint: {proj['last_checkpoint']}")


def main():
    """Command-line interface"""
    import sys

    resumer = SessionResumer()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "list":
            checkpoints = resumer.list_checkpoints()
            resumer.display_checkpoint_list(checkpoints)
            return
        elif command == "summary":
            checkpoint = resumer.load_latest_checkpoint()
            if checkpoint:
                print(resumer.generate_resume_summary(checkpoint))
            else:
                print("No checkpoint found")
            return
        elif command == "projects":
            resumer.display_projects_index()
            return
        else:
            # Try to load by session ID
            resumer.resume(session_id=command)
            return

    # Default: use new resume flow with task context
    resumer.resume()


if __name__ == "__main__":
    main()
