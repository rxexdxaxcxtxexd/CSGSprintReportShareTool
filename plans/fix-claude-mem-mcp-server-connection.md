# fix: Claude-mem MCP Server Connection

## Overview

The hybrid memory system is partially configured but not fully functional. The claude-mem plugin is **enabled** in `.claude/settings.json` but the **MCP server is not connected**. This means `/mem-search` commands won't work and no semantic observations are being captured.

**Current Status:**
- ✅ Code Context Layer - Working (`.claude-code-context.md` auto-generated)
- ❌ claude-mem MCP Server - Not connected (plugin enabled but server not configured)
- ⚠️ SessionStart/End Hooks - Running but can't access claude-mem

**Impact:** You're only getting 50% of your hybrid memory system. Technical context works, but semantic search and observation capture do not.

---

## Problem Statement

When running `claude mcp list`, claude-mem does not appear in the list of MCP servers:

```
Current MCP Servers:
✓ plugin:compound-engineering:pw (Playwright)
✓ plugin:compound-engineering:context7 (Context7)
✓ mcp-atlassian (Atlassian)

Missing:
✗ claude-mem (NOT CONNECTED)
```

Additionally:
- No `~/.claude/mcp/mcp.json` configuration file exists
- `/mem-search` commands won't work without MCP server
- Semantic observations are not being captured
- Plugin is enabled but has no server to connect to

---

## Root Cause Analysis

### Issue 1: Missing MCP Server Configuration

**Finding:** No MCP configuration file at `~/.claude/mcp/mcp.json`

**Evidence:**
```bash
$ Read C:\Users\layden\.claude\mcp\mcp.json
> File does not exist.
```

**Impact:** Claude Code doesn't know how to connect to claude-mem MCP server

### Issue 2: Plugin vs MCP Server Confusion

**Finding:** There's a difference between "enabled plugins" and "active MCP servers"

**From investigation:**
- `.claude/settings.json` shows `"claude-mem@anthropic": true` (plugin enabled)
- `claude mcp list` shows claude-mem is NOT connected (server not active)

**Understanding:**
- **Enabled Plugin** = Feature flag saying "I want to use claude-mem"
- **MCP Server** = Actual server process that provides claude-mem functionality
- You can have plugin enabled without server connected!

### Issue 3: Installation/Setup May Be Incomplete

**Finding:** Documentation assumes claude-mem "just works" when enabled

**Gap:** Missing setup steps for:
1. Installing claude-mem MCP server
2. Configuring MCP server in mcp.json
3. Verifying connection

---

## Proposed Solution

### Phase 1: Investigate claude-mem Installation

**Goal:** Determine if claude-mem is installed and where

**Tasks:**
1. Check if claude-mem is installed as npm package
   ```bash
   npm list -g | grep -i claude-mem
   ```

2. Check Claude Code plugin directory
   ```bash
   ls ~/.claude/plugins/
   ls "C:\Users\layden\.claude\plugins\"
   ```

3. Search for claude-mem related files
   ```bash
   # Find any claude-mem executables or configs
   find ~/.claude -name "*claude-mem*" -o -name "*mem*"
   ```

4. Check if claude-mem provides MCP server
   ```bash
   # Try to find documentation or command
   claude-mem --help 2>&1 || echo "Not installed as CLI"
   ```

### Phase 2: Configure MCP Server

**Goal:** Add claude-mem to MCP server configuration

**Option A: If claude-mem provides MCP server**

Create or update `~/.claude/mcp/mcp.json`:

```json
{
  "mcpServers": {
    "claude-mem": {
      "command": "claude-mem",
      "args": ["serve"],
      "env": {
        "CLAUDE_MEM_CONTEXT_OBSERVATIONS": "25"
      }
    }
  }
}
```

**Option B: If claude-mem is HTTP-based**

```json
{
  "mcpServers": {
    "claude-mem": {
      "url": "http://localhost:PORT/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
```

**Option C: If claude-mem is plugin-based (no separate server)**

Research if Anthropic plugins work differently than custom MCP servers. May need to:
- Contact Anthropic support
- Check official claude-mem documentation
- Verify if plugin-based memory works differently

