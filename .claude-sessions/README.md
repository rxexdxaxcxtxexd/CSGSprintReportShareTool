# Claude Code Session Continuity System

## Overview

This directory contains the session continuity system for maintaining context and progress across Claude Code sessions. The system uses a hybrid approach with both human-readable logs (Markdown) and machine-readable checkpoints (JSON) to ensure seamless handoffs between sessions.

## Directory Structure

```
.claude-sessions/
├── checkpoints/          # JSON checkpoint files
│   └── checkpoint-YYYYMMDD-HHMMSS.json
├── logs/                 # Markdown session logs
│   └── session-YYYYMMDD-HHMMSS.md
└── README.md            # This file
```

## Key Components

### 1. Checkpoint Files (JSON)
**Location:** `.claude-sessions/checkpoints/`
**Format:** `checkpoint-YYYYMMDD-HHMMSS.json`
**Purpose:** Machine-readable snapshots of session state

**Structure:**
```json
{
  "session_id": "abc123",
  "timestamp": "2025-11-12T17:03:31",
  "started_at": "2025-11-12T16:00:00",
  "current_task": "Currently working on...",
  "completed_tasks": [...],
  "pending_tasks": [...],
  "decisions": [...],
  "file_changes": [...],
  "context": {...},
  "resume_points": [...],
  "problems_encountered": [...],
  "next_steps": [...]
}
```

### 2. Session Logs (Markdown)
**Location:** `.claude-sessions/logs/`
**Format:** `session-YYYYMMDD-HHMMSS.md`
**Purpose:** Human-readable session summaries

**Contents:**
- Session metadata (ID, start/end times)
- Completed and pending tasks
- Decisions made during the session
- File changes with descriptions
- Problems encountered
- Resume points for next session
- Next steps for continuation

### 3. Helper Scripts
Located in `../scripts/`:
- **session-logger.py** - Create checkpoints and logs programmatically
- **update-session-state.py** - Sync CLAUDE.md with checkpoints
- **resume-session.py** - Load and display session state
- **save-session.py** - **NEW!** Automatically collect session data (recommended)

### 4. save-session.py - Automated Session Capture

**The easiest way to save your session!** This script intelligently detects what happened during your work session:

**Features:**
- ✅ **Git Integration:** Detects file changes via `git status` and `git diff`
- ✅ **Directory Scanning:** Finds modified files based on timestamps (fallback if no git)
- ✅ **Smart Inference:** Auto-generates session description from your changes
- ✅ **Interactive Mode:** Prompts for additional details (problems, decisions, custom notes)
- ✅ **Quick Mode:** One-command save with all auto-detected data
- ✅ **Dry Run:** Preview what would be saved without creating files
- ✅ **Auto-Update:** Automatically updates CLAUDE.md after saving

**Quick Usage:**
```bash
# Quick save (auto-detects everything, no prompts)
python scripts/save-session.py --quick

# Interactive mode (prompts for details)
python scripts/save-session.py

# Preview without saving
python scripts/save-session.py --dry-run

# With custom description
python scripts/save-session.py --quick --description "Implemented dark mode feature"

# Look for changes in last 60 minutes only
python scripts/save-session.py --quick --since-minutes 60
```

**What It Detects:**
- File changes (created, modified, deleted)
- Work patterns (tests, documentation, code changes)
- Suggested session description
- Recommended resume points
- Suggested next steps

**Example Output:**
```
Collecting session data...
  Found 17 file change(s)
    - 5 from git
    - 17 from filesystem scan

Description: Work on Python development (8 files), documentation updates
Changes: 17 file(s)
Resume points: 2
Next steps: 3

SESSION SAVED SUCCESSFULLY
Checkpoint: .claude-sessions/checkpoints/checkpoint-20251113-075434.json
Log: .claude-sessions/logs/session-20251113-075434.md
```

**When to Use:**
- ⚡ **At session end:** Before closing Claude Code
- ⏰ **Context warning:** When Claude warns context is getting full
- 📸 **Milestone reached:** After completing major tasks
- 🔄 **Switching tasks:** Before changing to different work

## Quick Start

