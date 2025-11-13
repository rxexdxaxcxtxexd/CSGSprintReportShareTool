# Context Tracking & Memory Management UX - Proof of Concept

> **Seamless session continuity for Claude Code** - Never lose context again!

## 🎯 Overview

This POC demonstrates an automated system for maintaining context and progress across Claude Code sessions. When working with AI assistants, context is lost between sessions. This system solves that problem with intelligent session tracking, automated checkpointing, and seamless resumption.

## ✨ Key Features

- 🤖 **Proactive AI Tracking** - Claude automatically asks to track substantial work and logs progress
- 💾 **Automated Session Capture** - One command saves everything: file changes, decisions, next steps
- 🔍 **Smart Detection** - Git integration + filesystem scanning detects all your work automatically
- 📊 **Hybrid Format** - Human-readable Markdown logs + machine-readable JSON checkpoints
- 🔄 **Seamless Resumption** - Start new sessions with full context from previous work
- ⚠️ **Context Awareness** - Warns when context window fills up (75%, 87%, 95%)
- 📝 **Decision Logging** - Tracks architectural decisions with rationale and alternatives

## 🚀 Quick Start

### 1. Save Your Current Session (Easiest!)

Before closing Claude Code, run:

```bash
python scripts/save-session.py --quick
```

This automatically:
- ✅ Detects all file changes (git + filesystem)
- ✅ Generates session description
- ✅ Suggests resume points and next steps
- ✅ Creates checkpoint + log files
- ✅ Updates CLAUDE.md

### 2. Resume in New Session

When you start a new Claude Code session:

```bash
python scripts/resume-session.py
```

This displays:
- Previous session summary
- What was completed
- Where to resume
- Next steps to take

### 3. Let Claude Track Automatically

When you ask Claude to do substantial work, it will ask:
> *"Would you like me to track this session for continuity?"*

Say **yes**, and Claude will automatically log:
- Tasks as completed
- Decisions as made
- File changes as they happen
- Problems encountered

## 📁 Project Structure

```
context-tracking-memory/
├── CLAUDE.md                      # Project memory & Claude instructions
├── README.md                      # This file
├── .claude-sessions/
│   ├── README.md                  # Comprehensive usage guide
│   ├── checkpoints/               # JSON session checkpoints
│   └── logs/                      # Markdown session logs
└── scripts/
    ├── session-logger.py          # Core logging functionality
    ├── save-session.py            # Automated session capture (⭐ main tool)
    ├── update-session-state.py    # Sync CLAUDE.md with checkpoints
    └── resume-session.py          # Load and display session state
```

## 🛠️ Core Tools

### save-session.py - Automated Session Capture

**The main tool you'll use!**

```bash
# Quick save (recommended)
python scripts/save-session.py --quick

# Interactive mode (prompts for details)
python scripts/save-session.py

# Preview without saving
python scripts/save-session.py --dry-run

# Custom description
python scripts/save-session.py --quick --description "Implemented auth system"

# Recent changes only (last 60 minutes)
python scripts/save-session.py --quick --since-minutes 60
```

**What it detects:**
- File changes via git (if available)
- File modifications by timestamp (fallback)
- Work patterns (tests, docs, code)
- Suggested session description
- Recommended resume points
- Suggested next steps

### resume-session.py - Load Session State

```bash
# Show latest checkpoint
python scripts/resume-session.py

# List all checkpoints
python scripts/resume-session.py list

# Show specific session
python scripts/resume-session.py <session-id>

# Quick summary
python scripts/resume-session.py summary
```

### update-session-state.py - Sync CLAUDE.md

```bash
# Update CLAUDE.md from latest checkpoint
python scripts/update-session-state.py update

# Clear current session state
python scripts/update-session-state.py clear
```

## 💡 How It Works

### Session Capture

1. **Git Integration**: Detects staged/unstaged changes via `git status` and `git diff`
2. **Filesystem Scanning**: Finds modified files in last N minutes (default: 240)
3. **Pattern Recognition**: Analyzes changes to infer what you were working on
4. **Smart Suggestions**: Generates resume points and next steps

### Session Resumption

1. **CLAUDE.md Auto-Load**: Project instructions load automatically in new sessions
2. **Checkpoint Display**: Run `resume-session.py` to see full context
3. **Seamless Continuation**: Pick up exactly where you left off

