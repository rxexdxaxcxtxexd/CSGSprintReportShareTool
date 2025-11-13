#!/usr/bin/env python3
"""
Checkpoint Schema - Validation schema for session checkpoints

Defines the expected structure of checkpoint JSON files and provides
validation functions to ensure data integrity.

Usage:
    from checkpoint_schema import validate_checkpoint, CHECKPOINT_SCHEMA

    is_valid, errors = validate_checkpoint(checkpoint_data)
    if not is_valid:
        print("Validation errors:", errors)
"""

from typing import Dict, List, Tuple, Any
from datetime import datetime


# Expected checkpoint schema
CHECKPOINT_SCHEMA = {
    "required_fields": [
        "session_id",
        "timestamp",
        "description",
        "file_changes",
        "completed_tasks",
        "pending_tasks",
        "next_steps",
        "resume_points"
    ],
    "optional_fields": [
        "current_task",
        "problems_encountered",
        "decisions",
        "context"
    ],
    "field_types": {
        "session_id": str,
        "timestamp": str,  # ISO format datetime string
        "description": str,
        "current_task": (str, type(None)),
        "file_changes": list,
        "completed_tasks": list,
        "pending_tasks": list,
        "next_steps": list,
        "resume_points": list,
        "problems_encountered": list,
        "decisions": list,
        "context": dict
    },
    "list_item_schemas": {
        "file_changes": {
            "required": ["file_path", "action"],
            "optional": ["description", "source", "modified"],
            "action_values": ["created", "modified", "deleted"]
        },
        "completed_tasks": {
            "required": ["description", "created_at"],
            "optional": ["completed_at", "notes", "status"]
        },
        "pending_tasks": {
            "required": ["description", "created_at", "status"],
            "optional": []
        },
        "problems_encountered": {
            "type": str
        },
        "decisions": {
            "required": ["question", "decision", "rationale", "timestamp"],
            "optional": ["alternatives_considered"]
        },
        "next_steps": {
            "type": str
        },
        "resume_points": {
            "type": str
        }
    }
}


def validate_checkpoint(checkpoint: Dict) -> Tuple[bool, List[str]]:
    """Validate a checkpoint against the schema

    Args:
        checkpoint: Checkpoint data dictionary

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check required fields
    for field in CHECKPOINT_SCHEMA["required_fields"]:
        if field not in checkpoint:
            errors.append(f"Missing required field: {field}")

    # Check field types
    for field, expected_type in CHECKPOINT_SCHEMA["field_types"].items():
        if field in checkpoint:
            value = checkpoint[field]

            # Handle None values for optional fields
            if value is None and field not in CHECKPOINT_SCHEMA["required_fields"]:
                continue

            # Handle union types (e.g., str | None)
            if isinstance(expected_type, tuple):
                if not isinstance(value, expected_type):
                    errors.append(
                        f"Field '{field}' has wrong type: expected {expected_type}, got {type(value).__name__}"
                    )
            else:
                if not isinstance(value, expected_type):
                    errors.append(
                        f"Field '{field}' has wrong type: expected {expected_type.__name__}, got {type(value).__name__}"
                    )

    # Validate timestamp format
    if "timestamp" in checkpoint:
        try:
            datetime.fromisoformat(checkpoint["timestamp"])
        except (ValueError, TypeError):
            errors.append(f"Invalid timestamp format: {checkpoint['timestamp']}")

    # Validate list items
    for list_field, item_schema in CHECKPOINT_SCHEMA["list_item_schemas"].items():
        if list_field not in checkpoint:
            continue

        items = checkpoint[list_field]
        if not isinstance(items, list):
            continue  # Already caught by type checking

        # If schema specifies a simple type (str), validate that
        if "type" in item_schema:
            for i, item in enumerate(items):
                if not isinstance(item, item_schema["type"]):
                    errors.append(
                        f"{list_field}[{i}]: expected {item_schema['type'].__name__}, "
                        f"got {type(item).__name__}"
                    )

        # If schema specifies required/optional fields, validate dict structure
        elif "required" in item_schema:
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append(f"{list_field}[{i}]: expected dict, got {type(item).__name__}")
                    continue

                # Check required fields
                for req_field in item_schema["required"]:
                    if req_field not in item:
                        errors.append(f"{list_field}[{i}]: missing required field '{req_field}'")

                # Validate action values for file_changes
                if list_field == "file_changes" and "action" in item:
                    if item["action"] not in item_schema["action_values"]:
                        errors.append(
                            f"{list_field}[{i}]: invalid action '{item['action']}', "
                            f"expected one of {item_schema['action_values']}"
                        )

    # Check for suspicious patterns that might indicate corruption
    if "session_id" in checkpoint:
        if len(checkpoint["session_id"]) == 0:
            errors.append("session_id is empty")

    if "description" in checkpoint:
        if len(checkpoint["description"]) == 0:
            errors.append("description is empty")

    # Validate counts are reasonable
    if "file_changes" in checkpoint:
        if len(checkpoint["file_changes"]) > 10000:
            errors.append(f"Suspiciously large number of file_changes: {len(checkpoint['file_changes'])}")

    return (len(errors) == 0, errors)


def format_validation_errors(errors: List[str]) -> str:
    """Format validation errors into a readable string

    Args:
        errors: List of error messages

    Returns:
        Formatted error string
    """
    if not errors:
        return "No errors"

    formatted = "Checkpoint validation failed:\n"
    for i, error in enumerate(errors, 1):
        formatted += f"  {i}. {error}\n"

    return formatted


def validate_checkpoint_file(filepath: str) -> Tuple[bool, List[str]]:
    """Validate a checkpoint file

    Args:
        filepath: Path to checkpoint JSON file

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    import json
    from pathlib import Path

    errors = []
    file_path = Path(filepath)

    # Check file exists
    if not file_path.exists():
        return (False, [f"File not found: {filepath}"])

    # Check file is not empty
    if file_path.stat().st_size == 0:
        return (False, ["File is empty"])

    # Try to load JSON
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            checkpoint = json.load(f)
    except json.JSONDecodeError as e:
        return (False, [f"Invalid JSON: {e}"])
    except Exception as e:
        return (False, [f"Failed to read file: {e}"])

    # Validate checkpoint structure
    return validate_checkpoint(checkpoint)


def main():
    """Command-line interface for validating checkpoint files"""
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate checkpoint files against schema"
    )
    parser.add_argument(
        'checkpoint_file',
        help='Path to checkpoint JSON file to validate'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed output even if valid'
    )

    args = parser.parse_args()

    print(f"Validating: {args.checkpoint_file}")
    print()

    is_valid, errors = validate_checkpoint_file(args.checkpoint_file)

    if is_valid:
        print("[OK] Checkpoint is valid")
        if args.verbose:
            import json
            with open(args.checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
            print(f"  Session ID: {checkpoint.get('session_id')}")
            print(f"  Timestamp: {checkpoint.get('timestamp')}")
            print(f"  File changes: {len(checkpoint.get('file_changes', []))}")
            print(f"  Tasks: {len(checkpoint.get('completed_tasks', []))} completed, "
                  f"{len(checkpoint.get('pending_tasks', []))} pending")
        return 0
    else:
        print("[ERROR] Checkpoint validation failed:")
        print()
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
