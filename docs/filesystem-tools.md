# Filesystem Tools for Chat Agents

Gorgon chat agents can access local project files to help with coding tasks. This enables agents to read code, understand project structure, and propose edits that require user approval.

## Overview

When you create a chat session with a `project_path`, agents gain access to filesystem tools:

- **read_file** - Read file content with line numbers
- **list_files** - List directory contents with glob patterns
- **search_code** - Search for patterns across files
- **get_structure** - Get project tree overview
- **propose_edit** - Propose file changes for user approval

## Quick Start

### 1. Create a Session with Project Path

```bash
curl -X POST http://localhost:8000/chat/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Code Review",
    "project_path": "/path/to/your/project",
    "filesystem_enabled": true
  }'
```

### 2. Ask About Files

Send messages like:
- "What files are in this project?"
- "Show me the main.py file"
- "Search for all functions that handle authentication"
- "Add a docstring to the main function"

### 3. Review Proposals

When the agent proposes edits, review them at:
```bash
GET /chat/sessions/{session_id}/proposals
```

Approve or reject:
```bash
POST /chat/sessions/{session_id}/proposals/{proposal_id}/approve
POST /chat/sessions/{session_id}/proposals/{proposal_id}/reject
```

## API Endpoints

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat/sessions` | Create session (include `project_path` for file access) |
| GET | `/chat/sessions/{id}` | Get session details |

### Proposals

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/chat/sessions/{id}/proposals` | List all proposals |
| GET | `/chat/sessions/{id}/proposals?status=pending` | List pending proposals |
| GET | `/chat/sessions/{id}/proposals/{pid}` | Get proposal with content |
| POST | `/chat/sessions/{id}/proposals/{pid}/approve` | Approve and apply |
| POST | `/chat/sessions/{id}/proposals/{pid}/reject` | Reject proposal |

## Security

### Path Validation

All file operations are constrained to the `project_path` directory:
- Path traversal attacks (`../`) are blocked
- Symlinks outside project bounds are rejected
- All paths are resolved and validated

### Excluded Patterns

The following patterns are automatically excluded:
- `.git/` - Git internals
- `node_modules/` - Node dependencies
- `__pycache__/` - Python cache
- `.venv/`, `venv/` - Virtual environments
- `.env`, `.env.*` - Environment files
- `*.pem`, `*.key` - Private keys
- `secrets.*`, `credentials.*` - Credential files

### Size Limits

- Maximum file size for reads: 1MB (configurable)
- Maximum results for listings/searches: 100 (configurable)

### Audit Logging

All file access is logged to the `file_access_log` table:
- Session ID
- Tool used
- File path accessed
- Operation type
- Success/failure status

## Tool Call Format

Agents use XML blocks to call tools:

```xml
<tool_call>
{"tool": "read_file", "path": "src/main.py"}
</tool_call>
```

Results are injected back:

```xml
<tool_result>
{"tool": "read_file", "success": true, "data": {...}}
</tool_result>
```

## Available Tools

### read_file

Read a file's content with optional line range.

```json
{
  "tool": "read_file",
  "path": "src/main.py",
  "start_line": 10,
  "end_line": 50
}
```

Response includes:
- Content with line numbers
- Total line count
- File size
- Truncation status

### list_files

List directory contents.

```json
{
  "tool": "list_files",
  "path": "src",
  "pattern": "*.py",
  "recursive": true
}
```

Response includes:
- File entries with names, paths, sizes
- Directory entries
- Total counts
- Truncation status

### search_code

Search for patterns in files (regex supported).

```json
{
  "tool": "search_code",
  "pattern": "def \\w+\\(",
  "path": "src",
  "file_pattern": "*.py",
  "case_sensitive": false,
  "max_results": 50
}
```

Response includes:
- Matches with file, line number, content
- Match positions
- Files searched count

### get_structure

Get project tree overview.

```json
{
  "tool": "get_structure",
  "max_depth": 4
}
```

Response includes:
- Tree-style representation
- Total files/directories
- File type breakdown

### propose_edit

Propose a file change (requires user approval).

```json
{
  "tool": "propose_edit",
  "path": "src/main.py",
  "new_content": "# Updated content...",
  "description": "Add docstring to main function"
}
```

Response includes:
- Proposal ID
- Status (pending)
- Approval instructions

## Database Schema

### edit_proposals

```sql
CREATE TABLE edit_proposals (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    old_content TEXT,
    new_content TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP,
    applied_at TIMESTAMP,
    error_message TEXT
);
```

### file_access_log

```sql
CREATE TABLE file_access_log (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    tool TEXT NOT NULL,
    file_path TEXT NOT NULL,
    operation TEXT NOT NULL,
    timestamp TIMESTAMP,
    success BOOLEAN,
    error_message TEXT
);
```

## Frontend Integration

The Gorgon web UI includes:

1. **New Chat Dialog** - Create sessions with project path
2. **File Access Badge** - Shows when filesystem tools are enabled
3. **Proposal Panel** - Review and approve/reject pending edits
4. **Diff View** - See before/after content comparison

## Configuration

### PathValidator Options

```python
PathValidator(
    project_path="/path/to/project",
    allowed_paths=["/additional/path"],  # Extra paths to allow
    exclude_patterns=[r"^custom_pattern"],  # Additional exclusions
    max_file_size=1024 * 1024,  # 1MB default
)
```

### FilesystemTools Options

```python
FilesystemTools(
    validator=validator,
    max_results=100,  # Max items in listings/searches
)
```

## Best Practices

1. **Always read before editing** - Agents should read files before proposing changes
2. **Keep edits focused** - Prefer small, targeted changes over large rewrites
3. **Review carefully** - Always review proposed changes before approving
4. **Use search** - Use `search_code` to find relevant code before making changes
5. **Check structure first** - Use `get_structure` to understand project layout

## Troubleshooting

### "Path is outside allowed directories"

The file path is outside the project directory. Check:
- `project_path` is set correctly on the session
- The path doesn't use `../` to escape
- Symlinks don't point outside the project

### "File exceeds size limit"

The file is larger than the configured maximum. Either:
- Increase `max_file_size` in PathValidator
- Read specific line ranges instead of the whole file

### "Path matches excluded pattern"

The file matches an exclusion pattern (e.g., `.git`, `node_modules`). These are intentionally blocked for security.

### "Filesystem tools not available"

Check that:
- `project_path` is set on the session
- `filesystem_enabled` is `true` (default when path is set)
- The project path exists and is a directory
