"""Webhook delivery with retries and dead-letter queue support.

Provides reliable outbound webhook delivery with:
- Configurable retry strategy with exponential backoff
- Dead-letter queue for failed deliveries
- Async and sync delivery options
- Delivery status tracking and history
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
import requests
from pydantic import BaseModel, Field

from test_ai.http import get_sync_client, get_async_client
from test_ai.state import DatabaseBackend, get_database

logger = logging.getLogger(__name__)


class DeliveryStatus(str, Enum):
    """Status of a webhook delivery attempt."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


class WebhookDelivery(BaseModel):
    """A webhook delivery record."""

    id: Optional[int] = None
    webhook_url: str
    payload: Dict[str, Any]
    headers: Dict[str, str] = Field(default_factory=dict)
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempt_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    last_attempt_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None


class RetryStrategy:
    """Configurable retry strategy with exponential backoff."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        """Initialize retry strategy.

        Args:
            max_retries: Maximum retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay between retries
            exponential_base: Base for exponential backoff
            jitter: Add randomization to prevent thundering herd
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number."""
        delay = self.base_delay * (self.exponential_base**attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            import random

            delay *= 0.5 + random.random()  # 50-150% of calculated delay

        return delay


class WebhookDeliveryManager:
    """Manages webhook delivery with retries and dead-letter queue."""

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS webhook_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            webhook_url TEXT NOT NULL,
            payload TEXT NOT NULL,
            headers TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            attempt_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            last_error TEXT,
            last_attempt_at TIMESTAMP,
            next_retry_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            response_status INTEGER,
            response_body TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_deliveries_status
        ON webhook_deliveries(status);

        CREATE INDEX IF NOT EXISTS idx_deliveries_next_retry
        ON webhook_deliveries(next_retry_at)
        WHERE status = 'retrying';

        CREATE TABLE IF NOT EXISTS webhook_dead_letter (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            delivery_id INTEGER NOT NULL,
            webhook_url TEXT NOT NULL,
            payload TEXT NOT NULL,
            headers TEXT,
            error TEXT,
            attempt_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reprocessed_at TIMESTAMP,
            FOREIGN KEY (delivery_id) REFERENCES webhook_deliveries(id)
        );

        CREATE INDEX IF NOT EXISTS idx_dlq_reprocessed
        ON webhook_dead_letter(reprocessed_at)
        WHERE reprocessed_at IS NULL;
    """

    def __init__(
        self,
        backend: DatabaseBackend | None = None,
        retry_strategy: RetryStrategy | None = None,
        timeout: float = 10.0,
    ):
        """Initialize delivery manager.

        Args:
            backend: Database backend (defaults to global)
            retry_strategy: Custom retry strategy
            timeout: Request timeout in seconds
        """
        self.backend = backend or get_database()
        self.retry_strategy = retry_strategy or RetryStrategy()
        self.timeout = timeout
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema."""
        self.backend.executescript(self.SCHEMA)

    def _generate_signature(
        self, payload: bytes, secret: str, algorithm: str = "sha256"
    ) -> str:
        """Generate HMAC signature for payload."""
        return (
            f"{algorithm}="
            + hmac.new(
                secret.encode(), payload, getattr(hashlib, algorithm)
            ).hexdigest()
        )

    def deliver(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str] | None = None,
        secret: str | None = None,
        max_retries: int | None = None,
    ) -> WebhookDelivery:
        """Deliver a webhook synchronously with retries.

        Args:
            url: Webhook URL
            payload: JSON payload
            headers: Custom headers
            secret: Secret for HMAC signature
            max_retries: Override default max retries

        Returns:
            WebhookDelivery with final status
        """
        headers = headers or {}
        max_retries = (
            max_retries if max_retries is not None else self.retry_strategy.max_retries
        )

        delivery = WebhookDelivery(
            webhook_url=url,
            payload=payload,
            headers=headers,
            max_retries=max_retries,
        )
        delivery = self._save_delivery(delivery)

        # Add signature if secret provided
        payload_bytes = json.dumps(payload).encode("utf-8")
        if secret:
            headers["X-Webhook-Signature"] = self._generate_signature(
                payload_bytes, secret
            )

        headers["Content-Type"] = "application/json"

        # Use pooled HTTP client for connection reuse
        client = get_sync_client()

        while delivery.attempt_count <= max_retries:
            delivery.attempt_count += 1
            delivery.last_attempt_at = datetime.now()
            delivery.status = (
                DeliveryStatus.RETRYING
                if delivery.attempt_count > 1
                else DeliveryStatus.PENDING
            )

            try:
                response = client.post(
                    url,
                    data=payload_bytes,
                    headers=headers,
                    timeout=self.timeout,
                )

                delivery.response_status = response.status_code
                delivery.response_body = response.text[:1000]

                if response.ok:
                    delivery.status = DeliveryStatus.SUCCESS
                    delivery.completed_at = datetime.now()
                    self._save_delivery(delivery)
                    logger.info(f"Webhook delivered successfully: {url}")
                    return delivery

                # Non-2xx response
                delivery.last_error = f"HTTP {response.status_code}"

            except requests.exceptions.Timeout:
                delivery.last_error = "Request timeout"
                logger.warning(
                    f"Webhook delivery timeout (attempt {delivery.attempt_count})"
                )

            except requests.exceptions.ConnectionError as e:
                delivery.last_error = f"Connection error: {e}"
                logger.warning(
                    f"Webhook delivery failed (attempt {delivery.attempt_count}): {delivery.last_error}"
                )

            except requests.exceptions.RequestException as e:
                delivery.last_error = str(e)
                logger.warning(
                    f"Webhook delivery failed (attempt {delivery.attempt_count}): {delivery.last_error}"
                )

            # Check if we should retry
            if delivery.attempt_count < max_retries:
                delay = self.retry_strategy.get_delay(delivery.attempt_count)
                delivery.next_retry_at = datetime.now() + timedelta(seconds=delay)
                self._save_delivery(delivery)
                time.sleep(delay)
            else:
                break

        # Max retries exceeded - move to dead letter queue
        delivery.status = DeliveryStatus.DEAD_LETTER
        delivery.completed_at = datetime.now()
        self._save_delivery(delivery)
        self._add_to_dlq(delivery)
        logger.error(
            f"Webhook delivery failed after {max_retries} retries, moved to DLQ: {url}"
        )

        return delivery

    async def deliver_async(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str] | None = None,
        secret: str | None = None,
        max_retries: int | None = None,
    ) -> WebhookDelivery:
        """Deliver a webhook asynchronously with retries.

        Args:
            url: Webhook URL
            payload: JSON payload
            headers: Custom headers
            secret: Secret for HMAC signature
            max_retries: Override default max retries

        Returns:
            WebhookDelivery with final status
        """
        headers = headers or {}
        max_retries = (
            max_retries if max_retries is not None else self.retry_strategy.max_retries
        )

        delivery = WebhookDelivery(
            webhook_url=url,
            payload=payload,
            headers=headers,
            max_retries=max_retries,
        )
        delivery = self._save_delivery(delivery)

        # Add signature if secret provided
        payload_bytes = json.dumps(payload).encode("utf-8")
        if secret:
            headers["X-Webhook-Signature"] = self._generate_signature(
                payload_bytes, secret
            )

        headers["Content-Type"] = "application/json"

        # Use pooled async HTTP client for connection reuse
        async with get_async_client() as client:
            while delivery.attempt_count <= max_retries:
                delivery.attempt_count += 1
                delivery.last_attempt_at = datetime.now()
                delivery.status = (
                    DeliveryStatus.RETRYING
                    if delivery.attempt_count > 1
                    else DeliveryStatus.PENDING
                )

                try:
                    response = await client.post(
                        url, content=payload_bytes, headers=headers
                    )
                    delivery.response_status = response.status_code
                    delivery.response_body = response.text[:1000]

                    if response.is_success:
                        delivery.status = DeliveryStatus.SUCCESS
                        delivery.completed_at = datetime.now()
                        self._save_delivery(delivery)
                        logger.info(f"Webhook delivered successfully (async): {url}")
                        return delivery

                    delivery.last_error = f"HTTP {response.status_code}"

                except httpx.TimeoutException:
                    delivery.last_error = "Request timeout"
                    logger.warning(
                        f"Webhook delivery timeout (attempt {delivery.attempt_count})"
                    )

                except httpx.RequestError as e:
                    delivery.last_error = str(e)
                    logger.warning(
                        f"Webhook delivery failed (attempt {delivery.attempt_count}): {delivery.last_error}"
                    )

                except Exception as e:
                    delivery.last_error = str(e)
                    logger.warning(
                        f"Webhook delivery failed (attempt {delivery.attempt_count}): {delivery.last_error}"
                    )

                # Check if we should retry
                if delivery.attempt_count < max_retries:
                    delay = self.retry_strategy.get_delay(delivery.attempt_count)
                    delivery.next_retry_at = datetime.now() + timedelta(seconds=delay)
                    self._save_delivery(delivery)
                    await asyncio.sleep(delay)
                else:
                    break

        # Max retries exceeded - move to dead letter queue
        delivery.status = DeliveryStatus.DEAD_LETTER
        delivery.completed_at = datetime.now()
        self._save_delivery(delivery)
        self._add_to_dlq(delivery)
        logger.error(
            f"Webhook delivery failed after {max_retries} retries, moved to DLQ: {url}"
        )

        return delivery

    def _save_delivery(self, delivery: WebhookDelivery) -> WebhookDelivery:
        """Save delivery to database."""
        try:
            if delivery.id is None:
                # Insert new
                with self.backend.transaction():
                    self.backend.execute(
                        """
                        INSERT INTO webhook_deliveries
                        (webhook_url, payload, headers, status, attempt_count,
                         max_retries, last_error, last_attempt_at, next_retry_at,
                         created_at, completed_at, response_status, response_body)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            delivery.webhook_url,
                            json.dumps(delivery.payload),
                            json.dumps(delivery.headers),
                            delivery.status.value,
                            delivery.attempt_count,
                            delivery.max_retries,
                            delivery.last_error,
                            delivery.last_attempt_at.isoformat()
                            if delivery.last_attempt_at
                            else None,
                            delivery.next_retry_at.isoformat()
                            if delivery.next_retry_at
                            else None,
                            delivery.created_at.isoformat(),
                            delivery.completed_at.isoformat()
                            if delivery.completed_at
                            else None,
                            delivery.response_status,
                            delivery.response_body,
                        ),
                    )
                    row = self.backend.fetchone("SELECT last_insert_rowid() as id")
                    delivery.id = row["id"]
            else:
                # Update existing
                with self.backend.transaction():
                    self.backend.execute(
                        """
                        UPDATE webhook_deliveries
                        SET status = ?, attempt_count = ?, last_error = ?,
                            last_attempt_at = ?, next_retry_at = ?, completed_at = ?,
                            response_status = ?, response_body = ?
                        WHERE id = ?
                        """,
                        (
                            delivery.status.value,
                            delivery.attempt_count,
                            delivery.last_error,
                            delivery.last_attempt_at.isoformat()
                            if delivery.last_attempt_at
                            else None,
                            delivery.next_retry_at.isoformat()
                            if delivery.next_retry_at
                            else None,
                            delivery.completed_at.isoformat()
                            if delivery.completed_at
                            else None,
                            delivery.response_status,
                            delivery.response_body,
                            delivery.id,
                        ),
                    )
        except Exception as e:
            logger.error(f"Failed to save delivery: {e}")

        return delivery

    def _add_to_dlq(self, delivery: WebhookDelivery):
        """Add failed delivery to dead-letter queue."""
        try:
            with self.backend.transaction():
                self.backend.execute(
                    """
                    INSERT INTO webhook_dead_letter
                    (delivery_id, webhook_url, payload, headers, error, attempt_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        delivery.id,
                        delivery.webhook_url,
                        json.dumps(delivery.payload),
                        json.dumps(delivery.headers),
                        delivery.last_error,
                        delivery.attempt_count,
                    ),
                )
        except Exception as e:
            logger.error(f"Failed to add to DLQ: {e}")

    def get_dlq_items(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get items from dead-letter queue that haven't been reprocessed."""
        rows = self.backend.fetchall(
            """
            SELECT * FROM webhook_dead_letter
            WHERE reprocessed_at IS NULL
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in rows]

    def reprocess_dlq_item(self, dlq_id: int) -> WebhookDelivery:
        """Reprocess a single item from the dead-letter queue.

        Args:
            dlq_id: Dead-letter queue item ID

        Returns:
            New WebhookDelivery result
        """
        row = self.backend.fetchone(
            "SELECT * FROM webhook_dead_letter WHERE id = ?", (dlq_id,)
        )
        if not row:
            raise ValueError(f"DLQ item {dlq_id} not found")

        # Mark as reprocessed
        with self.backend.transaction():
            self.backend.execute(
                "UPDATE webhook_dead_letter SET reprocessed_at = ? WHERE id = ?",
                (datetime.now().isoformat(), dlq_id),
            )

        # Redeliver
        return self.deliver(
            url=row["webhook_url"],
            payload=json.loads(row["payload"]),
            headers=json.loads(row["headers"]) if row["headers"] else None,
        )

    def get_delivery_stats(self) -> Dict[str, Any]:
        """Get delivery statistics."""
        stats = {}

        # Count by status
        for status in DeliveryStatus:
            row = self.backend.fetchone(
                "SELECT COUNT(*) as count FROM webhook_deliveries WHERE status = ?",
                (status.value,),
            )
            stats[f"{status.value}_count"] = row["count"]

        # DLQ count
        row = self.backend.fetchone(
            "SELECT COUNT(*) as count FROM webhook_dead_letter WHERE reprocessed_at IS NULL"
        )
        stats["dlq_pending_count"] = row["count"]

        # Average attempts for successful deliveries
        row = self.backend.fetchone(
            """
            SELECT AVG(attempt_count) as avg_attempts
            FROM webhook_deliveries
            WHERE status = 'success'
            """
        )
        stats["avg_attempts_success"] = row["avg_attempts"] or 0

        return stats

    def cleanup_old_deliveries(self, days: int = 30) -> int:
        """Remove delivery records older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of records deleted
        """
        cutoff = datetime.now() - timedelta(days=days)

        with self.backend.transaction():
            # Delete DLQ entries first (FK constraint)
            self.backend.execute(
                """
                DELETE FROM webhook_dead_letter
                WHERE delivery_id IN (
                    SELECT id FROM webhook_deliveries
                    WHERE created_at < ? AND status IN ('success', 'dead_letter')
                )
                """,
                (cutoff.isoformat(),),
            )

            self.backend.execute(
                """
                DELETE FROM webhook_deliveries
                WHERE created_at < ? AND status IN ('success', 'dead_letter')
                """,
                (cutoff.isoformat(),),
            )

        row = self.backend.fetchone("SELECT changes() as deleted")
        return row["deleted"]