### Phase 3: Verify Connection

**Goal:** Confirm claude-mem MCP server is connected

**Verification Steps:**

1. **Restart Claude Code** (required after MCP config changes)
   ```bash
   # Close and reopen Claude Code
   ```

2. **Check MCP server list**
   ```bash
   claude mcp list
   # Should now show: ✓ claude-mem (Connected)
   ```

3. **Test MCP resources**
   ```bash
   # In Claude Code conversation:
   ListMcpResourcesTool(server="claude-mem")
   ```

4. **Test /mem-search command**
   ```bash
   /mem-search test query
   # Should return: "No observations found" (empty database is OK)
   # Should NOT return: "Server not found" or error
   ```

### Phase 4: Capture Test Observations

**Goal:** Verify observations are being captured

**Test Procedure:**

1. **Have substantial conversation**
   - Ask Claude to explain architectural decisions
   - Discuss implementation strategies
   - Make technical decisions with rationale

2. **Wait for observation capture** (happens asynchronously)

3. **Search for captured observations**
   ```bash
   /mem-search [topic from your conversation]
   ```

4. **Verify results returned**
   - Should find observations from the test conversation
   - Should show timestamps and context

### Phase 5: Document and Validate

**Goal:** Update documentation and confirm full system working

**Final Checks:**

1. ✅ Code Context Layer working
   - `.claude-code-context.md` updates on commit
   - Dependency analysis present
   - Test recommendations included

2. ✅ claude-mem MCP Server connected
   - Listed in `claude mcp list`
   - Responds to resource requests
   - `/mem-search` command works

3. ✅ Observation capture working
   - Test conversations captured
   - Semantic search returns results
   - Timestamps and context present

4. ✅ SessionStart/End hooks working
   - Code context displayed at session start
   - Workspace state captured at session end
   - No errors in hook execution

---

## Alternative Approaches Considered

### Alternative 1: Disable claude-mem Entirely

**Approach:** Remove claude-mem plugin, rely only on Code Context Layer

**Pros:**
- Simpler system
- No MCP configuration needed
- Still have technical context from `.claude-code-context.md`

**Cons:**
- Lose semantic search capability
- Can't find things by meaning across sessions
- Documentation promises semantic search but doesn't deliver

**Verdict:** ❌ Not recommended - defeats purpose of hybrid system

### Alternative 2: Use Historical Context Instead

**Approach:** Leverage `~/.claude/historical-context/` from old system

**Pros:**
- Already working
- No new setup required
- Has historical session data

**Cons:**
- No semantic search (keyword only)
- Not auto-updated with new sessions
- Legacy system being phased out

**Verdict:** ❌ Not recommended - moving backward, not forward

### Alternative 3: Manual Observation Logging

**Approach:** Manually write important observations to markdown files

**Pros:**
- Simple, no MCP servers needed
- Full control over what's captured
- Can use grep for search

**Cons:**
- Manual intervention (defeats automation goal)
- No semantic search
- Extra overhead during work

**Verdict:** ❌ Not recommended - too much friction

### Selected Approach: Fix MCP Server Configuration

**Why this approach:**
1. Preserves intended hybrid system architecture
2. Enables semantic search as documented
3. Maintains full automation (no manual steps)
4. Delivers on system promises
5. Aligns with Phase 3 migration goals

---

## Acceptance Criteria

### Functional Requirements

- [ ] claude-mem appears in `claude mcp list` as connected
- [ ] `ListMcpResourcesTool(server="claude-mem")` returns resources (not error)
- [ ] `/mem-search <query>` executes without "server not found" error
- [ ] Substantial conversations result in captured observations
- [ ] Semantic search returns relevant results from past sessions
- [ ] SessionStart hook displays both code context + mem-search reminder
- [ ] SessionEnd hook runs without errors

### Non-Functional Requirements

- [ ] **Performance:** MCP connection doesn't slow down Claude Code startup (<2s overhead)
- [ ] **Reliability:** MCP server stays connected throughout session (no disconnects)
- [ ] **Cost:** Observation capture stays within $11.25/month budget (25 observations/context)
- [ ] **Privacy:** All observations stored locally in `~/.claude/mem/` (not cloud)

