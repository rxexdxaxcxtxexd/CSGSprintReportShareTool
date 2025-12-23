# Session Continuity Protocol

> **For Claude Code Reference** - Comprehensive instructions for session tracking and continuity

---

## Instructions for Claude Code

**IMPORTANT:** These instructions are for Claude to follow during sessions. Read and follow these at session start.

### Session Start Protocol

**When user requests substantial work:**
1. **Ask**: "Would you like me to track this session for continuity?"
2. **If yes**: Initialize SessionLogger and track progress automatically
3. **If no**: Proceed without session tracking

**What qualifies as "substantial work":**
- Multiple related tasks (3+ steps)
- Feature implementation or refactoring
- Debugging investigations requiring multiple attempts
- Architecture decisions
- Work spanning multiple files
- Any work that would benefit from resuming later

**What does NOT need tracking:**
- Simple one-off questions
- Single file edits
- Quick information lookups
- Trivial bug fixes
- Explanatory responses

### During Work (When Tracking Enabled)

**1. Initialize logger at start:**
```python
# Import and initialize
import sys, os, importlib.util
spec = importlib.util.spec_from_file_location("session_logger",
    os.path.join(os.path.dirname(__file__), "scripts/session-logger.py"))
session_logger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session_logger)
logger = session_logger.SessionLogger()

# Start session with description
logger.start_session("Feature: Dark mode toggle", context={
    "project": "api-documentation-agent",
    "type": "feature",
    "priority": "high"
})
```

**2. Log as you work:**
- `logger.add_task("Task description", "pending")` - When starting new tasks
- `logger.update_current_task("Task description")` - When switching tasks
- `logger.complete_task("Task description", "Notes")` - When finishing
- `logger.log_decision(question, decision, rationale, alternatives)` - For architectural choices
- `logger.log_file_change(file_path, action, description)` - After file modifications
- `logger.add_problem("Problem description")` - When encountering blockers

**3. Provide visibility:**
Show user progress markers like "✓ Task completed: Design toggle component"

### Session End Protocol

**If significant work was completed** (4+ tasks, important decisions, or multiple files changed):

1. **Remind user:**
   - "I've completed [X] tasks with [Y] key decisions. Shall I create a session checkpoint?"

2. **If user agrees, run end-of-session sequence:**
```python
# Add resume points
logger.add_resume_point("Continue with state management implementation")
logger.add_resume_point("Update existing components to use theme context")

# Add next steps
logger.add_next_step("Complete Context API setup")
logger.add_next_step("Test dark mode in all components")

# End session (creates checkpoint and log)
logger.end_session()
```

3. **Suggest automated collection:**
   - "You can also run `python scripts/checkpoint.py --quick` to capture any details I may have missed"

### Context Window Awareness

**Monitor context usage and warn proactively:**

- **At ~150K tokens (75% full):**
  - "ℹ️ Context window is 75% full. Consider checkpointing soon to preserve our work."

- **At ~175K tokens (87% full):**
  - "⚠️ Context window is 87% full. I recommend creating a checkpoint now before we lose context."
  - Offer: "Shall I create a checkpoint of our progress?"

- **At ~190K tokens (95% full):**
  - "🚨 Context window is 95% full. Please run `python scripts/checkpoint.py --quick` immediately to preserve work."
  - "We should start a fresh session after checkpointing."

**Recommended user action:**
1. Run: `python scripts/checkpoint.py --quick` (unified checkpoint command)
2. Start fresh Claude Code session
3. Resume with: `python scripts/resume-session.py`

### Best Practices

1. **Be proactive but not intrusive:**
   - Ask about tracking once at start
   - Don't repeatedly ask or mention it during work
   - Remind about checkpointing when appropriate

2. **Provide clear markers:**
   - Show completed task notifications
   - Mention when decisions are logged
   - Summarize progress at end

