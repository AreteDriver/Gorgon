# Gmail Integration

Gorgon provides read-only Gmail access via OAuth 2.0 for message listing, retrieval, and body extraction.

## Setup

1. Create a [Google Cloud project](https://console.cloud.google.com/) with Gmail API enabled
2. Create OAuth 2.0 credentials (Desktop application)
3. Download `credentials.json`

```bash
# .env
GMAIL_CREDENTIALS_PATH=path/to/credentials.json
```

## Authentication

First use triggers an OAuth browser flow. The token is cached in `token.json` for subsequent runs.

```python
from test_ai.api_clients import GmailClient

client = GmailClient()

if client.is_configured():
    client.authenticate()  # Opens browser on first run
```

**Scope**: `gmail.readonly` (read-only access)

## Usage

```python
# List recent messages
messages = client.list_messages(max_results=10)

# Search with Gmail query syntax
unread = client.list_messages(query="is:unread")
from_team = client.list_messages(query="from:team@company.com")

# Get full message
msg = client.get_message(messages[0]["id"])

# Extract body text
body = client.extract_email_body(msg)
```

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `is_configured()` | `bool` | Check if credentials path is set |
| `authenticate()` | `bool` | Run OAuth flow, return success |
| `list_messages(max_results, query)` | `List[Dict]` | List messages |
| `get_message(message_id)` | `Dict` | Get full message |
| `extract_email_body(message)` | `str` | Extract plain text body |

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `RATELIMIT_GMAIL_RPM` | 30 | Requests per minute |
| `BULKHEAD_GMAIL_CONCURRENT` | 5 | Max concurrent requests |

## Workflow Example

The `email_to_notion.json` workflow fetches unread emails, summarizes them with OpenAI, and creates Notion pages with the summaries.
