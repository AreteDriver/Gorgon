"""FastAPI backend for AI Workflow Orchestrator."""

import asyncio
import logging
import signal
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Header, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel

from test_ai.auth import create_access_token, verify_token
from test_ai.config import get_settings, configure_logging
from test_ai.orchestrator import WorkflowEngine, Workflow
from test_ai.prompts import PromptTemplateManager, PromptTemplate
from test_ai.api_clients import OpenAIClient
from test_ai.scheduler import (
    ScheduleManager,
    WorkflowSchedule,
)
from test_ai.webhooks import (
    WebhookManager,
    Webhook,
)
from test_ai.jobs import (
    JobManager,
    JobStatus,
)
from test_ai.state import (
    get_database,
    run_migrations,
    get_migration_status,
    SQLiteBackend,
    PostgresBackend,
)
from test_ai.utils.circuit_breaker import get_all_circuit_stats, reset_all_circuits

logger = logging.getLogger(__name__)

# Rate limiter - uses client IP for identification
limiter = Limiter(key_func=get_remote_address)

# Managers initialized in lifespan
schedule_manager: ScheduleManager | None = None
webhook_manager: WebhookManager | None = None
job_manager: JobManager | None = None

# Application state for health checks and graceful shutdown
_app_state = {
    "ready": False,
    "shutting_down": False,
    "start_time": None,
    "active_requests": 0,
}
_state_lock = asyncio.Lock()


async def _increment_active_requests():
    """Increment active request counter."""
    async with _state_lock:
        _app_state["active_requests"] += 1


async def _decrement_active_requests():
    """Decrement active request counter."""
    async with _state_lock:
        _app_state["active_requests"] -= 1


