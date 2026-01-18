"""Tests for the state persistence module."""

import pytest
import tempfile
import os
import sys
sys.path.insert(0, 'src')

from test_ai.state import StatePersistence, WorkflowStatus, CheckpointManager


class TestStatePersistence:
    """Tests for StatePersistence class."""

    @pytest.fixture
    def persistence(self):
        """Create a temporary persistence instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            yield StatePersistence(db_path)

    def test_create_workflow(self, persistence):
        """Can create a workflow."""
        persistence.create_workflow("wf-1", "Test Workflow", {"key": "value"})
        workflow = persistence.get_workflow("wf-1")
        assert workflow is not None
        assert workflow["name"] == "Test Workflow"
        assert workflow["status"] == "pending"
        assert workflow["config"]["key"] == "value"

    def test_update_status(self, persistence):
        """Can update workflow status."""
        persistence.create_workflow("wf-1", "Test")
        persistence.update_status("wf-1", WorkflowStatus.RUNNING)
        workflow = persistence.get_workflow("wf-1")
        assert workflow["status"] == "running"

    def test_checkpoint(self, persistence):
        """Can create checkpoints."""
        persistence.create_workflow("wf-1", "Test")
        cp_id = persistence.checkpoint(
            workflow_id="wf-1",
            stage="planning",
            status="success",
            input_data={"task": "test"},
            output_data={"plan": "..."},
            tokens_used=100,
            duration_ms=500,
        )
        assert cp_id > 0

        checkpoint = persistence.get_last_checkpoint("wf-1")
        assert checkpoint["stage"] == "planning"
        assert checkpoint["tokens_used"] == 100

    def test_get_all_checkpoints(self, persistence):
        """Can get all checkpoints for a workflow."""
        persistence.create_workflow("wf-1", "Test")
        persistence.checkpoint("wf-1", "step1", "success")
        persistence.checkpoint("wf-1", "step2", "success")
        persistence.checkpoint("wf-1", "step3", "failed")

        checkpoints = persistence.get_all_checkpoints("wf-1")
        assert len(checkpoints) == 3
        stages = [cp["stage"] for cp in checkpoints]
        assert "step1" in stages
        assert "step2" in stages
        assert "step3" in stages

    def test_resumable_workflows(self, persistence):
        """Can find resumable workflows."""
        persistence.create_workflow("wf-1", "Running")
        persistence.update_status("wf-1", WorkflowStatus.RUNNING)

        persistence.create_workflow("wf-2", "Completed")
        persistence.update_status("wf-2", WorkflowStatus.COMPLETED)

        persistence.create_workflow("wf-3", "Failed")
        persistence.update_status("wf-3", WorkflowStatus.FAILED)

        resumable = persistence.get_resumable_workflows()
        ids = [w["id"] for w in resumable]
        assert "wf-1" in ids
        assert "wf-3" in ids
        assert "wf-2" not in ids

    def test_resume_from_checkpoint(self, persistence):
        """Can resume from checkpoint."""
        persistence.create_workflow("wf-1", "Test")
        persistence.checkpoint("wf-1", "step1", "success", output_data={"result": "ok"})
        persistence.update_status("wf-1", WorkflowStatus.PAUSED)

        checkpoint = persistence.resume_from_checkpoint("wf-1")
        assert checkpoint["stage"] == "step1"

        workflow = persistence.get_workflow("wf-1")
        assert workflow["status"] == "running"

    def test_mark_complete(self, persistence):
        """Can mark workflow complete."""
        persistence.create_workflow("wf-1", "Test")
        persistence.mark_complete("wf-1")
        workflow = persistence.get_workflow("wf-1")
        assert workflow["status"] == "completed"

    def test_mark_failed(self, persistence):
        """Can mark workflow failed with error."""
        persistence.create_workflow("wf-1", "Test")
        persistence.mark_failed("wf-1", "Something went wrong")
        workflow = persistence.get_workflow("wf-1")
        assert workflow["status"] == "failed"
        assert workflow["error"] == "Something went wrong"

    def test_delete_workflow(self, persistence):
        """Can delete workflow and checkpoints."""
        persistence.create_workflow("wf-1", "Test")
        persistence.checkpoint("wf-1", "step1", "success")

        result = persistence.delete_workflow("wf-1")
        assert result is True

        workflow = persistence.get_workflow("wf-1")
        assert workflow is None

    def test_get_stats(self, persistence):
        """Can get persistence statistics."""
        persistence.create_workflow("wf-1", "Test")
        persistence.checkpoint("wf-1", "step1", "success")
        # Set status after checkpoint since checkpoint sets to RUNNING
        persistence.update_status("wf-1", WorkflowStatus.COMPLETED)

        stats = persistence.get_stats()
        assert stats["total_workflows"] == 1
        assert stats["by_status"]["completed"] == 1
        assert stats["total_checkpoints"] == 1


class TestCheckpointManager:
    """Tests for CheckpointManager class."""

    @pytest.fixture
    def manager(self):
        """Create a temporary checkpoint manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            yield CheckpointManager(db_path=db_path)

    def test_start_workflow(self, manager):
        """Can start a workflow."""
        wf_id = manager.start_workflow("Test Workflow", {"config": "value"})
        assert wf_id.startswith("wf-")
        assert manager.current_workflow_id == wf_id

    def test_complete_workflow(self, manager):
        """Can complete a workflow."""
        wf_id = manager.start_workflow("Test")
        manager.complete_workflow()
        assert manager.current_workflow_id is None

        workflow = manager.persistence.get_workflow(wf_id)
        assert workflow["status"] == "completed"

    def test_fail_workflow(self, manager):
        """Can fail a workflow."""
        wf_id = manager.start_workflow("Test")
        manager.fail_workflow("Error occurred")
        assert manager.current_workflow_id is None

        workflow = manager.persistence.get_workflow(wf_id)
        assert workflow["status"] == "failed"
        assert workflow["error"] == "Error occurred"

    def test_workflow_context_manager(self, manager):
        """Workflow context manager handles success."""
        with manager.workflow("Test Workflow") as wf_id:
            assert wf_id is not None
            assert manager.current_workflow_id == wf_id

        workflow = manager.persistence.get_workflow(wf_id)
        assert workflow["status"] == "completed"

    def test_workflow_context_manager_failure(self, manager):
        """Workflow context manager handles failure."""
        with pytest.raises(ValueError):
            with manager.workflow("Test") as wf_id:
                raise ValueError("Test error")

        workflow = manager.persistence.get_workflow(wf_id)
        assert workflow["status"] == "failed"

    def test_stage_context_manager(self, manager):
        """Stage context manager creates checkpoints."""
        manager.start_workflow("Test")

        with manager.stage("planning", {"task": "test"}) as ctx:
            ctx.output_data = {"plan": "..."}
            ctx.tokens_used = 100

        checkpoints = manager.persistence.get_all_checkpoints(manager.current_workflow_id)
        assert len(checkpoints) == 1
        assert checkpoints[0]["stage"] == "planning"
        assert checkpoints[0]["tokens_used"] == 100

    def test_stage_without_workflow_raises(self, manager):
        """Stage without active workflow raises."""
        with pytest.raises(ValueError):
            with manager.stage("test"):
                pass

    def test_checkpoint_now(self, manager):
        """Can create immediate checkpoint."""
        manager.start_workflow("Test")
        cp_id = manager.checkpoint_now(
            stage="manual",
            status="success",
            tokens_used=50,
        )
        assert cp_id > 0

    def test_resume(self, manager):
        """Can resume a workflow."""
        wf_id = manager.start_workflow("Test")
        with manager.stage("step1") as ctx:
            ctx.output_data = {"result": "step1"}

        manager.persistence.update_status(wf_id, WorkflowStatus.PAUSED)
        manager._current_workflow = None

        resume_data = manager.resume(wf_id)
        assert resume_data["resume_from_stage"] == "step1"
        assert manager.current_workflow_id == wf_id

    def test_get_progress(self, manager):
        """Can get workflow progress."""
        manager.start_workflow("Test")

        with manager.stage("step1") as ctx:
            ctx.tokens_used = 50

        with manager.stage("step2") as ctx:
            ctx.tokens_used = 75

        progress = manager.get_progress()
        assert len(progress["stages_completed"]) == 2
        assert progress["total_tokens"] == 125
        assert progress["total_checkpoints"] == 2
