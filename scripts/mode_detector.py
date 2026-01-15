#!/usr/bin/env python3
"""
Mode Detector - Automatic workflow mode detection for adaptive session state behavior.

Analyzes tool usage patterns to detect whether Claude is in:
- File mode: Heavy coding/editing (Edit, Write, NotebookEdit)
- Task mode: Heavy investigation (Read, Grep, Glob, WebFetch)
- Mixed mode: Balanced usage of both

Each mode has optimized checkpoint strategies and state detail levels.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from collections import Counter
from datetime import datetime


@dataclass
class ModeConfig:
    """Configuration for a specific workflow mode."""
    checkpoint_trigger: str
    state_detail: str
    auto_save_interval: Optional[int]
    description: str


class ModeDetector:
    """Detects workflow mode based on tool usage patterns."""

    # Tool classifications
    FILE_TOOLS = {'Edit', 'Write', 'NotebookEdit'}
    TASK_TOOLS = {'Read', 'Grep', 'Glob', 'WebFetch', 'Task', 'WebSearch'}
    NEUTRAL_TOOLS = {'Bash', 'TodoWrite', 'AskUserQuestion'}

    # Mode configurations
    MODE_CONFIGS = {
        "file": ModeConfig(
            checkpoint_trigger="git_commit",
            state_detail="minimal",
            auto_save_interval=None,
            description="File-heavy workflow: Checkpoints triggered by git commits, minimal state tracking"
        ),
        "task": ModeConfig(
            checkpoint_trigger="periodic_15min",
            state_detail="rich",
            auto_save_interval=10,
            description="Task-heavy workflow: Periodic checkpoints every 15min, rich state tracking, auto-save every 10 tools"
        ),
        "mixed": ModeConfig(
            checkpoint_trigger="commit_or_20min",
            state_detail="balanced",
            auto_save_interval=15,
            description="Mixed workflow: Checkpoints on commit or every 20min, balanced state tracking, auto-save every 15 tools"
        )
    }

    # Detection thresholds
    FILE_MODE_THRESHOLD = 0.6
    TASK_MODE_THRESHOLD = 0.6
    WINDOW_SIZE = 20  # Number of recent tools to analyze

    def __init__(self, session_dir: Optional[Path] = None):
        """Initialize mode detector.

        Args:
            session_dir: Directory containing session logs (default: .claude-sessions/)
        """
        if session_dir is None:
            # Default to .claude-sessions/ in user's home or current directory
            home_sessions = Path.home() / '.claude-sessions'
            cwd_sessions = Path.cwd() / '.claude-sessions'

            if home_sessions.exists():
                session_dir = home_sessions
            elif cwd_sessions.exists():
                session_dir = cwd_sessions
            else:
                session_dir = Path('.claude-sessions')

        self.session_dir = Path(session_dir)

    def detect_mode(self, tool_history: List[str]) -> str:
        """Detect workflow mode from tool usage history.

        Args:
            tool_history: List of tool names used (most recent last)

        Returns:
            Mode string: "file", "task", or "mixed"
        """
        if not tool_history:
            return "mixed"

        # Analyze last N tools
        recent_tools = tool_history[-self.WINDOW_SIZE:]

        # Calculate ratios
        file_ratio = self._calculate_ratio(recent_tools, self.FILE_TOOLS)
        task_ratio = self._calculate_ratio(recent_tools, self.TASK_TOOLS)

        # Determine mode
        if file_ratio >= self.FILE_MODE_THRESHOLD:
            return "file"
        elif task_ratio >= self.TASK_MODE_THRESHOLD:
            return "task"
        else:
            return "mixed"

    def _calculate_ratio(self, tools: List[str], target_tools: set) -> float:
        """Calculate ratio of target tools in tool list."""
        if not tools:
            return 0.0

        target_count = sum(1 for tool in tools if tool in target_tools)
        return target_count / len(tools)

    def get_config(self, mode: str) -> ModeConfig:
        """Get configuration for specified mode.

        Args:
            mode: Mode string ("file", "task", or "mixed")

        Returns:
            ModeConfig object with settings for this mode
        """
        return self.MODE_CONFIGS.get(mode, self.MODE_CONFIGS["mixed"])

    def should_auto_save(self, tool_count: int, mode: str) -> bool:
        """Check if auto-save should be triggered.

        Args:
            tool_count: Number of tools used since last save
            mode: Current workflow mode

        Returns:
            True if auto-save should be triggered
        """
        config = self.get_config(mode)

        if config.auto_save_interval is None:
            return False

        return tool_count >= config.auto_save_interval

    def analyze_session(self, session_file: Optional[Path] = None) -> Dict:
        """Analyze a session and generate mode report.

        Args:
            session_file: Path to session log (default: latest session)

        Returns:
            Dictionary with analysis results
        """
        if session_file is None:
            session_file = self._get_latest_session()

        if session_file is None or not session_file.exists():
            return {
                "error": "No session file found",
                "mode": "mixed",
                "tool_history": []
            }

        # Load session data
        tool_history = self._extract_tool_history(session_file)

        # Detect mode
        mode = self.detect_mode(tool_history)
        config = self.get_config(mode)

        # Calculate statistics
        tool_counts = Counter(tool_history)
        recent_tools = tool_history[-self.WINDOW_SIZE:]

        file_ratio = self._calculate_ratio(recent_tools, self.FILE_TOOLS)
        task_ratio = self._calculate_ratio(recent_tools, self.TASK_TOOLS)
        neutral_ratio = self._calculate_ratio(recent_tools, self.NEUTRAL_TOOLS)

        return {
            "session_file": str(session_file),
            "mode": mode,
            "config": {
                "checkpoint_trigger": config.checkpoint_trigger,
                "state_detail": config.state_detail,
                "auto_save_interval": config.auto_save_interval
            },
            "statistics": {
                "total_tools": len(tool_history),
                "analyzed_window": len(recent_tools),
                "file_ratio": round(file_ratio, 2),
                "task_ratio": round(task_ratio, 2),
                "neutral_ratio": round(neutral_ratio, 2)
            },
            "top_tools": tool_counts.most_common(5),
            "tool_history": recent_tools,
            "description": config.description
        }

    def _get_latest_session(self) -> Optional[Path]:
        """Get the most recent session log file."""
        if not self.session_dir.exists():
            return None

        # Look for session-*.json files
        session_files = list(self.session_dir.glob('session-*.json'))

        if not session_files:
            return None

        # Sort by modification time, most recent first
        session_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return session_files[0]

    def _extract_tool_history(self, session_file: Path) -> List[str]:
        """Extract tool usage history from session file."""
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Extract tool names from various possible formats
            tool_history = []

            # Check for tools array
            if 'tools' in data:
                tool_history = data['tools']

            # Check for events/actions array
            elif 'events' in data:
                for event in data['events']:
                    if 'tool' in event:
                        tool_history.append(event['tool'])

            # Check for flat tool list in metadata
            elif 'tool_usage' in data:
                tool_history = data['tool_usage']

            return tool_history

        except Exception as e:
            print(f"Warning: Could not parse session file: {e}", file=sys.stderr)
            return []

    def generate_recommendation(self, analysis: Dict) -> str:
        """Generate human-readable recommendation from analysis.

        Args:
            analysis: Analysis dictionary from analyze_session()

        Returns:
            Formatted recommendation string
        """
        if "error" in analysis:
            return f"Error: {analysis['error']}\n\nDefaulting to MIXED mode."

        mode = analysis['mode']
        config = analysis['config']
        stats = analysis['statistics']

        lines = [
            f"Session Workflow Mode: {mode.upper()}",
            f"",
            f"Analysis:",
            f"  • File tools:    {stats['file_ratio']:.0%} of recent usage",
            f"  • Task tools:    {stats['task_ratio']:.0%} of recent usage",
            f"  • Neutral tools: {stats['neutral_ratio']:.0%} of recent usage",
            f"  • Analyzed:      {stats['analyzed_window']} recent tools",
            f"",
            f"Recommended Configuration:",
            f"  • Checkpoint trigger:  {config['checkpoint_trigger']}",
            f"  • State detail level:  {config['state_detail']}",
            f"  • Auto-save interval:  {config['auto_save_interval'] or 'disabled'}",
            f"",
            f"Description:",
            f"  {analysis['description']}",
            f""
        ]

        if analysis.get('top_tools'):
            lines.append("Most Used Tools:")
            for tool, count in analysis['top_tools']:
                lines.append(f"  • {tool}: {count} times")

        return "\n".join(lines)


def main():
    """CLI interface for mode detection."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Detect workflow mode and recommend session settings"
    )
    parser.add_argument(
        'command',
        choices=['analyze', 'recommend'],
        help='Command to execute'
    )
    parser.add_argument(
        '--session-dir',
        type=Path,
        help='Directory containing session logs (default: .claude-sessions/)'
    )
    parser.add_argument(
        '--session-file',
        type=Path,
        help='Specific session file to analyze (default: latest)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output in JSON format'
    )

    args = parser.parse_args()

    # Initialize detector
    detector = ModeDetector(session_dir=args.session_dir)

    # Analyze session
    analysis = detector.analyze_session(session_file=args.session_file)

    if args.command == 'analyze':
        if args.json:
            print(json.dumps(analysis, indent=2))
        else:
            print(detector.generate_recommendation(analysis))

    elif args.command == 'recommend':
        recommendation = detector.generate_recommendation(analysis)
        print(recommendation)

        if not args.json:
            print("\nTo apply these settings:")
            print("  1. Update checkpoint.py to use mode-specific triggers")
            print("  2. Configure auto-save intervals in session logger")
            print("  3. Adjust state detail level in CLAUDE.md updates")


if __name__ == '__main__':
    main()