3. **Respect user preferences:**
   - If user declines tracking, don't bring it up again
   - If user wants minimal interruption, track silently
   - If user wants visibility, provide status updates

---

## Session Continuity Details

**Purpose:** Maintain context and progress across Claude Code sessions.

### For Claude at Session Start
1. **Read CLAUDE.md first** (automatically loaded via project instructions)
2. **Check for checkpoints:** Run `python scripts/resume-session.py` to see latest session state
3. **Review Current Session State** in CLAUDE.md for active work
4. **Confirm with user** which resume point to continue from
5. **Update session state** as work progresses

### For Claude at Session End
1. **Create checkpoint:** Use `checkpoint.py` to save progress
2. **Update CLAUDE.md:** Automatically synced by checkpoint script
3. **Document resume points:** Clearly state where next session should continue
4. **Log decisions:** Record any architectural or implementation choices made
5. **List next steps:** Provide clear continuation path

### Session Handoff Checklist
- [ ] Checkpoint file created (`.claude-sessions/checkpoints/`)
- [ ] Session log written (`.claude-sessions/logs/`)
- [ ] CLAUDE.md Current Session State updated
- [ ] Resume points documented
- [ ] Next steps listed
- [ ] Decisions logged
- [ ] File changes recorded

---

## Integration Map

### Project Structure
This repository has **two layers**:

#### 1. Root Directory (`C:\Users\layden\`)
**Purpose:** Project memory, planning, and session continuity
**Key Files:**
- `CLAUDE.md` - Project memory with current session state
- `SESSION_PROTOCOL.md` - This file, comprehensive instructions
- `.claude-sessions/` - Session logs and checkpoints
- `scripts/` - Helper scripts for session management
  - `checkpoint.py` - **Unified checkpoint command** (use this!)
  - `session-logger.py` - Create session logs and checkpoints
  - `update-session-state.py` - Sync CLAUDE.md with checkpoints
  - `resume-session.py` - Load and display session state
  - `context-monitor.py` - Monitor context window usage
  - `auto-checkpoint-daemon.py` - Background monitoring (optional)

#### 2. Projects Directory (`C:\Users\layden\Projects\api-documentation-agent\`)
**Purpose:** Full implementation of the API documentation system
**Status:** Fully implemented and production-ready
**Key Components:**
- `backend/` - FastAPI application with WebSocket support
- `frontend/` - React + TypeScript dashboard
- `src/core/` - Pipeline and progress tracking implementation
- `docker/` - Containerization configurations
- `monitoring/` - Prometheus + Grafana setup

### When to Use Which
- **CLAUDE.md:** Check current session state and recent decisions
- **SESSION_PROTOCOL.md:** Reference for session tracking procedures
- **Projects directory:** For implementation details and running the application

---

## Architecture Principles
- **Hybrid Approach**: Combine AI efficiency with traditional tool reliability
- **Modularity**: Each tool serves a specific purpose with clear interfaces
- **Quality Gates**: Automated validation at every step
- **Scalability**: Design for enterprise deployment patterns
- **Session Continuity**: Maintain context across Claude Code sessions

---

## Tool Stack Configuration

### Primary Tools (Phase 1)
- **OpenAPI Generator**: SDK and client library generation
- **Redoc**: Interactive API documentation
- **Schemathesis**: Property-based API testing
- **Step CI**: Declarative integration testing

### Secondary Tools (Phase 2)
- **Kiota**: Strongly-typed client generation
- **RESTler**: Advanced stateful API fuzzing
- **Microcks**: Service virtualization and contract testing

### Session Management Tools
- **checkpoint.py**: **Unified checkpoint command** (recommended)
- **session-logger.py**: Create session checkpoints and logs programmatically
- **update-session-state.py**: Sync CLAUDE.md with session progress
- **resume-session.py**: Load and display previous session state
- **context-monitor.py**: Check context window usage
- **auto-checkpoint-daemon.py**: Background monitoring and auto-checkpoint