def _handle_shutdown_signal(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    _app_state["shutting_down"] = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage component lifecycles with graceful shutdown."""
    global schedule_manager, webhook_manager, job_manager

    # Reset application state at startup
    _app_state["ready"] = False
    _app_state["shutting_down"] = False
    _app_state["active_requests"] = 0
    _app_state["start_time"] = datetime.now()

    # Configure logging
    settings = get_settings()
    configure_logging(
        level=settings.log_level,
        format=settings.log_format,
        sanitize_logs=settings.sanitize_logs,
    )

    # Register signal handlers for graceful shutdown (only in main thread)
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, _handle_shutdown_signal)
        signal.signal(signal.SIGINT, _handle_shutdown_signal)

    # Get shared database backend
    backend = get_database()

    # Run migrations
    logger.info("Running database migrations...")
    try:
        applied = run_migrations(backend)
        if applied:
            logger.info(f"Applied migrations: {', '.join(applied)}")
        else:
            logger.info("Database schema is up to date")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

    # Initialize managers with shared backend
    schedule_manager = ScheduleManager(backend=backend)
    webhook_manager = WebhookManager(backend=backend)
    job_manager = JobManager(backend=backend)

    schedule_manager.start()

    # Mark application as ready
    _app_state["ready"] = True
    logger.info("Application startup complete - ready to serve requests")

    yield

    # Begin graceful shutdown
    logger.info("Beginning graceful shutdown...")
    _app_state["shutting_down"] = True
    _app_state["ready"] = False

    # Wait for active requests to complete (with timeout)
    shutdown_timeout = 30  # seconds
    start = time.monotonic()
    while _app_state["active_requests"] > 0:
        if time.monotonic() - start > shutdown_timeout:
            logger.warning(
                f"Shutdown timeout reached with {_app_state['active_requests']} "
                "active requests still running"
            )
            break
        await asyncio.sleep(0.1)

    # Shutdown managers
    schedule_manager.shutdown()
    job_manager.shutdown()

    # Reset circuit breakers
    reset_all_circuits()

    logger.info("Graceful shutdown complete")


app = FastAPI(title="AI Workflow Orchestrator", version="0.1.0", lifespan=lifespan)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API requests with timing and request IDs.

    Also tracks active requests for graceful shutdown and rejects new
    requests during shutdown.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Reject requests during shutdown (except health checks)
        path = request.url.path
        if _app_state["shutting_down"] and not path.startswith("/health"):
            return JSONResponse(
                status_code=503,
                content={"detail": "Service shutting down"},
                headers={"Retry-After": "30"},
            )

        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]

        # Get client info
        client_ip = request.client.host if request.client else "unknown"
        method = request.method

        # Track active requests for graceful shutdown
        await _increment_active_requests()

        # Log request start with structured fields
        start_time = time.perf_counter()
        logger.info(
            f"[{request_id}] {method} {path} - client={client_ip}",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "client_ip": client_ip,
            },
        )

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log error and re-raise
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"[{request_id}] {method} {path} - 500 ERROR in {duration_ms:.1f}ms - {e}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "client_ip": client_ip,
                    "status_code": 500,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            raise
        finally:
            await _decrement_active_requests()

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log response with structured fields
        status_code = response.status_code
        log_level = logging.WARNING if status_code >= 400 else logging.INFO
        logger.log(
            log_level,
            f"[{request_id}] {method} {path} - {status_code} in {duration_ms:.1f}ms",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "client_ip": client_ip,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )

        # Add request ID to response headers for tracing
        response.headers["X-Request-ID"] = request_id

        return response


# Register middleware
app.add_middleware(RequestLoggingMiddleware)

# Register rate limiter
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded",
            "retry_after": exc.detail,
        },
        headers={"Retry-After": str(exc.detail)},
    )


# Initialize components
workflow_engine = WorkflowEngine()
prompt_manager = PromptTemplateManager()
openai_client = OpenAIClient()

# API v1 router
v1_router = APIRouter(prefix="/v1", tags=["v1"])


class LoginRequest(BaseModel):
    """Login request."""

    user_id: str
    password: str


class LoginResponse(BaseModel):
    """Login response."""

    access_token: str
    token_type: str = "bearer"


class WorkflowExecuteRequest(BaseModel):
    """Request to execute a workflow."""

    workflow_id: str
    variables: Optional[Dict] = None


def verify_auth(authorization: Optional[str] = Header(None)) -> str:
    """Verify authentication token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.split(" ")[1]
    user_id = verify_token(token)

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user_id


@app.get("/")
def root():
    """Root endpoint."""
    return {"app": "AI Workflow Orchestrator", "version": "0.1.0", "status": "running"}


@v1_router.post("/auth/login", response_model=LoginResponse)
@limiter.limit("5/minute")
def login(request: Request, login_request: LoginRequest):
    """Login endpoint (simplified). Rate limited to 5 requests/minute per IP."""
    if login_request.password == "demo":
        token = create_access_token(login_request.user_id)
        return LoginResponse(access_token=token)

    raise HTTPException(status_code=401, detail="Invalid credentials")


@v1_router.get("/workflows")
def list_workflows(authorization: Optional[str] = Header(None)):
    """List all workflows."""
    verify_auth(authorization)
    return workflow_engine.list_workflows()


@v1_router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str, authorization: Optional[str] = Header(None)):
    """Get a specific workflow."""
    verify_auth(authorization)
    workflow = workflow_engine.load_workflow(workflow_id)

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return workflow


@v1_router.post("/workflows")
def create_workflow(workflow: Workflow, authorization: Optional[str] = Header(None)):
    """Create a new workflow."""
    verify_auth(authorization)

    if workflow_engine.save_workflow(workflow):
        return {"status": "success", "workflow_id": workflow.id}

    raise HTTPException(status_code=500, detail="Failed to save workflow")


