"""Outbound Notification System for Workflow Events."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of workflow events."""

    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    BUDGET_WARNING = "budget_warning"
    BUDGET_EXCEEDED = "budget_exceeded"
    SCHEDULE_TRIGGERED = "schedule_triggered"


@dataclass
class NotificationEvent:
    """A notification event to send."""

    event_type: EventType
    workflow_name: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict = field(default_factory=dict)
    severity: str = "info"  # info, warning, error, success

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type.value,
            "workflow_name": self.workflow_name,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "severity": self.severity,
        }


class NotificationChannel(ABC):
    """Base class for notification channels."""

    @abstractmethod
    def send(self, event: NotificationEvent) -> bool:
        """Send a notification.

        Args:
            event: The notification event

        Returns:
            True if sent successfully
        """
        pass

    @abstractmethod
    def name(self) -> str:
        """Get channel name."""
        pass


class SlackChannel(NotificationChannel):
    """Send notifications to Slack via webhook."""

    def __init__(
        self,
        webhook_url: str,
        channel: str | None = None,
        username: str = "Gorgon",
        icon_emoji: str = ":robot_face:",
    ):
        """Initialize Slack channel.

        Args:
            webhook_url: Slack incoming webhook URL
            channel: Optional channel override
            username: Bot username
            icon_emoji: Bot icon emoji
        """
        self.webhook_url = webhook_url
        self.channel = channel
        self.username = username
        self.icon_emoji = icon_emoji

    def name(self) -> str:
        return "slack"

    def send(self, event: NotificationEvent) -> bool:
        """Send notification to Slack."""
        color = self._severity_to_color(event.severity)

        # Build Slack message
        payload = {
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            "attachments": [
                {
                    "color": color,
                    "title": f"{self._event_emoji(event.event_type)} {event.workflow_name}",
                    "text": event.message,
                    "fields": self._build_fields(event),
                    "footer": "Gorgon Workflow Engine",
                    "ts": int(event.timestamp.timestamp()),
                }
            ],
        }

        if self.channel:
            payload["channel"] = self.channel

        return self._post(payload)

    def _severity_to_color(self, severity: str) -> str:
        colors = {
            "info": "#3498db",
            "success": "#2ecc71",
            "warning": "#f39c12",
            "error": "#e74c3c",
        }
        return colors.get(severity, "#95a5a6")

    def _event_emoji(self, event_type: EventType) -> str:
        emojis = {
            EventType.WORKFLOW_STARTED: ":arrow_forward:",
            EventType.WORKFLOW_COMPLETED: ":white_check_mark:",
            EventType.WORKFLOW_FAILED: ":x:",
            EventType.STEP_COMPLETED: ":heavy_check_mark:",
            EventType.STEP_FAILED: ":warning:",
            EventType.BUDGET_WARNING: ":moneybag:",
            EventType.BUDGET_EXCEEDED: ":no_entry:",
            EventType.SCHEDULE_TRIGGERED: ":alarm_clock:",
        }
        return emojis.get(event_type, ":bell:")

    def _build_fields(self, event: NotificationEvent) -> list:
        fields = [
            {"title": "Event", "value": event.event_type.value, "short": True},
            {"title": "Severity", "value": event.severity.upper(), "short": True},
        ]

        # Add details as fields
        for key, value in event.details.items():
            if isinstance(value, (str, int, float, bool)):
                fields.append(
                    {
                        "title": key.replace("_", " ").title(),
                        "value": str(value),
                        "short": True,
                    }
                )

        return fields

    def _post(self, payload: dict) -> bool:
        try:
            data = json.dumps(payload).encode("utf-8")
            req = Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=10) as response:
                return response.status == 200
        except URLError as e:
            logger.error(f"Slack notification failed: {e}")
            return False


