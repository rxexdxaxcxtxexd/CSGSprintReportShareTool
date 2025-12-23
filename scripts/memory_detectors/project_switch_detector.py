"""
Project Switch Detector - Memory Trigger

Detects when the user switches between different projects and triggers
memory queries to retrieve project-specific context.

Detection scenarios:
- Git remote URL change (same directory, different remote)
- Git branch change (major branch switch, e.g., main -> feature-branch)
- Working directory change (moved to different project)
- Project name/identifier change

Author: Context-Aware Memory System
Date: 2025-12-23
"""

from pathlib import Path
from typing import Dict, Optional, Any

from . import MemoryDetector, TriggerResult

try:
    from project_tracker import ProjectTracker
except ImportError:
    # Try relative import if absolute fails
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from project_tracker import ProjectTracker


class ProjectSwitchDetector(MemoryDetector):
    """
    Detector for project context switches

    Triggers when user switches to a different project, enabling retrieval
    of project-specific memory context (decisions, architecture, issues).

    Priority: 1 (highest) - Project switches should trigger before other detectors
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize project switch detector

        Args:
            config: Configuration dict with optional keys:
                - priority: int - Detector priority (default: 1, highest)
                - enabled: bool - Whether detector is enabled
                - detect_branch_switch: bool - Detect branch changes (default: True)
                - major_branches: List[str] - Branches that trigger on switch (default: main, master, develop)
        """
        super().__init__(config)

        # Override priority to ensure this runs first
        if 'priority' not in config:
            self.priority = 1

        # Configuration options
        self.detect_branch_switch = config.get('detect_branch_switch', True)
        self.major_branches = config.get('major_branches', ['main', 'master', 'develop', 'development'])

        # Initialize project tracker
        self.tracker = ProjectTracker()

    @property
    def name(self) -> str:
        """Detector name"""
        return "project_switch_detector"

    def evaluate(self, prompt: str, context: Dict[str, Any]) -> Optional[TriggerResult]:
        """
        Evaluate if user has switched projects

        Args:
            prompt: User's message text (not used for project detection)
            context: Session context dict with keys:
                - current_project: dict with project metadata
                - cwd: str, current working directory
                - session_id: str, unique session identifier

        Returns:
            TriggerResult if project switch detected, None otherwise
        """
        # Get current project from context
        current_project = context.get('current_project')
        if not current_project:
            # No project information available
            return None

        # Get previous active project from tracker
        active_state = self.tracker.get_active_project()
        if not active_state:
            # First run - no previous project to compare
            # Update tracker with current project
            self._update_tracker_state(current_project)
            return None

        previous_project = active_state.get('project')
        if not previous_project:
            # Malformed state
            return None

        # Detect various types of switches
        switch_type, switch_details = self._detect_switch_type(
            current_project,
            previous_project
        )

        if switch_type:
            # Update tracker with new project
            self._update_tracker_state(current_project)

            # Build trigger result
            return self._build_trigger_result(
                current_project,
                previous_project,
                switch_type,
                switch_details
            )

        # No switch detected - update timestamp
        self._update_tracker_state(current_project)
        return None

    def _detect_switch_type(
        self,
        current: Dict[str, Any],
        previous: Dict[str, Any]
    ) -> tuple[Optional[str], Dict[str, Any]]:
        """
        Detect the type of project switch

        Args:
            current: Current project metadata
            previous: Previous project metadata

        Returns:
            Tuple of (switch_type, details_dict)
            switch_type: 'remote', 'directory', 'branch', or None
            details_dict: Additional context about the switch
        """
        details = {}

        # 1. Check for directory change (different projects)
        current_path = current.get('absolute_path', '')
        previous_path = previous.get('absolute_path', '')

        if current_path and previous_path:
            current_resolved = str(Path(current_path).resolve())
            previous_resolved = str(Path(previous_path).resolve())

            if current_resolved != previous_resolved:
                details['from_path'] = previous_path
                details['to_path'] = current_path
                details['from_project'] = previous.get('name', 'Unknown')
                details['to_project'] = current.get('name', 'Unknown')
                return 'directory', details

        # 2. Check for remote URL change (same directory, different remote)
        current_remote = current.get('git_remote_url', '')
        previous_remote = previous.get('git_remote_url', '')

        if current_remote and previous_remote:
            # Normalize URLs
            current_clean = current_remote.rstrip('.git').replace('http://', 'https://')
            previous_clean = previous_remote.rstrip('.git').replace('http://', 'https://')

            if current_clean != previous_clean:
                details['from_remote'] = previous_remote
                details['to_remote'] = current_remote
                details['project_name'] = current.get('name', 'Unknown')
                return 'remote', details

        # 3. Check for branch change (if enabled and on major branch)
        if self.detect_branch_switch:
            current_branch = current.get('git_branch', '')
            previous_branch = previous.get('git_branch', '')

            if current_branch and previous_branch and current_branch != previous_branch:
                # Only trigger on major branch switches
                is_major_switch = (
                    current_branch in self.major_branches or
                    previous_branch in self.major_branches
                )

                if is_major_switch:
                    details['from_branch'] = previous_branch
                    details['to_branch'] = current_branch
                    details['project_name'] = current.get('name', 'Unknown')
                    return 'branch', details

        # No switch detected
        return None, {}

    def _build_trigger_result(
        self,
        current_project: Dict[str, Any],
        previous_project: Dict[str, Any],
        switch_type: str,
        details: Dict[str, Any]
    ) -> TriggerResult:
        """
        Build a TriggerResult for the detected switch

        Args:
            current_project: Current project metadata
            previous_project: Previous project metadata
            switch_type: Type of switch detected
            details: Additional switch details

        Returns:
            TriggerResult with project context query
        """
        # Build query parameters
        project_name = current_project.get('name', 'Unknown')
        query_params = {
            'project': project_name,
            'project_path': current_project.get('absolute_path', ''),
            'git_remote': current_project.get('git_remote_url', ''),
            'branch': current_project.get('git_branch', ''),
            'switch_type': switch_type
        }

        # Build human-readable reason
        reason = self._build_reason_string(switch_type, details)

        # Calculate confidence based on switch type
        confidence = self._calculate_confidence(switch_type, current_project)

        return TriggerResult(
            triggered=True,
            confidence=confidence,
            estimated_tokens=200,  # Project context queries are typically ~200 tokens
            query_type="project_context",
            query_params=query_params,
            reason=reason
        )

    def _build_reason_string(self, switch_type: str, details: Dict[str, Any]) -> str:
        """
        Build human-readable explanation of switch

        Args:
            switch_type: Type of switch
            details: Switch details

        Returns:
            Explanation string
        """
        if switch_type == 'directory':
            from_proj = details.get('from_project', 'Unknown')
            to_proj = details.get('to_project', 'Unknown')
            return f"Switched projects: {from_proj} -> {to_proj}"

        elif switch_type == 'remote':
            from_remote = details.get('from_remote', 'unknown')
            to_remote = details.get('to_remote', 'unknown')
            # Shorten URLs for readability
            from_short = self._shorten_remote_url(from_remote)
            to_short = self._shorten_remote_url(to_remote)
            return f"Changed git remote: {from_short} -> {to_short}"

        elif switch_type == 'branch':
            from_branch = details.get('from_branch', 'unknown')
            to_branch = details.get('to_branch', 'unknown')
            project_name = details.get('project_name', 'project')
            return f"Switched branch in {project_name}: {from_branch} -> {to_branch}"

        return "Project context changed"

    def _shorten_remote_url(self, url: str) -> str:
        """
        Shorten git remote URL for display

        Args:
            url: Full git remote URL

        Returns:
            Shortened URL (e.g., github.com/user/repo)
        """
        import re

        if 'github.com' in url:
            match = re.search(r'github\.com[:/](.+?)(?:\.git)?$', url)
            if match:
                return f"github.com/{match.group(1)}"

        elif 'gitlab.com' in url:
            match = re.search(r'gitlab\.com[:/](.+?)(?:\.git)?$', url)
            if match:
                return f"gitlab.com/{match.group(1)}"

        elif 'bitbucket.org' in url:
            match = re.search(r'bitbucket\.org[:/](.+?)(?:\.git)?$', url)
            if match:
                return f"bitbucket.org/{match.group(1)}"

        # Fallback: return last 50 chars
        return url[-50:] if len(url) > 50 else url

    def _calculate_confidence(self, switch_type: str, current_project: Dict[str, Any]) -> float:
        """
        Calculate confidence score for this trigger

        Args:
            switch_type: Type of switch detected
            current_project: Current project metadata

        Returns:
            Confidence score 0.0-1.0
        """
        # Base confidence by switch type
        if switch_type == 'directory':
            confidence = 0.95  # Very confident - different directories
        elif switch_type == 'remote':
            confidence = 0.90  # High confidence - remote changed
        elif switch_type == 'branch':
            confidence = 0.75  # Moderate - branch switches are less critical
        else:
            confidence = 0.70  # Default

        # Boost confidence if project has git info (more reliable)
        if current_project.get('git_remote_url'):
            confidence = min(1.0, confidence + 0.05)

        return confidence

    def _update_tracker_state(self, current_project: Dict[str, Any]) -> None:
        """
        Update project tracker with current project state

        Args:
            current_project: Current project metadata
        """
        try:
            # Check for uncommitted changes if path available
            has_uncommitted = False
            project_path = current_project.get('absolute_path')
            if project_path:
                has_uncommitted = self.tracker.has_uncommitted_changes(Path(project_path))

            # Update active project
            self.tracker.set_active_project(
                project_metadata=current_project,
                has_uncommitted=has_uncommitted
            )
        except Exception as e:
            # Don't fail the detector if tracker update fails
            import sys
            print(f"Warning: Could not update project tracker: {e}", file=sys.stderr)


# Export
__all__ = ['ProjectSwitchDetector']
