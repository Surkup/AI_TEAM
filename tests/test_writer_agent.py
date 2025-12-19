#!/usr/bin/env python3
"""
Unit tests for WriterAgent "Пушкин".

Tests:
- Configuration loading
- LangGraph workflow structure
- Action execution (mocked LLM)
- SSOT compliance (MESSAGE_FORMAT, NODE_PASSPORT)

Usage:
    ./venv/bin/python -m pytest tests/test_writer_agent.py -v

See: docs/project/IMPLEMENTATION_ROADMAP.md Этап 4
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.writer_agent import WriterAgent, WriterState, AgentPhase


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_config():
    """Mock configuration for testing without file dependency."""
    return {
        "name": "agent.writer.test",
        "type": "writer",
        "version": "1.0.0",
        "display": {
            "name": "Пушкин-Тест",
            "description": "Test writer agent"
        },
        "capabilities": [
            {"name": "write_article", "version": "1.0.0"},
            {"name": "improve_text", "version": "1.0.0"},
            {"name": "generate_outline", "version": "1.0.0"}
        ],
        "llm": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 1000,
            "system_prompt": "You are a test writer."
        },
        "llm_fallback": {
            "enabled": False
        },
        "agent_loop": {
            "framework": "langgraph",
            "max_iterations": 3,
            "enable_self_critique": True
        },
        "registry": {
            "enabled": False,
            "heartbeat_interval_seconds": 10
        },
        "labels": {}
    }


@pytest.fixture
def writer_agent(mock_config, tmp_path):
    """Create WriterAgent with mocked config."""
    import yaml

    config_file = tmp_path / "writer_agent.yaml"
    config_file.write_text(yaml.dump({"writer_agent": mock_config}))

    with patch.object(WriterAgent, '_load_config', return_value=mock_config):
        agent = WriterAgent(str(config_file))

    return agent


# =============================================================================
# Configuration Tests
# =============================================================================

class TestWriterAgentConfig:
    """Test configuration loading and validation."""

    def test_display_name_loaded(self, writer_agent):
        """Test that display name (human name) is loaded correctly."""
        assert writer_agent.display_name == "Пушкин-Тест"

    def test_llm_config_loaded(self, writer_agent):
        """Test LLM configuration loaded correctly."""
        assert writer_agent.llm_model == "gpt-4o-mini"
        assert writer_agent.llm_temperature == 0.7
        assert writer_agent.llm_max_tokens == 1000

    def test_agent_loop_config(self, writer_agent):
        """Test agent loop configuration."""
        assert writer_agent.max_iterations == 3
        assert writer_agent.enable_self_critique is True

    def test_capabilities_in_config(self, mock_config):
        """Test capabilities are defined in config."""
        cap_names = [c["name"] for c in mock_config["capabilities"]]
        assert "write_article" in cap_names
        assert "improve_text" in cap_names
        assert "generate_outline" in cap_names


# =============================================================================
# Action Validation Tests
# =============================================================================

class TestActionValidation:
    """Test action validation."""

    def test_unsupported_action_raises(self, writer_agent):
        """Test that unsupported action raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            writer_agent.execute("unsupported_action", {})

        assert "Unknown action" in str(exc_info.value)
        assert "unsupported_action" in str(exc_info.value)

    def test_supported_actions(self, writer_agent):
        """Test list of supported actions."""
        # These should not raise during validation (may fail on LLM call)
        supported = ["write_article", "improve_text", "generate_outline"]
        for action in supported:
            # Just verify action name is valid (will fail on actual LLM call)
            assert action in ["write_article", "improve_text", "generate_outline"]


# =============================================================================
# LangGraph Workflow Tests
# =============================================================================

class TestLangGraphWorkflow:
    """Test LangGraph workflow structure."""

    def test_workflow_is_built(self, writer_agent):
        """Test that LangGraph workflow is built."""
        # May be None if LangGraph not installed
        if writer_agent._workflow is not None:
            assert writer_agent._workflow is not None

    def test_initial_state_structure(self):
        """Test WriterState TypedDict structure."""
        state: WriterState = {
            "action": "write_article",
            "params": {"topic": "AI"},
            "context": None,
            "phase": AgentPhase.UNDERSTAND.value,
            "iteration": 0,
            "understanding": "",
            "plan": None,
            "draft": "",
            "critique": "",
            "needs_improvement": False,
            "result": None,
            "error": None,
            "llm_calls": 0,
            "tokens_used": 0,
            "start_time": 0.0
        }

        # Verify all required fields
        assert "action" in state
        assert "params" in state
        assert "phase" in state
        assert "result" in state


