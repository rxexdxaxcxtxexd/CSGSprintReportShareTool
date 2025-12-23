# Context-Aware Memory Trigger System

## Overview

The Context-Aware Memory Trigger System is an intelligent feature that automatically queries your MCP memory graph during Claude Code sessions when relevant context is needed. Think of it as having an assistant that remembers past decisions, architectures, and important details, automatically surfacing them at the right moment.

### Why Memory Triggers?

When working on complex projects across multiple sessions, it's easy to forget:
- **Past decisions**: "Why did we choose this approach?"
- **Architecture patterns**: "How does our authentication system work?"
- **Important entities**: "What was that critical file I modified last week?"
- **Pending tasks**: "What was I working on before the session ended?"

Memory triggers solve this by **proactively** loading relevant context from your knowledge graph without manual queries.

### Key Benefits

✅ **Zero manual work** - Triggers fire automatically based on your workflow
✅ **Smart timing** - Context appears exactly when you need it
✅ **Low overhead** - Uses less than 2% of your context window (~850-2,050 tokens/session)
✅ **Graceful degradation** - Works fine even if MCP is unavailable
✅ **Fully configurable** - Enable/disable detectors, adjust priorities

---

## Quick Start

### Prerequisites

1. **MCP Memory Server** must be configured (`.claude/mcp/mcp.json`)
2. **Python 3.8+** installed
3. **Memory graph populated** with entities and observations

### Basic Usage

The memory trigger system runs automatically during checkpoints and context monitoring. You can also test it manually:

```bash
# Check system status
python scripts/memory_trigger.py --stats

# Test triggers without MCP calls
python scripts/memory_trigger.py --prompt "What is UserManager?" --test

# Manual trigger (with MCP)
python scripts/memory_trigger.py --prompt "remember our architecture decision"
```

### First-Time Setup

1. **Verify configuration exists**:
   ```bash
   ls ~/.claude/memory-trigger-config.json
   ```
   If not found, the system will create a default configuration automatically.

2. **Test your setup**:
   ```bash
   python scripts/memory_trigger.py --stats
   ```
   Expected output:
   ```
   === Memory Trigger Statistics ===
   Session ID: <uuid>
   Tokens Used: 0 / 5000
   Detectors: 4 enabled / 4 registered
   ```

3. **Run a checkpoint** to see memory extraction in action:
   ```bash
   python scripts/checkpoint.py --quick
   ```
   Look for: `[2.5/3] Extracting memory insights...`

---

## How It Works

### The 4 Detectors

The system uses four specialized detectors that analyze your prompts and session state:

#### 1. Project Switch Detector (Priority 1)

**Triggers When**: You switch git repositories or branches
**What It Loads**: Project-specific decisions, architecture patterns, design rationale
**Token Cost**: ~200 tokens per trigger
**Frequency**: 1-2 times per session

**Example Scenarios**:
- Switching from `feature-auth` branch to `main` branch
- Opening a different git repository
- Changing project directories

**What You'll See**:
```
[PROJECT_CONTEXT] Project switched to: my-app (main branch)
- Decision: Use JWT for authentication
- Architecture: REST API with Express.js
- Pattern: Repository pattern for data access
```

#### 2. Keyword Detector (Priority 2)

**Triggers When**: Your prompt contains trigger keywords like "remember", "decided", "why did we"
**What It Loads**: Relevant past decisions and contextual information
**Token Cost**: ~150 tokens per trigger
**Frequency**: 3-6 times per session

**Trigger Keywords**:
- **Memory**: "remember", "recall", "previously", "earlier"
- **Decisions**: "why did we", "decided", "chose", "selected"
- **Architecture**: "architecture", "design", "pattern"
- **Problems**: "issue", "bug", "error", "blocker"

**Example**:
```
Your prompt: "Remember why we decided to use PostgreSQL?"

[KEYWORD TRIGGER] Matched: 'remember', 'decided'
- Decision (2025-11-15): Chose PostgreSQL for ACID compliance
- Rationale: Need strong consistency for financial transactions
- Alternative considered: MongoDB (rejected due to transaction limitations)
```

#### 3. Entity Mention Detector (Priority 3)

