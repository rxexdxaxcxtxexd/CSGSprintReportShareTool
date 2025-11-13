#!/usr/bin/env python3
"""
Context Monitor - Track Claude's context window usage

This script:
1. Parses Claude's history.jsonl to track conversation
2. Estimates token usage (rough: chars / 4)
3. Warns at threshold levels (75%, 87%, 95%)
4. Provides actionable recommendations

Usage:
    python context-monitor.py              # Check current session
    python context-monitor.py --all        # Check all recent history
    python context-monitor.py --threshold 80  # Custom warning threshold
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import argparse


class ContextMonitor:
    """Monitor Claude's context window usage"""

    # Claude Sonnet 4.5 context window
    MAX_TOKENS = 200_000

    # Warning thresholds
    THRESHOLDS = {
        'safe': 0.75,      # 75% - Start thinking about checkpointing
        'warning': 0.87,   # 87% - Should checkpoint soon
        'critical': 0.95   # 95% - Checkpoint immediately!
    }

    # Rough estimation: 1 token ≈ 4 characters
    CHARS_PER_TOKEN = 4

    def __init__(self):
        """Initialize the context monitor"""
        self.home = Path.home()
        self.history_path = self.home / '.claude' / 'history.jsonl'

        if not self.history_path.exists():
            raise FileNotFoundError(
                f"Claude history not found at {self.history_path}\n"
                "Make sure you're running Claude Code."
            )

    def parse_history(self, session_id: Optional[str] = None,
                     limit_entries: Optional[int] = None) -> List[Dict]:
        """Parse history.jsonl and extract entries

        Args:
            session_id: Filter to specific session (None = current/latest)
            limit_entries: Maximum entries to read (None = all)

        Returns:
            List of history entries (dicts with: display, timestamp, sessionId, etc.)
        """
        entries = []

        with open(self.history_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    entry = json.loads(line)

                    # Filter by session if specified
                    if session_id and entry.get('sessionId') != session_id:
                        continue

                    entries.append(entry)

                    # Stop if we've hit the limit
                    if limit_entries and len(entries) >= limit_entries:
                        break

                except json.JSONDecodeError:
                    # Skip malformed lines
                    continue

        return entries

    def get_current_session_id(self) -> Optional[str]:
        """Get the most recent session ID from history"""
        # Read last few entries to find latest sessionId
        with open(self.history_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Search backwards through recent entries
        for line in reversed(lines[-50:]):  # Check last 50 entries
            if not line.strip():
                continue

            try:
                entry = json.loads(line)
                if 'sessionId' in entry:
                    return entry['sessionId']
            except json.JSONDecodeError:
                continue

        return None

    def estimate_tokens(self, entries: List[Dict]) -> int:
        """Estimate token count from character count

        LIMITATION: history.jsonl only contains USER messages, not Claude's
        responses. This means actual token usage is typically 5-10x higher.

        Estimation approach:
        - Count user input chars / 4 = user tokens
        - Multiply by 8x to estimate Claude's responses + system context
        - This is a rough approximation for warning purposes

        Returns:
            Estimated token count (very approximate)
        """
        total_chars = 0

        for entry in entries:
            # Count message content
            display = entry.get('display', '')
            total_chars += len(display)

            # Count pasted content
            pasted = entry.get('pastedContents', {})
            for content in pasted.values():
                if isinstance(content, str):
                    total_chars += len(content)
                elif isinstance(content, dict):
                    # Handle structured pasted content
                    content_str = json.dumps(content)
                    total_chars += len(content_str)

        # Convert to tokens
        user_tokens = total_chars // self.CHARS_PER_TOKEN

        # Multiply by 8 to estimate total conversation
        # (Claude's responses are typically 5-10x longer than user input)
        estimated_tokens = int(user_tokens * 8)

        return estimated_tokens

    def get_status_level(self, usage_percent: float) -> str:
        """Get status level based on usage percentage

        Returns: 'safe', 'warning', or 'critical'
        """
        if usage_percent >= self.THRESHOLDS['critical']:
            return 'critical'
        elif usage_percent >= self.THRESHOLDS['warning']:
            return 'warning'
        elif usage_percent >= self.THRESHOLDS['safe']:
            return 'safe'
        else:
            return 'ok'

    def get_recommendation(self, status: str, usage_percent: float) -> str:
        """Get recommendation based on status"""
        if status == 'critical':
            return (
                "[!] CRITICAL: Context window is nearly full!\n"
                "   ACTION REQUIRED: Run checkpoint immediately:\n"
                "   -> python scripts/checkpoint.py --quick\n"
                "   -> Start a fresh Claude Code session\n"
                "   -> Resume with: python scripts/resume-session.py"
            )
        elif status == 'warning':
            return (
                "[WARNING] Context window is filling up.\n"
                "   RECOMMENDED: Create checkpoint soon:\n"
                "   -> python scripts/checkpoint.py --quick\n"
                "   Consider starting fresh session after current task."
            )
        elif status == 'safe':
            return (
                "[INFO] Context usage is getting high.\n"
                "   SUGGESTED: Plan to checkpoint at next milestone.\n"
                "   -> python scripts/checkpoint.py --quick"
            )
        else:
            return (
                "[OK] Plenty of context window remaining.\n"
                "   Continue working normally."
            )

    def format_timestamp(self, ts_ms: int) -> str:
        """Format Unix timestamp (milliseconds) to readable string"""
        dt = datetime.fromtimestamp(ts_ms / 1000)
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    def display_status(self, entries: List[Dict], session_id: Optional[str] = None):
        """Display context window status"""
        if not entries:
            print("No history entries found.")
            return

        # Estimate token usage
        estimated_tokens = self.estimate_tokens(entries)
        usage_percent = (estimated_tokens / self.MAX_TOKENS) * 100
        remaining_tokens = self.MAX_TOKENS - estimated_tokens

        # Get status
        status = self.get_status_level(usage_percent / 100)
        recommendation = self.get_recommendation(status, usage_percent)

        # Get time range
        first_entry = entries[0]
        last_entry = entries[-1]

        # Display
        print("=" * 70)
        print(" " * 20 + "CONTEXT WINDOW MONITOR")
        print("=" * 70)
        print()

        if session_id:
            print(f"Session ID: {session_id}")

        print(f"History Entries: {len(entries)}")
        print(f"Time Range: {self.format_timestamp(first_entry['timestamp'])} ->")
        print(f"            {self.format_timestamp(last_entry['timestamp'])}")
        print()

        print("Context Usage (APPROXIMATION):")
        print(f"  Estimated Tokens: ~{estimated_tokens:,} / {self.MAX_TOKENS:,}")
        print(f"  Usage: ~{usage_percent:.1f}%")
        print(f"  Remaining: ~{remaining_tokens:,} tokens (~{100 - usage_percent:.1f}%)")
        print()
        print("  Note: Estimates based on user input only. Actual usage includes")
        print("        Claude's responses, tool calls, and system context.")
        print()

        # Visual bar
        bar_length = 50
        filled = int((usage_percent / 100) * bar_length)
        bar = '=' * filled + '-' * (bar_length - filled)
        print(f"  [{bar}]")
        print()

        # Status and recommendation
        print(recommendation)
        print()

        print("=" * 70)

    def check_current_session(self):
        """Check context usage for current session"""
        session_id = self.get_current_session_id()

        if not session_id:
            print("Warning: Could not determine current session ID")
            print("Showing all recent history instead...")
            entries = self.parse_history(limit_entries=200)
        else:
            entries = self.parse_history(session_id=session_id)

        self.display_status(entries, session_id)

    def check_all_recent(self, limit: int = 200):
        """Check context usage for all recent history"""
        entries = self.parse_history(limit_entries=limit)
        self.display_status(entries)


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description="Monitor Claude Code context window usage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python context-monitor.py
      Check current session context usage

  python context-monitor.py --all
      Check all recent history (not just current session)

  python context-monitor.py --limit 500
      Check last 500 history entries
        """
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Check all recent history, not just current session'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=200,
        help='Maximum history entries to check (default: 200)'
    )

    parser.add_argument(
        '--session',
        type=str,
        help='Check specific session ID'
    )

    args = parser.parse_args()

    try:
        monitor = ContextMonitor()

        if args.session:
            # Check specific session
            entries = monitor.parse_history(session_id=args.session)
            monitor.display_status(entries, args.session)
        elif args.all:
            # Check all recent
            monitor.check_all_recent(limit=args.limit)
        else:
            # Check current session (default)
            monitor.check_current_session()

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
