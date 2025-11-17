# Phase 2 Complete: Project Switch Detection & Prompt

## 🎯 **What Was Implemented**

Phase 2 adds intelligent project switch detection with user prompts to ensure no work is lost when switching between projects.

---

## **Phase 2.1: ProjectTracker Module** ✅

**New File:** `scripts/project_tracker.py` (~290 lines)

### **Core Features:**

**1. Active Project State Management**
```python
# Stored in: ~/.claude/active-project.json
{
  "project": {
    "absolute_path": "C:\\Users\\layden\\Projects\\project-A",
    "name": "project-A",
    "git_remote_url": "https://github.com/user/project-A.git",
    "git_branch": "main",
    "git_head_hash": "a3f8e9c2..."
  },
  "has_uncommitted_changes": true,
  "last_checkpoint": "2025-11-17T14:30:00",
  "updated_at": "2025-11-17T15:45:00"
}
```

**2. Project Comparison Logic**
- **Primary matching:** Git remote URL (portable across machines)
- **Fallback matching:** Absolute path (local repos)
- **Smart handling:** Detects remote URL changes

**3. Uncommitted Changes Detection**
- Runs `git status --porcelain`
- Returns true if any staged/unstaged changes exist

**4. Utility Functions:**
- `get_project_summary()` - Human-readable project description
- `format_time_ago()` - Relative timestamps ("2 hours ago")
- `projects_match()` - Determines if two projects are the same

---

## **Phase 2.2: Switch Detection Integration** ✅

**Modified File:** `scripts/save-session.py` (Lines 1122-1184)

### **Implementation Flow:**

```
1. User runs save-session.py
2. Initialize SessionSaver → sets base_dir
3. Collect current project metadata
4. Check if active project exists
5. Compare current vs. active
   ├─ IF MATCH → Continue normally
   └─ IF DIFFERENT → Trigger switch handling (Phase 2.3)
```

**Key Code:**
```python
# Collect current project metadata
current_project = saver._collect_project_metadata()

# Check for project switch
tracker = ProjectTracker()
has_switched, active_state = tracker.detect_switch(current_project)

if has_switched and active_state:
    # Project switch detected - prompt user
    choice = handle_project_switch(current_project, active_state)
    # Handle user's choice...
```

---

## **Phase 2.3: Checkpoint-Before-Switch Prompt** ✅

**Modified File:** `scripts/save-session.py` (Lines 254-308)

### **User Experience:**

```
======================================================================
⚠️ PROJECT SWITCH DETECTED
======================================================================

Previous project: project-A (github.com/user/project-A, branch: main)
Current project:  project-B (github.com/user/project-B, branch: feature-x)

⚠️  WARNING: You have uncommitted work in the previous project!
   Last checkpoint: 2 hours ago

What would you like to do?
  1. Create checkpoint for previous project first (recommended)
  2. Discard previous project changes and track current project
  3. Cancel (don't create any checkpoint)

Your choice (1-3): _
```

### **Option 1: Checkpoint Previous Project**

**Flow:**
1. User selects option 1
2. System creates new SessionSaver for previous project
3. Collects changes from previous project directory
4. Creates checkpoint + commit for previous project
5. Displays success message
6. Continues with current project checkpoint

**Output:**
```
📦 Creating checkpoint for previous project...
Collecting changes from project-A...
  Found 12 file change(s) in previous project

======================================================================
PROJECT CONTEXT
======================================================================
  Directory: C:\Users\layden\Projects\project-A
  Git Repo:  github.com/user/project-A
  Branch:    main
  Auto-commit: ENABLED
======================================================================

[... checkpoint creation ...]

✓ Previous project checkpointed successfully!

Now continuing with current project: project-B
```

### **Option 2: Discard Previous Changes**

**Flow:**
1. User selects option 2
2. System asks for confirmation: "Type 'yes' to confirm"
3. If confirmed: Updates active project, continues with current
4. If not confirmed: Returns to choice menu

**Safety:**
- Requires explicit "yes" confirmation
- Warns about data loss
- Gives user chance to reconsider

### **Option 3: Cancel**

**Flow:**
1. User selects option 3 (or presses Ctrl+C)
2. System exits without creating any checkpoint
3. Active project state remains unchanged

---

## **Active Project State Updates**

### **When State is Updated:**

**1. Before Switch Handling (Temporary):**
```python
# Line 1180-1184
tracker.set_active_project(
    current_project,
    has_uncommitted=saver.has_uncommitted_changes(saver.base_dir),
    last_checkpoint=None
)
```

**2. After Successful Checkpoint (Final):**
```python
# Line 1248-1252
tracker.set_active_project(
    current_project,
    has_uncommitted=False,  # Just checkpointed
    last_checkpoint=datetime.now().isoformat()
)
```

---

## **New Methods Added**

### **SessionSaver.has_uncommitted_changes()**
**File:** `scripts/save-session.py` (Lines 463-487)

**Purpose:** Check if directory has uncommitted git changes

**Usage:**
```python
has_uncommitted = saver.has_uncommitted_changes(Path("/path/to/project"))
# Returns: True if git status shows changes, False otherwise
```

---

## 📊 **Changes Summary**

### **New Files:**
- `scripts/project_tracker.py` - 290 lines (complete new module)

### **Modified Files:**
- `scripts/save-session.py` - +150 lines (switch detection, prompt, integration)

### **Total:** ~440 lines added

---

## 🧪 **Testing Scenarios**

### **Test 1: First Run (No Active Project)**
```bash
cd ~/Projects/project-A
python scripts/save-session.py --quick
```

