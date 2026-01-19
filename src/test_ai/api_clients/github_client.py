"""GitHub API client wrapper with sync and async support."""

import asyncio
from typing import Optional, List, Dict

from github import Github, GithubException

from test_ai.config import get_settings
from test_ai.utils.retry import with_retry
from test_ai.errors import MaxRetriesError


class GitHubClient:
    """Wrapper for GitHub API with sync and async support.

    Provides both synchronous and asynchronous methods for API calls.
    Async methods are suffixed with '_async' (e.g., create_issue_async).

    Note: PyGithub doesn't have native async support, so async methods
    use asyncio.to_thread() to run sync calls in a thread pool.
    """

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

    # -------------------------------------------------------------------------
    # Async Methods (using asyncio.to_thread for compatibility)
    # -------------------------------------------------------------------------

    async def create_issue_async(
        self, repo_name: str, title: str, body: str, labels: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """Create an issue in a GitHub repository (async).

        Runs the sync method in a thread pool to avoid blocking.
        """
        return await asyncio.to_thread(
            self.create_issue, repo_name, title, body, labels
        )

    async def commit_file_async(
        self,
        repo_name: str,
        file_path: str,
        content: str,
        message: str,
        branch: str = "main",
    ) -> Optional[Dict]:
        """Commit a file to a GitHub repository (async).

        Runs the sync method in a thread pool to avoid blocking.
        """
        return await asyncio.to_thread(
            self.commit_file, repo_name, file_path, content, message, branch
        )

    async def list_repositories_async(self) -> List[Dict]:
        """List user repositories (async).

        Runs the sync method in a thread pool to avoid blocking.
        """
        return await asyncio.to_thread(self.list_repositories)

    async def get_repo_info_async(self, repo_name: str) -> Optional[Dict]:
        """Get repository information (async)."""
        return await asyncio.to_thread(self.get_repo_info, repo_name)

    def get_repo_info(self, repo_name: str) -> Optional[Dict]:
        """Get repository information."""
        if not self.is_configured():
            return None

        try:
            return self._get_repo_info_with_retry(repo_name)
        except (GithubException, MaxRetriesError) as e:
            return {"error": str(e)}

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    def _get_repo_info_with_retry(self, repo_name: str) -> Dict:
        """Get repo info with retry logic."""
        repo = self.client.get_repo(repo_name)
        return {
            "name": repo.full_name,
            "description": repo.description,
            "url": repo.html_url,
            "stars": repo.stargazers_count,
            "forks": repo.forks_count,
            "language": repo.language,
            "default_branch": repo.default_branch,
        }
