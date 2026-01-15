# Context Hooks - Integration Guide

## Overview

`context_hooks.py` provides automatic task tracking by monitoring tool execution in Claude Code sessions. It eliminates manual state management by:

- Auto-detecting TodoWrite tasks and updating task stack
- Triggering auto-saves based on workflow mode
- Detecting context switches from tool patterns
- Preparing state before context window compression

## Architecture

```
┌─────────────────────────────────────────────────┐
│          Claude Code Tool Execution             │
└───────────────┬─────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────┐
│          ToolMonitor (context_hooks.py)         │
│                                                  │
│  • Tracks tool history (last 50 tools)          │
│  • Detects workflow mode                        │
│  • Triggers auto-save based on thresholds       │
│  • Logs context switches                        │
└───┬────────────────┬──────────────────┬─────────┘
    │                │                  │
    ▼                ▼                  ▼
┌─────────┐   ┌──────────────┐   ┌────────────┐
│TaskStack│   │SessionState  │   │ModeDetector│
│         │   │              │   │            │
│task-    │   │session-      │   │Analyzes    │
│stack    │   │state.json    │   │patterns    │
│.json    │   │              │   │            │
└─────────┘   └──────────────┘   └────────────┘
```

## Components

### ToolMonitor Class

**Purpose**: Central hub for monitoring tool execution and triggering state updates

**Key Methods**:
- `on_tool_executed(tool_name, success, metadata)` - Called after each tool
- `on_todo_write(todos)` - Processes TodoWrite tool, extracts current task
- `should_auto_save()` - Checks if auto-save threshold reached
- `detect_context_switch()` - Identifies workflow pattern changes
- `prepare_for_compact()` - Saves all state before context compression

### Auto-Save Thresholds

Based on detected workflow mode:

| Mode | Tools Since Save | Time Since Save |
|------|-----------------|-----------------|
| Task | 10 tools        | 15 minutes      |
| Mixed| 15 tools        | 20 minutes      |
| File | 20 tools        | 30 minutes      |

**Rationale**: Task mode has frequent changes requiring more frequent saves. File mode is commit-based, so less frequent saves are acceptable.

### Context Switch Detection

Compares two windows of 10 tools each:
- Calculates tool category distribution (file/task/neutral)
- Detects shifts >30% between windows
- Logs switch to session state
- Triggers auto-save

**Example**:
```
Previous window: 80% Read/Grep (task tools)
Recent window:   70% Edit/Write (file tools)
→ Context switch detected: "Investigation" → "Coding"
```

## Integration with Claude Code

### Method 1: Hook Configuration (Recommended)

Add to `.claude/settings.json`:

```json
{
  "hooks": {
    "onToolExecuted": "python scripts/context_hooks.py hook-tool-executed",
    "onTodoWrite": "python scripts/context_hooks.py hook-todo-write",
    "beforeCompact": "python scripts/context_hooks.py prepare-compact"
  }
}
```

**Note**: This is the intended integration method but depends on Claude Code supporting these hooks. Check official documentation for hook availability.

### Method 2: Manual Integration

If hooks aren't available, integrate manually in your workflow:

```bash
# After significant work, manually trigger auto-save check
python scripts/context_hooks.py check-autosave

# Before ending session, prepare state
python scripts/context_hooks.py prepare-compact
```

### Method 3: Wrapper Script

Create a wrapper that simulates hook behavior:

```python
# claude_wrapper.py
import sys
from context_hooks import ToolMonitor

monitor = ToolMonitor()

# Before running Claude command
tool_name = sys.argv[1]
result = run_claude_tool(tool_name)

# After tool execution
monitor.on_tool_executed(tool_name, result.success)
```

## CLI Commands

### Status Check
```bash
python context_hooks.py status
```

Shows current monitor state:
- Workflow mode (task/file/mixed)
- Tools executed since last save
- Time since last save
- Current task
- Task stack depth

### TodoWrite Testing
```bash
python context_hooks.py test-todo
```

Simulates TodoWrite execution with sample todos to verify integration.

### Auto-Save Testing
```bash
python context_hooks.py test-autosave
```

Simulates tool execution to trigger auto-save threshold.

### Monitor Loop (Development)
```bash
python context_hooks.py monitor [duration_seconds]
```

Runs continuous monitoring loop for testing. Default: 60 seconds.

### Prepare for Compact
```bash
python context_hooks.py prepare-compact
```

Forces save of all state before context window compression.

## Configuration

### Adjusting Thresholds

Edit constants in `ToolMonitor` class:

```python
class ToolMonitor:
    # Auto-save thresholds (tools since last save)
    AUTOSAVE_TASK_MODE = 10    # Change to adjust task mode
    AUTOSAVE_MIXED_MODE = 15   # Change to adjust mixed mode
    AUTOSAVE_FILE_MODE = 20    # Change to adjust file mode

    # Time-based auto-save (minutes)
    AUTOSAVE_TIME_TASK = 15
    AUTOSAVE_TIME_MIXED = 20
    AUTOSAVE_TIME_FILE = 30

    # Context switch detection sensitivity
    CONTEXT_WINDOW = 10        # Tools to analyze per window
```

### Logging Level

Adjust logging in script:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG for verbose output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## Workflow Examples

### Example 1: Investigation Task

User starts researching API documentation:

