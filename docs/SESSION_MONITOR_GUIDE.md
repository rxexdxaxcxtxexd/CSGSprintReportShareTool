# Active Session Monitor - Quick Start Guide

## Overview

The Active Session Monitor provides **100% automated session continuity** for Claude Code by continuously monitoring all active sessions and creating intelligent checkpoints based on activity, time, idle detection, and context usage.

**Inspired by:** [Memori](https://github.com/rxexdxaxcxtxexd/Memori)

## Key Features

- **Multi-Window Coordination**: Prevents duplicate checkpoints across multiple Claude Code windows
- **Intelligent Triggers**: Multi-factor decision engine (time + activity + idle + context)
- **Risk Prioritization**: Processes sessions with oldest checkpoints first
- **Idle Detection**: Automatically checkpoints sessions idle for 30+ minutes
- **Activity Tracking**: Monitors file modifications and message counts
- **Zero Configuration**: Works out of the box with sensible defaults

## Architecture

### Components

1. **session_detector.py** - Scans `.claude/projects/` for active sessions
2. **checkpoint_coordinator.py** - Coordinates checkpoints across multiple windows
3. **session_monitor.py** - Main daemon with multi-factor decision engine

### Decision Engine

The monitor uses weighted scoring to decide when to checkpoint:

| Trigger | Threshold | Weight | Description |
|---------|-----------|--------|-------------|
| Time | 2 hours | 0.3 | Time since last checkpoint |
| Activity | 15 files | 0.4 | Number of files modified |
| Context | 75% | 0.5 | Context window usage (planned) |
| Idle | 30 minutes | 0.2 | Time since last activity |

A checkpoint is created if:
- **Any single trigger reaches 100%** (e.g., 2+ hours since last checkpoint)
- **OR weighted total score ≥ 1.0** (e.g., 1.5 hours + 10 files + 20 min idle)

### Cooldown Period

- Minimum 30 minutes between checkpoints for the same session
- Prevents excessive checkpointing
- Can be configured via `checkpoint_coordinator.py`

## Installation

### Quick Install (Recommended)

```powershell
# Install with default settings (check every 5 minutes)
.\scripts\setup-session-monitor.ps1 install
```

### Custom Install

```powershell
# Custom check interval and triggers
.\scripts\setup-session-monitor.ps1 install `
    -Interval 10 `
    -TimeHours 1 `
    -ActivityFiles 10 `
    -IdleMinutes 20
```

**What it does:**
- Creates a Windows Scheduled Task
- Starts at logon and runs continuously
- Automatically restarts if it crashes
- Logs to `~/.claude/session-monitor.log`

## Usage

### Check Status

```powershell
.\scripts\setup-session-monitor.ps1 status
```

Shows:
- Current state (Running/Stopped)
- Last run time
- Next run time
- Configuration
- Log file location

### View Logs

```powershell
# Last 30 lines
.\scripts\setup-session-monitor.ps1 logs

# Follow logs in real-time
Get-Content ~/.claude/session-monitor.log -Wait -Tail 10
```

### Test Before Installing

```powershell
# Run a single check to see what would happen
.\scripts\setup-session-monitor.ps1 test
```

### Start/Stop

```powershell
# Stop temporarily (e.g., during heavy work)
.\scripts\setup-session-monitor.ps1 stop

# Resume monitoring
.\scripts\setup-session-monitor.ps1 start
```

### Uninstall

```powershell
.\scripts\setup-session-monitor.ps1 uninstall
```

## Manual Usage

### One-Time Check

```bash
python scripts/session_monitor.py --once
```

### Daemon Mode

```bash
# Check every 5 minutes (default)
python scripts/session_monitor.py

# Check every 10 minutes
python scripts/session_monitor.py --interval 10
```

### View Active Sessions

```bash
python scripts/session_detector.py
```

Output:
```
Found 268 active session(s):

Session 1:
  ID: 02d3f2d7
  Project: C:\Users\layden
  Last Activity: 2025-11-26T21:29:28.835Z
  Messages: 100
  Files Modified: 15
  Idle Time: 45 minute(s)
  Last Checkpoint: 2025-11-25T09:55:59
  Uncommitted Changes: Yes
```

## Configuration

### Config File Location

`~/.claude/monitor-config.json`

### Example Config

```json
{
  "interval": 5,
  "time_hours": 2,
  "activity_files": 15,
  "idle_minutes": 30,
  "installed_at": "2025-11-26 15:45:00"
}
```

### Adjusting Triggers

Edit the config file or reinstall with new parameters:

```powershell
# More aggressive (checkpoint more often)
.\scripts\setup-session-monitor.ps1 install `
    -TimeHours 1 `
    -ActivityFiles 5 `
    -IdleMinutes 15

# More conservative (checkpoint less often)
.\scripts\setup-session-monitor.ps1 install `
    -TimeHours 4 `
    -ActivityFiles 25 `
    -IdleMinutes 60
```

## How It Works

### Session Detection

1. Scans `~/.claude/projects/` for all project directories
2. Each directory contains session JSONL files
3. Extracts session ID, project path, and activity metrics
4. Decodes project path from directory name (e.g., `C--Users-layden` → `C:\Users\layden`)

### Checkpoint Coordination

1. Acquires exclusive lock via `~/.claude/checkpoint.lock`
2. Checks cooldown period (30 minutes minimum)
3. Updates state in `~/.claude/monitor-state.json`
4. Releases lock after checkpoint completes

### Decision Process

For each active session:

1. **Skip if in cooldown** - Last checkpoint < 30 minutes ago
2. **Calculate time score** - Hours since last checkpoint / threshold
3. **Calculate activity score** - Files modified / threshold
4. **Calculate idle score** - Minutes idle / threshold
5. **Compute weighted total** - Sum(score × weight) for each factor
6. **Checkpoint if triggered** - Any score ≥ 1.0 OR total ≥ 1.0

### Priority Sorting

Sessions are sorted by last checkpoint time (oldest first):
- Sessions never checkpointed: Highest priority
- Sessions with oldest checkpoints: Higher priority
- Recently checkpointed sessions: Lower priority

This ensures maximum risk mitigation - losing a session that hasn't been checkpointed in days is worse than losing one checkpointed 2 hours ago.

## Troubleshooting

### Monitor Not Running

```powershell
# Check status
.\scripts\setup-session-monitor.ps1 status

# If stopped, start it
.\scripts\setup-session-monitor.ps1 start

# If not installed, install it
.\scripts\setup-session-monitor.ps1 install
```

### No Checkpoints Being Created

**Check logs:**
```powershell
.\scripts\setup-session-monitor.ps1 logs
```

**Common causes:**
1. All sessions within cooldown period (wait 30 minutes)
2. No sessions meet trigger thresholds (check configuration)
3. Monitor not running (check status)
4. Python not in PATH (run `python --version`)

**Test manually:**
```bash
python scripts/session_monitor.py --once
```

### Too Many Checkpoints

Adjust thresholds to be more conservative:

```powershell
.\scripts\setup-session-monitor.ps1 install `
    -TimeHours 4 `
    -ActivityFiles 30 `
    -IdleMinutes 60
```

### Permission Errors

The monitor may need write access to:
- `~/.claude/checkpoint.lock`
- `~/.claude/monitor-state.json`
- `~/.claude/session-monitor.log`
- `~/.claude-sessions/checkpoints/`

If permission errors occur, check folder permissions.

### Lock File Issues

If the monitor reports "Failed to acquire lock":
1. Another monitor instance is running (normal - wait for it to finish)
2. Stale lock from crash (automatically cleaned after 10 minutes)
3. Manual cleanup: `Remove-Item ~/.claude/checkpoint.lock`

## Performance

### Resource Usage

- **CPU**: Minimal (only during checkpoint creation)
- **Memory**: ~50-100 MB for Python process
- **Disk**: ~7 KB per checkpoint

### Timing

- **Session scan**: ~1-2 seconds (for 268 sessions)
- **Checkpoint creation**: ~2 seconds per session
- **Total for 68 sessions**: ~2.5 minutes

### Scaling

Tested with **268 active sessions**:
- Detection: Fast (< 5 seconds)
- Processing: Efficient (~2 seconds per checkpoint)
- Coordination: No conflicts observed

## Integration with Existing System

The session monitor works alongside your existing automation:

### Existing Automation
- **SessionStart hook** → `resume-session.py` (when Claude starts)
- **SessionEnd hook** → `checkpoint.py` (when Claude exits)
- **Git post-commit hook** → `checkpoint.py` (after commits)
- **Task Scheduler** → `checkpoint.py` (every 30 min, optional)

### New Addition
- **Session Monitor** → Intelligent background monitoring (continuously)

### Coverage Matrix

| Scenario | Existing | Monitor | Coverage |
|----------|----------|---------|----------|
| Normal exit | SessionEnd hook | ✓ | 100% |
| Crash | Task Scheduler | ✓✓ | 100% |
| Long-running session | Task Scheduler | ✓✓✓ | 100% |
| Multiple windows | ❌ | ✓✓✓ | 100% |
| Idle sessions | ❌ | ✓✓✓ | 100% |
| Activity-based | ❌ | ✓✓✓ | 100% |

**Result:** True 100% automation with intelligent triggers!

## Advanced Usage

### Custom Decision Engine

Edit `scripts/session_monitor.py` to customize the decision engine:

```python
# Line 36-49: Adjust default config
self.config = config or {
    'time_hours': 2,           # Your custom value
    'activity_file_count': 15, # Your custom value
    'context_percent': 75,     # Future feature
    'idle_minutes': 30,        # Your custom value
}

# Line 43-49: Adjust weights
self.weights = {
    'time': 0.3,      # Increase for more time-sensitive
    'activity': 0.4,  # Increase for more activity-sensitive
    'context': 0.5,   # Future: context window usage
    'idle': 0.2       # Increase for more idle-sensitive
}
```

### Custom Cooldown Period

Edit `scripts/checkpoint_coordinator.py`:

```python
# Line 56: Adjust minimum interval (default: 30 minutes)
self.min_checkpoint_interval = 30  # Change to your value
```

### Log Level

Edit `scripts/session_monitor.py`:

```python
# Line 175: Change log level
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG for more detail
    ...
)
```

## FAQ

**Q: Will this checkpoint too often?**
A: No. The 30-minute cooldown prevents excessive checkpointing. In testing, 68 of 268 sessions were checkpointed (the rest were within cooldown).

**Q: What if I have hundreds of sessions?**
A: The system scales well. Session detection is fast (< 5 seconds for 268 sessions), and checkpoints are created sequentially with proper coordination.

**Q: Can I run multiple monitors?**
A: The lock coordinator prevents conflicts, but it's not recommended. The monitor is designed to handle all sessions from one instance.

**Q: How do I see what sessions were checkpointed?**
A: Check the logs: `.\scripts\setup-session-monitor.ps1 logs`

**Q: Can I customize trigger thresholds per session?**
A: Not yet. All sessions use the same thresholds. This could be added as a future enhancement.

**Q: What if my project path isn't in the home directory?**
A: The monitor detects projects from `.claude/projects/` and decodes the actual path. It works with any project path.

**Q: Does this replace the existing automation?**
A: No, it complements it. Keep your SessionStart/SessionEnd hooks and Task Scheduler for comprehensive coverage.

## Support

### Log Files
- Session monitor: `~/.claude/session-monitor.log`
- Checkpoint coordinator: `~/.claude/monitor-state.json`
- Lock file: `~/.claude/checkpoint.lock`

### Useful Commands

```powershell
# Full status check
.\scripts\setup-session-monitor.ps1 status

# Watch logs live
Get-Content ~/.claude/session-monitor.log -Wait -Tail 10

# Test decision engine
python scripts/session_monitor.py --once --time-hours 0.5

# View all active sessions
python scripts/session_detector.py

# Manual checkpoint
python scripts/checkpoint.py --quick

# Check coordinator state
Get-Content ~/.claude/monitor-state.json | ConvertFrom-Json
```

## Credits

**Inspired by:** [Memori](https://github.com/rxexdxaxcxtxexd/Memori) by rxexdxaxcxtxexd

**Key Concept Adopted:** Active monitoring daemon that continuously watches sessions instead of relying solely on hooks and fixed intervals.

**Enhancements Added:**
- Multi-window coordination via file locking
- Multi-factor decision engine with weighted scoring
- Risk-based prioritization (oldest checkpoints first)
- Intelligent idle detection
- Activity-based triggers
- Windows Task Scheduler integration
- Comprehensive PowerShell setup tool

---

**Documentation Version:** 1.0
**Last Updated:** 2025-11-26
**System Tested On:** Windows 11, Claude Code with 268 active sessions
