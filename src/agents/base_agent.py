"""
Base Agent — Abstract base class for all AI_TEAM agents.

All agents inherit from this class and implement the `execute` method.
The base class handles:
- Connection to MindBus
- Subscription to COMMAND messages
- Sending RESULT/ERROR responses
- Node registration (NODE_PASSPORT)
- Heartbeat to Registry
- Progress Heartbeat for long-running tasks (AGENT_SPEC v1.0.3)
- Singleton Enforcement - prevents duplicate instances (AGENT_SPEC v1.0.4)
- Tools Framework (ToolRegistry)
- Graceful shutdown

See: docs/project/IMPLEMENTATION_ROADMAP.md Step 1.4, 1.8.2
See: docs/SSOT/AGENT_SPEC_v1.0.md (Section 14.5 Progress Heartbeat, Section 14.6 Singleton)
"""

import logging
import signal
import threading
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.mindbus.core import MindBus
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

# Tools Framework import
from src.agents.tools import (
    ToolRegistry,
    ToolSecurityLevel,
    WebSearchTool,
    WebFetchTool,
    MemoryReadTool,
    MemoryWriteTool,
    MemoryListTool,
    MemoryDeleteTool,
    get_working_memory,
    set_working_memory,
    WorkingMemory,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Singleton Enforcement Exception (AGENT_SPEC v1.0.4 Section 14.6)
# =============================================================================

class AgentAlreadyRunningError(Exception):
    """
    Raised when another instance of the agent is already running.

    Per AGENT_SPEC v1.0.4: Uses RabbitMQ Exclusive Queue mechanism
    to prevent duplicate agent instances with the same name.
    """
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        super().__init__(
            f"Agent '{agent_name}' is already running. "
            f"Stop the existing instance before starting a new one."
        )


class BaseAgent(ABC):
    """
    Abstract base class for AI_TEAM agents.

    Subclasses must implement:
    - execute(action, params, context) -> dict

    The base class handles MindBus communication automatically.
    """

    def __init__(self, config_path: str):
        """
        Initialize agent with configuration.

        Args:
            config_path: Path to agent's YAML config file
        """
        self.config = self._load_config(config_path)
        self.name = self.config.get("name", "unknown-agent")
        self.agent_type = self.config.get("type", "agent")
        self.capabilities = self.config.get("capabilities", [])

        # Registry configuration (from config or defaults)
        registry_config = self.config.get("registry", {})
        self._heartbeat_interval = registry_config.get("heartbeat_interval_seconds", 10)
        self._enable_registration = registry_config.get("enabled", True)

        self.bus = MindBus()
        self._heartbeat_bus: Optional[MindBus] = None  # Separate connection for thread safety
        self._progress_bus: Optional[MindBus] = None   # Progress heartbeat connection (AGENT_SPEC v1.0.3)
        self._running = False
        self._start_time: Optional[datetime] = None
        self._tasks_processed = 0

        # Registration state
        self._node_uid: Optional[str] = None
        self._passport: Optional[NodePassport] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._stop_heartbeat = threading.Event()

        # Progress Heartbeat state (AGENT_SPEC v1.0.3)
        # Allows distinguishing "working long" from "stuck/crashed"
        self._progress_thread: Optional[threading.Thread] = None
        self._stop_progress = threading.Event()
        self._current_task_id: Optional[str] = None
        self._task_start_time: Optional[float] = None
        self._working = threading.Event()  # Set when processing a task

        # Progress heartbeat config
        progress_config = self.config.get("progress_heartbeat", {})
        self._progress_enabled = progress_config.get("enabled", True)
        self._progress_interval = progress_config.get("interval_seconds", 30)

        # Tools Framework (AGENT_SPEC Section 4)
        self.tool_registry = ToolRegistry()
        self._tool_calls_count = 0
        self._init_tools()

        # Working Memory (short-term memory for tools)
        self._working_memory = WorkingMemory(max_entries=100)
        set_working_memory(self._working_memory)

        # Idempotency Storage (AGENT_SPEC 14.1)
        # In-memory for MVP, can be Redis/file for production
        self._processed_command_ids: Dict[str, datetime] = {}
        self._idempotency_ttl_seconds = 86400  # 24 hours

        # Singleton Enforcement (AGENT_SPEC v1.0.4 Section 14.6)
        # Prevents duplicate agent instances with the same name
        singleton_config = self.config.get("singleton", {})
        self._singleton_enabled = singleton_config.get("enabled", True)  # Enabled by default
        self._singleton_queue_name: Optional[str] = None
        self._singleton_bus: Optional[MindBus] = None

    def _load_config(self, config_path: str) -> dict:
        """Load agent configuration from YAML file."""
        with open(config_path) as f:
            config = yaml.safe_load(f)
        # Extract agent-specific config (file may have nested structure)
        # e.g., {"dummy_agent": {...}} -> {...}
        if len(config) == 1:
            return list(config.values())[0]
        return config

    def _init_tools(self) -> None:
        """
        Initialize tools from configuration.

        Based on AGENT_SPEC Section 4.5 - Tools Security.
        Tools are loaded based on 'tools.enabled' list in config.
        """
        tools_config = self.config.get("tools", {})
        enabled_tools = tools_config.get("enabled", [])

        # Available tools mapping
        available_tools = {
            "web_search": WebSearchTool,
            "web_fetch": WebFetchTool,
            "memory_read": MemoryReadTool,
            "memory_write": MemoryWriteTool,
            "memory_list": MemoryListTool,
            "memory_delete": MemoryDeleteTool,
        }

        # Register enabled tools
        for tool_name in enabled_tools:
            if tool_name in available_tools:
                tool_class = available_tools[tool_name]
                tool_instance = tool_class()
                self.tool_registry.register(tool_instance)
                logger.debug(f"[{self.name}] Registered tool: {tool_name}")
            else:
                logger.warning(f"[{self.name}] Unknown tool: {tool_name}")

        # If no tools specified, register default safe tools
        if not enabled_tools:
            default_tools = ["web_search", "memory_read", "memory_write"]
            for tool_name in default_tools:
                if tool_name in available_tools:
                    tool_instance = available_tools[tool_name]()
                    self.tool_registry.register(tool_instance)
            logger.info(f"[{self.name}] Registered default tools: {default_tools}")

        logger.info(f"[{self.name}] Tools initialized: {list(self.tool_registry._tools.keys())}")

    def get_tools_schemas(self) -> List[Dict[str, Any]]:
        """
        Get OpenAI Function Calling schemas for all registered tools.

        Returns:
            List of tool schemas for LLM function calling
        """
        return self.tool_registry.get_openai_schemas()

    def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool parameters

        Returns:
            Dict with 'success', 'data', 'error' keys
        """
        self._tool_calls_count += 1
        result = self.tool_registry.execute(tool_name, **kwargs)
        return result.model_dump()

    async def aexecute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Async execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool parameters

        Returns:
            Dict with 'success', 'data', 'error' keys
        """
        self._tool_calls_count += 1
        result = await self.tool_registry.aexecute(tool_name, **kwargs)
        return result.model_dump()

    def get_working_memory(self) -> WorkingMemory:
        """Get agent's working memory instance."""
        return self._working_memory

    @abstractmethod
    def execute(
        self,
        action: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute the given action with parameters.

        Args:
            action: The action to perform (e.g., "generate_article")
            params: Action parameters
            context: Optional execution context (process_id, step, etc.)

        Returns:
            Result dictionary to be sent in RESULT message

        Raises:
            Exception: Any error will be caught and sent as ERROR message
        """
        pass

    def _on_command(self, event: dict, data: dict) -> None:
        """
        Handle incoming COMMAND message.

        This method is called by MindBus when a command is received.
        It executes the action and sends RESULT or ERROR response.

        Per AGENT_SPEC 14.2: Agent checks target_node in data payload
        and ignores messages addressed to other agents.
        """
        # =====================================================================
        # TARGET_NODE FILTERING (AGENT_SPEC 14.2)
        # =====================================================================
        # target_node can be in data directly or in data.context (from MindBus)
        context = data.get("context", {}) or {}
        target_node = data.get("target_node") or context.get("target_node")
        if target_node and target_node != self.name:
            # Message is addressed to another agent, ignore it
            logger.debug(f"[{self.name}] Ignoring COMMAND for target_node={target_node}")
            return

        start_time = time.time()

        action = data.get("action", "unknown")
        params = data.get("params", {})
        # context already extracted above for target_node
        timeout_seconds = data.get("timeout_seconds")

        # Extract message metadata for response
        command_id = event.get("id")
        subject = event.get("subject")
        traceparent = event.get("traceparent")
        reply_to = event.get("reply_to")  # AMQP reply_to for RPC pattern

        logger.info(f"[{self.name}] Received COMMAND: action={action}, target_node={target_node}, reply_to={reply_to}")

        # =====================================================================
        # IDEMPOTENCY CHECK (AGENT_SPEC 14.1)
        # =====================================================================
        if self._is_duplicate_command(command_id):
            logger.info(f"[{self.name}] Duplicate command ignored: {command_id}")
            return

        # =====================================================================
        # CAPABILITY VALIDATION (AGENT_SPEC Section 6)
        # =====================================================================
        if not self._has_capability(action):
            error_msg = f"Agent '{self.name}' does not support action '{action}'. Available: {self._get_capability_names()}"
            logger.warning(f"[{self.name}] {error_msg}")
            if reply_to:
                self.bus.send_error(
                    code="UNIMPLEMENTED",
                    message=error_msg,
                    retryable=False,
                    source=self.name,
                    reply_to=reply_to,
                    correlation_id=command_id,
                    subject=subject,
                    trace_id=traceparent,
                    details={"requested_action": action, "available_capabilities": self._get_capability_names()},
                    execution_time_ms=0
                )
            return

        # =====================================================================
        # PROGRESS TRACKING START (AGENT_SPEC v1.0.3 Section 14.5)
        # =====================================================================
        self._begin_task(command_id)

        try:
            # Execute the action
            result = self.execute(action, params, context)

            # Calculate execution time
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Send RESULT via RPC reply-to pattern
            if reply_to:
                self.bus.send_result(
                    output=result,
                    execution_time_ms=execution_time_ms,
                    source=self.name,
                    reply_to=reply_to,
                    correlation_id=command_id,
                    subject=subject,
                    trace_id=traceparent,
                    metrics=self._get_metrics()
                )
            else:
                logger.warning(f"[{self.name}] No reply_to in COMMAND, cannot send RESULT")

            self._tasks_processed += 1
            self._mark_command_processed(command_id)  # Idempotency (AGENT_SPEC 14.1)
            self._end_task()  # Progress tracking end (AGENT_SPEC v1.0.3)
            logger.info(f"[{self.name}] Sent RESULT for action={action} ({execution_time_ms}ms)")

        except Exception as e:
            # Calculate execution time until error
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Determine error code and retryability
            error_code = self._get_error_code(e)
            retryable = self._is_retryable(e)

            # Send ERROR via RPC reply-to pattern
            if reply_to:
                self.bus.send_error(
                    code=error_code,
                    message=str(e),
                    retryable=retryable,
                    source=self.name,
                    reply_to=reply_to,
                    correlation_id=command_id,
                    subject=subject,
                    trace_id=traceparent,
                    details={"exception_type": type(e).__name__},
                    execution_time_ms=execution_time_ms
                )
                logger.error(f"[{self.name}] Sent ERROR for action={action}: {e}")
            else:
                logger.error(f"[{self.name}] ERROR for action={action}: {e} (no reply_to)")

            self._end_task()  # Progress tracking end on error (AGENT_SPEC v1.0.3)

    def _get_error_code(self, error: Exception) -> str:
        """Map exception to google.rpc.Code."""
        error_type = type(error).__name__

        # Map common exceptions to standard codes
        mapping = {
            "ValueError": "INVALID_ARGUMENT",
            "TypeError": "INVALID_ARGUMENT",
            "KeyError": "NOT_FOUND",
            "FileNotFoundError": "NOT_FOUND",
            "PermissionError": "PERMISSION_DENIED",
            "TimeoutError": "DEADLINE_EXCEEDED",
            "ConnectionError": "UNAVAILABLE",
            "NotImplementedError": "UNIMPLEMENTED",
        }

        return mapping.get(error_type, "INTERNAL")

    def _is_retryable(self, error: Exception) -> bool:
        """Determine if error is retryable."""
        retryable_types = {
            "TimeoutError",
            "ConnectionError",
            "OSError",
        }
        return type(error).__name__ in retryable_types

    def _has_capability(self, action: str) -> bool:
        """
        Check if agent has the capability to perform the given action.

        Per AGENT_SPEC Section 6: Capabilities define what agent can do.
        """
        capability_names = self._get_capability_names()
        return action in capability_names

    def _get_capability_names(self) -> List[str]:
        """
        Get list of capability names from config.

        Handles both string capabilities and dict capabilities.
        """
        names = []
        for cap in self.capabilities:
            if isinstance(cap, str):
                names.append(cap)
            elif isinstance(cap, dict):
                names.append(cap.get("name", ""))
        return names

    def _is_duplicate_command(self, command_id: str) -> bool:
        """
        Check if command was already processed (idempotency).

        Per AGENT_SPEC 14.1: Prevents duplicate command processing.
        """
        if not command_id:
            return False

        # Cleanup expired entries periodically
        self._cleanup_idempotency_storage()

        return command_id in self._processed_command_ids

    def _mark_command_processed(self, command_id: str) -> None:
        """Mark command as processed for idempotency."""
        if command_id:
            self._processed_command_ids[command_id] = datetime.utcnow()

    def _cleanup_idempotency_storage(self) -> None:
        """Remove expired idempotency keys."""
        now = datetime.utcnow()
        expired = [
            cmd_id for cmd_id, timestamp in self._processed_command_ids.items()
            if (now - timestamp).total_seconds() > self._idempotency_ttl_seconds
        ]
        for cmd_id in expired:
            del self._processed_command_ids[cmd_id]

    def _get_metrics(self) -> Dict[str, Any]:
        """Get agent metrics for RESULT message."""
        return {
            "agent": self.name,
            "type": self.agent_type,
            "tasks_processed": self._tasks_processed,
            "tool_calls": self._tool_calls_count,
            "tools_available": list(self.tool_registry._tools.keys()),
        }

    # =========================================================================
    # Node Registration (NODE_PASSPORT)
    # =========================================================================

    def _build_passport(self) -> NodePassport:
        """
        Build NODE_PASSPORT from agent configuration.

        Returns:
            NodePassport ready for registration
        """
        # Generate or use existing UID
        if self._node_uid is None:
            self._node_uid = str(uuid.uuid4())

        # Build capabilities from config
        capabilities = []
        labels = {"node.type": self.agent_type}

        for cap in self.capabilities:
            if isinstance(cap, str):
                # Simple string capability
                capabilities.append(Capability(name=cap, version="1.0"))
                labels[f"capability.{cap}"] = "true"
            elif isinstance(cap, dict):
                # Full capability object
                capabilities.append(Capability(
                    name=cap.get("name", "unknown"),
                    version=cap.get("version", "1.0"),
                    parameters=cap.get("parameters", {})
                ))
                labels[f"capability.{cap.get('name', 'unknown')}"] = "true"

        # Add custom labels from config
        config_labels = self.config.get("labels", {})
        labels.update(config_labels)

        # Build passport
        passport = NodePassport(
            metadata=NodeMetadata(
                uid=self._node_uid,
                name=self.name,
                node_type=NodeType.AGENT,
                labels=labels,
                version=self.config.get("version", "1.0.0"),
            ),
            spec=NodeSpec(
                node_type=NodeType.AGENT,
                capabilities=capabilities,
                endpoint=Endpoint(
                    protocol="amqp",
                    queue=f"cmd.{self.name.replace('.', '_')}.*",
                ),
                configuration={
                    "agent_type": self.agent_type,
                    "llm": self.config.get("llm", {}),
                }
            ),
            status=NodeStatus(
                phase=NodePhase.RUNNING,
                conditions=[
                    Condition(
                        type="Ready",
                        status=ConditionStatus.TRUE,
                        reason="AgentStarted",
                        message=f"Agent {self.name} is ready to accept commands",
                    )
                ],
                lease=Lease(
                    holder_identity=self.name,
                    lease_duration_seconds=max(1, int(self._heartbeat_interval * 3)),
                ),
                current_tasks=0,
                total_tasks_processed=self._tasks_processed,
            ),
        )

        self._passport = passport
        return passport

    def _send_registration_event(self) -> None:
        """Send node.registered EVENT to MindBus."""
        if not self._enable_registration:
            return

        passport = self._build_passport()

        # Send EVENT with passport data
        # API: send_event(topic, event_type_suffix, event_data, source, ...)
        self.bus.send_event(
            topic="node",
            event_type_suffix="registered",
            event_data={
                "node_id": passport.metadata.uid,
                "name": passport.metadata.name,
                "node_type": passport.metadata.node_type.value,
                "capabilities": [cap.name for cap in passport.spec.capabilities],
                "labels": passport.metadata.labels,
                "passport": passport.model_dump(mode="json"),
            },
            source=self.name,
            tags=["registration", "node"],
        )

        logger.info(f"[{self.name}] Sent node.registered event (uid={self._node_uid[:8]}...)")

    def _send_heartbeat_event(self) -> None:
        """Send node.heartbeat EVENT to MindBus."""
        if not self._enable_registration or self._passport is None:
            return

        # Update lease time
        self._passport.status.lease.renew_time = datetime.utcnow()
        self._passport.status.total_tasks_processed = self._tasks_processed

        # Use separate heartbeat_bus for thread safety (pika is not thread-safe)
        if self._heartbeat_bus is None:
            return

        # Send lightweight heartbeat event via dedicated connection
        self._heartbeat_bus.send_event(
            topic="node",
            event_type_suffix="heartbeat",
            event_data={
                "node_id": self._node_uid,
                "name": self.name,
                "renew_time": self._passport.status.lease.renew_time.isoformat(),
                "current_tasks": self._passport.status.current_tasks,
                "total_tasks_processed": self._tasks_processed,
            },
            source=self.name,
            tags=["heartbeat", "node"],
        )

        logger.debug(f"[{self.name}] Sent heartbeat")

    def _send_deregistration_event(self, reason: str = "GracefulShutdown") -> None:
        """Send node.deregistered EVENT to MindBus."""
        if not self._enable_registration or self._node_uid is None:
            return

        self.bus.send_event(
            topic="node",
            event_type_suffix="deregistered",
            event_data={
                "node_id": self._node_uid,
                "name": self.name,
                "reason": reason,
                "total_tasks_processed": self._tasks_processed,
            },
            source=self.name,
            tags=["deregistration", "node"],
        )

        logger.info(f"[{self.name}] Sent node.deregistered event (reason={reason})")

    def _start_heartbeat_thread(self) -> None:
        """Start background thread for sending heartbeats."""
        if not self._enable_registration:
            return

        self._stop_heartbeat.clear()

        # Create dedicated MindBus connection for heartbeat thread (pika is not thread-safe)
        self._heartbeat_bus = MindBus()
        self._heartbeat_bus.connect()
        logger.info(f"[{self.name}] Heartbeat bus connected (separate connection for thread safety)")

        def heartbeat_loop():
            logger.info(f"[{self.name}] Heartbeat thread started (interval={self._heartbeat_interval}s)")

            while not self._stop_heartbeat.wait(timeout=self._heartbeat_interval):
                try:
                    self._send_heartbeat_event()
                except Exception as e:
                    logger.error(f"[{self.name}] Error sending heartbeat: {e}")

            logger.info(f"[{self.name}] Heartbeat thread stopped")

        self._heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _stop_heartbeat_thread(self) -> None:
        """Stop the heartbeat thread and close heartbeat bus."""
        self._stop_heartbeat.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=2.0)
            self._heartbeat_thread = None

        # Close dedicated heartbeat bus connection
        if self._heartbeat_bus:
            try:
                self._heartbeat_bus.disconnect()
            except Exception as e:
                logger.warning(f"[{self.name}] Error disconnecting heartbeat bus: {e}")
            self._heartbeat_bus = None

    # =========================================================================
    # Progress Heartbeat (AGENT_SPEC v1.0.3 Section 14.5)
    # =========================================================================

    def _start_progress_thread(self) -> None:
        """
        Start background thread for sending task.progress events.

        Creates a dedicated MindBus connection (pika is not thread-safe).
        Progress events are sent only when _working flag is set.
        """
        if not self._progress_enabled:
            return

        self._stop_progress.clear()

        # Create dedicated MindBus connection for progress thread
        self._progress_bus = MindBus()
        self._progress_bus.connect()
        logger.info(f"[{self.name}] Progress bus connected (separate connection for thread safety)")

        def progress_loop():
            logger.info(f"[{self.name}] Progress thread started (interval={self._progress_interval}s)")

            while not self._stop_progress.wait(timeout=self._progress_interval):
                try:
                    # Only send progress if actively working on a task
                    if self._working.is_set() and self._current_task_id:
                        self._send_progress_event()
                except Exception as e:
                    logger.error(f"[{self.name}] Error sending progress: {e}")

            logger.info(f"[{self.name}] Progress thread stopped")

        self._progress_thread = threading.Thread(target=progress_loop, daemon=True)
        self._progress_thread.start()

    def _stop_progress_thread(self) -> None:
        """Stop the progress thread and close progress bus."""
        self._stop_progress.set()
        self._working.clear()

        if self._progress_thread:
            self._progress_thread.join(timeout=2.0)
            self._progress_thread = None

        # Close dedicated progress bus connection
        if self._progress_bus:
            try:
                self._progress_bus.disconnect()
            except Exception as e:
                logger.warning(f"[{self.name}] Error disconnecting progress bus: {e}")
            self._progress_bus = None

    def _send_progress_event(self, phase: str = "processing") -> None:
        """
        Send task.progress EVENT to MindBus.

        Per AGENT_SPEC v1.0.3: Reports current task progress every interval_seconds.
        Allows Monitor/Orchestrator to distinguish "working long" from "stuck".

        Args:
            phase: Current work phase (e.g., "initializing", "generating", "processing")
        """
        if not self._progress_bus or not self._current_task_id:
            return

        # Calculate elapsed time since task start
        elapsed_seconds = 0
        if self._task_start_time:
            elapsed_seconds = int(time.time() - self._task_start_time)

        self._progress_bus.send_event(
            topic="task",
            event_type_suffix="progress",
            event_data={
                "task_id": self._current_task_id,
                "state": "working",
                "elapsed_seconds": elapsed_seconds,
                "phase": phase,
            },
            source=self.name,
            tags=["progress", "task"],
        )

        logger.debug(f"[{self.name}] Sent task.progress (task_id={self._current_task_id[:8]}..., elapsed={elapsed_seconds}s)")

    def _begin_task(self, task_id: str) -> None:
        """
        Mark task as started for progress tracking.

        Called at the beginning of _on_command() before execute().
        """
        self._current_task_id = task_id
        self._task_start_time = time.time()
        self._working.set()
        logger.debug(f"[{self.name}] Task started: {task_id}")

    def _end_task(self) -> None:
        """
        Mark task as finished for progress tracking.

        Called at the end of _on_command() after execute() or on error.
        """
        self._working.clear()
        task_id = self._current_task_id
        self._current_task_id = None
        self._task_start_time = None
        if task_id:
            logger.debug(f"[{self.name}] Task ended: {task_id}")

    def get_passport(self) -> Optional[NodePassport]:
        """Get current NODE_PASSPORT."""
        return self._passport

    # =========================================================================
    # Singleton Enforcement (AGENT_SPEC v1.0.4 Section 14.6)
    # =========================================================================

    def _acquire_singleton_lock(self) -> None:
        """
        Acquire exclusive lock to ensure only one instance of this agent runs.

        Uses RabbitMQ Exclusive Queue mechanism:
        - exclusive=True: Only this connection can consume from queue
        - auto_delete=True: Queue deleted when connection closes

        If another instance is running, raises AgentAlreadyRunningError.

        See: docs/SSOT/AGENT_SPEC_v1.0.md Section 14.6
        """
        if not self._singleton_enabled:
            return

        self._singleton_queue_name = f"singleton.{self.name}"

        # Create dedicated connection for singleton lock
        # Must be separate from main bus to avoid interference
        self._singleton_bus = MindBus()
        self._singleton_bus.connect()

        try:
            # Attempt to declare exclusive queue
            # This will fail with RESOURCE_LOCKED (405) if another instance has it
            channel = self._singleton_bus._channel
            channel.queue_declare(
                queue=self._singleton_queue_name,
                exclusive=True,
                auto_delete=True
            )

            # Success - we have the lock
            logger.info(
                f"[{self.name}] Singleton lock acquired "
                f"(queue: {self._singleton_queue_name})"
            )

        except Exception as e:
            # Clean up failed connection
            if self._singleton_bus:
                try:
                    self._singleton_bus.disconnect()
                except Exception:
                    pass
                self._singleton_bus = None

            # Log detailed error for diagnostics (per user request)
            logger.error(
                f"[{self.name}] SINGLETON CONFLICT: Agent '{self.name}' already running!"
            )
            logger.error(
                f"[{self.name}] Another instance holds exclusive queue "
                f"'{self._singleton_queue_name}'"
            )
            logger.error(
                f"[{self.name}] Action: Stop the existing instance or use a different agent name"
            )
            logger.error(
                f"[{self.name}] Shutting down to prevent duplicate processing"
            )

            raise AgentAlreadyRunningError(self.name) from e

    def _release_singleton_lock(self) -> None:
        """
        Release singleton lock by closing the exclusive queue connection.

        Called during agent shutdown.
        """
        if self._singleton_bus:
            try:
                self._singleton_bus.disconnect()
                logger.info(
                    f"[{self.name}] Singleton lock released "
                    f"(queue: {self._singleton_queue_name})"
                )
            except Exception as e:
                logger.warning(
                    f"[{self.name}] Error releasing singleton lock: {e}"
                )
            finally:
                self._singleton_bus = None
                self._singleton_queue_name = None

    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown on Ctrl+C."""
        def signal_handler(sig, frame):
            logger.info(f"[{self.name}] Received shutdown signal")
            self._running = False
            self.bus.stop_consuming()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def start(self) -> None:
        """Start the agent and begin processing commands."""
        print(f"\n🤖 Starting {self.name}...")
        print(f"   Type: {self.agent_type}")
        print(f"   Capabilities: {', '.join(str(c) for c in self.capabilities)}")
        print(f"   Tools: {', '.join(self.tool_registry._tools.keys()) or 'none'}")

        # =====================================================================
        # SINGLETON ENFORCEMENT (AGENT_SPEC v1.0.4 Section 14.6)
        # Must be FIRST to prevent any duplicate processing
        # =====================================================================
        if self._singleton_enabled:
            try:
                self._acquire_singleton_lock()
                print(f"   ✓ Singleton lock acquired (only one instance allowed)")
            except AgentAlreadyRunningError as e:
                print(f"\n❌ SINGLETON CONFLICT: {e}")
                print(f"   Another instance of '{self.name}' is already running.")
                print(f"   Stop the existing instance before starting a new one.")
                raise

        self.bus.connect()
        print(f"   ✓ Connected to MindBus")

        self._setup_signal_handlers()

        # Subscribe to commands for this agent
        # Pattern: cmd.{agent_type}.{agent_id} or cmd.{agent_type}.any
        # Using # (multi-word wildcard) to match routing keys with variable depth
        routing_pattern = f"cmd.{self.name.replace('.', '_')}.#"
        self.bus.subscribe(routing_pattern, self._on_command)
        print(f"   ✓ Subscribed to: {routing_pattern}")

        # Also subscribe to broadcast commands for agent type
        type_pattern = f"cmd.{self.agent_type}.#"
        if type_pattern != routing_pattern:
            self.bus.subscribe(type_pattern, self._on_command)
            print(f"   ✓ Subscribed to: {type_pattern}")

        self._running = True
        self._start_time = datetime.now()

        # Register with Node Registry
        if self._enable_registration:
            self._send_registration_event()
            self._start_heartbeat_thread()
            print(f"   ✓ Registered with Node Registry (heartbeat every {self._heartbeat_interval}s)")

        # Start Progress Heartbeat thread (AGENT_SPEC v1.0.3)
        if self._progress_enabled:
            self._start_progress_thread()
            print(f"   ✓ Progress Heartbeat enabled (interval every {self._progress_interval}s)")

        print(f"\n   Waiting for commands... (Ctrl+C to stop)\n")

        try:
            self.bus.start_consuming()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the agent and cleanup."""
        self._running = False

        # Stop Progress Heartbeat thread (AGENT_SPEC v1.0.3)
        if self._progress_enabled:
            self._stop_progress_thread()

        # Deregister from Node Registry
        if self._enable_registration:
            self._stop_heartbeat_thread()
            try:
                self._send_deregistration_event()
            except Exception as e:
                logger.warning(f"[{self.name}] Failed to send deregistration: {e}")

        self.bus.disconnect()

        # Release Singleton lock (AGENT_SPEC v1.0.4 Section 14.6)
        # Must be LAST to ensure agent is fully stopped before releasing
        if self._singleton_enabled:
            self._release_singleton_lock()

        uptime = ""
        if self._start_time:
            uptime = f" (uptime: {datetime.now() - self._start_time})"

        print(f"\n🛑 {self.name} stopped{uptime}")
        print(f"   Tasks processed: {self._tasks_processed}")
