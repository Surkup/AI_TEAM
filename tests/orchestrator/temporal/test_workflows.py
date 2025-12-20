"""
Tests for Temporal Workflows

Uses Temporal's test environment for deterministic testing.
No actual Temporal server required.
"""

import pytest
from datetime import timedelta

from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from src.orchestrator.temporal.workflows import ProcessCardWorkflow
from src.orchestrator.temporal.activities import (
    parse_process_card,
    execute_step,
    run_planning_meeting,
    run_quality_check,
)


@pytest.fixture
async def workflow_env():
    """Create Temporal test environment."""
    async with await WorkflowEnvironment.start_local() as env:
        yield env


@pytest.fixture
async def worker(workflow_env):
    """Create worker with workflows and activities."""
    async with Worker(
        workflow_env.client,
        task_queue="test-queue",
        workflows=[ProcessCardWorkflow],
        activities=[
            parse_process_card,
            execute_step,
            run_planning_meeting,
            run_quality_check,
        ],
    ):
        yield


@pytest.mark.asyncio
async def test_process_card_workflow_basic(workflow_env, worker):
    """Test basic workflow execution with empty card."""
    result = await workflow_env.client.execute_workflow(
        ProcessCardWorkflow.run,
        args=["test-card-001", None],
        id="test-workflow-001",
        task_queue="test-queue",
        execution_timeout=timedelta(seconds=60),
    )

    assert result["card_id"] == "test-card-001"
    assert result["status"] == "success"
    assert "steps_completed" in result
    assert result["quality_check"]["passed"] is True


@pytest.mark.asyncio
async def test_process_card_workflow_with_content(workflow_env, worker):
    """Test workflow with pre-parsed card content."""
    card_content = {
        "id": "test-card-002",
        "name": "Test Process",
        "version": "1.0",
        "steps": [
            {"action": "research", "agent": "researcher"},
            {"action": "write", "agent": "writer"},
        ],
    }

    result = await workflow_env.client.execute_workflow(
        ProcessCardWorkflow.run,
        args=["test-card-002", card_content],
        id="test-workflow-002",
        task_queue="test-queue",
        execution_timeout=timedelta(seconds=60),
    )

    assert result["card_id"] == "test-card-002"
    assert result["status"] == "success"
    assert result["steps_completed"] == 2


@pytest.mark.asyncio
async def test_workflow_status_query(workflow_env, worker):
    """Test querying workflow status."""
    handle = await workflow_env.client.start_workflow(
        ProcessCardWorkflow.run,
        args=["test-card-003", {"id": "test-card-003", "steps": []}],
        id="test-workflow-003",
        task_queue="test-queue",
        execution_timeout=timedelta(seconds=60),
    )

    # Wait for completion
    await handle.result()

    # Query final status
    status = await handle.query(ProcessCardWorkflow.status)
    assert status["status"] == "completed"
    assert "planning" in status["completed_steps"]


@pytest.mark.asyncio
async def test_workflow_pause_resume(workflow_env, worker):
    """Test pause/resume signals."""
    card_content = {
        "id": "test-card-004",
        "steps": [
            {"action": "step1"},
            {"action": "step2"},
            {"action": "step3"},
        ],
    }

    handle = await workflow_env.client.start_workflow(
        ProcessCardWorkflow.run,
        args=["test-card-004", card_content],
        id="test-workflow-004",
        task_queue="test-queue",
        execution_timeout=timedelta(seconds=60),
    )

    # Let workflow start
    await workflow_env.sleep(timedelta(milliseconds=100))

    # Send pause signal
    await handle.signal(ProcessCardWorkflow.pause)

    # Query status - should be paused
    status = await handle.query(ProcessCardWorkflow.status)
    assert status["is_paused"] is True

    # Resume
    await handle.signal(ProcessCardWorkflow.resume)

    # Wait for completion
    result = await handle.result()
    assert result["status"] == "success"
