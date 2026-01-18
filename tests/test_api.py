"""Tests for FastAPI endpoints."""

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, "src")

from test_ai.state.backends import SQLiteBackend


@pytest.fixture
def backend():
    """Create a temporary SQLite backend."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        backend = SQLiteBackend(db_path=db_path)
        yield backend
        backend.close()


@pytest.fixture
def client(backend):
    """Create a test client with mocked managers."""
    with patch("test_ai.api.get_database", return_value=backend):
        with patch("test_ai.api.run_migrations", return_value=[]):
            with patch(
                "test_ai.scheduler.schedule_manager.WorkflowEngine"
            ) as mock_sched_engine:
                with patch(
                    "test_ai.webhooks.webhook_manager.WorkflowEngine"
                ) as mock_webhook_engine:
                    with patch(
                        "test_ai.jobs.job_manager.WorkflowEngine"
                    ) as mock_job_engine:
                        # Mock workflow engine for all managers
                        mock_workflow = MagicMock()
                        mock_workflow.variables = {}
                        mock_sched_engine.return_value.load_workflow.return_value = (
                            mock_workflow
                        )
                        mock_webhook_engine.return_value.load_workflow.return_value = (
                            mock_workflow
                        )
                        mock_job_engine.return_value.load_workflow.return_value = (
                            mock_workflow
                        )

                        # Mock execute_workflow result - must have string status
                        mock_result = MagicMock()
                        mock_result.status = "completed"  # String, not MagicMock
                        mock_result.errors = []
                        mock_result.model_dump.return_value = {"status": "completed"}

                        # Apply to all engines
                        mock_sched_engine.return_value.execute_workflow.return_value = (
                            mock_result
                        )
                        mock_webhook_engine.return_value.execute_workflow.return_value = mock_result
                        mock_job_engine.return_value.execute_workflow.return_value = (
                            mock_result
                        )

                        from test_ai.api import app, limiter

                        # Disable rate limiting for tests
                        limiter.enabled = False

                        with TestClient(app) as test_client:
                            yield test_client

                        # Re-enable rate limiting after tests
                        limiter.enabled = True


@pytest.fixture
def auth_headers(client):
    """Get authentication headers."""
    response = client.post("/auth/login", json={"user_id": "test", "password": "demo"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestHealthEndpoint:
    """Tests for health endpoint."""

    def test_health_check(self, client):
        """GET /health returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_database_health_check(self, client):
        """GET /health/db returns database health status."""
        response = client.get("/health/db")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["backend"] == "sqlite"
        assert "migrations" in data
        assert "timestamp" in data

    def test_database_health_check_migrations_info(self, client):
        """GET /health/db returns migration status details."""
        response = client.get("/health/db")
        assert response.status_code == 200
        data = response.json()
        migrations = data["migrations"]
        assert "applied" in migrations
        assert "pending" in migrations
        assert "up_to_date" in migrations

    def test_request_id_header(self, client):
        """All responses include X-Request-ID header."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        # Request ID should be 8 characters (UUID prefix)
        assert len(response.headers["X-Request-ID"]) == 8


class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root(self, client):
        """GET / returns app info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["app"] == "AI Workflow Orchestrator"
        assert data["status"] == "running"


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    def test_login_success(self, client):
        """POST /auth/login with valid credentials returns token."""
        response = client.post(
            "/auth/login", json={"user_id": "test", "password": "demo"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_failure(self, client):
        """POST /auth/login with invalid credentials returns 401."""
        response = client.post(
            "/auth/login", json={"user_id": "test", "password": "wrong"}
        )
        assert response.status_code == 401

    def test_protected_endpoint_without_auth(self, client):
        """Protected endpoint without auth returns 401."""
        response = client.get("/jobs")
        assert response.status_code == 401

    def test_protected_endpoint_with_auth(self, client, auth_headers):
        """Protected endpoint with valid auth succeeds."""
        response = client.get("/jobs", headers=auth_headers)
        assert response.status_code == 200


class TestJobEndpoints:
    """Tests for job endpoints."""

    def test_list_jobs_empty(self, client, auth_headers):
        """GET /jobs returns empty list initially."""
        response = client.get("/jobs", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_submit_job(self, client, auth_headers):
        """POST /jobs submits a job."""
        response = client.post(
            "/jobs",
            json={"workflow_id": "test-workflow", "variables": {"key": "value"}},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "submitted"
        assert "job_id" in data
        assert data["workflow_id"] == "test-workflow"
        assert "poll_url" in data

    def test_get_job(self, client, auth_headers):
        """GET /jobs/{id} returns job details."""
        # Submit a job first
        submit_response = client.post(
            "/jobs",
            json={"workflow_id": "test-workflow"},
            headers=auth_headers,
        )
        job_id = submit_response.json()["job_id"]

        # Get job
        response = client.get(f"/jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id
        assert data["workflow_id"] == "test-workflow"

    def test_get_job_not_found(self, client, auth_headers):
        """GET /jobs/{id} returns 404 for nonexistent job."""
        response = client.get("/jobs/nonexistent", headers=auth_headers)
        assert response.status_code == 404

    def test_get_job_stats(self, client, auth_headers):
        """GET /jobs/stats returns statistics."""
        response = client.get("/jobs/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "pending" in data
        assert "completed" in data

    def test_cancel_job(self, client, auth_headers):
        """POST /jobs/{id}/cancel cancels a pending job."""
        # Submit a job
        submit_response = client.post(
            "/jobs",
            json={"workflow_id": "test-workflow"},
            headers=auth_headers,
        )
        job_id = submit_response.json()["job_id"]

        # Cancel it (may fail if already completed)
        response = client.post(f"/jobs/{job_id}/cancel", headers=auth_headers)
        # Either success or already completed
        assert response.status_code in (200, 400)

    def test_list_jobs_with_filter(self, client, auth_headers):
        """GET /jobs with status filter works."""
        response = client.get("/jobs?status=completed", headers=auth_headers)
        assert response.status_code == 200

    def test_list_jobs_invalid_status(self, client, auth_headers):
        """GET /jobs with invalid status returns 400."""
        response = client.get("/jobs?status=invalid", headers=auth_headers)
        assert response.status_code == 400


class TestScheduleEndpoints:
    """Tests for schedule endpoints."""

    def test_list_schedules_empty(self, client, auth_headers):
        """GET /schedules returns empty list initially."""
        response = client.get("/schedules", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_schedule(self, client, auth_headers):
        """POST /schedules creates a schedule."""
        response = client.post(
            "/schedules",
            json={
                "id": "test-schedule",
                "workflow_id": "test-workflow",
                "name": "Test Schedule",
                "schedule_type": "interval",
                "interval_config": {"minutes": 30},
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["schedule_id"] == "test-schedule"

    def test_get_schedule(self, client, auth_headers):
        """GET /schedules/{id} returns schedule details."""
        # Create schedule first
        client.post(
            "/schedules",
            json={
                "id": "get-test",
                "workflow_id": "test-workflow",
                "name": "Get Test",
                "schedule_type": "interval",
                "interval_config": {"minutes": 15},
            },
            headers=auth_headers,
        )

        response = client.get("/schedules/get-test", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "get-test"
        assert data["name"] == "Get Test"

    def test_get_schedule_not_found(self, client, auth_headers):
        """GET /schedules/{id} returns 404 for nonexistent schedule."""
        response = client.get("/schedules/nonexistent", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_schedule(self, client, auth_headers):
        """DELETE /schedules/{id} deletes a schedule."""
        # Create schedule
        client.post(
            "/schedules",
            json={
                "id": "delete-me",
                "workflow_id": "test-workflow",
                "name": "Delete Me",
                "schedule_type": "interval",
                "interval_config": {"minutes": 5},
            },
            headers=auth_headers,
        )

        # Delete it
        response = client.delete("/schedules/delete-me", headers=auth_headers)
        assert response.status_code == 200

        # Verify deleted
        response = client.get("/schedules/delete-me", headers=auth_headers)
        assert response.status_code == 404

    def test_pause_resume_schedule(self, client, auth_headers):
        """POST /schedules/{id}/pause and resume work."""
        # Create schedule
        client.post(
            "/schedules",
            json={
                "id": "pause-test",
                "workflow_id": "test-workflow",
                "name": "Pause Test",
                "schedule_type": "interval",
                "interval_config": {"minutes": 10},
            },
            headers=auth_headers,
        )

        # Pause
        response = client.post("/schedules/pause-test/pause", headers=auth_headers)
        assert response.status_code == 200

        # Resume
        response = client.post("/schedules/pause-test/resume", headers=auth_headers)
        assert response.status_code == 200


class TestWebhookEndpoints:
    """Tests for webhook endpoints."""

    def test_list_webhooks_empty(self, client, auth_headers):
        """GET /webhooks returns empty list initially."""
        response = client.get("/webhooks", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_webhook(self, client, auth_headers):
        """POST /webhooks creates a webhook."""
        response = client.post(
            "/webhooks",
            json={
                "id": "test-webhook",
                "name": "Test Webhook",
                "workflow_id": "test-workflow",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["webhook_id"] == "test-webhook"
        assert "secret" in data
        assert "trigger_url" in data

    def test_get_webhook(self, client, auth_headers):
        """GET /webhooks/{id} returns webhook details."""
        # Create webhook first
        client.post(
            "/webhooks",
            json={
                "id": "get-test",
                "name": "Get Test",
                "workflow_id": "test-workflow",
            },
            headers=auth_headers,
        )

        response = client.get("/webhooks/get-test", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "get-test"
        assert data["name"] == "Get Test"
        assert "secret" in data

    def test_get_webhook_not_found(self, client, auth_headers):
        """GET /webhooks/{id} returns 404 for nonexistent webhook."""
        response = client.get("/webhooks/nonexistent", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_webhook(self, client, auth_headers):
        """DELETE /webhooks/{id} deletes a webhook."""
        # Create webhook
        client.post(
            "/webhooks",
            json={
                "id": "delete-me",
                "name": "Delete Me",
                "workflow_id": "test-workflow",
            },
            headers=auth_headers,
        )

        # Delete it
        response = client.delete("/webhooks/delete-me", headers=auth_headers)
        assert response.status_code == 200

        # Verify deleted
        response = client.get("/webhooks/delete-me", headers=auth_headers)
        assert response.status_code == 404

    def test_regenerate_secret(self, client, auth_headers):
        """POST /webhooks/{id}/regenerate-secret generates new secret."""
        # Create webhook
        create_response = client.post(
            "/webhooks",
            json={
                "id": "regen-test",
                "name": "Regen Test",
                "workflow_id": "test-workflow",
            },
            headers=auth_headers,
        )
        original_secret = create_response.json()["secret"]

        # Regenerate secret
        response = client.post(
            "/webhooks/regen-test/regenerate-secret", headers=auth_headers
        )
        assert response.status_code == 200
        new_secret = response.json()["secret"]
        assert new_secret != original_secret

    def test_trigger_webhook_public(self, client, auth_headers):
        """POST /hooks/{id} triggers webhook without auth."""
        # Create webhook first (requires auth)
        client.post(
            "/webhooks",
            json={
                "id": "trigger-test",
                "name": "Trigger Test",
                "workflow_id": "test-workflow",
            },
            headers=auth_headers,
        )

        # Trigger it (no auth required)
        response = client.post(
            "/hooks/trigger-test",
            json={"data": {"id": 123}},
        )
        assert response.status_code == 200

    def test_trigger_webhook_not_found(self, client):
        """POST /hooks/{id} returns 404 for nonexistent webhook."""
        response = client.post("/hooks/nonexistent", json={})
        assert response.status_code == 404


class TestRateLimiting:
    """Tests for rate limiting."""

    @pytest.fixture
    def rate_limited_client(self, backend):
        """Create a test client with rate limiting enabled."""
        from unittest.mock import patch, MagicMock

        with patch("test_ai.api.get_database", return_value=backend):
            with patch("test_ai.api.run_migrations", return_value=[]):
                with patch(
                    "test_ai.scheduler.schedule_manager.WorkflowEngine"
                ) as mock_sched_engine:
                    with patch(
                        "test_ai.webhooks.webhook_manager.WorkflowEngine"
                    ) as mock_webhook_engine:
                        with patch(
                            "test_ai.jobs.job_manager.WorkflowEngine"
                        ) as mock_job_engine:
                            mock_workflow = MagicMock()
                            mock_workflow.variables = {}
                            mock_sched_engine.return_value.load_workflow.return_value = (
                                mock_workflow
                            )
                            mock_webhook_engine.return_value.load_workflow.return_value = (
                                mock_workflow
                            )
                            mock_job_engine.return_value.load_workflow.return_value = (
                                mock_workflow
                            )

                            from test_ai.api import app, limiter

                            # Enable rate limiting for this test
                            limiter.enabled = True
                            # Reset limiter storage
                            limiter.reset()

                            from fastapi.testclient import TestClient

                            with TestClient(app) as test_client:
                                yield test_client

                            limiter.enabled = False

    def test_login_rate_limit(self, rate_limited_client):
        """Login endpoint enforces rate limit after 5 requests."""
        # Make 5 successful requests
        for _ in range(5):
            response = rate_limited_client.post(
                "/auth/login", json={"user_id": "test", "password": "demo"}
            )
            assert response.status_code == 200

        # 6th request should be rate limited
        response = rate_limited_client.post(
            "/auth/login", json={"user_id": "test", "password": "demo"}
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers
