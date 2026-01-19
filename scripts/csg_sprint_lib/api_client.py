"""
API clients for Jira and Fathom
Direct HTTP calls without MCP dependency
"""

import requests
import time
import logging
from typing import List, Optional, Dict
from datetime import datetime
from .models import JiraIssue, FathomMeeting

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors"""
    pass


class AuthenticationError(APIError):
    """Authentication failed"""
    pass


class RateLimitError(APIError):
    """Rate limit exceeded"""
    pass


class CreditExhaustedError(APIError):
    """Claude API credits exhausted"""
    def __init__(self, message: str, admin_contact: Optional[str] = None):
        super().__init__(message)
        self.admin_contact = admin_contact


def fetch_with_retry(api_call, max_retries=3):
    """Retry API call with exponential backoff on network errors"""
    for attempt in range(max_retries):
        try:
            return api_call()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                delay = 5 * (2 ** attempt)  # 5s, 10s, 20s
                print(f"   Retry {attempt+1}/{max_retries} in {delay}s...")
                time.sleep(delay)
            else:
                raise APIError(f"Network error after {max_retries} attempts: {e}")
        except requests.exceptions.HTTPError as e:
            # Handle rate limiting
            if e.response.status_code == 429:
                if attempt < max_retries - 1:
                    delay = 10 * (2 ** attempt)  # 10s, 20s, 40s
                    print(f"   Rate limited. Retry {attempt+1}/{max_retries} in {delay}s...")
                    time.sleep(delay)
                else:
                    raise RateLimitError("Rate limit exceeded")
            elif e.response.status_code == 410:
                # Don't retry 410 Gone - resource deleted/archived
                raise ValueError(
                    "Resource no longer available (410 Gone). "
                    "This sprint may have been archived or deleted in Jira. "
                    "Try a different sprint number or check your board configuration."
                )
            else:
                raise


class JiraClient:
    """Client for Jira REST API v3"""

    def __init__(self, site_name: str, email: str, api_token: str):
        self.base_url = f"https://{site_name}.atlassian.net"
        self.api_v3_url = f"{self.base_url}/rest/api/3"
        self.agile_url = f"{self.base_url}/rest/agile/1.0"
        self.auth = (email, api_token)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })

    def test_connection(self) -> bool:
        """Test Jira authentication"""
        try:
            response = self.session.get(f"{self.api_v3_url}/myself", timeout=10)
            response.raise_for_status()
            return True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [401, 403]:
                return False
            raise
        except Exception:
            return False

    def get_sprint_by_number(self, board_id: int, sprint_num: int) -> Optional[Dict]:
        """Get sprint by number from a board - returns first BOPS sprint if multiple matches"""
        def call():
            # Fetch all sprints from board (paginated)
            start_at = 0
            max_results = 50
            matching_sprints = []

            while True:
                url = f"{self.agile_url}/board/{board_id}/sprint"
                params = {"startAt": start_at, "maxResults": max_results}
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                # Collect ALL sprints matching the number
                for sprint in data.get('values', []):
                    sprint_name = sprint.get('name', '')
                    # Extract sprint number from name (e.g., "BOPS: Sprint 13" -> 13)
                    if f"Sprint {sprint_num}" in sprint_name or sprint_name.endswith(str(sprint_num)):
                        matching_sprints.append(sprint)

                # Check if there are more sprints
                if data.get('isLast', True):
                    break
                start_at += max_results

            # If no matches, return None
            if not matching_sprints:
                return None

            # If only one match, return it
            if len(matching_sprints) == 1:
                return matching_sprints[0]

            # If multiple matches, prioritize BOPS sprints (for iBOPS team)
            # But also print warning so user knows there are multiple
            logger.warning(f"Found {len(matching_sprints)} sprints matching number {sprint_num}:")
            for sprint in matching_sprints:
                logger.warning(f"  - {sprint.get('name')} (ID: {sprint.get('id')})")

            # Prioritize BOPS: prefix (iBOPS team work)
            for sprint in matching_sprints:
                if sprint.get('name', '').startswith('BOPS:'):
                    logger.warning(f"Selected: {sprint.get('name')} (BOPS team sprint)")
                    return sprint

            # If no BOPS sprint, return first match and warn
            logger.warning(f"No BOPS sprint found, using: {matching_sprints[0].get('name')}")
            return matching_sprints[0]

        return fetch_with_retry(call)

    def get_board_name(self, board_id: int) -> str:
        """Get board name by ID"""
        def call():
            url = f"{self.agile_url}/board/{board_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('name', f'Board {board_id}')

        try:
            return fetch_with_retry(call)
        except Exception as e:
            logger.warning(f"Could not fetch board name for board {board_id}: {e}")
            return f"Board {board_id}"

    def get_sprint_issues(self, board_id: int, sprint_id: int) -> List[JiraIssue]:
        """Get all issues in a sprint (paginated) using Agile API"""
        def call():
            issues = []
            start_at = 0
            max_results = 100

            while True:
                # Use Agile API endpoint instead of JQL search (which returns 410 for some sprints)
                url = f"{self.agile_url}/sprint/{sprint_id}/issue"
                params = {
                    "startAt": start_at,
                    "maxResults": max_results,
                    "fields": "summary,status,assignee,issuetype,priority,parent"
                }
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                # Parse issues
                for issue_data in data.get('issues', []):
                    issues.append(JiraIssue.from_api_response(issue_data))

                # Check if there are more issues
                if start_at + max_results >= data.get('total', 0):
                    break
                start_at += max_results

            return issues

        return fetch_with_retry(call)

    def search_issues(self, jql: str) -> List[JiraIssue]:
        """Generic JQL search with pagination"""
        def call():
            issues = []
            start_at = 0
            max_results = 100

            while True:
                url = f"{self.api_v3_url}/search/jql"
                params = {
                    "jql": jql,
                    "startAt": start_at,
                    "maxResults": max_results,
                    "fields": "summary,status,assignee,issuetype,priority,parent"
                }
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                # Parse issues
                for issue_data in data.get('issues', []):
                    issues.append(JiraIssue.from_api_response(issue_data))

                # Check if there are more issues
                if start_at + max_results >= data.get('total', 0):
                    break
                start_at += max_results

            return issues

        return fetch_with_retry(call)


class FathomClient:
    """Client for Fathom API v1"""

    def __init__(self, api_key: str):
        self.base_url = "https://api.fathom.ai/external/v1"
        self.headers = {
            "X-Api-Key": api_key,
            "Accept": "application/json"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def test_connection(self) -> bool:
        """Test Fathom API key"""
        try:
            # Try to list meetings with limit 1
            url = f"{self.base_url}/meetings"
            params = {"per_page": 1}
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [401, 403]:
                return False
            raise
        except Exception:
            return False

    def search_meetings(self, title_filter: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[FathomMeeting]:
        """Search meetings by title and date range"""
        logger.info(f"Searching Fathom meetings: filter='{title_filter}', start={start_date}, end={end_date}")

        def call():
            meetings = []
            cursor = None
            per_page = 50
            page_num = 1
            total_fetched = 0

            while True:
                url = f"{self.base_url}/meetings"
                params = {"per_page": per_page}

                # Add date filters if provided
                if start_date:
                    params["created_after"] = start_date.isoformat()
                if end_date:
                    params["created_before"] = end_date.isoformat()
                if cursor:
                    params["cursor"] = cursor

                logger.debug(f"Fetching page {page_num}: {url} with params {params}")
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                # Fathom API returns 'items' not 'meetings'
                meetings_in_page = data.get('items', [])
                total_fetched += len(meetings_in_page)
                logger.debug(f"Page {page_num}: Got {len(meetings_in_page)} meetings (total fetched: {total_fetched})")

                # Filter meetings by title
                matched_in_page = 0
                for meeting_data in meetings_in_page:
                    title = meeting_data.get('title', '')
                    # Check if title contains any of the filter keywords
                    keywords = title_filter.split()
                    matches = any(keyword.lower() in title.lower() for keyword in keywords)

                    if matches:
                        matched_in_page += 1
                        meeting = FathomMeeting.from_api_response(meeting_data)
                        meetings.append(meeting)
                        logger.debug(f"  ✓ Match: '{title}' (keywords: {keywords})")
                    else:
                        logger.debug(f"  ✗ No match: '{title}' (keywords: {keywords})")

                logger.info(f"Page {page_num}: {matched_in_page} matches out of {len(meetings_in_page)} meetings")

                # Check for next page
                cursor = data.get('next_cursor')
                if not cursor:
                    logger.info(f"No more pages. Total: {len(meetings)} matched out of {total_fetched} fetched")
                    break

                page_num += 1

            return meetings

        return fetch_with_retry(call)

    def get_meeting_details(self, recording_id: int) -> Dict:
        """
        Get full meeting details - DEPRECATED

        The Fathom /meetings/{id} endpoint returns 404 for all meetings.
        Meeting details (summary, action_items) are already included in the
        /meetings list endpoint response, so no additional call needed.

        This method is kept for backward compatibility but returns empty dict.
        """
        logger.warning(f"get_meeting_details() called but not needed - details already in list response")
        return {}


class ClaudeClient:
    """Client for Claude API - AI-powered report synthesis"""

    def __init__(self, api_key: str, key_metadata: Optional[Dict] = None):
        self.api_key = api_key
        self.key_metadata = key_metadata or {}
        try:
            from anthropic import Anthropic, RateLimitError, AuthenticationError
            self.client = Anthropic(api_key=api_key)
            self.available = True
            # Store exception classes for cleaner exception handling
            self.RateLimitError = RateLimitError
            self.AuthenticationError = AuthenticationError
        except ImportError:
            logger.error("anthropic package not installed. Install with: pip install anthropic")
            self.available = False
            # Define dummy exception classes so isinstance checks don't fail
            self.RateLimitError = Exception
            self.AuthenticationError = Exception
        except Exception as e:
            logger.error(f"Failed to initialize Claude client: {e}")
            self.available = False
            # Define dummy exception classes for safety
            self.RateLimitError = Exception
            self.AuthenticationError = Exception

    def _is_credit_exhaustion_error(self, error) -> bool:
        """
        Check if RateLimitError is due to credit exhaustion using multi-tier detection.

        Priority 1: HTTP status code (402 = Payment Required)
        Priority 2: Check error attributes (type, code, error_type)
        Priority 3: Keyword matching in error message (fallback)

        Returns True if error indicates insufficient credits/quota.
        """
        # Priority 1: Check HTTP status code for payment issues
        if hasattr(error, 'status_code'):
            # 402 Payment Required = definite billing issue
            if error.status_code == 402:
                logger.info("Credit exhaustion detected via HTTP 402 status code")
                return True
            # 429 could be rate limit OR billing - need to check message
            # Other codes (401, 403, etc.) are not credit exhaustion
            if error.status_code != 429:
                return False

        # Priority 2: Check structured error attributes if available
        # Anthropic SDK may include type/code fields in response
        if hasattr(error, 'type') and error.type in ['insufficient_quota', 'billing_error', 'payment_required']:
            logger.info(f"Credit exhaustion detected via error type: {error.type}")
            return True

        if hasattr(error, 'code') and error.code in ['insufficient_quota', 'payment_required', 'billing_error']:
            logger.info(f"Credit exhaustion detected via error code: {error.code}")
            return True

        # Priority 3: Fallback to keyword matching in error message
        # This catches cases where structured data isn't available
        error_msg = str(error).lower()
        credit_keywords = [
            "credit", "billing", "balance", "quota",
            "insufficient funds", "payment", "account limit"
        ]

        if any(keyword in error_msg for keyword in credit_keywords):
            logger.warning(f"Credit exhaustion detected via keyword matching (fallback): {error_msg[:100]}")
            return True

        # If none of the above matched, it's likely a regular rate limit
        return False

    def test_connection(self) -> bool:
        """Test Claude API key validity"""
        if not self.available:
            return False

        try:
            # Make a minimal API call to test authentication
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            return True
        except self.AuthenticationError as e:
            logger.error(f"Claude API authentication failed: {e}")
            return False
        except self.RateLimitError as e:
            if self._is_credit_exhaustion_error(e):
                logger.error(f"Claude API credits exhausted: {e}")
                return False
            else:
                logger.warning(f"Claude API rate limited (retry later): {e}")
                return False
        except Exception as e:
            logger.error(f"Claude API test failed: {e}")
            return False

    def synthesize_meeting_insights(self, meetings: List[Dict], sprint_context: str) -> Dict[str, str]:
        """
        Use Claude to synthesize meeting insights into narrative sections

        Returns dict with:
        - executive_summary: AI-generated sprint summary
        - key_decisions: Extracted decisions with context
        - meeting_themes: Grouped and synthesized meeting insights
        """
        if not self.available:
            logger.warning("Claude client not available, skipping AI synthesis")
            return {
                "executive_summary": "",
                "key_decisions": "",
                "meeting_themes": ""
            }

        try:
            # Prepare meeting data for Claude
            meeting_summaries = []
            for meeting in meetings:
                meeting_summaries.append(f"""
