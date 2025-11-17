#!/usr/bin/env python3
"""
Session Logger - Track progress across Claude Code sessions

This script provides functionality to:
1. Create session logs (human-readable markdown)
2. Create checkpoint files (machine-readable JSON)
3. Track tasks, decisions, and file changes
4. Facilitate handoff between Claude Code sessions
"""

import json
import os
import subprocess
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict, field
import uuid


@dataclass
class Task:
    """Represents a task in the session"""
    description: str
    status: str  # pending, in_progress, completed, blocked
    created_at: str
    completed_at: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class Decision:
    """Represents a decision made during the session"""
    timestamp: str
    question: str
    decision: str
    rationale: str
    alternatives_considered: List[str] = field(default_factory=list)


@dataclass
class FileChange:
    """Represents a file modification"""
    file_path: str
    action: str  # created, modified, deleted
    timestamp: str
    description: Optional[str] = None


@dataclass
class SessionCheckpoint:
    """Complete checkpoint of the session state"""
    session_id: str
    timestamp: str
    started_at: str
    current_task: Optional[str]
    completed_tasks: List[Task]
    pending_tasks: List[Task]
    decisions: List[Decision]
    file_changes: List[FileChange]
    context: Dict[str, Any]
    resume_points: List[str]
    problems_encountered: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    # Git information (added for commit tracking)
    git_commit_hash: Optional[str] = None
    git_branch: Optional[str] = None
    git_remote_url: Optional[str] = None
    # Project identification (added for multi-project support)
    project: Optional[Dict[str, Any]] = None