```
1. Read api_docs.md          → ToolMonitor records
2. Grep for "endpoint"       → ToolMonitor records
3. Read server.py            → ToolMonitor records
4. WebSearch for examples    → ToolMonitor records
...
10. Read config.json         → Auto-save triggered! (task mode, 10 tools)
```

### Example 2: TodoWrite Integration

User creates todo list:

```
TodoWrite: [
  {status: "completed", content: "Research API"},
  {status: "in_progress", content: "Implement auth endpoint"},
  {status: "pending", content: "Write tests"}
]

→ ToolMonitor detects "in_progress" task
→ TaskStack.push("Implement auth endpoint")
→ SessionState.update_current_task("Implement auth endpoint", ["TodoWrite"])
```

### Example 3: Context Switch

User switches from investigation to coding:

```
Tools 1-10:  Read, Grep, Read, WebSearch, Read...  (80% task tools)
Tools 11-20: Edit, Write, Edit, Write, Edit...     (70% file tools)

→ Context switch detected: "Investigation" → "Coding"
→ SessionState.log_context_switch()
→ Auto-save triggered
```

### Example 4: Pre-Compact Save

Context window approaching limit:

```
Claude Code: [Internal] Context at 95%
→ Calls: monitor.prepare_for_compact()
→ Force save TaskStack
→ Force save SessionState
→ Display summary:
   [!]  CONTEXT LIMIT APPROACHING - STATE SAVED
   Mode: task
   Tools executed: 142
   Current task: Implement user authentication
   Task stack depth: 3
```

## Troubleshooting

### Issue: Auto-save not triggering

**Cause**: Thresholds not reached or wrong mode detected

**Solution**: Check status:
```bash
python context_hooks.py status
```

Review `tools_since_save` and compare to threshold for current mode.

### Issue: TodoWrite not updating task

**Cause**: No task with `status: "in_progress"`

**Solution**: Ensure at least one todo has `in_progress` status. The monitor only tracks the current active task.

### Issue: Context switches not detected

**Cause**: Not enough tool history (need 20+ tools)

**Solution**: Context switch detection requires minimum 20 tools (2 windows of 10). Keep working until threshold reached.

### Issue: Import errors

**Cause**: Required modules not in same directory

**Solution**: Ensure these files are in the same directory:
- `context_hooks.py`
- `task_stack.py`
- `session_state_manager.py`
- `mode_detector.py`

## Performance Impact

### Memory Usage
- Tool history: ~50 events × ~200 bytes = ~10 KB
- Minimal overhead on Claude Code operation

### Execution Time
- `on_tool_executed()`: <1ms (appends to deque)
- `detect_context_switch()`: ~1-2ms (analyzes 20 tools)
- `should_auto_save()`: <1ms (simple comparisons)
- **Total overhead per tool**: ~2-3ms (negligible)

### Storage Impact
- `task-stack.json`: ~1-2 KB
- `session-state.json`: ~5-10 KB
- Tool history (in memory only, not persisted)

## Future Enhancements

### Phase 1 (Current)
- ✅ Tool execution monitoring
- ✅ Auto-save based on thresholds
- ✅ TodoWrite integration
- ✅ Context switch detection

### Phase 2 (Planned)
- Hook integration with Claude Code
- Real-time dashboard/status display
- Customizable threshold profiles
- Tool execution analytics

### Phase 3 (Future)
- Machine learning for optimal save timing
- Predictive context switch detection
- Cross-session pattern analysis
- Integration with git hooks

## Testing

### Unit Tests

Create `test_context_hooks.py`:

```python
import unittest
from context_hooks import ToolMonitor

class TestToolMonitor(unittest.TestCase):
    def test_auto_save_threshold(self):
        monitor = ToolMonitor()

        # Simulate task mode tools
        for i in range(10):
            monitor.on_tool_executed("Read", True)

        # Should trigger auto-save at 10
        self.assertTrue(monitor.should_auto_save())

    def test_todo_write_extraction(self):
        monitor = ToolMonitor()
        todos = [
            {"status": "in_progress", "content": "Test task"}
        ]

        monitor.on_todo_write(todos)

        self.assertEqual(monitor.task_stack.current(), "Test task")

if __name__ == '__main__':
    unittest.main()
```

### Integration Tests

```bash
# Test full workflow
python scripts/context_hooks.py test-todo
python scripts/context_hooks.py test-autosave

# Verify state persistence
python scripts/task_stack.py show
python scripts/session_state_manager.py show
```

## Best Practices

1. **Let it run automatically**: Don't manually trigger auto-saves unless testing
2. **Trust the thresholds**: They're calibrated for optimal performance
3. **Use TodoWrite consistently**: This is how the monitor knows your current task
4. **Review status periodically**: Run `status` command to understand behavior
5. **Adjust thresholds cautiously**: Default values work for most workflows

## Support

For issues or questions:
1. Check `CLAUDE.md` for project overview
2. Review `SESSION_PROTOCOL.md` for session continuity concepts
3. Examine logs in `~/.claude-sessions/`
4. Run diagnostic commands to understand behavior

## Related Documentation

- `CLAUDE.md` - Project memory and overview
- `SESSION_PROTOCOL.md` - Session continuity system
- `docs/DEPENDENCY_TRACKING.md` - Cross-file dependency tracking
- `docs/MULTI_PROJECT_SESSION_TRACKING.md` - Multi-project support