### Starting a New Session

1. **Check for previous work:**
   ```bash
   python scripts/resume-session.py
   ```

2. **Review CLAUDE.md:**
   The "Current Session State" section contains the latest status

3. **Start working:**
   Begin from documented resume points or ask user for clarification

### During a Session

Use the SessionLogger API in your Python code:

```python
from scripts.session_logger import SessionLogger

# Initialize logger
logger = SessionLogger()

# Start session
logger.start_session(
    "Implementing user authentication",
    context={"project": "api-docs", "phase": "development"}
)

# Add tasks
logger.add_task("Design auth flow", "completed")
logger.complete_task("Design auth flow", "Flow documented in auth.md")

logger.add_task("Implement JWT tokens", "in_progress")
logger.update_current_task("Implement JWT tokens")

logger.add_task("Write auth tests", "pending")

# Log decisions
logger.log_decision(
    question="Which JWT library to use?",
    decision="Use PyJWT",
    rationale="Most popular, well-maintained, simple API",
    alternatives=["python-jose", "authlib"]
)

# Log file changes
logger.log_file_change("src/auth/jwt.py", "created", "JWT token generation")
logger.log_file_change("src/auth/middleware.py", "modified", "Added JWT verification")

# Document problems
logger.add_problem("Token expiration not working correctly")

# Add resume points
logger.add_resume_point("Fix token expiration issue before continuing")
logger.add_resume_point("Continue with auth middleware implementation")

# Add next steps
logger.add_next_step("Fix token expiration bug")
logger.add_next_step("Implement refresh token logic")
logger.add_next_step("Write comprehensive auth tests")
```

### Ending a Session

1. **Create checkpoint:**
   ```python
   logger.end_session()
   ```
   This creates both JSON checkpoint and Markdown log

2. **Update CLAUDE.md:**
   ```bash
   python scripts/update-session-state.py update
   ```
   This syncs the "Current Session State" section with your latest checkpoint

3. **Verify handoff:**
   Check that:
   - Checkpoint file created in `checkpoints/`
   - Session log created in `logs/`
   - CLAUDE.md updated with current state
   - Resume points documented
   - Next steps listed

## Command Reference

### resume-session.py

```bash
# Display latest checkpoint
python scripts/resume-session.py

# List all checkpoints
python scripts/resume-session.py list

# Get concise summary
python scripts/resume-session.py summary

# Load specific session by ID
python scripts/resume-session.py abc123
```

### update-session-state.py

```bash
# Update CLAUDE.md from latest checkpoint
python scripts/update-session-state.py update

# Clear current session state
python scripts/update-session-state.py clear
```

### session-logger.py

```bash
# Run example session (for testing)
python scripts/session-logger.py

# Load latest checkpoint (programmatic)
python scripts/session-logger.py load
```

## Workflow Examples

### Example 1: Feature Implementation

**Session Start:**
```python
logger = SessionLogger()
logger.start_session("Implement dark mode toggle", context={"feature": "dark-mode"})
logger.add_task("Design toggle component", "pending")
logger.add_task("Add state management", "pending")
logger.add_task("Update existing components", "pending")
```

**During Work:**
```python
logger.complete_task("Design toggle component", "Component designed in Figma")
logger.log_file_change("src/components/DarkModeToggle.tsx", "created")

logger.update_current_task("Add state management")
logger.add_task("Add state management", "in_progress")
logger.log_decision(
    "Should we use Context API or Redux?",
    "Use Context API",
    "Feature is simple, Context is sufficient"
)
```

**Session End:**
```python
logger.add_resume_point("Continue with state management implementation")
logger.add_next_step("Complete Context API setup")
logger.add_next_step("Update all components to use theme context")
logger.end_session()
```

### Example 2: Bug Investigation

**Session Start:**
```python
logger = SessionLogger()
logger.start_session("Debug authentication timeout issue", context={"bug": "auth-timeout"})
logger.add_problem("Users getting logged out after 5 minutes")
```