**Triggers When**: You mention known entities (files, classes, modules) from your memory graph
**What It Loads**: Entity details and relationships
**Token Cost**: ~100 tokens per trigger
**Frequency**: 2-4 times per session

**Example Scenarios**:
- Mentioning "UserManager" class
- Referring to "auth.py" file
- Discussing "PaymentService" module

**How It Works**:
- Maintains a cache of entity names (refreshed every 5 minutes)
- Uses fuzzy matching (handles typos, case-insensitive)
- Matches partial names ("payment service" → "PaymentService")

**Example**:
```
Your prompt: "How does the UserManager work?"

[ENTITY_DETAILS] Matched entity: UserManager
- Type: Class
- Location: src/auth/user_manager.py:45
- Purpose: Handles user authentication and session management
- Related: SessionStore, AuthMiddleware
```

#### 4. Token Threshold Detector (Priority 4)

**Triggers When**: Your context usage reaches 100K or 150K tokens (50% or 75% of window)
**What It Loads**: Pending decisions, incomplete tasks, next steps
**Token Cost**: ~175 tokens per trigger
**Frequency**: 0-2 times per session

**Thresholds**:
- **100,000 tokens (50%)**: First checkpoint - capture important context
- **150,000 tokens (75%)**: Second checkpoint - prepare for session wrap-up

**Example**:
```
[THRESHOLD_CHECK] Token usage: 100,500 / 200,000 (50.3%)
Pending items from memory:
- TODO: Complete authentication tests
- DECISION NEEDED: Choose caching strategy (Redis vs in-memory)
- IN PROGRESS: Refactoring payment module
```

### Detector Priority Order

Detectors execute in **priority order** (1 → 2 → 3 → 4) with **short-circuit evaluation**:
- Once a detector triggers, the search stops
- Higher priority detectors run first
- This keeps overhead low and responses fast

---

## Configuration

### Configuration File

**Location**: `.claude/memory-trigger-config.json`

### Full Configuration Schema

```json
{
  "version": "1.0",
  "detectors": {
    "project_switch": {
      "enabled": true,
      "priority": 1,
      "detect_branch_switch": true,
      "major_branches": ["main", "master", "develop"]
    },
    "keyword": {
      "enabled": true,
      "priority": 2,
      "keywords": {
        "memory": ["remember", "recall", "previously"],
        "decision": ["why did we", "decided", "chose"],
        "architecture": ["architecture", "design", "pattern"],
        "problem": ["issue", "bug", "error"]
      }
    },
    "entity_mention": {
      "enabled": true,
      "priority": 3,
      "min_entity_length": 2,
      "partial_match_threshold": 0.7
    },
    "token_threshold": {
      "enabled": true,
      "priority": 4,
      "thresholds": [100000, 150000]
    }
  },
  "budget": {
    "max_tokens_per_session": 5000,
    "max_tokens_per_trigger": 500,
    "warning_threshold": 4500
  },
  "cache": {
    "entity_refresh_minutes": 5,
    "query_cache_minutes": 10,
    "max_cache_size_kb": 200
  },
  "mcp": {
    "connection_timeout_seconds": 5,
    "query_timeout_seconds": 3,
    "retry_attempts": 2
  },
  "logging": {
    "level": "INFO",
    "file": ".claude/memory-trigger.log",
    "max_size_mb": 10
  }
}
```

### Common Configuration Changes

#### Disable a Detector

```json
{
  "detectors": {
    "entity_mention": {
      "enabled": false  // Disable entity mention detector
    }
  }
}
```

#### Adjust Token Budget

```json
{
  "budget": {
    "max_tokens_per_session": 10000  // Increase from default 5000
  }
}
```

#### Change Token Thresholds

```json
{
  "detectors": {
    "token_threshold": {
      "thresholds": [80000, 120000, 160000]  // Three checkpoints instead of two
    }
  }
}
```

#### Add Custom Keywords

```json
{
  "detectors": {
    "keyword": {
      "keywords": {
        "custom": ["my custom phrase", "special keyword"]
      }
    }
  }
}
```

---

## Integration

### Checkpoint Workflow Integration

Memory extraction runs automatically during checkpoints:

```bash
python scripts/checkpoint.py --quick
```

