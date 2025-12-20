"""
Temporal Worker for AI_TEAM Orchestrator

The Worker polls Temporal server for tasks and executes:
- Workflows (ProcessCardWorkflow)
- Activities (parse_process_card, execute_step, etc.)

Usage:
    python -m src.orchestrator.temporal.worker

Or programmatically:
    from src.orchestrator.temporal import run_worker
    await run_worker()
"""

import asyncio
import logging
from typing import Optional

from temporalio.client import Client
from temporalio.worker import Worker, UnsandboxedWorkflowRunner

from .config import TemporalConfig, DEFAULT_CONFIG
from .workflows import ProcessCardWorkflow
from .activities import (
    parse_process_card,
    execute_step,
    run_planning_meeting,
    run_quality_check,
)

logger = logging.getLogger(__name__)


async def create_worker(
    client: Client,
    config: Optional[TemporalConfig] = None,
) -> Worker:
    """
    Create a Temporal Worker.

    Args:
        client: Connected Temporal client
        config: Optional configuration (uses default if not provided)

    Returns:
        Configured Worker instance
    """
    config = config or DEFAULT_CONFIG

    # Use UnsandboxedWorkflowRunner because parent orchestrator package
    # contains datetime.utcnow which conflicts with Temporal sandbox.
    # This is safe because our workflows are deterministic.
    worker = Worker(
        client,
        task_queue=config.main_task_queue,
        workflows=[ProcessCardWorkflow],
        activities=[
            parse_process_card,
            execute_step,
            run_planning_meeting,
            run_quality_check,
        ],
        workflow_runner=UnsandboxedWorkflowRunner(),
    )

    return worker


async def run_worker(config: Optional[TemporalConfig] = None) -> None:
    """
    Run the Temporal Worker (blocking).

    This connects to Temporal server and starts polling for tasks.
    Runs until interrupted (Ctrl+C).

    Args:
        config: Optional configuration
    """
    config = config or DEFAULT_CONFIG

    logger.info(f"Connecting to Temporal at {config.target}...")

    client = await Client.connect(
        config.target,
        namespace=config.namespace,
    )

    logger.info(f"Connected. Starting worker on queue '{config.main_task_queue}'...")

    worker = await create_worker(client, config)

    try:
        await worker.run()
    except asyncio.CancelledError:
        logger.info("Worker cancelled, shutting down...")
    finally:
        logger.info("Worker stopped.")


def main():
    """Entry point for running worker from command line."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        print("\nWorker interrupted by user.")


if __name__ == "__main__":
    main()