---

## Key Workflows

### Documentation Generation
1. Validate OpenAPI specification
2. Generate interactive docs with Redoc
3. Create SDK clients with OpenAPI Generator
4. Run property-based tests with Schemathesis
5. Execute integration tests with Step CI
6. Package and deploy artifacts

### Session Continuity Workflow
1. **Session Start:**
   - Check latest checkpoint with `resume-session.py`
   - Review Current Session State in CLAUDE.md
   - Confirm continuation point with user

2. **During Session:**
   - Log progress using `session-logger.py` APIs (if tracking enabled)
   - Update Current Session State as work progresses
   - Document decisions in Decision Log

3. **Session End:**
   - Run `python scripts/checkpoint.py --quick` (one command!)
   - Verify checkpoint created successfully
   - Note resume points for next session

### Quality Assurance
- Specification validation before processing
- Generated code quality checks
- Security vulnerability scanning
- Performance benchmarking
- Documentation accuracy verification

---

## Common Commands

### API Documentation Commands
- `generate full-docs from specs/api.yaml` - Complete documentation pipeline
- `create python-sdk from specs/api.yaml` - Generate Python SDK
- `run api-tests against https://api.example.com` - Execute test suite
- `validate spec specs/api.yaml` - Check OpenAPI specification
- `deploy docs to staging` - Deploy documentation

### Session Management Commands
```bash
# PRIMARY COMMAND: Unified checkpoint (recommended)
python scripts/checkpoint.py --quick

# With custom description
python scripts/checkpoint.py --quick --description "Implemented auth system"

# Preview without saving
python scripts/checkpoint.py --dry-run

# Resume from last session
python scripts/resume-session.py

# List all checkpoints
python scripts/resume-session.py list

# Get quick summary
python scripts/resume-session.py summary

# Check context window usage
python scripts/context-monitor.py

# Check memory trigger status
python scripts/memory_trigger.py --stats

# Test memory triggers (no MCP calls)
python scripts/memory_trigger.py --prompt "test query" --test

# Start background monitoring (optional)
python scripts/auto-checkpoint-daemon.py &

# Manual commands (for advanced users)
python scripts/save-session.py --quick
python scripts/update-session-state.py update

# Example: Using session logger in Python
from scripts.session_logger import SessionLogger
logger = SessionLogger()
logger.start_session("Working on feature X")
logger.add_task("Implement feature", "in_progress")
logger.log_decision("Question?", "Answer", "Rationale")
logger.end_session()
```

---

## Common Resumption Scenarios

### Scenario 1: Continuing Implementation Work
**Context:** You were implementing a feature when the session ended
**Resume Steps:**
1. Run `python scripts/resume-session.py` to see what was being worked on
2. Review the "Current Task" and "Recent Changes"
3. Check "Problems Encountered" for any blockers
4. Continue from the documented resume point
5. Update session state as you progress

### Scenario 2: Starting New Feature
**Context:** Beginning work on a new feature or task
**Resume Steps:**
1. Review Decision Log for relevant past decisions
2. Check Integration Map to understand project structure
3. Create new session with `session-logger.py` (if tracking)
4. Document your plan and start implementation
5. Log decisions as you make architectural choices

### Scenario 3: Debugging Issues
**Context:** Investigating problems or bugs
**Resume Steps:**
1. Check "Problems Encountered" in latest checkpoint
2. Review relevant file changes to understand recent modifications
3. Use Decision Log to understand why things were implemented a certain way
4. Document findings and solutions as you debug
5. Update session with problem resolution

### Scenario 4: Long Break Return
**Context:** Returning after days/weeks away from the project
**Resume Steps:**
1. Read CLAUDE.md to refresh context
2. Run `python scripts/resume-session.py list` to see recent sessions
3. Review Decision Log to understand recent choices
4. Check Current Session State for active work
5. Ask user for clarification on priorities before continuing