class DiscordChannel(NotificationChannel):
    """Send notifications to Discord via webhook."""

    def __init__(
        self,
        webhook_url: str,
        username: str = "Gorgon",
        avatar_url: str | None = None,
    ):
        """Initialize Discord channel.

        Args:
            webhook_url: Discord webhook URL
            username: Bot username
            avatar_url: Optional avatar URL
        """
        self.webhook_url = webhook_url
        self.username = username
        self.avatar_url = avatar_url

    def name(self) -> str:
        return "discord"

    def send(self, event: NotificationEvent) -> bool:
        """Send notification to Discord."""
        color = self._severity_to_color(event.severity)

        # Build Discord embed
        embed = {
            "title": f"{self._event_emoji(event.event_type)} {event.workflow_name}",
            "description": event.message,
            "color": color,
            "fields": self._build_fields(event),
            "footer": {"text": "Gorgon Workflow Engine"},
            "timestamp": event.timestamp.isoformat(),
        }

        payload = {
            "username": self.username,
            "embeds": [embed],
        }

        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url

        return self._post(payload)

    def _severity_to_color(self, severity: str) -> int:
        # Discord uses decimal colors
        colors = {
            "info": 3447003,  # Blue
            "success": 3066993,  # Green
            "warning": 15844367,  # Orange
            "error": 15158332,  # Red
        }
        return colors.get(severity, 9807270)  # Gray

    def _event_emoji(self, event_type: EventType) -> str:
        emojis = {
            EventType.WORKFLOW_STARTED: "▶️",
            EventType.WORKFLOW_COMPLETED: "✅",
            EventType.WORKFLOW_FAILED: "❌",
            EventType.STEP_COMPLETED: "☑️",
            EventType.STEP_FAILED: "⚠️",
            EventType.BUDGET_WARNING: "💰",
            EventType.BUDGET_EXCEEDED: "🚫",
            EventType.SCHEDULE_TRIGGERED: "⏰",
        }
        return emojis.get(event_type, "🔔")

    def _build_fields(self, event: NotificationEvent) -> list:
        fields = [
            {"name": "Event", "value": event.event_type.value, "inline": True},
            {"name": "Severity", "value": event.severity.upper(), "inline": True},
        ]

        for key, value in event.details.items():
            if isinstance(value, (str, int, float, bool)):
                fields.append(
                    {
                        "name": key.replace("_", " ").title(),
                        "value": str(value),
                        "inline": True,
                    }
                )

        return fields

    def _post(self, payload: dict) -> bool:
        try:
            data = json.dumps(payload).encode("utf-8")
            req = Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=10) as response:
                return response.status in (200, 204)
        except URLError as e:
            logger.error(f"Discord notification failed: {e}")
            return False


class WebhookChannel(NotificationChannel):
    """Send notifications to a generic webhook endpoint."""

    def __init__(
        self,
        url: str,
        headers: dict | None = None,
        method: str = "POST",
    ):
        """Initialize generic webhook channel.

        Args:
            url: Webhook URL
            headers: Optional custom headers
            method: HTTP method (default POST)
        """
        self.url = url
        self.headers = headers or {}
        self.method = method

    def name(self) -> str:
        return "webhook"

    def send(self, event: NotificationEvent) -> bool:
        """Send notification to webhook."""
        try:
            data = json.dumps(event.to_dict()).encode("utf-8")
            headers = {"Content-Type": "application/json", **self.headers}
            req = Request(self.url, data=data, headers=headers, method=self.method)
            with urlopen(req, timeout=10) as response:
                return 200 <= response.status < 300
        except URLError as e:
            logger.error(f"Webhook notification failed: {e}")
            return False


