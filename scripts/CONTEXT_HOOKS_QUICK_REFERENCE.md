# Context Hooks - Quick Reference

## One-Line Summary
Automatic task tracking for Claude Code through intelligent tool execution monitoring.

## Installation
```bash
# Already installed at:
C:\Users\layden\scripts\context_hooks.py

# Dependencies (already available):
- task_stack.py
- session_state_manager.py
- mode_detector.py
```

## Quick Commands

```bash
# Check status
python scripts/context_hooks.py status

# Test TodoWrite integration
python scripts/context_hooks.py test-todo

# Test auto-save
python scripts/context_hooks.py test-autosave

# Prepare before context compression
python scripts/context_hooks.py prepare-compact

# Monitor loop (testing, 60 seconds)
python scripts/context_hooks.py monitor
```

## Auto-Save Thresholds

| Mode  | Tools | Time    |
|-------|-------|---------|
| Task  | 10    | 15 min  |
| Mixed | 15    | 20 min  |
| File  | 20    | 30 min  |

## Tool Categories

- **File Tools**: Edit, Write, NotebookEdit
- **Task Tools**: Read, Grep, Glob, WebFetch, WebSearch, Task
- **Neutral**: Bash, TodoWrite, AskUserQuestion

## Key Classes & Methods

### ToolMonitor
```python
from context_hooks import ToolMonitor

monitor = ToolMonitor()

# Track tool execution
monitor.on_tool_executed("Read", success=True)

# Process TodoWrite
monitor.on_todo_write([{
    "status": "in_progress",
    "content": "My current task"
}])

# Check if auto-save needed
if monitor.should_auto_save():
    # Save triggered automatically

# Detect context switches
switch = monitor.detect_context_switch()

# Prepare for compact
monitor.prepare_for_compact()
```

## Configuration

Edit `context_hooks.py` constants:

```python
# Tool thresholds
AUTOSAVE_TASK_MODE = 10    # Change for task mode
AUTOSAVE_MIXED_MODE = 15   # Change for mixed mode
AUTOSAVE_FILE_MODE = 20    # Change for file mode

# Time thresholds (minutes)
AUTOSAVE_TIME_TASK = 15
AUTOSAVE_TIME_MIXED = 20
AUTOSAVE_TIME_FILE = 30
```

## Integration Status

- ✅ CLI commands working
- ⏳ Hook integration (awaiting Claude Code support)
- ✅ TaskStack integration
- ✅ SessionState integration
- ✅ ModeDetector integration

## Common Workflows

### Check Current State
```bash
python scripts/context_hooks.py status
```

### Before Ending Session
```bash
python scripts/context_hooks.py prepare-compact
```

### Test TodoWrite
```bash
python scripts/context_hooks.py test-todo
# Verifies task extraction from todos
```

## Troubleshooting

### Auto-save not triggering
```bash
# Check status to see thresholds
python scripts/context_hooks.py status

# Look at:
# - tools_since_save (compare to threshold for mode)
# - time_since_save_minutes
```

### TodoWrite not updating
- Ensure todo has `status: "in_progress"`
- Only in_progress tasks are tracked as current

### Import errors
- Verify all files in same directory:
  - context_hooks.py
  - task_stack.py
  - session_state_manager.py
  - mode_detector.py

## Files Created

```
C:\Users\layden\scripts\
├── context_hooks.py                          # Main (513 lines)
├── CONTEXT_HOOKS_INTEGRATION.md              # Full guide
└── CONTEXT_HOOKS_QUICK_REFERENCE.md          # This file

C:\Users\layden\
└── CONTEXT_HOOKS_IMPLEMENTATION_SUMMARY.md   # Summary
```

## Performance

- **Overhead**: 2-3ms per tool (negligible)
- **Memory**: ~10 KB (50 tool history)
- **Storage**: ~15 KB (task + session state)

## Related Commands

```bash
# Task Stack
python scripts/task_stack.py show

# Session State
python scripts/session_state_manager.py show

# Mode Detection
python scripts/mode_detector.py analyze
```

## Documentation

- **Integration Guide**: `CONTEXT_HOOKS_INTEGRATION.md`
- **Implementation Summary**: `CONTEXT_HOOKS_IMPLEMENTATION_SUMMARY.md`
- **Project Memory**: `CLAUDE.md`
- **Session Protocol**: `SESSION_PROTOCOL.md`

## Support

1. Check status: `python scripts/context_hooks.py status`
2. Review logs: Look for INFO/WARNING messages
3. Verify state files: `~/.claude-sessions/task-stack.json`
4. Read integration guide: `CONTEXT_HOOKS_INTEGRATION.md`