**What Happens**:
1. Step 1: Save session log
2. Step 2: Update CLAUDE.md
3. **Step 2.5: Extract memory insights** ← Memory triggers run here
4. Step 3: Display summary

**Output Example**:
```
[2/3] Update CLAUDE.md...
[OK] CLAUDE.md synchronized with checkpoint

[2.5/3] Extracting memory insights...
[DEBUG] Trigger fired: keyword_match (confidence: 0.85)
[OK] Memory insights extracted

[3/3] Session summary:
...
```

### Context Monitor Integration

Memory suggestions appear when token usage is high:

```bash
python scripts/context-monitor.py
```

**Example Output** (at warning threshold):
```
Context Usage (APPROXIMATION):
  Estimated Tokens: ~175,000 / 200,000
  Usage: ~87.5%
  Remaining: ~25,000 tokens (~12.5%)

[========================================----------]

⚠ WARNING: Context usage above 87%
Recommendation: Create checkpoint now to preserve context

  Consider running checkpoint to preserve memory context
```

---

## Troubleshooting

### No Detectors Registered

**Problem**: `python scripts/memory_trigger.py --stats` shows "0 detectors registered"

**Possible Causes**:
1. Configuration file missing or corrupted
2. Import errors in detector modules
3. Python path issues

**Solutions**:
```bash
# Check if config file exists
ls ~/.claude/memory-trigger-config.json

# If missing, create default config
python scripts/memory_trigger.py --stats  # Auto-creates default

# Check for import errors
python -c "from memory_detectors.keyword_detector import KeywordDetector"
python -c "from memory_detectors.entity_mention_detector import EntityMentionDetector"
```

### MCP Server Unavailable

**Problem**: Memory queries fail with "MCP unavailable"

**This is normal!** The system degrades gracefully:
- Triggers still evaluate (no errors)
- Memory queries return empty results
- Operations continue normally

**To Fix MCP Connection**:
```bash
# Check MCP configuration
cat ~/.claude/mcp/mcp.json

# Verify memory database exists
ls ~/.claude-memory/

# Test MCP connection
python scripts/memory_client.py  # If you have a test script
```

### High Token Usage

**Problem**: Token budget warning appears frequently

**Solution**: Adjust budget in configuration:
```json
{
  "budget": {
    "max_tokens_per_session": 10000  // Increase limit
  }
}
```

Or disable less critical detectors:
```json
{
  "detectors": {
    "entity_mention": {
      "enabled": false  // Reduce trigger frequency
    }
  }
}
```

### Triggers Not Firing

**Problem**: Expected triggers don't fire

**Debugging Steps**:
1. **Check configuration**:
   ```bash
   python scripts/memory_trigger.py --stats
   # Verify detectors are enabled
   ```

2. **Test in isolation**:
   ```bash
   python scripts/memory_trigger.py --prompt "remember our decision" --test
   # Should show which detector would trigger
   ```

3. **Check logs**:
   ```bash
   tail -f ~/.claude/memory-trigger.log
   # Look for "DEBUG" entries showing evaluation
   ```

4. **Verify prompt matches trigger patterns**:
   - Keyword detector: Does prompt contain trigger keywords?
   - Entity detector: Are entities in your memory graph?
   - Threshold detector: Is token count high enough?

### Cache Issues

**Problem**: Entity names not updating

**Solution**: Force cache refresh:
```bash
# Delete cache file
rm ~/.claude/memory-cache.json

# Next trigger will rebuild cache
python scripts/memory_trigger.py --prompt "test"
```

---

## FAQ

### Q: How much overhead does this add?

**A**: Very little! The system uses 850-2,050 tokens per session, which is 0.4-1.0% of the 200K context window. That's less than a single medium-sized code file.

### Q: Can I disable it completely?

**A**: Yes! Disable all detectors in the configuration:
```json
{
  "detectors": {
    "project_switch": {"enabled": false},
    "keyword": {"enabled": false},
    "entity_mention": {"enabled": false},
    "token_threshold": {"enabled": false}
  }
}
```

### Q: What happens if MCP is down?

**A**: The system degrades gracefully - triggers still evaluate but memory queries return empty results. Your session continues normally without any errors.

### Q: Can I add custom trigger keywords?