class SessionLogger:
    """Manages session logging and checkpointing"""

    def __init__(self, base_dir: str = None):
        """Initialize the session logger"""
        if base_dir is None:
            base_dir = Path.home()

        self.base_dir = Path(base_dir)
        self.sessions_dir = self.base_dir / ".claude-sessions"
        self.checkpoints_dir = self.sessions_dir / "checkpoints"
        self.logs_dir = self.sessions_dir / "logs"

        # Ensure directories exist
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Session state
        self.session_id = str(uuid.uuid4())[:8]
        self.started_at = datetime.now().isoformat()
        self.current_task: Optional[str] = None
        self.completed_tasks: List[Task] = []
        self.pending_tasks: List[Task] = []
        self.decisions: List[Decision] = []
        self.file_changes: List[FileChange] = []
        self.context: Dict[str, Any] = {}
        self.resume_points: List[str] = []
        self.problems_encountered: List[str] = []
        self.next_steps: List[str] = []

    def _get_git_info(self) -> Optional[Dict]:
        """Get git repository information"""
        try:
            # Check if it's a git repo
            result = subprocess.run(
                ['git', 'rev-parse', '--is-inside-work-tree'],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return None

            # Get remote URL
            remote_result = subprocess.run(
                ['git', 'config', '--get', 'remote.origin.url'],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            remote_url = remote_result.stdout.strip() if remote_result.returncode == 0 else "No remote"

            # Get current branch
            branch_result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=self.base_dir,
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
                'branch': branch
            }
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return None

    def start_session(self, description: str, context: Dict[str, Any] = None):
        """Start a new session with initial context"""
        self.context = context or {}
        self.context['description'] = description

        # Display project context
        print("\n" + "="*70)
        print("SESSION STARTED")
        print("="*70)
        print(f"  Session ID:  {self.session_id}")
        print(f"  Description: {description}")

        # Display git information if available
        git_info = self._get_git_info()
        if git_info:
            print(f"  Git Repo:    {git_info['display_url']}")
            print(f"  Branch:      {git_info['branch']}")
            print(f"  Auto-commit: ENABLED")
        else:
            print("  Git: Not a git repository")
        print("="*70)

    def add_task(self, description: str, status: str = "pending") -> Task:
        """Add a new task to the session"""
        task = Task(
            description=description,
            status=status,
            created_at=datetime.now().isoformat()
        )

        if status == "in_progress":
            self.current_task = description

        if status == "pending":
            self.pending_tasks.append(task)
        elif status == "completed":
            self.completed_tasks.append(task)

        return task

    def complete_task(self, description: str, notes: Optional[str] = None):
        """Mark a task as completed"""
        # Find in pending tasks
        for task in self.pending_tasks:
            if task.description == description:
                task.status = "completed"
                task.completed_at = datetime.now().isoformat()
                task.notes = notes
                self.pending_tasks.remove(task)
                self.completed_tasks.append(task)
                print(f"Task completed: {description}")
                return

        # If not found, create a new completed task
        task = Task(
            description=description,
            status="completed",
            created_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            notes=notes
        )
        self.completed_tasks.append(task)

    def update_current_task(self, description: str):
        """Update the current task being worked on"""
        self.current_task = description
        print(f"Current task: {description}")

    def log_decision(self, question: str, decision: str, rationale: str,
                     alternatives: List[str] = None):
        """Log a decision made during the session"""
        dec = Decision(
            timestamp=datetime.now().isoformat(),
            question=question,
            decision=decision,
            rationale=rationale,
            alternatives_considered=alternatives or []
        )
        self.decisions.append(dec)
        print(f"Decision logged: {question} -> {decision}")

    def log_file_change(self, file_path: str, action: str, description: str = None):
        """Log a file modification"""
        change = FileChange(
            file_path=file_path,
            action=action,
            timestamp=datetime.now().isoformat(),
            description=description
        )
        self.file_changes.append(change)
        print(f"File change logged: {action} {file_path}")

    def add_problem(self, problem: str):
        """Log a problem encountered during the session"""
        self.problems_encountered.append(problem)
        print(f"Problem logged: {problem}")

    def add_resume_point(self, point: str):
        """Add a resume point for the next session"""
        self.resume_points.append(point)
        print(f"Resume point added: {point}")

    def add_next_step(self, step: str):
        """Add a next step for continuation"""
        self.next_steps.append(step)
        print(f"Next step added: {step}")

    def create_checkpoint(self) -> str:
        """Create a checkpoint file (JSON format)"""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        checkpoint_file = self.checkpoints_dir / f"checkpoint-{timestamp}.json"

        # Extract project metadata from context (if provided)
        project_metadata = self.context.get('project', None)

        checkpoint = SessionCheckpoint(
            session_id=self.session_id,
            timestamp=datetime.now().isoformat(),
            started_at=self.started_at,
            current_task=self.current_task,
            completed_tasks=self.completed_tasks,
            pending_tasks=self.pending_tasks,
            decisions=self.decisions,
            file_changes=self.file_changes,
            context=self.context,
            resume_points=self.resume_points,
            problems_encountered=self.problems_encountered,
            next_steps=self.next_steps,
            project=project_metadata  # Add project identification
        )

        # Convert dataclasses to dict
        checkpoint_dict = asdict(checkpoint)

        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_dict, f, indent=2, ensure_ascii=False)

        print(f"Checkpoint saved: {checkpoint_file}")
        return str(checkpoint_file)

    def create_session_log(self) -> str:
        """Create a human-readable session log (Markdown format)"""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_file = self.logs_dir / f"session-{timestamp}.md"

        # Build markdown content
        lines = []
        lines.append(f"# Session Log: {self.session_id}")
        lines.append(f"\n**Started:** {self.started_at}")
        lines.append(f"**Ended:** {datetime.now().isoformat()}")

        if self.context.get('description'):
            lines.append(f"\n## Session Description\n")
            lines.append(self.context['description'])

        # Completed tasks
        if self.completed_tasks:
            lines.append(f"\n## Completed Tasks\n")
            for task in self.completed_tasks:
                lines.append(f"- ✅ {task.description}")
                if task.notes:
                    lines.append(f"  - Notes: {task.notes}")
                lines.append(f"  - Completed: {task.completed_at}")

        # Pending tasks
        if self.pending_tasks:
            lines.append(f"\n## Pending Tasks\n")
            for task in self.pending_tasks:
                status_emoji = "⏳" if task.status == "in_progress" else "⏸️"
                lines.append(f"- {status_emoji} {task.description}")

        # Current task
        if self.current_task:
            lines.append(f"\n## Current Task\n")
            lines.append(f"🔄 {self.current_task}")

        # Decisions
        if self.decisions:
            lines.append(f"\n## Decisions Made\n")
            for dec in self.decisions:
                lines.append(f"\n### {dec.question}")
                lines.append(f"**Decision:** {dec.decision}")
                lines.append(f"**Rationale:** {dec.rationale}")
                if dec.alternatives_considered:
                    lines.append(f"**Alternatives Considered:**")
                    for alt in dec.alternatives_considered:
                        lines.append(f"- {alt}")
                lines.append(f"**Time:** {dec.timestamp}")

        # File changes
        if self.file_changes:
            lines.append(f"\n## File Changes\n")
            for change in self.file_changes:
                action_emoji = {"created": "➕", "modified": "✏️", "deleted": "❌"}.get(change.action, "📝")
                lines.append(f"- {action_emoji} **{change.action.upper()}**: `{change.file_path}`")
                if change.description:
                    lines.append(f"  - {change.description}")

        # Problems encountered
        if self.problems_encountered:
            lines.append(f"\n## Problems Encountered\n")
            for problem in self.problems_encountered:
                lines.append(f"- ⚠️ {problem}")

        # Resume points
        if self.resume_points:
            lines.append(f"\n## Resume Points for Next Session\n")
            for i, point in enumerate(self.resume_points, 1):
                lines.append(f"{i}. {point}")

        # Next steps
        if self.next_steps:
            lines.append(f"\n## Next Steps\n")
            for step in self.next_steps:
                lines.append(f"- [ ] {step}")

        # Context
        if self.context:
            lines.append(f"\n## Session Context\n")
            lines.append("```json")
            lines.append(json.dumps(self.context, indent=2))
            lines.append("```")

        content = "\n".join(lines)

        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"Session log saved: {log_file}")
        return str(log_file)

    def end_session(self):
        """End the session and create both checkpoint and log"""
        checkpoint_file = self.create_checkpoint()
        log_file = self.create_session_log()

        print("\n" + "="*60)
        print("SESSION ENDED")
        print("="*60)
        print(f"Session ID: {self.session_id}")
        print(f"Checkpoint: {checkpoint_file}")
        print(f"Log: {log_file}")
        print("="*60)

        return checkpoint_file, log_file

    @staticmethod
    def load_latest_checkpoint(base_dir: str = None) -> Optional[SessionCheckpoint]:
        """Load the most recent checkpoint"""
        if base_dir is None:
            base_dir = Path.home()

        checkpoints_dir = Path(base_dir) / ".claude-sessions" / "checkpoints"

        if not checkpoints_dir.exists():
            return None

        checkpoint_files = sorted(checkpoints_dir.glob("checkpoint-*.json"), reverse=True)

        if not checkpoint_files:
            return None

        latest = checkpoint_files[0]

        with open(latest, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Convert back to dataclasses
        checkpoint = SessionCheckpoint(
            session_id=data['session_id'],
            timestamp=data['timestamp'],
            started_at=data['started_at'],
            current_task=data.get('current_task'),
            completed_tasks=[Task(**t) for t in data['completed_tasks']],
            pending_tasks=[Task(**t) for t in data['pending_tasks']],
            decisions=[Decision(**d) for d in data['decisions']],
            file_changes=[FileChange(**fc) for fc in data['file_changes']],
            context=data['context'],
            resume_points=data.get('resume_points', []),
            problems_encountered=data.get('problems_encountered', []),
            next_steps=data.get('next_steps', [])
        )

        return checkpoint


def main():
    """Example usage"""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "load":
        # Load latest checkpoint
        checkpoint = SessionLogger.load_latest_checkpoint()
        if checkpoint:
            print("Latest Checkpoint:")
            print(f"Session ID: {checkpoint.session_id}")
            print(f"Timestamp: {checkpoint.timestamp}")
            print(f"Current Task: {checkpoint.current_task}")
            print(f"\nResume Points:")
            for point in checkpoint.resume_points:
                print(f"  - {point}")
            print(f"\nNext Steps:")
            for step in checkpoint.next_steps:
                print(f"  - {step}")
        else:
            print("No checkpoints found")
        return

    # Create a new session
    logger = SessionLogger()
    logger.start_session(
        "Example session for testing",
        context={"project": "api-documentation-agent", "phase": "development"}
    )

    # Add some tasks
    logger.add_task("Task 1: Setup environment", "completed")
    logger.complete_task("Task 1: Setup environment", "Environment configured successfully")

    logger.add_task("Task 2: Implement feature", "in_progress")
    logger.update_current_task("Task 2: Implement feature")

    logger.add_task("Task 3: Write tests", "pending")

    # Log a decision
    logger.log_decision(
        question="Which logging library to use?",
        decision="Use built-in logging module",
        rationale="Built-in module is sufficient for our needs",
        alternatives=["loguru", "structlog"]
    )

    # Log file changes
    logger.log_file_change("scripts/session-logger.py", "created", "Session logger implementation")

    # Add resume points and next steps
    logger.add_resume_point("Continue with Task 2 implementation")
    logger.add_next_step("Complete Task 2: Implement feature")
    logger.add_next_step("Start Task 3: Write tests")

    # End session
    logger.end_session()


if __name__ == "__main__":
    main()
