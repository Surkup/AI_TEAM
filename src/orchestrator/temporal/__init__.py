"""
Temporal-based Orchestrator for AI_TEAM

Architecture (ORCHESTRATOR_SPEC_v2.1):
- Execution Layer: Temporal (durable execution, event sourcing)
- Intelligence Layer: LangGraph (AI logic, planning, meetings)
- Transport Layer: MindBus/AMQP (agent communication)

Key principle: LangGraph runs INSIDE Temporal Activity (not vice versa)

IMPORTANT: This module is isolated from parent orchestrator package
to avoid Temporal sandbox restrictions on datetime.utcnow.
"""

# Only export what's needed - avoid importing from parent package
from .config import TemporalConfig, DEFAULT_CONFIG

__all__ = [
    "TemporalConfig",
    "DEFAULT_CONFIG",
]
