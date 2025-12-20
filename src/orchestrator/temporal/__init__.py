"""
Temporal-based Orchestrator for AI_TEAM

Architecture (ORCHESTRATOR_SPEC_v2.1):
- Execution Layer: Temporal (durable execution, event sourcing)
- Intelligence Layer: LangGraph (AI logic, planning, meetings)
- Transport Layer: MindBus/AMQP (agent communication)

Key principle: LangGraph runs INSIDE Temporal Activity (not vice versa)
"""

from .workflows import ProcessCardWorkflow
from .activities import (
    parse_process_card,
    execute_step,
    run_planning_meeting,
    run_quality_check,
)
from .worker import create_worker, run_worker
from .client import TemporalClient

__all__ = [
    # Workflows
    "ProcessCardWorkflow",
    # Activities
    "parse_process_card",
    "execute_step",
    "run_planning_meeting",
    "run_quality_check",
    # Infrastructure
    "create_worker",
    "run_worker",
    "TemporalClient",
]
