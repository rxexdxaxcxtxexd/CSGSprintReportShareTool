# CSG Sprint Reporter

**Standalone tool for generating sprint reports from Jira and Fathom**

This tool automatically generates comprehensive sprint reports combining Jira issue data with meeting insights from Fathom recordings. No AI access required!

---

## Quick Start

### 1. Install Dependencies

Open a terminal/command prompt and run:

```bash
cd C:\Users\layden\scripts
pip install -r requirements-sprint-reporter.txt
```

This installs:
- `requests` - For API calls to Jira and Fathom
- `keyring` - For secure credential storage

### 2. First-Time Setup

Configure your API credentials (one-time setup):

```bash
python csg-sprint-reporter.py --config
```

You'll be prompted for:

**Jira Credentials:**
- **Site name:** Default is `csgsolutions` - just press Enter to use it
- **Username:** Enter just your username (e.g., `john.doe`) - automatically becomes `john.doe@csgsolutions.com`
- **API token:** Press Enter to use the temporary CSG team token (valid until Jan 13, 2026), or [get your own](https://id.atlassian.com/manage-profile/security/api-tokens)

**Fathom Credentials (Optional):**
- **API key:** Get from [Fathom Settings](https://app.fathom.video/settings/api), or press Enter to skip

**Smart Defaults:** CSG team members can press Enter for all prompts to get started immediately with the temporary token. You'll be prompted to add your own token before it expires.

**Note:** Your API tokens are stored securely in your system keyring (encrypted), NOT in plain text.

### 3. Generate Your First Report

Interactive mode (recommended):

```bash
python csg-sprint-reporter.py
```

Follow the prompts:
1. Board ID (default: 38)
2. Sprint number (e.g., 13, 14, 15)
3. Meeting keywords (default: "CSG Sprint")
4. Date range (default: auto-detect from sprint)
5. Report sections (default: all enabled)

The report will be saved to: `C:\Users\{YourUsername}\Downloads\CSG-Sprint-{N}-Report.md`

---

## Usage Modes

### Interactive Mode (Default)
Guided step-by-step configuration:
```bash
python csg-sprint-reporter.py
```

### Quick Mode
Use saved configuration from last run:
```bash
python csg-sprint-reporter.py --quick --sprint 13
```

### Reconfigure Credentials
Update your API keys:
```bash
python csg-sprint-reporter.py --config
```

---

## API Token Management

### Temporary vs Personal Tokens

**Temporary CSG Team Token:**
- Automatically provided during first-time setup
- Valid until **January 13, 2026**
- Shared across the team
- Best for: Quick start, testing, short-term use

**Personal API Token:**
- Your own token from Atlassian
- Never expires (unless you revoke it)
- Recommended for regular use
- Get yours at: https://id.atlassian.com/manage-profile/security/api-tokens

### Expiration Notifications

The tool automatically checks for token expiration:

**7 Days Before Expiration:**
```
[WARNING] Temporary API key expires in 7 day(s) (2026-01-13)
[WARNING] Get your own token: https://id.atlassian.com/manage-profile/security/api-tokens
[WARNING] Configure with: python csg-sprint-reporter.py --config
```

**After Expiration (January 13, 2026):**
```
============================================================
API KEY EXPIRED - ACTION REQUIRED
============================================================

The temporary CSG team API key expired on 2026-01-13.
You must add your own Atlassian API key to continue.

To get your API key:
1. Visit: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Copy the token

Run: python csg-sprint-reporter.py --config
============================================================
```

### Switching to Your Personal Token

At any time, you can switch from the temporary token to your own:

1. Run the configuration:
   ```bash
   python csg-sprint-reporter.py --config
   ```

2. When prompted for "Jira API token", paste your personal token (don't press Enter)

3. The tool will save your personal token and stop checking for expiration

---

## What's Included in the Report

The generated Markdown report includes:

### 1. Sprint Summary
- Total issues
- Completed issues (with completion %)
- Issues in progress
- Issues not started

### 2. Team Breakdown
Table showing:
- Team member name
- Issues assigned
- Issues completed
- Completion percentage

### 3. Issue Status
Breakdown by status:
- Done
- In Progress
- In Code Review
- Ready for Dev
- etc.

### 4. Epic Progress
For each epic:
- Epic key (e.g., BOPS-3515)
- Subtasks completed / total
- Completion percentage
- Remaining subtasks

### 5. Blockers
High-priority issues that are not completed:
- Issue key and summary
- Assignee

### 6. Meeting Insights
From Fathom recordings:
- List of meetings analyzed
- Key takeaways from meeting summaries
- Action items extracted from meetings

---

## Troubleshooting

### "Jira authentication failed"
**Solution:**
1. Verify your Jira email and API token
2. Generate a new API token at: https://id.atlassian.com/manage-profile/security/api-tokens
3. Run: `python csg-sprint-reporter.py --config`
4. Enter your new credentials

### "API KEY EXPIRED - ACTION REQUIRED"
**Cause:** The temporary CSG team token expired on January 13, 2026.

**Solution:**
1. Visit: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token" and give it a name (e.g., "Sprint Reporter")
3. Copy the token
4. Run: `python csg-sprint-reporter.py --config`
5. Paste your token when prompted (don't press Enter)

Your personal token never expires and you won't see this message again.

### "WARNING: Temporary API key expires in X days"
**Cause:** The temporary CSG team token is expiring soon.

**Solution:**
- No action required immediately - the tool will still work
- Recommended: Get your own token before expiration (see above)
- You have until January 13, 2026 to switch

### "Fathom unavailable"
**Solution:**
- The tool will ask if you want to continue without meeting insights
- Press `y` to generate a report with just Jira data
- Or update your Fathom API key: `python csg-sprint-reporter.py --config`

### "Sprint X not found"
**Solution:**
- Verify the sprint number exists in Jira
- Check you're using the correct board ID (default: 38)
- Sprint numbers must match exactly (e.g., "BOPS: Sprint 13" = sprint number 13)

### "Network error after 3 attempts"
**Solution:**
- Check your internet connection
- Verify you can access csgsolutions.atlassian.net in your browser
- The tool will automatically retry with delays: 5s, 10s, 20s

### Import errors or "Module not found"
**Solution:**
```bash
# Reinstall dependencies
pip install -r requirements-sprint-reporter.txt

# If still failing, try:
pip install --upgrade requests keyring
```

---

## Configuration Files

### Where Credentials are Stored

**Sensitive data (encrypted):**
- Location: System keyring (Windows Credential Manager)
- Contains: Jira API token, Fathom API key
- **Security:** Encrypted by your operating system

**Non-sensitive data:**
- Location: `C:\Users\{YourUsername}\.csg-sprint-config.json`
- Contains: Jira site name, email, last board/sprint used
- **Security:** Plain text, but contains no secrets

### To Reset Everything

Delete the config file and stored credentials:

1. Delete `C:\Users\{YourUsername}\.csg-sprint-config.json`
2. Open Windows Credential Manager → Generic Credentials
3. Delete any entries starting with `csg-sprint-reporter`
4. Run `python csg-sprint-reporter.py --config`

---

## Example Workflow

### Weekly Sprint Review

Every sprint end, generate the report:

```bash
python csg-sprint-reporter.py --quick --sprint 13
```

**Output:** `C:\Users\{YourUsername}\Downloads\CSG-Sprint-13-Report.md`

Open the file in any Markdown viewer or text editor:
- Notepad
- VS Code
- Obsidian
- Typora

Share with your team or copy sections into email/Slack.

---

## Advanced: Customization

### Custom Board

Default is Board 38 (BargeOps). To use a different board:

```bash
# Interactive mode will prompt you
python csg-sprint-reporter.py

# At prompt:
Board ID [38]: 42
```

### Custom Meeting Filter

Default searches for meetings with "CSG Sprint" in the title. To customize:

```bash
# Interactive mode will prompt you
python csg-sprint-reporter.py

# At prompt:
Meeting keyword [CSG Sprint]: Engineering
```

**Note:** Fathom search uses fuzzy matching on a single keyword. For example, "Engineering" will match "Engineering Standup", "iBOPS Engineering", etc. The search does NOT support OR logic like "Engineering OR Standup".

### Custom Date Range

By default, the tool uses sprint start/end dates from Jira. To override:

```bash
# Interactive mode
python csg-sprint-reporter.py

# At prompt:
Customize date range? (y/N): y
Start: 2025-12-01
End: 2025-12-31
```

---

## Tips & Best Practices

### 1. Run at Sprint End
Generate reports after sprint retrospectives for most accurate completion data.

### 2. Use Quick Mode
After your first run, use `--quick` mode to skip the interactive prompts:
```bash
python csg-sprint-reporter.py --quick --sprint 14
```

### 3. Archive Reports
Create a folder to organize reports:
```
C:\Users\{YourUsername}\Documents\Sprint Reports\
  ├── Sprint-13-Report.md
  ├── Sprint-14-Report.md
  └── Sprint-15-Report.md
```

### 4. Meeting Insights Quality
For better meeting insights:
- Ensure Fathom is recording sprint meetings
- Use consistent naming: "CSG Sprint 13 Planning", "CSG Sprint 13 Review"
- Wait for Fathom to generate summaries (takes ~30 min after meeting ends)

---

## Differences from ibops-sprint Skill

| Feature | CSG Sprint Reporter | ibops-sprint Skill |
|---------|---------------------|-------------------|
| AI Required | No | Yes (Claude Code) |
| Setup | One-time credential config | Built into Claude |
| Customization | Interactive prompts | Skill arguments |
| Output Location | Downloads folder | OneDrive |
| Meeting Insights | Fathom API | Fathom MCP |
| Velocity Analysis | Not included | Optional (--admin-only) |
| Gamma Slides | Not included | Optional |

**When to use CSG Sprint Reporter:**
- You don't have Claude Code access
- You want a quick report without AI
- You need to automate reports (scripts)

**When to use ibops-sprint skill:**
- You want AI-powered analysis
- You need Admin Velocity tracking
- You want Gamma presentation slides

---

## Getting Help

### Check Tool Version
```bash
python csg-sprint-reporter.py --help
```

### Test API Connections
The tool automatically tests connections when you run it:
```bash
python csg-sprint-reporter.py --quick --sprint 13

# Output will show:
# Testing Jira connection...
#   Jira connection OK
# Testing Fathom connection...
#   Fathom connection OK
```

### Common Error Messages

**"Credentials not configured"**
→ Run: `python csg-sprint-reporter.py --config`

**"Sprint X not found on Board Y"**
→ Verify sprint number in Jira Board 38

**"Fathom authentication failed"**
→ Check API key at: https://app.fathom.video/settings/api

---

## Technical Details

### API Endpoints Used

**Jira REST API v3:**
- `GET /rest/api/3/myself` - Test authentication
- `GET /rest/agile/1.0/board/{board}/sprint` - Get sprint info
- `GET /rest/api/3/search` - Get sprint issues (JQL: `sprint={id}`)

**Fathom API v1:**
- `GET /external/v1/meetings` - List meetings with filters
- `GET /external/v1/meetings/{id}` - Get meeting details

### Rate Limiting
- **Jira:** 300 requests per minute (automatic retry with backoff)
- **Fathom:** 100 requests per minute (automatic retry with backoff)

### Data Privacy
- All API calls are direct HTTPS connections
- No data is stored outside your computer
- Credentials encrypted in system keyring
- Reports saved locally only

---

## Contact & Support

**Created by:** Layden (CSG)
**For:** CSG Sprint reporting automation
**Version:** 1.0 (January 2026)

**Questions?** Contact the creator for assistance.

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────┐
│         CSG Sprint Reporter - Quick Reference        │
├─────────────────────────────────────────────────────┤
│ First-Time Setup:                                   │
│   python csg-sprint-reporter.py --config            │
│                                                      │
│ Generate Report (Interactive):                      │
│   python csg-sprint-reporter.py                     │
│                                                      │
│ Generate Report (Quick):                            │
│   python csg-sprint-reporter.py --quick --sprint 13 │
│                                                      │
│ Reconfigure:                                        │
│   python csg-sprint-reporter.py --config            │
│                                                      │
│ Output Location:                                    │
│   C:\Users\{You}\Downloads\CSG-Sprint-{N}-Report.md │
│                                                      │
│ Help:                                               │
│   python csg-sprint-reporter.py --help              │
└─────────────────────────────────────────────────────┘
```