**During Work:**
```python
logger.add_task("Check JWT expiration settings", "completed")
logger.complete_task("Check JWT expiration settings", "Found: exp set to 5min instead of 60min")

logger.log_decision(
    "Where to fix the expiration time?",
    "Update in config/auth.py",
    "Centralized configuration is best practice"
)

logger.log_file_change("config/auth.py", "modified", "Changed JWT_EXPIRATION to 60min")
```

**Session End:**
```python
logger.add_resume_point("Test the fix in staging environment")
logger.add_next_step("Deploy to staging")
logger.add_next_step("Verify users stay logged in for 60 minutes")
logger.end_session()
```

## Best Practices

### 1. Checkpoint Frequency
- **Always** create checkpoint before context window closes
- Create checkpoints at major milestones
- Create checkpoints when switching between major tasks
- Create checkpoints after important decisions

### 2. Documentation Quality
- Write clear, descriptive task names
- Include rationale for all decisions
- Document alternatives considered
- Note problems immediately when encountered
- Be specific with resume points

### 3. File Change Tracking
- Log all significant file modifications
- Include brief description of what changed
- Use appropriate action: created, modified, deleted
- Track configuration changes especially

### 4. Context Preservation
- Include relevant project context in session start
- Document assumptions made during work
- Link to related issues/PRs when applicable
- Note any external dependencies

### 5. Handoff Clarity
- Resume points should be actionable
- Next steps should be specific and ordered
- Document blockers clearly
- Include any required information for continuation

## Integration with CLAUDE.md

The session continuity system integrates with the root CLAUDE.md file:

1. **Current Session State** section is auto-updated from checkpoints
2. **Decision Log** section accumulates decisions over time
3. **Session Continuity Protocol** provides instructions for Claude

### Updating CLAUDE.md

After ending a session:
```bash
python scripts/update-session-state.py update
```

This will:
- Update "Current Session State" with latest checkpoint data
- Append new decisions to "Decision Log"
- Maintain session history

### Clearing Session State

When starting completely fresh:
```bash
python scripts/update-session-state.py clear
```

## Troubleshooting

### No checkpoints found
- Run `session-logger.py` to create your first checkpoint
- Verify `.claude-sessions/checkpoints/` directory exists

### Encoding errors on Windows
- The scripts automatically disable rich output on Windows
- If you see encoding errors, update to latest version of scripts

### Cannot load checkpoint
- Verify JSON file is valid with: `python -m json.tool checkpoint.json`
- Check file permissions

### CLAUDE.md not updating
- Ensure CLAUDE.md exists in root directory
- Check that checkpoint files exist
- Verify Python script has write permissions

## File Retention

- Keep all checkpoint and log files for audit trail
- Consider archiving older files after 30-90 days
- Never delete files manually; use a proper archiving system
- Checkpoint files are small (typically < 10KB each)

## Advanced Usage

### Custom Session Logger

```python
from scripts.session_logger import SessionLogger

class MyProjectLogger(SessionLogger):
    def __init__(self):
        super().__init__(base_dir="/path/to/project")
        # Add custom initialization

    def log_api_change(self, endpoint, change_type, description):
        """Custom method for API changes"""
        self.log_file_change(
            f"api/{endpoint}.py",
            change_type,
            f"API: {description}"
        )
        self.context['api_changes'] = self.context.get('api_changes', 0) + 1
```

### Programmatic Checkpoint Loading

```python
from scripts.session_logger import SessionLogger

# Load latest
checkpoint = SessionLogger.load_latest_checkpoint()

if checkpoint:
    print(f"Last session: {checkpoint.session_id}")
    print(f"Resume from: {checkpoint.resume_points}")

    # Continue work
    logger = SessionLogger()
    logger.session_id = checkpoint.session_id + "-continued"
    logger.context = checkpoint.context
    # ... continue work
```

## Support

For issues or questions:
1. Check this README for common solutions
2. Review example usage in the scripts
3. Consult the Session Continuity Protocol in CLAUDE.md
4. Test with the example session: `python scripts/session-logger.py`

## Version History

- **v1.0** (2025-11-12): Initial implementation
  - Session logging with JSON checkpoints
  - Markdown session logs
  - CLAUDE.md integration
  - Resume session capability
  - Windows compatibility fixes
