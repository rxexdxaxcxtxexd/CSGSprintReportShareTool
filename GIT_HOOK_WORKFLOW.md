# Git Hook-Based Checkpoint Workflow

## 🎯 **Overview**

The session tracking system now uses a **unified git workflow** where checkpoints are automatically created after every git commit via a post-commit hook. This separates checkpoint creation from committing, giving you full control over your git workflow while maintaining seamless session continuity.

---

## 🔄 **How It Works**

### **Old Workflow** (Before Git Hooks):
```
python save-session.py → creates checkpoint → auto-commits everything
```
- Auto-commit was opinionated
- User had limited control over commit message and staging
- Mixed session tracking with version control

### **New Workflow** (Unified with Git Hooks):
```
python save-session.py → creates checkpoint → stages changes

User: git commit -m "Your message"

post-commit hook → updates checkpoint with commit info → registers in index
```

**Benefits:**
- ✅ Full control over git workflow (stage, commit message, etc.)
- ✅ Checkpoints for ALL commits (not just save-session.py commits)
- ✅ Automatic linking of checkpoints to commits
- ✅ Follows standard git best practices
- ✅ Works with any git workflow (feature branches, rebasing, etc.)

---

## 📥 **Installation**

### **Step 1: Install the Post-Commit Hook**

```bash
cd ~/Projects/your-project
python scripts/install-hooks.py
```

**What this does:**
- Creates `.git/hooks/post-commit` in your repository
- Configures the hook to call `post-commit-handler.py`
- Makes the hook executable (on Unix systems)
- Tests installation (optional: use `--test` flag)

**Output:**
```
======================================================================
✓ POST-COMMIT HOOK INSTALLED SUCCESSFULLY
======================================================================
Repository: /Users/layden/Projects/your-project
Hook file:  /Users/layden/Projects/your-project/.git/hooks/post-commit

What happens now:
  • Every git commit will automatically create a session checkpoint
  • Checkpoints will be linked to commits via commit hash
  • save-session.py now stages changes (user commits manually)

Next steps:
  1. Test the hook: python scripts/install-hooks.py --test
  2. Make a commit: git commit -m "Test commit"
  3. Check checkpoint: python scripts/resume-session.py
======================================================================
```

### **Step 2: Verify Installation**

```bash
# Test the hook
python scripts/install-hooks.py --test

# Check that the hook file exists
ls -la .git/hooks/post-commit  # Unix
dir .git\hooks\post-commit      # Windows
```

---

## 🚀 **Usage**

### **Typical Workflow**

**1. Create a Checkpoint:**
```bash
python scripts/save-session.py --quick
```

**Output:**
```
======================================================================
SESSION CHECKPOINT CREATED
======================================================================

Checkpoint: checkpoint-20251117-143000.json
Log:        session-20251117-143000.md

Files tracked: 5
Resume points: 3
Next steps:    4

----------------------------------------------------------------------
NEXT STEP: Create Git Commit
----------------------------------------------------------------------

To finalize this checkpoint, commit your changes:
  git add .
  git commit -m "Your commit message"

The post-commit hook will automatically link this checkpoint
to your commit and update it with commit information.

Need to install the hook? Run:
  python scripts/install-hooks.py

To resume in a new session:
  python scripts/resume-session.py
======================================================================
```

**2. Commit Your Changes:**
```bash
# Stage files (already done by save-session.py, but you can adjust)
git add .

# Create commit with your message
git commit -m "Implement feature X with tests and documentation"
```

**3. Hook Automatically Runs:**
```
✓ Session checkpoint created: checkpoint-20251117-143000.json
```

**What the hook does:**
- Collects commit information (hash, branch, remote, message, files)
- Updates the checkpoint with git commit metadata
- Re-registers the checkpoint in session index
- Updates active project state

**4. Resume Later:**
```bash
python scripts/resume-session.py
```

**Now shows commit information:**
```
======================================================================
📋 Session Checkpoint

[PROJECT]
  Name:   your-project
  Path:   /Users/layden/Projects/your-project
  Remote: github.com/user/your-project
  Branch: main

[GIT COMMIT]
  Hash: a3f8e9c2
  Branch: main
  Remote: github.com/user/your-project

[SESSION CONTEXT]
  Implement feature X with tests and documentation
...
======================================================================
```

---

## 🎨 **Workflow Examples**

### **Example 1: Feature Development**

```bash
# Start working
cd ~/Projects/my-app

# Work on feature...
# Edit files, write code, run tests

# Create checkpoint
python scripts/save-session.py --quick
# Checkpoint created, files staged

# Commit with descriptive message
git commit -m "Add user authentication with JWT tokens

- Implement login/logout endpoints
- Add JWT token generation and validation
- Write unit tests for auth service
- Update API documentation"

# Hook runs automatically, links checkpoint to commit
```

