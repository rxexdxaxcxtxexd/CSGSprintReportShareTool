#!/usr/bin/env python3
"""
Unified Checkpoint Command
Combines: save-session.py + update-session-state.py + display

Usage:
    python checkpoint.py --quick                    # Quick checkpoint
    python checkpoint.py                            # Interactive mode
    python checkpoint.py --description "message"    # With description
    python checkpoint.py --dry-run                  # Preview only
"""

import sys
import subprocess
import argparse
from pathlib import Path

# Import the UI design system
try:
    import claude_terminal_ui as ui
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False
    # Fallback functions if UI not available
    class ui:
        @staticmethod
        def header(title, **kwargs):
            line = "=" * 70
            centered = " " * ((70 - len(title)) // 2) + title
            return "\n".join([line, centered, line])

        @staticmethod
        def divider(**kwargs):
            print("-" * 70)

        @staticmethod
        def step_indicator(current, total, message=""):
            return f"[{current}/{total}] {message}"

        @staticmethod
        def print_success(message, **kwargs):
            print(f"[OK] {message}")

        @staticmethod
        def print_error(message, **kwargs):
            print(f"[ERROR] {message}")

        @staticmethod
        def print_warning(message, **kwargs):
            print(f"[WARNING] {message}")

        @staticmethod
        def print_info(message, **kwargs):
            print(f"[INFO] {message}")


def run_command(command: list, description: str, can_fail: bool = False, verbose: bool = False) -> bool:
    """Run a command and display results

    Args:
        command: Command to run
        description: What the command does
        can_fail: If True, continue on error; if False, exit on error

    Returns:
        True if successful, False if failed
    """
    if verbose:
        ui.print_info(f"Running: {' '.join(command)}")

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        if can_fail:
            ui.print_warning(f"{description} failed:")
            print(f"  {result.stderr}")
            return False
        else:
            ui.print_error(f"{description} failed:")
            print(f"  {result.stderr}")
            sys.exit(1)

    # Show output
    if result.stdout:
        print(result.stdout)

    return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Unified checkpoint command for session continuity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python checkpoint.py --quick
      Quick checkpoint with auto-detected description

  python checkpoint.py --description "Implemented auth system"
      Checkpoint with custom description

  python checkpoint.py --dry-run
      Preview what would be checkpointed without saving

  python checkpoint.py
      Interactive mode with prompts for details
        """
    )

    # Main options
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick checkpoint (no prompts, auto-detect everything)'
    )

    parser.add_argument(
        '--description',
        type=str,
        help='Custom session description'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview checkpoint without creating files'
    )

    parser.add_argument(
        '--since-minutes',
        type=int,
        default=240,
        help='Look for changes in last N minutes (default: 240)'
    )

    parser.add_argument(
        '--project-path',
        type=str,
        help='Project directory path (bypasses auto-detection)'
    )

    parser.add_argument(
        '--force-home',
        action='store_true',
        help='Allow checkpointing from home directory (for automated monitoring)'
    )

    # Advanced options
    parser.add_argument(
        '--skip-update',
        action='store_true',
        help='Skip CLAUDE.md update (advanced)'
    )

    parser.add_argument(
        '--skip-display',
        action='store_true',
        help='Skip summary display (advanced)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed progress'
    )

    args = parser.parse_args()

    # Get scripts directory
    scripts_dir = Path(__file__).parent

    # Print header
    print()
    print(ui.header("UNIFIED CHECKPOINT"))

    if args.dry_run:
        ui.print_info("DRY RUN MODE - No files will be created")

    print()

    # Step 1: Save session
    print(ui.step_indicator(1, 3, "Collecting and saving session data..."))
    print()

    save_cmd = [sys.executable, str(scripts_dir / 'save-session.py')]

    if args.quick:
        save_cmd.append('--quick')

    if args.description:
        save_cmd.extend(['--description', args.description])

    if args.dry_run:
        save_cmd.append('--dry-run')

    if args.project_path:
        save_cmd.extend(['--project-path', args.project_path])

    if args.force_home:
        save_cmd.append('--force-home')

    save_cmd.extend(['--since-minutes', str(args.since_minutes)])

    success = run_command(
        save_cmd,
        "Save session",
        can_fail=False,
        verbose=args.verbose
    )

    # If dry-run, stop here
    if args.dry_run:
        print()
        print(ui.divider())
        ui.print_info("DRY RUN COMPLETE - No files were created")
        print(ui.divider())
        return 0

    # Step 2: Update CLAUDE.md (unless skipped)
    if not args.skip_update:
        print()
        print(ui.step_indicator(2, 3, "Updating CLAUDE.md..."))

        update_cmd = [
            sys.executable,
            str(scripts_dir / 'update-session-state.py'),
            'update'
        ]

        success = run_command(
            update_cmd,
            "Update CLAUDE.md",
            can_fail=True,  # Can continue if this fails
            verbose=args.verbose
        )

        if success:
            ui.print_success("CLAUDE.md synchronized with checkpoint")

        # Step 2.5: Extract memory insights (optional)
        if success and not args.skip_update:  # Only if CLAUDE.md update succeeded
            print()
            print(ui.step_indicator(2.5, 3, "Extracting memory insights..."))

            memory_cmd = [
                sys.executable,
                str(scripts_dir / 'memory_trigger.py'),
                '--prompt', 'session checkpoint - extract relevant context',
                '--test'  # Use test mode initially to avoid MCP dependency
            ]

            memory_success = run_command(
                memory_cmd,
                "Extract memory context",
                can_fail=True,  # Memory extraction is optional
                verbose=args.verbose
            )

            if memory_success:
                ui.print_success("Memory insights extracted")
            else:
                ui.print_info("Memory extraction skipped (MCP unavailable)")
    else:
        if args.verbose:
            print()
            print(ui.step_indicator(2, 3, "Skipping CLAUDE.md update (--skip-update)"))

    # Step 3: Display summary (unless skipped)
    if not args.skip_display:
        print()
        print(ui.step_indicator(3, 3, "Session summary:"))
        print(ui.divider())

        summary_cmd = [
            sys.executable,
            str(scripts_dir / 'resume-session.py'),
            'summary'
        ]

        run_command(
            summary_cmd,
            "Display summary",
            can_fail=True,  # Can continue if this fails
            verbose=args.verbose
        )
    else:
        if args.verbose:
            print()
            print(ui.step_indicator(3, 3, "Skipping summary display (--skip-display)"))

    # Final message
    print()
    print(ui.header("CHECKPOINT COMPLETE"))
    print()
    ui.print_info("To resume in a new session:")
    print("  python scripts/resume-session.py")
    print()
    ui.print_info("To check context usage:")
    print("  python scripts/context-monitor.py")
    print()
    print(ui.divider())

    return 0


if __name__ == "__main__":
    sys.exit(main())
