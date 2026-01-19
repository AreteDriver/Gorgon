"""Notion API client wrapper."""

from typing import Optional, Dict, List
from test_ai.config import get_settings
from test_ai.utils.retry import with_retry
from test_ai.errors import MaxRetriesError

try:
    from notion_client import Client as NotionClient
    from notion_client import APIResponseError
except ImportError:
    NotionClient = None
    APIResponseError = Exception


class NotionClientWrapper:
    """Wrapper for Notion API."""

    def __init__(self):
        settings = get_settings()
        if settings.notion_token and NotionClient:
            self.client = NotionClient(auth=settings.notion_token)
        else:
            self.client = None

    def is_configured(self) -> bool:
        """Check if Notion client is configured."""
        return self.client is not None

    def create_page(self, parent_id: str, title: str, content: str) -> Optional[Dict]:
        """Create a page in Notion."""
        if not self.is_configured():
            return None

        try:
            return self._create_page_with_retry(parent_id, title, content)
        except (APIResponseError, MaxRetriesError) as e:
            return {"error": str(e)}

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    def _create_page_with_retry(self, parent_id: str, title: str, content: str) -> Dict:
        """Create page with retry logic."""
        page = self.client.pages.create(
            parent={"database_id": parent_id},
            properties={"Name": {"title": [{"text": {"content": title}}]}},
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content}}]
                    },
                }
            ],
        )
        return {"id": page["id"], "url": page["url"]}

    def append_to_page(self, page_id: str, content: str) -> Optional[Dict]:
        """Append content to an existing Notion page."""
        if not self.is_configured():
            return None

        try:
            return self._append_to_page_with_retry(page_id, content)
        except (APIResponseError, MaxRetriesError) as e:
            return {"error": str(e)}

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    def _append_to_page_with_retry(self, page_id: str, content: str) -> Dict:
        """Append to page with retry logic."""
        block = self.client.blocks.children.append(
            block_id=page_id,
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content}}]
                    },
                }
            ],
        )
        return {"success": True, "block_id": block["results"][0]["id"]}

    def search_pages(self, query: str) -> List[Dict]:
        """Search for pages in Notion."""
        if not self.is_configured():
            return []

        try:
            return self._search_pages_with_retry(query)
        except (APIResponseError, MaxRetriesError):
            return []

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    def _search_pages_with_retry(self, query: str) -> List[Dict]:
        """Search pages with retry logic."""
        results = self.client.search(
            query=query, filter={"property": "object", "value": "page"}
        )
        return [
            {
                "id": page["id"],
                "title": page.get("properties", {})
                .get("Name", {})
                .get("title", [{}])[0]
                .get("text", {})
                .get("content", "Untitled"),
                "url": page.get("url", ""),
            }
            for page in results.get("results", [])
        ]
