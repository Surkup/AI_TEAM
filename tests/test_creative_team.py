#!/usr/bin/env python3
"""
Tests for Creative Team (Этап 4).

Tests:
- Agent configuration loading
- Agent instantiation
- Team creation
- Rollcall functionality
- Action validation
- Basic workflow (without real LLM)
"""

import pytest
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


# =============================================================================
# Test Configuration Loading
# =============================================================================

class TestConfigLoading:
    """Тесты загрузки конфигураций агентов."""

    @pytest.fixture
    def config_dir(self):
        return Path("config/agents")

    def test_researcher_config_exists(self, config_dir):
        """Конфиг Исследователя существует."""
        assert (config_dir / "researcher_agent.yaml").exists()

    def test_ideator_config_exists(self, config_dir):
        """Конфиг Генератора идей существует."""
        assert (config_dir / "ideator_agent.yaml").exists()

    def test_critic_config_exists(self, config_dir):
        """Конфиг Критика существует."""
        assert (config_dir / "critic_agent.yaml").exists()

    def test_editor_config_exists(self, config_dir):
        """Конфиг Редактора существует."""
        assert (config_dir / "editor_agent.yaml").exists()

    def test_researcher_config_valid(self, config_dir):
        """Конфиг Исследователя валиден."""
        with open(config_dir / "researcher_agent.yaml") as f:
            config = yaml.safe_load(f)

        agent = config["researcher_agent"]
        assert agent["type"] == "researcher"
        assert "display" in agent
        assert agent["display"]["name"] == "Исследователь"
        assert len(agent["capabilities"]) == 4
        assert "system_prompt" in agent["llm"]

    def test_ideator_config_valid(self, config_dir):
        """Конфиг Генератора идей валиден."""
        with open(config_dir / "ideator_agent.yaml") as f:
            config = yaml.safe_load(f)

        agent = config["ideator_agent"]
        assert agent["type"] == "ideator"
        assert agent["display"]["name"] == "Генератор идей"
        assert agent["llm"]["temperature"] == 0.9  # Высокая для креативности

    def test_critic_config_valid(self, config_dir):
        """Конфиг Критика валиден."""
        with open(config_dir / "critic_agent.yaml") as f:
            config = yaml.safe_load(f)

        agent = config["critic_agent"]
        assert agent["type"] == "critic"
        assert agent["display"]["name"] == "Критик"
        assert len(agent["capabilities"]) == 5

    def test_editor_config_valid(self, config_dir):
        """Конфиг Редактора валиден."""
        with open(config_dir / "editor_agent.yaml") as f:
            config = yaml.safe_load(f)

        agent = config["editor_agent"]
        assert agent["type"] == "editor"
        assert agent["display"]["name"] == "Редактор"
        assert len(agent["capabilities"]) == 6


# =============================================================================
# Test Agent Instantiation
# =============================================================================

class TestAgentInstantiation:
    """Тесты создания экземпляров агентов."""

    def test_researcher_instantiation(self):
        """Исследователь создаётся корректно."""
        from src.agents.creative_agent import ResearcherAgent

        agent = ResearcherAgent()
        assert agent.display_name == "Исследователь"
        assert agent.agent_type == "researcher"
        assert agent.llm_temperature == 0.3
        assert agent.display_avatar == "🔍"

    def test_ideator_instantiation(self):
        """Генератор идей создаётся корректно."""
        from src.agents.creative_agent import IdeatorAgent

        agent = IdeatorAgent()
        assert agent.display_name == "Генератор идей"
        assert agent.agent_type == "ideator"
        assert agent.llm_temperature == 0.9
        assert agent.display_avatar == "💡"

    def test_critic_instantiation(self):
        """Критик создаётся корректно."""
        from src.agents.creative_agent import CriticAgent

        agent = CriticAgent()
        assert agent.display_name == "Критик"
        assert agent.agent_type == "critic"
        assert agent.llm_temperature == 0.4
        assert agent.display_avatar == "🎯"

    def test_editor_instantiation(self):
        """Редактор создаётся корректно."""
        from src.agents.creative_agent import EditorAgent

        agent = EditorAgent()
        assert agent.display_name == "Редактор"
        assert agent.agent_type == "editor"
        assert agent.llm_temperature == 0.5
        assert agent.display_avatar == "✨"


