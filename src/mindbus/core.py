"""
MindBus Core — Message bus integration using RabbitMQ + CloudEvents

This module provides the "glue" code that connects:
- RabbitMQ (via pika library) — message transport
- CloudEvents (via cloudevents library) — message envelope format
- Pydantic models — SSOT validation

We write ~150 lines of "glue" code, leveraging ~90,000 lines of ready-made solutions.
See: docs/project/IMPLEMENTATION_ROADMAP.md section "Ready-Made Solutions First"
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

import pika
from cloudevents.http import CloudEvent, to_json, from_json
from pydantic import ValidationError
import yaml

from .models import (
    MESSAGE_TYPE_TO_MODEL,
    CommandData,
    ResultData,
    ErrorData,
    EventData,
    ControlData,
    ErrorInfo,
    validate_message_data,
)

logger = logging.getLogger(__name__)


class MindBusConfig:
    """Configuration loader for MindBus (Zero Hardcoding principle)."""

    def __init__(self, config_path: str = "config/mindbus.yaml"):
        with open(config_path) as f:
            self._config = yaml.safe_load(f)
        self._mindbus = self._config.get("mindbus", {})

    @property
    def rabbitmq_host(self) -> str:
        return self._mindbus.get("rabbitmq", {}).get("host", "localhost")

    @property
    def rabbitmq_port(self) -> int:
        return self._mindbus.get("rabbitmq", {}).get("port", 5672)

    @property
    def rabbitmq_username(self) -> str:
        env_var = self._mindbus.get("rabbitmq", {}).get("username_env", "RABBITMQ_USER")
        default = self._mindbus.get("rabbitmq", {}).get("default_username", "guest")
        return os.getenv(env_var, default)

    @property
    def rabbitmq_password(self) -> str:
        env_var = self._mindbus.get("rabbitmq", {}).get("password_env", "RABBITMQ_PASSWORD")
        default = self._mindbus.get("rabbitmq", {}).get("default_password", "guest")
        return os.getenv(env_var, default)

    @property
    def exchange_name(self) -> str:
        return self._mindbus.get("exchange", {}).get("name", "ai_team")

    @property
    def exchange_type(self) -> str:
        return self._mindbus.get("exchange", {}).get("type", "topic")

    def get_priority(self, message_type: str) -> int:
        """Get priority for message type from config."""
        priorities = self._mindbus.get("priorities", {})
        # Extract type suffix: ai.team.command -> command
        type_suffix = message_type.split(".")[-1] if "." in message_type else message_type
        return priorities.get(type_suffix, 20)

    @property
    def validation_strict_mode(self) -> bool:
        return self._mindbus.get("validation", {}).get("strict_mode", True)

    @property
    def connection_heartbeat_seconds(self) -> int:
        """Heartbeat timeout for RabbitMQ connection (Zero Hardcoding principle)."""
        return self._mindbus.get("connection", {}).get("heartbeat_seconds", 300)

    @property
    def connection_blocked_timeout_seconds(self) -> int:
        """Blocked connection timeout for RabbitMQ (Zero Hardcoding principle)."""
        return self._mindbus.get("connection", {}).get("blocked_connection_timeout_seconds", 300)


class MindBus:
    """
    MindBus Core — the messaging backbone of AI_TEAM.

    This class integrates:
    - RabbitMQ for message transport (AMQP 0-9-1)
    - CloudEvents for message envelope format (CNCF standard)
    - Pydantic for SSOT validation

    Usage:
        bus = MindBus()
        bus.connect()

        # Send a command
        bus.send_command(
            action="generate_article",
            params={"topic": "AI trends"},
            target="writer",
            source="orchestrator"
        )

        # Subscribe to messages
        bus.subscribe("cmd.writer.*", callback_function)

        # Start consuming
        bus.start_consuming()
    """

    def __init__(self, config_path: str = "config/mindbus.yaml"):
        self.config = MindBusConfig(config_path)
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel: Optional[pika.channel.Channel] = None
        self._callbacks: Dict[str, Callable] = {}

    def connect(self) -> None:
        """Establish connection to RabbitMQ."""
        credentials = pika.PlainCredentials(
            self.config.rabbitmq_username,
            self.config.rabbitmq_password
        )
        parameters = pika.ConnectionParameters(
            host=self.config.rabbitmq_host,
            port=self.config.rabbitmq_port,
            credentials=credentials,
            # Heartbeat and blocked connection timeouts from config (Zero Hardcoding principle)
            # See: config/mindbus.yaml section "connection"
            heartbeat=self.config.connection_heartbeat_seconds,
            blocked_connection_timeout=self.config.connection_blocked_timeout_seconds,
        )
        self._connection = pika.BlockingConnection(parameters)
        self._channel = self._connection.channel()

        # Declare exchange
        self._channel.exchange_declare(
            exchange=self.config.exchange_name,
            exchange_type=self.config.exchange_type,
            durable=True,
        )
        logger.info(f"Connected to RabbitMQ at {self.config.rabbitmq_host}:{self.config.rabbitmq_port}")

    def disconnect(self) -> None:
        """Close connection to RabbitMQ."""
        if self._connection and self._connection.is_open:
            self._connection.close()
            logger.info("Disconnected from RabbitMQ")

    def _create_cloud_event(
        self,
        event_type: str,
        source: str,
        data: Dict[str, Any],
        subject: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> CloudEvent:
        """Create a CloudEvents envelope for the message."""
        attributes = {
            "type": event_type,
            "source": source,
            "subject": subject,
            "time": datetime.utcnow().isoformat() + "Z",
        }
        if trace_id:
            attributes["traceparent"] = trace_id

        return CloudEvent(attributes, data)

    def _validate_and_send(
        self,
        event_type: str,
        source: str,
        data: Dict[str, Any],
        routing_key: str,
        subject: Optional[str] = None,
        trace_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> str:
        """Validate message data and send to RabbitMQ.

        Args:
            event_type: CloudEvents type (e.g., 'ai.team.command')
            source: Who is sending (CloudEvents source)
            data: Message payload
            routing_key: AMQP routing key
            subject: Business entity ID (Task ID)
            trace_id: W3C Trace Context traceparent
            correlation_id: Correlation ID for request-response linking
            reply_to: Queue name for RPC response (for COMMAND messages)

        Returns:
            Event ID
        """
        # Validate data against SSOT schema
        try:
            validate_message_data(event_type, data)
        except ValidationError as e:
            logger.error(f"SSOT validation failed: {e}")
            raise ValueError(f"Message data validation failed: {e}")

        # Create CloudEvent
        event = self._create_cloud_event(
            event_type=event_type,
            source=source,
            data=data,
            subject=subject,
            trace_id=trace_id,
        )

        # Serialize to JSON
        message_body = to_json(event)
        event_id = event["id"]

        # Set AMQP properties
        properties = pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,  # Persistent
            priority=self.config.get_priority(event_type),
            correlation_id=correlation_id or event_id,  # Use event_id if not provided
            message_id=event_id,
            reply_to=reply_to,  # Queue for RPC response
        )

        # Publish to RabbitMQ
        self._channel.basic_publish(
            exchange=self.config.exchange_name,
            routing_key=routing_key,
            body=message_body,
            properties=properties,
        )

        logger.info(f"Sent {event_type} to {routing_key} (id={event_id})")
        return event_id

    def _send_rpc_response(
        self,
        event_type: str,
        source: str,
        data: Dict[str, Any],
        reply_to: str,
        correlation_id: str,
        subject: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        """Send RPC response directly to reply_to queue (for RESULT/ERROR).

        Per MindBus Protocol v1.0.1:
        - RESULT and ERROR use RPC reply-to pattern
        - Message is sent to the queue specified in reply_to (from incoming COMMAND)
        - Uses default exchange ("") with routing_key = queue_name

        Args:
            event_type: CloudEvents type (ai.team.result or ai.team.error)
            source: Who is sending (CloudEvents source)
            data: Message payload
            reply_to: Queue name to send response to
            correlation_id: Correlation ID for request-response linking
            subject: Business entity ID (Task ID)
            trace_id: W3C Trace Context traceparent

        Returns:
            Event ID
        """
        # Validate data against SSOT schema
        try:
            validate_message_data(event_type, data)
        except ValidationError as e:
            logger.error(f"SSOT validation failed: {e}")
            raise ValueError(f"Message data validation failed: {e}")

        # Create CloudEvent
        event = self._create_cloud_event(
            event_type=event_type,
            source=source,
            data=data,
            subject=subject,
            trace_id=trace_id,
        )

        # Serialize to JSON
        message_body = to_json(event)
        event_id = event["id"]

        # Set AMQP properties for RPC response
        properties = pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,  # Persistent
            priority=self.config.get_priority(event_type),
            correlation_id=correlation_id,
            message_id=event_id,
        )

        # Publish directly to reply_to queue using default exchange ("")
        # In AMQP, publishing to "" exchange with routing_key=queue_name
        # delivers directly to that queue
        self._channel.basic_publish(
            exchange="",  # Default exchange for direct queue delivery
            routing_key=reply_to,  # Queue name from incoming COMMAND
            body=message_body,
            properties=properties,
        )

        logger.info(f"Sent {event_type} to reply_to={reply_to} (id={event_id}, correlation={correlation_id})")
        return event_id

    def send_command(
        self,
        action: str,
        params: Dict[str, Any],
        target: str,
        source: str,
        target_id: str = "any",
        subject: Optional[str] = None,
        trace_id: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        requirements: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        reply_to: Optional[str] = None,
    ) -> str:
        """Send a COMMAND message to an agent.

        Per MindBus Protocol v1.0.1:
        - Commands are sent via routing key: cmd.{role}.{agent_id}
        - reply_to specifies the queue where RESULT/ERROR should be sent
        - correlation_id is automatically set to event_id for request-response linking

        Args:
            action: Action to execute (e.g., 'generate_article', 'review_code')
            params: Action parameters (structure depends on action)
            target: Target agent role (e.g., 'writer', 'coder')
            source: Who is sending (CloudEvents source) — e.g. 'orchestrator-core'
            target_id: Specific agent ID or 'any' for round-robin
            subject: Business entity ID (Task ID)
            trace_id: W3C Trace Context traceparent
            timeout_seconds: Execution timeout in seconds
            requirements: Requirements for the executing node (capabilities, constraints)
            context: Business context (process_id, step, etc.)
            reply_to: Queue for RPC response (RESULT/ERROR will be sent here)

        Returns:
            Event ID (also used as correlation_id)

        Example:
            # Orchestrator sends command and waits for response
            event_id = bus.send_command(
                action="generate_article",
                params={"topic": "AI trends"},
                target="writer",
                source="orchestrator-core",
                reply_to="orchestrator.responses"  # Queue for responses
            )
        """
        data = {
            "action": action,
            "params": params,
        }
        if timeout_seconds:
            data["timeout_seconds"] = timeout_seconds
        if requirements:
            data["requirements"] = requirements
        if context:
            data["context"] = context

        routing_key = f"cmd.{target}.{target_id}"
        return self._validate_and_send(
            event_type="ai.team.command",
            source=source,
            data=data,
            routing_key=routing_key,
            subject=subject,
            trace_id=trace_id,
            reply_to=reply_to,
        )

    def send_result(
        self,
        output: Dict[str, Any],
        execution_time_ms: int,
        source: str,
        reply_to: str,
        correlation_id: str,
        subject: Optional[str] = None,
        trace_id: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Send a RESULT message (successful execution) via RPC reply-to pattern.

        Per MindBus Protocol v1.0.1, RESULT messages are sent directly to the
        reply_to queue specified in the original COMMAND's AMQP properties,
        NOT via routing keys.

        Args:
            output: Execution result (structure depends on action)
            execution_time_ms: Actual execution time in milliseconds
            source: Who is sending (CloudEvents source) — e.g. 'agent.writer.001'
            reply_to: Reply queue from incoming COMMAND (AMQP reply_to property)
            correlation_id: Correlation ID from incoming COMMAND (for request-response linking)
            subject: Business entity ID (Task ID)
            trace_id: W3C Trace Context traceparent
            metrics: Execution metrics (model, tokens, cost, etc.)

        Returns:
            Event ID

        Example:
            # In agent callback after processing COMMAND:
            bus.send_result(
                output={"article": "Generated content..."},
                execution_time_ms=1500,
                source="agent.writer.001",
                reply_to=properties.reply_to,      # From incoming COMMAND
                correlation_id=properties.correlation_id  # From incoming COMMAND
            )
        """
        data = {
            "status": "SUCCESS",
            "output": output,
            "execution_time_ms": execution_time_ms,
        }
        if metrics:
            data["metrics"] = metrics

        return self._send_rpc_response(
            event_type="ai.team.result",
            source=source,
            data=data,
            reply_to=reply_to,
            correlation_id=correlation_id,
            subject=subject,
            trace_id=trace_id,
        )

    def send_error(
        self,
        code: str,
        message: str,
        retryable: bool,
        source: str,
        reply_to: str,
        correlation_id: str,
        subject: Optional[str] = None,
        trace_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        execution_time_ms: Optional[int] = None,
    ) -> str:
        """Send an ERROR message via RPC reply-to pattern.

        Per MindBus Protocol v1.0.1, ERROR messages are sent directly to the
        reply_to queue specified in the original COMMAND's AMQP properties,
        NOT via routing keys. This follows the same RPC pattern as RESULT.

        Args:
            code: Standard error code (google.rpc.Code) — e.g. 'INVALID_ARGUMENT', 'INTERNAL'
            message: Human-readable error description
            retryable: Whether the operation can be safely retried
            source: Who is sending (CloudEvents source) — e.g. 'agent.writer.001'
            reply_to: Reply queue from incoming COMMAND (AMQP reply_to property)
            correlation_id: Correlation ID from incoming COMMAND (for request-response linking)
            subject: Business entity ID (Task ID)
            trace_id: W3C Trace Context traceparent
            details: Additional error details (domain-specific)
            execution_time_ms: Time until error occurred (if applicable)

        Returns:
            Event ID

        Example:
            # In agent callback when error occurs:
            bus.send_error(
                code="INVALID_ARGUMENT",
                message="Topic parameter is required",
                retryable=False,
                source="agent.writer.001",
                reply_to=properties.reply_to,      # From incoming COMMAND
                correlation_id=properties.correlation_id  # From incoming COMMAND
            )
        """
        data = {
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
            }
        }
        if details:
            data["error"]["details"] = details
        if execution_time_ms is not None:
            data["execution_time_ms"] = execution_time_ms

        return self._send_rpc_response(
            event_type="ai.team.error",
            source=source,
            data=data,
            reply_to=reply_to,
            correlation_id=correlation_id,
            subject=subject,
            trace_id=trace_id,
        )

    def send_event(
        self,
        topic: str,
        event_type_suffix: str,
        event_data: Dict[str, Any],
        source: str,
        subject: Optional[str] = None,
        trace_id: Optional[str] = None,
        severity: str = "INFO",
        tags: Optional[list] = None,
    ) -> str:
        """Send an EVENT message (Pub/Sub notification).

        Args:
            topic: О ЧЁМ событие (routing key topic) — например 'task', 'registry', 'process'
            event_type_suffix: ТИП события — например 'completed', 'failed', 'node_registered'
            event_data: Данные события
            source: КТО отправляет (CloudEvents source) — например 'orchestrator-core'
            subject: ID бизнес-сущности (Task ID)
            trace_id: W3C Trace Context
            severity: Уровень важности (INFO, WARNING, ERROR, CRITICAL)
            tags: Теги для фильтрации

        Returns:
            Event ID

        Example:
            # Событие о завершении задачи
            bus.send_event(
                topic="task",
                event_type_suffix="completed",
                event_data={"task_id": "123", "duration": 45},
                source="agent.writer.001"
            )
            # → routing_key = 'evt.task.completed'
            # → CloudEvents source = 'agent.writer.001'
        """
        # Формируем event_type для data payload (полный формат)
        full_event_type = f"{topic}.{event_type_suffix}"

        data = {
            "event_type": full_event_type,
            "event_data": event_data,
            "severity": severity,
        }
        if tags:
            data["tags"] = tags

        # Routing key по протоколу: evt.{topic}.{event_type}
        # Описывает О ЧЁМ событие (тема), а НЕ "от кого"
        # "От кого" указывается в CloudEvents source
        routing_key = f"evt.{topic}.{event_type_suffix}"

        return self._validate_and_send(
            event_type="ai.team.event",
            source=source,
            data=data,
            routing_key=routing_key,
            subject=subject,
            trace_id=trace_id,
        )

    def send_control(
        self,
        control_type: str,
        target: str = "all",
        source: str = "operator",
        reason: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Send a CONTROL signal (highest priority)."""
        data = {
            "control_type": control_type,
        }
        if reason:
            data["reason"] = reason
        if parameters:
            data["parameters"] = parameters

        routing_key = f"ctl.{target}.{control_type}"
        return self._validate_and_send(
            event_type="ai.team.control",
            source=source,
            data=data,
            routing_key=routing_key,
        )

    def subscribe(
        self,
        routing_pattern: str,
        callback: Callable[[CloudEvent, Dict[str, Any]], None],
        queue_name: Optional[str] = None,
    ) -> str:
        """
        Subscribe to messages matching a routing pattern.

        Args:
            routing_pattern: AMQP routing key pattern (e.g., "cmd.writer.*")
            callback: Function to call with (cloud_event, validated_data)
            queue_name: Optional queue name (auto-generated if not provided)

        Returns:
            Queue name
        """
        if queue_name is None:
            queue_name = f"mindbus.{routing_pattern.replace('*', 'any').replace('.', '_')}.{uuid4().hex[:8]}"

        # Declare queue
        self._channel.queue_declare(queue=queue_name, durable=True)

        # Bind queue to exchange with routing pattern
        self._channel.queue_bind(
            exchange=self.config.exchange_name,
            queue=queue_name,
            routing_key=routing_pattern,
        )

        def on_message(ch, method, properties, body):
            try:
                # Parse CloudEvent
                event = from_json(body)
                event_type = event["type"]
                data = event.data

                # Build event dict from CloudEvent attributes for callback access
                # (CloudEvent object cannot be converted with dict() directly)
                event_dict = {
                    "id": event["id"],
                    "type": event["type"],
                    "source": event["source"],
                    "subject": event.get("subject"),
                    "time": event.get("time"),
                    "traceparent": event.get("traceparent"),
                }
                # Add AMQP properties (not in CloudEvent)
                if properties.correlation_id:
                    event_dict["correlationid"] = properties.correlation_id
                if properties.reply_to:
                    event_dict["reply_to"] = properties.reply_to

                # Validate against SSOT
                if self.config.validation_strict_mode:
                    validated_data = validate_message_data(event_type, data)
                    callback(event_dict, validated_data.model_dump())
                else:
                    callback(event_dict, data)

                # Acknowledge message
                ch.basic_ack(delivery_tag=method.delivery_tag)

            except ValidationError as e:
                logger.error(f"SSOT validation failed for incoming message: {e}")
                # NACK without requeue -> goes to DLQ
                try:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                except Exception as nack_err:
                    logger.warning(f"Failed to NACK message (channel may be closed): {nack_err}")

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                try:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                except Exception as nack_err:
                    logger.warning(f"Failed to NACK message (channel may be closed): {nack_err}")

        self._channel.basic_consume(queue=queue_name, on_message_callback=on_message)
        self._callbacks[routing_pattern] = callback

        logger.info(f"Subscribed to {routing_pattern} via queue {queue_name}")
        return queue_name

    def subscribe_queue(
        self,
        queue_name: str,
        callback: Callable[[CloudEvent, Dict[str, Any]], None],
    ) -> str:
        """
        Subscribe to a direct queue (for RPC replies, no exchange binding).

        This is used for receiving RESULT/ERROR messages sent via reply_to pattern.
        The queue is declared but not bound to any exchange - messages are sent
        directly to the queue using the default exchange.

        Args:
            queue_name: Queue name to subscribe to
            callback: Function to call with (cloud_event, validated_data)

        Returns:
            Queue name
        """
        # Declare queue (no exchange binding - direct delivery)
        self._channel.queue_declare(queue=queue_name, durable=True)

        def on_message(ch, method, properties, body):
            try:
                # Parse CloudEvent
                event = from_json(body)
                event_type = event["type"]
                data = event.data

                # Build event dict
                event_dict = {
                    "id": event["id"],
                    "type": event_type,
                    "source": event["source"],
                    "subject": event.get("subject"),
                    "time": event.get("time"),
                    "correlation_id": event.get("correlationid"),
                    "traceparent": event.get("traceparent"),
                    "reply_to": properties.reply_to if properties else None,
                }

                # Call the callback
                callback(event_dict, data)
                ch.basic_ack(delivery_tag=method.delivery_tag)

            except Exception as e:
                logger.error(f"Error processing direct queue message: {e}")
                try:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                except Exception as nack_err:
                    logger.warning(f"Failed to NACK message (channel may be closed): {nack_err}")

        self._channel.basic_consume(queue=queue_name, on_message_callback=on_message)
        self._callbacks[f"direct:{queue_name}"] = callback

        logger.info(f"Subscribed to direct queue {queue_name}")
        return queue_name

    def start_consuming(self) -> None:
        """Start consuming messages (blocking)."""
        logger.info("Starting to consume messages...")
        try:
            self._channel.start_consuming()
        except KeyboardInterrupt:
            self._channel.stop_consuming()
            logger.info("Stopped consuming messages")

    def stop_consuming(self) -> None:
        """Stop consuming messages."""
        if self._channel:
            self._channel.stop_consuming()
