# GitHub Integration

Gorgon integrates with GitHub via PyGithub for repository management, issue tracking, and file operations.

## Setup

```bash
# .env
GITHUB_TOKEN=ghp_...
```

## Usage

```python
from test_ai.api_clients import GitHubClient

client = GitHubClient()

if client.is_configured():
    # List repositories
    repos = client.list_repositories()

    # Get repo details (cached 5 min)
    info = client.get_repo_info("owner/repo")

    # Create issue
    issue = client.create_issue(
        "owner/repo",
        title="Bug: login fails",
        body="Steps to reproduce...",
        labels=["bug"]
    )

    # Commit file
    result = client.commit_file(
        "owner/repo",
        "docs/guide.md",
        "# Guide\nContent here",
        "Add guide document"
    )
```

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `is_configured()` | `bool` | Check if token is set |
| `list_repositories()` | `List[Dict]` | First 20 user repos |
| `get_repo_info(repo_name)` | `Dict` | Repo details (cached) |
| `create_issue(repo, title, body, labels)` | `Dict` | Create GitHub issue |
| `commit_file(repo, path, content, message, branch)` | `Dict` | Create/update file |

All methods have `_async` variants using `asyncio.to_thread()`.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `RATELIMIT_GITHUB_RPM` | 30 | Requests per minute |
| `BULKHEAD_GITHUB_CONCURRENT` | 5 | Max concurrent requests |

## Workflow Example

```json
{
  "id": "create_issue",
  "type": "github",
  "action": "create_issue",
  "params": {
    "repo_name": "owner/repo",
    "title": "{{issue_title}}",
    "body": "{{issue_body}}"
  }
}
```
