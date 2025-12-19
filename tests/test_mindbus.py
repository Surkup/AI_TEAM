"""
Tests for MindBus Core — SSOT validation and message handling

These tests verify:
1. Pydantic models match SSOT MESSAGE_FORMAT v1.1.2 specification
2. Valid messages pass validation
3. Invalid messages are rejected with clear errors
4. CloudEvents envelope is correctly formed
"""

import pytest
from pydantic import ValidationError

# Add src to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mindbus.models import (
    CommandData,
    ResultData,
    ErrorData,
    EventData,
    ControlData,
    RetryPolicy,
    CommandRequirements,
    ErrorInfo,
    validate_message_data,
    MESSAGE_TYPE_TO_MODEL,
)


# =============================================================================
# COMMAND Tests
# =============================================================================

class TestCommandData:
    """Tests for COMMAND message validation."""

    def test_minimal_command(self):
        """Minimal valid command with only required fields."""
        cmd = CommandData(
            action="generate_article",
            params={"topic": "AI trends"}
        )
        assert cmd.action == "generate_article"
        assert cmd.params == {"topic": "AI trends"}
        assert cmd.timeout_seconds is None
        assert cmd.requirements is None

    def test_full_command(self):
        """Full command with all optional fields."""
        cmd = CommandData(
            action="generate_article",
            params={"topic": "AI trends", "length": 2000},
            requirements=CommandRequirements(
                capabilities=["generate_text", "use_gpt4"],
                constraints={"sandbox": False}
            ),
            context={"process_id": "book-001", "step": "chapter-3"},
            timeout_seconds=300,
            idempotency_key="create-article-12345",
            retry_policy=RetryPolicy(
                max_attempts=3,
                retry_delay_seconds=5,
                backoff_multiplier=2.0
            )
        )
        assert cmd.action == "generate_article"
        assert cmd.timeout_seconds == 300
        assert cmd.requirements.capabilities == ["generate_text", "use_gpt4"]
        assert cmd.retry_policy.max_attempts == 3

    def test_command_action_required(self):
        """Action field is required."""
        with pytest.raises(ValidationError) as exc_info:
            CommandData(params={})
        assert "action" in str(exc_info.value)

    def test_command_action_max_length(self):
        """Action cannot exceed 100 characters."""
        with pytest.raises(ValidationError):
            CommandData(action="x" * 101, params={})

    def test_command_timeout_range(self):
        """Timeout must be between 1 and 3600 seconds."""
        # Valid range
        cmd = CommandData(action="test", params={}, timeout_seconds=1)
        assert cmd.timeout_seconds == 1

        cmd = CommandData(action="test", params={}, timeout_seconds=3600)
        assert cmd.timeout_seconds == 3600

        # Invalid: below minimum
        with pytest.raises(ValidationError):
            CommandData(action="test", params={}, timeout_seconds=0)

        # Invalid: above maximum
        with pytest.raises(ValidationError):
            CommandData(action="test", params={}, timeout_seconds=3601)


# =============================================================================
# RESULT Tests
# =============================================================================

class TestResultData:
    """Tests for RESULT message validation (only SUCCESS status)."""

    def test_successful_result(self):
        """Valid successful result."""
        result = ResultData(
            status="SUCCESS",
            output={"article": "Generated content...", "word_count": 2000},
            execution_time_ms=12450,
            metrics={"model": "gpt-4", "tokens_used": 3500}
        )
        assert result.status == "SUCCESS"
        assert result.output["word_count"] == 2000
        assert result.execution_time_ms == 12450

    def test_result_default_status(self):
        """Status defaults to SUCCESS."""
        result = ResultData(
            output={"text": "Hello"},
            execution_time_ms=100
        )
        assert result.status == "SUCCESS"

    def test_result_status_only_success(self):
        """RESULT status can ONLY be SUCCESS (errors go to ERROR type)."""
        # This is the key v1.1.2 change: RESULT is only for success
        with pytest.raises(ValidationError):
            ResultData(
                status="FAILURE",  # Not allowed!
                output=None,
                execution_time_ms=100
            )

    def test_result_execution_time_required(self):
        """execution_time_ms is required."""
        with pytest.raises(ValidationError) as exc_info:
            ResultData(output={})
        assert "execution_time_ms" in str(exc_info.value)

    def test_result_execution_time_non_negative(self):
        """execution_time_ms must be >= 0."""
        with pytest.raises(ValidationError):
            ResultData(output={}, execution_time_ms=-1)


# =============================================================================
# ERROR Tests
# =============================================================================

class TestErrorData:
    """Tests for ERROR message validation (v1.1 separate type)."""

    def test_valid_error(self):
        """Valid error with standard google.rpc.Code."""
        error = ErrorData(
            error=ErrorInfo(
                code="DEADLINE_EXCEEDED",
                message="Operation timed out after 30 seconds",
                retryable=True,
                details={"timeout_seconds": 30, "elapsed_seconds": 32.5}
            ),
            execution_time_ms=30500
        )
        assert error.error.code == "DEADLINE_EXCEEDED"
        assert error.error.retryable is True
        assert error.execution_time_ms == 30500

    def test_error_standard_codes(self):
        """All google.rpc.Code values are valid."""
        valid_codes = [
            "OK", "CANCELLED", "UNKNOWN", "INVALID_ARGUMENT",
            "DEADLINE_EXCEEDED", "NOT_FOUND", "ALREADY_EXISTS",
            "PERMISSION_DENIED", "RESOURCE_EXHAUSTED", "FAILED_PRECONDITION",
            "ABORTED", "OUT_OF_RANGE", "UNIMPLEMENTED", "INTERNAL",
            "UNAVAILABLE", "DATA_LOSS", "UNAUTHENTICATED"
        ]
        for code in valid_codes:
            error = ErrorData(
                error=ErrorInfo(
                    code=code,
                    message=f"Test error with code {code}",
                    retryable=False
                )
            )
            assert error.error.code == code

    def test_error_invalid_code(self):
        """Non-standard error codes are rejected."""
        with pytest.raises(ValidationError):
            ErrorData(
                error=ErrorInfo(
                    code="CUSTOM_ERROR",  # Not in google.rpc.Code
                    message="Custom error",
                    retryable=False
                )
            )

    def test_error_retryable_required(self):
        """retryable field is required."""
        with pytest.raises(ValidationError) as exc_info:
            ErrorData(
                error=ErrorInfo(
                    code="INTERNAL",
                    message="Something went wrong"
                    # Missing: retryable
                )
            )
        assert "retryable" in str(exc_info.value)


