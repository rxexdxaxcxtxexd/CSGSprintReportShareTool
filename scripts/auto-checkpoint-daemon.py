#!/usr/bin/env python3
"""
Auto-Checkpoint Daemon - Background context monitoring and checkpoint reminders

This script:
1. Runs in background monitoring context window usage
2. Checks context usage every N minutes
3. Notifies user when checkpoint is recommended
4. Optionally auto-checkpoints at critical threshold

Usage:
    python auto-checkpoint-daemon.py                    # Start daemon (check every 5 min)
    python auto-checkpoint-daemon.py --interval 10      # Check every 10 minutes
    python auto-checkpoint-daemon.py --auto-checkpoint  # Auto-checkpoint when critical
    python auto-checkpoint-daemon.py --once             # Check once and exit

Note: This is a simple daemon. For production use, consider using a proper
      task scheduler (Windows Task Scheduler, systemd timer, etc.)
"""

import sys
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional


class CheckpointDaemon:
    """Background daemon for context monitoring and checkpoint reminders"""

    def __init__(self, interval_minutes: int = 5,
                 auto_checkpoint: bool = False,
                 quiet: bool = False):
        """Initialize daemon

        Args:
            interval_minutes: Minutes between checks (default: 5)
            auto_checkpoint: Auto-checkpoint at critical threshold (default: False)
            quiet: Suppress normal output, only show warnings (default: False)
        """
        self.interval_minutes = interval_minutes
        self.auto_checkpoint = auto_checkpoint
        self.quiet = quiet

        self.scripts_dir = Path(__file__).parent
        self.context_monitor_path = self.scripts_dir / 'context-monitor.py'
        self.checkpoint_path = self.scripts_dir / 'checkpoint.py'

        # Verify scripts exist
        if not self.context_monitor_path.exists():
            raise FileNotFoundError(
                f"context-monitor.py not found at {self.context_monitor_path}"
            )

        if not self.checkpoint_path.exists():
            raise FileNotFoundError(
                f"checkpoint.py not found at {self.checkpoint_path}"
            )

        # Track last notification to avoid spam
        self.last_notification_level = None
        self.last_checkpoint_time = None

    def run_context_monitor(self) -> Optional[dict]:
        """Run context monitor and parse results

        Returns:
            Dict with: usage_percent, estimated_tokens, status
            None if monitoring failed
        """
        try:
            result = subprocess.run(
                [sys.executable, str(self.context_monitor_path)],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                if not self.quiet:
                    print(f"[WARNING] Context monitor failed: {result.stderr}")
                return None

            # Parse output to extract status
            # Look for lines like "Usage: 75.5%"
            output = result.stdout
            usage_percent = None
            estimated_tokens = None
            status = 'ok'

            for line in output.split('\n'):
                if 'Usage:' in line and '%' in line:
                    # Extract percentage
                    parts = line.split('~')
                    if len(parts) > 1:
                        pct_str = parts[1].split('%')[0].strip()
                        try:
                            usage_percent = float(pct_str)
                        except ValueError:
                            pass

                if 'Estimated Tokens:' in line:
                    # Extract token count
                    parts = line.split('~')
                    if len(parts) > 1:
                        tokens_str = parts[1].split('/')[0].strip().replace(',', '')
                        try:
                            estimated_tokens = int(tokens_str)
                        except ValueError:
                            pass

                # Detect status from output
                if '[!] CRITICAL' in line:
                    status = 'critical'
                elif '[WARNING]' in line:
                    status = 'warning'
                elif '[INFO]' in line:
                    status = 'safe'

            return {
                'usage_percent': usage_percent,
                'estimated_tokens': estimated_tokens,
                'status': status,
                'raw_output': output
            }

        except subprocess.TimeoutExpired:
            if not self.quiet:
                print("[WARNING] Context monitor timed out")
            return None
        except Exception as e:
            if not self.quiet:
                print(f"[ERROR] Context monitoring failed: {e}")
            return None

    def run_checkpoint(self, description: str = None) -> bool:
        """Run checkpoint script

        Args:
            description: Optional checkpoint description

        Returns:
            True if successful, False otherwise
        """
        try:
            cmd = [sys.executable, str(self.checkpoint_path), '--quick']

            if description:
                cmd.extend(['--description', description])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0:
                self.last_checkpoint_time = datetime.now()
                return True
            else:
                print(f"[ERROR] Checkpoint failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            print("[ERROR] Checkpoint timed out (>5 minutes)")
            return False
        except Exception as e:
            print(f"[ERROR] Checkpoint failed: {e}")
            return False

    def handle_status(self, monitor_result: dict):
        """Handle context status and take appropriate action

        Args:
            monitor_result: Result from run_context_monitor()
        """
        status = monitor_result['status']
        usage_percent = monitor_result.get('usage_percent')

        # Only notify if status changed or got worse
        if status == self.last_notification_level:
            return  # Already notified at this level

        # Take action based on status
        if status == 'critical':
            print("\n" + "=" * 70)
            print("[!] CRITICAL: Context window is nearly full!")
            print("=" * 70)
            if usage_percent:
                print(f"Usage: ~{usage_percent:.1f}%")
            print()

            if self.auto_checkpoint:
                print("Auto-checkpointing enabled - creating checkpoint now...")
                success = self.run_checkpoint(
                    description="Auto-checkpoint: Context window critical"
                )
                if success:
                    print("[OK] Checkpoint created successfully!")
                    print("     Consider starting a fresh Claude Code session.")
                else:
                    print("[ERROR] Auto-checkpoint failed!")
                    print("        Please run manually: python scripts/checkpoint.py --quick")
            else:
                print("ACTION REQUIRED: Run checkpoint immediately:")
                print("  -> python scripts/checkpoint.py --quick")
                print("  -> Start a fresh Claude Code session")
                print("  -> Resume with: python scripts/resume-session.py")

            print("=" * 70)
            self.last_notification_level = 'critical'

        elif status == 'warning':
            print("\n" + "-" * 70)
            print("[WARNING] Context window is filling up")
            print("-" * 70)
            if usage_percent:
                print(f"Usage: ~{usage_percent:.1f}%")
            print()
            print("RECOMMENDED: Create checkpoint soon:")
            print("  -> python scripts/checkpoint.py --quick")
            print("  Consider starting fresh session after current task")
            print("-" * 70)
            self.last_notification_level = 'warning'

        elif status == 'safe':
            if not self.quiet:
                print(f"\n[INFO] Context usage is getting high (~{usage_percent:.1f}%)")
                print("       Plan to checkpoint at next milestone")
            self.last_notification_level = 'safe'

        else:  # ok
            if not self.quiet and self.last_notification_level:
                print(f"[OK] Context usage is normal (~{usage_percent:.1f}%)")
            self.last_notification_level = 'ok'

    def check_once(self) -> int:
        """Run a single check and exit

        Returns:
            Exit code (0 = ok, 1 = warning, 2 = critical)
        """
        if not self.quiet:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking context usage...", flush=True)

        result = self.run_context_monitor()

        if not result:
            return 1  # Error

        self.handle_status(result)

        if not self.quiet:
            print(f"[OK] Check complete", flush=True)

        # Return appropriate exit code
        status_codes = {
            'ok': 0,
            'safe': 0,
            'warning': 1,
            'critical': 2
        }

        return status_codes.get(result['status'], 0)

    def run_daemon(self):
        """Run daemon in loop, checking periodically"""
        print("=" * 70)
        print(" " * 15 + "AUTO-CHECKPOINT DAEMON STARTED")
        print("=" * 70)
        print(f"Checking context usage every {self.interval_minutes} minute(s)")
        if self.auto_checkpoint:
            print("Auto-checkpoint: ENABLED (will checkpoint at critical threshold)")
        else:
            print("Auto-checkpoint: DISABLED (notifications only)")
        print()
        print("Press Ctrl+C to stop")
        print("=" * 70)
        print()

        try:
            while True:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                if not self.quiet:
                    print(f"[{timestamp}] Checking context usage...")

                result = self.run_context_monitor()

                if result:
                    self.handle_status(result)
                else:
                    if not self.quiet:
                        print(f"[{timestamp}] Context check failed (will retry)")

                # Sleep until next check
                if not self.quiet:
                    print(f"[{timestamp}] Sleeping for {self.interval_minutes} minute(s)...")
                    print()

                time.sleep(self.interval_minutes * 60)

        except KeyboardInterrupt:
            print()
            print("=" * 70)
            print("Daemon stopped by user")
            print("=" * 70)
            return 0


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description="Background daemon for context monitoring and checkpoint reminders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python auto-checkpoint-daemon.py
      Start daemon checking every 5 minutes (notifications only)

  python auto-checkpoint-daemon.py --interval 10
      Check every 10 minutes

  python auto-checkpoint-daemon.py --auto-checkpoint
      Enable auto-checkpoint at critical threshold

  python auto-checkpoint-daemon.py --once
      Check once and exit (useful for testing or cron)

  python auto-checkpoint-daemon.py --quiet --once
      Silent check (useful for scripts)
        """
    )

    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Minutes between checks (default: 5)'
    )

    parser.add_argument(
        '--auto-checkpoint',
        action='store_true',
        help='Automatically checkpoint at critical threshold (default: notifications only)'
    )

    parser.add_argument(
        '--once',
        action='store_true',
        help='Check once and exit (useful for testing)'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress normal output, only show warnings'
    )

    args = parser.parse_args()

    try:
        daemon = CheckpointDaemon(
            interval_minutes=args.interval,
            auto_checkpoint=args.auto_checkpoint,
            quiet=args.quiet
        )

        if args.once:
            return daemon.check_once()
        else:
            return daemon.run_daemon()

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