**Expected:**
- No switch detected
- Checkpoint created normally
- Active project set to project-A

### **Test 2: Same Project (No Switch)**
```bash
# Still in project-A
python scripts/save-session.py --quick
```

**Expected:**
- No switch detected
- Checkpoint created normally
- Active project updated

### **Test 3: Project Switch with Uncommitted Work**
```bash
# Edit files in project-A (don't checkpoint)
echo "test" >> file.txt

# Switch to project-B
cd ~/Projects/project-B
python scripts/save-session.py --quick
```

**Expected:**
```
⚠️ PROJECT SWITCH DETECTED
Previous project: project-A (github.com/user/project-A, branch: main)
Current project:  project-B (github.com/user/project-B, branch: main)

⚠️  WARNING: You have uncommitted work in the previous project!
   Last checkpoint: 5 minutes ago

What would you like to do?
  1. Create checkpoint for previous project first (recommended)
  2. Discard previous project changes and track current project
  3. Cancel (don't create any checkpoint)
```

### **Test 4: Choose Checkpoint Previous**
```bash
Your choice (1-3): 1
```

**Expected:**
```
📦 Creating checkpoint for previous project...
Collecting changes from project-A...
  Found 1 file change(s) in previous project

[... creates checkpoint for project-A ...]

✓ Previous project checkpointed successfully!

Now continuing with current project: project-B

[... continues with project-B checkpoint ...]
```

### **Test 5: Choose Discard**
```bash
Your choice (1-3): 2
⚠️  Confirm discard? Type 'yes' to confirm: yes
```

**Expected:**
```
⚠️  Discarding changes from project-A
Continuing with current project: project-B

[... continues with project-B checkpoint ...]
```

### **Test 6: Choose Cancel**
```bash
Your choice (1-3): 3
```

**Expected:**
```
Operation cancelled. No checkpoint created.
[Script exits with code 0]
```

---

## 🎨 **Visual Flow Diagram**

```
┌─────────────────────────────────────────┐
│ User runs: python save-session.py      │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Initialize SessionSaver                 │
│ - Set base_dir to current directory    │
│ - Collect current project metadata     │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Load active project from disk           │
│ (~/.claude/active-project.json)        │
└──────────────┬──────────────────────────┘
               │
               ▼
       ┌───────┴────────┐
       │ Projects match? │
       └───┬────────┬────┘
     YES │        │ NO
         │        │
         │        ▼
         │  ┌─────────────────────────────┐
         │  │ PROJECT SWITCH DETECTED     │
         │  │ Display prompt with options │
         │  └─────┬───────┬──────┬────────┘
         │        │       │      │
         │    ┌───┴───┐ ┌─┴──┐ ┌─┴─────┐
         │    │ Chkpt │ │Disc│ │Cancel │
         │    │ Prev  │ │ard │ │       │
         │    └───┬───┘ └─┬──┘ └─┬─────┘
         │        │       │      │
         │        ▼       │      ▼
         │  ┌──────────┐  │  [EXIT]
         │  │Create CP │  │
         │  │for prev  │  │
         │  │project   │  │
         │  └────┬─────┘  │
         │       │        │
         ▼       ▼        ▼
┌─────────────────────────────────────────┐
│ Continue with current project           │
│ - Collect changes                       │
│ - Create checkpoint                     │
│ - Auto-commit                           │
│ - Update active project state           │
└─────────────────────────────────────────┘
```

---

## 🏆 **Problems Solved**

### **Problem 1: Silent Project Switches**
**Before:** User could switch projects without realizing, mixing changes from multiple projects into one checkpoint
**After:** Explicit detection and prompt ensures user is aware of switches

### **Problem 2: Lost Work**
**Before:** Switching projects without checkpointing meant uncommitted work was lost
**After:** System prompts to checkpoint before switching, protecting work

### **Problem 3: Confusion About Active Context**
**Before:** No way to know which project was last worked on
**After:** Active project state stored and tracked persistently

### **Problem 4: No Recovery Path**
**Before:** If user accidentally switched, no way to go back and checkpoint
**After:** User explicitly chooses what to do, can checkpoint previous project

---

## ⏭️ **What's Next (Phases 3-6)**

**Phase 3:** Central session index for cross-project queries
**Phase 4:** Migration script to add project metadata to old checkpoints
**Phase 5:** Resume validation - ensure checkpoints match current project
**Phase 6:** Path storage enhancement (relative + absolute paths)

---

## 📝 **Configuration File Created**

**Location:** `~/.claude/active-project.json`

**Purpose:** Persistent storage of currently active project

**Auto-managed:** System creates/updates automatically, user doesn't need to touch it

---

## ✨ **Key Features**

1. ✅ **Automatic Detection** - No manual intervention required
2. ✅ **User Control** - Three clear options when switch detected
3. ✅ **Safety First** - Warns about uncommitted work
4. ✅ **Confirmation Required** - Discard requires explicit "yes"
5. ✅ **Dual Checkpointing** - Can checkpoint both projects in one run
6. ✅ **Cancel Anytime** - Ctrl+C or option 3 exits safely
7. ✅ **State Persistence** - Active project survives reboots
8. ✅ **Smart Matching** - Works with remote URL or local path

---

**Implementation Date:** November 17, 2025
**Files Modified:** 1 (save-session.py)
**Files Created:** 1 (project_tracker.py)
**Lines Added:** ~440
**Critical Features:** 3 (detection, prompt, state management)

**Status:** Phase 2 (100% complete) - Ready for Phase 3
