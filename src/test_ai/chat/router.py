"""FastAPI router for chat endpoints."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .models import (
    ChatSessionDetailResponse,
    ChatSessionResponse,
    CreateSessionRequest,
    MessageRole,
    SendMessageRequest,
    StreamChunk,
)
from .session_manager import ChatSessionManager

if TYPE_CHECKING:
    from test_ai.state.backends import DatabaseBackend

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Module-level manager (initialized by lifespan)
_session_manager: ChatSessionManager | None = None
_supervisor_factory = None  # Factory function for creating supervisor
_backend: "DatabaseBackend | None" = None

# Track active generation tasks for cancellation
_active_generations: dict[str, asyncio.Event] = {}


def get_session_manager() -> ChatSessionManager:
    """Get the chat session manager."""
    if _session_manager is None:
        raise HTTPException(status_code=503, detail="Chat service not initialized")
    return _session_manager


def get_backend() -> "DatabaseBackend":
    """Get the database backend."""
    if _backend is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return _backend


def init_chat_module(backend: "DatabaseBackend", supervisor_factory=None):
    """Initialize the chat module with database backend.

    Args:
        backend: Database backend instance.
        supervisor_factory: Factory function to create SupervisorAgent.
    """
    global _session_manager, _supervisor_factory, _backend
    _session_manager = ChatSessionManager(backend)
    _supervisor_factory = supervisor_factory
    _backend = backend
    logger.info("Chat module initialized")


# ============================================================================
# Session endpoints
# ============================================================================


@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(
    request: CreateSessionRequest,
    manager: ChatSessionManager = Depends(get_session_manager),
) -> ChatSessionResponse:
    """Create a new chat session."""
    # Store allowed_paths in metadata if provided
    metadata = {}
    if request.allowed_paths:
        metadata["allowed_paths"] = request.allowed_paths

    session = manager.create_session(
        title=request.title,
        project_path=request.project_path,
        mode=request.mode,
        metadata=metadata,
    )

    # Determine filesystem_enabled status
    filesystem_enabled = request.filesystem_enabled and request.project_path is not None

    return ChatSessionResponse(
        id=session.id,
        title=session.title,
        project_path=session.project_path,
        mode=session.mode,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=0,
        filesystem_enabled=filesystem_enabled,
    )


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    manager: ChatSessionManager = Depends(get_session_manager),
) -> list[ChatSessionResponse]:
    """List chat sessions."""
    sessions = manager.list_sessions(status=status, limit=limit, offset=offset)
    return [
        ChatSessionResponse(
            id=s.id,
            title=s.title,
            project_path=s.project_path,
            mode=s.mode,
            status=s.status,
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=manager.get_message_count(s.id),
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
async def get_session(
    session_id: str,
    manager: ChatSessionManager = Depends(get_session_manager),
) -> ChatSessionDetailResponse:
    """Get a chat session with messages."""
    session = manager.get_session_with_messages(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return ChatSessionDetailResponse(
        id=session.id,
        title=session.title,
        project_path=session.project_path,
        mode=session.mode,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=len(session.messages),
        messages=session.messages,
    )


class UpdateSessionRequest(BaseModel):
    """Request to update a session."""

    title: str | None = None
    status: str | None = None


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    manager: ChatSessionManager = Depends(get_session_manager),
) -> ChatSessionResponse:
    """Update a chat session."""
    session = manager.update_session(
        session_id,
        title=request.title,
        status=request.status,
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return ChatSessionResponse(
        id=session.id,
        title=session.title,
        project_path=session.project_path,
        mode=session.mode,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=manager.get_message_count(session.id),
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    manager: ChatSessionManager = Depends(get_session_manager),
):
    """Delete a chat session."""
    if not manager.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}


# ============================================================================
# Message endpoints
# ============================================================================


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    manager: ChatSessionManager = Depends(get_session_manager),
) -> StreamingResponse:
    """Send a message and stream the response.

    Uses Server-Sent Events (SSE) for streaming.
    """
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Store user message
    manager.add_message(
        session_id=session_id,
        role=MessageRole.USER,
        content=request.content,
    )

    # Update title if this is the first message
    if manager.get_message_count(session_id) == 1:
        title = manager.generate_title(session_id)
        manager.update_session(session_id, title=title)

    # Create cancellation event for this generation
    cancel_event = asyncio.Event()
    _active_generations[session_id] = cancel_event

    # Stream response
    async def generate() -> AsyncGenerator[str, None]:
        """Generate SSE stream."""
        try:
            if _supervisor_factory is None:
                # No supervisor available, return simple acknowledgment
                chunk = StreamChunk(
                    type="text",
                    content="I received your message, but the AI backend is not configured.",
                    agent="system",
                )
                yield f"data: {chunk.model_dump_json()}\n\n"
                yield f"data: {StreamChunk(type='done').model_dump_json()}\n\n"
                return

            # Create supervisor with session and backend context
            supervisor = _supervisor_factory(
                mode=session.mode,
                session=session,
                backend=_backend,
            )

            # Get conversation history
            messages = manager.get_messages(session_id)

            # Process message through supervisor
            full_response = ""
            current_agent = "supervisor"
            cancelled = False

            async for chunk_data in supervisor.process_message(
                content=request.content,
                messages=messages[:-1],  # Exclude the just-added user message
                project_path=session.project_path,
            ):
                # Check for cancellation
                if cancel_event.is_set():
                    cancelled = True
                    cancel_chunk = StreamChunk(
                        type="cancelled", content="Generation cancelled"
                    )
                    yield f"data: {cancel_chunk.model_dump_json()}\n\n"
                    break

                chunk_type = chunk_data.get("type", "text")
                content = chunk_data.get("content", "")
                agent = chunk_data.get("agent", current_agent)

                if agent:
                    current_agent = agent

                if chunk_type == "text" and content:
                    full_response += content

                chunk = StreamChunk(
                    type=chunk_type,
                    content=content,
                    agent=agent,
                    job_id=chunk_data.get("job_id"),
                    error=chunk_data.get("error"),
                )
                yield f"data: {chunk.model_dump_json()}\n\n"

            # Store assistant response (even partial if cancelled)
            if full_response:
                manager.add_message(
                    session_id=session_id,
                    role=MessageRole.ASSISTANT,
                    content=full_response + (" [cancelled]" if cancelled else ""),
                    agent=current_agent,
                )

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            error_chunk = StreamChunk(type="error", error=str(e))
            yield f"data: {error_chunk.model_dump_json()}\n\n"

            # Store error as system message
            manager.add_message(
                session_id=session_id,
                role=MessageRole.SYSTEM,
                content=f"Error: {str(e)}",
            )
        finally:
            # Clean up cancellation tracking
            _active_generations.pop(session_id, None)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sessions/{session_id}/cancel")
async def cancel_generation(
    session_id: str,
    manager: ChatSessionManager = Depends(get_session_manager),
):
    """Cancel an ongoing generation.

    Sets the cancellation event for the session, which will cause
    the streaming generator to stop and return a cancelled chunk.
    """
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if there's an active generation for this session
    cancel_event = _active_generations.get(session_id)
    if cancel_event is None:
        return {"status": "no_active_generation"}

    # Signal cancellation
    cancel_event.set()
    return {"status": "cancelled"}


# ============================================================================
# Job linkage endpoints
# ============================================================================


@router.get("/sessions/{session_id}/jobs")
async def get_session_jobs(
    session_id: str,
    manager: ChatSessionManager = Depends(get_session_manager),
):
    """Get jobs linked to a chat session with full details."""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    job_ids = manager.get_session_jobs(session_id)

    # Fetch full job details from JobManager
    jobs = []
    try:
        from test_ai.api import job_manager

        if job_manager:
            for job_id in job_ids:
                job = job_manager.get_job(job_id)
                if job:
                    jobs.append(
                        {
                            "id": job.id,
                            "workflow_id": job.workflow_id,
                            "status": job.status.value,
                            "created_at": job.created_at.isoformat(),
                            "started_at": job.started_at.isoformat()
                            if job.started_at
                            else None,
                            "completed_at": job.completed_at.isoformat()
                            if job.completed_at
                            else None,
                            "progress": job.progress,
                            "error": job.error,
                        }
                    )
    except ImportError:
        logger.warning("JobManager not available, returning job IDs only")

    return {"session_id": session_id, "jobs": jobs, "job_ids": job_ids}


# ============================================================================
# Edit proposal endpoints
# ============================================================================


class ProposalResponse(BaseModel):
    """Response model for edit proposals."""

    id: str
    session_id: str
    file_path: str
    description: str
    status: str
    created_at: str
    applied_at: str | None = None
    error_message: str | None = None
    # Content fields (optional for list views)
    old_content: str | None = None
    new_content: str | None = None


class ApproveProposalRequest(BaseModel):
    """Request to approve a proposal."""

    pass  # No body needed, just the action


class RejectProposalRequest(BaseModel):
    """Request to reject a proposal."""

    reason: str | None = Field(default=None, description="Optional rejection reason")


def _get_proposal_manager(session_id: str):
    """Get proposal manager for a session."""
    backend = get_backend()
    manager = get_session_manager()
    session = manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.project_path:
        raise HTTPException(
            status_code=400,
            detail="Session has no project path configured",
        )

    from test_ai.tools.safety import PathValidator, SecurityError
    from test_ai.tools.proposals import ProposalManager

    try:
        validator = PathValidator(
            project_path=session.project_path,
            allowed_paths=session.allowed_paths,
        )
        return ProposalManager(backend, validator)
    except SecurityError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}/proposals", response_model=list[ProposalResponse])
async def list_proposals(
    session_id: str,
    status: str | None = Query(None, description="Filter by status"),
    manager: ChatSessionManager = Depends(get_session_manager),
) -> list[ProposalResponse]:
    """List edit proposals for a session."""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.project_path:
        return []  # No proposals without project path

    proposal_manager = _get_proposal_manager(session_id)

    # Convert status string to enum if provided
    from test_ai.tools.models import ProposalStatus

    status_filter = ProposalStatus(status) if status else None
    proposals = proposal_manager.get_session_proposals(session_id, status_filter)

    return [
        ProposalResponse(
            id=p.id,
            session_id=p.session_id,
            file_path=p.file_path,
            description=p.description,
            status=p.status.value,
            created_at=p.created_at.isoformat(),
            applied_at=p.applied_at.isoformat() if p.applied_at else None,
            error_message=p.error_message,
        )
        for p in proposals
    ]


@router.get(
    "/sessions/{session_id}/proposals/{proposal_id}", response_model=ProposalResponse
)
async def get_proposal(
    session_id: str,
    proposal_id: str,
    manager: ChatSessionManager = Depends(get_session_manager),
) -> ProposalResponse:
    """Get a specific edit proposal with content."""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    proposal_manager = _get_proposal_manager(session_id)
    proposal = proposal_manager.get_proposal(proposal_id)

    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    if proposal.session_id != session_id:
        raise HTTPException(
            status_code=404, detail="Proposal not found in this session"
        )

    return ProposalResponse(
        id=proposal.id,
        session_id=proposal.session_id,
        file_path=proposal.file_path,
        description=proposal.description,
        status=proposal.status.value,
        created_at=proposal.created_at.isoformat(),
        applied_at=proposal.applied_at.isoformat() if proposal.applied_at else None,
        error_message=proposal.error_message,
        old_content=proposal.old_content,
        new_content=proposal.new_content,
    )


@router.post(
    "/sessions/{session_id}/proposals/{proposal_id}/approve",
    response_model=ProposalResponse,
)
async def approve_proposal(
    session_id: str,
    proposal_id: str,
    manager: ChatSessionManager = Depends(get_session_manager),
) -> ProposalResponse:
    """Approve and apply an edit proposal."""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    proposal_manager = _get_proposal_manager(session_id)

    # Verify proposal belongs to session
    proposal = proposal_manager.get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.session_id != session_id:
        raise HTTPException(
            status_code=404, detail="Proposal not found in this session"
        )

    try:
        approved = proposal_manager.approve_proposal(proposal_id)
        return ProposalResponse(
            id=approved.id,
            session_id=approved.session_id,
            file_path=approved.file_path,
            description=approved.description,
            status=approved.status.value,
            created_at=approved.created_at.isoformat(),
            applied_at=approved.applied_at.isoformat() if approved.applied_at else None,
            error_message=approved.error_message,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to approve proposal: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to apply edit: {e}")


@router.post(
    "/sessions/{session_id}/proposals/{proposal_id}/reject",
    response_model=ProposalResponse,
)
async def reject_proposal(
    session_id: str,
    proposal_id: str,
    request: RejectProposalRequest | None = None,
    manager: ChatSessionManager = Depends(get_session_manager),
) -> ProposalResponse:
    """Reject an edit proposal."""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    proposal_manager = _get_proposal_manager(session_id)

    # Verify proposal belongs to session
    proposal = proposal_manager.get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.session_id != session_id:
        raise HTTPException(
            status_code=404, detail="Proposal not found in this session"
        )

    try:
        rejected = proposal_manager.reject_proposal(proposal_id)
        return ProposalResponse(
            id=rejected.id,
            session_id=rejected.session_id,
            file_path=rejected.file_path,
            description=rejected.description,
            status=rejected.status.value,
            created_at=rejected.created_at.isoformat(),
            applied_at=rejected.applied_at.isoformat() if rejected.applied_at else None,
            error_message=rejected.error_message,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