# =============================================================================
# Test Team Creation
# =============================================================================

class TestTeamCreation:
    """Тесты создания команды."""

    def test_create_creative_team(self):
        """Команда создаётся с 4 агентами."""
        from src.agents.creative_agent import create_creative_team

        team = create_creative_team()
        assert len(team) == 4
        assert "researcher" in team
        assert "ideator" in team
        assert "critic" in team
        assert "editor" in team

    def test_team_agents_are_correct_types(self):
        """Агенты команды имеют правильные типы."""
        from src.agents.creative_agent import (
            create_creative_team,
            ResearcherAgent,
            IdeatorAgent,
            CriticAgent,
            EditorAgent
        )

        team = create_creative_team()
        assert isinstance(team["researcher"], ResearcherAgent)
        assert isinstance(team["ideator"], IdeatorAgent)
        assert isinstance(team["critic"], CriticAgent)
        assert isinstance(team["editor"], EditorAgent)


# =============================================================================
# Test Rollcall
# =============================================================================

class TestRollcall:
    """Тесты функции переклички."""

    def test_team_rollcall_returns_string(self):
        """Перекличка возвращает строку."""
        from src.agents.creative_agent import create_creative_team, team_rollcall

        team = create_creative_team()
        rollcall = team_rollcall(team)
        assert isinstance(rollcall, str)

    def test_team_rollcall_contains_all_agents(self):
        """Перекличка содержит всех агентов."""
        from src.agents.creative_agent import create_creative_team, team_rollcall

        team = create_creative_team()
        rollcall = team_rollcall(team)

        assert "Исследователь" in rollcall
        assert "Генератор идей" in rollcall
        assert "Критик" in rollcall
        assert "Редактор" in rollcall

    def test_team_rollcall_contains_avatars(self):
        """Перекличка содержит аватары."""
        from src.agents.creative_agent import create_creative_team, team_rollcall

        team = create_creative_team()
        rollcall = team_rollcall(team)

        assert "🔍" in rollcall
        assert "💡" in rollcall
        assert "🎯" in rollcall
        assert "✨" in rollcall

    def test_introduce_method(self):
        """Метод introduce() работает."""
        from src.agents.creative_agent import ResearcherAgent

        agent = ResearcherAgent()
        intro = agent.introduce()

        assert "Исследователь" in intro
        assert "🔍" in intro
        assert "Роль:" in intro


# =============================================================================
# Test Action Validation
# =============================================================================

class TestActionValidation:
    """Тесты валидации действий."""

    def test_researcher_valid_actions(self):
        """Исследователь поддерживает правильные действия."""
        from src.agents.creative_agent import ResearcherAgent

        agent = ResearcherAgent()
        capabilities = agent.config.get("capabilities", [])
        action_names = [cap["name"] for cap in capabilities]

        assert "research_topic" in action_names
        assert "analyze_market" in action_names
        assert "analyze_audience" in action_names
        assert "fact_check" in action_names

    def test_researcher_rejects_unknown_action(self):
        """Исследователь отклоняет неизвестное действие."""
        from src.agents.creative_agent import ResearcherAgent

        agent = ResearcherAgent()

        with pytest.raises(ValueError) as exc_info:
            agent.execute("unknown_action", {})

        assert "Unknown action" in str(exc_info.value)
        assert "research_topic" in str(exc_info.value)

    def test_critic_valid_actions(self):
        """Критик поддерживает правильные действия."""
        from src.agents.creative_agent import CriticAgent

        agent = CriticAgent()
        capabilities = agent.config.get("capabilities", [])
        action_names = [cap["name"] for cap in capabilities]

        assert "review_content" in action_names
        assert "evaluate_idea" in action_names
        assert "find_weaknesses" in action_names
        assert "suggest_improvements" in action_names
        assert "compare_options" in action_names

    def test_ideator_valid_actions(self):
        """Генератор идей поддерживает правильные действия."""
        from src.agents.creative_agent import IdeatorAgent

        agent = IdeatorAgent()
        capabilities = agent.config.get("capabilities", [])
        action_names = [cap["name"] for cap in capabilities]

        assert "generate_ideas" in action_names
        assert "brainstorm" in action_names
        assert "develop_concept" in action_names
        assert "combine_ideas" in action_names

    def test_editor_valid_actions(self):
        """Редактор поддерживает правильные действия."""
        from src.agents.creative_agent import EditorAgent

        agent = EditorAgent()
        capabilities = agent.config.get("capabilities", [])
        action_names = [cap["name"] for cap in capabilities]

        assert "edit_content" in action_names
        assert "polish_style" in action_names
        assert "fix_errors" in action_names
        assert "restructure" in action_names
        assert "adapt_audience" in action_names
        assert "finalize" in action_names


