"""
Configuration manager with secure credential storage using system keyring
"""

import json
import keyring
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime


class ConfigManager:
    """Manages configuration and credentials for CSG Sprint Reporter"""

    CONFIG_FILE = Path.home() / ".csg-sprint-config.json"
    SERVICE_NAME = "csg-sprint-reporter"

    # Note: This tool requires user to configure their own API keys
    # No default tokens are provided for security reasons
    # Run: python csg-sprint-reporter.py --config to set up credentials

    def credentials_exist(self) -> bool:
        """Check if credentials are configured"""
        if not self.CONFIG_FILE.exists():
            return False

        try:
            config = self._load_config_file()
            # Check if required fields exist
            if not config.get('jira_site') or not config.get('jira_email'):
                return False

            # Check if tokens exist in keyring
            jira_token = keyring.get_password(self.SERVICE_NAME, "jira_token")
            if not jira_token:
                return False

            return True
        except Exception:
            return False

    def save_credentials(self, jira_site: str, jira_email: str, jira_token: str, fathom_key: Optional[str] = None, claude_api_key: Optional[str] = None) -> None:
        """Save credentials to keyring (encrypted) and config file"""
        # Save sensitive data to system keyring (encrypted)
        keyring.set_password(self.SERVICE_NAME, "jira_token", jira_token)
        if fathom_key:
            keyring.set_password(self.SERVICE_NAME, "fathom_key", fathom_key)
        if claude_api_key:
            keyring.set_password(self.SERVICE_NAME, "claude_api_key", claude_api_key)

        # Save non-sensitive data to JSON config file
        config = {
            "jira_site": jira_site,
            "jira_email": jira_email,
            "last_board": 38,  # Default board
            "last_sprint": None,
            "jira_token_configured_at": datetime.now().isoformat()
        }

        self.CONFIG_FILE.write_text(json.dumps(config, indent=2))
        print(f"[OK] Credentials saved to {self.CONFIG_FILE}")
        print("[OK] API tokens stored securely in system keyring")

    def load_credentials(self) -> Dict[str, str]:
        """Load credentials from keyring and config file"""
        if not self.credentials_exist():
            raise ValueError("Credentials not configured. Run --config first.")

        # Load non-sensitive data from JSON
        config = self._load_config_file()

        # Load sensitive data from keyring
        jira_token = keyring.get_password(self.SERVICE_NAME, "jira_token")
        fathom_key = keyring.get_password(self.SERVICE_NAME, "fathom_key")
        claude_api_key = keyring.get_password(self.SERVICE_NAME, "claude_api_key")

        return {
            "jira_site": config["jira_site"],
            "jira_email": config["jira_email"],
            "jira_token": jira_token,
            "fathom_key": fathom_key,
            "claude_api_key": claude_api_key,
            "last_board": config.get("last_board", 38),
            "last_sprint": config.get("last_sprint"),
            "last_meeting_filter": config.get("last_meeting_filter")
        }

    def save_last_config(self, board: int, sprint: int, meeting_filter: Optional[str] = None) -> None:
        """Save last used configuration for quick mode"""
        if not self.CONFIG_FILE.exists():
            return

        config = self._load_config_file()
        config["last_board"] = board
        config["last_sprint"] = sprint
        if meeting_filter:
            config["last_meeting_filter"] = meeting_filter
        self.CONFIG_FILE.write_text(json.dumps(config, indent=2))

    def first_run_setup(self) -> None:
        """Interactive wizard for first-time credential setup"""
        print("="*60)
        print("CSG Sprint Reporter - First-Time Setup")
        print("="*60)
        print()
        print("Press Enter to use defaults, or type your own values.")
        print()

        # Hardcoded Jira site - no user input needed
        jira_site = "csgsolutions"
        print("Jira site: csgsolutions.atlassian.net")

        # Collect Jira email
        print()
        jira_email = input("Jira email (e.g., name@csgsolutions.com): ").strip()
        if not jira_email:
            print("[ERROR] Jira email is required")
            return

        # Collect Jira token
        print()
        print("Jira API Token:")
        print("  Get your API token: https://id.atlassian.com/manage-profile/security/api-tokens")
        print("  (Ctrl+Click the link above to open in your browser)")
        jira_token = input("Jira API token: ").strip()

        if not jira_token:
            print("[ERROR] Jira API token is required")
            return

        # Collect Fathom credentials (required)
        print()
        print("Fathom API Key (required for meeting insights)")
        print("  Get from: https://fathom.video/customize")
        print("  (Ctrl+Click the link above to open in your browser)")
        fathom_key = input("Fathom API key: ").strip()
        if not fathom_key:
            print("[ERROR] Fathom API key is required")
            return

        # Collect Claude API key (optional - for AI-enhanced reports)
        print()
        print("Claude API Key (OPTIONAL - for AI-powered narrative synthesis)")
        print("  Get from: https://console.anthropic.com/settings/keys")
        print("  Cost: ~$0.50-$2.00 per report (depending on meeting volume)")
        print("  Press Enter to skip (use FREE rule-based templates)")
        print("  (Ctrl+Click the link above to open in your browser)")
        claude_api_key = input("Claude API key [optional]: ").strip()

        # Save credentials
        self.save_credentials(jira_site, jira_email, jira_token, fathom_key, claude_api_key if claude_api_key else None)
        print()
        if claude_api_key:
            print("[OK] Setup complete! You can now run the sprint reporter with --ai flag for AI-powered reports.")
        else:
            print("[OK] Setup complete! You can now run the sprint reporter (using FREE rule-based templates).")
        print()

    def save_claude_api_key(self, claude_api_key: str) -> None:
        """Save Claude API key for existing users (marked as PERMANENT)"""
        if claude_api_key:
            keyring.set_password(self.SERVICE_NAME, "claude_api_key", claude_api_key)

            # Mark as PERMANENT personal key
            config = self._load_config_file()
            config.update({
                "claude_key_type": "PERMANENT",
                "claude_key_configured_at": datetime.now().isoformat()
            })
            self.CONFIG_FILE.write_text(json.dumps(config, indent=2))

            print("[OK] Personal Claude API key stored (PERMANENT)")
            print("[OK] No credit monitoring - you manage your own billing")
            print("[OK] You can now use --ai flag for AI-powered reports")
        else:
            print("[ERROR] Claude API key cannot be empty")

    def get_claude_key_metadata(self) -> Dict[str, str]:
        """Get metadata about configured Claude API key"""
        config = self._load_config_file()
        return {
            "key_type": config.get("claude_key_type", "UNKNOWN"),
            "configured_at": config.get("claude_key_configured_at"),
            "admin_contact": config.get("admin_contact"),
            "description": config.get("claude_key_description", "")
        }

    def is_shared_temp_key(self) -> bool:
        """Check if current key is a shared temporary key"""
        config = self._load_config_file()
        return config.get("claude_key_type") == "TEMP"

    def check_token_expiration(self) -> Optional[str]:
        """
        Token expiration check - no-op in public version.
        Personal API tokens don't expire unless manually revoked.
        Returns None (no warnings).
        """
        return None

    def _load_config_file(self) -> Dict:
        """Load config file from disk"""
        if not self.CONFIG_FILE.exists():
            return {}

        try:
            return json.loads(self.CONFIG_FILE.read_text())
        except json.JSONDecodeError:
            return {}