### Quality Gates

- [ ] **Documentation Updated:** `docs/CLAUDE_MEM_GUIDE.md` reflects actual setup steps
- [ ] **Troubleshooting Guide:** Add "MCP server not connected" section to docs
- [ ] **Verification Script:** Create `scripts/verify-claude-mem.py` to check setup
- [ ] **Integration Test:** Can search for observation from test conversation

---

## Success Metrics

**Primary Metrics:**

1. **MCP Connection Status**
   - Before: ❌ Not connected (0/1 servers)
   - After: ✅ Connected (4/4 servers including claude-mem)

2. **Semantic Search Availability**
   - Before: ❌ `/mem-search` fails with "server not found"
   - After: ✅ `/mem-search` executes and returns results

3. **Observation Capture Rate**
   - Before: 0 observations/session
   - After: ~5-15 observations per meaningful session

**Secondary Metrics:**

4. **Documentation Accuracy**
   - Match between docs and actual behavior: 100%
   - Setup steps clearly documented: Yes

5. **User Experience**
   - Manual steps required: 0 (fully automated)
   - Session start time: <3s (with MCP connection)
   - Search response time: <2s for typical query

---

## Dependencies & Prerequisites

### Hard Dependencies

1. **Claude Code Installation**
   - Status: ✅ Installed (`C:\Users\layden\AppData\Roaming\npm\claude`)
   - Version: Latest (assumed)

2. **Node.js/npm**
   - Status: ✅ Present (Claude Code requires it)
   - Used for: npm-based MCP servers

3. **Python 3.8+**
   - Status: ✅ Present (hooks working)
   - Used for: SessionStart/End hooks

### Soft Dependencies

4. **Git Repository**
   - Status: ✅ Active git repo
   - Used for: Code context generation on commit

5. **Internet Connection**
   - Needed for: Initial claude-mem setup/download
   - Not needed for: Runtime operation (all local)

### Blockers/Unknowns

- **Unknown:** How to install/configure claude-mem MCP server
  - Risk: May not be publicly available yet
  - Mitigation: Contact Anthropic support if needed

- **Unknown:** Whether claude-mem requires separate server or is built into plugin
  - Risk: Configuration approach depends on this
  - Mitigation: Investigation in Phase 1 will clarify

---

## Risk Analysis & Mitigation

### Risk 1: claude-mem Not Publicly Available

