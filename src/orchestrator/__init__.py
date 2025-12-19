"""
AI_TEAM Orchestrator Module.

The Orchestrator is the "brain" of AI_TEAM:
- Receives tasks from users
- Finds suitable agents via Node Registry
- Sends commands via MindBus
- Collects results and stores in Storage

See: docs/SSOT/PROCESS_CARD_SPEC_v1.0.md
"""

from .models import ProcessCard, StepSpec, ProcessMetadata, ProcessInstance, ProcessStatus
from .simple_orchestrator import SimpleOrchestrator
from .integrated_orchestrator import IntegratedOrchestrator, run_process

__all__ = [
    "ProcessCard",
    "StepSpec",
    "ProcessMetadata",
    "ProcessInstance",
    "ProcessStatus",
    "SimpleOrchestrator",
    "IntegratedOrchestrator",
    "run_process",
]
