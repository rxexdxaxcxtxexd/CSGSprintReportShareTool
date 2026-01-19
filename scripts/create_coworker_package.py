#!/usr/bin/env python3
"""
Create a ZIP package for sharing the CSG Sprint Reporter with coworkers
"""

import zipfile
from pathlib import Path
from datetime import datetime

# Files to include in the package
FILES_TO_INCLUDE = [
    # Main script
    "csg-sprint-reporter.py",
    "manage-claude-key.py",

    # Helper scripts for Windows
    "INSTALL.bat",
    "SETUP.bat",
    "RUN_REPORT.bat",

    # Helper scripts for Mac/Linux
    "install.sh",
    "setup.sh",
    "run_report.sh",

    # Documentation
    "COWORKER_SETUP_SIMPLE.md",
    "COWORKER_SETUP_TECHNICAL.md",
    "README.md",

    # Requirements
    "requirements-sprint-reporter.txt",

    # Library modules
    "csg_sprint_lib/__init__.py",
    "csg_sprint_lib/models.py",
    "csg_sprint_lib/api_client.py",
    "csg_sprint_lib/config_manager.py",
    "csg_sprint_lib/report_generator.py",
    "csg_sprint_lib/word_generator.py",
    "csg_sprint_lib/interactive_menu.py",
]

def create_package():
    """Create ZIP package for coworker sharing"""
    # Generate timestamped filename
    timestamp = datetime.now().strftime('%Y%m%d')
    output_file = Path.home() / "Downloads" / f"CSG-Sprint-Reporter-{timestamp}.zip"

    print("=" * 60)
    print("Creating Coworker Package")
    print("=" * 60)
    print()

    # Get script directory
    script_dir = Path(__file__).parent

    # Create ZIP file
    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in FILES_TO_INCLUDE:
            source = script_dir / file_path

            if not source.exists():
                print(f"[SKIP] {file_path} (not found)")
                continue

            # Add to ZIP with relative path
            zipf.write(source, f"CSG-Sprint-Reporter/{file_path}")
            print(f"[ADD]  {file_path}")

    print()
    print("=" * 60)
    print("PACKAGE CREATED SUCCESSFULLY!")
    print("=" * 60)
    print()
    print(f"Location: {output_file}")
    print(f"Size:     {output_file.stat().st_size / 1024:.1f} KB")
    print()
    print("Next Steps:")
    print("1. Upload this ZIP to OneDrive/SharePoint/Teams")
    print("2. Share the link with your coworker")
    print("3. Include the sharing message template (see output below)")
    print()
    print("=" * 60)
    print()

    return output_file


if __name__ == "__main__":
    package_path = create_package()

    # Print sharing message template
    print()
    print("📧 SHARING MESSAGE TEMPLATE")
    print("=" * 60)
    print()
    print("""Hey [Name]! 👋

I built a tool that automates our sprint reports - no coding required!

📥 Download: [Paste your OneDrive/SharePoint/Teams link here]
📖 Step-by-step guide: Included in the ZIP (COWORKER_SETUP_SIMPLE.md)

Super simple:
1. Extract the ZIP file
2. Double-click "INSTALL.bat" (installs dependencies)
3. Double-click "SETUP.bat" (enter your Jira/Fathom credentials)
4. Double-click "RUN_REPORT.bat" (enter sprint number)

The tool pulls Jira tickets and Fathom meetings, then creates a professional
Word document report in 2 minutes. I'm covering the AI costs so it's free for you!

Your reports will be saved as Word documents using our company template to:
OneDrive - Cornerstone Solutions Group\\Desktop\\Files in use\\Michael SRT\\

Questions? Just ping me!

Layden
""")
    print("=" * 60)
    print()
    print(f"✅ Package ready: {package_path}")