**Likelihood:** Medium
**Impact:** High (can't implement solution)

**Mitigation:**
- Check Anthropic documentation for claude-mem availability
- Contact Anthropic support for plugin setup guidance
- Consider alternative: Custom MCP server for semantic search

### Risk 2: MCP Configuration Breaking Other Servers

**Likelihood:** Low
**Impact:** Medium (lose other MCP functionality)

**Mitigation:**
- Backup existing `mcp.json` before changes
- Test other MCP servers after claude-mem configuration
- Rollback procedure documented

### Risk 3: Performance Degradation

**Likelihood:** Low
**Impact:** Medium (slow session starts, laggy responses)

**Mitigation:**
- Monitor session start times before/after
- Optimize `CLAUDE_MEM_CONTEXT_OBSERVATIONS` if needed
- Can disable claude-mem if performance unacceptable

### Risk 4: Cost Overruns

**Likelihood:** Low
**Impact:** Medium (higher API costs than expected)

**Mitigation:**
- Start with conservative `CLAUDE_MEM_CONTEXT_OBSERVATIONS=15`
- Monitor usage in Anthropic dashboard
- Adjust observations/context based on actual costs

---

## Implementation Checklist

### Phase 1: Investigation (1-2 hours)
- [ ] Check npm for claude-mem package
- [ ] Search Claude Code plugin directory
- [ ] Find claude-mem documentation (official Anthropic)
- [ ] Determine if MCP server or plugin-only
- [ ] Document findings in investigation notes

### Phase 2: Configuration (1 hour)
- [ ] Backup existing `.claude/` directory
- [ ] Create or update `mcp.json` based on findings
- [ ] Configure claude-mem server (command/URL/args)
- [ ] Set environment variables (CLAUDE_MEM_CONTEXT_OBSERVATIONS)
- [ ] Restart Claude Code

### Phase 3: Verification (30 minutes)
- [ ] Run `claude mcp list` - confirm claude-mem connected
- [ ] Test `ListMcpResourcesTool(server="claude-mem")`
- [ ] Try `/mem-search test` - should not error
- [ ] Check SessionStart hook output - includes mem-search reminder

### Phase 4: Testing (1 hour)
- [ ] Have substantial test conversation (architectural discussion)
- [ ] Wait 5 minutes for observation capture
- [ ] Search for test conversation topics
- [ ] Verify results returned with context
- [ ] Test multiple queries for same content

### Phase 5: Documentation (1 hour)
- [ ] Update `docs/CLAUDE_MEM_GUIDE.md` with actual setup steps
- [ ] Add "Troubleshooting MCP Connection" section
- [ ] Create `scripts/verify-claude-mem.py` verification script
- [ ] Update `docs/MIGRATION_GUIDE.md` with MCP config requirements
- [ ] Document setup steps in `SESSION_PROTOCOL.md`

---

## File Changes Required

### New Files

#### `~/.claude/mcp/mcp.json`
```json
{
  "mcpServers": {
    "claude-mem": {
      "command": "TBD_AFTER_INVESTIGATION",
      "args": ["TBD"],
      "env": {
        "CLAUDE_MEM_CONTEXT_OBSERVATIONS": "25"
      }
    }
  }
}
```
**Purpose:** Configure claude-mem as MCP server

#### `scripts/verify-claude-mem.py`
```python
#!/usr/bin/env python3
"""
Verify claude-mem hybrid memory system is fully operational
"""

def verify_mcp_server():
    """Check if claude-mem MCP server is connected"""
    # Implementation TBD
    pass

def verify_observation_capture():
    """Check if observations are being captured"""
    # Implementation TBD
    pass

def verify_search_functionality():
    """Check if /mem-search works"""
    # Implementation TBD
    pass

if __name__ == '__main__':
    main()
```
**Purpose:** Quick verification script for troubleshooting

### Modified Files

#### `docs/CLAUDE_MEM_GUIDE.md`
**Changes:**
- Add "MCP Server Setup" section (lines 22-50)
- Add "Troubleshooting MCP Connection" section (lines 300-330)
- Update "Quick Start" with MCP configuration steps
- Add verification commands

#### `docs/MIGRATION_GUIDE.md`
**Changes:**
- Update Phase 1 checklist with MCP configuration (line 291)
- Add prerequisite: MCP server must be configured
- Add troubleshooting for "MCP server not connected"

#### `SESSION_PROTOCOL.md`
**Changes:**
- Add MCP server setup to "Getting Started" section
- Update architecture diagram to show MCP layer
- Document claude-mem as MCP server (not just plugin)

---

## Testing Strategy

### Unit Tests

1. **MCP Server Connection**
   ```python
   def test_claude_mem_mcp_connected():
       """Verify claude-mem appears in MCP server list"""
       result = run_command("claude mcp list")
       assert "claude-mem" in result
       assert "Connected" in result
   ```

2. **Resource Listing**
   ```python
   def test_claude_mem_resources():
       """Verify MCP server responds to resource requests"""
       # Use ListMcpResourcesTool in Claude Code
       # Should return resources, not error
   ```

### Integration Tests

3. **End-to-End Observation Capture**
   ```python
   def test_observation_capture_and_search():
       """Test full workflow: conversation → capture → search"""
       # 1. Have conversation with unique identifier
       # 2. Wait for observation capture
       # 3. Search for unique identifier
       # 4. Verify results contain conversation content
   ```

4. **Session Continuity**
   ```python
   def test_session_start_with_mem():
       """Verify SessionStart hook mentions claude-mem"""
       # Start new Claude Code session
       # Check output includes "/mem-search" reminder
   ```

### Manual Verification

5. **Semantic Search Quality**
   - Create conversation about "authentication with JWT tokens"
   - Search with: "login security"
   - Verify results include JWT conversation
   - Confirms semantic search works (not just keyword)

6. **Cost Verification**
   - Monitor Anthropic dashboard for 1 week
   - Confirm costs ~$11.25/month with 25 observations
   - Adjust `CLAUDE_MEM_CONTEXT_OBSERVATIONS` if needed

---

## Rollback Plan

If claude-mem MCP server causes issues:

### Immediate Rollback (< 5 minutes)

1. **Remove claude-mem from MCP config**
   ```bash
   # Edit ~/.claude/mcp/mcp.json
   # Remove "claude-mem" section
   ```

2. **Restart Claude Code**
   ```bash
   # Close and reopen
   ```

3. **Verify other MCP servers still work**
   ```bash
   claude mcp list
   # Should show other servers connected
   ```

### Partial Rollback (Keep plugin, remove MCP)

1. **Keep plugin enabled in settings**
   ```json
   {
     "enabledPlugins": {
       "claude-mem@anthropic": true  // Keep this
     }
   }
   ```

2. **Remove MCP server config**
   - Keeps plugin for future when setup is clearer
   - Loses MCP functionality but no harm

### Full Rollback (Remove everything)

1. **Disable plugin**
   ```json
   {
     "enabledPlugins": {
       "claude-mem@anthropic": false  // Disable
     }
   }
   ```

2. **Remove MCP config**
3. **Remove environment variable**
4. **Restart Claude Code**

**Result:** Back to Code Context Layer only (still functional)

---

## Future Considerations

### Phase 4: Historical Data Migration

Once claude-mem is working, migrate old checkpoints:

```python
# scripts/migrate-checkpoints-to-mem.py
# Convert last 90 days of checkpoints → claude-mem observations
```

### Enhanced Search

Add search UI or command-line tool:
```bash
claude-mem search "authentication decisions" --format=markdown
```

### Multi-Machine Sync

Consider syncing `~/.claude/mem/` across machines:
- Dropbox/OneDrive sync
- Git repository
- Custom sync service

### Team Sharing

For team environments:
- Shared observation database
- Team-wide semantic search
- Privacy controls per observation

---

## References & Research

### Internal References

- **Settings:** `.claude/settings.json:36` - Plugin enabled
- **SessionStart Hook:** `scripts/session_start_bridge.py:74-80` - Mentions /mem-search
- **Documentation:** `docs/CLAUDE_MEM_GUIDE.md:1-471` - User guide (assumes working)
- **Migration Guide:** `docs/MIGRATION_GUIDE.md:1-438` - Old → new workflow

### External References

- **Claude Code Docs:** https://docs.claudecode.com/mcp - MCP server configuration
- **Anthropic Plugins:** https://anthropic.com/plugins - Official plugin documentation
- **MCP Protocol:** https://modelcontextprotocol.io - Protocol specification

### Related Work

- **Issue:** "claude-mem not connected" - This plan
- **Previous Work:** Code Context Layer (working)
- **Previous Work:** SessionStart/End hooks (working)
- **Blocker:** MCP server configuration (this plan resolves)

---

## Appendix: Investigation Commands

### Check Current MCP Status
```bash
# List connected MCP servers
claude mcp list

# Check MCP configuration file
cat ~/.claude/mcp/mcp.json  # Unix/Mac
type "%USERPROFILE%\.claude\mcp\mcp.json"  # Windows

# Check enabled plugins
cat ~/.claude/settings.json | grep claude-mem
```

### Search for claude-mem Installation
```bash
# Check npm global packages
npm list -g | grep claude-mem

# Check plugin directory
ls ~/.claude/plugins/

# Search for claude-mem executables
which claude-mem  # Unix/Mac
where claude-mem  # Windows

# Check if command exists
claude-mem --version 2>&1 || echo "Not installed"
```

### Verify Environment
```bash
# Check environment variables
env | grep CLAUDE_MEM

# Check Claude Code version
claude --version

# Check Node.js version
node --version

# Check Python version
python --version
```

### Test MCP Connection (in Claude Code)
```
# Use these in Claude Code conversation:
ListMcpResourcesTool(server="claude-mem")
/mem-search test query
```

---

**Last Updated:** 2025-12-19
**Status:** Ready for Investigation
**Estimated Time:** 3-5 hours total
**Priority:** High (core functionality not working)
