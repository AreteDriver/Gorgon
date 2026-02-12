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

from fastapi import (
    APIRouter,
    FastAPI,
    HTTPException,
    Header,
    Query,
    Request,
    Response,
    WebSocket,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel, Field

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
from test_ai.mcp import MCPConnectorManager
from test_ai.mcp.models import (
    MCPServerCreateInput,
    MCPServerUpdateInput,
    CredentialCreateInput,
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
from test_ai.contracts.base import AgentRole
from test_ai.contracts.definitions import _CONTRACT_REGISTRY

logger = logging.getLogger(__name__)

# Rate limiter - uses client IP for identification
limiter = Limiter(key_func=get_remote_address)

# Managers initialized in lifespan
schedule_manager: ScheduleManager | None = None
webhook_manager: WebhookManager | None = None
job_manager: JobManager | None = None
version_manager: WorkflowVersionManager | None = None
execution_manager = None  # type: ExecutionManager | None
mcp_manager: MCPConnectorManager | None = None
settings_manager = None  # type: "SettingsManager | None"
budget_manager = None  # type: "PersistentBudgetManager | None"

# WebSocket components initialized in lifespan
ws_manager = None  # type: "ConnectionManager | None"
ws_broadcaster = None  # type: "Broadcaster | None"

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
        execution_manager, \
        mcp_manager, \
        settings_manager, \
        budget_manager, \
        ws_manager, \
        ws_broadcaster

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
    _app_state["backend"] = backend  # Store for supervisor factory

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
    mcp_manager = MCPConnectorManager(backend=backend)

    # Import and initialize execution manager
    from test_ai.executions import ExecutionManager

    execution_manager = ExecutionManager(backend=backend)

    # Initialize settings manager
    from test_ai.settings import SettingsManager

    settings_manager = SettingsManager(backend=backend)

    # Initialize budget manager
    from test_ai.budget import PersistentBudgetManager

    budget_manager = PersistentBudgetManager(backend=backend)

    # Initialize WebSocket components
    from test_ai.websocket import ConnectionManager, Broadcaster

    ws_manager = ConnectionManager()
    ws_broadcaster = Broadcaster(ws_manager)

    # Start broadcaster with current event loop
    loop = asyncio.get_running_loop()
    ws_broadcaster.start(loop)

    # Register broadcaster callback with execution manager
    execution_manager.register_callback(ws_broadcaster.create_execution_callback())

    logger.info("WebSocket components initialized")

    # Initialize chat module
    from test_ai.chat import router as chat_router
    from test_ai.chat.router import init_chat_module
    from test_ai.agents import SupervisorAgent, create_agent_provider

    def create_supervisor(mode=None, session=None, backend=None):
        """Factory function to create Supervisor agent.

        Args:
            mode: Chat mode (assistant or self_improve).
            session: Chat session for filesystem access context.
            backend: Database backend for proposal storage.
        """
        try:
            provider = create_agent_provider("anthropic")
            return SupervisorAgent(
                provider,
                mode=mode,
                session=session,
                backend=backend or _app_state.get("backend"),
            )
        except Exception as e:
            logger.warning(f"Could not create supervisor: {e}")
            return None

    init_chat_module(backend, supervisor_factory=create_supervisor)
    app.include_router(chat_router)
    logger.info("Chat module initialized")

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

    # Shutdown WebSocket broadcaster
    if ws_broadcaster:
        await ws_broadcaster.stop()

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

    user_id: str = Field(..., max_length=128, pattern=r"^[\w@.\-]+$")
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

    Configure credentials (bcrypt preferred):
        API_CREDENTIALS='user1:$2b$12$...,user2:$2b$12$...'
        Generate hash: python -c "import bcrypt; print(bcrypt.hashpw(b'password', bcrypt.gensalt()).decode())"
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
        logger.error("Failed to load YAML workflow %s: %s", workflow_id, e)
        raise internal_error("Failed to load workflow")


class YAMLWorkflowExecuteRequest(BaseModel):
    """Request to execute a YAML workflow."""

    workflow_id: str = Field(..., pattern=r"^[\w\-]+$")
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
        logger.error("Failed to execute YAML workflow %s: %s", body.workflow_id, e)
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


# =============================================================================
# MCP Connector Endpoints
# =============================================================================


@v1_router.get("/mcp/servers", responses=AUTH_RESPONSES)
def list_mcp_servers(authorization: Optional[str] = Header(None)):
    """List all registered MCP servers."""
    verify_auth(authorization)
    servers = mcp_manager.list_servers()
    return [s.model_dump(mode="json") for s in servers]


@v1_router.get("/mcp/servers/{server_id}", responses=CRUD_RESPONSES)
def get_mcp_server(server_id: str, authorization: Optional[str] = Header(None)):
    """Get a specific MCP server by ID."""
    verify_auth(authorization)
    server = mcp_manager.get_server(server_id)
    if not server:
        raise not_found("MCP Server", server_id)
    return server.model_dump(mode="json")


@v1_router.post("/mcp/servers", responses=CRUD_RESPONSES)
def create_mcp_server(
    data: MCPServerCreateInput, authorization: Optional[str] = Header(None)
):
    """Register a new MCP server."""
    verify_auth(authorization)
    try:
        server = mcp_manager.create_server(data)
        return server.model_dump(mode="json")
    except ValueError as e:
        raise bad_request(str(e))


@v1_router.put("/mcp/servers/{server_id}", responses=CRUD_RESPONSES)
def update_mcp_server(
    server_id: str,
    data: MCPServerUpdateInput,
    authorization: Optional[str] = Header(None),
):
    """Update an MCP server registration."""
    verify_auth(authorization)
    server = mcp_manager.update_server(server_id, data)
    if not server:
        raise not_found("MCP Server", server_id)
    return server.model_dump(mode="json")


@v1_router.delete("/mcp/servers/{server_id}", responses=CRUD_RESPONSES)
def delete_mcp_server(server_id: str, authorization: Optional[str] = Header(None)):
    """Delete an MCP server registration."""
    verify_auth(authorization)
    if mcp_manager.delete_server(server_id):
        return {"status": "success"}
    raise not_found("MCP Server", server_id)


@v1_router.post("/mcp/servers/{server_id}/test", responses=CRUD_RESPONSES)
def test_mcp_connection(server_id: str, authorization: Optional[str] = Header(None)):
    """Test connection to an MCP server.

    Attempts to connect and discover available tools.
    """
    verify_auth(authorization)
    server = mcp_manager.get_server(server_id)
    if not server:
        raise not_found("MCP Server", server_id)

    result = mcp_manager.test_connection(server_id)
    return {
        "success": result.success,
        "error": result.error,
        "tools": [t.model_dump() for t in result.tools],
        "resources": [r.model_dump() for r in result.resources],
    }


@v1_router.get("/mcp/servers/{server_id}/tools", responses=CRUD_RESPONSES)
def get_mcp_server_tools(server_id: str, authorization: Optional[str] = Header(None)):
    """Get tools available on an MCP server."""
    verify_auth(authorization)
    server = mcp_manager.get_server(server_id)
    if not server:
        raise not_found("MCP Server", server_id)
    return [t.model_dump() for t in server.tools]


# =============================================================================
# Credentials Endpoints
# =============================================================================


@v1_router.get("/credentials", responses=AUTH_RESPONSES)
def list_credentials(authorization: Optional[str] = Header(None)):
    """List all credentials (values not exposed)."""
    verify_auth(authorization)
    credentials = mcp_manager.list_credentials()
    return [c.model_dump(mode="json") for c in credentials]


@v1_router.get("/credentials/{credential_id}", responses=CRUD_RESPONSES)
def get_credential(credential_id: str, authorization: Optional[str] = Header(None)):
    """Get a specific credential by ID (value not exposed)."""
    verify_auth(authorization)
    credential = mcp_manager.get_credential(credential_id)
    if not credential:
        raise not_found("Credential", credential_id)
    return credential.model_dump(mode="json")


@v1_router.post("/credentials", responses=CRUD_RESPONSES)
def create_credential(
    data: CredentialCreateInput, authorization: Optional[str] = Header(None)
):
    """Create a new credential.

    The credential value is encrypted before storage and never exposed via API.
    """
    verify_auth(authorization)
    try:
        credential = mcp_manager.create_credential(data)
        return credential.model_dump(mode="json")
    except ValueError as e:
        raise bad_request(str(e))


@v1_router.delete("/credentials/{credential_id}", responses=CRUD_RESPONSES)
def delete_credential(credential_id: str, authorization: Optional[str] = Header(None)):
    """Delete a credential.

    Any MCP servers using this credential will be set to 'not_configured' status.
    """
    verify_auth(authorization)
    if mcp_manager.delete_credential(credential_id):
        return {"status": "success"}
    raise not_found("Credential", credential_id)


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


# =============================================================================
# Settings Endpoints (User Preferences and API Keys)
# =============================================================================


class PreferencesUpdateRequest(BaseModel):
    """Request to update user preferences."""

    theme: Optional[str] = None
    compact_view: Optional[bool] = None
    show_costs: Optional[bool] = None
    default_page_size: Optional[int] = None
    notifications: Optional[Dict] = None


class APIKeyCreateRequest(BaseModel):
    """Request to create/update an API key."""

    provider: str
    key: str


@v1_router.get("/settings/preferences", responses=AUTH_RESPONSES)
def get_preferences(authorization: Optional[str] = Header(None)):
    """Get user preferences."""
    user_id = verify_auth(authorization)

    prefs = settings_manager.get_preferences(user_id)
    return prefs.model_dump(mode="json")


@v1_router.post("/settings/preferences", responses=AUTH_RESPONSES)
def update_preferences(
    request: PreferencesUpdateRequest,
    authorization: Optional[str] = Header(None),
):
    """Update user preferences."""
    user_id = verify_auth(authorization)

    from test_ai.settings.models import NotificationSettings, UserPreferencesUpdate

    # Build update object
    update_data = {}
    if request.theme is not None:
        if request.theme not in ("light", "dark", "system"):
            raise bad_request(
                "Invalid theme", {"valid_values": ["light", "dark", "system"]}
            )
        update_data["theme"] = request.theme
    if request.compact_view is not None:
        update_data["compact_view"] = request.compact_view
    if request.show_costs is not None:
        update_data["show_costs"] = request.show_costs
    if request.default_page_size is not None:
        if request.default_page_size < 10 or request.default_page_size > 100:
            raise bad_request("Invalid page size", {"valid_range": "10-100"})
        update_data["default_page_size"] = request.default_page_size
    if request.notifications is not None:
        update_data["notifications"] = NotificationSettings(**request.notifications)

    update = UserPreferencesUpdate(**update_data)
    prefs = settings_manager.update_preferences(user_id, update)
    return prefs.model_dump(mode="json")


@v1_router.get("/settings/api-keys", responses=AUTH_RESPONSES)
def get_api_keys(authorization: Optional[str] = Header(None)):
    """Get API key metadata (keys are masked, not returned in full)."""
    user_id = verify_auth(authorization)

    keys = settings_manager.get_api_keys(user_id)
    return [k.model_dump(mode="json") for k in keys]


@v1_router.get("/settings/api-keys/status", responses=AUTH_RESPONSES)
def get_api_key_status(authorization: Optional[str] = Header(None)):
    """Get status of which API keys are configured."""
    user_id = verify_auth(authorization)

    status = settings_manager.get_api_key_status(user_id)
    return status.model_dump()


@v1_router.post("/settings/api-keys", responses=AUTH_RESPONSES)
def set_api_key(
    request: APIKeyCreateRequest,
    authorization: Optional[str] = Header(None),
):
    """Set or update an API key."""
    user_id = verify_auth(authorization)

    if request.provider not in ("openai", "anthropic", "github"):
        raise bad_request(
            "Invalid provider",
            {"valid_providers": ["openai", "anthropic", "github"]},
        )

    if not request.key or len(request.key) < 10:
        raise bad_request("API key is too short")

    from test_ai.settings.models import APIKeyCreate

    key_create = APIKeyCreate(provider=request.provider, key=request.key)
    key_info = settings_manager.set_api_key(user_id, key_create)
    return {
        "status": "success",
        "key": key_info.model_dump(mode="json"),
    }


@v1_router.delete("/settings/api-keys/{provider}", responses=CRUD_RESPONSES)
def delete_api_key(provider: str, authorization: Optional[str] = Header(None)):
    """Delete an API key."""
    user_id = verify_auth(authorization)

    if provider not in ("openai", "anthropic", "github"):
        raise bad_request(
            "Invalid provider",
            {"valid_providers": ["openai", "anthropic", "github"]},
        )

    if settings_manager.delete_api_key(user_id, provider):
        return {"status": "success"}

    raise not_found("API Key", provider)


# =============================================================================
# Budget Endpoints
# =============================================================================


class BudgetCreateRequest(BaseModel):
    """Request to create a budget."""

    name: str
    total_amount: float
    period: str = "monthly"
    agent_id: Optional[str] = None


class BudgetUpdateRequest(BaseModel):
    """Request to update a budget."""

    name: Optional[str] = None
    total_amount: Optional[float] = None
    used_amount: Optional[float] = None
    period: Optional[str] = None
    agent_id: Optional[str] = None


@v1_router.get("/budgets", responses=AUTH_RESPONSES)
def list_budgets(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    period: Optional[str] = Query(
        None, description="Filter by period (daily/weekly/monthly)"
    ),
    authorization: Optional[str] = Header(None),
):
    """List all budgets with optional filtering."""
    verify_auth(authorization)

    from test_ai.budget import BudgetPeriod

    period_enum = None
    if period:
        try:
            period_enum = BudgetPeriod(period)
        except ValueError:
            raise bad_request(
                "Invalid period",
                {"valid_periods": ["daily", "weekly", "monthly"]},
            )

    budgets = budget_manager.list_budgets(agent_id=agent_id, period=period_enum)
    return [b.model_dump(mode="json") for b in budgets]


@v1_router.get("/budgets/summary", responses=AUTH_RESPONSES)
def get_budget_summary(authorization: Optional[str] = Header(None)):
    """Get overall budget summary."""
    verify_auth(authorization)

    summary = budget_manager.get_summary()
    return summary.model_dump()


@v1_router.get("/budgets/{budget_id}", responses=CRUD_RESPONSES)
def get_budget(budget_id: str, authorization: Optional[str] = Header(None)):
    """Get a specific budget by ID."""
    verify_auth(authorization)

    budget = budget_manager.get_budget(budget_id)
    if not budget:
        raise not_found("Budget", budget_id)
    return budget.model_dump(mode="json")


@v1_router.post("/budgets", responses=CRUD_RESPONSES)
def create_budget(
    request: BudgetCreateRequest,
    authorization: Optional[str] = Header(None),
):
    """Create a new budget."""
    verify_auth(authorization)

    from test_ai.budget import BudgetCreate, BudgetPeriod

    # Validate period
    try:
        period = BudgetPeriod(request.period)
    except ValueError:
        raise bad_request(
            "Invalid period",
            {"valid_periods": ["daily", "weekly", "monthly"]},
        )

    # Validate name
    if not request.name or len(request.name) < 1:
        raise bad_request("Budget name is required")

    # Validate amount
    if request.total_amount < 0:
        raise bad_request("Total amount must be non-negative")

    budget_create = BudgetCreate(
        name=request.name,
        total_amount=request.total_amount,
        period=period,
        agent_id=request.agent_id,
    )

    try:
        budget = budget_manager.create_budget(budget_create)
        return budget.model_dump(mode="json")
    except ValueError as e:
        raise bad_request(str(e))


@v1_router.patch("/budgets/{budget_id}", responses=CRUD_RESPONSES)
def update_budget(
    budget_id: str,
    request: BudgetUpdateRequest,
    authorization: Optional[str] = Header(None),
):
    """Update a budget."""
    verify_auth(authorization)

    from test_ai.budget import BudgetUpdate, BudgetPeriod

    # Validate period if provided
    period = None
    if request.period is not None:
        try:
            period = BudgetPeriod(request.period)
        except ValueError:
            raise bad_request(
                "Invalid period",
                {"valid_periods": ["daily", "weekly", "monthly"]},
            )

    # Validate amounts if provided
    if request.total_amount is not None and request.total_amount < 0:
        raise bad_request("Total amount must be non-negative")
    if request.used_amount is not None and request.used_amount < 0:
        raise bad_request("Used amount must be non-negative")

    budget_update = BudgetUpdate(
        name=request.name,
        total_amount=request.total_amount,
        used_amount=request.used_amount,
        period=period,
        agent_id=request.agent_id,
    )

    budget = budget_manager.update_budget(budget_id, budget_update)
    if not budget:
        raise not_found("Budget", budget_id)
    return budget.model_dump(mode="json")


@v1_router.delete("/budgets/{budget_id}", responses=CRUD_RESPONSES)
def delete_budget(budget_id: str, authorization: Optional[str] = Header(None)):
    """Delete a budget."""
    verify_auth(authorization)

    if budget_manager.delete_budget(budget_id):
        return {"status": "success"}
    raise not_found("Budget", budget_id)


@v1_router.post("/budgets/{budget_id}/add-usage", responses=CRUD_RESPONSES)
def add_budget_usage(
    budget_id: str,
    amount: float = Query(..., ge=0, description="Amount to add to usage"),
    authorization: Optional[str] = Header(None),
):
    """Add usage to a budget."""
    verify_auth(authorization)

    budget = budget_manager.add_usage(budget_id, amount)
    if not budget:
        raise not_found("Budget", budget_id)
    return budget.model_dump(mode="json")


@v1_router.post("/budgets/{budget_id}/reset", responses=CRUD_RESPONSES)
def reset_budget_usage(budget_id: str, authorization: Optional[str] = Header(None)):
    """Reset usage for a budget."""
    verify_auth(authorization)

    budget = budget_manager.reset_usage(budget_id)
    if not budget:
        raise not_found("Budget", budget_id)
    return budget.model_dump(mode="json")


# =============================================================================
# Agents Endpoint
# =============================================================================

# Icon mapping for agent roles (used by frontend)
_AGENT_ICONS = {
    AgentRole.PLANNER: "Brain",
    AgentRole.BUILDER: "Code",
    AgentRole.TESTER: "TestTube",
    AgentRole.REVIEWER: "Search",
    AgentRole.ANALYST: "BarChart3",
    AgentRole.VISUALIZER: "PieChart",
    AgentRole.REPORTER: "FileOutput",
    AgentRole.DATA_ANALYST: "Database",
    AgentRole.DEVOPS: "Server",
    AgentRole.SECURITY_AUDITOR: "Shield",
    AgentRole.MIGRATOR: "ArrowRightLeft",
    AgentRole.MODEL_BUILDER: "Boxes",
}

# Color mapping for agent roles (used by frontend)
_AGENT_COLORS = {
    AgentRole.PLANNER: "#8B5CF6",
    AgentRole.BUILDER: "#3B82F6",
    AgentRole.TESTER: "#10B981",
    AgentRole.REVIEWER: "#F59E0B",
    AgentRole.ANALYST: "#14B8A6",
    AgentRole.VISUALIZER: "#F97316",
    AgentRole.REPORTER: "#8B5CF6",
    AgentRole.DATA_ANALYST: "#06B6D4",
    AgentRole.DEVOPS: "#6366F1",
    AgentRole.SECURITY_AUDITOR: "#EF4444",
    AgentRole.MIGRATOR: "#EC4899",
    AgentRole.MODEL_BUILDER: "#A855F7",
}

# Capabilities mapping for agent roles
_AGENT_CAPABILITIES = {
    AgentRole.PLANNER: [
        "Task decomposition",
        "Dependency analysis",
        "Resource estimation",
    ],
    AgentRole.BUILDER: ["Code generation", "Refactoring", "Implementation"],
    AgentRole.TESTER: ["Unit tests", "Integration tests", "Edge case coverage"],
    AgentRole.REVIEWER: ["Code review", "Security audit", "Best practices check"],
    AgentRole.ANALYST: ["Data analysis", "Pattern recognition", "Insights extraction"],
    AgentRole.VISUALIZER: [
        "Chart generation",
        "Dashboard design",
        "Data visualization",
    ],
    AgentRole.REPORTER: [
        "Summary generation",
        "Progress reports",
        "Stakeholder updates",
    ],
    AgentRole.DATA_ANALYST: ["SQL queries", "Pandas pipelines", "Statistical analysis"],
    AgentRole.DEVOPS: [
        "CI/CD pipelines",
        "Infrastructure as code",
        "Container orchestration",
    ],
    AgentRole.SECURITY_AUDITOR: [
        "Vulnerability scanning",
        "OWASP compliance",
        "Dependency audits",
    ],
    AgentRole.MIGRATOR: ["Framework upgrades", "Code refactoring", "API migrations"],
    AgentRole.MODEL_BUILDER: ["3D modeling", "Scene creation", "Asset generation"],
}


class AgentDefinitionResponse(BaseModel):
    """Response model for agent definition."""

    id: str
    name: str
    description: str
    capabilities: list[str]
    icon: str
    color: str


@v1_router.get("/agents", responses=AUTH_RESPONSES)
def list_agents(
    authorization: Optional[str] = Header(None),
) -> list[AgentDefinitionResponse]:
    """List all available agent role definitions.

    Returns agent roles with their descriptions, capabilities, and display metadata.
    """
    verify_auth(authorization)

    agents = []
    for role, contract in _CONTRACT_REGISTRY.items():
        agents.append(
            AgentDefinitionResponse(
                id=role.value,
                name=role.value.replace("_", " ").title(),
                description=contract.description,
                capabilities=_AGENT_CAPABILITIES.get(role, []),
                icon=_AGENT_ICONS.get(role, "Bot"),
                color=_AGENT_COLORS.get(role, "#6B7280"),
            )
        )

    return agents


@v1_router.get("/agents/{agent_id}", responses=CRUD_RESPONSES)
def get_agent(agent_id: str, authorization: Optional[str] = Header(None)):
    """Get a specific agent role definition by ID."""
    verify_auth(authorization)

    # Find the matching role
    try:
        role = AgentRole(agent_id)
    except ValueError:
        raise not_found("Agent", agent_id)

    if role not in _CONTRACT_REGISTRY:
        raise not_found("Agent", agent_id)

    contract = _CONTRACT_REGISTRY[role]
    return AgentDefinitionResponse(
        id=role.value,
        name=role.value.replace("_", " ").title(),
        description=contract.description,
        capabilities=_AGENT_CAPABILITIES.get(role, []),
        icon=_AGENT_ICONS.get(role, "Bot"),
        color=_AGENT_COLORS.get(role, "#6B7280"),
    )


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


# =============================================================================
# Dashboard Endpoints
# =============================================================================


class DashboardStats(BaseModel):
    """Dashboard statistics response."""

    totalWorkflows: int
    activeExecutions: int
    completedToday: int
    failedToday: int
    totalTokensToday: int
    totalCostToday: float


class RecentExecution(BaseModel):
    """Recent execution summary for dashboard."""

    id: str
    name: str
    status: str
    time: str


class DailyUsage(BaseModel):
    """Daily usage data point."""

    date: str
    tokens: int
    cost: float


class AgentUsage(BaseModel):
    """Per-agent usage data point."""

    agent: str
    tokens: int


class BudgetStatus(BaseModel):
    """Budget status for an agent."""

    agent: str
    used: float
    limit: float


class DashboardBudget(BaseModel):
    """Dashboard budget summary."""

    totalBudget: float
    totalUsed: float
    percentUsed: float
    byAgent: list[BudgetStatus]
    alert: Optional[str] = None


@v1_router.get("/dashboard/stats", responses=AUTH_RESPONSES)
def get_dashboard_stats(authorization: Optional[str] = Header(None)):
    """Get dashboard statistics."""
    verify_auth(authorization)

    from datetime import date

    from test_ai.executions import ExecutionStatus

    today_start = datetime.combine(date.today(), datetime.min.time())

    # Get workflow count
    workflows = workflow_engine.list_workflows()
    total_workflows = len(workflows) if workflows else 0

    # Get execution stats from database
    backend = get_database()

    # Active executions (running or paused)
    active_row = backend.fetchone(
        """
        SELECT COUNT(*) as count FROM executions
        WHERE status IN (?, ?)
        """,
        (ExecutionStatus.RUNNING.value, ExecutionStatus.PAUSED.value),
    )
    active_executions = active_row["count"] if active_row else 0

    # Completed today
    completed_row = backend.fetchone(
        """
        SELECT COUNT(*) as count FROM executions
        WHERE status = ?
        AND datetime(completed_at) >= datetime(?)
        """,
        (ExecutionStatus.COMPLETED.value, today_start.isoformat()),
    )
    completed_today = completed_row["count"] if completed_row else 0

    # Failed today
    failed_row = backend.fetchone(
        """
        SELECT COUNT(*) as count FROM executions
        WHERE status = ?
        AND datetime(completed_at) >= datetime(?)
        """,
        (ExecutionStatus.FAILED.value, today_start.isoformat()),
    )
    failed_today = failed_row["count"] if failed_row else 0

    # Token usage today - aggregate from metrics for executions started today
    tokens_row = backend.fetchone(
        """
        SELECT COALESCE(SUM(m.total_tokens), 0) as tokens,
               COALESCE(SUM(m.total_cost_cents), 0) as cost_cents
        FROM execution_metrics m
        JOIN executions e ON e.id = m.execution_id
        WHERE datetime(e.created_at) >= datetime(?)
        """,
        (today_start.isoformat(),),
    )
    total_tokens_today = tokens_row["tokens"] if tokens_row else 0
    total_cost_today = (tokens_row["cost_cents"] / 100.0) if tokens_row else 0.0

    return DashboardStats(
        totalWorkflows=total_workflows,
        activeExecutions=active_executions,
        completedToday=completed_today,
        failedToday=failed_today,
        totalTokensToday=total_tokens_today,
        totalCostToday=total_cost_today,
    )


@v1_router.get("/dashboard/recent-executions", responses=AUTH_RESPONSES)
def get_recent_executions(
    limit: int = 5,
    authorization: Optional[str] = Header(None),
):
    """Get recent executions for dashboard display."""
    verify_auth(authorization)

    result = execution_manager.list_executions(page=1, page_size=limit)
    executions = []

    for exec in result.data:
        # Calculate relative time
        if exec.started_at:
            delta = datetime.now() - exec.started_at
            if delta.total_seconds() < 60:
                time_str = "just now"
            elif delta.total_seconds() < 3600:
                mins = int(delta.total_seconds() / 60)
                time_str = f"{mins} min ago"
            elif delta.total_seconds() < 86400:
                hours = int(delta.total_seconds() / 3600)
                time_str = f"{hours} hour{'s' if hours > 1 else ''} ago"
            else:
                days = int(delta.total_seconds() / 86400)
                time_str = f"{days} day{'s' if days > 1 else ''} ago"
        else:
            time_str = "pending"

        executions.append(
            RecentExecution(
                id=exec.id,
                name=exec.workflow_name,
                status=exec.status.value,
                time=time_str,
            )
        )

    return executions


@v1_router.get("/dashboard/usage/daily", responses=AUTH_RESPONSES)
def get_daily_usage(
    days: int = 7,
    authorization: Optional[str] = Header(None),
):
    """Get daily token and cost usage for the past N days."""
    verify_auth(authorization)

    from datetime import date, timedelta

    backend = get_database()
    usage_data = []

    # Generate data for each day
    for i in range(days - 1, -1, -1):
        target_date = date.today() - timedelta(days=i)
        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = datetime.combine(target_date + timedelta(days=1), datetime.min.time())

        row = backend.fetchone(
            """
            SELECT COALESCE(SUM(m.total_tokens), 0) as tokens,
                   COALESCE(SUM(m.total_cost_cents), 0) as cost_cents
            FROM execution_metrics m
            JOIN executions e ON e.id = m.execution_id
            WHERE datetime(e.created_at) >= datetime(?)
            AND datetime(e.created_at) < datetime(?)
            """,
            (day_start.isoformat(), day_end.isoformat()),
        )

        # Format day name (Mon, Tue, etc.)
        day_name = target_date.strftime("%a")

        usage_data.append(
            DailyUsage(
                date=day_name,
                tokens=row["tokens"] if row else 0,
                cost=round((row["cost_cents"] / 100.0) if row else 0.0, 2),
            )
        )

    return usage_data


@v1_router.get("/dashboard/usage/by-agent", responses=AUTH_RESPONSES)
def get_agent_usage(authorization: Optional[str] = Header(None)):
    """Get token usage breakdown by agent role.

    Note: This requires workflow step tracking to be implemented.
    For now, returns mock data based on workflow names/patterns.
    """
    verify_auth(authorization)

    backend = get_database()

    # Get total tokens from recent executions grouped by workflow name patterns
    # In a full implementation, this would track per-step agent usage
    rows = backend.fetchall(
        """
        SELECT e.workflow_name, COALESCE(SUM(m.total_tokens), 0) as tokens
        FROM executions e
        JOIN execution_metrics m ON e.id = m.execution_id
        WHERE datetime(e.created_at) >= datetime('now', '-30 days')
        GROUP BY e.workflow_name
        ORDER BY tokens DESC
        LIMIT 10
        """
    )

    # Map workflow names to agent-like categories
    # In production, this would come from step-level tracking
    agent_map = {
        "planner": 0,
        "builder": 0,
        "tester": 0,
        "reviewer": 0,
        "documenter": 0,
    }

    for row in rows:
        name_lower = (row["workflow_name"] or "").lower()
        tokens = row["tokens"] or 0

        # Distribute tokens based on workflow name patterns
        if "plan" in name_lower or "analysis" in name_lower:
            agent_map["planner"] += tokens
        elif "build" in name_lower or "implement" in name_lower or "code" in name_lower:
            agent_map["builder"] += tokens
        elif "test" in name_lower:
            agent_map["tester"] += tokens
        elif "review" in name_lower:
            agent_map["reviewer"] += tokens
        elif "doc" in name_lower:
            agent_map["documenter"] += tokens
        else:
            # Distribute to builder as default
            agent_map["builder"] += tokens

    # Convert to list format for frontend
    usage = [
        AgentUsage(agent=agent.title(), tokens=tokens)
        for agent, tokens in agent_map.items()
        if tokens > 0
    ]

    # If no data, return reasonable defaults
    if not usage:
        usage = [
            AgentUsage(agent="Planner", tokens=0),
            AgentUsage(agent="Builder", tokens=0),
            AgentUsage(agent="Tester", tokens=0),
            AgentUsage(agent="Reviewer", tokens=0),
            AgentUsage(agent="Documenter", tokens=0),
        ]

    return usage


@v1_router.get("/dashboard/budget", responses=AUTH_RESPONSES)
def get_dashboard_budget(authorization: Optional[str] = Header(None)):
    """Get budget status for dashboard display."""
    verify_auth(authorization)

    # Default budget limits (in production these would come from settings/database)
    budget_limits = {
        "Builder": 40.0,
        "Planner": 20.0,
        "Reviewer": 25.0,
        "Tester": 15.0,
    }
    total_budget = 100.0

    backend = get_database()

    # Get this month's usage
    from datetime import date

    month_start = date.today().replace(day=1)

    # Get usage by workflow pattern (proxy for agent)
    rows = backend.fetchall(
        """
        SELECT e.workflow_name, COALESCE(SUM(m.total_cost_cents), 0) as cost_cents
        FROM executions e
        JOIN execution_metrics m ON e.id = m.execution_id
        WHERE datetime(e.created_at) >= datetime(?)
        GROUP BY e.workflow_name
        """,
        (datetime.combine(month_start, datetime.min.time()).isoformat(),),
    )

    # Map to agents (simplified)
    agent_costs = {agent: 0.0 for agent in budget_limits}

    for row in rows:
        name_lower = (row["workflow_name"] or "").lower()
        cost = (row["cost_cents"] or 0) / 100.0

        if "plan" in name_lower or "analysis" in name_lower:
            agent_costs["Planner"] += cost
        elif "review" in name_lower:
            agent_costs["Reviewer"] += cost
        elif "test" in name_lower:
            agent_costs["Tester"] += cost
        else:
            agent_costs["Builder"] += cost

    total_used = sum(agent_costs.values())

    # Build response
    by_agent = [
        BudgetStatus(agent=agent, used=round(cost, 2), limit=budget_limits[agent])
        for agent, cost in agent_costs.items()
    ]

    # Generate alert if any agent is over 80% of limit
    alert = None
    for status in by_agent:
        if status.limit > 0:
            percent = (status.used / status.limit) * 100
            if percent >= 80:
                alert = f"{status.agent} agent at {int(percent)}% of monthly limit"
                break

    return DashboardBudget(
        totalBudget=total_budget,
        totalUsed=round(total_used, 2),
        percentUsed=round((total_used / total_budget) * 100, 1)
        if total_budget > 0
        else 0,
        byAgent=by_agent,
        alert=alert,
    )


# Include versioned API router
app.include_router(v1_router)


# =============================================================================
# WebSocket Endpoint
# =============================================================================


@app.websocket("/ws/executions")
async def websocket_executions(
    websocket: WebSocket,
    token: str | None = Query(None),
):
    """WebSocket endpoint for real-time execution updates.

    Authentication via query parameter: ws://host/ws/executions?token=<jwt>

    Protocol:
    - Client sends: subscribe, unsubscribe, ping
    - Server sends: connected, execution_status, execution_log, execution_metrics, pong, error

    Example:
        ws = new WebSocket("ws://localhost:8000/ws/executions?token=eyJ...")
        ws.send(JSON.stringify({type: "subscribe", execution_ids: ["abc"]}))
    """
    # Verify authentication
    if not token:
        await websocket.close(code=4001, reason="Missing token parameter")
        return

    user_id = verify_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    # Handle connection
    if ws_manager is None:
        await websocket.close(code=4500, reason="WebSocket not available")
        return

    await ws_manager.handle_connection(websocket)


@app.get("/ws/stats", include_in_schema=False)
def websocket_stats():
    """Get WebSocket connection statistics (internal use)."""
    if ws_manager is None:
        return {"error": "WebSocket not initialized"}
    return ws_manager.get_stats()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
