"""FastAPI router for chat endpoints."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

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


def get_session_manager() -> ChatSessionManager:
    """Get the chat session manager."""
    if _session_manager is None:
        raise HTTPException(status_code=503, detail="Chat service not initialized")
    return _session_manager


def init_chat_module(backend: "DatabaseBackend", supervisor_factory=None):
    """Initialize the chat module with database backend.

    Args:
        backend: Database backend instance.
        supervisor_factory: Factory function to create SupervisorAgent.
    """
    global _session_manager, _supervisor_factory
    _session_manager = ChatSessionManager(backend)
    _supervisor_factory = supervisor_factory
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
    session = manager.create_session(
        title=request.title,
        project_path=request.project_path,
        mode=request.mode,
    )
    return ChatSessionResponse(
        id=session.id,
        title=session.title,
        project_path=session.project_path,
        mode=session.mode,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=0,
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

    # Stream response
    async def generate() -> AsyncGenerator[str, None]:
        """Generate SSE stream."""
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

        try:
            # Create supervisor with session context
            supervisor = _supervisor_factory(mode=session.mode)

            # Get conversation history
            messages = manager.get_messages(session_id)

            # Process message through supervisor
            full_response = ""
            current_agent = "supervisor"

            async for chunk_data in supervisor.process_message(
                content=request.content,
                messages=messages[:-1],  # Exclude the just-added user message
                project_path=session.project_path,
            ):
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

            # Store assistant response
            if full_response:
                manager.add_message(
                    session_id=session_id,
                    role=MessageRole.ASSISTANT,
                    content=full_response,
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

    Note: This is a placeholder. Actual cancellation requires
    tracking active generation tasks.
    """
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # TODO: Implement actual cancellation via task tracking
    return {"status": "cancelled"}


# ============================================================================
# Job linkage endpoints
# ============================================================================


@router.get("/sessions/{session_id}/jobs")
async def get_session_jobs(
    session_id: str,
    manager: ChatSessionManager = Depends(get_session_manager),
):
    """Get jobs linked to a chat session."""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    job_ids = manager.get_session_jobs(session_id)

    # TODO: Fetch full job details from JobManager
    return {"session_id": session_id, "job_ids": job_ids}
