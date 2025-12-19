"""
Simple Orchestrator MVP — The "brain" of AI_TEAM.

This orchestrator:
- Loads and validates Process Cards
- Finds suitable agents via Node Registry
- Sends commands via MindBus
- Tracks process execution state
- Stores results in Storage Service

Philosophy: "Dumb Card, Smart Orchestrator"
- Card describes WHAT to do
- Orchestrator decides HOW and WHERE

See: docs/SSOT/PROCESS_CARD_SPEC_v1.0.md
"""

import logging
import signal
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

import yaml

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.mindbus.core import MindBus
from src.registry.node_registry import NodeRegistry
from src.registry.models import (
    NodePassport,
    NodeMetadata,
    NodeSpec,
    NodeStatus,
    NodeType,
    NodePhase,
    ConditionStatus,
    Capability,
    Condition,
    Lease,
    Endpoint,
)
from src.orchestrator.models import (
    ProcessCard,
    ProcessInstance,
    ProcessStatus,
    StepSpec,
    StepType,
    StepStatus,
    StepResult,
)

logger = logging.getLogger(__name__)


class SimpleOrchestrator:
    """
    Simple Orchestrator MVP for AI_TEAM.

    Capabilities:
    - Load Process Cards from YAML
    - Execute process steps sequentially
    - Find agents via Node Registry
    - Send commands and receive results via MindBus
    - Track process state

    Limitations (MVP):
    - Sequential execution only (no parallel steps)
    - Simple condition evaluation
    - In-memory state (no persistence)
    """

    def __init__(self, config_path: str = "config/orchestrator.yaml"):
        """Initialize orchestrator with configuration."""
        self.config = self._load_config(config_path)
        self.name = self.config.get("name", "orchestrator-01")

        # Registry configuration
        registry_config = self.config.get("registry", {})
        self._heartbeat_interval = registry_config.get("heartbeat_interval_seconds", 10)
        self._enable_registration = registry_config.get("enabled", True)

        # Process limits
        limits = self.config.get("process_limits", {})
        self._max_execution_time = limits.get("max_execution_time_seconds", 3600)
        self._step_timeout = limits.get("step_timeout_seconds", 300)
        self._max_retries = limits.get("max_retries_per_step", 3)

        # Components
        self.bus = MindBus()
        self.registry = NodeRegistry()

        # State
        self._running = False
        self._start_time: Optional[datetime] = None
        self._processes: Dict[str, ProcessInstance] = {}  # process_id -> instance
        self._pending_commands: Dict[str, dict] = {}  # command_id -> {process_id, step_id, ...}

        # Registration state
        self._node_uid: Optional[str] = None
        self._passport: Optional[NodePassport] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._stop_heartbeat = threading.Event()

        # Callbacks
        self._on_process_complete: Optional[Callable[[ProcessInstance], None]] = None
        self._on_step_complete: Optional[Callable[[str, StepResult], None]] = None

        logger.info(f"SimpleOrchestrator initialized: {self.name}")

    def _load_config(self, config_path: str) -> dict:
        """Load orchestrator configuration."""
        defaults = {
            "name": "orchestrator-01",
            "type": "orchestrator",
            "capabilities": ["process_execution", "task_routing"],
            "process_limits": {
                "max_execution_time_seconds": 3600,
                "step_timeout_seconds": 300,
                "max_retries_per_step": 3,
            },
            "registry": {
                "enabled": True,
                "heartbeat_interval_seconds": 10,
            },
        }

        if Path(config_path).exists():
            try:
                with open(config_path) as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        # Handle nested config (orchestrator: {...})
                        if len(file_config) == 1:
                            file_config = list(file_config.values())[0]
                        defaults.update(file_config)
            except Exception as e:
                logger.warning(f"Failed to load config: {e}, using defaults")

        return defaults

    # =========================================================================
    # Process Card Loading
    # =========================================================================

    def load_card(self, card_path: str) -> ProcessCard:
        """
        Load and validate Process Card from YAML file.

        Args:
            card_path: Path to YAML file

        Returns:
            Validated ProcessCard

        Raises:
            ValueError: If card is invalid
            FileNotFoundError: If file doesn't exist
        """
        logger.info(f"Loading process card: {card_path}")

        with open(card_path) as f:
            data = yaml.safe_load(f)

        card = ProcessCard.model_validate(data)

        # Validate references
        errors = card.validate_references()
        if errors:
            raise ValueError(f"Invalid process card: {'; '.join(errors)}")

        logger.info(f"Loaded card: {card.metadata.name} v{card.metadata.version}")
        return card

    def load_card_from_dict(self, data: dict) -> ProcessCard:
        """Load Process Card from dictionary."""
        card = ProcessCard.model_validate(data)
        errors = card.validate_references()
        if errors:
            raise ValueError(f"Invalid process card: {'; '.join(errors)}")
        return card

    # =========================================================================
    # Process Execution
    # =========================================================================

    def start_process(
        self,
        card: ProcessCard,
        input_params: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ) -> ProcessInstance:
        """
        Start executing a process.

        Args:
            card: Process Card to execute
            input_params: Input parameters for the process
            trace_id: Optional trace ID for distributed tracing

        Returns:
            ProcessInstance representing the running process
        """
        # Create process instance
        instance = ProcessInstance(
            card_id=card.metadata.id,
            card_name=card.metadata.name,
            input_params=input_params or {},
            variables=dict(card.spec.variables),  # Copy initial variables
            trace_id=trace_id or str(uuid.uuid4()),
        )

        # Set input variables
        instance.variables["input"] = input_params or {}

        # Store instance
        self._processes[instance.id] = instance

        logger.info(f"Starting process: {card.metadata.name} (id={instance.id[:8]}...)")

        # Start execution in background
        instance.status = ProcessStatus.RUNNING
        instance.started_at = datetime.utcnow()
        instance.current_step_id = card.get_first_step().id if card.get_first_step() else None

        return instance

    def execute_process_sync(
        self,
        card: ProcessCard,
        input_params: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ) -> ProcessInstance:
        """
        Execute process synchronously (blocking).

        This is the main execution method for MVP.
        """
        instance = self.start_process(card, input_params, trace_id)

        try:
            self._execute_steps(card, instance)
        except Exception as e:
            instance.status = ProcessStatus.FAILED
            instance.error = str(e)
            logger.error(f"Process failed: {e}")

        instance.completed_at = datetime.utcnow()

        if self._on_process_complete:
            self._on_process_complete(instance)

        return instance

    def _execute_steps(self, card: ProcessCard, instance: ProcessInstance) -> None:
        """Execute process steps sequentially."""
        max_iterations = len(card.spec.steps) * (self._max_retries + 1) * 2  # Safety limit
        iteration = 0

        while instance.current_step_id and iteration < max_iterations:
            iteration += 1

            step = card.get_step(instance.current_step_id)
            if not step:
                raise ValueError(f"Step not found: {instance.current_step_id}")

            logger.info(f"Executing step: {step.id} (type={step.get_type().value})")

            # Execute step
            result = self._execute_step(step, instance)
            instance.add_step_result(result)

            if self._on_step_complete:
                self._on_step_complete(instance.id, result)

            # Handle step result
            if result.status == StepStatus.FAILED:
                # Check retry policy
                retry = step.retry
                if retry and result.attempts < retry.max_attempts:
                    logger.info(f"Retrying step {step.id} (attempt {result.attempts + 1})")
                    time.sleep(retry.delay_seconds)
                    continue
                elif retry and retry.on_failure == "continue":
                    # Continue to next step despite failure
                    pass
                elif retry and retry.on_failure == "escalate":
                    instance.status = ProcessStatus.WAITING_HUMAN
                    instance.error = f"Step {step.id} failed, escalation required"
                    return
                else:
                    # Abort
                    instance.status = ProcessStatus.FAILED
                    instance.error = result.error
                    return

            # Determine next step
            next_step_id = self._get_next_step(step, result, instance)

            if next_step_id == "complete" or next_step_id is None:
                # Process completed
                instance.status = ProcessStatus.COMPLETED
                instance.result = instance.variables.get("_result")
                instance.current_step_id = None
                logger.info(f"Process completed: {instance.id[:8]}...")
                return

            instance.current_step_id = next_step_id

        if iteration >= max_iterations:
            raise ValueError("Process exceeded maximum iterations (possible infinite loop)")

    def _execute_step(self, step: StepSpec, instance: ProcessInstance) -> StepResult:
        """Execute a single step."""
        result = StepResult(
            step_id=step.id,
            status=StepStatus.RUNNING,
            started_at=datetime.utcnow(),
            attempts=(instance.get_step_result(step.id).attempts + 1
                     if instance.get_step_result(step.id) else 1)
        )

        step_type = step.get_type()

        try:
            if step_type == StepType.EXECUTE:
                output = self._execute_action_step(step, instance)
                result.output = output
                result.status = StepStatus.COMPLETED

                # Store output in variable if specified
                if step.output:
                    instance.variables[step.output] = output

            elif step_type == StepType.CONDITION:
                # Conditions don't have output
                result.status = StepStatus.COMPLETED

            elif step_type == StepType.COMPLETE:
                result.status = StepStatus.COMPLETED
                # Store final result
                if step.result:
                    instance.variables["_result"] = self._resolve_variable(
                        step.result, instance.variables
                    )

            elif step_type == StepType.WAIT:
                # MVP: just sleep for duration
                if step.duration:
                    seconds = self._parse_duration(step.duration)
                    time.sleep(min(seconds, 10))  # Cap at 10s for MVP
                result.status = StepStatus.COMPLETED

            else:
                raise ValueError(f"Unsupported step type: {step_type}")

        except Exception as e:
            result.status = StepStatus.FAILED
            result.error = str(e)
            logger.error(f"Step {step.id} failed: {e}")

        result.completed_at = datetime.utcnow()
        return result

    def _execute_action_step(self, step: StepSpec, instance: ProcessInstance) -> Any:
        """
        Execute an action step by finding an agent and sending command.

        This is where the "Smart Orchestrator" logic lives:
        1. Find agents with required capability
        2. Select best agent
        3. Send command via MindBus
        4. Wait for result
        """
        action = step.action
        if not action:
            raise ValueError("Action step must have action field")

        # Resolve parameters (replace ${var} with values)
        params = self._resolve_params(step.params, instance.variables)

        logger.info(f"Looking for agent with capability: {action}")

        # Find agents with capability
        agents = self.registry.find_nodes_by_capability(action)
        if not agents:
            # No agent available - this is where Orchestrator makes decisions
            raise ValueError(f"No agent found with capability: {action}")

        # Select best agent (MVP: just pick first available)
        agent = agents[0]
        logger.info(f"Selected agent: {agent.metadata.name}")

        # For MVP: direct call without MindBus async
        # In production, this would be async with MindBus
        return self._call_agent_direct(agent, action, params, instance)

    def _call_agent_direct(
        self,
        agent: NodePassport,
        action: str,
        params: Dict[str, Any],
        instance: ProcessInstance
    ) -> Any:
        """
        Call agent directly (MVP implementation).

        TODO: Replace with async MindBus command/result pattern.
        """
        # For MVP, we simulate the call by returning mock data
        # In production, this would send COMMAND via MindBus and wait for RESULT

        logger.info(f"Calling agent {agent.metadata.name} with action={action}")

        # Simulate agent call with mock response
        # This is placeholder for actual MindBus integration
        mock_result = {
            "action": action,
            "status": "completed",
            "agent": agent.metadata.name,
            "params_received": params,
            "message": f"Executed {action} successfully (mock)",
        }

        return mock_result

    def _get_next_step(
        self,
        step: StepSpec,
        result: StepResult,
        instance: ProcessInstance
    ) -> Optional[str]:
        """Determine next step based on current step and result."""
        step_type = step.get_type()

        if step_type == StepType.CONDITION:
            # Evaluate condition
            condition_result = self._evaluate_condition(step.condition, instance.variables)

            if condition_result:
                return step.then
            else:
                return step.else_step

        elif step_type == StepType.COMPLETE:
            return None  # End of process

        elif step.next:
            return step.next

        else:
            # Find next step in sequence
            card_steps = list(self._processes[instance.id].variables.get("_card_steps", []))
            if not card_steps:
                # Get from card (simplified - would need card reference)
                return None

            try:
                current_idx = next(i for i, s in enumerate(card_steps) if s == step.id)
                if current_idx + 1 < len(card_steps):
                    return card_steps[current_idx + 1]
            except StopIteration:
                pass

            return None

    def _evaluate_condition(self, condition: str, variables: Dict[str, Any]) -> bool:
        """
        Evaluate a condition expression.

        MVP: Simple evaluation using Python eval with restricted context.
        Production: Use proper expression parser.
        """
        if not condition:
            return True

        # Resolve variables in condition
        resolved = self._resolve_variable(condition, variables)

        # Simple conditions
        if resolved in ("true", "True", True):
            return True
        if resolved in ("false", "False", False):
            return False

        # Try to evaluate as expression
        try:
            # Create safe context with only variables
            context = dict(variables)
            result = eval(resolved, {"__builtins__": {}}, context)
            return bool(result)
        except Exception as e:
            logger.warning(f"Failed to evaluate condition '{condition}': {e}")
            return False

    def _resolve_params(self, params: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve variable references in parameters."""
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str):
                resolved[key] = self._resolve_variable(value, variables)
            elif isinstance(value, dict):
                resolved[key] = self._resolve_params(value, variables)
            elif isinstance(value, list):
                resolved[key] = [
                    self._resolve_variable(v, variables) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                resolved[key] = value
        return resolved

    def _resolve_variable(self, value: str, variables: Dict[str, Any]) -> Any:
        """
        Resolve ${variable} references in a string.

        Examples:
            "${topic}" -> variables["topic"]
            "${input.topic}" -> variables["input"]["topic"]
        """
        if not isinstance(value, str):
            return value

        import re

        # Pattern: ${variable} or ${variable.nested}
        pattern = r'\$\{([^}]+)\}'

        def replace(match):
            var_path = match.group(1)
            parts = var_path.split('.')

            result = variables
            for part in parts:
                if isinstance(result, dict) and part in result:
                    result = result[part]
                else:
                    return match.group(0)  # Keep original if not found

            return str(result) if not isinstance(result, (dict, list)) else str(result)

        resolved = re.sub(pattern, replace, value)

        # If entire string was a variable reference, return the actual value (not string)
        if value.startswith("${") and value.endswith("}") and value.count("${") == 1:
            var_path = value[2:-1]
            parts = var_path.split('.')
            result = variables
            for part in parts:
                if isinstance(result, dict) and part in result:
                    result = result[part]
                else:
                    return resolved
            return result

        return resolved

    def _parse_duration(self, duration: str) -> float:
        """Parse duration string (e.g., '5s', '1m', '1h') to seconds."""
        duration = duration.strip().lower()

        if duration.endswith('s'):
            return float(duration[:-1])
        elif duration.endswith('m'):
            return float(duration[:-1]) * 60
        elif duration.endswith('h'):
            return float(duration[:-1]) * 3600

        return float(duration)

    # =========================================================================
    # Process Management
    # =========================================================================

    def get_process(self, process_id: str) -> Optional[ProcessInstance]:
        """Get process instance by ID."""
        return self._processes.get(process_id)

    def get_all_processes(self) -> List[ProcessInstance]:
        """Get all process instances."""
        return list(self._processes.values())

    def cancel_process(self, process_id: str) -> bool:
        """Cancel a running process."""
        instance = self._processes.get(process_id)
        if instance and instance.status == ProcessStatus.RUNNING:
            instance.status = ProcessStatus.CANCELLED
            instance.completed_at = datetime.utcnow()
            logger.info(f"Process cancelled: {process_id[:8]}...")
            return True
        return False

    # =========================================================================
    # Callbacks
    # =========================================================================

    def on_process_complete(self, callback: Callable[[ProcessInstance], None]) -> None:
        """Register callback for process completion."""
        self._on_process_complete = callback

    def on_step_complete(self, callback: Callable[[str, StepResult], None]) -> None:
        """Register callback for step completion."""
        self._on_step_complete = callback

    # =========================================================================
    # Node Registration (same as BaseService)
    # =========================================================================

    def _build_passport(self) -> NodePassport:
        """Build NODE_PASSPORT for orchestrator."""
        if self._node_uid is None:
            self._node_uid = str(uuid.uuid4())

        capabilities = [
            Capability(name="process_execution", version="1.0"),
            Capability(name="task_routing", version="1.0"),
        ]

        labels = {
            "node.type": "orchestrator",
            "capability.process_execution": "true",
            "capability.task_routing": "true",
        }

        passport = NodePassport(
            metadata=NodeMetadata(
                uid=self._node_uid,
                name=self.name,
                node_type=NodeType.ORCHESTRATOR,
                labels=labels,
                version=self.config.get("version", "1.0.0"),
            ),
            spec=NodeSpec(
                node_type=NodeType.ORCHESTRATOR,
                capabilities=capabilities,
                endpoint=Endpoint(
                    protocol="amqp",
                    queue=f"cmd.{self.name.replace('.', '_')}.*",
                ),
                configuration=self.config.get("process_limits", {})
            ),
            status=NodeStatus(
                phase=NodePhase.RUNNING,
                conditions=[
                    Condition(
                        type="Ready",
                        status=ConditionStatus.TRUE,
                        reason="OrchestratorStarted",
                        message=f"Orchestrator {self.name} is ready",
                    )
                ],
                lease=Lease(
                    holder_identity=self.name,
                    lease_duration_seconds=max(1, int(self._heartbeat_interval * 3)),
                ),
                current_tasks=len([p for p in self._processes.values()
                                  if p.status == ProcessStatus.RUNNING]),
                total_tasks_processed=len([p for p in self._processes.values()
                                          if p.status == ProcessStatus.COMPLETED]),
            ),
        )

        self._passport = passport
        return passport

    def _send_registration_event(self) -> None:
        """Send node.registered EVENT to MindBus."""
        if not self._enable_registration:
            return

        passport = self._build_passport()

        self.bus.send_event(
            event_type_name="node.registered",
            event_data={
                "node_id": passport.metadata.uid,
                "name": passport.metadata.name,
                "node_type": passport.metadata.node_type.value,
                "capabilities": [cap.name for cap in passport.spec.capabilities],
                "labels": passport.metadata.labels,
                "passport": passport.model_dump(mode="json"),
            },
            source=self.name,
            tags=["registration", "node", "orchestrator"],
        )

        logger.info(f"[{self.name}] Sent node.registered event")

    def _send_heartbeat_event(self) -> None:
        """Send heartbeat event."""
        if not self._enable_registration or self._passport is None:
            return

        self._passport.status.lease.renew_time = datetime.utcnow()
        self._passport.status.current_tasks = len([
            p for p in self._processes.values()
            if p.status == ProcessStatus.RUNNING
        ])

        self.bus.send_event(
            event_type_name="node.heartbeat",
            event_data={
                "node_id": self._node_uid,
                "name": self.name,
                "renew_time": self._passport.status.lease.renew_time.isoformat(),
                "current_tasks": self._passport.status.current_tasks,
            },
            source=self.name,
            tags=["heartbeat", "node", "orchestrator"],
        )

    def _send_deregistration_event(self, reason: str = "GracefulShutdown") -> None:
        """Send deregistration event."""
        if not self._enable_registration or self._node_uid is None:
            return

        self.bus.send_event(
            event_type_name="node.deregistered",
            event_data={
                "node_id": self._node_uid,
                "name": self.name,
                "reason": reason,
            },
            source=self.name,
            tags=["deregistration", "node", "orchestrator"],
        )

    def _start_heartbeat_thread(self) -> None:
        """Start heartbeat thread."""
        if not self._enable_registration:
            return

        self._stop_heartbeat.clear()

        def heartbeat_loop():
            while not self._stop_heartbeat.wait(timeout=self._heartbeat_interval):
                try:
                    self._send_heartbeat_event()
                except Exception as e:
                    logger.error(f"Error sending heartbeat: {e}")

        self._heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _stop_heartbeat_thread(self) -> None:
        """Stop heartbeat thread."""
        self._stop_heartbeat.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=2.0)
            self._heartbeat_thread = None

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def start(self) -> None:
        """Start the orchestrator."""
        print(f"\n🎯 Starting {self.name}...")
        print(f"   Type: orchestrator")
        print(f"   NodeType: {NodeType.ORCHESTRATOR.value}")

        self.bus.connect()
        print(f"   ✓ Connected to MindBus")

        self._running = True
        self._start_time = datetime.now()

        if self._enable_registration:
            self._send_registration_event()
            self._start_heartbeat_thread()
            print(f"   ✓ Registered with Node Registry")

        print(f"\n   Orchestrator ready.\n")

    def stop(self) -> None:
        """Stop the orchestrator."""
        self._running = False

        if self._enable_registration:
            self._stop_heartbeat_thread()
            try:
                self._send_deregistration_event()
            except Exception as e:
                logger.warning(f"Failed to send deregistration: {e}")

        self.bus.disconnect()

        uptime = ""
        if self._start_time:
            uptime = f" (uptime: {datetime.now() - self._start_time})"

        print(f"\n🛑 {self.name} stopped{uptime}")
        print(f"   Processes executed: {len(self._processes)}")

    def get_stats(self) -> dict:
        """Get orchestrator statistics."""
        processes = self._processes.values()
        return {
            "name": self.name,
            "running": self._running,
            "uptime": str(datetime.now() - self._start_time) if self._start_time else None,
            "processes": {
                "total": len(processes),
                "running": len([p for p in processes if p.status == ProcessStatus.RUNNING]),
                "completed": len([p for p in processes if p.status == ProcessStatus.COMPLETED]),
                "failed": len([p for p in processes if p.status == ProcessStatus.FAILED]),
            }
        }


def main():
    """Run the orchestrator."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    )

    orchestrator = SimpleOrchestrator()
    orchestrator.start()

    # Keep running until interrupted
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        orchestrator.stop()


if __name__ == "__main__":
    main()