### Claude Integration

Claude is instructed to:
- Ask about tracking at session start (for substantial work)
- Log progress automatically when tracking is enabled
- Warn when context window fills (75%, 87%, 95%)
- Offer to create checkpoints when significant work is completed

## 📋 Example Workflow

### Day 1 - Implementing a Feature

```bash
# User asks Claude: "Help me implement dark mode"
# Claude asks: "Would you like me to track this session?"
# User: "Yes"

# ... Claude works and logs progress automatically ...
# Claude: "✓ Task completed: Design toggle component"
# Claude: "✓ Decision logged: Use Context API for state"

# Context approaching 87% full
# Claude: "⚠️ Context window is 87% full. Shall I create a checkpoint?"

# At end of session
$ python scripts/save-session.py --quick
```

**Output:**
```
SESSION SAVED SUCCESSFULLY
Checkpoint: .claude-sessions/checkpoints/checkpoint-20251113-143022.json
Log: .claude-sessions/logs/session-20251113-143022.md

To resume in a new session:
  python scripts/resume-session.py
```

### Day 2 - Resuming Work

```bash
# Start new Claude Code session
$ python scripts/resume-session.py
```

**Output:**
```
============================================================
SESSION CHECKPOINT: a8f3d912
============================================================
Started: 2025-11-13T14:30:22

[CURRENT TASK]
  Implement dark mode state management

[COMPLETED TASKS] (3)
  + Design toggle component
  + Create DarkModeContext
  + Update app wrapper

[DECISIONS MADE] (1)
  Q: Should we use Context API or Redux?
  A: Use Context API
     Feature is simple, Context is sufficient

------------------------------------------------------------
[RESUME POINTS]
------------------------------------------------------------
1. Continue with state management implementation
2. Update existing components to use theme context

------------------------------------------------------------
[NEXT STEPS]
------------------------------------------------------------
[ ] Complete Context API setup
[ ] Test dark mode in all components
```

## 🎓 Best Practices

### When to Save Sessions

- ⚡ **At session end**: Always run `save-session.py` before closing
- ⏰ **Context warnings**: When Claude warns context is filling
- 📸 **Milestones**: After completing major tasks
- 🔄 **Task switching**: Before changing to different work

### What Gets Tracked

**Automatically by save-session.py:**
- All file changes (created, modified, deleted)
- Session description (inferred from patterns)
- Resume points (suggested from work)
- Next steps (recommended actions)

**When Claude tracking is enabled:**
- Tasks as completed
- Decisions as made
- File changes with descriptions
- Problems encountered
- Custom resume points and next steps

### Session Hygiene

- Create checkpoints at logical stopping points
- Use descriptive session descriptions
- Add custom resume points for complex work
- Document blockers in "problems"
- Log important decisions with rationale

## 🔧 Configuration

### Excluded Directories

The system automatically excludes:
- `.git`, `.claude-sessions`, `__pycache__`
- `node_modules`, `.venv`, `venv`
- `.pytest_cache`, `.mypy_cache`
- `dist`, `build`, `.eggs`

### Scan Limits

To prevent excessive scanning:
- Max depth: 3 levels
- Max files: 100 per scan
- Default time window: 240 minutes (4 hours)

Adjust with `--since-minutes` flag:
```bash
python scripts/save-session.py --quick --since-minutes 60  # Last hour only
```

## 📚 Documentation

- **CLAUDE.md**: Complete project memory and Claude instructions
- **.claude-sessions/README.md**: Comprehensive usage guide with examples
- **This README**: Quick start and overview

## 🤝 Contributing

This is a proof of concept. Areas for enhancement:

- [ ] Integration with Claude Code's internal todo system
- [ ] Real-time checkpoint creation (not just end of session)
- [ ] Automatic commit message generation from checkpoints
- [ ] Multi-project support
- [ ] Session analytics and insights
- [ ] Web UI for browsing checkpoints

## 📜 License

MIT License - Use freely for your projects!

## 🙏 Acknowledgments

Built with Claude Code - demonstrating how AI-assisted development can maintain its own context across sessions.

---

**Never lose context again!** 🎉

For issues or questions, see the comprehensive documentation in `.claude-sessions/README.md`
