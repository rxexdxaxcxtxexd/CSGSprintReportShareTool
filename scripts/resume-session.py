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
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich import box


class SessionResumer:
    """Load and display previous session information"""

    def __init__(self, base_dir: str = None):
        """Initialize the session resumer"""
        if base_dir is None:
            base_dir = Path.home()

        self.base_dir = Path(base_dir)
        self.checkpoints_dir = self.base_dir / ".claude-sessions" / "checkpoints"
        self.logs_dir = self.base_dir / ".claude-sessions" / "logs"

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

    def display_checkpoint_simple(self, checkpoint: dict):
        """Display checkpoint information using simple text formatting"""
        print("\n" + "="*60)
        print(f"SESSION CHECKPOINT: {checkpoint['session_id']}")
        print("="*60)
        print(f"Started: {checkpoint['started_at']}")
        print(f"Checkpoint: {checkpoint['timestamp']}")

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
        if self.use_rich and self.console:
            self.display_checkpoint_rich(checkpoint)
        else:
            self.display_checkpoint_simple(checkpoint)

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
        else:
            # Try to load by session ID
            checkpoint = resumer.load_checkpoint_by_id(command)
            if checkpoint:
                resumer.display_checkpoint(checkpoint)
            else:
                print(f"Checkpoint not found: {command}")
            return

    # Default: display latest checkpoint
    checkpoint = resumer.load_latest_checkpoint()

    if checkpoint:
        resumer.display_checkpoint(checkpoint)
    else:
        print("No checkpoints found.")
        print("\nRun session-logger.py to create a session checkpoint.")


if __name__ == "__main__":
    main()
