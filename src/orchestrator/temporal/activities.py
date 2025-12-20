"""
Temporal Activities for AI_TEAM Orchestrator

Activities are the "work units" that run actual logic:
- parse_process_card: Load and parse YAML card
- execute_step: Execute a single step via MindBus
- run_planning_meeting: LangGraph-based planning (AI logic)
- run_quality_check: LangGraph-based quality assessment

Key principle: LangGraph runs INSIDE Activity, not vice versa.

Architecture:
- _impl functions: Pure business logic (testable without Temporal)
- @activity.defn functions: Temporal wrappers with heartbeats
"""

from typing import Dict, Any, List
from datetime import datetime

from temporalio import activity


# =============================================================================
# Pure Implementation Functions (for testing)
# =============================================================================

async def _parse_process_card_impl(card_id: str) -> Dict[str, Any]:
    """
    Pure implementation of parse_process_card.

    Args:
        card_id: Process card identifier

    Returns:
        Parsed card content as dictionary
    """
    # TODO: Integrate with Storage layer
    # For now, return mock structure
    return {
        "id": card_id,
        "name": f"Process Card {card_id}",
        "version": "1.0",
        "steps": [],
        "parsed_at": datetime.utcnow().isoformat(),
    }


async def _execute_step_impl(
    step: Dict[str, Any],
    use_mindbus: bool = False,
) -> Dict[str, Any]:
    """
    Pure implementation of execute_step.

    Args:
        step: Step definition with action, agent, params
        use_mindbus: If True, send real command via MindBus

    Returns:
        Step execution result
    """
    step_id = step.get("id", "unknown")
    action = step.get("action", "unknown")
    agent_role = step.get("agent_id", "default-agent")
    params = step.get("params", {})

    if use_mindbus:
        # Real MindBus integration
        try:
            from src.mindbus.core import MindBus

            bus = MindBus()
            bus.connect()

            # Send command to agent
            event_id = bus.send_command(
                action=action,
                params=params,
                target=agent_role,
                source="temporal-orchestrator",
                subject=step_id,
            )

            # TODO: Wait for RESULT message (need async RPC pattern)
            # For now, just send command and return success
            bus.disconnect()

            return {
                "step_id": step_id,
                "action": action,
                "agent_id": agent_role,
                "event_id": event_id,
                "status": "sent",
                "output": f"Command sent to {agent_role}",
                "executed_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {
                "step_id": step_id,
                "action": action,
                "agent_id": agent_role,
                "status": "failed",
                "error": str(e),
                "executed_at": datetime.utcnow().isoformat(),
            }
    else:
        # Mock mode for testing
        return {
            "step_id": step_id,
            "action": action,
            "agent_id": agent_role,
            "status": "completed",
            "output": f"Mock output for {action}",
            "executed_at": datetime.utcnow().isoformat(),
        }


async def _run_planning_meeting_impl(card_content: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure implementation of run_planning_meeting.

    Args:
        card_content: Parsed Process Card

    Returns:
        Execution plan with steps and assignments
    """
    # TODO: Integrate with LangGraph planning graph
    # For now, return mock plan

    steps = card_content.get("steps", [])

    # Create execution plan
    execution_plan = {
        "card_id": card_content.get("id"),
        "strategy": "sequential",  # or "parallel"
        "steps": [
            {
                "id": f"step_{i}",
                "action": step.get("action", "default"),
                "agent_id": step.get("agent", "default-agent"),
                "params": step.get("params", {}),
                "type": step.get("type", "action"),
            }
            for i, step in enumerate(steps)
        ],
        "planned_at": datetime.utcnow().isoformat(),
    }

    return execution_plan


async def _run_quality_check_impl(
    card_id: str,
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Pure implementation of run_quality_check.

    Args:
        card_id: Process card identifier
        results: List of step execution results

    Returns:
        Quality check result with pass/fail status
    """
    # TODO: Integrate with LangGraph quality check graph
    # For now, simple pass/fail logic

    failed_steps = [
        r for r in results
        if r.get("result", {}).get("status") == "failed"
    ]

    return {
        "card_id": card_id,
        "passed": len(failed_steps) == 0,
        "total_steps": len(results),
        "failed_steps": len(failed_steps),
        "checked_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# Temporal Activity Wrappers (with heartbeats)
# =============================================================================

@activity.defn
async def parse_process_card(card_id: str) -> Dict[str, Any]:
    """
    Parse a Process Card from storage.

    Temporal wrapper with heartbeat support.
    """
    activity.heartbeat()
    return await _parse_process_card_impl(card_id)


@activity.defn
async def execute_step(step: Dict[str, Any], use_mindbus: bool = False) -> Dict[str, Any]:
    """
    Execute a single step via MindBus.

    Temporal wrapper with heartbeat support.

    Args:
        step: Step definition
        use_mindbus: If True, send real command via MindBus
    """
    activity.heartbeat()
    result = await _execute_step_impl(step, use_mindbus=use_mindbus)
    activity.heartbeat()
    return result


@activity.defn
async def run_planning_meeting(card_content: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run LangGraph-based planning meeting.

    Temporal wrapper with heartbeat support.
    """
    activity.heartbeat()
    result = await _run_planning_meeting_impl(card_content)
    activity.heartbeat()
    return result


@activity.defn
async def run_quality_check(
    card_id: str,
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Run LangGraph-based quality check.

    Temporal wrapper with heartbeat support.
    """
    activity.heartbeat()
    return await _run_quality_check_impl(card_id, results)