### **Example 2: Multiple Commits in One Session**

```bash
# Feature work in progress
vim src/feature.py
git add src/feature.py
git commit -m "Add feature scaffolding"
# → Checkpoint created automatically

# Continue work
vim src/feature.py
vim tests/test_feature.py
git add src/ tests/
git commit -m "Implement feature logic and tests"
# → Another checkpoint created automatically

# Final polish
vim README.md
git add README.md
git commit -m "Update documentation"
# → Third checkpoint created automatically

# View all checkpoints for this session
python scripts/resume-session.py list
```

### **Example 3: Emergency Fix**

```bash
# Urgent bug fix needed
cd ~/Projects/production-app

# Fix the bug
vim src/critical_module.py

# Quick commit (hook creates checkpoint automatically)
git add src/critical_module.py
git commit -m "HOTFIX: Fix null pointer exception in payment processing"

# Push immediately
git push origin main

# Checkpoint is created and linked to commit
# Can resume later if needed
```

---

## 🔧 **Configuration**

### **Hook Location**
```
.git/hooks/post-commit
```

### **Hook Handler**
```
scripts/post-commit-handler.py
```

### **Checkpoint Storage**
```
~/.claude-sessions/checkpoints/
```

### **Session Index**
```
~/.claude/session-index.json
```

### **Active Project State**
```
~/.claude/active-project.json
```

---

## 🛠️ **Maintenance**

### **Uninstall the Hook**

```bash
python scripts/install-hooks.py --uninstall
```

This removes the post-commit hook. Existing checkpoints are not affected.

### **Reinstall the Hook**

```bash
python scripts/install-hooks.py
```

### **Install in Multiple Repositories**

```bash
# Install in specific repo
python scripts/install-hooks.py --repo ~/Projects/project-A

# Install in another repo
python scripts/install-hooks.py --repo ~/Projects/project-B
```

### **Update the Hook**

If `post-commit-handler.py` is updated, reinstall the hook:

```bash
python scripts/install-hooks.py
# Choose "y" to overwrite existing hook
```

---

## 🧪 **Testing**

### **Test Hook Installation**

```bash
python scripts/install-hooks.py --test
```

This creates a test commit and verifies the hook works correctly.

### **Manual Hook Test**

```bash
# Create test file
echo "test" > .test-file.txt

# Commit
git add .test-file.txt
git commit -m "Test commit"

# Check checkpoint was created
python scripts/resume-session.py

# Clean up
rm .test-file.txt
git add .test-file.txt
git commit -m "Remove test file"
```

---

## 🔍 **Troubleshooting**

### **Problem: Hook Not Running**

**Symptoms:**
- Commit succeeds but no checkpoint message
- No checkpoint created after commit

**Solutions:**
1. Check hook exists: `ls -la .git/hooks/post-commit`
2. Check hook is executable (Unix): `chmod +x .git/hooks/post-commit`
3. Verify Python path in hook is correct
4. Check hook output: `cat .git/hooks/post-commit`
5. Test manually: `python scripts/post-commit-handler.py`

### **Problem: Hook Fails Silently**

**Symptoms:**
- Commit succeeds but checkpoint creation fails
- No error message shown

**Solutions:**
1. Check stderr: Hooks log errors to stderr
2. Run handler manually to see full error:
   ```bash
   python scripts/post-commit-handler.py
   ```
3. Check Python version: Must be Python 3.6+
4. Verify all imports work:
   ```bash
   python -c "from scripts.checkpoint_utils import *"
   ```

### **Problem: Windows Hook Execution Issues**

**Symptoms:**
- Hook doesn't run on Windows
- "command not found" errors

**Solutions:**
1. Verify Python is in PATH:
   ```cmd
   python --version
   ```
2. Check hook shebang is correct: `#!/usr/bin/env python3`
3. Try explicit Python path in hook:
   ```python
   import sys
   sys.executable  # Use this path in hook
   ```

### **Problem: Checkpoint Not Linked to Commit**

**Symptoms:**
- Checkpoint created but no git_commit_hash field
- Resume shows "no commit info"

**Solutions:**
1. Hook may have failed to update checkpoint
2. Check checkpoint file manually:
   ```bash
   cat ~/.claude-sessions/checkpoints/checkpoint-YYYYMMDD-HHMMSS.json | grep git_commit_hash
   ```
