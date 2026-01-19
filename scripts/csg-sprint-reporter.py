#!/usr/bin/env python3
"""
CSG Sprint Reporter - Standalone CLI Tool
Generate sprint reports from Jira + Fathom without AI

Usage:
  python csg-sprint-reporter.py                    # Interactive mode
  python csg-sprint-reporter.py --config           # Configure credentials
  python csg-sprint-reporter.py --quick --sprint 13 # Quick mode

Requirements:
  pip install -r requirements-sprint-reporter.txt
"""

import argparse
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add script directory to path to import csg_sprint_lib
sys.path.insert(0, str(Path(__file__).parent))

from csg_sprint_lib import (
    ConfigManager,
    JiraClient,
    FathomClient,
    ClaudeClient,
    SprintReportGenerator,
    InteractiveMenu
)
from csg_sprint_lib.api_client import CreditExhaustedError


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="CSG Sprint Reporter - Generate sprint reports from Jira + Fathom",
        epilog="For first-time setup, run: python csg-sprint-reporter.py --config"
    )
    parser.add_argument("--config", action="store_true", help="Configure credentials")
    parser.add_argument("--add-claude-key", action="store_true", help="Add Claude API key to existing configuration")
    parser.add_argument("--quick", action="store_true", help="Skip interactive menu, use last config")
    parser.add_argument("--sprint", type=int, help="Sprint number (required for --quick mode)")
    parser.add_argument("--ai", action="store_true", help="Use AI-powered narrative synthesis (requires Claude API key)")
    parser.add_argument(
        '--format',
        choices=['docx', 'md', 'both'],
        default=None,
        help='Output format: docx (Word), md (Markdown), or both (default: docx)'
    )
    parser.add_argument(
        '--template',
        type=str,
        help='Path to Word template .docx file (optional)'
    )

    args = parser.parse_args()

    # Setup debug logging to Downloads folder
    log_dir = Path.home() / "Downloads"
    log_file = log_dir / f"csg-sprint-reporter-debug-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info(f"Debug log created: {log_file}")
    logger.info(f"Command: {' '.join(sys.argv)}")

    # Initialize config manager
    config_mgr = ConfigManager()

    # Track if we just completed setup
    just_completed_setup = False

    # Mode 1: Reconfigure credentials
    if args.config:
        config_mgr.first_run_setup()
        just_completed_setup = True
        # Don't return - fall through to interactive mode

    # Mode 1b: Add Claude API key to existing config
    if args.add_claude_key:
        print("=" * 60)
        print("ADD CLAUDE API KEY")
        print("=" * 60)
        print()
        print("Add Claude API key for AI-powered report synthesis")
        print("Get your key at: https://console.anthropic.com/settings/keys")
        print("Cost: ~$0.50-$2.00 per report")
        print()
        claude_key = input("Claude API key: ").strip()
        if claude_key:
            config_mgr.save_claude_api_key(claude_key)
            print()
            print("✅ Done! Run with --ai flag to use AI-powered reports")
        else:
            print("[ERROR] No API key provided")
        return 0

    # Mode 2: Check if credentials exist
    if not config_mgr.credentials_exist():
        print("=" * 60)
        print("FIRST-TIME SETUP REQUIRED")
        print("=" * 60)
        print()
        print("No credentials found. Running first-time setup...")
        print()
        config_mgr.first_run_setup()

        if not config_mgr.credentials_exist():
            print()
            print("[ERROR] Setup cancelled or failed")
            return 1

        just_completed_setup = True

    # If we just completed setup, force interactive mode
    if just_completed_setup:
        print()
        print("=" * 60)
        print("Setup complete! Starting interactive mode...")
        print("=" * 60)
        print()
        # Force interactive mode even if --quick was specified
        args.quick = False

    # Check for API token expiration
    expiration_msg = config_mgr.check_token_expiration()
    if expiration_msg:
        print(expiration_msg)

        # Block if expired
        if "EXPIRED" in expiration_msg:
            return 1

        # Just warn if expiring soon
        print()

    # Load credentials
    try:
        creds = config_mgr.load_credentials()
    except Exception as e:
        print(f"[ERROR] Failed to load credentials: {e}")
        print("[ERROR] Run --config to reconfigure")
        return 1

    # Initialize API clients
    print("Initializing API clients...")
    jira_client = JiraClient(creds['jira_site'], creds['jira_email'], creds['jira_token'])

    fathom_client = None
    if creds.get('fathom_key'):
        fathom_client = FathomClient(creds['fathom_key'])

    # Test Jira connection
    print("Testing Jira connection...")
    if not jira_client.test_connection():
        print("[ERROR] Jira authentication failed")
        print("[ERROR] Check your credentials with: python csg-sprint-reporter.py --config")
        return 1
    print("  Jira connection OK")

    # Test Fathom connection if available
    if fathom_client:
        print("Testing Fathom connection...")
        if not fathom_client.test_connection():
            print("[WARNING] Fathom authentication failed")
            print("[WARNING] Meeting insights will not be available")
            fathom_client = None
        else:
            print("  Fathom connection OK")

    # Initialize Claude client if AI mode requested
    claude_client = None
    if args.ai:
        if creds.get('claude_api_key'):
            print("Initializing Claude AI client...")

            # Get key metadata
            key_metadata = config_mgr.get_claude_key_metadata()

            # Pass metadata to Claude client
            claude_client = ClaudeClient(
                creds['claude_api_key'],
                key_metadata=key_metadata
            )

            print("Testing Claude API connection...")
            if not claude_client.test_connection():
                print("[WARNING] Claude API authentication failed")
                print("[WARNING] AI synthesis will not be available - using FREE templates")
                claude_client = None
            else:
                print("  Claude API connection OK - AI synthesis enabled")

                # Display key type
                key_type = key_metadata.get("key_type", "UNKNOWN")
                if key_type == "TEMP":
                    desc = key_metadata.get('description', 'N/A')
                    print(f"  Using shared team key: {desc}")
                elif key_type == "PERMANENT":
                    print("  Using personal API key (you manage billing)")
        else:
            print("[WARNING] --ai flag set but no Claude API key configured")
            print("[WARNING] Run --config to add Claude API key, or use without --ai flag")
            print("[WARNING] Continuing with FREE rule-based templates...")

    # Mode 3: Quick mode (use last config)
    if args.quick:
        if not args.sprint:
            print("[ERROR] --quick mode requires --sprint N")
            return 1

        # Use last meeting filter or prompt if not set
        last_meeting_filter = creds.get('last_meeting_filter')
        if not last_meeting_filter:
            print()
            print("Quick mode: Meeting filter not configured.")
            print("Enter keyword for Fathom meeting search (e.g., 'iBOPS', 'Engineering', 'Sprint')")
            last_meeting_filter = input("Meeting keyword: ").strip()
            if not last_meeting_filter:
                print("[ERROR] Meeting filter required for quick mode")
                return 1
            # Save for next time
            config_mgr.save_last_config(creds.get('last_board', 38), args.sprint, last_meeting_filter)

        config = {
            'board_id': creds.get('last_board', 38),
            'sprint_number': args.sprint,
            'meeting_filter': last_meeting_filter,
            'custom_dates': None,
            'sections': {
                'sprint_summary': True,
                'team_breakdown': True,
                'issue_status': True,
                'epic_progress': True,
                'blockers': True,
                'meeting_insights': True
            }
        }
        print(f"Quick mode: Board {config['board_id']}, Sprint {config['sprint_number']}, Meetings: '{last_meeting_filter}'")

    # Mode 4: Interactive mode (default)
    else:
        menu = InteractiveMenu(jira_client, config_mgr)
        config = menu.run()

        if not config:
            print()
            print("[CANCELLED] Report generation cancelled by user")
            return 0

    # Generate report
    print()
    print("=" * 60)
    print(f"Generating Sprint {config['sprint_number']} Report")
    print("=" * 60)
    print()

    generator = SprintReportGenerator(jira_client, fathom_client, config, claude_client)

    try:
        # Fetch data
        generator.fetch_data()

        # Calculate metrics
        print("Calculating metrics...")
        metrics = generator.calculate_metrics()

        # Determine output format
        format_type = args.format if args.format else config_mgr.get_default_format()

        # Get template path if using Word format
        template_path = None
        if format_type in ['docx', 'both']:
            if args.template:
                template_path = Path(args.template)
            else:
                template_path = config_mgr.get_template_path()

        # Generate report(s)
        print("Generating report...")
        if format_type == 'both':
            # Generate both formats
            output_dir_word = config_mgr.get_output_directory('docx')
            output_path_word = generator.save_report(
                output_dir_word,
                format_type='docx',
                template_path=template_path
            )

            output_dir_md = config_mgr.get_output_directory('md')
            markdown = generator.generate_markdown()  # Generate markdown for metrics display
            output_path_md = generator.save_report(
                output_dir_md,
                format_type='md'
            )

            # Save last config for quick mode
            config_mgr.save_last_config(config['board_id'], config['sprint_number'], config['meeting_filter'])

            # Success summary
            print()
            print("=" * 60)
            print("REPORTS GENERATED SUCCESSFULLY")
            print("=" * 60)
            print(f"Word:            {output_path_word}")
            print(f"Markdown:        {output_path_md}")
            print(f"Total Issues:    {metrics.total_issues}")
            print(f"Completed:       {metrics.done_count} ({metrics.completion_rate:.1f}%)")
            print(f"In Progress:     {metrics.in_progress_count}")
            print(f"Meetings:        {len(generator.meetings)}")
            print(f"Debug Log:       {log_file}")
            print("=" * 60)

        else:
            # Generate single format
            output_dir = config_mgr.get_output_directory(format_type)

            # Generate markdown if needed (for display)
            if format_type == 'md':
                markdown = generator.generate_markdown()

            output_path = generator.save_report(
                output_dir,
                format_type=format_type,
                template_path=template_path
            )

            # Save last config for quick mode
            config_mgr.save_last_config(config['board_id'], config['sprint_number'], config['meeting_filter'])

            # Success summary
            print()
            print("=" * 60)
            print("REPORT GENERATED SUCCESSFULLY")
            print("=" * 60)
            print(f"Output:          {output_path}")
            print(f"Format:          {format_type.upper()}")
            print(f"Total Issues:    {metrics.total_issues}")
            print(f"Completed:       {metrics.done_count} ({metrics.completion_rate:.1f}%)")
            print(f"In Progress:     {metrics.in_progress_count}")
            print(f"Meetings:        {len(generator.meetings)}")
            print(f"Debug Log:       {log_file}")
            print("=" * 60)
        print()

        return 0

    except CreditExhaustedError as e:
        print()
        print("=" * 60)
        print("CLAUDE API CREDITS EXHAUSTED")
        print("=" * 60)
        print()
        print("The shared Claude API key has run out of credits.")
        print()
        print("You have TWO OPTIONS to continue using AI-powered reports:")
        print()
        print("Option 1: Contact Tool Admin")
        if e.admin_contact:
            print(f"  Contact: {e.admin_contact}")
            print("  Request: New shared API key or credit top-up")
        else:
            print("  Contact your team lead for a new shared key")
        print()
        print("Option 2: Add Your Personal API Key")
        print("  Run: python csg-sprint-reporter.py --add-claude-key")
        print("  Get key: https://console.anthropic.com/settings/keys")
        print("  Cost: ~$0.50-$2.00 per report")
        print()
        print("=" * 60)
        print()
        print("Continuing with FREE rule-based report (no AI synthesis)...")
        print()

        # Continue with non-AI report
        generator.claude_client = None

        print("Calculating metrics...")
        metrics = generator.calculate_metrics()

        # Determine output format
        format_type = args.format if args.format else config_mgr.get_default_format()

        # Get template path if using Word format
        template_path = None
        if format_type in ['docx', 'both']:
            if args.template:
                template_path = Path(args.template)
            else:
                template_path = config_mgr.get_template_path()

        # Generate report
        print("Generating report...")
        output_dir = config_mgr.get_output_directory(format_type)
        output_path = generator.save_report(
            output_dir,
            format_type=format_type,
            template_path=template_path
        )

        print()
        print("=" * 60)
        print("REPORT GENERATED (WITHOUT AI)")
        print("=" * 60)
        print(f"Output:          {output_path}")
        print(f"Format:          {format_type.upper()}")
        print(f"Total Issues:    {metrics.total_issues}")
        print(f"Completed:       {metrics.done_count} ({metrics.completion_rate:.1f}%)")
        print(f"Meetings:        {len(generator.meetings)}")
        print()
        print("Note: This report uses FREE rule-based templates.")
        print("      Add Claude API key to enable AI-powered synthesis.")
        print("=" * 60)

        return 0

    except ImportError as e:
        if 'docx' in str(e):
            print()
            print("=" * 60)
            print("MISSING DEPENDENCY: python-docx")
            print("=" * 60)
            print()
            print("The python-docx library is required for Word document generation.")
            print()
            print("To install it, run:")
            print("  pip install python-docx")
            print()
            print("Or install all dependencies:")
            print("  pip install -r requirements-sprint-reporter.txt")
            print()
            print("=" * 60)
            return 1
        else:
            # Re-raise other import errors
            raise

    except KeyboardInterrupt:
        print()
        print("[CANCELLED] Report generation interrupted by user")
        print(f"[DEBUG] See log file: {log_file}")
        return 130

    except Exception as e:
        print()
        print("=" * 60)
        print("ERROR GENERATING REPORT")
        print("=" * 60)
        print(f"Error: {e}")
        print()
        print("Troubleshooting:")
        print("  - Check sprint number exists on the board")
        print("  - Verify API credentials with --config")
        print("  - Check network connection")
        print(f"  - Check debug log: {log_file}")
        print("=" * 60)
        logger.exception("Report generation failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
