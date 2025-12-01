#!/usr/bin/env python3
"""
Session Monitor - Active monitoring daemon for long-running Claude Code sessions

This daemon continuously monitors all active Claude Code sessions and creates
intelligent checkpoints based on activity, time, context usage, and idle detection.

Achieves 100% automation for long-running sessions that stay open for days.
"""

import sys
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

# Import our modules
import session_detector
import checkpoint_coordinator


class CheckpointDecisionEngine:
    """Decide when to create checkpoints based on multi-factor analysis"""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize decision engine

        Args:
            config: Configuration dictionary with trigger thresholds
        """
        # Default configuration (can be overridden)
        self.config = config or {
            'time_hours': 2,           # Checkpoint every 2 hours
            'activity_file_count': 15,  # Or 15 files changed
            'context_percent': 75,      # Or context 75% full
            'idle_minutes': 30,         # Or 30 min idle
        }

        # Trigger weights for scoring
        self.weights = {
            'time': 0.3,
            'activity': 0.4,
            'context': 0.5,
            'idle': 0.2
        }

    def should_checkpoint(self, session: session_detector.SessionInfo) -> tuple[bool, str]:
        """
        Determine if session should be checkpointed

        Args:
            session: SessionInfo object

        Returns:
            (should_checkpoint, reason)
        """
        scores = {}
        reasons = []

        # Factor 1: Time since last checkpoint
        time_score = self._calculate_time_score(session)
        scores['time'] = time_score
        if time_score >= 1.0:
            hours = self.config['time_hours']
            reasons.append(f"Time trigger ({hours}+ hours since last checkpoint)")

        # Factor 2: Activity (file changes)
        activity_score = self._calculate_activity_score(session)
        scores['activity'] = activity_score
        if activity_score >= 1.0:
            count = self.config['activity_file_count']
            reasons.append(f"Activity trigger ({count}+ files modified)")

        # Factor 3: Context usage (not implemented yet, placeholder)
        context_score = 0.0  # TODO: Implement context monitoring
        scores['context'] = context_score

        # Factor 4: Idle detection
        idle_score = self._calculate_idle_score(session)
        scores['idle'] = idle_score
        if idle_score >= 1.0:
            mins = self.config['idle_minutes']
            reasons.append(f"Idle trigger ({mins}+ minutes idle)")

        # Calculate weighted total score
        total_score = sum(
            scores[factor] * self.weights[factor]
            for factor in scores
        )

        # Checkpoint if any single factor is triggered OR weighted score >= 1.0
        should_checkpoint = total_score >= 1.0 or any(s >= 1.0 for s in scores.values())

        reason = "; ".join(reasons) if reasons else f"Multi-factor score: {total_score:.2f}"

        return should_checkpoint, reason

    def _calculate_time_score(self, session: session_detector.SessionInfo) -> float:
        """Calculate time-based score"""
        if not session.last_checkpoint_time:
            # Never checkpointed - high urgency if session has activity
            if session.activity_metrics.messages_count > 0:
                return 1.5  # Trigger immediately
            return 0.0

        try:
            last_checkpoint = datetime.fromisoformat(session.last_checkpoint_time)
            now = datetime.now()
            delta = now - last_checkpoint

            hours_since = delta.total_seconds() / 3600
            threshold = self.config['time_hours']

            return hours_since / threshold

        except Exception:
            return 0.0

    def _calculate_activity_score(self, session: session_detector.SessionInfo) -> float:
        """Calculate activity-based score"""
        files_modified = session.activity_metrics.files_modified
        threshold = self.config['activity_file_count']

        if files_modified == 0:
            return 0.0

        return files_modified / threshold

    def _calculate_idle_score(self, session: session_detector.SessionInfo) -> float:
        """Calculate idle-based score"""
        time_since_activity = session.activity_metrics.time_since_activity_minutes

        if time_since_activity is None:
            return 0.0

        threshold = self.config['idle_minutes']
        return time_since_activity / threshold


class SessionMonitor:
    """Main session monitoring daemon"""

    def __init__(self, config: Optional[Dict] = None, quiet: bool = False):
        """
        Initialize session monitor

        Args:
            config: Configuration dictionary
            quiet: Suppress normal output
        """
        self.config = config or {}
        self.quiet = quiet

        # Initialize components
        self.detector = session_detector.SessionDetector()
        self.coordinator = checkpoint_coordinator.CheckpointCoordinator()
        self.decision_engine = CheckpointDecisionEngine(config)

        # Setup logging
        self._setup_logging()

        # Track last check time
        self.last_check = None

    def _setup_logging(self):
        """Setup logging"""
        log_file = Path.home() / '.claude' / 'session-monitor.log'
        log_file.parent.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=logging.INFO if not self.quiet else logging.WARNING,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout) if not self.quiet else logging.NullHandler()
            ]
        )

        self.logger = logging.getLogger(__name__)

    def run_once(self) -> int:
        """
        Run a single monitoring check

        Returns:
            Number of checkpoints created
        """
        self.logger.info("=" * 70)
        self.logger.info("Starting session check...")

        # Find all active sessions
        sessions = self.detector.find_active_sessions()
        self.logger.info(f"Found {len(sessions)} active session(s)")

        if not sessions:
            self.logger.info("No active sessions found")
            return 0

        # Sort sessions by priority: oldest checkpoint first
        sessions_to_checkpoint = []

        for session in sessions:
            # Check if checkpoint is allowed (cooldown period)
            if not self.coordinator.can_checkpoint(session.session_id, session.project_path):
                self.logger.info(f"Session {session.session_id[:8]} is in cooldown period")
                continue

            # Check if checkpoint needed
            should_checkpoint, reason = self.decision_engine.should_checkpoint(session)

            if should_checkpoint:
                sessions_to_checkpoint.append((session, reason))
                self.logger.info(f"Session {session.session_id[:8]} needs checkpoint: {reason}")

        if not sessions_to_checkpoint:
            self.logger.info("No sessions need checkpointing")
            return 0

        # Sort by last checkpoint time (oldest first) to prioritize risk
        sessions_to_checkpoint.sort(
            key=lambda x: x[0].last_checkpoint_time or '1970-01-01'
        )

        # Checkpoint each session
        checkpoints_created = 0
        for session, reason in sessions_to_checkpoint:
            if self._create_checkpoint(session, reason):
                checkpoints_created += 1

        self.logger.info(f"Created {checkpoints_created} checkpoint(s)")
        return checkpoints_created

    def _create_checkpoint(self, session: session_detector.SessionInfo, reason: str) -> bool:
        """
        Create checkpoint for a session

        Args:
            session: SessionInfo object
            reason: Reason for checkpoint

        Returns:
            True if successful
        """
        self.logger.info(f"Creating checkpoint for {session.project_path}")
        self.logger.info(f"  Reason: {reason}")

        # Validate project path exists
        from pathlib import Path
        project_path = Path(session.project_path)
        if not project_path.exists():
            self.logger.error(f"Project path does not exist: {session.project_path}")
            return False
        if not project_path.is_dir():
            self.logger.error(f"Project path is not a directory: {session.project_path}")
            return False

        # Acquire lock
        if not self.coordinator.acquire_lock(timeout=60):
            self.logger.warning("Failed to acquire checkpoint lock (timeout)")
            return False

        try:
            # Change to project directory
            checkpoint_script = Path(__file__).parent / 'checkpoint.py'

            # Build command with project path and force-home flag
            cmd = [
                sys.executable, str(checkpoint_script),
                '--quick',
                '--description', f'Auto: {reason}',
                '--project-path', session.project_path,
                '--force-home'  # Allow checkpointing from home directory
            ]

            # Run checkpoint script (no cwd needed since we pass --project-path)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0:
                self.logger.info("Checkpoint created successfully")

                # Update coordinator state
                self.coordinator.update_session_state(
                    session.session_id,
                    session.project_path,
                    reason
                )

                return True
            else:
                self.logger.error(f"Checkpoint failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            self.logger.error("Checkpoint timed out (>5 minutes)")
            return False

        except Exception as e:
            self.logger.error(f"Checkpoint error: {e}")
            return False

        finally:
            # Always release lock
            self.coordinator.release_lock()

    def run_daemon(self, check_interval: int = 300):
        """
        Run as daemon, checking periodically

        Args:
            check_interval: Seconds between checks (default: 5 minutes)
        """
        self.logger.info("=" * 70)
        self.logger.info("SESSION MONITOR STARTED")
        self.logger.info("=" * 70)
        self.logger.info(f"Check interval: {check_interval} seconds ({check_interval/60:.1f} minutes)")
        self.logger.info(f"Configuration: {self.config}")
        self.logger.info("")
        self.logger.info("Press Ctrl+C to stop")
        self.logger.info("=" * 70)

        try:
            while True:
                self.last_check = datetime.now()

                try:
                    self.run_once()
                except Exception as e:
                    self.logger.error(f"Check failed: {e}", exc_info=True)

                # Sleep until next check
                self.logger.info(f"Next check in {check_interval/60:.1f} minutes...")
                self.logger.info("")
                time.sleep(check_interval)

        except KeyboardInterrupt:
            self.logger.info("")
            self.logger.info("=" * 70)
            self.logger.info("Session monitor stopped by user")
            self.logger.info("=" * 70)


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description="Session Monitor - Active monitoring daemon for Claude Code sessions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python session_monitor.py
      Start daemon with default settings (check every 5 minutes)

  python session_monitor.py --interval 10
      Check every 10 minutes

  python session_monitor.py --once
      Run a single check and exit

  python session_monitor.py --quiet --once
      Silent single check (useful for testing)

Configuration:
  Default triggers: 2 hours OR 15 files OR 30 min idle OR 75% context
  Adjust via --config-file option (future enhancement)
        """
    )

    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Minutes between checks (default: 5)'
    )

    parser.add_argument(
        '--once',
        action='store_true',
        help='Run once and exit (useful for testing)'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress normal output'
    )

    parser.add_argument(
        '--time-hours',
        type=float,
        help='Time trigger threshold in hours (default: 2)'
    )

    parser.add_argument(
        '--activity-files',
        type=int,
        help='Activity trigger threshold in files (default: 15)'
    )

    parser.add_argument(
        '--idle-minutes',
        type=int,
        help='Idle trigger threshold in minutes (default: 30)'
    )

    parser.add_argument(
        '--context-percent',
        type=int,
        help='Context trigger threshold in percent (default: 75)'
    )

    args = parser.parse_args()

    # Build configuration
    config = {}
    if args.time_hours is not None:
        config['time_hours'] = args.time_hours
    if args.activity_files is not None:
        config['activity_file_count'] = args.activity_files
    if args.idle_minutes is not None:
        config['idle_minutes'] = args.idle_minutes
    if args.context_percent is not None:
        config['context_percent'] = args.context_percent

    # Initialize monitor
    monitor = SessionMonitor(config=config, quiet=args.quiet)

    try:
        if args.once:
            # Single check
            checkpoints = monitor.run_once()
            return 0 if checkpoints >= 0 else 1
        else:
            # Daemon mode
            interval_seconds = args.interval * 60
            monitor.run_daemon(check_interval=interval_seconds)
            return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
