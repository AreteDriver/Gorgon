"""Tests for threat detection and suspicious activity monitoring."""

import sys

import pytest

sys.path.insert(0, "src")

from test_ai.security.threat_detection import (
    ThreatCategory,
    ThreatDetector,
    ThreatSeverity,
)


class TestThreatDetector:
    """Tests for ThreatDetector."""

    @pytest.fixture
    def detector(self):
        return ThreatDetector(
            auth_failure_threshold=3,
            credential_stuffing_threshold=3,
            rate_anomaly_threshold=10,
            rate_anomaly_window=60.0,
            scanner_probe_threshold=2,
        )

    def test_clean_request(self, detector):
        """Normal requests generate no threats."""
        threats = detector.analyze_request(
            source_ip="192.168.1.1",
            path="/v1/workflows",
            method="GET",
            user_agent="Mozilla/5.0",
        )
        assert len(threats) == 0

    def test_sql_injection_detection(self, detector):
        """Detects SQL injection patterns."""
        threats = detector.analyze_request(
            source_ip="10.0.0.1",
            path="/v1/workflows",
            method="GET",
            query_string="id=1 UNION SELECT * FROM users",
        )
        assert any(t.category == ThreatCategory.INJECTION_SQL for t in threats)

    def test_xss_detection(self, detector):
        """Detects XSS patterns."""
        threats = detector.analyze_request(
            source_ip="10.0.0.1",
            path="/v1/workflows",
            method="POST",
            body_snippet='<script>alert("xss")</script>',
        )
        assert any(t.category == ThreatCategory.INJECTION_XSS for t in threats)

    def test_path_traversal_detection(self, detector):
        """Detects path traversal attempts."""
        threats = detector.analyze_request(
            source_ip="10.0.0.1",
            path="/v1/../../etc/passwd",
            method="GET",
        )
        assert any(t.category == ThreatCategory.PATH_TRAVERSAL for t in threats)

    def test_suspicious_user_agent(self, detector):
        """Detects suspicious user agents."""
        threats = detector.analyze_request(
            source_ip="10.0.0.1",
            path="/v1/workflows",
            method="GET",
            user_agent="sqlmap/1.5",
        )
        assert any(t.category == ThreatCategory.SUSPICIOUS_USER_AGENT for t in threats)

    def test_scanner_detection(self, detector):
        """Detects automated scanners probing common paths."""
        detector.analyze_request(
            source_ip="10.0.0.1",
            path="/.env",
            method="GET",
        )
        threats = detector.analyze_request(
            source_ip="10.0.0.1",
            path="/.git/config",
            method="GET",
        )
        assert any(t.category == ThreatCategory.SCANNER_DETECTED for t in threats)

    def test_rate_anomaly(self, detector):
        """Detects abnormal request rates."""
        threats_found = False
        for _ in range(15):
            threats = detector.analyze_request(
                source_ip="10.0.0.1",
                path="/v1/workflows",
                method="GET",
                user_agent="Mozilla/5.0",
            )
            if any(t.category == ThreatCategory.RATE_ANOMALY for t in threats):
                threats_found = True
                break

        assert threats_found

    def test_brute_force_detection(self, detector):
        """Detects brute force auth attempts."""
        threats_found = False
        for i in range(5):
            threats = detector.record_auth_failure(
                source_ip="10.0.0.1",
                username="admin",
                path="/auth/login",
            )
            if any(t.category == ThreatCategory.AUTH_BRUTE_FORCE for t in threats):
                threats_found = True
                break

        assert threats_found

    def test_credential_stuffing_detection(self, detector):
        """Detects credential stuffing (many distinct usernames)."""
        threats_found = False
        for i in range(5):
            threats = detector.record_auth_failure(
                source_ip="10.0.0.2",
                username=f"user{i}@example.com",
                path="/auth/login",
            )
            if any(
                t.category == ThreatCategory.AUTH_CREDENTIAL_STUFFING for t in threats
            ):
                threats_found = True
                break

        assert threats_found

    def test_auth_success_resets_counters(self, detector):
        """Successful auth resets failure counters."""
        detector.record_auth_failure("10.0.0.1", "admin")
        detector.record_auth_failure("10.0.0.1", "admin")
        detector.record_auth_success("10.0.0.1")

        # Should not trigger brute force after reset
        threats = detector.record_auth_failure("10.0.0.1", "admin")
        assert not any(t.category == ThreatCategory.AUTH_BRUTE_FORCE for t in threats)

    def test_get_recent_events(self, detector):
        """Recent events are retrievable."""
        detector.analyze_request(
            source_ip="10.0.0.1",
            path="/v1/../../etc/passwd",
            method="GET",
            user_agent="Mozilla/5.0",
        )
        events = detector.get_recent_events()
        assert len(events) > 0
        categories = {e["category"] for e in events}
        assert ThreatCategory.PATH_TRAVERSAL.value in categories

    def test_get_recent_events_filter_severity(self, detector):
        """Events can be filtered by severity."""
        detector.analyze_request(
            source_ip="10.0.0.1",
            path="/v1/../../etc/passwd",
            method="GET",
        )
        events = detector.get_recent_events(severity=ThreatSeverity.HIGH)
        for event in events:
            assert event["severity"] == "high"

    def test_get_stats(self, detector):
        """Stats are computed correctly."""
        detector.analyze_request(
            source_ip="10.0.0.1",
            path="/v1/../../etc/passwd",
            method="GET",
        )
        stats = detector.get_stats()
        assert stats["total_events"] > 0
        assert stats["tracked_ips"] > 0
        assert "by_category" in stats
        assert "by_severity" in stats

    def test_different_ips_tracked_separately(self, detector):
        """Different IPs have separate tracking."""
        detector.record_auth_failure("10.0.0.1", "admin")
        detector.record_auth_failure("10.0.0.1", "admin")

        # Different IP should not be affected
        threats = detector.record_auth_failure("10.0.0.2", "admin")
        assert not any(t.category == ThreatCategory.AUTH_BRUTE_FORCE for t in threats)

    def test_event_serialization(self, detector):
        """Threat events serialize correctly."""
        detector.analyze_request(
            source_ip="10.0.0.1",
            path="/v1/../../etc/passwd",
            method="GET",
            user_agent="test-agent",
        )
        events = detector.get_recent_events(limit=1)
        event = events[0]
        assert "timestamp" in event
        assert "source_ip" in event
        assert "category" in event
        assert "severity" in event
        assert "description" in event