3. Manually update checkpoint:
   ```bash
   python -c "
   from scripts.checkpoint_utils import *
   from pathlib import Path

   base_dir = Path.cwd()
   commit_hash = get_git_commit_hash(base_dir)
   branch = get_git_branch(base_dir)
   remote = get_git_remote_url(base_dir)

   checkpoint_path = Path('~/.claude-sessions/checkpoints/checkpoint-YYYYMMDD-HHMMSS.json').expanduser()
   update_checkpoint_with_git_info(checkpoint_path, commit_hash, branch, remote)
   "
   ```

---

## 📊 **Comparison: Old vs New Workflow**

| Feature | Old Workflow | New Workflow (Git Hooks) |
|---------|--------------|--------------------------|
| **Checkpoint Creation** | `save-session.py` only | Every git commit |
| **Commit Control** | Auto-commit (opinionated) | Full user control |
| **Commit Message** | Auto-generated | User-defined |
| **Staging** | Auto-stages everything | User controls staging |
| **Git Workflow** | Interferes with standard git | Integrates seamlessly |
| **Feature Branches** | Creates commits on current branch | Works with any branch |
| **Rebasing** | Problematic | Fully compatible |
| **Coverage** | Only save-session.py runs | All commits tracked |
| **Team Collaboration** | Commits show "auto-generated" | Natural commit history |

---

## 💡 **Best Practices**

### **1. Install Hook in All Projects**

```bash
# Install once per repository
cd ~/Projects/project-A && python scripts/install-hooks.py
cd ~/Projects/project-B && python scripts/install-hooks.py
cd ~/Projects/project-C && python scripts/install-hooks.py
```

### **2. Use Descriptive Commit Messages**

The commit message becomes part of the checkpoint description:

```bash
# Good: Descriptive message
git commit -m "Add user authentication with JWT tokens and session management"

# Less ideal: Generic message
git commit -m "Update files"
```

### **3. Commit Regularly**

Each commit creates a checkpoint, so commit frequently to maintain fine-grained session history:

```bash
# Good: Atomic commits
git commit -m "Add login endpoint"
git commit -m "Add logout endpoint"
git commit -m "Add session validation middleware"

# Less ideal: One giant commit
git commit -m "Add all auth stuff"
```

### **4. Review Checkpoints**

```bash
# View all project checkpoints
python scripts/resume-session.py projects

# View latest checkpoint
python scripts/resume-session.py

# List all checkpoints
python scripts/resume-session.py list
```

### **5. Keep Hook Updated**

When you update `post-commit-handler.py`, reinstall the hook:

```bash
python scripts/install-hooks.py
```

---

## 🔮 **Advanced Usage**

### **Query Checkpoints Across Projects**

```python
from scripts.session_index import SessionIndex
from datetime import datetime, timedelta

index = SessionIndex()

# Get checkpoints from last 7 days
week_ago = (datetime.now() - timedelta(days=7)).isoformat()
recent = index.query_checkpoints({
    'date_from': week_ago,
    'min_file_changes': 3
})

for checkpoint in recent:
    print(f"{checkpoint['project_name']}: {checkpoint['description']}")
    print(f"  Files: {checkpoint['file_change_count']}, Commit: {checkpoint.get('git_commit_hash', 'N/A')[:8]}")
```

### **Find Checkpoints by Commit Hash**

```python
from scripts.session_index import SessionIndex

index = SessionIndex()

# Search for specific commit
commit_hash = "a3f8e9c2"
results = index.query_checkpoints({
    'git_commit_hash': commit_hash
})

if results:
    print(f"Found checkpoint for commit {commit_hash}")
    print(f"Project: {results[0]['project_name']}")
    print(f"Description: {results[0]['description']}")
```

---

## ✨ **Key Benefits**

1. **✅ Automatic** - Every commit creates a checkpoint (no manual intervention)
2. **✅ Seamless** - Integrates with standard git workflow
3. **✅ Complete** - Captures all commits, not just save-session.py runs
4. **✅ Non-Intrusive** - Doesn't interfere with commit flow (hook failures don't break commits)
5. **✅ Portable** - Works across branches, machines, and team members
6. **✅ Maintainable** - Easy to install, update, and remove
7. **✅ Flexible** - Compatible with any git workflow (rebasing, cherry-picking, etc.)

---

## 📝 **Migration Guide**

### **For Existing Users**

If you've been using the old auto-commit workflow:

**1. Install the hook:**
```bash
python scripts/install-hooks.py
```

**2. Update your workflow:**
- Old: `python save-session.py --quick` (creates checkpoint AND commits)
- New: `python save-session.py --quick` (creates checkpoint) → `git commit -m "..."` (hook adds commit info)

**3. Existing checkpoints:**
- Old checkpoints without commit info remain valid
- New checkpoints will have full git integration
- No migration needed

---

**Implementation Date:** November 17, 2025
**Status:** Production Ready
**Compatibility:** All existing checkpoints remain valid
