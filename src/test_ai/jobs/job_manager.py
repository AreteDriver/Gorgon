"""Async job execution manager for background workflow runs."""

import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from test_ai.config import get_settings
from test_ai.orchestrator import WorkflowEngine, WorkflowResult

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(BaseModel):
    """An async job representing a workflow execution."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Job ID")
    workflow_id: str = Field(..., description="Workflow being executed")
    status: JobStatus = Field(JobStatus.PENDING, description="Current status")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Job creation time"
    )
    started_at: Optional[datetime] = Field(None, description="Execution start time")
    completed_at: Optional[datetime] = Field(None, description="Execution end time")
    variables: Dict[str, Any] = Field(
        default_factory=dict, description="Variables passed to workflow"
    )
    result: Optional[Dict[str, Any]] = Field(None, description="Workflow result")
    error: Optional[str] = Field(None, description="Error message if failed")
    progress: Optional[str] = Field(None, description="Progress message")


class JobManager:
    """Manages async workflow execution with status polling."""

    def __init__(self, max_workers: int = 4):
        self.settings = get_settings()
        self.jobs_dir = self.settings.jobs_dir
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.workflow_engine = WorkflowEngine()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: Dict[str, Job] = {}
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
        self._load_recent_jobs()

    def _load_recent_jobs(self, limit: int = 100):
        """Load recent jobs from disk on startup."""
        job_files = sorted(self.jobs_dir.glob("*.json"), reverse=True)[:limit]
        for file_path in job_files:
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                job = Job(**data)
                # Mark running jobs as failed (server restart)
                if job.status == JobStatus.RUNNING:
                    job.status = JobStatus.FAILED
                    job.error = "Server restarted during execution"
                    job.completed_at = datetime.now()
                self._jobs[job.id] = job
            except Exception as e:
                logger.error(f"Failed to load job {file_path}: {e}")

    def _save_job(self, job: Job) -> bool:
        """Save job to disk."""
        try:
            file_path = self.jobs_dir / f"{job.id}.json"
            with open(file_path, "w") as f:
                json.dump(job.model_dump(mode="json"), f, indent=2, default=str)
            return True
        except Exception as e:
            logger.error(f"Failed to save job {job.id}: {e}")
            return False

    def _execute_workflow(self, job_id: str):
        """Execute workflow in background thread."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status == JobStatus.CANCELLED:
                return

            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
            job.progress = "Loading workflow..."
            self._save_job(job)

        try:
            workflow = self.workflow_engine.load_workflow(job.workflow_id)
            if not workflow:
                raise ValueError(f"Workflow {job.workflow_id} not found")

            with self._lock:
                job.progress = "Executing workflow..."
                self._save_job(job)

            if job.variables:
                workflow.variables.update(job.variables)

            result: WorkflowResult = self.workflow_engine.execute_workflow(workflow)

            with self._lock:
                job.status = (
                    JobStatus.COMPLETED
                    if result.status == "completed"
                    else JobStatus.FAILED
                )
                job.result = result.model_dump(mode="json")
                job.completed_at = datetime.now()
                job.progress = None
                if result.errors:
                    job.error = "; ".join(result.errors)
                self._save_job(job)

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            with self._lock:
                job.status = JobStatus.FAILED
                job.error = str(e)
                job.completed_at = datetime.now()
                job.progress = None
                self._save_job(job)

    def submit(self, workflow_id: str, variables: Optional[Dict] = None) -> Job:
        """Submit a workflow for async execution."""
        # Validate workflow exists
        workflow = self.workflow_engine.load_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        job = Job(
            workflow_id=workflow_id,
            variables=variables or {},
        )

        with self._lock:
            self._jobs[job.id] = job
            self._save_job(job)

        future = self.executor.submit(self._execute_workflow, job.id)
        self._futures[job.id] = future

        logger.info(f"Submitted job {job.id} for workflow {workflow_id}")
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        workflow_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Job]:
        """List jobs with optional filtering."""
        jobs = list(self._jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]

        if workflow_id:
            jobs = [j for j in jobs if j.workflow_id == workflow_id]

        # Sort by creation time, newest first
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        return jobs[:limit]

    def cancel(self, job_id: str) -> bool:
        """Cancel a pending or running job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False

            if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
                return False

            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            job.error = "Cancelled by user"
            self._save_job(job)

        # Try to cancel the future (only works if not yet started)
        future = self._futures.get(job_id)
        if future:
            future.cancel()

        logger.info(f"Cancelled job {job_id}")
        return True

    def delete_job(self, job_id: str) -> bool:
        """Delete a completed/failed/cancelled job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False

            # Don't delete running jobs
            if job.status == JobStatus.RUNNING:
                return False

            # Remove from memory
            del self._jobs[job_id]

            # Remove from disk
            file_path = self.jobs_dir / f"{job_id}.json"
            try:
                file_path.unlink()
            except Exception:
                pass

        return True

    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """Remove jobs older than max_age_hours."""
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
        deleted = 0

        with self._lock:
            to_delete = []
            for job_id, job in self._jobs.items():
                if job.status in (
                    JobStatus.COMPLETED,
                    JobStatus.FAILED,
                    JobStatus.CANCELLED,
                ):
                    if job.completed_at and job.completed_at.timestamp() < cutoff:
                        to_delete.append(job_id)

            for job_id in to_delete:
                del self._jobs[job_id]
                file_path = self.jobs_dir / f"{job_id}.json"
                try:
                    file_path.unlink()
                    deleted += 1
                except Exception:
                    pass

        logger.info(f"Cleaned up {deleted} old jobs")
        return deleted

    def shutdown(self, wait: bool = True):
        """Shutdown the executor."""
        self.executor.shutdown(wait=wait)
        logger.info("Job manager shutdown")

    def get_stats(self) -> Dict[str, int]:
        """Get job statistics."""
        stats = {
            "total": len(self._jobs),
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }
        for job in self._jobs.values():
            stats[job.status.value] += 1
        return stats
