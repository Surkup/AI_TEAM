"""
Tests for Temporal Activities

Tests activity functions in isolation (without Temporal).
"""

import pytest
from datetime import datetime

pytestmark = pytest.mark.asyncio(loop_scope="function")

from src.orchestrator.temporal.activities import (
    _parse_process_card_impl,
    _execute_step_impl,
    _run_planning_meeting_impl,
    _run_quality_check_impl,
)


class TestParseProcessCard:
    """Tests for parse_process_card activity."""

    @pytest.mark.asyncio
    async def test_parse_returns_dict(self):
        """Activity returns dictionary with card info."""
        result = await _parse_process_card_impl("card-001")

        assert isinstance(result, dict)
        assert result["id"] == "card-001"
        assert "name" in result
        assert "version" in result
        assert "steps" in result
        assert "parsed_at" in result

    @pytest.mark.asyncio
    async def test_parse_includes_timestamp(self):
        """Activity includes parsing timestamp."""
        result = await _parse_process_card_impl("card-002")

        # Verify timestamp is valid ISO format
        parsed_at = result["parsed_at"]
        datetime.fromisoformat(parsed_at)  # Should not raise


class TestExecuteStep:
    """Tests for execute_step activity."""

    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        """Activity returns execution result."""
        step = {
            "id": "step-001",
            "action": "generate_article",
            "agent_id": "writer-001",
            "params": {"topic": "AI"},
        }

        result = await _execute_step_impl(step)

        assert result["step_id"] == "step-001"
        assert result["action"] == "generate_article"
        assert result["agent_id"] == "writer-001"
        assert result["status"] == "completed"
        assert "output" in result
        assert "executed_at" in result

    @pytest.mark.asyncio
    async def test_execute_handles_missing_fields(self):
        """Activity handles steps with missing optional fields."""
        step = {"action": "simple_action"}

        result = await _execute_step_impl(step)

        assert result["step_id"] == "unknown"
        assert result["action"] == "simple_action"
        assert result["status"] == "completed"


class TestRunPlanningMeeting:
    """Tests for run_planning_meeting activity."""

    @pytest.mark.asyncio
    async def test_planning_returns_execution_plan(self):
        """Activity returns structured execution plan."""
        card_content = {
            "id": "card-001",
            "name": "Test Card",
            "steps": [
                {"action": "research", "agent": "researcher"},
                {"action": "write", "agent": "writer"},
            ],
        }

        result = await _run_planning_meeting_impl(card_content)

        assert result["card_id"] == "card-001"
        assert result["strategy"] in ["sequential", "parallel"]
        assert len(result["steps"]) == 2
        assert "planned_at" in result

    @pytest.mark.asyncio
    async def test_planning_with_empty_steps(self):
        """Activity handles cards with no steps."""
        card_content = {
            "id": "empty-card",
            "steps": [],
        }

        result = await _run_planning_meeting_impl(card_content)

        assert result["card_id"] == "empty-card"
        assert result["steps"] == []

    @pytest.mark.asyncio
    async def test_planning_step_structure(self):
        """Each planned step has required fields."""
        card_content = {
            "id": "card-002",
            "steps": [{"action": "test_action", "agent": "test-agent"}],
        }

        result = await _run_planning_meeting_impl(card_content)
        step = result["steps"][0]

        assert "id" in step
        assert "action" in step
        assert "agent_id" in step
        assert "params" in step
        assert "type" in step


class TestRunQualityCheck:
    """Tests for run_quality_check activity."""

    @pytest.mark.asyncio
    async def test_quality_check_all_passed(self):
        """Quality check passes when all steps succeeded."""
        results = [
            {"step_id": "step-1", "result": {"status": "completed"}},
            {"step_id": "step-2", "result": {"status": "completed"}},
        ]

        result = await _run_quality_check_impl("card-001", results)

        assert result["passed"] is True
        assert result["total_steps"] == 2
        assert result["failed_steps"] == 0

    @pytest.mark.asyncio
    async def test_quality_check_with_failures(self):
        """Quality check fails when steps failed."""
        results = [
            {"step_id": "step-1", "result": {"status": "completed"}},
            {"step_id": "step-2", "result": {"status": "failed"}},
            {"step_id": "step-3", "result": {"status": "completed"}},
        ]

        result = await _run_quality_check_impl("card-002", results)

        assert result["passed"] is False
        assert result["total_steps"] == 3
        assert result["failed_steps"] == 1

    @pytest.mark.asyncio
    async def test_quality_check_empty_results(self):
        """Quality check handles empty results."""
        result = await _run_quality_check_impl("card-003", [])

        assert result["passed"] is True
        assert result["total_steps"] == 0
        assert result["failed_steps"] == 0
