#!/usr/bin/env python3
"""
Update Session State - Sync CLAUDE.md with latest checkpoint

This script:
1. Reads the latest checkpoint JSON
2. Updates the "Current Session State" section in CLAUDE.md
3. Appends decisions to the Decision Log
4. Maintains session continuity information
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple


class ClaudeMdUpdater:
    """Updates CLAUDE.md with session state information"""

    def __init__(self, base_dir: str = None):
        """Initialize the updater"""
        if base_dir is None:
            base_dir = Path.home()

        self.base_dir = Path(base_dir)
        self.claude_md_path = self.base_dir / "CLAUDE.md"
        self.checkpoints_dir = self.base_dir / ".claude-sessions" / "checkpoints"

        if not self.claude_md_path.exists():
            raise FileNotFoundError(f"CLAUDE.md not found at {self.claude_md_path}")

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

    def read_claude_md(self) -> str:
        """Read the current CLAUDE.md content"""
        with open(self.claude_md_path, 'r', encoding='utf-8') as f:
            return f.read()

    def write_claude_md(self, content: str):
        """Write updated content to CLAUDE.md"""
        with open(self.claude_md_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def find_section(self, content: str, section_title: str) -> Tuple[Optional[int], Optional[int]]:
        """Find the start and end positions of a section"""
        # Look for the section header
        pattern = rf'^## {re.escape(section_title)}$'
        match = re.search(pattern, content, re.MULTILINE)

        if not match:
            return None, None

        start = match.start()

        # Find the next section (starts with ##)
        next_section_pattern = r'^## '
        remaining_content = content[match.end():]
        next_match = re.search(next_section_pattern, remaining_content, re.MULTILINE)

        if next_match:
            end = match.end() + next_match.start()
        else:
            end = len(content)

        return start, end

    def update_section(self, content: str, section_title: str, new_section_content: str) -> str:
        """Update or insert a section in the markdown content"""
        start, end = self.find_section(content, section_title)

        if start is not None and end is not None:
            # Replace existing section
            before = content[:start]
            after = content[end:]
            return before + new_section_content + "\n" + after
        else:
            # Insert new section before the last section or at the end
            # Find a good insertion point (before "Development Guidelines" or at the end)
            insertion_sections = ["Development Guidelines", "CI/CD Integration"]
            insertion_point = None

            for section in insertion_sections:
                start, _ = self.find_section(content, section)
                if start is not None:
                    insertion_point = start
                    break

            if insertion_point:
                before = content[:insertion_point]
                after = content[insertion_point:]
                return before + new_section_content + "\n\n" + after
            else:
                # Append at the end
                return content + "\n\n" + new_section_content

    def generate_session_state_section(self, checkpoint: dict) -> str:
        """Generate the Current Session State section from checkpoint"""
        lines = []
        lines.append("## Current Session State")
        lines.append("")
        lines.append(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Session ID:** {checkpoint.get('session_id', 'N/A')}")
        lines.append("")

        # Current task
        current_task = checkpoint.get('current_task')
        if current_task:
            lines.append(f"### Active Task")
            lines.append(f"🔄 {current_task}")
            lines.append("")

        # Recently completed tasks
        completed_tasks = checkpoint.get('completed_tasks', [])
        if completed_tasks:
            lines.append(f"### Recently Completed ({len(completed_tasks)})")
            for task in completed_tasks[-3:]:  # Show last 3
                lines.append(f"- ✅ {task['description']}")
            lines.append("")

        # Pending tasks
        pending_tasks = checkpoint.get('pending_tasks', [])
        if pending_tasks:
            lines.append(f"### Pending Tasks ({len(pending_tasks)})")
            for task in pending_tasks[:5]:  # Show first 5
                lines.append(f"- ⏸️ {task['description']}")
            lines.append("")

        # Resume points
        resume_points = checkpoint.get('resume_points', [])
        if resume_points:
            lines.append(f"### Resume Points")
            for i, point in enumerate(resume_points, 1):
                lines.append(f"{i}. {point}")
            lines.append("")

        # Next steps
        next_steps = checkpoint.get('next_steps', [])
        if next_steps:
            lines.append(f"### Next Steps")
            for step in next_steps:
                lines.append(f"- [ ] {step}")
            lines.append("")

        # Problems encountered
        problems = checkpoint.get('problems_encountered', [])
        if problems:
            lines.append(f"### Issues to Address")
            for problem in problems:
                lines.append(f"- ⚠️ {problem}")
            lines.append("")

        # Recent file changes
        file_changes = checkpoint.get('file_changes', [])
        if file_changes:
            lines.append(f"### Recent Changes")
            for change in file_changes[-5:]:  # Show last 5
                action_emoji = {"created": "➕", "modified": "✏️", "deleted": "❌"}.get(change['action'], "📝")
                lines.append(f"- {action_emoji} `{change['file_path']}`")
            lines.append("")

        return "\n".join(lines)

    def append_to_decision_log(self, content: str, checkpoint: dict) -> str:
        """Append new decisions to the Decision Log section"""
        decisions = checkpoint.get('decisions', [])

        if not decisions:
            return content

        # Check if Decision Log section exists
        start, end = self.find_section(content, "Decision Log")

        decision_lines = []
        for dec in decisions:
            decision_lines.append(f"\n### {dec['question']}")
            decision_lines.append(f"**Date:** {dec['timestamp'][:10]}")
            decision_lines.append(f"**Decision:** {dec['decision']}")
            decision_lines.append(f"**Rationale:** {dec['rationale']}")

            if dec.get('alternatives_considered'):
                decision_lines.append("**Alternatives Considered:**")
                for alt in dec['alternatives_considered']:
                    decision_lines.append(f"- {alt}")
            decision_lines.append("")

        decision_content = "\n".join(decision_lines)

        if start is not None and end is not None:
            # Append to existing Decision Log
            before = content[:end]
            after = content[end:]
            return before + decision_content + after
        else:
            # Create new Decision Log section
            new_section = "## Decision Log\n\n" + decision_content
            return self.update_section(content, "Decision Log", new_section)

        return content

    def update_from_checkpoint(self, checkpoint: dict):
        """Update CLAUDE.md from checkpoint data"""
        content = self.read_claude_md()

        # Update Current Session State section
        session_state = self.generate_session_state_section(checkpoint)
        content = self.update_section(content, "Current Session State", session_state)

        # Append decisions to Decision Log
        content = self.append_to_decision_log(content, checkpoint)

        # Write updated content
        self.write_claude_md(content)

        print(f"[OK] CLAUDE.md updated successfully")
        print(f"   - Current Session State: Updated")
        print(f"   - Decision Log: {len(checkpoint.get('decisions', []))} decisions logged")

    def clear_session_state(self):
        """Clear the Current Session State section (for clean slate)"""
        content = self.read_claude_md()

        cleared_section = """## Current Session State

**Last Updated:** {timestamp}

No active session. Start a new session to track progress.
""".format(timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        content = self.update_section(content, "Current Session State", cleared_section)
        self.write_claude_md(content)

        print("✅ Session state cleared")


def main():
    """Command-line interface"""
    import sys

    updater = ClaudeMdUpdater()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "clear":
            updater.clear_session_state()
            return
        elif command == "update":
            checkpoint = updater.load_latest_checkpoint()
            if checkpoint:
                updater.update_from_checkpoint(checkpoint)
            else:
                print("No checkpoint found to update from")
            return
        else:
            print(f"Unknown command: {command}")
            print("Usage: python update-session-state.py [update|clear]")
            return

    # Default: update from latest checkpoint
    checkpoint = updater.load_latest_checkpoint()

    if checkpoint:
        print(f"Loading checkpoint from {checkpoint.get('timestamp')}")
        updater.update_from_checkpoint(checkpoint)
    else:
        print("No checkpoint found. Run session-logger.py first to create a checkpoint.")


if __name__ == "__main__":
    main()
