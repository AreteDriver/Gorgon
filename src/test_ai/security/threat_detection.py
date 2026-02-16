"""Threat detection and suspicious activity monitoring.

Monitors request patterns and flags suspicious behavior including:
- Rapid sequential failed authentication attempts
- Unusual request patterns (path traversal, injection probes)
- Geographic or IP anomalies
- Abnormal traffic volumes
- Known malicious user-agent signatures

Events are logged to the ``gorgon.security`` logger for SIEM integration.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger("gorgon.security")


class ThreatSeverity(str, Enum):
    """Severity level for detected threats."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatCategory(str, Enum):
    """Category of detected threat."""

    AUTH_BRUTE_FORCE = "auth.brute_force"
    AUTH_CREDENTIAL_STUFFING = "auth.credential_stuffing"
    INJECTION_SQL = "injection.sql"
    INJECTION_XSS = "injection.xss"
    INJECTION_CMD = "injection.command"
    PATH_TRAVERSAL = "path.traversal"
    SUSPICIOUS_USER_AGENT = "suspicious.user_agent"
    RATE_ANOMALY = "rate.anomaly"
    SCANNER_DETECTED = "scanner.detected"
    ENUMERATION = "enumeration"


@dataclass
class ThreatEvent:
    """A detected threat event."""

    category: ThreatCategory
    severity: ThreatSeverity
    source_ip: str
    description: str
    path: str = ""
    user_agent: str = ""
    user_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """Serialize to dictionary for logging."""
        return {
            "event": "threat_detected",
            "category": self.category.value,
            "severity": self.severity.value,
            "source_ip": self.source_ip,
            "description": self.description,
            "path": self.path,
            "user_agent": self.user_agent[:200] if self.user_agent else "",
            "user_id": self.user_id,
            "metadata": self.metadata,
            "timestamp": datetime.fromtimestamp(
                self.timestamp, tz=timezone.utc
            ).isoformat(),
        }


# Patterns indicating injection attempts
_SQL_INJECTION_PATTERNS = [
    re.compile(
        r"(?i)(\b(union|select|insert|update|delete|drop|alter)\b.*\b(from|into|table|where)\b)"
    ),
    re.compile(r"(?i)(--|#|/\*|\*/|;).*\b(select|drop|delete|update)\b"),
    re.compile(r"(?i)(\bor\b|\band\b)\s+\d+\s*=\s*\d+"),
    re.compile(r"'(\s*or\s*'|--|;)"),
]

_XSS_PATTERNS = [
    re.compile(r"(?i)<\s*script"),
    re.compile(r"(?i)javascript\s*:"),
    re.compile(r"(?i)on(error|load|click|mouseover)\s*="),
    re.compile(r"(?i)<\s*iframe"),
    re.compile(r"(?i)<\s*object"),
]

_CMD_INJECTION_PATTERNS = [
    re.compile(r"[;&|`$]"),
    re.compile(r"\.\./\.\./"),
    re.compile(r"(?i)(;|\||&&)\s*(cat|ls|whoami|id|pwd|curl|wget|nc)\b"),
]

_PATH_TRAVERSAL_PATTERNS = [
    re.compile(r"\.\./"),
    re.compile(r"(?i)(etc/passwd|etc/shadow|proc/self|windows/system32)"),
    re.compile(r"%2e%2e[/\\]", re.IGNORECASE),
    re.compile(r"\.\.%2f", re.IGNORECASE),
]

# Known scanner/malicious user agents
_SUSPICIOUS_USER_AGENTS = [
    re.compile(r"(?i)(sqlmap|nikto|nmap|masscan|dirbuster|gobuster)"),
    re.compile(r"(?i)(havij|acunetix|netsparker|burpsuite)"),
    re.compile(r"^$"),  # Empty user agent
]

# Paths commonly probed by scanners
_SCANNER_PROBE_PATHS = {
    "/.env",
    "/wp-admin",
    "/wp-login.php",
    "/admin",
    "/phpmyadmin",
    "/.git/config",
    "/actuator",
    "/server-status",
    "/config.json",
    "/.aws/credentials",
}


@dataclass
class _IPTracker:
    """Per-IP tracking state."""

    auth_failures: int = 0
    auth_failure_window_start: float = 0.0
    request_count: int = 0
    request_window_start: float = 0.0
    distinct_users_attempted: set = field(default_factory=set)
    scanner_probes: int = 0