Meeting: {meeting.get('title', 'Untitled')}
Date: {meeting.get('date', 'Unknown')}
Summary: {meeting.get('summary', 'No summary')}
Action Items: {', '.join(meeting.get('action_items', [])) if meeting.get('action_items') else 'None'}
---
""")

            prompt = f"""You are analyzing sprint meetings to create a professional sprint report.

SPRINT CONTEXT:
{sprint_context}

MEETINGS ({len(meetings)} total):
{''.join(meeting_summaries)}

Please provide:

1. EXECUTIVE SUMMARY (2-3 sentences):
Synthesize the overall sprint progress and health based on meeting discussions.

2. KEY DECISIONS (bullet list):
Extract major decisions made during the sprint with context about when/why.

3. MEETING THEMES:
Group meetings by theme (Planning, Stand-Ups, Reviews, Demos) and provide a 1-2 sentence synthesis for each theme.

Format your response as:
## EXECUTIVE SUMMARY
[your summary]

## KEY DECISIONS
- [decision 1]
- [decision 2]

## MEETING THEMES
### [Theme 1]
[synthesis]

### [Theme 2]
[synthesis]
"""

            logger.info("Calling Claude API for meeting synthesis...")
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse response
            content = response.content[0].text

            # Extract sections
            result = {
                "executive_summary": self._extract_section(content, "EXECUTIVE SUMMARY", "KEY DECISIONS"),
                "key_decisions": self._extract_section(content, "KEY DECISIONS", "MEETING THEMES"),
                "meeting_themes": self._extract_section(content, "MEETING THEMES", None)
            }

            logger.info(f"AI synthesis complete. Tokens used: {response.usage.input_tokens + response.usage.output_tokens}")
            return result

        except self.RateLimitError as e:
            if self._is_credit_exhaustion_error(e):
                logger.error(f"Claude API credits exhausted: {e}")
                admin_contact = self.key_metadata.get("admin_contact")
                raise CreditExhaustedError(
                    "Shared Claude API key has run out of credits",
                    admin_contact=admin_contact
                )
            else:
                logger.error(f"Claude API rate limited: {e}")
                return {
                    "executive_summary": "",
                    "key_decisions": "",
                    "meeting_themes": ""
                }
        except self.AuthenticationError as e:
            logger.error(f"Claude API authentication failed: {e}")
            return {
                "executive_summary": "",
                "key_decisions": "",
                "meeting_themes": ""
            }
        except Exception as e:
            logger.error(f"Claude API synthesis failed: {e}")
            return {
                "executive_summary": "",
                "key_decisions": "",
                "meeting_themes": ""
            }

    def _extract_section(self, text: str, start_marker: str, end_marker: Optional[str]) -> str:
        """Extract content between two section markers"""
        try:
            start_idx = text.find(f"## {start_marker}")
            if start_idx == -1:
                return ""

            start_idx = text.find("\n", start_idx) + 1

            if end_marker:
                end_idx = text.find(f"## {end_marker}", start_idx)
                if end_idx == -1:
                    end_idx = len(text)
            else:
                end_idx = len(text)

            return text[start_idx:end_idx].strip()
        except Exception:
            return ""