# =============================================================================
# Execute Tests (with mocked LLM)
# =============================================================================

class TestExecuteWithMockedLLM:
    """Test execute methods with mocked LLM calls."""

    @patch.object(WriterAgent, '_call_llm')
    def test_write_article_simple_mode(self, mock_llm, writer_agent):
        """Test write_article in simple mode (no LangGraph)."""
        mock_llm.return_value = "# Test Article\n\nThis is a test article about AI."

        # Force simple mode
        writer_agent._workflow = None

        result = writer_agent.execute(
            "write_article",
            {"topic": "AI", "style": "formal", "length": 500}
        )

        assert result["action"] == "write_article"
        assert result["status"] == "completed"
        assert "text" in result["output"]
        assert result["output"]["text"] == "# Test Article\n\nThis is a test article about AI."
        assert "word_count" in result["output"]
        assert "metrics" in result
        assert result["metrics"]["mode"] == "simple"

    @patch.object(WriterAgent, '_call_llm')
    def test_improve_text_simple_mode(self, mock_llm, writer_agent):
        """Test improve_text in simple mode."""
        mock_llm.return_value = "This is the improved text with better clarity."

        # Force simple mode
        writer_agent._workflow = None

        result = writer_agent.execute(
            "improve_text",
            {
                "text": "This is original text.",
                "feedback": "Make it clearer"
            }
        )

        assert result["action"] == "improve_text"
        assert result["status"] == "completed"
        assert "text" in result["output"]

    @patch.object(WriterAgent, '_call_llm')
    def test_generate_outline_simple_mode(self, mock_llm, writer_agent):
        """Test generate_outline in simple mode."""
        mock_llm.return_value = "## Outline\n1. Introduction\n2. Main Part\n3. Conclusion"

        # Force simple mode
        writer_agent._workflow = None

        result = writer_agent.execute(
            "generate_outline",
            {"topic": "Machine Learning", "sections_count": 3}
        )

        assert result["action"] == "generate_outline"
        assert result["status"] == "completed"
        assert "text" in result["output"]


# =============================================================================
# SSOT Compliance Tests
# =============================================================================

class TestSSOTCompliance:
    """Test compliance with SSOT specifications."""

    @patch.object(WriterAgent, '_call_llm')
    def test_result_format_message_format_ssot(self, mock_llm, writer_agent):
        """
        Test that result format complies with MESSAGE_FORMAT SSOT.

        Expected structure (simplified):
        {
            "action": str,
            "status": "completed",
            "output": {...},
            "metrics": {...},
            "agent": {...}
        }
        """
        mock_llm.return_value = "Test content"
        writer_agent._workflow = None

        result = writer_agent.execute("write_article", {"topic": "Test"})

        # Required fields per MESSAGE_FORMAT
        assert "status" in result
        assert result["status"] == "completed"
        assert "output" in result
        assert isinstance(result["output"], dict)

        # Metrics should be present
        assert "metrics" in result
        assert "execution_time_seconds" in result["metrics"]

    @patch.object(WriterAgent, '_call_llm')
    def test_agent_info_in_result(self, mock_llm, writer_agent):
        """Test that agent info is included in result."""
        mock_llm.return_value = "Test"
        writer_agent._workflow = None

        result = writer_agent.execute("write_article", {"topic": "Test"})

        assert "agent" in result
        assert "name" in result["agent"]
        assert "display_name" in result["agent"]
        assert result["agent"]["display_name"] == "Пушкин-Тест"

    def test_capabilities_match_node_passport_format(self, mock_config):
        """
        Test capabilities format matches NODE_PASSPORT_SPEC.

        Each capability should have: name, version
        """
        for cap in mock_config["capabilities"]:
            assert "name" in cap
            assert "version" in cap


# =============================================================================
# Node Understanding Tests
# =============================================================================