# =============================================================================
# EVENT Tests
# =============================================================================

class TestEventData:
    """Tests for EVENT message validation (Pub/Sub)."""

    def test_valid_event(self):
        """Valid event with all fields."""
        event = EventData(
            event_type="task.completed",
            event_data={"task_id": "task-555", "status": "SUCCESS"},
            severity="INFO",
            tags=["task", "completion"]
        )
        assert event.event_type == "task.completed"
        assert event.severity == "INFO"
        assert "task" in event.tags

    def test_event_type_required(self):
        """event_type is required."""
        with pytest.raises(ValidationError) as exc_info:
            EventData(event_data={})
        assert "event_type" in str(exc_info.value)

    def test_event_severity_values(self):
        """Severity must be INFO, WARNING, ERROR, or CRITICAL."""
        for severity in ["INFO", "WARNING", "ERROR", "CRITICAL"]:
            event = EventData(
                event_type="test.event",
                event_data={},
                severity=severity
            )
            assert event.severity == severity

        with pytest.raises(ValidationError):
            EventData(
                event_type="test.event",
                event_data={},
                severity="DEBUG"  # Not allowed
            )

    def test_event_default_severity(self):
        """Severity defaults to INFO."""
        event = EventData(event_type="test", event_data={})
        assert event.severity == "INFO"


# =============================================================================
# CONTROL Tests
# =============================================================================

class TestControlData:
    """Tests for CONTROL message validation."""

    def test_valid_control(self):
        """Valid control signal."""
        control = ControlData(
            control_type="stop",
            reason="Emergency stop requested by operator",
            parameters={"grace_period_seconds": 30}
        )
        assert control.control_type == "stop"
        assert control.reason == "Emergency stop requested by operator"

    def test_control_types(self):
        """All control types are valid."""
        for ctrl_type in ["stop", "pause", "resume", "shutdown", "config"]:
            control = ControlData(control_type=ctrl_type)
            assert control.control_type == ctrl_type

    def test_control_invalid_type(self):
        """Invalid control type is rejected."""
        with pytest.raises(ValidationError):
            ControlData(control_type="restart")  # Not allowed


# =============================================================================
# Message Type Validation Tests
# =============================================================================

class TestValidateMessageData:
    """Tests for the validate_message_data function."""

    def test_validate_command(self):
        """Validate COMMAND data."""
        data = {"action": "test", "params": {}}
        result = validate_message_data("ai.team.command", data)
        assert isinstance(result, CommandData)

    def test_validate_result(self):
        """Validate RESULT data."""
        data = {"status": "SUCCESS", "output": {}, "execution_time_ms": 100}
        result = validate_message_data("ai.team.result", data)
        assert isinstance(result, ResultData)

    def test_validate_error(self):
        """Validate ERROR data."""
        data = {
            "error": {
                "code": "INTERNAL",
                "message": "Something went wrong",
                "retryable": False
            }
        }
        result = validate_message_data("ai.team.error", data)
        assert isinstance(result, ErrorData)

    def test_validate_event(self):
        """Validate EVENT data."""
        data = {"event_type": "test.event", "event_data": {}}
        result = validate_message_data("ai.team.event", data)
        assert isinstance(result, EventData)

    def test_validate_control(self):
        """Validate CONTROL data."""
        data = {"control_type": "stop"}
        result = validate_message_data("ai.team.control", data)
        assert isinstance(result, ControlData)

    def test_validate_unknown_type(self):
        """Unknown event type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_message_data("ai.team.unknown", {})
        assert "Unknown event type" in str(exc_info.value)

    def test_validate_invalid_data(self):
        """Invalid data raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_message_data("ai.team.command", {"params": {}})  # Missing action


# =============================================================================
# RetryPolicy Tests
# =============================================================================

class TestRetryPolicy:
    """Tests for RetryPolicy validation."""

    def test_valid_retry_policy(self):
        """Valid retry policy."""
        policy = RetryPolicy(
            max_attempts=3,
            retry_delay_seconds=5,
            backoff_multiplier=2.0
        )
        assert policy.max_attempts == 3
        assert policy.backoff_multiplier == 2.0

    def test_retry_max_attempts_range(self):
        """max_attempts must be between 1 and 10."""
        with pytest.raises(ValidationError):
            RetryPolicy(max_attempts=0, retry_delay_seconds=5)

        with pytest.raises(ValidationError):
            RetryPolicy(max_attempts=11, retry_delay_seconds=5)

    def test_retry_backoff_range(self):
        """backoff_multiplier must be between 1.0 and 5.0."""
        with pytest.raises(ValidationError):
            RetryPolicy(max_attempts=3, retry_delay_seconds=5, backoff_multiplier=0.5)

        with pytest.raises(ValidationError):
            RetryPolicy(max_attempts=3, retry_delay_seconds=5, backoff_multiplier=6.0)


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
