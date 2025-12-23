# Plan: Verify and Test Memory Server

## Current Status
- ✅ Memory server configured in `~/.claude.json`
- ✅ Claude Code restarted
- ⏳ Verification pending

## Phase 1: Verify Connection (5 minutes)

### Task 1.1: Check MCP Server List
```bash
# Run in terminal (outside Claude Code)
claude mcp list
```

**Expected Output:**
```
Connected MCP Servers:
✓ mcp-atlassian
✓ memory          # Should appear here
```

### Task 1.2: Test MCP Resource Listing
In Claude Code conversation:
```
ListMcpResourcesTool(server="memory")
```

**Expected:** Empty array `[]` (no resources yet, database is fresh)
**Bad:** "Server not found" error

### Task 1.3: Search for Memory Tools
Try to find memory MCP tools:
```
MCPSearch(query="create_entities")
```

**Expected:** Should find `mcp__memory__create_entities` tool

---

## Phase 2: Test Memory Functionality (10 minutes)

### Task 2.1: Create Test Observation
Have a conversation with unique content:
```
User: "Tell me about the three-tier architecture pattern with
specific focus on the data layer isolation principle."

Claude: [Explains architecture]
```

### Task 2.2: Wait for Capture
Wait 30-60 seconds for automatic observation capture.

### Task 2.3: Search for Observation
```
/mem-search architecture pattern
```

**Expected:** Should return observation from the test conversation
**Bad:** "Command not found" or "No results"

---

## Phase 3: Fix if Not Working (30-60 minutes)

### Scenario A: Server Not Connected

**Symptoms:**
- `claude mcp list` doesn't show memory
- ListMcpResourcesTool returns "Server not found"

**Fix Steps:**
1. Check `.claude.json` syntax (valid JSON?)
2. Verify npx is installed: `npx --version`
3. Check for errors in Claude Code logs
4. Try manual server start: `npx -y @modelcontextprotocol/server-memory --memory-path C:\Users\layden\.claude-memory`

### Scenario B: Server Connected but Tools Not Available

**Symptoms:**
- `claude mcp list` shows memory ✓
- But MCPSearch finds no tools
- ListMcpResourcesTool returns empty array

**Fix Steps:**
1. Check MCP permissions in `/permissions`
2. Verify tools aren't blocked by permission rules
3. Try enabling memory server explicitly: `/mcp enable memory`

### Scenario C: Tools Available but Search Doesn't Work

**Symptoms:**
- Memory tools exist (create_entities, search_nodes)
- Can create observations manually
- But `/mem-search` command doesn't work

**Fix Steps:**
1. Verify `/mem-search` command exists as slash command
2. Check if it's a plugin-provided command
3. Test memory tools directly instead of slash command

---

## Phase 4: Document Final Configuration (15 minutes)

### Task 4.1: Update Documentation Files

**Files to update:**
1. `docs/CLAUDE_MEM_GUIDE.md`
   - Add "Prerequisites" section
   - Add "MCP Server Setup" instructions
   - Update with actual setup steps

2. `docs/MIGRATION_GUIDE.md`
   - Add Phase 0: MCP Server Configuration
   - Update troubleshooting section

3. `SESSION_PROTOCOL.md`
   - Add memory server to architecture diagram
   - Document MCP configuration location

### Task 4.2: Create Verification Script

**File:** `scripts/verify-memory-server.py`

```python
#!/usr/bin/env python3
"""Verify claude-mem hybrid memory system is operational"""

import subprocess
import json
import sys

def check_mcp_list():
    """Check if memory server appears in MCP list"""
    result = subprocess.run(
        ["claude", "mcp", "list"],
        capture_output=True,
        text=True
    )
    return "memory" in result.stdout

def check_config():
    """Check if memory server is in .claude.json"""
    import os
    config_path = os.path.expanduser("~/.claude.json")
    with open(config_path) as f:
        config = json.load(f)
    return "memory" in config.get("mcpServers", {})

def main():
    print("🔍 Verifying Memory Server Setup...")

    # Check 1: Configuration
    if check_config():
        print("✅ Memory server configured in ~/.claude.json")
    else:
        print("❌ Memory server NOT in configuration")
        return 1

    # Check 2: MCP Connection
    if check_mcp_list():
        print("✅ Memory server connected")
    else:
        print("❌ Memory server NOT connected")
        print("   Try restarting Claude Code")
        return 1

    print("\n✅ Memory server is operational!")
    print("\nNext steps:")
    print("1. Have a conversation with technical content")
    print("2. Wait 60 seconds for observation capture")
    print("3. Test search: /mem-search <your topic>")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

---

## Acceptance Criteria

- [ ] `claude mcp list` shows memory server as connected
- [ ] ListMcpResourcesTool(server="memory") returns empty array (not error)
- [ ] Memory tools are discoverable via MCPSearch
- [ ] Test observation can be created and searched
- [ ] Documentation updated with correct setup steps
- [ ] Verification script created and tested

---

## Rollback Plan

If memory server causes issues:

1. **Quick disable:** Edit `~/.claude.json` and remove memory section
2. **Restart:** Close and reopen Claude Code
3. **Verify:** `claude mcp list` should no longer show memory

---

## Time Estimate

- Phase 1 (Verification): 5 minutes
- Phase 2 (Testing): 10 minutes
- Phase 3 (Fixes if needed): 30-60 minutes
- Phase 4 (Documentation): 15 minutes

**Total:** 60-90 minutes

---

**Created:** 2025-12-22
**Status:** Ready to Execute
**Priority:** High (blocking hybrid memory functionality)
