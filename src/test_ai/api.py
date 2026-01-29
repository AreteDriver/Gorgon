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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel

from test_ai.auth import create_access_token, verify_token
from test_ai.config import get_settings, configure_logging
from test_ai.orchestrator import Workflow
from test_ai.orchestrator.workflow_engine_adapter import WorkflowEngineAdapter
from test_ai.prompts import PromptTemplateManager, PromptTemplate
from test_ai.workflow import WorkflowVersionManager
from test_ai.workflow.loader import (
    load_workflow as load_yaml_workflow,
    list_workflows as list_yaml_workflows,
)
from test_ai.workflow.executor import WorkflowExecutor
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
from test_ai.errors import GorgonError
from test_ai.security import (
    RequestSizeLimitMiddleware,
    RequestLimitConfig,
    BruteForceMiddleware,
    BruteForceConfig,
    get_brute_force_protection,
    AuditLogMiddleware,
)
from test_ai.tracing.middleware import TracingMiddleware
from test_ai.api_clients.resilience import get_all_provider_stats
from test_ai.api_errors import (
    RateLimitErrorResponse,
    gorgon_exception_handler,
    APIException,
    api_exception_handler,
    responses,
    AUTH_RESPONSES,
    CRUD_RESPONSES,
    WORKFLOW_RESPONSES,
    not_found,
    unauthorized,
    bad_request,
    internal_error,
)

logger = logging.getLogger(__name__)

# Rate limiter - uses client IP for identification
limiter = Limiter(key_func=get_remote_address)

# Managers initialized in lifespan
schedule_manager: ScheduleManager | None = None
webhook_manager: WebhookManager | None = None
job_manager: JobManager | None = None
version_manager: WorkflowVersionManager | None = None
execution_manager = None  # type: ExecutionManager | None

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
    global \
        schedule_manager, \
        webhook_manager, \
        job_manager, \
        version_manager, \
        execution_manager

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
    version_manager = WorkflowVersionManager(backend=backend)

    # Import and initialize execution manager
    from test_ai.executions import ExecutionManager

    execution_manager = ExecutionManager(backend=backend)

    # Migrate existing workflows (one-time)
    try:
        workflows_dir = settings.workflows_dir
        migrated = version_manager.migrate_existing_workflows(workflows_dir)
        if migrated:
            logger.info(
                f"Migrated {len(migrated)} existing workflows to version control"
            )
    except Exception as e:
        logger.warning(f"Workflow migration skipped: {e}")

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

# CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


# Register middleware (order matters: last added runs first on request)
# 1. RequestLoggingMiddleware - request logging and shutdown handling
app.add_middleware(RequestLoggingMiddleware)

# 1b. AuditLogMiddleware - structured audit trail for compliance
app.add_middleware(AuditLogMiddleware)

# 2. TracingMiddleware - distributed tracing (conditionally enabled via settings)
_tracing_settings = get_settings()
if _tracing_settings.tracing_enabled:
    app.add_middleware(
        TracingMiddleware,
        service_name=_tracing_settings.tracing_service_name,
        exclude_paths=["/health", "/health/live", "/health/ready", "/metrics"],
    )

# 3. BruteForceMiddleware - rate limiting for auth endpoints
_settings = get_settings()
brute_force_config = BruteForceConfig(
    max_attempts_per_minute=_settings.brute_force_max_attempts_per_minute,
    max_attempts_per_hour=_settings.brute_force_max_attempts_per_hour,
    max_auth_attempts_per_minute=_settings.brute_force_max_auth_attempts_per_minute,
    max_auth_attempts_per_hour=_settings.brute_force_max_auth_attempts_per_hour,
    initial_block_seconds=_settings.brute_force_initial_block_seconds,
    max_block_seconds=_settings.brute_force_max_block_seconds,
    auth_paths=("/v1/auth/", "/auth/", "/login"),
)
app.add_middleware(
    BruteForceMiddleware, protection=get_brute_force_protection(brute_force_config)
)

# 4. RequestSizeLimitMiddleware - reject oversized requests early
request_limit_config = RequestLimitConfig(
    max_body_size=_settings.request_max_body_size,
    max_json_size=_settings.request_max_json_size,
    max_form_size=_settings.request_max_form_size,
    large_upload_paths=("/v1/workflows/upload",),  # Future: file upload endpoint
)
app.add_middleware(RequestSizeLimitMiddleware, config=request_limit_config)