---

## Standards and Guidelines
- All OpenAPI specs must be valid OpenAPI 3.0+
- Generated SDKs must include comprehensive examples
- Documentation must be accessible and responsive
- Tests must achieve >90% code coverage
- All outputs must pass security scans
- **Session Continuity:** Always create checkpoints before context window closes
- **Decision Documentation:** Log all architectural and implementation decisions
- **Progress Tracking:** Update Current Session State regularly

---

## Error Handling
- Invalid specs should be rejected with clear error messages
- Failed generations should not corrupt existing artifacts
- All operations should be reversible
- Detailed logging for debugging and auditing
- **Session Recovery:** Checkpoints enable recovery from interruptions
- **State Consistency:** Always sync CLAUDE.md with checkpoint data

---

## Development Guidelines
- Use TypeScript for Node.js components
- Use Python 3.9+ for processing scripts
- Follow OpenAPI specification best practices
- Implement comprehensive error handling
- Include detailed documentation for all modules
- **Session Management:** Use `checkpoint.py` for easy checkpointing
- **Context Preservation:** Document decisions and rationale clearly
- **Checkpoint Frequency:** Create checkpoints at major milestones and session ends

---

## Automated Session Continuity

### Overview
The session continuity system supports full automation via Claude Code hooks, eliminating manual checkpoint/resume steps.

### Quick Setup (Recommended)
```bash
# Run automated setup
.\scripts\setup-automation.ps1

# Optional: Add Task Scheduler safety net
.\scripts\setup-task-scheduler.ps1
```

### How It Works
Claude Code hooks trigger automatically on session lifecycle events:

**SessionStart Hook:**
- Triggers when: Claude Code starts, resumes, or clears
- Action: Runs `python scripts/resume-session.py summary`
- Shows: Previous session summary and resume points
- Timeout: 30 seconds

**SessionEnd Hook:**
- Triggers when: Claude Code exits cleanly (Ctrl+D, /exit, logout)
- Action: Runs `python scripts/checkpoint.py --quick`
- Creates: Checkpoint + log files
- Updates: CLAUDE.md with session state
- Timeout: 60 seconds

### Configuration
Hooks are configured in `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python scripts/resume-session.py summary",
            "timeout": 30000
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python scripts/checkpoint.py --quick",
            "timeout": 60000
          }
        ]
      }
    ]
  }
}
```

### Installation Locations
- **Project-local:** `<project>/.claude/settings.json` (recommended, checked into git)
- **Global:** `~/.claude/settings.json` (applies to all Claude Code sessions)

### Task Scheduler Safety Net (Optional)
For comprehensive coverage including crashes:

```powershell
# Set up periodic checkpoints every 30 minutes
.\scripts\setup-task-scheduler.ps1

# Or manually:
$action = New-ScheduledTaskAction -Execute "python.exe" `
    -Argument "C:\Users\layden\scripts\checkpoint.py --quick"

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 30) `
    -RepetitionDuration ([TimeSpan]::MaxValue)

Register-ScheduledTask -TaskName "ClaudePeriodicCheckpoint" `
    -Action $action -Trigger $trigger
