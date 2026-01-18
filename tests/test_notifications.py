"""Tests for the notifications module."""

import pytest
import sys
sys.path.insert(0, 'src')

from test_ai.notifications import (
    Notifier,
    NotificationEvent,
    NotificationChannel,
    EventType,
    SlackChannel,
    DiscordChannel,
    WebhookChannel,
)


class MockChannel(NotificationChannel):
    """Mock channel for testing."""

    def __init__(self, should_fail=False, channel_name="mock"):
        self.sent = []
        self.should_fail = should_fail
        self._name = channel_name

    def name(self):
        return self._name

    def send(self, event):
        if self.should_fail:
            return False
        self.sent.append(event)
        return True


class TestNotificationEvent:
    """Tests for NotificationEvent class."""

    def test_create_event(self):
        """Can create notification event."""
        event = NotificationEvent(
            event_type=EventType.WORKFLOW_COMPLETED,
            workflow_name="test-workflow",
            message="Workflow completed",
            severity="success",
            details={"tokens": 100},
        )
        assert event.event_type == EventType.WORKFLOW_COMPLETED
        assert event.workflow_name == "test-workflow"
        assert event.severity == "success"

    def test_to_dict(self):
        """Event can be converted to dict."""
        event = NotificationEvent(
            event_type=EventType.WORKFLOW_FAILED,
            workflow_name="test",
            message="Failed",
        )
        data = event.to_dict()
        assert data["event_type"] == "workflow_failed"
        assert data["workflow_name"] == "test"
        assert "timestamp" in data


class TestEventType:
    """Tests for EventType enum."""

    def test_all_event_types(self):
        """All expected event types exist."""
        assert EventType.WORKFLOW_STARTED.value == "workflow_started"
        assert EventType.WORKFLOW_COMPLETED.value == "workflow_completed"
        assert EventType.WORKFLOW_FAILED.value == "workflow_failed"
        assert EventType.STEP_COMPLETED.value == "step_completed"
        assert EventType.STEP_FAILED.value == "step_failed"
        assert EventType.BUDGET_WARNING.value == "budget_warning"
        assert EventType.BUDGET_EXCEEDED.value == "budget_exceeded"


class TestNotifier:
    """Tests for Notifier class."""

    def test_add_channel(self):
        """Can add notification channel."""
        notifier = Notifier()
        channel = MockChannel()
        notifier.add_channel(channel)
        assert len(notifier._channels) == 1

    def test_remove_channel(self):
        """Can remove channel by name."""
        notifier = Notifier()
        notifier.add_channel(MockChannel())
        result = notifier.remove_channel("mock")
        assert result is True
        assert len(notifier._channels) == 0

    def test_notify_sends_to_all_channels(self):
        """Notification is sent to all channels."""
        notifier = Notifier()
        channel1 = MockChannel()
        channel2 = MockChannel()
        notifier.add_channel(channel1)
        notifier.add_channel(channel2)

        event = NotificationEvent(
            event_type=EventType.WORKFLOW_COMPLETED,
            workflow_name="test",
            message="Done",
        )
        results = notifier.notify(event)

        assert len(channel1.sent) == 1
        assert len(channel2.sent) == 1
        assert results["mock"] is True

    def test_notify_returns_results(self):
        """Notify returns success status per channel."""
        notifier = Notifier()
        notifier.add_channel(MockChannel(should_fail=True, channel_name="failing"))
        notifier.add_channel(MockChannel(should_fail=False, channel_name="succeeding"))

        event = NotificationEvent(
            event_type=EventType.WORKFLOW_STARTED,
            workflow_name="test",
            message="Started",
        )
        results = notifier.notify(event)

        # One succeeded, one failed
        assert results["failing"] is False
        assert results["succeeding"] is True

    def test_event_filtering(self):
        """Event filtering works."""
        notifier = Notifier()
        channel = MockChannel()
        notifier.add_channel(channel)

        # Disable step_failed events
        notifier.set_filter(EventType.STEP_FAILED, False)

        # This should be filtered
        notifier.notify(NotificationEvent(
            event_type=EventType.STEP_FAILED,
            workflow_name="test",
            message="Step failed",
        ))

        # This should go through
        notifier.notify(NotificationEvent(
            event_type=EventType.WORKFLOW_COMPLETED,
            workflow_name="test",
            message="Done",
        ))

        assert len(channel.sent) == 1
        assert channel.sent[0].event_type == EventType.WORKFLOW_COMPLETED


