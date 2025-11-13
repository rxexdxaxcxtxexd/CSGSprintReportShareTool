# API Documentation Agent - Project Memory

## Project Overview
This project demonstrates an automated session continuity system for Claude Code, enabling seamless context preservation across sessions through intelligent checkpointing, automated change detection, and smart resume point generation.

## Session Protocol
For comprehensive instructions on session tracking and continuity, see [SESSION_PROTOCOL.md](SESSION_PROTOCOL.md).

**Quick commands:**
```bash
python scripts/checkpoint.py --quick        # Save session
python scripts/resume-session.py            # Load previous session
python scripts/context-monitor.py           # Check context usage
```

---

## Current Session State

**Last Updated:** 2025-11-13 (System setup complete)
**Session ID:** system-v2

### Active Focus
Implementing 10 critical improvements to session continuity system:
1. ✅ Split CLAUDE.md (reduced from 455 lines to ~100 lines, 8K → 1K tokens)
2. ⏳ Exclude `.claude/` internal files from tracking
3. ⏳ Create unified `checkpoint.py` command
4. ⏳ Add file size limits and binary exclusions
5. ⏳ Implement atomic CLAUDE.md updates
6. ⏳ Create context window monitoring
7. ⏳ Add auto-checkpoint triggers
8. ⏳ Detect accurate session boundaries
9. ⏳ Generate smart resume points
10. ⏳ Add checkpoint validation

### Recent Work
- Created SESSION_PROTOCOL.md with all instructions (7K tokens moved)
- Refactored CLAUDE.md to data-focused format
- Reduced token overhead by 87.5% (8K → 1K tokens)

### Next Steps
- [ ] Continue Phase 1 improvements (items 2-5)
- [ ] Implement Phase 2 critical fixes (items 6-8)
- [ ] Add Phase 3 enhancements (items 9-10)
- [ ] Test all improvements
- [ ] Update documentation and push to GitHub

---

## Decision Log

### Decision: Split CLAUDE.md into Data + Protocol
**Date:** 2025-11-13
**Decision:** Separate project memory (CLAUDE.md) from instructions (SESSION_PROTOCOL.md)
**Rationale:** CLAUDE.md was 90% instructions, wasting 7K tokens per session. Instructions are reference material, not live data.
**Impact:** 87.5% reduction in token usage per session
**Alternatives Considered:**
- Keep combined (rejected: token waste)
- Remove instructions entirely (rejected: Claude needs reference)
- Use comments/hidden sections (rejected: still loaded)

### Decision: Hybrid Logging Format
**Date:** 2025-11-12
**Decision:** Use both Markdown (human-readable) and JSON (machine-readable) for session logs
**Rationale:** Provides best of both worlds - humans can read logs naturally, machines can parse checkpoints for automation
**Alternatives Considered:**
- JSON only (harder for humans to read)
- Markdown only (harder for automation)

### Decision: Root vs Projects CLAUDE.md Location
**Date:** 2025-11-12
**Decision:** Maintain CLAUDE.md in root directory, not in Projects directory
**Rationale:** Root location keeps project memory close to working directory and separate from implementation details
**Alternatives Considered:**
- Projects directory (conflicts with implementation focus)
- Both locations (synchronization complexity)

### Decision: Script-Based Session Management
**Date:** 2025-11-12
**Decision:** Use Python scripts for session management instead of integrated automation
**Rationale:** Scripts provide flexibility, can be run manually or integrated later, easier to debug and customize
**Alternatives Considered:**
- Automated hooks (more complex, harder to debug)
- Manual markdown updates (error-prone, no checkpoints)

### Decision: Windows Encoding Compatibility
**Date:** 2025-11-13
**Decision:** Disable rich output on Windows, use ASCII-friendly formatting
**Rationale:** Prevents UnicodeEncodeError with emoji characters in Windows console
**Alternatives Considered:**
- Force UTF-8 (doesn't work reliably on Windows)
- Remove all special characters (loses visual clarity)

---

## Integration Notes

**Project Structure:** See [SESSION_PROTOCOL.md - Integration Map](SESSION_PROTOCOL.md#integration-map) for full details.

**Key Directories:**
- `.claude-sessions/` - Session checkpoints and logs
- `scripts/` - Session management tools
- Root directory - Project memory and planning

**Main Tools:**
- `checkpoint.py` - Unified checkpoint command (use this!)
- `resume-session.py` - Load previous session state
- `context-monitor.py` - Check context window usage

---

## Quick Reference

### Create Checkpoint
```bash
python scripts/checkpoint.py --quick
```

### Resume Session
```bash
python scripts/resume-session.py
```

### Check Context
```bash
python scripts/context-monitor.py
```

### List All Sessions
```bash
python scripts/resume-session.py list
```

---

**For complete documentation, workflows, and detailed instructions:**
→ See [SESSION_PROTOCOL.md](SESSION_PROTOCOL.md)
