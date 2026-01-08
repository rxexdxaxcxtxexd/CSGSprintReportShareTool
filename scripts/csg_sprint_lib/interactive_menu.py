"""
Interactive CLI menu system for CSG Sprint Reporter
"""

from typing import Optional, Dict, Tuple
from datetime import datetime
from .api_client import JiraClient
from .config_manager import ConfigManager


class InteractiveMenu:
    """Interactive menu for collecting sprint report configuration"""

    def __init__(self, jira_client: JiraClient, config_manager: ConfigManager):
        self.jira_client = jira_client
        self.config_manager = config_manager

    def run(self) -> Optional[Dict]:
        """Run interactive menu, return configuration or None if cancelled"""
        print("=" * 60)
        print("CSG Sprint Reporter - Interactive Mode")
        print("=" * 60)
        print()

        config = {}

        # 1. Board selection
        config['board_id'] = self.prompt_board_selection()

        # 2. Sprint number
        config['sprint_number'] = self.prompt_sprint_number()

        # 3. Meeting filter
        config['meeting_filter'] = self.prompt_meeting_filter()

        # 4. Date range
        config['custom_dates'] = self.prompt_date_range()

        # 5. Report sections
        config['sections'] = self.prompt_report_sections()

        # Show confirmation summary
        if not self.confirm_configuration(config):
            return None

        return config

    def prompt_board_selection(self) -> int:
        """Prompt for board (default 38) with name display"""
        print("1. Board Selection")
        print()

        # Try to get default board name
        default_board_id = 38
        try:
            default_board_name = self.jira_client.get_board_name(default_board_id)
            print(f"Default: Board {default_board_id} ({default_board_name})")
        except:
            print(f"Default: Board {default_board_id}")

        print()
        print("Enter board ID (appears at end of board URL)")
        print("e.g., https://csgsolutions.atlassian.net/.../boards/38")
        print()
        response = input("Board ID [38]: ").strip()

        if not response:
            return default_board_id

        try:
            board_id = int(response)
            # Validate board exists and show name
            board_name = self.jira_client.get_board_name(board_id)
            print(f"  Selected: {board_name}")
            return board_id
        except ValueError:
            print("  Invalid board ID, using default (38)")
            return default_board_id
        except Exception as e:
            print(f"  Warning: Could not validate board {response}: {e}")
            print("  Using anyway...")
            return int(response)

    def prompt_sprint_number(self) -> int:
        """Prompt for sprint number (manual entry, no auto-detect)"""
        print()
        print("2. Sprint Number")
        while True:
            response = input("   Enter sprint number: ").strip()

            if not response:
                print("   Sprint number is required")
                continue

            try:
                sprint_num = int(response)
                if sprint_num <= 0:
                    print("   Sprint number must be positive")
                    continue
                return sprint_num
            except ValueError:
                print("   Invalid number, please try again")

    def prompt_meeting_filter(self) -> str:
        """Prompt for meeting keyword (single keyword for Fathom search)"""
        print()
        print("3. Meeting Keyword")
        print()
        print("Enter keyword to filter meetings (e.g., 'iBOPS', 'Engineering', 'Sprint')")
        print("Fathom uses fuzzy matching - 'iBOPS' matches 'iBOPS Stand-Up', 'Sprint Review iBOPS', etc.")
        print()
        response = input("Meeting keyword [required]: ").strip()

        # Require user to specify - no generic default
        while not response:
            print("  Meeting keyword is required (no default)")
            response = input("  Enter keyword: ").strip()

        return response

    def prompt_date_range(self) -> Optional[Tuple[datetime, datetime]]:
        """Prompt to customize date range (default: auto from sprint dates)"""
        print()
        print("4. Date Range")
        print("   Default: Auto-detect from sprint dates")
        response = input("   Customize date range? (y/N): ").strip().lower()

        if response != 'y':
            return None

        # Prompt for custom dates
        print("   Enter start date (YYYY-MM-DD):")
        start_str = input("   Start: ").strip()
        print("   Enter end date (YYYY-MM-DD):")
        end_str = input("   End: ").strip()

        try:
            start_date = datetime.fromisoformat(start_str)
            end_date = datetime.fromisoformat(end_str)
            return (start_date, end_date)
        except ValueError:
            print("   Invalid dates, using auto-detect")
            return None

    def prompt_report_sections(self) -> dict:
        """Prompt for sections to include (all enabled by default)"""
        print()
        print("Report Sections")
        print("Select sections to include (all checked by default):")
        print()

        # Show all sections with checkboxes
        sections = {
            'sprint_summary': 'Sprint Summary',
            'team_breakdown': 'Team Breakdown',
            'issue_status': 'Issue Status',
            'epic_progress': 'Epic Progress',
            'blockers': 'Blockers',
            'meeting_insights': 'Meeting Insights'
        }

        # Display with checkbox notation
        for i, (key, name) in enumerate(sections.items(), 1):
            print(f"  [{i}] [X] {name}")

        print()
        print("Press Enter to include all sections, or type section numbers to exclude")
        print("(e.g., '3 5' to exclude Issue Status and Blockers)")
        response = input("Sections to exclude: ").strip()

        # If empty, include all
        if not response:
            return {key: True for key in sections.keys()}

        # Parse exclusions
        try:
            exclude_nums = [int(n) for n in response.split()]
            result = {}
            for i, key in enumerate(sections.keys(), 1):
                result[key] = (i not in exclude_nums)
            return result
        except ValueError:
            print("  Invalid input, using all sections")
            return {key: True for key in sections.keys()}

    def confirm_configuration(self, config: dict) -> bool:
        """Show summary and confirm"""
        print()
        print("=" * 60)
        print("Configuration Summary")
        print("=" * 60)
        print(f"Board:           {config['board_id']}")
        print(f"Sprint:          {config['sprint_number']}")
        print(f"Meeting Filter:  {config['meeting_filter']}")

        if config['custom_dates']:
            start, end = config['custom_dates']
            print(f"Date Range:      {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")
        else:
            print(f"Date Range:      Auto-detect from sprint")

        print(f"Sections:        All enabled")
        print("=" * 60)
        print()

        response = input("Generate report with this configuration? (Y/n): ").strip().lower()

        return response != 'n'
