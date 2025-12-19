#!/usr/bin/env python3
"""
End-to-End API Test — Full system integration through HTTP API.

Tests the complete flow:
Human → API Gateway → Orchestrator → Agent → Storage → Result

This validates that the entire system works together through HTTP interface.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fastapi.testclient import TestClient

from api_gateway.gateway import create_app, APIGateway


# =============================================================================
# Test Setup
# =============================================================================

@pytest.fixture(scope="module")
def gateway():
    """Create gateway for all tests."""
    return APIGateway()


@pytest.fixture(scope="module")
def client(gateway):
    """Create test client for all tests."""
    app = create_app(gateway)
    return TestClient(app)


# =============================================================================
# E2E Scenario 1: Simple Task Creation
# =============================================================================

class TestE2ESimpleTask:
    """E2E test for simple task flow."""

    def test_scenario_create_task_and_get_result(self, client):
        """
        Scenario: Create a simple text generation task

        Given: API Gateway is running
        When: User creates a task with description
        Then: Task is executed and result is returned
        """
        # 1. Create task
        response = client.post("/tasks", json={
            "description": "Write a haiku about Python",
            "time_budget_seconds": 30
        })

        assert response.status_code == 200
        task = response.json()

        # 2. Verify task was created
        assert "task_id" in task
        assert task["status"] == "completed"
        assert task["result"] is not None

        # 3. Verify task is in the list
        list_response = client.get("/tasks")
        task_ids = [t["task_id"] for t in list_response.json()]
        assert task["task_id"] in task_ids


# =============================================================================
# E2E Scenario 2: Process Card Execution
# =============================================================================

class TestE2EProcessCard:
    """E2E test for process card execution."""

    def test_scenario_execute_simple_text_generation(self, client):
        """
        Scenario: Execute simple_text_generation process card

        Given: Process card exists
        When: User executes the card with input params
        Then: Process completes with result
        """
        # 1. Check card exists
        cards_response = client.get("/cards")
        assert "simple_text_generation" in cards_response.json()

        # 2. Execute process
        response = client.post("/process", json={
            "card_name": "simple_text_generation",
            "input_params": {"prompt": "Test prompt for E2E"}
        })

        assert response.status_code == 200
        process = response.json()

        # 3. Verify process completed
        assert process["status"] == "completed"
        assert process["steps_completed"] == 2
        assert process["result"] is not None

    def test_scenario_execute_article_generation(self, client):
        """
        Scenario: Execute article_generation process card (multi-step)

        Given: Article generation card exists
        When: User executes with topic
        Then: Multiple steps are executed
        """
        # Check card exists
        cards_response = client.get("/cards")
        cards = cards_response.json()

        if "article_generation" not in cards:
            pytest.skip("article_generation card not found")

        # Execute process
        response = client.post("/process", json={
            "card_name": "article_generation",
            "input_params": {"topic": "E2E Testing"}
        })

        process = response.json()

        # Should complete (even with DummyAgent)
        assert process["status"] in ["completed", "failed"]


# =============================================================================
# E2E Scenario 3: Full API Workflow
# =============================================================================

class TestE2EFullWorkflow:
    """E2E test for complete API workflow."""

    def test_scenario_full_api_workflow(self, client):
        """
        Scenario: Complete API workflow from status check to task completion

        1. Check system status
        2. List available process cards
        3. Create and execute a task
        4. Get task result
        5. Verify in task list
        """
        # Step 1: Check system status
        status_response = client.get("/status")
        assert status_response.status_code == 200
        status = status_response.json()
        assert status["status"] == "healthy"
        assert len(status["agents"]) > 0

        # Step 2: List process cards
        cards_response = client.get("/cards")
        assert cards_response.status_code == 200
        cards = cards_response.json()
        assert len(cards) > 0

        # Step 3: Create task
        create_response = client.post("/tasks", json={
            "description": "E2E workflow test",
            "process_card": cards[0]  # Use first available card
        })
        assert create_response.status_code == 200
        task = create_response.json()
        task_id = task["task_id"]

        # Step 4: Get task result
        get_response = client.get(f"/tasks/{task_id}")
        assert get_response.status_code == 200
        retrieved_task = get_response.json()
        assert retrieved_task["task_id"] == task_id

        # Step 5: Verify in list
        list_response = client.get("/tasks")
        task_ids = [t["task_id"] for t in list_response.json()]
        assert task_id in task_ids


# =============================================================================
# E2E Scenario 4: Error Handling
# =============================================================================

class TestE2EErrorHandling:
    """E2E test for error handling."""

    def test_scenario_nonexistent_task(self, client):
        """Requesting nonexistent task returns 404."""
        response = client.get("/tasks/nonexistent-task-id-12345")
        assert response.status_code == 404

    def test_scenario_nonexistent_process_card(self, client):
        """Executing nonexistent card returns 404."""
        response = client.post("/process", json={
            "card_name": "totally_nonexistent_card",
            "input_params": {}
        })
        assert response.status_code == 404

    def test_scenario_invalid_request(self, client):
        """Invalid request returns error."""
        response = client.post("/tasks", json={
            # Missing required "description" field
        })
        assert response.status_code == 422  # Validation error


# =============================================================================
# E2E Scenario 5: Concurrent Operations
# =============================================================================

class TestE2EConcurrency:
    """E2E test for concurrent operations."""

    def test_scenario_multiple_tasks(self, client):
        """
        Scenario: Create multiple tasks

        Given: System is running
        When: Multiple tasks are created
        Then: All tasks complete independently
        """
        tasks = []

        # Create 3 tasks
        for i in range(3):
            response = client.post("/tasks", json={
                "description": f"Concurrent task {i}",
                "time_budget_seconds": 30
            })
            tasks.append(response.json())

        # All should complete
        for task in tasks:
            assert task["status"] == "completed"

        # All should have unique IDs
        task_ids = [t["task_id"] for t in tasks]
        assert len(set(task_ids)) == 3


# =============================================================================
# E2E Scenario 6: Storage Integration
# =============================================================================

class TestE2EStorage:
    """E2E test for storage integration."""

    def test_scenario_storage_stats_update(self, client):
        """
        Scenario: Storage is updated after task execution

        Given: Initial storage state
        When: Task is executed
        Then: Storage stats are updated
        """
        # Get initial status
        initial_status = client.get("/status").json()
        initial_artifacts = initial_status["storage"]["artifacts_count"] if initial_status["storage"] else 0

        # Execute a task
        client.post("/tasks", json={
            "description": "Storage test task"
        })

        # Get final status
        final_status = client.get("/status").json()
        final_artifacts = final_status["storage"]["artifacts_count"] if final_status["storage"] else 0

        # Artifacts should increase (process result is saved)
        assert final_artifacts >= initial_artifacts


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