# Register rate limiter
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded errors with structured response."""
    request_id = request.headers.get("X-Request-ID")
    response = RateLimitErrorResponse(
        error={
            "error_code": "RATE_LIMITED",
            "message": "Rate limit exceeded",
            "details": {"limit": str(exc.detail)},
            "request_id": request_id,
        },
        retry_after=int(exc.detail) if str(exc.detail).isdigit() else 60,
    )
    return JSONResponse(
        status_code=429,
        content=response.model_dump(),
        headers={"Retry-After": str(exc.detail)},
    )


# Register exception handlers for structured error responses
app.add_exception_handler(GorgonError, gorgon_exception_handler)
app.add_exception_handler(APIException, api_exception_handler)


# Initialize components
workflow_engine = WorkflowEngineAdapter()
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
        raise unauthorized(
            "Authentication required. Provide Bearer token in Authorization header."
        )

    token = authorization.split(" ")[1]
    user_id = verify_token(token)

    if not user_id:
        raise unauthorized("Invalid or expired token")

    return user_id


@app.get("/")
def root():
    """Root endpoint."""
    return {"app": "AI Workflow Orchestrator", "version": "0.1.0", "status": "running"}


@v1_router.post(
    "/auth/login",
    response_model=LoginResponse,
    responses=responses(401, 429),
)
@limiter.limit("5/minute")
def login(request: Request, login_request: LoginRequest):
    """Login endpoint. Rate limited to 5 requests/minute per IP.

    Authentication methods (in priority order):
    1. Configured credentials via API_CREDENTIALS env var
    2. Demo auth (password='demo') if ALLOW_DEMO_AUTH=true (default in dev)

    Configure credentials:
        API_CREDENTIALS='user1:sha256hash1,user2:sha256hash2'
        Generate hash: python -c "from hashlib import sha256; print(sha256(b'password').hexdigest())"
    """
    settings = get_settings()

    if settings.verify_credentials(login_request.user_id, login_request.password):
        token = create_access_token(login_request.user_id)
        logger.info("User '%s' logged in successfully", login_request.user_id)
        return LoginResponse(access_token=token)

    logger.warning(
        "Failed login attempt for user '%s' from IP %s",
        login_request.user_id,
        get_remote_address(request),
    )
    raise unauthorized("Invalid credentials")


@v1_router.get("/workflows", responses=AUTH_RESPONSES)
def list_workflows(authorization: Optional[str] = Header(None)):
    """List all workflows."""
    verify_auth(authorization)
    return workflow_engine.list_workflows()


@v1_router.get("/workflows/{workflow_id}", responses=CRUD_RESPONSES)
def get_workflow(workflow_id: str, authorization: Optional[str] = Header(None)):
    """Get a specific workflow."""
    verify_auth(authorization)
    workflow = workflow_engine.load_workflow(workflow_id)

    if not workflow:
        raise not_found("Workflow", workflow_id)

    return workflow


@v1_router.post("/workflows", responses=CRUD_RESPONSES)
def create_workflow(workflow: Workflow, authorization: Optional[str] = Header(None)):
    """Create a new workflow."""
    verify_auth(authorization)

    if workflow_engine.save_workflow(workflow):
        return {"status": "success", "workflow_id": workflow.id}

    raise internal_error("Failed to save workflow")


@v1_router.post("/workflows/execute", responses=WORKFLOW_RESPONSES)
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
        raise not_found("Workflow", request.workflow_id)

    if request.variables:
        workflow.variables.update(request.variables)

    result = workflow_engine.execute_workflow(workflow)
    return result


# =============================================================================
# YAML Workflow Endpoints (Decision Support, etc.)
# =============================================================================

# Initialize YAML workflow executor
yaml_workflow_executor = WorkflowExecutor()

# YAML workflows directory
YAML_WORKFLOWS_DIR = get_settings().base_dir / "workflows"


@v1_router.get("/yaml-workflows", responses=AUTH_RESPONSES)
def list_yaml_workflow_definitions(authorization: Optional[str] = Header(None)):
    """List all YAML workflow definitions."""
    verify_auth(authorization)
    try:
        workflows = list_yaml_workflows(str(YAML_WORKFLOWS_DIR))
        return {
            "workflows": [
                {
                    "id": w.get("name", "").lower().replace(" ", "-"),
                    "name": w.get("name"),
                    "description": w.get("description"),
                    "version": w.get("version"),
                    "path": w.get("path"),
                }
                for w in workflows
            ]
        }
    except Exception as e:
        logger.error(f"Failed to list YAML workflows: {e}")
        return {"workflows": []}


@v1_router.get("/yaml-workflows/{workflow_id}", responses=CRUD_RESPONSES)
def get_yaml_workflow_definition(
    workflow_id: str, authorization: Optional[str] = Header(None)
):
    """Get a specific YAML workflow definition."""
    verify_auth(authorization)

    # Try to find the workflow file
    yaml_file = YAML_WORKFLOWS_DIR / f"{workflow_id}.yaml"
    yml_file = YAML_WORKFLOWS_DIR / f"{workflow_id}.yml"

    workflow_path = (
        yaml_file if yaml_file.exists() else yml_file if yml_file.exists() else None
    )

    if not workflow_path:
        raise not_found("YAML Workflow", workflow_id)

    try:
        workflow = load_yaml_workflow(str(workflow_path), str(YAML_WORKFLOWS_DIR))
        return {
            "id": workflow_id,
            "name": workflow.name,
            "description": getattr(workflow, "description", ""),
            "version": getattr(workflow, "version", "1.0"),
            "inputs": getattr(workflow, "inputs", {}),
            "outputs": getattr(workflow, "outputs", []),
            "steps": [
                {
                    "id": step.id,
                    "type": step.type,
                    "params": step.params,
                }
                for step in workflow.steps
            ],
        }
    except Exception as e:
        logger.error(f"Failed to load YAML workflow {workflow_id}: {e}")
        logger.error("Failed to load workflow: %s", e)
        raise internal_error("Failed to load workflow")


class YAMLWorkflowExecuteRequest(BaseModel):
    """Request to execute a YAML workflow."""

    workflow_id: str
    inputs: Optional[Dict] = None


@v1_router.post("/yaml-workflows/execute", responses=WORKFLOW_RESPONSES)
@limiter.limit("10/minute")
def execute_yaml_workflow(
    request: Request,
    body: YAMLWorkflowExecuteRequest,
    authorization: Optional[str] = Header(None),
):
    """Execute a YAML workflow (e.g., decision-support).

    Rate limited to 10 executions/minute per IP.
    """
    verify_auth(authorization)

    # Find the workflow file
    yaml_file = YAML_WORKFLOWS_DIR / f"{body.workflow_id}.yaml"
    yml_file = YAML_WORKFLOWS_DIR / f"{body.workflow_id}.yml"

    workflow_path = (
        yaml_file if yaml_file.exists() else yml_file if yml_file.exists() else None
    )

    if not workflow_path:
        raise not_found("YAML Workflow", body.workflow_id)

    try:
        # Load the workflow
        workflow = load_yaml_workflow(str(workflow_path), str(YAML_WORKFLOWS_DIR))

        # Execute with provided inputs
        inputs = body.inputs or {}
        result = yaml_workflow_executor.execute(workflow, inputs=inputs)

        # Format response
        return {
            "id": str(uuid.uuid4()),
            "workflow_id": body.workflow_id,
            "workflow_name": workflow.name,
            "status": result.status,
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "completed_at": result.completed_at.isoformat()
            if result.completed_at
            else None,
            "total_duration_ms": result.total_duration_ms,
            "total_tokens": result.total_tokens,
            "outputs": result.outputs,
            "steps": [
                {
                    "step_id": step.step_id,
                    "status": step.status.value
                    if hasattr(step.status, "value")
                    else str(step.status),
                    "duration_ms": step.duration_ms,
                    "tokens_used": step.tokens_used,
                }
                for step in result.steps
            ],
            "error": result.error,
        }
    except Exception as e:
        logger.error(f"Failed to execute YAML workflow {body.workflow_id}: {e}")
        logger.error("Workflow execution failed: %s", e)
        raise internal_error("Workflow execution failed")


@v1_router.get("/prompts", responses=AUTH_RESPONSES)
def list_prompts(authorization: Optional[str] = Header(None)):
    """List all prompt templates."""
    verify_auth(authorization)
    return prompt_manager.list_templates()


@v1_router.get("/prompts/{template_id}", responses=CRUD_RESPONSES)
def get_prompt(template_id: str, authorization: Optional[str] = Header(None)):
    """Get a specific prompt template."""
    verify_auth(authorization)
    template = prompt_manager.load_template(template_id)

    if not template:
        raise not_found("Template", template_id)

    return template


@v1_router.post("/prompts", responses=CRUD_RESPONSES)
def create_prompt(
    template: PromptTemplate, authorization: Optional[str] = Header(None)
):
    """Create a new prompt template."""
    verify_auth(authorization)

    if prompt_manager.save_template(template):
        return {"status": "success", "template_id": template.id}

    raise internal_error("Failed to save template")


@v1_router.delete("/prompts/{template_id}", responses=CRUD_RESPONSES)
def delete_prompt(template_id: str, authorization: Optional[str] = Header(None)):
    """Delete a prompt template."""
    verify_auth(authorization)

    if prompt_manager.delete_template(template_id):
        return {"status": "success"}

    raise not_found("Template", template_id)


# Schedule endpoints
@v1_router.get("/schedules", responses=AUTH_RESPONSES)
def list_schedules(authorization: Optional[str] = Header(None)):
    """List all schedules."""
    verify_auth(authorization)
    return schedule_manager.list_schedules()


@v1_router.get("/schedules/{schedule_id}", responses=CRUD_RESPONSES)
def get_schedule(schedule_id: str, authorization: Optional[str] = Header(None)):
    """Get a specific schedule."""
    verify_auth(authorization)
    schedule = schedule_manager.get_schedule(schedule_id)

    if not schedule:
        raise not_found("Schedule", schedule_id)

    return schedule


@v1_router.post("/schedules", responses=CRUD_RESPONSES)
def create_schedule(
    schedule: WorkflowSchedule, authorization: Optional[str] = Header(None)
):
    """Create a new schedule."""
    verify_auth(authorization)

    try:
        if schedule_manager.create_schedule(schedule):
            return {"status": "success", "schedule_id": schedule.id}
        raise internal_error("Failed to save schedule")
    except ValueError as e:
        raise bad_request(str(e))


@v1_router.put("/schedules/{schedule_id}", responses=CRUD_RESPONSES)
def update_schedule(
    schedule_id: str,
    schedule: WorkflowSchedule,
    authorization: Optional[str] = Header(None),
):
    """Update an existing schedule."""
    verify_auth(authorization)

    if schedule.id != schedule_id:
        raise bad_request(
            "Schedule ID mismatch", {"expected": schedule_id, "got": schedule.id}
        )

    try:
        if schedule_manager.update_schedule(schedule):
            return {"status": "success", "schedule_id": schedule.id}
        raise internal_error("Failed to update schedule")
    except ValueError:
        raise not_found("Schedule", schedule_id)


@v1_router.delete("/schedules/{schedule_id}", responses=CRUD_RESPONSES)
def delete_schedule(schedule_id: str, authorization: Optional[str] = Header(None)):
    """Delete a schedule."""
    verify_auth(authorization)

    if schedule_manager.delete_schedule(schedule_id):
        return {"status": "success"}

    raise not_found("Schedule", schedule_id)


@v1_router.post("/schedules/{schedule_id}/pause", responses=CRUD_RESPONSES)
def pause_schedule(schedule_id: str, authorization: Optional[str] = Header(None)):
    """Pause a schedule."""
    verify_auth(authorization)

    if schedule_manager.pause_schedule(schedule_id):
        return {"status": "success", "message": "Schedule paused"}

    raise not_found("Schedule", schedule_id)


@v1_router.post("/schedules/{schedule_id}/resume", responses=CRUD_RESPONSES)
def resume_schedule(schedule_id: str, authorization: Optional[str] = Header(None)):
    """Resume a paused schedule."""
    verify_auth(authorization)

    if schedule_manager.resume_schedule(schedule_id):
        return {"status": "success", "message": "Schedule resumed"}

    raise not_found("Schedule", schedule_id)


@v1_router.post("/schedules/{schedule_id}/trigger", responses=CRUD_RESPONSES)
def trigger_schedule(schedule_id: str, authorization: Optional[str] = Header(None)):
    """Manually trigger a scheduled workflow immediately."""
    verify_auth(authorization)

    if schedule_manager.trigger_now(schedule_id):
        return {"status": "success", "message": "Workflow triggered"}

    raise not_found("Schedule", schedule_id)


@v1_router.get("/schedules/{schedule_id}/history", responses=CRUD_RESPONSES)
def get_schedule_history(
    schedule_id: str,
    limit: int = 10,
    authorization: Optional[str] = Header(None),
):
    """Get execution history for a schedule."""
    verify_auth(authorization)

    schedule = schedule_manager.get_schedule(schedule_id)
    if not schedule:
        raise not_found("Schedule", schedule_id)

    history = schedule_manager.get_execution_history(schedule_id, limit)
    return [h.model_dump(mode="json") for h in history]


# Webhook endpoints (authenticated management)
@v1_router.get("/webhooks", responses=AUTH_RESPONSES)
def list_webhooks(authorization: Optional[str] = Header(None)):
    """List all webhooks."""
    verify_auth(authorization)
    return webhook_manager.list_webhooks()


@v1_router.get("/webhooks/{webhook_id}", responses=CRUD_RESPONSES)
def get_webhook(webhook_id: str, authorization: Optional[str] = Header(None)):
    """Get a specific webhook (secret redacted)."""
    verify_auth(authorization)
    webhook = webhook_manager.get_webhook(webhook_id)

    if not webhook:
        raise not_found("Webhook", webhook_id)

    # Redact secret — only shown at creation time
    if hasattr(webhook, "model_dump"):
        result = webhook.model_dump()
    elif isinstance(webhook, dict):
        result = dict(webhook)
    else:
        result = vars(webhook)
    result["secret"] = "***REDACTED***"
    return result


@v1_router.post("/webhooks", responses=CRUD_RESPONSES)
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
        raise internal_error("Failed to save webhook")
    except ValueError as e:
        raise bad_request(str(e))


@v1_router.put("/webhooks/{webhook_id}", responses=CRUD_RESPONSES)
def update_webhook(
    webhook_id: str,
    webhook: Webhook,
    authorization: Optional[str] = Header(None),
):
    """Update an existing webhook."""
    verify_auth(authorization)

    if webhook.id != webhook_id:
        raise bad_request(
            "Webhook ID mismatch", {"expected": webhook_id, "got": webhook.id}
        )

    try:
        if webhook_manager.update_webhook(webhook):
            return {"status": "success", "webhook_id": webhook.id}
        raise internal_error("Failed to update webhook")
    except ValueError:
        raise not_found("Webhook", webhook_id)


@v1_router.delete("/webhooks/{webhook_id}", responses=CRUD_RESPONSES)
def delete_webhook(webhook_id: str, authorization: Optional[str] = Header(None)):
    """Delete a webhook."""
    verify_auth(authorization)

    if webhook_manager.delete_webhook(webhook_id):
        return {"status": "success"}

    raise not_found("Webhook", webhook_id)


@v1_router.post("/webhooks/{webhook_id}/regenerate-secret", responses=CRUD_RESPONSES)
def regenerate_webhook_secret(
    webhook_id: str, authorization: Optional[str] = Header(None)
):
    """Regenerate the secret for a webhook."""
    verify_auth(authorization)

    try:
        new_secret = webhook_manager.regenerate_secret(webhook_id)
        return {"status": "success", "secret": new_secret}
    except ValueError:
        raise not_found("Webhook", webhook_id)


@v1_router.get("/webhooks/{webhook_id}/history", responses=CRUD_RESPONSES)
def get_webhook_history(
    webhook_id: str,
    limit: int = 10,
    authorization: Optional[str] = Header(None),
):
    """Get trigger history for a webhook."""
    verify_auth(authorization)

    webhook = webhook_manager.get_webhook(webhook_id)
    if not webhook:
        raise not_found("Webhook", webhook_id)

    history = webhook_manager.get_trigger_history(webhook_id, limit)
    return [h.model_dump(mode="json") for h in history]


# Public webhook trigger endpoint (uses signature verification, not JWT)
@app.post("/hooks/{webhook_id}", responses=responses(400, 401, 404, 429))
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
        raise not_found("Webhook", webhook_id)

    # Get raw body for signature verification
    body = await request.body()

    # Verify HMAC signature (required)
    if not x_webhook_signature:
        raise unauthorized("Missing X-Webhook-Signature header")
    if not webhook_manager.verify_signature(webhook_id, body, x_webhook_signature):
        raise unauthorized("Invalid webhook signature")

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
        raise bad_request(str(e))


# Job endpoints (async workflow execution)
@v1_router.post("/jobs", responses=CRUD_RESPONSES)
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
        raise bad_request(str(e))


@v1_router.get("/jobs", responses=AUTH_RESPONSES)
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
            raise bad_request(
                f"Invalid status: {status}",
                {"valid_statuses": [s.value for s in JobStatus]},
            )

    jobs = job_manager.list_jobs(
        status=status_filter, workflow_id=workflow_id, limit=limit
    )
    return [j.model_dump(mode="json") for j in jobs]


@v1_router.get("/jobs/stats", responses=AUTH_RESPONSES)
def get_job_stats(authorization: Optional[str] = Header(None)):
    """Get job statistics."""
    verify_auth(authorization)
    return job_manager.get_stats()


@v1_router.get("/jobs/{job_id}", responses=CRUD_RESPONSES)
def get_job(job_id: str, authorization: Optional[str] = Header(None)):
    """Get job status and result."""
    verify_auth(authorization)

    job = job_manager.get_job(job_id)
    if not job:
        raise not_found("Job", job_id)

    return job.model_dump(mode="json")


@v1_router.post("/jobs/{job_id}/cancel", responses=CRUD_RESPONSES)
def cancel_job(job_id: str, authorization: Optional[str] = Header(None)):
    """Cancel a pending or running job."""
    verify_auth(authorization)

    if job_manager.cancel(job_id):
        return {"status": "success", "message": "Job cancelled"}

    job = job_manager.get_job(job_id)
    if not job:
        raise not_found("Job", job_id)

    raise bad_request(
        f"Cannot cancel job in {job.status.value} status",
        {"job_id": job_id, "current_status": job.status.value},
    )


@v1_router.delete("/jobs/{job_id}", responses=CRUD_RESPONSES)
def delete_job(job_id: str, authorization: Optional[str] = Header(None)):
    """Delete a completed/failed/cancelled job."""
    verify_auth(authorization)

    if job_manager.delete_job(job_id):
        return {"status": "success"}

    job = job_manager.get_job(job_id)
    if not job:
        raise not_found("Job", job_id)

    raise bad_request(
        "Cannot delete running job", {"job_id": job_id, "status": job.status.value}
    )


@v1_router.post("/jobs/cleanup")
def cleanup_jobs(max_age_hours: int = 24, authorization: Optional[str] = Header(None)):
    """Remove old completed/failed/cancelled jobs."""
    verify_auth(authorization)
    deleted = job_manager.cleanup_old_jobs(max_age_hours)
    return {"status": "success", "deleted": deleted}


# =============================================================================
# Execution Endpoints (ReactFlow Workflow Execution)
# =============================================================================


class ExecutionStartRequest(BaseModel):
    """Request to start a workflow execution."""

    variables: Optional[Dict] = None


@v1_router.get("/executions", responses=AUTH_RESPONSES)
def list_executions(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    workflow_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """List workflow executions with pagination."""
    verify_auth(authorization)

    from test_ai.executions import ExecutionStatus

    status_filter = None
    if status:
        try:
            status_filter = ExecutionStatus(status)
        except ValueError:
            raise bad_request(
                f"Invalid status: {status}",
                {"valid_statuses": [s.value for s in ExecutionStatus]},
            )

    result = execution_manager.list_executions(
        page=page,
        page_size=page_size,
        status=status_filter,
        workflow_id=workflow_id,
    )
    return {
        "data": [e.model_dump(mode="json") for e in result.data],
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
    }


@v1_router.get("/executions/{execution_id}", responses=CRUD_RESPONSES)
def get_execution(execution_id: str, authorization: Optional[str] = Header(None)):
    """Get a specific execution by ID."""
    verify_auth(authorization)

    execution = execution_manager.get_execution(execution_id)
    if not execution:
        raise not_found("Execution", execution_id)

    # Include logs and metrics
    execution.logs = execution_manager.get_logs(execution_id, limit=50)
    execution.metrics = execution_manager.get_metrics(execution_id)

    return execution.model_dump(mode="json")


@v1_router.get("/executions/{execution_id}/logs", responses=CRUD_RESPONSES)
def get_execution_logs(
    execution_id: str,
    limit: int = 100,
    level: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """Get logs for an execution."""
    verify_auth(authorization)

    from test_ai.executions import LogLevel

    execution = execution_manager.get_execution(execution_id)
    if not execution:
        raise not_found("Execution", execution_id)

    level_filter = None
    if level:
        try:
            level_filter = LogLevel(level)
        except ValueError:
            raise bad_request(
                f"Invalid level: {level}",
                {"valid_levels": [lvl.value for lvl in LogLevel]},
            )

    logs = execution_manager.get_logs(execution_id, limit=limit, level=level_filter)
    return [log.model_dump(mode="json") for log in logs]


@v1_router.post("/workflows/{workflow_id}/execute", responses=WORKFLOW_RESPONSES)
@limiter.limit("10/minute")
def start_workflow_execution(
    request: Request,
    workflow_id: str,
    body: ExecutionStartRequest,
    authorization: Optional[str] = Header(None),
):
    """Start a new workflow execution.

    Rate limited to 10 executions/minute per IP.
    """
    verify_auth(authorization)

    # Try to find the workflow (JSON or YAML)
    workflow = workflow_engine.load_workflow(workflow_id)
    workflow_name = workflow_id

    if workflow:
        workflow_name = getattr(workflow, "name", workflow_id)
    else:
        # Try YAML workflows
        yaml_file = YAML_WORKFLOWS_DIR / f"{workflow_id}.yaml"
        yml_file = YAML_WORKFLOWS_DIR / f"{workflow_id}.yml"
        workflow_path = (
            yaml_file if yaml_file.exists() else yml_file if yml_file.exists() else None
        )
        if workflow_path:
            try:
                yaml_workflow = load_yaml_workflow(
                    str(workflow_path), str(YAML_WORKFLOWS_DIR)
                )
                workflow_name = yaml_workflow.name
            except Exception:
                pass
        else:
            raise not_found("Workflow", workflow_id)

    # Create execution record
    execution = execution_manager.create_execution(
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        variables=body.variables,
    )

    # Start execution (mark as running)
    execution_manager.start_execution(execution.id)

    return {
        "execution_id": execution.id,
        "workflow_id": workflow_id,
        "workflow_name": workflow_name,
        "status": "running",
        "poll_url": f"/v1/executions/{execution.id}",
    }


@v1_router.post("/executions/{execution_id}/pause", responses=CRUD_RESPONSES)
def pause_execution(execution_id: str, authorization: Optional[str] = Header(None)):
    """Pause a running execution."""
    verify_auth(authorization)

    execution = execution_manager.get_execution(execution_id)
    if not execution:
        raise not_found("Execution", execution_id)

    from test_ai.executions import ExecutionStatus

    if execution.status != ExecutionStatus.RUNNING:
        raise bad_request(
            f"Cannot pause execution in {execution.status.value} status",
            {"execution_id": execution_id, "current_status": execution.status.value},
        )

    updated = execution_manager.pause_execution(execution_id)
    return {
        "status": "success",
        "execution_id": execution_id,
        "execution_status": updated.status.value if updated else "unknown",
    }


@v1_router.post("/executions/{execution_id}/resume", responses=CRUD_RESPONSES)
def resume_execution(execution_id: str, authorization: Optional[str] = Header(None)):
    """Resume a paused execution."""
    verify_auth(authorization)

    execution = execution_manager.get_execution(execution_id)
    if not execution:
        raise not_found("Execution", execution_id)

    from test_ai.executions import ExecutionStatus

    if execution.status != ExecutionStatus.PAUSED:
        raise bad_request(
            f"Cannot resume execution in {execution.status.value} status",
            {"execution_id": execution_id, "current_status": execution.status.value},
        )

    updated = execution_manager.resume_execution(execution_id)
    return {
        "status": "success",
        "execution_id": execution_id,
        "execution_status": updated.status.value if updated else "unknown",
    }


@v1_router.post("/executions/{execution_id}/cancel", responses=CRUD_RESPONSES)
def cancel_execution(execution_id: str, authorization: Optional[str] = Header(None)):
    """Cancel a running or paused execution."""
    verify_auth(authorization)

    execution = execution_manager.get_execution(execution_id)
    if not execution:
        raise not_found("Execution", execution_id)

    if execution_manager.cancel_execution(execution_id):
        return {"status": "success", "message": "Execution cancelled"}

    raise bad_request(
        f"Cannot cancel execution in {execution.status.value} status",
        {"execution_id": execution_id, "current_status": execution.status.value},
    )


@v1_router.delete("/executions/{execution_id}", responses=CRUD_RESPONSES)
def delete_execution(execution_id: str, authorization: Optional[str] = Header(None)):
    """Delete an execution (must be completed/failed/cancelled)."""
    verify_auth(authorization)

    execution = execution_manager.get_execution(execution_id)
    if not execution:
        raise not_found("Execution", execution_id)

    from test_ai.executions import ExecutionStatus

    if execution.status in (
        ExecutionStatus.PENDING,
        ExecutionStatus.RUNNING,
        ExecutionStatus.PAUSED,
    ):
        raise bad_request(
            f"Cannot delete execution in {execution.status.value} status",
            {"execution_id": execution_id, "current_status": execution.status.value},
        )

    if execution_manager.delete_execution(execution_id):
        return {"status": "success"}

    raise internal_error("Failed to delete execution")


@v1_router.post("/executions/cleanup")
def cleanup_executions(
    max_age_hours: int = 168, authorization: Optional[str] = Header(None)
):
    """Remove old completed/failed/cancelled executions (default 7 days)."""
    verify_auth(authorization)
    deleted = execution_manager.cleanup_old_executions(max_age_hours)
    return {"status": "success", "deleted": deleted}


# =============================================================================
# Workflow Version Endpoints
# =============================================================================


class WorkflowVersionRequest(BaseModel):
    """Request to save a workflow version."""

    content: str
    version: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    activate: bool = True


class VersionCompareRequest(BaseModel):
    """Request to compare two versions."""

    from_version: str
    to_version: str


@v1_router.get("/workflows/{workflow_name}/versions", responses=AUTH_RESPONSES)
def list_workflow_versions(
    workflow_name: str,
    limit: int = 50,
    offset: int = 0,
    authorization: Optional[str] = Header(None),
):
    """List all versions of a workflow."""
    verify_auth(authorization)
    versions = version_manager.list_versions(workflow_name, limit=limit, offset=offset)
    return [v.model_dump(mode="json") for v in versions]


@v1_router.get("/workflows/{workflow_name}/versions/compare", responses=CRUD_RESPONSES)
def compare_workflow_versions(
    workflow_name: str,
    from_version: str,
    to_version: str,
    authorization: Optional[str] = Header(None),
):
    """Compare two workflow versions."""
    verify_auth(authorization)

    try:
        diff = version_manager.compare_versions(workflow_name, from_version, to_version)
        return {
            "workflow_name": workflow_name,
            "from_version": diff.from_version,
            "to_version": diff.to_version,
            "has_changes": diff.has_changes,
            "added_lines": diff.added_lines,
            "removed_lines": diff.removed_lines,
            "changed_sections": diff.changed_sections,
            "unified_diff": diff.unified_diff,
        }
    except ValueError as e:
        raise bad_request(str(e))


@v1_router.get(
    "/workflows/{workflow_name}/versions/{version}", responses=CRUD_RESPONSES
)
def get_workflow_version(
    workflow_name: str,
    version: str,
    authorization: Optional[str] = Header(None),
):
    """Get a specific workflow version."""
    verify_auth(authorization)
    wv = version_manager.get_version(workflow_name, version)
    if not wv:
        raise not_found("Version", f"{workflow_name}@{version}")
    return wv.model_dump(mode="json")


@v1_router.post("/workflows/{workflow_name}/versions", responses=CRUD_RESPONSES)
def save_workflow_version(
    workflow_name: str,
    request: WorkflowVersionRequest,
    authorization: Optional[str] = Header(None),
):
    """Save a new workflow version."""
    verify_auth(authorization)

    try:
        wv = version_manager.save_version(
            workflow_name=workflow_name,
            content=request.content,
            version=request.version,
            description=request.description,
            author=request.author,
            activate=request.activate,
        )
        return {
            "status": "success",
            "workflow_name": wv.workflow_name,
            "version": wv.version,
            "is_active": wv.is_active,
        }
    except ValueError as e:
        raise bad_request(str(e))


@v1_router.post(
    "/workflows/{workflow_name}/versions/{version}/activate", responses=CRUD_RESPONSES
)
def activate_workflow_version(
    workflow_name: str,
    version: str,
    authorization: Optional[str] = Header(None),
):
    """Activate a specific workflow version."""
    verify_auth(authorization)

    try:
        version_manager.set_active(workflow_name, version)
        return {
            "status": "success",
            "workflow_name": workflow_name,
            "active_version": version,
        }
    except ValueError:
        raise not_found("Version", f"{workflow_name}@{version}")


@v1_router.post("/workflows/{workflow_name}/rollback", responses=CRUD_RESPONSES)
def rollback_workflow(
    workflow_name: str,
    authorization: Optional[str] = Header(None),
):
    """Rollback to the previous workflow version."""
    verify_auth(authorization)

    wv = version_manager.rollback(workflow_name)
    if not wv:
        raise bad_request(
            "No previous version to rollback to",
            {"workflow_name": workflow_name},
        )

    return {
        "status": "success",
        "workflow_name": workflow_name,
        "rolled_back_to": wv.version,
    }


@v1_router.delete(
    "/workflows/{workflow_name}/versions/{version}", responses=CRUD_RESPONSES
)
def delete_workflow_version(
    workflow_name: str,
    version: str,
    authorization: Optional[str] = Header(None),
):
    """Delete a workflow version (cannot delete active version)."""
    verify_auth(authorization)

    try:
        version_manager.delete_version(workflow_name, version)
        return {"status": "success"}
    except ValueError as e:
        raise bad_request(str(e))


@v1_router.get("/workflow-versions", responses=AUTH_RESPONSES)
def list_versioned_workflows(authorization: Optional[str] = Header(None)):
    """List all workflows with version information."""
    verify_auth(authorization)
    return version_manager.list_workflows()


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
        logger.error("Database health check failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "database": "disconnected",
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
        "api_clients": get_all_provider_stats(),
        "security": {
            "brute_force": get_brute_force_protection().get_stats(),
        },
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


# =============================================================================
# Metrics Endpoint
# =============================================================================


@app.get("/metrics", include_in_schema=False)
def metrics_endpoint():
    """Prometheus metrics endpoint.

    Exposes application metrics in Prometheus text format for scraping.
    Excludes from OpenAPI schema since it's infrastructure-only.

    Returns:
        Plain text response with Prometheus metrics
    """
    from test_ai.metrics import get_collector, PrometheusExporter

    collector = get_collector()
    exporter = PrometheusExporter(prefix="gorgon")

    # Export workflow metrics
    metrics_output = exporter.export(collector)

    # Add API-specific metrics
    lines = [metrics_output.rstrip()]

    # Application state metrics
    lines.append("# TYPE gorgon_app_ready gauge")
    lines.append(f"gorgon_app_ready {1 if _app_state['ready'] else 0}")

    lines.append("# TYPE gorgon_app_shutting_down gauge")
    lines.append(f"gorgon_app_shutting_down {1 if _app_state['shutting_down'] else 0}")

    lines.append("# TYPE gorgon_active_requests gauge")
    lines.append(f"gorgon_active_requests {_app_state['active_requests']}")

    # Uptime metric
    if _app_state["start_time"]:
        uptime = (datetime.now() - _app_state["start_time"]).total_seconds()
        lines.append("# TYPE gorgon_uptime_seconds counter")
        lines.append(f"gorgon_uptime_seconds {uptime:.2f}")

    # Circuit breaker metrics
    for name, stats in get_all_circuit_stats().items():
        safe_name = name.replace("-", "_").replace(".", "_")
        lines.append(f"# TYPE gorgon_circuit_breaker_{safe_name}_state gauge")
        state_value = {"closed": 0, "open": 1, "half_open": 2}.get(stats["state"], -1)
        lines.append(f"gorgon_circuit_breaker_{safe_name}_state {state_value}")

        lines.append(f"# TYPE gorgon_circuit_breaker_{safe_name}_failures gauge")
        lines.append(
            f"gorgon_circuit_breaker_{safe_name}_failures {stats['failure_count']}"
        )

    from starlette.responses import PlainTextResponse

    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain")


# Include versioned API router
app.include_router(v1_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
