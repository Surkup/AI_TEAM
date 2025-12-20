"""
Temporal Workflows for AI_TEAM Orchestrator

Main workflow: ProcessCardWorkflow
- Parses Process Card YAML
- Executes steps sequentially or in parallel
- Handles subprocesses via Child Workflows
- Integrates with LangGraph for AI decisions

Architecture: LangGraph runs INSIDE Temporal Activity
"""

from datetime import timedelta
from typing import Optional, List, Dict, Any

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activity stubs (will be implemented in activities.py)
with workflow.unsafe.imports_passed_through():
    from .activities import (
        parse_process_card,
        execute_step,
        run_planning_meeting,
        run_quality_check,
    )


@workflow.defn
class ProcessCardWorkflow:
    """
    Main workflow for executing Process Cards.

    Responsibilities:
    1. Parse Process Card (YAML → structured steps)
    2. Execute each step via Activities
    3. Handle parallel steps (gather)
    4. Handle subprocesses (child workflows)
    5. Run quality checks after execution

    Signals:
    - pause: Pause execution
    - resume: Resume execution
    - cancel: Cancel workflow

    Queries:
    - status: Get current execution status
    - current_step: Get currently executing step
    """

    def __init__(self) -> None:
        self._is_paused = False
        self._current_step: Optional[str] = None
        self._completed_steps: List[str] = []
        self._status = "initialized"

    @workflow.run
    async def run(
        self,
        card_id: str,
        card_content: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a Process Card.

        Args:
            card_id: Process card identifier
            card_content: Optional pre-parsed card content

        Returns:
            Execution result with status and outputs
        """
        self._status = "running"

        # Retry policy for activities
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=60),
            maximum_attempts=3,
        )

        # Step 1: Parse Process Card (if not provided)
        if card_content is None:
            self._current_step = "parse_card"
            card_content = await workflow.execute_activity(
                parse_process_card,
                args=[card_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )
            self._completed_steps.append("parse_card")

        # Step 2: Run Planning Meeting (LangGraph inside Activity)
        self._current_step = "planning"
        execution_plan = await workflow.execute_activity(
            run_planning_meeting,
            args=[card_content],
            start_to_close_timeout=timedelta(seconds=120),
            heartbeat_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )
        self._completed_steps.append("planning")

        # Step 3: Execute each step
        steps = execution_plan.get("steps", [])
        results = []

        for step in steps:
            # Check for pause signal
            await workflow.wait_condition(lambda: not self._is_paused)

            step_id = step.get("id", "unknown")
            self._current_step = step_id

            # Check if this is a subprocess (child workflow)
            if step.get("type") == "subprocess":
                # Execute as child workflow
                result = await workflow.execute_child_workflow(
                    ProcessCardWorkflow.run,
                    args=[step["subprocess_card_id"], None],
                    id=f"{workflow.info().workflow_id}-{step_id}",
                )
            else:
                # Execute as activity
                result = await workflow.execute_activity(
                    execute_step,
                    args=[step],
                    start_to_close_timeout=timedelta(seconds=300),
                    heartbeat_timeout=timedelta(seconds=30),
                    retry_policy=retry_policy,
                )

            results.append({"step_id": step_id, "result": result})
            self._completed_steps.append(step_id)

        # Step 4: Quality Check
        self._current_step = "quality_check"
        quality_result = await workflow.execute_activity(
            run_quality_check,
            args=[card_id, results],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry_policy,
        )
        self._completed_steps.append("quality_check")

        self._status = "completed"
        self._current_step = None

        return {
            "card_id": card_id,
            "status": "success" if quality_result.get("passed") else "failed",
            "steps_completed": len(results),
            "quality_check": quality_result,
            "results": results,
        }

    @workflow.signal
    async def pause(self) -> None:
        """Pause workflow execution."""
        self._is_paused = True
        self._status = "paused"

    @workflow.signal
    async def resume(self) -> None:
        """Resume workflow execution."""
        self._is_paused = False
        self._status = "running"

    @workflow.query
    def status(self) -> Dict[str, Any]:
        """Get current workflow status."""
        return {
            "status": self._status,
            "current_step": self._current_step,
            "completed_steps": self._completed_steps,
            "is_paused": self._is_paused,
        }

    @workflow.query
    def current_step(self) -> Optional[str]:
        """Get currently executing step."""
        return self._current_step
