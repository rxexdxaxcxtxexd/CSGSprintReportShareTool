#!/usr/bin/env python3
"""
Admin tool for managing shared temporary Claude API keys
"""

import argparse
import json
import keyring
from pathlib import Path
from datetime import datetime

SERVICE_NAME = "csg-sprint-reporter"
CONFIG_FILE = Path.home() / ".csg-sprint-config.json"


def load_config():
    """Load config file"""
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text())
    except json.JSONDecodeError:
        return {}


def save_config(config):
    """Save config file"""
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def add_shared_key(api_key: str, admin_email: str, description: str):
    """Add shared temporary Claude API key"""
    # Store key in keyring (encrypted)
    keyring.set_password(SERVICE_NAME, "claude_api_key", api_key)

    # Update config with metadata
    config = load_config()
    config.update({
        "claude_key_type": "TEMP",
        "claude_key_configured_at": datetime.now().isoformat(),
        "claude_key_configured_by": admin_email,
        "claude_key_description": description,
        "admin_contact": admin_email
    })
    save_config(config)

    print("[OK] Shared temporary Claude API key configured")
    print(f"[OK] Admin contact: {admin_email}")
    print(f"[OK] Description: {description}")
    print()
    print("Users will see this contact when credits are exhausted.")


def show_status():
    """Display current key configuration"""
    config = load_config()
    key_exists = keyring.get_password(SERVICE_NAME, "claude_api_key") is not None

    if not key_exists:
        print("No Claude API key configured")
        return

    key_type = config.get("claude_key_type", "UNKNOWN")
    print(f"Claude API Key Status:")
    print(f"  Type: {key_type}")
    print(f"  Configured: {config.get('claude_key_configured_at', 'Unknown')}")

    if key_type == "TEMP":
        print(f"  Admin: {config.get('claude_key_configured_by', 'Unknown')}")
        print(f"  Description: {config.get('claude_key_description', 'N/A')}")
        print(f"  Admin Contact: {config.get('admin_contact', 'Unknown')}")
    elif key_type == "PERMANENT":
        print("  Owner: Personal key (user manages billing)")


def remove_key():
    """Remove Claude API key"""
    try:
        keyring.delete_password(SERVICE_NAME, "claude_api_key")
        print("[OK] Claude API key removed from keyring")
    except keyring.errors.PasswordDeleteError:
        print("[WARN] No key found in keyring")

    # Remove metadata from config
    config = load_config()
    keys_to_remove = [
        "claude_key_type",
        "claude_key_configured_at",
        "claude_key_configured_by",
        "claude_key_description",
        "admin_contact"
    ]
    for key in keys_to_remove:
        config.pop(key, None)
    save_config(config)

    print("[OK] Claude API key metadata removed from config")


def main():
    parser = argparse.ArgumentParser(
        description="Admin tool for managing shared Claude API keys"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Add shared key
    add_parser = subparsers.add_parser("add-shared-key", help="Add shared temporary key")
    add_parser.add_argument("--key", required=True, help="Claude API key")
    add_parser.add_argument("--admin", required=True, help="Admin email")
    add_parser.add_argument("--description", default="Shared team key", help="Description")

    # Show status
    subparsers.add_parser("status", help="Display current key status")

    # Remove key
    subparsers.add_parser("remove-key", help="Remove Claude API key")

    args = parser.parse_args()

    if args.command == "add-shared-key":
        add_shared_key(args.key, args.admin, args.description)
    elif args.command == "status":
        show_status()
    elif args.command == "remove-key":
        remove_key()


if __name__ == "__main__":
    main()