```

### What Gets Automated
✅ **Automatic on Session Start:**
- Load previous session state
- Display resume points
- Show completed/pending tasks
- Display session summary

✅ **Automatic on Session End:**
- Detect session boundaries (via history.jsonl gaps)
- Collect file changes (git + filesystem)
- Generate smart resume points (AST analysis + TODO detection)
- Validate checkpoint structure
- Update CLAUDE.md
- Create checkpoint + log files

✅ **Optional Periodic Safety:**
- Task Scheduler checkpoints every 30 minutes
- Catches crashes and forced terminations
- Independent of Claude Code state

### Troubleshooting

**Hooks not running:**
1. Check `.claude/settings.json` exists and is valid JSON
2. Verify Python scripts are executable: `python scripts/checkpoint.py --dry-run`
3. Check timeout values (may need to increase for large sessions)
4. Review Claude Code logs for hook errors

**SessionEnd not triggering:**
- Only fires on *clean* exits (Ctrl+D, /exit, logout, clear)
- Crashes and force-kills bypass SessionEnd hook
- Solution: Use Task Scheduler safety net for crash coverage

**Paths not working:**
- Use absolute paths if relative paths fail
- Windows: Escape backslashes in JSON (`C:\\Users\\...`)
- Or use forward slashes (`C:/Users/...`)

**Timeout errors:**
- Default: SessionStart = 30s, SessionEnd = 60s
- Increase if needed: `"timeout": 120000` (2 minutes)
- Large sessions may need longer timeouts

### Testing Automation
```bash
# Test hooks manually
python scripts/resume-session.py summary
python scripts/checkpoint.py --quick

# Test with actual Claude session
1. Start Claude Code → Should show resume summary
2. Do some work
3. Exit cleanly (Ctrl+D or /exit) → Should create checkpoint

# Verify checkpoint created
ls ~/.claude-sessions/checkpoints/
cat CLAUDE.md  # Should show updated session state
```

### Benefits of Automation
- **Zero user friction** - No manual commands to remember
- **Consistent checkpoints** - Never forget to save session
- **Smart resume** - Always know where to continue
- **Crash protection** - Task Scheduler catches edge cases
- **Context preservation** - Automatic session continuity
- **95%+ reliability** - Hooks + Task Scheduler cover nearly all scenarios

---

## Memory Trigger System

The Context-Aware Memory Trigger System automatically queries the MCP memory graph when relevant context is needed, enhancing session continuity.

### How It Works

The system uses 4 intelligent detectors that trigger on specific conditions:

1. **Project Switch Detector** (Priority 1)
   - Triggers when: Switching git repositories or branches
   - Loads: Project decisions, architecture patterns, design rationale
   - Token cost: ~200 tokens

2. **Keyword Detector** (Priority 2)
   - Triggers when: Phrases like "remember", "why did we", "decided"
   - Loads: Relevant past decisions and context
   - Token cost: ~150 tokens

3. **Entity Mention Detector** (Priority 3)
   - Triggers when: Known entities (files, classes, modules) are mentioned
   - Loads: Entity details and relationships
   - Token cost: ~100 tokens

4. **Token Threshold Detector** (Priority 4)
   - Triggers when: Context usage reaches 100K or 150K tokens
   - Loads: Pending decisions, incomplete tasks
   - Token cost: ~175 tokens

### Integration Points

**Checkpoint Workflow**: Memory extraction runs automatically during `checkpoint.py --quick` (Step 2.5)

**Context Monitor**: Memory suggestions appear when token usage reaches warning/critical levels

**Token Budget**: Maximum 5,000 tokens per session (~2.5% of context window)

### Commands

```bash
# Check trigger statistics
python scripts/memory_trigger.py --stats

# Test triggers (no MCP calls)
python scripts/memory_trigger.py --prompt "test" --test

# Manual trigger
python scripts/memory_trigger.py --prompt "remember our decision"
```

### Configuration

**File**: `.claude/memory-trigger-config.json`

Enable/disable detectors, adjust priorities, configure cache settings.

### Troubleshooting

**No detectors registered**: Check configuration file exists at `.claude/memory-trigger-config.json`

**MCP unavailable**: System degrades gracefully - operations continue without memory queries

**High token usage**: Adjust `max_tokens_per_session` in configuration (default: 5000)

---

## CI/CD Integration
- GitHub Actions for automation
- Docker containers for consistent environments
- Automated testing on pull requests
- Staging deployments for validation
- Production deployments with approval gates
- **Session Logs:** Consider integrating checkpoint creation into CI/CD pipelines
- **Audit Trail:** Use session logs for compliance and debugging