**A**: Yes! Edit `.claude/memory-trigger-config.json`:
```json
{
  "detectors": {
    "keyword": {
      "keywords": {
        "my_category": ["my phrase", "another keyword"]
      }
    }
  }
}
```

### Q: How does caching work?

**A**:
- **Entity names**: Cached for 5 minutes (configurable)
- **Query results**: Cached for 10 minutes with LRU eviction
- **Cache storage**: `~/.claude/memory-cache.json`
- **Thread-safe**: Multiple processes can access safely

### Q: Can I see which detector triggered?

**A**: Yes! Run with stats mode:
```bash
python scripts/memory_trigger.py --prompt "your prompt" --test
```
Output shows which detector would trigger and why.

### Q: What's the token budget for?

**A**: To prevent excessive MCP queries from consuming too much of your context window. Default is 5,000 tokens/session (2.5% of window). Once exhausted, no more queries until next session.

### Q: How do I know if it's working?

**A**:
1. Run checkpoint: Should see `[2.5/3] Extracting memory insights...`
2. Check context monitor: Memory suggestions appear at warning/critical thresholds
3. View stats: `python scripts/memory_trigger.py --stats` shows detectors and usage

### Q: Can I change detector priorities?

**A**: Priorities are designed for optimal performance (project context first, thresholds last). Changing them isn't recommended, but you can disable detectors you don't need.

---

## Best Practices

### 1. Populate Your Memory Graph

The system is only as good as your memory graph. Regularly add:
- Important decisions with rationale
- Architecture patterns and conventions
- Key entities (files, classes, modules)
- Pending tasks and blockers

### 2. Use Descriptive Entity Names

Good entity names improve fuzzy matching:
- ✅ "UserAuthenticationManager"
- ✅ "payment_processing_service"
- ❌ "mgr"
- ❌ "svc1"

### 3. Monitor Token Usage

Check stats occasionally:
```bash
python scripts/memory_trigger.py --stats
```

If you're hitting the budget limit frequently, consider:
- Increasing the limit
- Disabling low-value detectors
- Optimizing your memory graph queries

### 4. Test Before Relying On It

Before a critical session:
```bash
# Verify system is working
python scripts/memory_trigger.py --stats
python scripts/memory_trigger.py --prompt "test query" --test
```

### 5. Keep Configuration Simple

Start with defaults. Only customize if needed. Over-configuration can reduce effectiveness.

---

## Advanced Usage

### Manual Triggers

For specific memory queries:
```bash
python scripts/memory_trigger.py --prompt "what were our database decisions?"
```

### Debug Mode

Enable verbose logging:
1. Edit `.claude/memory-trigger-config.json`:
   ```json
   {
     "logging": {
       "level": "DEBUG"
     }
   }
   ```

2. Watch logs:
   ```bash
   tail -f ~/.claude/memory-trigger.log
   ```

### Integration with Custom Scripts

```python
from memory_trigger_engine import MemoryTriggerEngine

# Initialize engine
engine = MemoryTriggerEngine()

# Evaluate trigger
result = engine.evaluate_triggers("Remember our auth decision?", {})

if result:
    # Query memory
    memory = engine.query_memory(result)
    print(f"Found {len(memory.get('entities', []))} relevant entities")
```

---

## Support

### Getting Help

1. **Documentation**: See `SESSION_PROTOCOL.md` for integration details
2. **Logs**: Check `~/.claude/memory-trigger.log` for debugging
3. **Test Mode**: Use `--test` flag to see what would trigger without MCP calls

### Reporting Issues

When reporting issues, include:
- Output of `python scripts/memory_trigger.py --stats`
- Relevant lines from `~/.claude/memory-trigger.log`
- Your configuration file (`.claude/memory-trigger-config.json`)
- Description of expected vs actual behavior

---

## Version History

**v1.0** (2025-12-23)
- Initial release
- 4 core detectors (project_switch, keyword, entity_mention, token_threshold)
- Checkpoint and context monitor integration
- Configuration system
- Cache infrastructure
- Token budget enforcement

---

**Thank you for using the Context-Aware Memory Trigger System!**

For technical details and developer documentation, see `docs/MEMORY_TRIGGERS_TECHNICAL.md` (coming in Phase 4).