# =============================================================================
# Test Process Card
# =============================================================================

class TestProcessCard:
    """Тесты Process Card creative_project."""

    @pytest.fixture
    def process_card(self):
        with open("config/process_cards/creative_project.yaml") as f:
            return yaml.safe_load(f)

    def test_process_card_exists(self):
        """Process Card существует."""
        assert Path("config/process_cards/creative_project.yaml").exists()

    def test_process_card_has_required_fields(self, process_card):
        """Process Card имеет обязательные поля."""
        assert "name" in process_card
        assert "version" in process_card
        assert "steps" in process_card
        assert "input" in process_card
        assert "output" in process_card

    def test_process_card_has_7_steps(self, process_card):
        """Process Card имеет 7 шагов."""
        assert len(process_card["steps"]) == 7

    def test_process_card_steps_have_correct_agents(self, process_card):
        """Шаги Process Card используют правильных агентов."""
        agent_roles = [step["agent_role"] for step in process_card["steps"]]

        assert "researcher" in agent_roles
        assert "ideator" in agent_roles
        assert "critic" in agent_roles
        assert "editor" in agent_roles
        assert "writer" in agent_roles

    def test_process_card_has_project_types(self, process_card):
        """Process Card поддерживает типы проектов."""
        project_types = process_card["input"]["project_type"]["enum"]

        assert "scenario" in project_types
        assert "business_plan" in project_types
        assert "book_plot" in project_types
        assert "product_concept" in project_types
        assert "marketing" in project_types

    def test_process_card_has_error_handling(self, process_card):
        """Process Card имеет обработку ошибок."""
        assert "error_handling" in process_card
        assert "on_step_failure" in process_card["error_handling"]
        assert "on_timeout" in process_card["error_handling"]

    def test_process_card_has_limits(self, process_card):
        """Process Card имеет лимиты."""
        assert "limits" in process_card
        assert process_card["limits"]["max_total_time_seconds"] == 900
        assert process_card["limits"]["max_cost_usd"] == 2.00


# =============================================================================
# Test System Prompts
# =============================================================================

class TestSystemPrompts:
    """Тесты системных промптов."""

    def test_researcher_system_prompt_has_role(self):
        """System prompt Исследователя содержит описание роли."""
        from src.agents.creative_agent import ResearcherAgent

        agent = ResearcherAgent()
        prompt = agent.system_prompt

        assert "Исследователь" in prompt
        assert "команде" in prompt.lower() or "команда" in prompt.lower()

    def test_ideator_system_prompt_has_creativity(self):
        """System prompt Генератора идей содержит креативные методы."""
        from src.agents.creative_agent import IdeatorAgent

        agent = IdeatorAgent()
        prompt = agent.system_prompt

        assert "SCAMPER" in prompt or "креатив" in prompt.lower()

    def test_critic_system_prompt_has_evaluation(self):
        """System prompt Критика содержит критерии оценки."""
        from src.agents.creative_agent import CriticAgent

        agent = CriticAgent()
        prompt = agent.system_prompt

        assert "оцен" in prompt.lower()
        assert "1-10" in prompt or "баллов" in prompt.lower()

    def test_editor_system_prompt_has_preservation(self):
        """System prompt Редактора содержит сохранение авторского голоса."""
        from src.agents.creative_agent import EditorAgent

        agent = EditorAgent()
        prompt = agent.system_prompt

        assert "голос" in prompt.lower() or "стиль" in prompt.lower()


