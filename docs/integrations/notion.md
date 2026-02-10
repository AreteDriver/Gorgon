# Notion Integration

Gorgon provides full Notion CRUD operations for databases, pages, and blocks with schema caching and property type parsing.

## Setup

```bash
# .env
NOTION_TOKEN=secret_...
```

Create an [internal integration](https://www.notion.so/my-integrations) and share target databases/pages with it.

## Usage

```python
from test_ai.api_clients import NotionClientWrapper

client = NotionClientWrapper()

# Query database with filter
pages = client.query_database(
    "database-id",
    filter={"property": "Status", "select": {"equals": "Active"}},
    sorts=[{"property": "Created", "direction": "descending"}]
)

# Create page
page = client.create_page("database-id", title="Meeting Notes", content="Q1 goals...")

# Read page content
blocks = client.read_page_content(page["id"])

# Update page properties
client.update_page(page["id"], {"Status": {"select": {"name": "Done"}}})

# Search workspace
results = client.search_pages("quarterly review")

# Append content
client.append_to_page(page["id"], "Follow-up: schedule next review")
```

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `query_database(db_id, filter, sorts)` | `List[Dict]` | Query with filters |
| `get_database_schema(db_id)` | `Dict` | Schema (cached 1hr) |
| `create_database_entry(db_id, properties)` | `Dict` | Create entry |
| `create_page(parent_id, title, content)` | `Dict` | Create page |
| `get_page(page_id)` | `Dict` | Get page metadata |
| `read_page_content(page_id)` | `List[Dict]` | Read all blocks |
| `update_page(page_id, properties)` | `Dict` | Update properties |
| `append_to_page(page_id, content)` | `Dict` | Append block |
| `archive_page(page_id)` | `Dict` | Soft-delete |
| `search_pages(query)` | `List[Dict]` | Search workspace |

All methods have `_async` variants.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `RATELIMIT_NOTION_RPM` | 30 | Requests per minute |
| `BULKHEAD_NOTION_CONCURRENT` | 3 | Max concurrent requests |

## Property Type Support

Automatic parsing for: title, rich_text, number, checkbox, url, email, phone_number, select, status, multi_select, relation, date, formula.
