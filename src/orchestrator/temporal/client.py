"""
Temporal Client for AI_TEAM Orchestrator

Provides connection to Temporal server and workflow management.
"""

import asyncio
from typing import Optional, Any
from datetime import timedelta

from temporalio.client import Client, WorkflowHandle
from temporalio.common import RetryPolicy

from .config import TemporalConfig, DEFAULT_CONFIG


class TemporalClient:
    """
    Temporal client wrapper for AI_TEAM.

    Usage:
        async with TemporalClient() as client:
            handle = await client.start_process_card(card_id="card-123")
            result = await handle.result()
    """

    def __init__(self, config: Optional[TemporalConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self._client: Optional[Client] = None

    async def connect(self) -> "TemporalClient":
        """Connect to Temporal server."""
        self._client = await Client.connect(
            self.config.target,
            namespace=self.config.namespace,
        )
        return self

    async def close(self) -> None:
        """Close connection (no-op for now, client handles cleanup)."""
        pass

    async def __aenter__(self) -> "TemporalClient":
        return await self.connect()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    @property
    def client(self) -> Client:
        """Get underlying Temporal client."""
        if self._client is None:
            raise RuntimeError("Client not connected. Use 'async with TemporalClient()' or call connect()")
        return self._client

    async def start_process_card(
        self,
        card_id: str,
        card_content: Optional[dict] = None,
        *,
        workflow_id: Optional[str] = None,
    ) -> WorkflowHandle:
        """
        Start ProcessCardWorkflow for a given card.

        Args:
            card_id: Process card identifier
            card_content: Optional parsed card content (if not provided, will be loaded)
            workflow_id: Optional custom workflow ID (defaults to card_id)

        Returns:
            WorkflowHandle for tracking and querying the workflow
        """
        from .workflows import ProcessCardWorkflow

        wf_id = workflow_id or f"process-card-{card_id}"

        handle = await self.client.start_workflow(
            ProcessCardWorkflow.run,
            args=[card_id, card_content],
            id=wf_id,
            task_queue=self.config.main_task_queue,
            execution_timeout=timedelta(seconds=self.config.workflow_execution_timeout),
            retry_policy=RetryPolicy(
                maximum_attempts=1,  # Workflows should not auto-retry
            ),
        )
        return handle

    async def get_workflow_status(self, workflow_id: str) -> dict:
        """
        Get status of a running workflow.

        Returns:
            Dict with workflow status information
        """
        handle = self.client.get_workflow_handle(workflow_id)
        desc = await handle.describe()
        return {
            "workflow_id": workflow_id,
            "status": desc.status.name,
            "start_time": desc.start_time.isoformat() if desc.start_time else None,
            "close_time": desc.close_time.isoformat() if desc.close_time else None,
        }

    async def cancel_workflow(self, workflow_id: str) -> None:
        """Cancel a running workflow."""
        handle = self.client.get_workflow_handle(workflow_id)
        await handle.cancel()

    async def signal_workflow(self, workflow_id: str, signal_name: str, *args: Any) -> None:
        """Send a signal to a running workflow."""
        handle = self.client.get_workflow_handle(workflow_id)
        await handle.signal(signal_name, *args)


async def get_client(config: Optional[TemporalConfig] = None) -> TemporalClient:
    """
    Factory function to get connected Temporal client.

    Usage:
        client = await get_client()
        handle = await client.start_process_card("card-123")
    """
    client = TemporalClient(config)
    return await client.connect()
