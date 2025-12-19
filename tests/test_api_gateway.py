#!/usr/bin/env python3
"""
Tests for API Gateway.

Tests the HTTP interface for AI_TEAM.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fastapi.testclient import TestClient

from api_gateway.gateway import create_app, APIGateway, TaskRequest, ProcessRequest


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def gateway():
    """Create a test gateway."""
    return APIGateway()


@pytest.fixture
def client(gateway):
    """Create a test client."""
    app = create_app(gateway)
    return TestClient(app)


# =============================================================================
# Root Endpoint Tests
# =============================================================================

class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root_returns_api_info(self, client):
        """Root endpoint returns API information."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "AI_TEAM API"
        assert "endpoints" in data

    def test_root_lists_endpoints(self, client):
        """Root endpoint lists available endpoints."""
        response = client.get("/")
        data = response.json()
        assert "/tasks" in data["endpoints"].values()
        assert "/status" in data["endpoints"].values()


# =============================================================================
# Task Endpoint Tests
# =============================================================================

class TestTaskEndpoints:
    """Tests for task endpoints."""

    def test_create_task_returns_task_id(self, client):
        """Creating task returns task ID."""
        response = client.post("/tasks", json={
            "description": "Test task",
            "time_budget_seconds": 30
        })
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["description"] == "Test task"

    def test_create_task_executes_process(self, client):
        """Creating task executes the process."""
        response = client.post("/tasks", json={
            "description": "Generate some text",
            "time_budget_seconds": 60
        })
        data = response.json()
        # Task should complete (with DummyAgent)
        assert data["status"] in ["completed", "failed"]

    def test_create_task_with_params(self, client):
        """Creating task with custom params."""
        response = client.post("/tasks", json={
            "description": "Custom task",
            "params": {"prompt": "Hello world"}
        })
        data = response.json()
        assert data["status"] in ["completed", "failed"]

    def test_get_task_by_id(self, client):
        """Get task by ID."""
        # Create task first
        create_response = client.post("/tasks", json={
            "description": "Task to retrieve"
        })
        task_id = create_response.json()["task_id"]

        # Get task
        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id

    def test_get_nonexistent_task_returns_404(self, client):
        """Getting nonexistent task returns 404."""
        response = client.get("/tasks/nonexistent-id")
        assert response.status_code == 404

    def test_list_tasks_returns_all(self, client):
        """List tasks returns all tasks."""
        # Create a few tasks
        client.post("/tasks", json={"description": "Task 1"})
        client.post("/tasks", json={"description": "Task 2"})

        # List tasks
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2


# =============================================================================
# Process Endpoint Tests
# =============================================================================

class TestProcessEndpoints:
    """Tests for process endpoints."""

    def test_execute_process_card(self, client):
        """Execute a process card."""
        response = client.post("/process", json={
            "card_name": "simple_text_generation",
            "input_params": {"prompt": "Test prompt"}
        })
        assert response.status_code == 200
        data = response.json()
        assert data["card_name"] == "simple_text_generation"
        assert data["status"] in ["completed", "failed"]

    def test_execute_nonexistent_card_returns_404(self, client):
        """Executing nonexistent card returns 404."""
        response = client.post("/process", json={
            "card_name": "nonexistent_card",
            "input_params": {}
        })
        assert response.status_code == 404

    def test_list_process_cards(self, client):
        """List available process cards."""
        response = client.get("/cards")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert "simple_text_generation" in data


# =============================================================================
# Status Endpoint Tests
# =============================================================================

class TestStatusEndpoint:
    """Tests for status endpoint."""

    def test_status_returns_healthy(self, client):
        """Status endpoint returns healthy status."""
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_status_shows_orchestrator(self, client):
        """Status shows orchestrator name."""
        response = client.get("/status")
        data = response.json()
        assert "orchestrator" in data

    def test_status_shows_agents(self, client):
        """Status shows registered agents."""
        response = client.get("/status")
        data = response.json()
        assert "agents" in data
        assert isinstance(data["agents"], list)

    def test_status_shows_process_counts(self, client):
        """Status shows process counts."""
        response = client.get("/status")
        data = response.json()
        assert "processes" in data
        assert "total" in data["processes"]

    def test_status_shows_storage(self, client):
        """Status shows storage info."""
        response = client.get("/status")
        data = response.json()
        assert "storage" in data


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for API Gateway."""

    def test_full_task_workflow(self, client):
        """Test complete task workflow: create -> get -> list."""
        # 1. Create task
        create_response = client.post("/tasks", json={
            "description": "Integration test task",
            "time_budget_seconds": 60
        })
        assert create_response.status_code == 200
        task_id = create_response.json()["task_id"]

        # 2. Get task
        get_response = client.get(f"/tasks/{task_id}")
        assert get_response.status_code == 200
        assert get_response.json()["task_id"] == task_id

        # 3. List tasks
        list_response = client.get("/tasks")
        assert list_response.status_code == 200
        task_ids = [t["task_id"] for t in list_response.json()]
        assert task_id in task_ids

    def test_process_card_execution_saves_result(self, client):
        """Process execution saves result to storage."""
        response = client.post("/process", json={
            "card_name": "simple_text_generation",
            "input_params": {"prompt": "Save this result"}
        })
        data = response.json()

        assert data["status"] == "completed"
        assert data["steps_completed"] == 2  # generate + complete

    def test_multiple_concurrent_tasks(self, client):
        """Multiple tasks can be created."""
        responses = []
        for i in range(5):
            response = client.post("/tasks", json={
                "description": f"Concurrent task {i}"
            })
            responses.append(response)

        # All should succeed
        for response in responses:
            assert response.status_code == 200

        # All should have unique IDs
        task_ids = [r.json()["task_id"] for r in responses]
        assert len(set(task_ids)) == 5


# =============================================================================
# Gateway Class Tests
# =============================================================================

class TestAPIGatewayClass:
    """Tests for APIGateway class directly."""

    def test_gateway_initializes(self):
        """Gateway initializes correctly."""
        gateway = APIGateway()
        assert gateway.orchestrator is not None
        assert gateway.orchestrator.storage is not None

    def test_gateway_has_default_agents(self):
        """Gateway registers default agents."""
        gateway = APIGateway()
        agents = gateway.orchestrator._local_agents
        assert "generate_text" in agents
        assert "research" in agents

    def test_gateway_loads_config(self):
        """Gateway loads configuration."""
        gateway = APIGateway()
        assert "port" in gateway.config
        assert "process_cards_dir" in gateway.config


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