@v1_router.post("/workflows/execute")
@limiter.limit("10/minute")
def execute_workflow(
    request_obj: Request,
    request: WorkflowExecuteRequest,
    authorization: Optional[str] = Header(None),
):
    """Execute a workflow. Rate limited to 10 executions/minute per IP."""
    verify_auth(authorization)

    workflow = workflow_engine.load_workflow(request.workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if request.variables:
        workflow.variables.update(request.variables)

    result = workflow_engine.execute_workflow(workflow)
    return result


@v1_router.get("/prompts")
def list_prompts(authorization: Optional[str] = Header(None)):
    """List all prompt templates."""
    verify_auth(authorization)
    return prompt_manager.list_templates()


@v1_router.get("/prompts/{template_id}")
def get_prompt(template_id: str, authorization: Optional[str] = Header(None)):
    """Get a specific prompt template."""
    verify_auth(authorization)
    template = prompt_manager.load_template(template_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return template


@v1_router.post("/prompts")
def create_prompt(
    template: PromptTemplate, authorization: Optional[str] = Header(None)
):
    """Create a new prompt template."""
    verify_auth(authorization)

    if prompt_manager.save_template(template):
        return {"status": "success", "template_id": template.id}

    raise HTTPException(status_code=500, detail="Failed to save template")


@v1_router.delete("/prompts/{template_id}")
def delete_prompt(template_id: str, authorization: Optional[str] = Header(None)):
    """Delete a prompt template."""
    verify_auth(authorization)

    if prompt_manager.delete_template(template_id):
        return {"status": "success"}

    raise HTTPException(status_code=404, detail="Template not found")


# Schedule endpoints
@v1_router.get("/schedules")
def list_schedules(authorization: Optional[str] = Header(None)):
    """List all schedules."""
    verify_auth(authorization)
    return schedule_manager.list_schedules()


@v1_router.get("/schedules/{schedule_id}")
def get_schedule(schedule_id: str, authorization: Optional[str] = Header(None)):
    """Get a specific schedule."""
    verify_auth(authorization)
    schedule = schedule_manager.get_schedule(schedule_id)

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return schedule


@v1_router.post("/schedules")
def create_schedule(
    schedule: WorkflowSchedule, authorization: Optional[str] = Header(None)
):
    """Create a new schedule."""
    verify_auth(authorization)

    try:
        if schedule_manager.create_schedule(schedule):
            return {"status": "success", "schedule_id": schedule.id}
        raise HTTPException(status_code=500, detail="Failed to save schedule")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@v1_router.put("/schedules/{schedule_id}")
def update_schedule(
    schedule_id: str,
    schedule: WorkflowSchedule,
    authorization: Optional[str] = Header(None),
):
    """Update an existing schedule."""
    verify_auth(authorization)

    if schedule.id != schedule_id:
        raise HTTPException(status_code=400, detail="Schedule ID mismatch")

    try:
        if schedule_manager.update_schedule(schedule):
            return {"status": "success", "schedule_id": schedule.id}
        raise HTTPException(status_code=500, detail="Failed to update schedule")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@v1_router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: str, authorization: Optional[str] = Header(None)):
    """Delete a schedule."""
    verify_auth(authorization)

    if schedule_manager.delete_schedule(schedule_id):
        return {"status": "success"}

    raise HTTPException(status_code=404, detail="Schedule not found")


@v1_router.post("/schedules/{schedule_id}/pause")
def pause_schedule(schedule_id: str, authorization: Optional[str] = Header(None)):
    """Pause a schedule."""
    verify_auth(authorization)

    if schedule_manager.pause_schedule(schedule_id):
        return {"status": "success", "message": "Schedule paused"}

    raise HTTPException(status_code=404, detail="Schedule not found")


@v1_router.post("/schedules/{schedule_id}/resume")
def resume_schedule(schedule_id: str, authorization: Optional[str] = Header(None)):
    """Resume a paused schedule."""
    verify_auth(authorization)

    if schedule_manager.resume_schedule(schedule_id):
        return {"status": "success", "message": "Schedule resumed"}

    raise HTTPException(status_code=404, detail="Schedule not found")


@v1_router.post("/schedules/{schedule_id}/trigger")
def trigger_schedule(schedule_id: str, authorization: Optional[str] = Header(None)):
    """Manually trigger a scheduled workflow immediately."""
    verify_auth(authorization)

    if schedule_manager.trigger_now(schedule_id):
        return {"status": "success", "message": "Workflow triggered"}

    raise HTTPException(status_code=404, detail="Schedule not found")


@v1_router.get("/schedules/{schedule_id}/history")
def get_schedule_history(
    schedule_id: str,
    limit: int = 10,
    authorization: Optional[str] = Header(None),
):
    """Get execution history for a schedule."""
    verify_auth(authorization)

    schedule = schedule_manager.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    history = schedule_manager.get_execution_history(schedule_id, limit)
    return [h.model_dump(mode="json") for h in history]


# Webhook endpoints (authenticated management)
@v1_router.get("/webhooks")
def list_webhooks(authorization: Optional[str] = Header(None)):
    """List all webhooks."""
    verify_auth(authorization)
    return webhook_manager.list_webhooks()


@v1_router.get("/webhooks/{webhook_id}")
def get_webhook(webhook_id: str, authorization: Optional[str] = Header(None)):
    """Get a specific webhook (includes secret)."""
    verify_auth(authorization)
    webhook = webhook_manager.get_webhook(webhook_id)

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return webhook


@v1_router.post("/webhooks")
def create_webhook(webhook: Webhook, authorization: Optional[str] = Header(None)):
    """Create a new webhook."""
    verify_auth(authorization)

    try:
        if webhook_manager.create_webhook(webhook):
            return {
                "status": "success",
                "webhook_id": webhook.id,
                "secret": webhook.secret,
                "trigger_url": f"/hooks/{webhook.id}",
            }
        raise HTTPException(status_code=500, detail="Failed to save webhook")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@v1_router.put("/webhooks/{webhook_id}")
def update_webhook(
    webhook_id: str,
    webhook: Webhook,
    authorization: Optional[str] = Header(None),
):
    """Update an existing webhook."""
    verify_auth(authorization)

    if webhook.id != webhook_id:
        raise HTTPException(status_code=400, detail="Webhook ID mismatch")

    try:
        if webhook_manager.update_webhook(webhook):
            return {"status": "success", "webhook_id": webhook.id}
        raise HTTPException(status_code=500, detail="Failed to update webhook")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@v1_router.delete("/webhooks/{webhook_id}")
def delete_webhook(webhook_id: str, authorization: Optional[str] = Header(None)):
    """Delete a webhook."""
    verify_auth(authorization)

    if webhook_manager.delete_webhook(webhook_id):
        return {"status": "success"}

    raise HTTPException(status_code=404, detail="Webhook not found")


@v1_router.post("/webhooks/{webhook_id}/regenerate-secret")
def regenerate_webhook_secret(
    webhook_id: str, authorization: Optional[str] = Header(None)
):
    """Regenerate the secret for a webhook."""
    verify_auth(authorization)

    try:
        new_secret = webhook_manager.regenerate_secret(webhook_id)
        return {"status": "success", "secret": new_secret}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@v1_router.get("/webhooks/{webhook_id}/history")
def get_webhook_history(
    webhook_id: str,
    limit: int = 10,
    authorization: Optional[str] = Header(None),
):
    """Get trigger history for a webhook."""
    verify_auth(authorization)

    webhook = webhook_manager.get_webhook(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    history = webhook_manager.get_trigger_history(webhook_id, limit)
    return [h.model_dump(mode="json") for h in history]


# Public webhook trigger endpoint (uses signature verification, not JWT)
@app.post("/hooks/{webhook_id}")
@limiter.limit("30/minute")
async def trigger_webhook(
    webhook_id: str,
    request: Request,
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
):
    """
    Public endpoint to trigger a webhook. Rate limited to 30 requests/minute per IP.

    Authentication is via HMAC-SHA256 signature in X-Webhook-Signature header.
    Generate signature: HMAC-SHA256(secret, request_body)
    Format: sha256=<hex_digest>
    """
    webhook = webhook_manager.get_webhook(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Get raw body for signature verification
    body = await request.body()

    # Verify signature if provided (recommended but optional for testing)
    if x_webhook_signature:
        if not webhook_manager.verify_signature(webhook_id, body, x_webhook_signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    try:
        payload = await request.json() if body else {}
    except Exception:
        payload = {}

    # Get client IP
    client_ip = request.client.host if request.client else None

    # Trigger the webhook
    try:
        result = webhook_manager.trigger(webhook_id, payload, source_ip=client_ip)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Job endpoints (async workflow execution)
@v1_router.post("/jobs")
@limiter.limit("20/minute")
def submit_job(
    request_obj: Request,
    request: WorkflowExecuteRequest,
    authorization: Optional[str] = Header(None),
):
    """Submit a workflow for async execution. Rate limited to 20 jobs/minute per IP."""
    verify_auth(authorization)

    try:
        job = job_manager.submit(request.workflow_id, request.variables)
        return {
            "status": "submitted",
            "job_id": job.id,
            "workflow_id": job.workflow_id,
            "poll_url": f"/jobs/{job.id}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@v1_router.get("/jobs")
def list_jobs(
    status: Optional[str] = None,
    workflow_id: Optional[str] = None,
    limit: int = 50,
    authorization: Optional[str] = Header(None),
):
    """List jobs with optional filtering."""
    verify_auth(authorization)

    status_filter = None
    if status:
        try:
            status_filter = JobStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    jobs = job_manager.list_jobs(
        status=status_filter, workflow_id=workflow_id, limit=limit
    )
    return [j.model_dump(mode="json") for j in jobs]


@v1_router.get("/jobs/stats")
def get_job_stats(authorization: Optional[str] = Header(None)):
    """Get job statistics."""
    verify_auth(authorization)
    return job_manager.get_stats()


@v1_router.get("/jobs/{job_id}")
def get_job(job_id: str, authorization: Optional[str] = Header(None)):
    """Get job status and result."""
    verify_auth(authorization)

    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job.model_dump(mode="json")


@v1_router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, authorization: Optional[str] = Header(None)):
    """Cancel a pending or running job."""
    verify_auth(authorization)

    if job_manager.cancel(job_id):
        return {"status": "success", "message": "Job cancelled"}

    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    raise HTTPException(
        status_code=400, detail=f"Cannot cancel job in {job.status.value} status"
    )


@v1_router.delete("/jobs/{job_id}")
def delete_job(job_id: str, authorization: Optional[str] = Header(None)):
    """Delete a completed/failed/cancelled job."""
    verify_auth(authorization)

    if job_manager.delete_job(job_id):
        return {"status": "success"}

    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    raise HTTPException(status_code=400, detail="Cannot delete running job")


@v1_router.post("/jobs/cleanup")
def cleanup_jobs(max_age_hours: int = 24, authorization: Optional[str] = Header(None)):
    """Remove old completed/failed/cancelled jobs."""
    verify_auth(authorization)
    deleted = job_manager.cleanup_old_jobs(max_age_hours)
    return {"status": "success", "deleted": deleted}


@app.get("/health")
def health_check():
    """Basic health check (liveness probe).

    Returns 200 if the application process is running.
    Use for Kubernetes liveness probes.
    """
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/health/live")
def liveness_check():
    """Liveness probe - is the process alive?

    Returns 200 as long as the process is running.
    Use for Kubernetes livenessProbe.
    """
    return {"status": "alive"}


@app.get("/health/ready")
def readiness_check():
    """Readiness probe - is the application ready to serve traffic?

    Returns 200 if the application is fully initialized and not shutting down.
    Returns 503 if the application is not ready or is shutting down.
    Use for Kubernetes readinessProbe.
    """
    if not _app_state["ready"]:
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "reason": "Application not initialized"},
        )

    if _app_state["shutting_down"]:
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "reason": "Application shutting down"},
        )

    return {"status": "ready"}


