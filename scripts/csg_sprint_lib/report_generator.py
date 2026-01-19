"""
Sprint report generator with metric calculations and Markdown output
"""

from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
import logging

from .models import JiraIssue, FathomMeeting, SprintMetrics
from .api_client import JiraClient, FathomClient, ClaudeClient
from .word_generator import WordDocumentGenerator

logger = logging.getLogger(__name__)


class SprintReportGenerator:
    """Generates sprint reports from Jira and Fathom data"""

    def __init__(self, jira_client: JiraClient, fathom_client: Optional[FathomClient], config: dict, claude_client: Optional[ClaudeClient] = None):
        self.jira_client = jira_client
        self.fathom_client = fathom_client
        self.claude_client = claude_client
        self.config = config

        self.sprint = None
        self.issues: List[JiraIssue] = []
        self.meetings: List[FathomMeeting] = []
        self.metrics: Optional[SprintMetrics] = None
        self.ai_insights: Optional[Dict] = None

    def fetch_data(self) -> None:
        """Fetch sprint data from Jira and Fathom"""
        board_id = self.config['board_id']
        sprint_number = self.config['sprint_number']

        # Fetch sprint info
        print(f"Fetching Sprint {sprint_number} from Board {board_id}...")
        self.sprint = self.jira_client.get_sprint_by_number(board_id, sprint_number)

        if not self.sprint:
            raise ValueError(f"Sprint {sprint_number} not found on Board {board_id}")

        print(f"  Found: {self.sprint['name']}")

        # Fetch sprint issues
        sprint_id = self.sprint['id']
        print(f"Fetching issues...")
        self.issues = self.jira_client.get_sprint_issues(board_id, sprint_id)
        print(f"  Fetched {len(self.issues)} issues")

        # Fetch Fathom meetings if client available
        if self.fathom_client and self.config.get('meeting_filter'):
            try:
                print(f"Fetching meetings...")

                # Determine date range for filtering
                start_date = None
                end_date = None
                if self.config.get('custom_dates'):
                    start_date, end_date = self.config['custom_dates']
                    print(f"  Using custom date range: {start_date} to {end_date}")
                else:
                    # Use sprint dates for post-filtering
                    start_date = self.sprint.get('start_date')
                    end_date = self.sprint.get('end_date')
                    # Convert datetime to date if needed
                    if start_date and hasattr(start_date, 'date'):
                        start_date = start_date.date()
                    if end_date and hasattr(end_date, 'date'):
                        end_date = end_date.date()
                    if start_date and end_date:
                        print(f"  Sprint date range: {start_date} to {end_date}")
                        print(f"  Searching all meetings (will filter by date after fetching)")
                    else:
                        print(f"  No date range available (searching all meetings)")

                # Search all meetings by keyword (don't use API date filter - it often fails)
                self.meetings = self.fathom_client.search_meetings(
                    self.config['meeting_filter'],
                    None,  # Don't filter by date at API level
                    None
                )
                print(f"  Fetched {len(self.meetings)} meetings matching keyword")

                # Filter meetings by sprint dates on the client side
                if start_date and end_date and self.meetings:
                    meetings_before_filter = len(self.meetings)
                    self.meetings = [
                        m for m in self.meetings
                        if start_date <= m.date.date() <= end_date
                    ]
                    filtered_count = meetings_before_filter - len(self.meetings)
                    print(f"  Filtered to {len(self.meetings)} meetings within sprint dates")
                    if filtered_count > 0:
                        logger.info(f"Filtered out {filtered_count} meetings outside sprint date range")
                    if len(self.meetings) == 0:
                        print(f"  WARNING: No meetings found in sprint date range {start_date} to {end_date}")
                        print(f"  This might mean:")
                        print(f"    1. Sprint dates in Jira are incorrect")
                        print(f"    2. Meetings weren't recorded during this sprint")
                        print(f"  Consider using custom date range or checking sprint dates")

                # Meetings already contain full details from list API (no enrichment needed)
                if self.meetings:
                    logger.info(f"Fetched {len(self.meetings)} meetings with details")
                    meetings_with_summary = sum(1 for m in self.meetings if m.summary)
                    meetings_with_actions = sum(1 for m in self.meetings if m.action_items)
                    print(f"  Meetings with summaries: {meetings_with_summary}/{len(self.meetings)}")
                    if meetings_with_actions > 0:
                        print(f"  Meetings with action items: {meetings_with_actions}/{len(self.meetings)}")

                self.config['include_meetings'] = True
            except Exception as e:
                print(f"  WARNING: Fathom unavailable: {e}")
                print("  Report will be incomplete - meetings are required.")
                user_input = input("  Continue anyway? (y/N): ")
                if user_input.lower() != 'y':
                    raise
                self.config['include_meetings'] = False
                self.meetings = []
        else:
            self.config['include_meetings'] = False

        # Synthesize meeting insights with AI if Claude client available
        if self.claude_client and self.meetings:
            print("Synthesizing meeting insights with AI...")
            sprint_context = f"""
Sprint: {self.sprint.get('name', 'Unknown')}
Date Range: {self.sprint.get('start_date')} to {self.sprint.get('end_date')}
Total Issues: {len(self.issues)}
"""
            # Convert FathomMeeting objects to dicts for Claude client
            meeting_dicts = [
                {
                    'title': m.title,
                    'date': m.date.strftime('%Y-%m-%d') if m.date else 'Unknown',
                    'summary': m.summary or 'No summary',
                    'action_items': m.action_items or []
                }
                for m in self.meetings
            ]
            self.ai_insights = self.claude_client.synthesize_meeting_insights(
                meeting_dicts,
                sprint_context
            )
            if self.ai_insights and any(self.ai_insights.values()):
                print("  AI synthesis complete")
            else:
                print("  AI synthesis failed - using rule-based templates")
                self.ai_insights = None

    def calculate_metrics(self) -> SprintMetrics:
        """Calculate sprint metrics from issues"""
        # Status breakdown
        status_counts = Counter([issue.status for issue in self.issues])

        # Count by status category
        done_count = sum(1 for issue in self.issues if issue.status_category == 'done')
        in_progress_count = sum(1 for issue in self.issues if issue.status_category == 'indeterminate')
        not_started_count = sum(1 for issue in self.issues if issue.status_category == 'new')

        # Completion rate
        completion_rate = (done_count / len(self.issues) * 100) if self.issues else 0

        # Team contributions
        assignee_stats = defaultdict(lambda: {"assigned": 0, "completed": 0, "in_progress": 0})
        for issue in self.issues:
            assignee = issue.assignee or "Unassigned"
            assignee_stats[assignee]["assigned"] += 1

            if issue.status_category == "done":
                assignee_stats[assignee]["completed"] += 1
            elif issue.status_category == "indeterminate":
                assignee_stats[assignee]["in_progress"] += 1

        # Epic progress
        epic_stats = defaultdict(lambda: {"total": 0, "done": 0, "in_progress": 0, "summary": ""})
        for issue in self.issues:
            if issue.parent:
                parent = issue.parent
                epic_stats[parent]["total"] += 1
                if issue.status_category == "done":
                    epic_stats[parent]["done"] += 1
                elif issue.status_category == "indeterminate":
                    epic_stats[parent]["in_progress"] += 1

        # Identify blockers (high priority and not done)
        blockers = [
            issue for issue in self.issues
            if issue.priority in ["High", "Highest"] and issue.status_category != "done"
        ]

        # Calculate QA and ready counts
        qa_count = sum(1 for issue in self.issues if 'qa' in issue.status.lower() or 'uvt' in issue.status.lower())
        ready_count = sum(1 for issue in self.issues if 'ready' in issue.status.lower())

        self.metrics = SprintMetrics(
            total_issues=len(self.issues),
            done_count=done_count,
            in_progress_count=in_progress_count,
            not_started_count=not_started_count,
            completion_rate=completion_rate,
            status_counts=dict(status_counts),
            assignee_stats=dict(assignee_stats),
            epic_stats=dict(epic_stats),
            blockers=blockers,
            qa_count=qa_count,
            ready_count=ready_count
        )

        return self.metrics

    def generate_markdown(self) -> str:
        """Generate rich narrative Markdown report"""
        if not self.metrics:
            raise ValueError("Must call calculate_metrics() first")

        # Prepare data structures
        epic_groups = self._group_issues_by_epic()
        accomplishments = self._categorize_accomplishments(epic_groups)
        decisions = self._extract_decisions()
        meeting_themes = self._synthesize_meeting_themes()
        health_emoji, health_text = self._assess_sprint_health()

        # Extract sprint dates
        start_date = self.sprint['startDate'][:10]
        end_date = self.sprint['endDate'][:10]
        sprint_num = self.config['sprint_number']

        # Get board name
        board_name = "Unknown Board"
        try:
            board_name = self.jira_client.get_board_name(self.config['board_id'])
        except:
            board_name = f"Board {self.config['board_id']}"

        lines = []

        # === HEADER ===
        lines.append(f"# CSG Sprint {sprint_num} Report")
        lines.append("")
        lines.append(f"**Board:** {board_name}")
        lines.append(f"**Sprint Dates:** {start_date} - {end_date}")
        lines.append(f"**Report Generated:** {datetime.now().strftime('%B %d, %Y')}")
        lines.append(f"**Sprint Status:** Active")
        lines.append("")
        lines.append("---")
        lines.append("")

        # === EXECUTIVE SUMMARY ===
        lines.append("## Executive Summary")
        lines.append("")

        # Use AI-generated summary if available
        if self.ai_insights and self.ai_insights.get('executive_summary'):
            lines.append(self.ai_insights['executive_summary'])
            lines.append("")
            lines.append("---")
            lines.append("")

        # Always include metrics
        lines.append(f"**Sprint {sprint_num} Progress:**")
        lines.append(f"- **Total Issues:** {self.metrics.total_issues}")
        lines.append(f"- **Completed (Done):** {self.metrics.done_count} ({self.metrics.completion_rate:.1f}%)")

        qa_pct = (self.metrics.qa_count / self.metrics.total_issues * 100) if self.metrics.total_issues > 0 else 0
        lines.append(f"- **In QA/UVT:** {self.metrics.qa_count} ({qa_pct:.1f}%)")
        lines.append(f"- **In Progress:** {self.metrics.in_progress_count}")

        if self.metrics.ready_count > 0:
            ready_pct = (self.metrics.ready_count / self.metrics.total_issues * 100)
            lines.append(f"- **Ready for Development:** {self.metrics.ready_count} ({ready_pct:.1f}%)")

        not_started_pct = (self.metrics.not_started_count / self.metrics.total_issues * 100) if self.metrics.total_issues > 0 else 0
        lines.append(f"- **Not Started:** {self.metrics.not_started_count} ({not_started_pct:.1f}%)")
        lines.append("")
        lines.append(f"**Sprint Health:** {health_emoji} {health_text}")
        lines.append("")

        if self.meetings:
            mode = "🤖 AI-Powered Analysis" if self.ai_insights else "Rule-Based Analysis"
            lines.append(f"**Meeting Insights:** Analyzed {len(self.meetings)} team meetings ({mode})")
        lines.append("")
        lines.append("---")
        lines.append("")

        # === KEY ACCOMPLISHMENTS ===
        lines.append("## Key Accomplishments ✅")
        lines.append("")

        if accomplishments:
            for idx, acc in enumerate(accomplishments[:5], 1):
                lines.append(f"### {idx}. **{acc['epic_summary']}** ({acc['epic_key']})")

                if acc['done'] == acc['total']:
                    lines.append(f"- ✅ **COMPLETED**: All {acc['total']} issues resolved")
                else:
                    lines.append(f"- **Progress**: {acc['done']} completed, {acc['qa']} in QA, {acc['in_progress']} in progress")
                    if acc['remaining'] > 0:
                        lines.append(f"- **Remaining**: {acc['remaining']} tasks")

                completion_pct = (acc['done'] / acc['total'] * 100) if acc['total'] > 0 else 0
                lines.append(f"- **Completion**: {completion_pct:.0f}%")
                lines.append("")
        else:
            lines.append("- Sprint work in progress - no major completions yet")
            lines.append("")

        # === DECISIONS & DISCUSSIONS ===
        lines.append("## Decisions/Discussions 💡")
        lines.append("")

        # Use AI-extracted decisions if available
        if self.ai_insights and self.ai_insights.get('key_decisions'):
            lines.append("### Key Decisions (AI-Extracted)")
            lines.append("")
            lines.append(self.ai_insights['key_decisions'])
            lines.append("")
        elif decisions:
            lines.append("### Key Decisions")
            for decision in decisions[:10]:
                date_str = decision['date'].strftime('%b %d')
                lines.append(f"- **From {decision['meeting']} ({date_str}):** {decision['decision']}")
            lines.append("")
        else:
            lines.append("- No specific decisions extracted from meeting notes")
            lines.append("")

        # === BLOCKERS & RISKS ===
        lines.append("## Blockers/Risks ⚠️")
        lines.append("")

        if self.metrics.blockers:
            lines.append("### High Priority Issues")
            for blocker in self.metrics.blockers:
                assignee = blocker.assignee or "Unassigned"
                lines.append(f"- **{blocker.key}:** {blocker.summary}")
                lines.append(f"  - Priority: {blocker.priority}, Status: {blocker.status}, Assignee: {assignee}")
        else:
            lines.append("- No high-priority blockers identified")

        lines.append("")

        if self.metrics.not_started_count > (self.metrics.total_issues * 0.3):
            lines.append("### Resource Concerns")
            lines.append(f"- **High backlog**: {self.metrics.not_started_count} issues not yet started ({not_started_pct:.0f}% of sprint)")
            lines.append("")

        # === TEAM CONTRIBUTIONS ===
        lines.append("## Team Contributions")
        lines.append("")
        lines.append("| Team Member | Assigned | Completed | In Progress/QA | Completion % |")
        lines.append("|-------------|----------|-----------|----------------|--------------|")

        for assignee, stats in sorted(self.metrics.assignee_stats.items(), key=lambda x: -x[1]["assigned"]):
            in_prog_qa = stats.get("in_progress", 0)
            completion_pct = (stats["completed"] / stats["assigned"] * 100) if stats["assigned"] > 0 else 0
            lines.append(f"| {assignee} | {stats['assigned']} | {stats['completed']} | {in_prog_qa} | {completion_pct:.1f}% |")

        lines.append("")

        # === WORK STREAM STATUS ===
        lines.append("## Work Stream Status")
        lines.append("")
        lines.append("### 📊 By Epic/Parent")
        lines.append("")
        lines.append("| Epic/Parent | Key | Total | Done | In QA | In Progress | Remaining |")
        lines.append("|-------------|-----|-------|------|-------|-------------|-----------|")

        for acc in accomplishments:
            summary_short = acc['epic_summary'][:40] + "..." if len(acc['epic_summary']) > 40 else acc['epic_summary']
            lines.append(f"| {summary_short} | {acc['epic_key']} | {acc['total']} | {acc['done']} | {acc['qa']} | {acc['in_progress']} | {acc['remaining']} |")

        lines.append("")

        # === MEETING INSIGHTS ===
        if self.config.get('include_meetings') and self.meetings:
            lines.append("## Meeting Insights 💬")
            lines.append("")
            lines.append(f"**Meetings Analyzed:** {len(self.meetings)} meetings")
            lines.append("")

            # Use AI-generated meeting themes if available
            if self.ai_insights and self.ai_insights.get('meeting_themes'):
                lines.append("### AI-Synthesized Themes")
                lines.append("")
                lines.append(self.ai_insights['meeting_themes'])
                lines.append("")
            else:
                # Fall back to rule-based grouping
                for theme, meetings in meeting_themes.items():
                    if not meetings:
                        continue

                    lines.append(f"### {theme} Meetings ({len(meetings)})")
                    for meeting in meetings[:5]:
                        date_str = meeting.date.strftime('%b %d')
                        lines.append(f"- **{meeting.title}** ({date_str})")

                        if meeting.summary:
                            summary_short = meeting.summary[:200] + "..." if len(meeting.summary) > 200 else meeting.summary
                            lines.append(f"  - {summary_short}")

                        if meeting.action_items:
                            lines.append(f"  - **Actions**: {len(meeting.action_items)} items")

                    lines.append("")
        else:
            lines.append("## Meeting Insights")
            lines.append("*Meeting insights: N/A - Fathom unavailable*")
            lines.append("")

        # === APPENDIX ===
        lines.append("---")
        lines.append("")
        lines.append("## Appendix: Sprint Metrics")
        lines.append("")
        lines.append("**Data Sources:**")
        lines.append(f"- Jira Board {self.config['board_id']}")
        if self.meetings:
            lines.append(f"- Fathom Meetings: {len(self.meetings)} analyzed")
        lines.append("")
        lines.append(f"**Sprint ID:** {self.sprint['id']}")
        lines.append(f"**Sprint Name:** {self.sprint['name']}")
        lines.append("")

        lines.append("**Detailed Status Breakdown:**")
        for status, count in sorted(self.metrics.status_counts.items(), key=lambda x: -x[1]):
            pct = (count / self.metrics.total_issues * 100) if self.metrics.total_issues > 0 else 0
            lines.append(f"- **{status}:** {count} ({pct:.1f}%)")

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(f"**Report Generated By:** CSG Sprint Reporter")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        return "\n".join(lines)

    def generate_word_document(self, template_path: Optional[Path] = None):
        """
        Generate Word document from sprint data

        Args:
            template_path: Path to template file (optional)

        Returns:
            Word Document object
        """
        from docx import Document

        # Prepare sprint data
        sprint_data = {
            'sprint_number': self.config['sprint_number'],
            'board_name': self.config['board_name'],
            'start_date': self.sprint.get('startDate', 'N/A')[:10] if self.sprint else 'N/A',
            'end_date': self.sprint.get('endDate', 'N/A')[:10] if self.sprint else 'N/A'
        }

        # Get AI insights if available
        ai_insights = None
        if self.claude_client and self.meetings:
            ai_insights = self._get_ai_insights()

        # Generate document
        generator = WordDocumentGenerator(template_path)
        document = generator.generate(
            sprint_data=sprint_data,
            metrics=self.metrics,
            ai_insights=ai_insights
        )

        return document

    def _get_ai_insights(self) -> Dict[str, str]:
        """Get AI insights from meetings (if available)"""
        if not self.meetings:
            return {}

        try:
            insights = self.claude_client.synthesize_meeting_insights(self.meetings)
            return {
                'executive_summary': insights.get('executive_summary', ''),
                'key_decisions': insights.get('key_decisions', ''),
                'meeting_themes': insights.get('meeting_themes', '')
            }
        except Exception as e:
            logger.warning(f"Failed to get AI insights: {e}")
            return {}

    def save_report(self, output_dir: Path, format_type: str = "md",
                    template_path: Optional[Path] = None) -> Path:
        """
        Save report to file

        Args:
            output_dir: Directory to save report
            format_type: 'md' or 'docx'
            template_path: Template path for Word docs (optional)

        Returns:
            Path to saved file
        """
        if not self.metrics:
            raise ValueError("Must call calculate_metrics() first")

        sprint_num = self.config['sprint_number']

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        if format_type == "docx":
            # Generate Word document
            document = self.generate_word_document(template_path)

            # Save to file
            output_file = output_dir / f"CSG-Sprint-{sprint_num}-Report.docx"
            document.save(str(output_file))

            logger.info(f"Word report saved: {output_file}")
            return output_file

        else:
            # Generate markdown (existing behavior)
            markdown = self.generate_markdown()
            output_file = output_dir / f"CSG-Sprint-{sprint_num}-Report.md"
            output_file.write_text(markdown, encoding='utf-8')

            logger.info(f"Markdown report saved: {output_file}")
            return output_file

    # === Helper Methods for Rich Report Generation ===

    def _group_issues_by_epic(self) -> Dict[str, List[JiraIssue]]:
        """Group issues by their parent epic"""
        grouped = defaultdict(list)
        for issue in self.issues:
            parent = issue.parent or "No Epic"
            grouped[parent].append(issue)
        return dict(grouped)

    def _get_epic_summary(self, epic_key: str) -> str:
        """Get epic summary by finding epic issue in issues list"""
        for issue in self.issues:
            if issue.key == epic_key and issue.issue_type == "Epic":
                return issue.summary
        # Fallback: return key if epic not found
        return epic_key

    def _categorize_accomplishments(self, epic_groups: Dict) -> List[Dict]:
        """
        Identify major accomplishments from completed epics/issues
        Returns list of accomplishment dictionaries
        """
        accomplishments = []
        for epic_key, issues in epic_groups.items():
            if epic_key == "No Epic":
                continue

            done = [i for i in issues if i.status_category == 'done']
            qa = [i for i in issues if 'qa' in i.status.lower() or 'uvt' in i.status.lower()]
            in_prog = [i for i in issues if i.status_category == 'indeterminate' and i not in qa]

            # Only include if has progress
            if len(done) > 0 or len(qa) > 0 or len(in_prog) > 0:
                accomplishments.append({
                    'epic_key': epic_key,
                    'epic_summary': self._get_epic_summary(epic_key),
                    'total': len(issues),
                    'done': len(done),
                    'qa': len(qa),
                    'in_progress': len(in_prog),
                    'remaining': len(issues) - len(done) - len(qa) - len(in_prog)
                })

        # Sort by total issues (largest epics first)
        return sorted(accomplishments, key=lambda x: x['total'], reverse=True)

    def _extract_decisions(self) -> List[Dict]:
        """
        Extract decision points from meetings
        Look for keywords: decided, agreed, established, plan to, prioritized
        """
        decisions = []
        decision_keywords = ['decided', 'agreed', 'established', 'plan to',
                            'prioritize', 'strategy', 'approach', 'determined']

        for meeting in self.meetings:
            if not meeting.summary:
                continue

            sentences = meeting.summary.split('.')
            for sentence in sentences:
                if any(keyword in sentence.lower() for keyword in decision_keywords):
                    decisions.append({
                        'meeting': meeting.title,
                        'date': meeting.date,
                        'decision': sentence.strip()
                    })

        return decisions

    def _synthesize_meeting_themes(self) -> Dict[str, List]:
        """
        Group meetings by type: Planning, Review, Retro, Stand-Up, Demo, Other
        """
        themes = {
            'Planning': [],
            'Review': [],
            'Retrospective': [],
            'Stand-Up': [],
            'Demo': [],
            'Other': []
        }

        for meeting in self.meetings:
            title_lower = meeting.title.lower()
            if 'planning' in title_lower:
                themes['Planning'].append(meeting)
            elif 'review' in title_lower:
                themes['Review'].append(meeting)
            elif 'retro' in title_lower:
                themes['Retrospective'].append(meeting)
            elif 'stand' in title_lower or 'standup' in title_lower:
                themes['Stand-Up'].append(meeting)
            elif 'demo' in title_lower:
                themes['Demo'].append(meeting)
            else:
                themes['Other'].append(meeting)

        # Remove empty themes
        return {k: v for k, v in themes.items() if v}

    def _assess_sprint_health(self) -> tuple:
        """
        Assess sprint health based on completion rate
        Returns: (emoji, status_text)
        """
        completion = self.metrics.completion_rate
        qa_pct = (self.metrics.qa_count / self.metrics.total_issues * 100) if self.metrics.total_issues > 0 else 0

        combined = completion + qa_pct

        if combined >= 70:
            return ("🟢", "On Track - Strong progress with high completion")
        elif combined >= 40:
            return ("🟡", f"On Track - {combined:.1f}% of issues completed or in QA/UVT")
        elif combined >= 20:
            return ("🟠", "At Risk - Lower than expected progress")
        else:
            return ("🔴", "Blocked - Minimal progress, needs attention")