# =============================================================================
# Test Tools Configuration
# =============================================================================

class TestToolsConfiguration:
    """Тесты конфигурации инструментов."""

    def test_researcher_has_web_search(self):
        """Исследователь имеет web_search."""
        from src.agents.creative_agent import ResearcherAgent

        agent = ResearcherAgent()
        tools_config = agent.config.get("tools", {})
        enabled_tools = tools_config.get("enabled", [])

        assert "web_search" in enabled_tools

    def test_researcher_has_research_enabled(self):
        """У Исследователя включён research."""
        from src.agents.creative_agent import ResearcherAgent

        agent = ResearcherAgent()
        assert agent.enable_research is True

    def test_ideator_no_web_search(self):
        """У Генератора идей нет web_search."""
        from src.agents.creative_agent import IdeatorAgent

        agent = IdeatorAgent()
        tools_config = agent.config.get("tools", {})
        enabled_tools = tools_config.get("enabled", [])

        assert "web_search" not in enabled_tools

    def test_all_agents_have_memory(self):
        """Все агенты имеют memory tools."""
        from src.agents.creative_agent import create_creative_team

        team = create_creative_team()

        for role, agent in team.items():
            tools_config = agent.config.get("tools", {})
            enabled_tools = tools_config.get("enabled", [])

            assert "memory_read" in enabled_tools, f"{role} missing memory_read"
            assert "memory_write" in enabled_tools, f"{role} missing memory_write"


# =============================================================================
# Test Temperature Settings
# =============================================================================

class TestTemperatureSettings:
    """Тесты настроек temperature."""

    def test_researcher_low_temperature(self):
        """Исследователь имеет низкую temperature (точность)."""
        from src.agents.creative_agent import ResearcherAgent

        agent = ResearcherAgent()
        assert agent.llm_temperature == 0.3

    def test_ideator_high_temperature(self):
        """Генератор идей имеет высокую temperature (креативность)."""
        from src.agents.creative_agent import IdeatorAgent

        agent = IdeatorAgent()
        assert agent.llm_temperature == 0.9

    def test_critic_medium_temperature(self):
        """Критик имеет среднюю temperature (баланс)."""
        from src.agents.creative_agent import CriticAgent

        agent = CriticAgent()
        assert agent.llm_temperature == 0.4

    def test_editor_medium_temperature(self):
        """Редактор имеет среднюю temperature (баланс)."""
        from src.agents.creative_agent import EditorAgent

        agent = EditorAgent()
        assert agent.llm_temperature == 0.5


# =============================================================================
# Test Agent Loop Settings
# =============================================================================

class TestAgentLoopSettings:
    """Тесты настроек Agent Loop."""

    def test_critic_no_self_critique(self):
        """У Критика отключена самокритика (он сам критик!)."""
        from src.agents.creative_agent import CriticAgent

        agent = CriticAgent()
        assert agent.enable_self_critique is False

    def test_ideator_no_self_critique(self):
        """У Генератора идей отключена самокритика."""
        from src.agents.creative_agent import IdeatorAgent

        agent = IdeatorAgent()
        assert agent.enable_self_critique is False

    def test_editor_has_self_critique(self):
        """У Редактора включена самокритика."""
        from src.agents.creative_agent import EditorAgent

        agent = EditorAgent()
        assert agent.enable_self_critique is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