class EmailChannel(NotificationChannel):
    """Send notifications via SMTP email."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        username: str | None = None,
        password: str | None = None,
        from_addr: str = "gorgon@localhost",
        to_addrs: list[str] | None = None,
        use_tls: bool = True,
    ):
        """Initialize email channel.

        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port (default 587 for TLS)
            username: SMTP username (optional)
            password: SMTP password (optional)
            from_addr: From email address
            to_addrs: List of recipient email addresses
            use_tls: Whether to use TLS (default True)
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs or []
        self.use_tls = use_tls

    def name(self) -> str:
        return "email"

    def send(self, event: NotificationEvent) -> bool:
        """Send notification via email."""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        if not self.to_addrs:
            logger.warning("Email channel has no recipients configured")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = (
                f"[Gorgon] {self._event_emoji(event.event_type)} {event.workflow_name}"
            )
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)

            # Plain text version
            text_body = self._format_text(event)
            msg.attach(MIMEText(text_body, "plain"))

            # HTML version
            html_body = self._format_html(event)
            msg.attach(MIMEText(html_body, "html"))

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())

            return True
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            return False

    def _event_emoji(self, event_type: EventType) -> str:
        emojis = {
            EventType.WORKFLOW_STARTED: "▶️",
            EventType.WORKFLOW_COMPLETED: "✅",
            EventType.WORKFLOW_FAILED: "❌",
            EventType.STEP_COMPLETED: "☑️",
            EventType.STEP_FAILED: "⚠️",
            EventType.BUDGET_WARNING: "💰",
            EventType.BUDGET_EXCEEDED: "🚫",
            EventType.SCHEDULE_TRIGGERED: "⏰",
        }
        return emojis.get(event_type, "🔔")

    def _format_text(self, event: NotificationEvent) -> str:
        lines = [
            f"Workflow: {event.workflow_name}",
            f"Event: {event.event_type.value}",
            f"Message: {event.message}",
            f"Severity: {event.severity}",
            f"Time: {event.timestamp.isoformat()}",
            "",
            "Details:",
        ]
        for key, value in event.details.items():
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    def _format_html(self, event: NotificationEvent) -> str:
        severity_colors = {
            "info": "#3498db",
            "success": "#2ecc71",
            "warning": "#f39c12",
            "error": "#e74c3c",
        }
        color = severity_colors.get(event.severity, "#95a5a6")

        details_html = "".join(
            f"<tr><td><strong>{k}</strong></td><td>{v}</td></tr>"
            for k, v in event.details.items()
        )

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="border-left: 4px solid {color}; padding-left: 16px; margin: 16px 0;">
                <h2 style="margin: 0;">{event.workflow_name}</h2>
                <p style="color: #666; margin: 8px 0;">{event.message}</p>
                <table style="border-collapse: collapse; margin-top: 16px;">
                    <tr><td><strong>Event</strong></td><td>{event.event_type.value}</td></tr>
                    <tr><td><strong>Severity</strong></td><td style="color: {color};">{event.severity.upper()}</td></tr>
                    <tr><td><strong>Time</strong></td><td>{event.timestamp.isoformat()}</td></tr>
                    {details_html}
                </table>
            </div>
            <p style="color: #999; font-size: 12px;">Sent by Gorgon Workflow Engine</p>
        </body>
        </html>
        """


class TeamsChannel(NotificationChannel):
    """Send notifications to Microsoft Teams via webhook."""

    def __init__(self, webhook_url: str):
        """Initialize Teams channel.

        Args:
            webhook_url: Microsoft Teams incoming webhook URL
        """
        self.webhook_url = webhook_url

    def name(self) -> str:
        return "teams"

    def send(self, event: NotificationEvent) -> bool:
        """Send notification to Teams."""
        color = self._severity_to_color(event.severity)

        # Build Teams Adaptive Card
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": f"{event.workflow_name}: {event.message}",
            "sections": [
                {
                    "activityTitle": f"{self._event_emoji(event.event_type)} {event.workflow_name}",
                    "activitySubtitle": event.timestamp.strftime(
                        "%Y-%m-%d %H:%M:%S UTC"
                    ),
                    "text": event.message,
                    "facts": self._build_facts(event),
                }
            ],
        }

        return self._post(payload)

    def _severity_to_color(self, severity: str) -> str:
        colors = {
            "info": "0078D7",
            "success": "2DC72D",
            "warning": "FFA500",
            "error": "FF0000",
        }
        return colors.get(severity, "808080")

    def _event_emoji(self, event_type: EventType) -> str:
        emojis = {
            EventType.WORKFLOW_STARTED: "▶️",
            EventType.WORKFLOW_COMPLETED: "✅",
            EventType.WORKFLOW_FAILED: "❌",
            EventType.STEP_COMPLETED: "☑️",
            EventType.STEP_FAILED: "⚠️",
            EventType.BUDGET_WARNING: "💰",
            EventType.BUDGET_EXCEEDED: "🚫",
            EventType.SCHEDULE_TRIGGERED: "⏰",
        }
        return emojis.get(event_type, "🔔")

    def _build_facts(self, event: NotificationEvent) -> list:
        facts = [
            {"name": "Event", "value": event.event_type.value},
            {"name": "Severity", "value": event.severity.upper()},
        ]
        for key, value in event.details.items():
            if isinstance(value, (str, int, float, bool)):
                facts.append(
                    {"name": key.replace("_", " ").title(), "value": str(value)}
                )
        return facts

    def _post(self, payload: dict) -> bool:
        try:
            data = json.dumps(payload).encode("utf-8")
            req = Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=10) as response:
                return response.status == 200
        except URLError as e:
            logger.error(f"Teams notification failed: {e}")
            return False


class PagerDutyChannel(NotificationChannel):
    """Send notifications to PagerDuty via Events API v2."""

    def __init__(
        self,
        routing_key: str,
        source: str = "gorgon",
        component: str = "workflow-engine",
    ):
        """Initialize PagerDuty channel.

        Args:
            routing_key: PagerDuty Events API v2 integration key
            source: Source identifier for events
            component: Component name
        """
        self.routing_key = routing_key
        self.source = source
        self.component = component
        self.api_url = "https://events.pagerduty.com/v2/enqueue"

    def name(self) -> str:
        return "pagerduty"

    def send(self, event: NotificationEvent) -> bool:
        """Send notification to PagerDuty."""
        # Only send critical events to PagerDuty
        if event.severity not in ("error", "warning") and event.event_type not in (
            EventType.WORKFLOW_FAILED,
            EventType.BUDGET_EXCEEDED,
        ):
            logger.debug(
                f"Skipping PagerDuty for non-critical event: {event.event_type}"
            )
            return True

        severity = self._map_severity(event.severity)
        action = "trigger" if event.severity == "error" else "trigger"

        payload = {
            "routing_key": self.routing_key,
            "event_action": action,
            "dedup_key": f"{event.workflow_name}-{event.event_type.value}",
            "payload": {
                "summary": f"{event.workflow_name}: {event.message}",
                "source": self.source,
                "severity": severity,
                "timestamp": event.timestamp.isoformat(),
                "component": self.component,
                "custom_details": {
                    "workflow_name": event.workflow_name,
                    "event_type": event.event_type.value,
                    **event.details,
                },
            },
        }

        return self._post(payload)

    def _map_severity(self, severity: str) -> str:
        """Map internal severity to PagerDuty severity."""
        mapping = {
            "error": "critical",
            "warning": "warning",
            "info": "info",
            "success": "info",
        }
        return mapping.get(severity, "info")

    def _post(self, payload: dict) -> bool:
        try:
            data = json.dumps(payload).encode("utf-8")
            req = Request(
                self.api_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=10) as response:
                return response.status in (200, 202)
        except URLError as e:
            logger.error(f"PagerDuty notification failed: {e}")
            return False

    def resolve(self, workflow_name: str, event_type: EventType) -> bool:
        """Resolve a PagerDuty incident.

        Args:
            workflow_name: Name of the workflow
            event_type: Original event type that triggered the incident

        Returns:
            True if resolved successfully
        """
        payload = {
            "routing_key": self.routing_key,
            "event_action": "resolve",
            "dedup_key": f"{workflow_name}-{event_type.value}",
        }
        return self._post(payload)


class Notifier:
    """Central notification manager.

    Usage:
        notifier = Notifier()
        notifier.add_channel(SlackChannel(webhook_url="..."))
        notifier.add_channel(DiscordChannel(webhook_url="..."))

        # Send notification
        notifier.notify(NotificationEvent(
            event_type=EventType.WORKFLOW_COMPLETED,
            workflow_name="feature-build",
            message="Workflow completed successfully",
            severity="success",
            details={"tokens_used": 5000, "duration_ms": 12000}
        ))

        # Or use convenience methods
        notifier.workflow_completed("feature-build", tokens=5000)
        notifier.workflow_failed("feature-build", error="Step 3 failed")
    """

    def __init__(self):
        self._channels: list[NotificationChannel] = []
        self._event_filters: dict[EventType, bool] = {e: True for e in EventType}

    def add_channel(self, channel: NotificationChannel) -> None:
        """Add a notification channel."""
        self._channels.append(channel)
        logger.info(f"Added notification channel: {channel.name()}")

    def remove_channel(self, channel_name: str) -> bool:
        """Remove a channel by name."""
        for i, ch in enumerate(self._channels):
            if ch.name() == channel_name:
                self._channels.pop(i)
                return True
        return False

    def set_filter(self, event_type: EventType, enabled: bool) -> None:
        """Enable/disable notifications for an event type."""
        self._event_filters[event_type] = enabled

    def notify(self, event: NotificationEvent) -> dict[str, bool]:
        """Send notification to all channels.

        Args:
            event: The notification event

        Returns:
            Dict of channel_name -> success status
        """
        # Check filter
        if not self._event_filters.get(event.event_type, True):
            return {}

        results = {}
        for channel in self._channels:
            try:
                results[channel.name()] = channel.send(event)
            except Exception as e:
                logger.error(f"Channel {channel.name()} failed: {e}")
                results[channel.name()] = False

        return results

    # Convenience methods

    def workflow_started(self, workflow_name: str, **details) -> dict[str, bool]:
        """Notify that a workflow has started."""
        return self.notify(
            NotificationEvent(
                event_type=EventType.WORKFLOW_STARTED,
                workflow_name=workflow_name,
                message=f"Workflow '{workflow_name}' started",
                severity="info",
                details=details,
            )
        )

    def workflow_completed(
        self,
        workflow_name: str,
        tokens: int = 0,
        duration_ms: int = 0,
        **details,
    ) -> dict[str, bool]:
        """Notify that a workflow completed successfully."""
        details.update({"tokens_used": tokens, "duration_ms": duration_ms})
        return self.notify(
            NotificationEvent(
                event_type=EventType.WORKFLOW_COMPLETED,
                workflow_name=workflow_name,
                message=f"Workflow '{workflow_name}' completed successfully",
                severity="success",
                details=details,
            )
        )

    def workflow_failed(
        self,
        workflow_name: str,
        error: str,
        step: str | None = None,
        **details,
    ) -> dict[str, bool]:
        """Notify that a workflow failed."""
        if step:
            details["failed_step"] = step
        details["error"] = error
        return self.notify(
            NotificationEvent(
                event_type=EventType.WORKFLOW_FAILED,
                workflow_name=workflow_name,
                message=f"Workflow '{workflow_name}' failed: {error}",
                severity="error",
                details=details,
            )
        )

    def step_failed(
        self,
        workflow_name: str,
        step_name: str,
        error: str,
        **details,
    ) -> dict[str, bool]:
        """Notify that a step failed."""
        details.update({"step": step_name, "error": error})
        return self.notify(
            NotificationEvent(
                event_type=EventType.STEP_FAILED,
                workflow_name=workflow_name,
                message=f"Step '{step_name}' failed in '{workflow_name}': {error}",
                severity="warning",
                details=details,
            )
        )

    def budget_warning(
        self,
        workflow_name: str,
        used: int,
        budget: int,
        percent: float,
        **details,
    ) -> dict[str, bool]:
        """Notify that budget threshold was crossed."""
        details.update({"used": used, "budget": budget, "percent": f"{percent:.1f}%"})
        return self.notify(
            NotificationEvent(
                event_type=EventType.BUDGET_WARNING,
                workflow_name=workflow_name,
                message=f"Budget warning: {percent:.1f}% used ({used}/{budget} tokens)",
                severity="warning",
                details=details,
            )
        )

    def budget_exceeded(
        self,
        workflow_name: str,
        used: int,
        budget: int,
        **details,
    ) -> dict[str, bool]:
        """Notify that budget was exceeded."""
        details.update({"used": used, "budget": budget})
        return self.notify(
            NotificationEvent(
                event_type=EventType.BUDGET_EXCEEDED,
                workflow_name=workflow_name,
                message=f"Budget exceeded: {used}/{budget} tokens",
                severity="error",
                details=details,
            )
        )