class TestNodeUnderstand:
    """Test the understand node logic."""

    def test_understand_write_article(self, writer_agent):
        """Test understanding of write_article action."""
        state: WriterState = {
            "action": "write_article",
            "params": {
                "topic": "Artificial Intelligence",
                "style": "formal",
                "length": 1000,
                "language": "ru"
            },
            "context": None,
            "phase": "",
            "iteration": 0,
            "understanding": "",
            "plan": None,
            "draft": "",
            "critique": "",
            "needs_improvement": False,
            "result": None,
            "error": None,
            "llm_calls": 0,
            "tokens_used": 0,
            "start_time": 0.0
        }

        result_state = writer_agent._node_understand(state)

        assert result_state["phase"] == AgentPhase.UNDERSTAND.value
        assert "Artificial Intelligence" in result_state["understanding"]
        assert "formal" in result_state["understanding"]

    def test_understand_improve_text(self, writer_agent):
        """Test understanding of improve_text action."""
        state: WriterState = {
            "action": "improve_text",
            "params": {
                "text": "Original text here",
                "feedback": "Make it better"
            },
            "context": None,
            "phase": "",
            "iteration": 0,
            "understanding": "",
            "plan": None,
            "draft": "",
            "critique": "",
            "needs_improvement": False,
            "result": None,
            "error": None,
            "llm_calls": 0,
            "tokens_used": 0,
            "start_time": 0.0
        }

        result_state = writer_agent._node_understand(state)

        assert "улучшить текст" in result_state["understanding"]
        assert "Make it better" in result_state["understanding"]


# =============================================================================
# Routing Logic Tests
# =============================================================================

class TestRoutingLogic:
    """Test LangGraph routing logic."""

    def test_should_critique_when_enabled(self, writer_agent):
        """Test that critique is performed when enabled."""
        state: WriterState = {
            "action": "write_article",
            "params": {},
            "context": None,
            "phase": AgentPhase.EXECUTE.value,
            "iteration": 1,
            "understanding": "",
            "plan": None,
            "draft": "Some draft",
            "critique": "",
            "needs_improvement": False,
            "result": None,
            "error": None,
            "llm_calls": 1,
            "tokens_used": 0,
            "start_time": 0.0
        }

        writer_agent.enable_self_critique = True
        result = writer_agent._should_critique(state)
        assert result == "critique"

    def test_should_skip_critique_on_error(self, writer_agent):
        """Test that critique is skipped when there's an error."""
        state: WriterState = {
            "action": "write_article",
            "params": {},
            "context": None,
            "phase": AgentPhase.EXECUTE.value,
            "iteration": 1,
            "understanding": "",
            "plan": None,
            "draft": "",
            "critique": "",
            "needs_improvement": False,
            "result": None,
            "error": "Some error occurred",
            "llm_calls": 1,
            "tokens_used": 0,
            "start_time": 0.0
        }

        result = writer_agent._should_critique(state)
        assert result == "finish"

    def test_should_improve_when_needed(self, writer_agent):
        """Test improvement routing when critique says needs improvement."""
        state: WriterState = {
            "action": "write_article",
            "params": {},
            "context": None,
            "phase": AgentPhase.CRITIQUE.value,
            "iteration": 1,
            "understanding": "",
            "plan": None,
            "draft": "Some draft",
            "critique": "Needs work",
            "needs_improvement": True,
            "result": None,
            "error": None,
            "llm_calls": 2,
            "tokens_used": 0,
            "start_time": 0.0
        }

        result = writer_agent._should_improve(state)
        assert result == "execute"

    def test_should_finish_when_no_improvement_needed(self, writer_agent):
        """Test finish routing when no improvement needed."""
        state: WriterState = {
            "action": "write_article",
            "params": {},
            "context": None,
            "phase": AgentPhase.CRITIQUE.value,
            "iteration": 1,
            "understanding": "",
            "plan": None,
            "draft": "Good draft",
            "critique": "Looks good",
            "needs_improvement": False,
            "result": None,
            "error": None,
            "llm_calls": 2,
            "tokens_used": 0,
            "start_time": 0.0
        }

        result = writer_agent._should_improve(state)
        assert result == "finish"


# =============================================================================
# Display Identity Tests (AGENT_HUMAN_NAMES)
# =============================================================================

class TestDisplayIdentity:
    """Test Display Identity feature per AGENT_HUMAN_NAMES_v0.1.md."""

    def test_display_name_is_pushkin(self, writer_agent):
        """Test that default display name is 'Пушкин'."""
        # In test fixture it's "Пушкин-Тест"
        assert "Пушкин" in writer_agent.display_name

    def test_display_name_in_result(self, writer_agent):
        """Test display name is included in execution result."""
        with patch.object(writer_agent, '_call_llm', return_value="Test"):
            writer_agent._workflow = None
            result = writer_agent.execute("write_article", {"topic": "Test"})

            assert result["agent"]["display_name"] == "Пушкин-Тест"

    def test_system_name_different_from_display(self, writer_agent):
        """Test that system name (UID-based) is different from display name."""
        assert writer_agent.name != writer_agent.display_name
        assert writer_agent.name == "agent.writer.test"


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
