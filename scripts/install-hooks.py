#!/usr/bin/env python3
"""
Git Hook Installer - Install post-commit hook for automatic checkpoints

This script installs the post-commit hook that automatically creates
session checkpoints after every git commit.

Usage:
  python scripts/install-hooks.py              # Install in current repo
  python scripts/install-hooks.py --uninstall  # Remove hooks
  python scripts/install-hooks.py --test       # Test hook functionality
  python scripts/install-hooks.py --repo /path # Install in specific repo
"""

import os
import sys
import stat
import subprocess
import argparse
from pathlib import Path
from typing import Optional


class GitHookInstaller:
    """Install and manage git hooks for session tracking"""

    def __init__(self, repo_path: Optional[Path] = None):
        """
        Initialize the hook installer.

        Args:
            repo_path: Path to git repository (defaults to current directory)
        """
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self.git_dir = self.repo_path / ".git"
        self.hooks_dir = self.git_dir / "hooks"
        self.post_commit_hook = self.hooks_dir / "post-commit"
        self.script_dir = Path(__file__).parent

    def is_git_repo(self) -> bool:
        """Check if the current directory is a git repository"""
        return self.git_dir.exists() and self.git_dir.is_dir()

    def hook_exists(self) -> bool:
        """Check if post-commit hook already exists"""
        return self.post_commit_hook.exists()

    def install_hook(self) -> bool:
        """
        Install the post-commit hook.

        Returns:
            True if successful, False otherwise
        """
        if not self.is_git_repo():
            print(f"Error: {self.repo_path} is not a git repository")
            print("Please run this command from within a git repository.")
            return False

        # Ensure hooks directory exists
        self.hooks_dir.mkdir(parents=True, exist_ok=True)

        # Check if hook already exists
        if self.hook_exists():
            print(f"\nWARNING: Post-commit hook already exists: {self.post_commit_hook}")
            response = input("Overwrite existing hook? (y/n): ").strip().lower()
            if response != 'y':
                print("Installation cancelled.")
                return False

        # Create hook content
        hook_content = self._generate_hook_content()

        try:
            # Write hook file
            with open(self.post_commit_hook, 'w', encoding='utf-8', newline='\n') as f:
                f.write(hook_content)

            # Make executable (Unix)
            if os.name != 'nt':  # Not Windows
                current_permissions = os.stat(self.post_commit_hook).st_mode
                os.chmod(self.post_commit_hook, current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

            print("\n" + "="*70)
            print("SUCCESS: POST-COMMIT HOOK INSTALLED")
            print("="*70)
            print(f"Repository: {self.repo_path}")
            print(f"Hook file:  {self.post_commit_hook}")
            print()
            print("What happens now:")
            print("  - Every git commit will automatically create a session checkpoint")
            print("  - Checkpoints will be linked to commits via commit hash")
            print("  - save-session.py now stages changes (user commits manually)")
            print()
            print("Next steps:")
            print("  1. Test the hook: python scripts/install-hooks.py --test")
            print("  2. Make a commit: git commit -m \"Test commit\"")
            print("  3. Check checkpoint: python scripts/resume-session.py")
            print("="*70)

            return True

        except Exception as e:
            print(f"\nError installing hook: {e}")
            return False

    def _generate_hook_content(self) -> str:
        """Generate the post-commit hook script content"""
        # Use absolute path to post-commit-handler.py
        handler_path = self.script_dir / "post-commit-handler.py"

        hook_content = f"""#!/usr/bin/env python3
#
# Post-Commit Hook - Automatic Session Checkpoint Creation
#
# This hook automatically creates session checkpoints after every commit.
# Installed by: scripts/install-hooks.py
# Handler: {handler_path}
#

import sys
import subprocess
from pathlib import Path

# Path to post-commit handler
HANDLER_PATH = r"{handler_path}"

try:
    # Run post-commit handler
    result = subprocess.run(
        [sys.executable, HANDLER_PATH],
        capture_output=False,
        text=True,
        timeout=30
    )

    # Exit with handler's exit code (should always be 0 to not break commits)
    sys.exit(result.returncode)

except subprocess.TimeoutExpired:
    print("\\nWARNING: Checkpoint creation timed out (commit succeeded)", file=sys.stderr)
    sys.exit(0)  # Don't break commit

except Exception as e:
    print(f"\\nWARNING: Post-commit hook error: {{e}} (commit succeeded)", file=sys.stderr)
    sys.exit(0)  # Don't break commit
"""
        return hook_content

    def uninstall_hook(self) -> bool:
        """
        Remove the post-commit hook.

        Returns:
            True if successful, False otherwise
        """
        if not self.hook_exists():
            print("No post-commit hook found.")
            return True

        try:
            # Check if it's our hook (contains "scripts/install-hooks.py")
            with open(self.post_commit_hook, 'r', encoding='utf-8') as f:
                content = f.read()

            if "scripts/install-hooks.py" not in content:
                print("\nWARNING: Post-commit hook was not installed by this script.")
                response = input("Remove it anyway? (y/n): ").strip().lower()
                if response != 'y':
                    print("Uninstall cancelled.")
                    return False

            # Remove hook
            self.post_commit_hook.unlink()

            print("\n" + "="*70)
            print("SUCCESS: POST-COMMIT HOOK REMOVED")
            print("="*70)
            print(f"Removed: {self.post_commit_hook}")
            print()
            print("Note: Existing checkpoints are not affected.")
            print("You can reinstall anytime with: python scripts/install-hooks.py")
            print("="*70)

            return True

        except Exception as e:
            print(f"\nError removing hook: {e}")
            return False

    def test_hook(self) -> bool:
        """
        Test the post-commit hook functionality.

        Returns:
            True if test successful, False otherwise
        """
        if not self.hook_exists():
            print("Error: Post-commit hook not installed.")
            print("Run: python scripts/install-hooks.py")
            return False

        print("\n" + "="*70)
        print("TESTING POST-COMMIT HOOK")
        print("="*70)
        print()

        try:
            # Create a test file
            test_file = self.repo_path / ".test-hook-file.txt"
            with open(test_file, 'w') as f:
                f.write(f"Test file created at {sys.argv[0]}\n")

            print("1. Created test file")

            # Stage the test file
            subprocess.run(['git', 'add', str(test_file)], cwd=self.repo_path, check=True)
            print("2. Staged test file")

            # Create test commit
            subprocess.run(
                ['git', 'commit', '-m', 'Test commit for post-commit hook'],
                cwd=self.repo_path,
                check=True,
                capture_output=True
            )
            print("3. Created test commit")

            # Clean up test file
            try:
                test_file.unlink()
                subprocess.run(['git', 'add', str(test_file)], cwd=self.repo_path)
                subprocess.run(
                    ['git', 'commit', '-m', 'Clean up test file'],
                    cwd=self.repo_path,
                    capture_output=True
                )
            except:
                pass

            print()
            print("="*70)
            print("SUCCESS: HOOK TEST PASSED")
            print("="*70)
            print()
            print("The hook is working correctly!")
            print("Check the checkpoint with: python scripts/resume-session.py")
            print("="*70)

            return True

        except subprocess.CalledProcessError as e:
            print(f"\nError during test: {e}")
            print("\nTest failed. Check:")
            print("  1. Git is installed and working")
            print("  2. You're in a git repository")
            print("  3. The hook file has correct permissions")
            return False

        except Exception as e:
            print(f"\nUnexpected error during test: {e}")
            return False


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description="Install git hooks for automatic session checkpoint creation"
    )
    parser.add_argument(
        '--repo',
        type=str,
        default=None,
        help="Path to git repository (default: current directory)"
    )
    parser.add_argument(
        '--uninstall',
        action='store_true',
        help="Remove the post-commit hook"
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help="Test the hook functionality"
    )

    args = parser.parse_args()

    # Initialize installer
    repo_path = Path(args.repo) if args.repo else None
    installer = GitHookInstaller(repo_path)

    # Execute requested action
    if args.uninstall:
        success = installer.uninstall_hook()
    elif args.test:
        success = installer.test_hook()
    else:
        success = installer.install_hook()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