class TestNotifierConvenienceMethods:
    """Tests for Notifier convenience methods."""

    def test_workflow_started(self):
        """workflow_started sends correct event."""
        notifier = Notifier()
        channel = MockChannel()
        notifier.add_channel(channel)

        notifier.workflow_started("my-workflow", input_count=5)

        assert len(channel.sent) == 1
        event = channel.sent[0]
        assert event.event_type == EventType.WORKFLOW_STARTED
        assert event.workflow_name == "my-workflow"
        assert event.details["input_count"] == 5

    def test_workflow_completed(self):
        """workflow_completed sends correct event."""
        notifier = Notifier()
        channel = MockChannel()
        notifier.add_channel(channel)

        notifier.workflow_completed("my-workflow", tokens=1000, duration_ms=5000)

        event = channel.sent[0]
        assert event.event_type == EventType.WORKFLOW_COMPLETED
        assert event.severity == "success"
        assert event.details["tokens_used"] == 1000

    def test_workflow_failed(self):
        """workflow_failed sends correct event."""
        notifier = Notifier()
        channel = MockChannel()
        notifier.add_channel(channel)

        notifier.workflow_failed("my-workflow", error="Something broke", step="build")

        event = channel.sent[0]
        assert event.event_type == EventType.WORKFLOW_FAILED
        assert event.severity == "error"
        assert event.details["error"] == "Something broke"
        assert event.details["failed_step"] == "build"

    def test_step_failed(self):
        """step_failed sends correct event."""
        notifier = Notifier()
        channel = MockChannel()
        notifier.add_channel(channel)

        notifier.step_failed("my-workflow", "build", "Compilation error")

        event = channel.sent[0]
        assert event.event_type == EventType.STEP_FAILED
        assert event.details["step"] == "build"

    def test_budget_warning(self):
        """budget_warning sends correct event."""
        notifier = Notifier()
        channel = MockChannel()
        notifier.add_channel(channel)

        notifier.budget_warning("my-workflow", used=8000, budget=10000, percent=80.0)

        event = channel.sent[0]
        assert event.event_type == EventType.BUDGET_WARNING
        assert event.severity == "warning"
        assert "80.0%" in event.details["percent"]

    def test_budget_exceeded(self):
        """budget_exceeded sends correct event."""
        notifier = Notifier()
        channel = MockChannel()
        notifier.add_channel(channel)

        notifier.budget_exceeded("my-workflow", used=11000, budget=10000)

        event = channel.sent[0]
        assert event.event_type == EventType.BUDGET_EXCEEDED
        assert event.severity == "error"


class TestSlackChannel:
    """Tests for SlackChannel class."""

    def test_channel_name(self):
        """Channel name is 'slack'."""
        channel = SlackChannel(webhook_url="https://hooks.slack.com/xxx")
        assert channel.name() == "slack"

    def test_severity_colors(self):
        """Severity maps to colors."""
        channel = SlackChannel(webhook_url="https://example.com")
        assert channel._severity_to_color("success") == "#2ecc71"
        assert channel._severity_to_color("error") == "#e74c3c"
        assert channel._severity_to_color("warning") == "#f39c12"
        assert channel._severity_to_color("info") == "#3498db"

    def test_event_emojis(self):
        """Events map to emojis."""
        channel = SlackChannel(webhook_url="https://example.com")
        assert ":white_check_mark:" in channel._event_emoji(EventType.WORKFLOW_COMPLETED)
        assert ":x:" in channel._event_emoji(EventType.WORKFLOW_FAILED)


class TestDiscordChannel:
    """Tests for DiscordChannel class."""

    def test_channel_name(self):
        """Channel name is 'discord'."""
        channel = DiscordChannel(webhook_url="https://discord.com/api/webhooks/xxx")
        assert channel.name() == "discord"

    def test_severity_colors(self):
        """Severity maps to decimal colors."""
        channel = DiscordChannel(webhook_url="https://example.com")
        # Discord uses decimal colors
        assert isinstance(channel._severity_to_color("success"), int)
        assert channel._severity_to_color("success") == 3066993  # Green


class TestWebhookChannel:
    """Tests for WebhookChannel class."""

    def test_channel_name(self):
        """Channel name is 'webhook'."""
        channel = WebhookChannel(url="https://example.com/webhook")
        assert channel.name() == "webhook"

    def test_custom_headers(self):
        """Can set custom headers."""
        channel = WebhookChannel(
            url="https://example.com",
            headers={"Authorization": "Bearer token"},
        )
        assert channel.headers["Authorization"] == "Bearer token"
