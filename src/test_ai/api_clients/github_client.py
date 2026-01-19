"""GitHub API client wrapper."""

from typing import Optional, List, Dict
from github import Github, GithubException

from test_ai.config import get_settings
from test_ai.utils.retry import with_retry
from test_ai.errors import MaxRetriesError


class GitHubClient:
    """Wrapper for GitHub API."""

    def __init__(self):
        settings = get_settings()
        if settings.github_token:
            self.client = Github(settings.github_token)
        else:
            self.client = None

    def is_configured(self) -> bool:
        """Check if GitHub client is configured."""
        return self.client is not None

    def create_issue(
        self, repo_name: str, title: str, body: str, labels: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """Create an issue in a GitHub repository."""
        if not self.is_configured():
            return None

        try:
            return self._create_issue_with_retry(repo_name, title, body, labels)
        except (GithubException, MaxRetriesError) as e:
            return {"error": str(e)}

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    def _create_issue_with_retry(
        self, repo_name: str, title: str, body: str, labels: Optional[List[str]]
    ) -> Dict:
        """Create issue with retry logic."""
        repo = self.client.get_repo(repo_name)
        issue = repo.create_issue(title=title, body=body, labels=labels or [])
        return {"number": issue.number, "url": issue.html_url, "title": issue.title}

    def commit_file(
        self,
        repo_name: str,
        file_path: str,
        content: str,
        message: str,
        branch: str = "main",
    ) -> Optional[Dict]:
        """Commit a file to a GitHub repository."""
        if not self.is_configured():
            return None

        try:
            return self._commit_file_with_retry(
                repo_name, file_path, content, message, branch
            )
        except (GithubException, MaxRetriesError) as e:
            return {"error": str(e)}

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    def _commit_file_with_retry(
        self,
        repo_name: str,
        file_path: str,
        content: str,
        message: str,
        branch: str,
    ) -> Dict:
        """Commit file with retry logic."""
        repo = self.client.get_repo(repo_name)

        try:
            file = repo.get_contents(file_path, ref=branch)
            result = repo.update_file(
                file_path, message, content, file.sha, branch=branch
            )
        except GithubException:
            result = repo.create_file(file_path, message, content, branch=branch)

        return {
            "commit_sha": result["commit"].sha,
            "url": result["content"].html_url,
        }

    def list_repositories(self) -> List[Dict]:
        """List user repositories."""
        if not self.is_configured():
            return []

        try:
            return self._list_repos_with_retry()
        except (GithubException, MaxRetriesError):
            return []

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    def _list_repos_with_retry(self) -> List[Dict]:
        """List repos with retry logic."""
        repos = self.client.get_user().get_repos()
        return [
            {
                "name": repo.full_name,
                "description": repo.description,
                "url": repo.html_url,
            }
            for repo in repos[:20]
        ]