class ThreatDetector:
    """Detects suspicious patterns in incoming requests.

    Thread-safe detector that maintains per-IP state and emits
    structured threat events to the security logger.
    """

    def __init__(
        self,
        auth_failure_threshold: int = 10,
        auth_failure_window: float = 300.0,
        credential_stuffing_threshold: int = 5,
        rate_anomaly_threshold: int = 200,
        rate_anomaly_window: float = 60.0,
        scanner_probe_threshold: int = 3,
    ) -> None:
        """Initialize detector.

        Args:
            auth_failure_threshold: Auth failures from one IP before alerting.
            auth_failure_window: Window in seconds for auth failure counting.
            credential_stuffing_threshold: Distinct usernames from one IP before alerting.
            rate_anomaly_threshold: Requests per window before rate anomaly alert.
            rate_anomaly_window: Window in seconds for rate anomaly detection.
            scanner_probe_threshold: Scanner probe hits before alerting.
        """
        self.auth_failure_threshold = auth_failure_threshold
        self.auth_failure_window = auth_failure_window
        self.credential_stuffing_threshold = credential_stuffing_threshold
        self.rate_anomaly_threshold = rate_anomaly_threshold
        self.rate_anomaly_window = rate_anomaly_window
        self.scanner_probe_threshold = scanner_probe_threshold

        self._trackers: dict[str, _IPTracker] = defaultdict(_IPTracker)
        self._lock = threading.Lock()
        self._events: list[ThreatEvent] = []
        self._max_events = 10_000

    def analyze_request(
        self,
        source_ip: str,
        path: str,
        method: str,
        user_agent: str = "",
        query_string: str = "",
        body_snippet: str = "",
    ) -> list[ThreatEvent]:
        """Analyze an incoming request for threats.

        Args:
            source_ip: Client IP address.
            path: Request path.
            method: HTTP method.
            user_agent: User-Agent header value.
            query_string: URL query string.
            body_snippet: First portion of request body (for injection checks).

        Returns:
            List of detected threat events (empty if clean).
        """
        threats: list[ThreatEvent] = []

        # Check injection patterns in path + query + body
        check_text = f"{path} {query_string} {body_snippet}"

        for pattern in _SQL_INJECTION_PATTERNS:
            if pattern.search(check_text):
                threats.append(
                    ThreatEvent(
                        category=ThreatCategory.INJECTION_SQL,
                        severity=ThreatSeverity.HIGH,
                        source_ip=source_ip,
                        description="SQL injection pattern detected in request",
                        path=path,
                        user_agent=user_agent,
                    )
                )
                break

        for pattern in _XSS_PATTERNS:
            if pattern.search(check_text):
                threats.append(
                    ThreatEvent(
                        category=ThreatCategory.INJECTION_XSS,
                        severity=ThreatSeverity.MEDIUM,
                        source_ip=source_ip,
                        description="XSS pattern detected in request",
                        path=path,
                        user_agent=user_agent,
                    )
                )
                break

        for pattern in _CMD_INJECTION_PATTERNS:
            if pattern.search(query_string) or pattern.search(body_snippet):
                threats.append(
                    ThreatEvent(
                        category=ThreatCategory.INJECTION_CMD,
                        severity=ThreatSeverity.HIGH,
                        source_ip=source_ip,
                        description="Command injection pattern detected",
                        path=path,
                        user_agent=user_agent,
                    )
                )
                break

        # Path traversal
        for pattern in _PATH_TRAVERSAL_PATTERNS:
            if pattern.search(path) or pattern.search(query_string):
                threats.append(
                    ThreatEvent(
                        category=ThreatCategory.PATH_TRAVERSAL,
                        severity=ThreatSeverity.HIGH,
                        source_ip=source_ip,
                        description="Path traversal attempt detected",
                        path=path,
                        user_agent=user_agent,
                    )
                )
                break

        # Suspicious user agent
        for pattern in _SUSPICIOUS_USER_AGENTS:
            if pattern.search(user_agent):
                threats.append(
                    ThreatEvent(
                        category=ThreatCategory.SUSPICIOUS_USER_AGENT,
                        severity=ThreatSeverity.LOW,
                        source_ip=source_ip,
                        description=f"Suspicious user agent: {user_agent[:100]}",
                        path=path,
                        user_agent=user_agent,
                    )
                )
                break

        # Scanner probe detection
        if path.rstrip("/") in _SCANNER_PROBE_PATHS:
            with self._lock:
                tracker = self._trackers[source_ip]
                tracker.scanner_probes += 1
                if tracker.scanner_probes >= self.scanner_probe_threshold:
                    threats.append(
                        ThreatEvent(
                            category=ThreatCategory.SCANNER_DETECTED,
                            severity=ThreatSeverity.MEDIUM,
                            source_ip=source_ip,
                            description=f"Scanner detected: {tracker.scanner_probes} probe paths hit",
                            path=path,
                            user_agent=user_agent,
                            metadata={"probe_count": tracker.scanner_probes},
                        )
                    )

        # Rate anomaly tracking
        with self._lock:
            tracker = self._trackers[source_ip]
            now = time.time()

            if now - tracker.request_window_start > self.rate_anomaly_window:
                tracker.request_count = 0
                tracker.request_window_start = now

            tracker.request_count += 1

            if tracker.request_count >= self.rate_anomaly_threshold:
                threats.append(
                    ThreatEvent(
                        category=ThreatCategory.RATE_ANOMALY,
                        severity=ThreatSeverity.MEDIUM,
                        source_ip=source_ip,
                        description=(
                            f"Abnormal request rate: {tracker.request_count} "
                            f"requests in {self.rate_anomaly_window}s"
                        ),
                        path=path,
                        user_agent=user_agent,
                        metadata={"request_count": tracker.request_count},
                    )
                )

        # Log and store events
        for event in threats:
            self._emit(event)

        return threats

    def record_auth_failure(
        self,
        source_ip: str,
        username: str,
        path: str = "",
    ) -> list[ThreatEvent]:
        """Record a failed authentication attempt.

        Args:
            source_ip: Client IP address.
            username: Attempted username.
            path: Request path.

        Returns:
            List of threat events triggered (may include brute force or credential stuffing).
        """
        threats: list[ThreatEvent] = []

        with self._lock:
            tracker = self._trackers[source_ip]
            now = time.time()

            # Reset window if expired
            if now - tracker.auth_failure_window_start > self.auth_failure_window:
                tracker.auth_failures = 0
                tracker.auth_failure_window_start = now
                tracker.distinct_users_attempted.clear()

            tracker.auth_failures += 1
            tracker.distinct_users_attempted.add(username)

            # Brute force detection
            if tracker.auth_failures >= self.auth_failure_threshold:
                threats.append(
                    ThreatEvent(
                        category=ThreatCategory.AUTH_BRUTE_FORCE,
                        severity=ThreatSeverity.HIGH,
                        source_ip=source_ip,
                        description=(
                            f"Brute force detected: {tracker.auth_failures} "
                            f"failed attempts in {self.auth_failure_window}s"
                        ),
                        path=path,
                        user_id=username,
                        metadata={"failure_count": tracker.auth_failures},
                    )
                )

            # Credential stuffing detection (many distinct usernames)
            if (
                len(tracker.distinct_users_attempted)
                >= self.credential_stuffing_threshold
            ):
                threats.append(
                    ThreatEvent(
                        category=ThreatCategory.AUTH_CREDENTIAL_STUFFING,
                        severity=ThreatSeverity.CRITICAL,
                        source_ip=source_ip,
                        description=(
                            f"Credential stuffing suspected: {len(tracker.distinct_users_attempted)} "
                            f"distinct usernames attempted"
                        ),
                        path=path,
                        user_id=username,
                        metadata={
                            "distinct_users": len(tracker.distinct_users_attempted),
                        },
                    )
                )

        for event in threats:
            self._emit(event)

        return threats

    def record_auth_success(self, source_ip: str) -> None:
        """Record a successful authentication (resets failure counters).

        Args:
            source_ip: Client IP address.
        """
        with self._lock:
            tracker = self._trackers.get(source_ip)
            if tracker:
                tracker.auth_failures = 0
                tracker.distinct_users_attempted.clear()

    def get_recent_events(
        self,
        limit: int = 100,
        severity: Optional[ThreatSeverity] = None,
        category: Optional[ThreatCategory] = None,
    ) -> list[dict]:
        """Get recent threat events.

        Args:
            limit: Maximum events to return.
            severity: Filter by severity.
            category: Filter by category.

        Returns:
            List of serialized threat events, newest first.
        """
        with self._lock:
            events = list(reversed(self._events))

        if severity:
            events = [e for e in events if e.severity == severity]
        if category:
            events = [e for e in events if e.category == category]

        return [e.to_dict() for e in events[:limit]]

    def get_stats(self) -> dict:
        """Get threat detection statistics.

        Returns:
            Dictionary with event counts by category and severity.
        """
        with self._lock:
            by_category: dict[str, int] = defaultdict(int)
            by_severity: dict[str, int] = defaultdict(int)

            for event in self._events:
                by_category[event.category.value] += 1
                by_severity[event.severity.value] += 1

            return {
                "total_events": len(self._events),
                "tracked_ips": len(self._trackers),
                "by_category": dict(by_category),
                "by_severity": dict(by_severity),
            }

    def _emit(self, event: ThreatEvent) -> None:
        """Log and store a threat event."""
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events :]

        entry = json.dumps(event.to_dict())
        if event.severity in (ThreatSeverity.HIGH, ThreatSeverity.CRITICAL):
            logger.warning(entry)
        else:
            logger.info(entry)


# Global instance
_detector: ThreatDetector | None = None


def get_threat_detector() -> ThreatDetector:
    """Get or create the global threat detector."""
    global _detector
    if _detector is None:
        _detector = ThreatDetector()
    return _detector
