"""
API Gateway — HTTP interface for AI_TEAM.

Provides REST API endpoints for:
- POST /tasks — create a new task
- GET /tasks/{task_id} — get task status
- GET /tasks — list all tasks
- POST /process — execute a process card
- GET /status — system status
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.orchestrator.integrated_orchestrator import IntegratedOrchestrator
from src.orchestrator.models import ProcessStatus
from src.agents.dummy_agent import DummyAgent

logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================

class TaskRequest(BaseModel):
    """Request to create a new task."""
    description: str = Field(..., description="Task description/prompt")
    time_budget_seconds: int = Field(default=60, description="Maximum execution time")
    process_card: Optional[str] = Field(default=None, description="Process card name to use")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Input parameters")


class TaskResponse(BaseModel):
    """Response with task information."""
    task_id: str
    status: str
    created_at: str
    description: str
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None


class ProcessRequest(BaseModel):
    """Request to execute a process card."""
    card_name: str = Field(..., description="Process card name (without .yaml)")
    input_params: Optional[Dict[str, Any]] = Field(default={}, description="Input parameters")


class ProcessResponse(BaseModel):
    """Response from process execution."""
    process_id: str
    card_name: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_seconds: float
    steps_completed: int


class StatusResponse(BaseModel):
    """System status response."""
    status: str
    orchestrator: str
    agents: List[str]
    processes: Dict[str, int]
    storage: Optional[Dict[str, Any]] = None


# =============================================================================
# API Gateway Class
# =============================================================================

class APIGateway:
    """
    API Gateway for AI_TEAM system.

    Manages HTTP requests and delegates to Orchestrator.
    """

    def __init__(self, config_path: str = "config/api_gateway.yaml"):
        """Initialize API Gateway."""
        self.config = self._load_config(config_path)
        self.orchestrator = IntegratedOrchestrator()
        self.orchestrator.init_storage()

        # Register default agents
        self._register_default_agents()

        # Task storage (in-memory for MVP)
        self._tasks: Dict[str, dict] = {}

        logger.info(f"APIGateway initialized")

    def _load_config(self, config_path: str) -> dict:
        """Load configuration."""
        defaults = {
            "host": "0.0.0.0",
            "port": 8000,
            "process_cards_dir": "config/process_cards",
        }

        if Path(config_path).exists():
            try:
                with open(config_path) as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        defaults.update(file_config)
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")

        return defaults

    def _register_default_agents(self):
        """Register default agents for testing."""
        dummy = DummyAgent()
        self.orchestrator.register_local_agent("generate_text", dummy)
        self.orchestrator.register_local_agent("research", dummy)
        self.orchestrator.register_local_agent("review_text", dummy)
        self.orchestrator.register_local_agent("improve_text", dummy)
        self.orchestrator.register_local_agent("test.echo", dummy)

    # =========================================================================
    # Task Operations
    # =========================================================================

    def create_task(self, request: TaskRequest) -> TaskResponse:
        """Create and execute a new task."""
        task_id = str(uuid.uuid4())
        created_at = datetime.utcnow()

        # Store task info
        self._tasks[task_id] = {
            "id": task_id,
            "description": request.description,
            "status": "pending",
            "created_at": created_at,
            "time_budget": request.time_budget_seconds,
            "result": None,
            "error": None,
        }

        try:
            # Determine which process card to use
            if request.process_card:
                card_path = f"{self.config['process_cards_dir']}/{request.process_card}.yaml"
            else:
                # Default to simple_text_generation
                card_path = f"{self.config['process_cards_dir']}/simple_text_generation.yaml"

            # Load and execute
            card = self.orchestrator.load_card(card_path)

            # Prepare input params
            input_params = request.params or {}
            if "prompt" not in input_params:
                input_params["prompt"] = request.description

            # Execute
            self._tasks[task_id]["status"] = "running"
            instance = self.orchestrator.execute_process(card, input_params)

            # Update task with results
            self._tasks[task_id]["status"] = instance.status.value
            self._tasks[task_id]["result"] = instance.result
            self._tasks[task_id]["error"] = instance.error
            self._tasks[task_id]["duration"] = instance.duration_seconds()
            self._tasks[task_id]["process_id"] = instance.id

        except Exception as e:
            self._tasks[task_id]["status"] = "failed"
            self._tasks[task_id]["error"] = str(e)
            logger.error(f"Task {task_id} failed: {e}")

        task = self._tasks[task_id]
        return TaskResponse(
            task_id=task_id,
            status=task["status"],
            created_at=task["created_at"].isoformat(),
            description=request.description,
            result=task.get("result"),
            error=task.get("error"),
            duration_seconds=task.get("duration"),
        )

    def get_task(self, task_id: str) -> TaskResponse:
        """Get task by ID."""
        if task_id not in self._tasks:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

        task = self._tasks[task_id]
        return TaskResponse(
            task_id=task_id,
            status=task["status"],
            created_at=task["created_at"].isoformat(),
            description=task["description"],
            result=task.get("result"),
            error=task.get("error"),
            duration_seconds=task.get("duration"),
        )

    def list_tasks(self) -> List[TaskResponse]:
        """List all tasks."""
        return [
            TaskResponse(
                task_id=task["id"],
                status=task["status"],
                created_at=task["created_at"].isoformat(),
                description=task["description"],
                result=task.get("result"),
                error=task.get("error"),
                duration_seconds=task.get("duration"),
            )
            for task in self._tasks.values()
        ]

    # =========================================================================
    # Process Operations
    # =========================================================================

    def execute_process(self, request: ProcessRequest) -> ProcessResponse:
        """Execute a process card directly."""
        card_path = f"{self.config['process_cards_dir']}/{request.card_name}.yaml"

        if not Path(card_path).exists():
            raise HTTPException(
                status_code=404,
                detail=f"Process card not found: {request.card_name}"
            )

        try:
            card = self.orchestrator.load_card(card_path)
            instance = self.orchestrator.execute_process(card, request.input_params)

            completed_steps = len([
                r for r in instance.step_results
                if r.status.value == "completed"
            ])

            return ProcessResponse(
                process_id=instance.id,
                card_name=request.card_name,
                status=instance.status.value,
                result=instance.result,
                error=instance.error,
                duration_seconds=instance.duration_seconds(),
                steps_completed=completed_steps,
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def list_process_cards(self) -> List[str]:
        """List available process cards."""
        cards_dir = Path(self.config["process_cards_dir"])
        if not cards_dir.exists():
            return []
        return [p.stem for p in cards_dir.glob("*.yaml")]

    # =========================================================================
    # Status Operations
    # =========================================================================

    def get_status(self) -> StatusResponse:
        """Get system status."""
        stats = self.orchestrator.get_stats()

        storage_stats = None
        if self.orchestrator.storage:
            storage_result = self.orchestrator.storage.handle_command("get_stats", {})
            storage_stats = storage_result.get("stats")

        return StatusResponse(
            status="healthy",
            orchestrator=stats["name"],
            agents=stats["local_agents"],
            processes=stats["processes"],
            storage=storage_stats,
        )


# =============================================================================
# FastAPI Application
# =============================================================================

def create_app(gateway: Optional[APIGateway] = None) -> FastAPI:
    """Create FastAPI application."""

    if gateway is None:
        gateway = APIGateway()

    app = FastAPI(
        title="AI_TEAM API",
        description="HTTP API for AI_TEAM multi-agent system",
        version="1.0.0",
    )

    # Store gateway instance
    app.state.gateway = gateway

    # ==========================================================================
    # Routes
    # ==========================================================================

    @app.get("/")
    async def root():
        """API root."""
        return {
            "name": "AI_TEAM API",
            "version": "1.0.0",
            "endpoints": {
                "tasks": "/tasks",
                "process": "/process",
                "cards": "/cards",
                "status": "/status",
            }
        }

    @app.post("/tasks", response_model=TaskResponse)
    async def create_task(request: TaskRequest):
        """Create a new task."""
        return gateway.create_task(request)

    @app.get("/tasks", response_model=List[TaskResponse])
    async def list_tasks():
        """List all tasks."""
        return gateway.list_tasks()

    @app.get("/tasks/{task_id}", response_model=TaskResponse)
    async def get_task(task_id: str):
        """Get task by ID."""
        return gateway.get_task(task_id)

    @app.post("/process", response_model=ProcessResponse)
    async def execute_process(request: ProcessRequest):
        """Execute a process card."""
        return gateway.execute_process(request)

    @app.get("/cards", response_model=List[str])
    async def list_cards():
        """List available process cards."""
        return gateway.list_process_cards()

    @app.get("/status", response_model=StatusResponse)
    async def get_status():
        """Get system status."""
        return gateway.get_status()

    return app


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    )

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
