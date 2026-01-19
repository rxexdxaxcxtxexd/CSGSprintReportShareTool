# CSG Sprint Reporter - Setup Instructions (Technical)

Hey! 👋

I've set up a tool to automate our sprint reports. It pulls data from Jira and Fathom, then generates a nice markdown report. I'm funding a shared Claude API key so the tool can add AI-powered insights (like summarizing meetings and identifying themes).

## What You'll Get

- Automated sprint reports in ~2 minutes
- AI-powered meeting summaries
- Epic progress tracking
- Team velocity metrics
- Reports saved to your Downloads folder

**Cost to you:** $0 (I'm covering the Claude API credits)

---

## Prerequisites

- Python 3.8 or higher installed
- Git installed
- Access to Jira (csgsolutions.atlassian.net)
- Access to Fathom (fathom.video)

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/rxexdxaxcxtxexd/CSGSprintReportShareTool.git
cd CSGSprintReportShareTool
```

---

## Step 2: Install Dependencies

```bash
pip install -r scripts/requirements-sprint-reporter.txt
```

This installs packages for Jira, Fathom, and Claude API access.

---

## Step 3: Configure Your Credentials

Run the setup wizard:

```bash
python scripts/csg-sprint-reporter.py --config
```

You'll be prompted for:

1. **Jira email** - Your csgsolutions.com email
2. **Jira API token** - Get from: https://id.atlassian.com/manage-profile/security/api-tokens
   - Click "Create API token"
   - Name it "Sprint Reporter"
   - Copy the token
3. **Fathom API key** - Get from: https://fathom.video/customize
   - Scroll to "API Key"
   - Copy the key
4. **Claude API key** - **PRESS ENTER TO SKIP THIS**
   - The shared team key is already configured
   - Don't enter your own key unless you want to use your personal credits

---

## Step 4: Generate Your First Report

```bash
python scripts/csg-sprint-reporter.py --ai --quick --sprint 13
```

Replace `13` with your current sprint number.

**First run only:** You'll be prompted for a meeting keyword filter. Enter something like:
- `iBOPS` (for iBOPS team meetings)
- `Engineering` (for engineering meetings)
- `Sprint` (for sprint-related meetings)

This filter is saved for future quick runs.

---

## Step 5: Find Your Report

Reports are saved to: `~/Downloads/sprint-report-YYYY-MM-DD-HHMMSS.md`

Open with any markdown viewer or VS Code.

---

## Usage Examples

```bash
# Quick mode (uses saved settings)
python scripts/csg-sprint-reporter.py --ai --quick --sprint 14

# Interactive mode (choose settings)
python scripts/csg-sprint-reporter.py --ai

# Without AI (free, no Claude credits used)
python scripts/csg-sprint-reporter.py --quick --sprint 14
```

---

## What If Credits Run Out?

If you see this message:
```
CLAUDE API CREDITS EXHAUSTED
```

You have two options:

1. **Contact me** (layden@csgsolutions.com) for a credit top-up
2. **Add your own key** with `python scripts/csg-sprint-reporter.py --add-claude-key`
   - Cost: ~$0.50-$2.00 per report
   - Get key: https://console.anthropic.com/settings/keys

The tool will automatically continue with free templates if credits run out.

---

## Troubleshooting

**"Authentication failed"**
- Check your Jira API token hasn't expired
- Verify your Fathom API key is correct
- Run `--config` again to update credentials

**"No meetings found"**
- Try a different keyword filter (more generic like "Sprint" or "iBOPS")
- Check date range matches your sprint dates

**Other issues?**
- Debug logs are saved to Downloads folder
- Contact me: layden@csgsolutions.com

---

## Output Formats and Templates

**Default Format:** Word documents (.docx) using company template

**Output Location:**
- Word docs: `C:\Users\<you>\OneDrive - Cornerstone Solutions Group\Desktop\Files in use\Michael SRT\`
- Markdown: `~/Downloads`

**Format Options:**

```bash
# Word document (default)
python scripts/csg-sprint-reporter.py --quick --sprint 14

# Markdown format
python scripts/csg-sprint-reporter.py --quick --sprint 14 --format md

# Both formats
python scripts/csg-sprint-reporter.py --quick --sprint 14 --format both

# Custom template
python scripts/csg-sprint-reporter.py --quick --sprint 14 --template "/path/to/template.docx"
```

**Template Configuration:**

The tool uses this template by default:
`C:\Users\<you>\OneDrive - Cornerstone Solutions Group\Desktop\Files in use\Michael SRT\Doc Template.docx`

To use a different template, either:
1. Pass `--template` flag with each run
2. Or configure default in `~/.csg-sprint-config.json`:
   ```json
   {
     "word_template_path": "C:\\path\\to\\your\\template.docx",
     "default_format": "docx"
   }
   ```

---

## Tips

- Run reports at end of sprint for complete data
- Use `--ai` flag for AI insights (uses shared credits)
- Word format provides professional formatting for stakeholders
- Markdown format is great for version control and sharing
- The tool remembers your last sprint settings

---

**Questions?** Ping me on Teams or email layden@csgsolutions.com

Enjoy! 🚀
