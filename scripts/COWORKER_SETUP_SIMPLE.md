# Sprint Report Tool - Easy Setup Guide

Hi! 👋

Layden set up an automated sprint report tool for the team. This guide will help you get it running in about 10 minutes. **No technical experience needed!**

## What This Tool Does

- Generates sprint reports automatically
- Pulls your Jira tickets and Fathom meeting notes
- Creates a nice formatted report in 2 minutes
- Uses AI to summarize meetings (Layden is covering the AI costs)

---

## What You Need Before Starting

✅ Python installed on your computer
✅ Your Jira login info
✅ Your Fathom account access

**Don't have Python?** Download from: https://www.python.org/downloads/
- Click "Download Python"
- Run the installer
- ✅ Check "Add Python to PATH" during installation

---

## Step 1: Download the Tool

**Option A - Simple Download (Recommended):**
1. Download this ZIP file: [Link Layden will provide]
2. Right-click → Extract All
3. Save to a folder you'll remember (like `Documents`)

**Option B - If you know Git:**
```
git clone https://github.com/rxexdxaxcxtxexd/CSGSprintReportShareTool.git
```

---

## Step 2: Install Required Packages

**Windows:**
1. Open the extracted folder
2. Double-click `INSTALL.bat`
3. Wait for it to finish (may take 1-2 minutes)
4. Press any key to close

**Mac/Linux:**
1. Open Terminal
2. Navigate to the extracted folder: `cd path/to/CSGSprintReportShareTool`
3. Run: `./install.sh`

---

## Step 3: Set Up Your Credentials

**Windows:**
1. Double-click `SETUP.bat`
2. Follow the prompts

**Mac/Linux:**
1. Run: `./setup.sh`

### What You'll Need to Enter:

#### 1️⃣ Your Jira Email
Just type your work email: `yourname@csgsolutions.com`

#### 2️⃣ Jira API Token
**How to get it:**
1. Open: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Name it: "Sprint Reporter"
4. Copy the long code that appears
5. Paste it when the setup asks

#### 3️⃣ Fathom API Key
**How to get it:**
1. Open: https://fathom.video/customize
2. Scroll down to "API Key"
3. Copy the key
4. Paste it when the setup asks

#### 4️⃣ Claude API Key
**IMPORTANT:** Just press Enter (don't type anything)
- Layden already set up a shared team key
- You don't need your own

---

## Step 4: Generate Your First Report

**Windows:**
1. Double-click `RUN_REPORT.bat`
2. The interactive menu will appear - follow the prompts:
   - Select your board (e.g., "iBOPS Board")
   - Select your sprint number (e.g., "Sprint 13")
   - Choose if you want meeting insights included
3. Wait 1-2 minutes

**Mac/Linux:**
```bash
./run_report.sh
```

**Your Word report will appear in OneDrive!**
`C:\Users\<your-name>\OneDrive - Cornerstone Solutions Group\Desktop\Files in use\Michael SRT\`

---

## Daily Usage (After Setup)

Once configured, generating reports is easy:

**Windows:** Double-click `RUN_REPORT.bat`
**Mac/Linux:** Run `./run_report.sh`

The interactive menu will guide you through selecting your board and sprint. The tool remembers your last selections, making it even faster!

---

## What Your Report Includes

✅ All Jira tickets in the sprint
✅ Team completion statistics
✅ Epic progress breakdown
✅ Meeting summaries (AI-powered)
✅ Identified blockers
✅ Team velocity trends

## Output Format

**By default, reports are saved as Word documents (.docx)** to:
`C:\Users\<your-name>\OneDrive - Cornerstone Solutions Group\Desktop\Files in use\Michael SRT\`

This uses the company template for professional formatting!

**Want markdown instead?**
The interactive menu will let you choose the format (Word/Markdown/Both) when generating the report.

**Advanced Users:** You can also use command-line flags:
```bash
python csg-sprint-reporter.py --ai --format md    # Markdown only
python csg-sprint-reporter.py --ai --format both  # Both formats
```

**Viewing reports:**
- Word (.docx): Open with Microsoft Word
- Markdown (.md): Open with Notepad/TextEdit or VS Code

---

## If Something Goes Wrong

### "Python not found"
- Reinstall Python from python.org
- ✅ Make sure you check "Add Python to PATH"

### "Authentication failed"
- Your Jira or Fathom credentials might be wrong
- Run setup again: double-click `SETUP.bat`

### "No meetings found"
- Try a simpler keyword like "Sprint" instead of specific team names
- Check that Fathom has meetings recorded

### "Credits exhausted"
The tool will show you two options:
1. Contact Layden for more credits
2. Add your own Claude key (~$1-2 per report)

**Don't worry** - the tool still works without AI, you just won't get meeting summaries.

---

## Need Help?

📧 Email: layden@csgsolutions.com
💬 Teams: Message Layden

He set this up to make our lives easier, so don't hesitate to ask questions!

---

## Quick Reference Card

```
📥 Download tool → Extract ZIP
🔧 Double-click INSTALL.bat
⚙️ Double-click SETUP.bat (enter credentials)
▶️ Double-click RUN_REPORT.bat (use interactive menu)
📄 Check OneDrive folder for Word report
```

**That's it!** 🎉

---

**Pro Tip:** Create a desktop shortcut to `RUN_REPORT.bat` for one-click reports!
