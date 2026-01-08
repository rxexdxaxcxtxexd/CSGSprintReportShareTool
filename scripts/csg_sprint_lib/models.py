"""
Data models for CSG Sprint Reporter
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict


@dataclass
class JiraIssue:
    """Represents a Jira issue"""
    key: str
    summary: str
    status: str
    status_category: str  # new, indeterminate, done
    assignee: Optional[str]
    issue_type: str
    priority: str
    parent: Optional[str] = None

    @classmethod
    def from_api_response(cls, data: dict) -> 'JiraIssue':
        """Create JiraIssue from Jira API response"""
        fields = data.get('fields', {})

        # Extract assignee
        assignee_data = fields.get('assignee')
        assignee = assignee_data.get('displayName') if assignee_data else None

        # Extract status category
        status_data = fields.get('status', {})
        status_category_data = status_data.get('statusCategory', {})
        status_category = status_category_data.get('key', 'new')

        # Extract parent
        parent_data = fields.get('parent')
        parent = parent_data.get('key') if parent_data else None

        return cls(
            key=data.get('key', ''),
            summary=fields.get('summary', ''),
            status=status_data.get('name', 'Unknown'),
            status_category=status_category,
            assignee=assignee,
            issue_type=fields.get('issuetype', {}).get('name', 'Unknown'),
            priority=fields.get('priority', {}).get('name', 'Medium'),
            parent=parent
        )


@dataclass
class FathomMeeting:
    """Represents a Fathom meeting"""
    recording_id: int
    title: str
    date: datetime
    summary: Optional[str] = None
    action_items: List[str] = field(default_factory=list)

    @classmethod
    def from_api_response(cls, data: dict) -> 'FathomMeeting':
        """Create FathomMeeting from Fathom API response"""
        # Parse date from various possible formats (Fathom API uses recording_start_time or created_at)
        date_str = data.get('recording_start_time') or data.get('created_at', '')
        try:
            date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            date = datetime.now()

        # Extract action items if available
        action_items = []
        action_items_data = data.get('action_items')
        if action_items_data:  # Check if not None and not empty
            action_items = [item.get('text', '') for item in action_items_data]

        # Fathom API uses 'recording_id' field and 'title' or 'meeting_title'
        return cls(
            recording_id=data.get('recording_id', 0),
            title=data.get('title') or data.get('meeting_title', 'Untitled Meeting'),
            date=date,
            summary=data.get('default_summary'),
            action_items=action_items
        )


@dataclass
class SprintMetrics:
    """Aggregated sprint metrics"""
    total_issues: int
    done_count: int
    in_progress_count: int
    not_started_count: int
    completion_rate: float
    status_counts: Dict[str, int]
    assignee_stats: Dict[str, Dict[str, int]]
    epic_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    blockers: List[JiraIssue] = field(default_factory=list)
    qa_count: int = 0  # Count of issues in QA/UVT status
    ready_count: int = 0  # Count of ready-for-dev issues
