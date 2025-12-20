"""
Temporal Configuration for AI_TEAM Orchestrator

All configuration loaded from environment/config files.
Zero hardcoding principle applied.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TemporalConfig:
    """Temporal connection and workflow configuration."""

    # Connection
    host: str = "localhost"
    port: int = 7233
    namespace: str = "default"

    # Task Queues
    main_task_queue: str = "ai-team-orchestrator"
    agent_task_queue: str = "ai-team-agents"

    # Timeouts (seconds)
    workflow_execution_timeout: int = 3600  # 1 hour max for workflow
    activity_start_to_close_timeout: int = 300  # 5 min per activity
    activity_heartbeat_timeout: int = 30  # heartbeat every 30s

    # Retry Policy
    activity_max_retries: int = 3
    activity_initial_interval: float = 1.0
    activity_backoff_coefficient: float = 2.0
    activity_max_interval: float = 60.0

    @property
    def target(self) -> str:
        """Temporal server address."""
        return f"{self.host}:{self.port}"

    @classmethod
    def from_env(cls) -> "TemporalConfig":
        """Load configuration from environment variables."""
        return cls(
            host=os.getenv("TEMPORAL_HOST", "localhost"),
            port=int(os.getenv("TEMPORAL_PORT", "7233")),
            namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
            main_task_queue=os.getenv("TEMPORAL_MAIN_QUEUE", "ai-team-orchestrator"),
            agent_task_queue=os.getenv("TEMPORAL_AGENT_QUEUE", "ai-team-agents"),
            workflow_execution_timeout=int(os.getenv("TEMPORAL_WORKFLOW_TIMEOUT", "3600")),
            activity_start_to_close_timeout=int(os.getenv("TEMPORAL_ACTIVITY_TIMEOUT", "300")),
            activity_heartbeat_timeout=int(os.getenv("TEMPORAL_HEARTBEAT_TIMEOUT", "30")),
            activity_max_retries=int(os.getenv("TEMPORAL_MAX_RETRIES", "3")),
        )


# Default configuration (can be overridden)
DEFAULT_CONFIG = TemporalConfig.from_env()