@app.get("/health/db")
def database_health_check():
    """Database health check endpoint.

    Checks database connectivity and migration status.
    Returns 503 if database is unreachable.
    """
    try:
        backend = get_database()

        # Test connectivity with a simple query
        backend.fetchone("SELECT 1 AS ping")

        # Determine backend type
        if isinstance(backend, PostgresBackend):
            backend_type = "postgresql"
        elif isinstance(backend, SQLiteBackend):
            backend_type = "sqlite"
        else:
            backend_type = "unknown"

        # Get migration status
        migration_status = get_migration_status(backend)

        return {
            "status": "healthy",
            "database": "connected",
            "backend": backend_type,
            "migrations": migration_status,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )


@app.get("/health/full")
def full_health_check():
    """Comprehensive health check with all subsystem statuses.

    Checks application state, database, and circuit breakers.
    Useful for detailed monitoring and debugging.
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": None,
        "application": {
            "ready": _app_state["ready"],
            "shutting_down": _app_state["shutting_down"],
            "active_requests": _app_state["active_requests"],
        },
        "database": None,
        "circuit_breakers": get_all_circuit_stats(),
    }

    # Calculate uptime
    if _app_state["start_time"]:
        uptime = datetime.now() - _app_state["start_time"]
        health["uptime_seconds"] = uptime.total_seconds()

    # Check database
    try:
        backend = get_database()
        backend.fetchone("SELECT 1 AS ping")

        if isinstance(backend, PostgresBackend):
            backend_type = "postgresql"
        elif isinstance(backend, SQLiteBackend):
            backend_type = "sqlite"
        else:
            backend_type = "unknown"

        health["database"] = {
            "status": "connected",
            "backend": backend_type,
        }
    except Exception as e:
        health["database"] = {
            "status": "disconnected",
            "error": str(e),
        }
        health["status"] = "degraded"

    # Check if any circuit breakers are open
    for name, stats in health["circuit_breakers"].items():
        if stats["state"] == "open":
            health["status"] = "degraded"
            break

    # Check if shutting down
    if _app_state["shutting_down"]:
        health["status"] = "shutting_down"

    return health


# Include versioned API router
app.include_router(v1_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
