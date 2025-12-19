#!/usr/bin/env python3
"""
CreativeAgent — Базовый класс для творческой команды AI_TEAM.

Унифицированная реализация для агентов:
- Исследователь (Researcher)
- Генератор идей (Ideator)
- Критик (Critic)
- Редактор (Editor)
- Автор (Writer / Пушкин) — уже реализован в writer_agent.py

Все агенты используют одну архитектуру:
- LiteLLM для LLM вызовов
- LangGraph для Agent Loop
- BaseAgent для MindBus интеграции
- Конфиг определяет "личность" через system_prompt

See:
- docs/SSOT/AGENT_SPEC_v1.0.md
- docs/project/IMPLEMENTATION_ROADMAP.md (Этап 4)
"""

import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict

from dotenv import load_dotenv

# Ready-Made First: LiteLLM
try:
    from litellm import completion
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    logging.warning("LiteLLM not installed. Run: pip install litellm")

# Ready-Made First: LangGraph
try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logging.warning("LangGraph not installed. Run: pip install langgraph")

from .base_agent import BaseAgent

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# LangGraph State
# =============================================================================

class AgentPhase(str, Enum):
    """Фазы работы агента."""
    UNDERSTAND = "understand"
    RESEARCH = "research"
    EXECUTE = "execute"
    CRITIQUE = "critique"
    FINISH = "finish"


class CreativeState(TypedDict):
    """Универсальное состояние для творческих агентов."""
    # Input
    action: str
    params: Dict[str, Any]
    context: Optional[Dict[str, Any]]

    # Working state
    phase: str
    iteration: int
    understanding: str
    draft: str
    critique: str
    needs_improvement: bool

    # Tools state
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    research_data: Optional[str]

    # Output
    result: Optional[Dict[str, Any]]
    error: Optional[str]

    # Metrics
    llm_calls: int
    tool_calls_count: int
    start_time: float


# =============================================================================
# CreativeAgent Base Class
# =============================================================================

class CreativeAgent(BaseAgent):
    """
    Базовый класс для творческих агентов AI_TEAM.

    Агенты отличаются только конфигурацией:
    - system_prompt — "личность" и экспертиза
    - capabilities — что умеет делать
    - tools — какие инструменты использует
    - temperature — уровень креативности

    Архитектура:
    - LiteLLM → унифицированные LLM вызовы
    - LangGraph → Agent Loop (understand → research → execute → critique → finish)
    - BaseAgent → MindBus интеграция
    """

    def __init__(self, config_path: str):
        super().__init__(config_path)

        # Определяем тип агента из конфига
        self.agent_type = self.config.get("type", "creative")

        # Display Identity
        display_config = self.config.get("display", {})
        self.display_name = display_config.get("name", self.agent_type.title())
        self.display_description = display_config.get("description", "")
        self.display_avatar = display_config.get("avatar", "🤖")
        self.role_in_team = display_config.get("role_in_team", "")

        # LLM Configuration
        llm_config = self.config.get("llm", {})
        self.llm_provider = llm_config.get("provider", "openai")
        self.llm_model = llm_config.get("model", "gpt-4o")
        self.llm_temperature = llm_config.get("temperature", 0.7)
        self.llm_max_tokens = llm_config.get("max_tokens", 4000)
        self.system_prompt = llm_config.get("system_prompt", "You are a helpful assistant.")

        # Fallback LLM
        fallback_config = self.config.get("llm_fallback", {})
        self.fallback_enabled = fallback_config.get("enabled", False)
        self.fallback_model = fallback_config.get("model", "gpt-4o-mini")

        # Agent Loop settings
        loop_config = self.config.get("agent_loop", {})
        self.max_iterations = loop_config.get("max_iterations", 3)
        self.enable_self_critique = loop_config.get("enable_self_critique", False)

        # Tools settings
        tools_config = self.config.get("tools", {})
        self.enable_research = tools_config.get("enable_research", False)
        self.max_tool_calls = tools_config.get("max_tool_calls", 10)

        # Build workflow
        self._workflow = self._build_workflow() if LANGGRAPH_AVAILABLE else None

        logger.info(
            f"{self.display_avatar} {self.display_name} initialized: "
            f"model={self.llm_model}, temp={self.llm_temperature}"
        )

    def _build_workflow(self) -> Optional[Any]:
        """Build LangGraph workflow."""
        if not LANGGRAPH_AVAILABLE:
            return None

        workflow = StateGraph(CreativeState)

        # Add nodes
        workflow.add_node("understand", self._node_understand)
        workflow.add_node("research", self._node_research)
        workflow.add_node("execute", self._node_execute)
        workflow.add_node("critique", self._node_critique)
        workflow.add_node("finish", self._node_finish)

        # Entry point
        workflow.set_entry_point("understand")

        # Routing
        workflow.add_conditional_edges(
            "understand",
            self._should_research,
            {"research": "research", "execute": "execute"}
        )
        workflow.add_edge("research", "execute")
        workflow.add_conditional_edges(
            "execute",
            self._should_critique,
            {"critique": "critique", "finish": "finish"}
        )
        workflow.add_conditional_edges(
            "critique",
            self._should_improve,
            {"execute": "execute", "finish": "finish"}
        )
        workflow.add_edge("finish", END)

        return workflow.compile()

    # =========================================================================
    # LangGraph Nodes
    # =========================================================================

    def _node_understand(self, state: CreativeState) -> CreativeState:
        """Node: Понимание задачи."""
        logger.info(f"[{self.display_name}] Phase: UNDERSTAND")

        action = state["action"]
        params = state["params"]
        context = state.get("context", {})

        # Формируем понимание задачи
        understanding = f"Действие: {action}\n"
        understanding += f"Параметры: {params}\n"
        if context:
            understanding += f"Контекст: {context}\n"

        state["understanding"] = understanding
        state["phase"] = AgentPhase.UNDERSTAND.value

        logger.info(f"[{self.display_name}] Understanding: {understanding[:100]}...")

        return state

    def _node_research(self, state: CreativeState) -> CreativeState:
        """Node: Исследование (web_search, memory)."""
        logger.info(f"[{self.display_name}] Phase: RESEARCH")

        tool_calls = state.get("tool_calls", [])
        tool_results = state.get("tool_results", [])
        research_data = ""

        # Поиск в памяти
        params = state["params"]
        topic = params.get("topic", params.get("content", ""))[:50]

        if topic and "memory_read" in self.tool_registry:
            memory_key = f"research:{topic}"
            memory_result = self.execute_tool("memory_read", key=memory_key)

            if memory_result.get("success") and memory_result.get("data", {}).get("found"):
                cached = memory_result["data"]["value"]
                research_data += f"[Из памяти]: {cached}\n"
                tool_results.append({"tool": "memory_read", "result": "cache_hit"})

            tool_calls.append({"tool": "memory_read", "params": {"key": memory_key}})

        # Web search
        if "web_search" in self.tool_registry and self.enable_research:
            search_query = params.get("topic", params.get("content", ""))
            if search_query:
                search_result = self.execute_tool(
                    "web_search",
                    query=search_query,
                    max_results=3
                )

                tool_calls.append({
                    "tool": "web_search",
                    "params": {"query": search_query}
                })

                if search_result.get("success"):
                    results = search_result.get("data", [])
                    research_data += "Результаты поиска:\n"
                    for i, r in enumerate(results, 1):
                        research_data += f"{i}. {r.get('title', '')}: {r.get('snippet', '')[:150]}\n"

                    tool_results.append({
                        "tool": "web_search",
                        "result": f"found {len(results)} results"
                    })

        state["research_data"] = research_data if research_data else None
        state["tool_calls"] = tool_calls
        state["tool_results"] = tool_results
        state["tool_calls_count"] = len(tool_calls)
        state["phase"] = AgentPhase.RESEARCH.value

        return state

    def _node_execute(self, state: CreativeState) -> CreativeState:
        """Node: Выполнение основной работы."""
        logger.info(f"[{self.display_name}] Phase: EXECUTE (iteration {state.get('iteration', 0) + 1})")

        state["iteration"] = state.get("iteration", 0) + 1

        action = state["action"]
        params = state["params"]
        context = state.get("context", {})
        research_data = state.get("research_data")
        previous_critique = state.get("critique")

        # Формируем промпт для LLM
        prompt = self._build_execution_prompt(
            action=action,
            params=params,
            context=context,
            research_data=research_data,
            previous_critique=previous_critique
        )

        # Вызов LLM
        draft = self._call_llm(prompt)

        state["draft"] = draft
        state["llm_calls"] = state.get("llm_calls", 0) + 1
        state["phase"] = AgentPhase.EXECUTE.value

        return state

    def _node_critique(self, state: CreativeState) -> CreativeState:
        """Node: Самокритика."""
        logger.info(f"[{self.display_name}] Phase: CRITIQUE")

        draft = state.get("draft", "")
        action = state["action"]

        critique_prompt = f"""
Оцени свой результат как эксперт.

Задача была: {state.get('understanding', '')}

Результат:
---
{draft[:3000]}
---

Ответь кратко:
ОЦЕНКА: [1-10]
ГЛАВНАЯ ПРОБЛЕМА: [если есть]
НУЖНО УЛУЧШИТЬ: [ДА/НЕТ]
"""

        critique_response = self._call_llm(critique_prompt, max_tokens=300)
        state["critique"] = critique_response
        state["llm_calls"] = state.get("llm_calls", 0) + 1

        needs_improvement = "НУЖНО УЛУЧШИТЬ: ДА" in critique_response.upper()

        if state.get("iteration", 0) >= self.max_iterations:
            needs_improvement = False
            logger.info(f"[{self.display_name}] Max iterations reached")

        state["needs_improvement"] = needs_improvement
        state["phase"] = AgentPhase.CRITIQUE.value

        return state

    def _node_finish(self, state: CreativeState) -> CreativeState:
        """Node: Финализация."""
        logger.info(f"[{self.display_name}] Phase: FINISH")

        action = state["action"]
        draft = state.get("draft", "")
        execution_time = time.time() - state.get("start_time", time.time())

        result = {
            "action": action,
            "status": "completed",
            "output": {
                "text": draft,
                "word_count": len(draft.split()) if draft else 0,
            },
            "metrics": {
                "llm_calls": state.get("llm_calls", 0),
                "tool_calls": state.get("tool_calls_count", 0),
                "iterations": state.get("iteration", 1),
                "execution_time_seconds": round(execution_time, 2),
                "model": self.llm_model,
            },
            "agent": {
                "name": self.name,
                "display_name": self.display_name,
                "type": self.agent_type,
                "avatar": self.display_avatar,
            }
        }

        if state.get("tool_calls"):
            result["tool_calls"] = state["tool_calls"]

        state["result"] = result
        state["phase"] = AgentPhase.FINISH.value

        logger.info(
            f"[{self.display_name}] Finished: "
            f"{result['output']['word_count']} words, "
            f"{state.get('llm_calls', 0)} LLM calls"
        )

        return state

    # =========================================================================
    # Routing Functions
    # =========================================================================

    def _should_research(self, state: CreativeState) -> str:
        """Нужно ли исследование?"""
        if self.enable_research and "web_search" in self.tool_registry:
            return "research"
        return "execute"

    def _should_critique(self, state: CreativeState) -> str:
        """Нужна ли самокритика?"""
        if self.enable_self_critique and not state.get("error"):
            return "critique"
        return "finish"

    def _should_improve(self, state: CreativeState) -> str:
        """Нужно ли улучшение?"""
        if state.get("needs_improvement", False):
            return "execute"
        return "finish"

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _build_execution_prompt(
        self,
        action: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        research_data: Optional[str],
        previous_critique: Optional[str]
    ) -> str:
        """Построить промпт для выполнения действия."""
        prompt = f"Выполни действие: {action}\n\n"
        prompt += f"Параметры:\n{self._format_params(params)}\n"

        if context:
            prompt += f"\nКонтекст от других агентов:\n{context}\n"

        if research_data:
            prompt += f"\nДанные исследования:\n{research_data}\n"

        if previous_critique:
            prompt += f"\nПредыдущие замечания (учти их):\n{previous_critique}\n"

        return prompt

    def _format_params(self, params: Dict[str, Any]) -> str:
        """Форматировать параметры для промпта."""
        lines = []
        for key, value in params.items():
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    def _call_llm(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Вызов LLM через LiteLLM."""
        if not LITELLM_AVAILABLE:
            return self._call_llm_fallback(prompt, max_tokens)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]

        try:
            response = completion(
                model=self.llm_model,
                messages=messages,
                temperature=self.llm_temperature,
                max_tokens=max_tokens or self.llm_max_tokens
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"[{self.display_name}] LLM error: {e}")

            if self.fallback_enabled:
                logger.info(f"[{self.display_name}] Trying fallback: {self.fallback_model}")
                try:
                    response = completion(
                        model=self.fallback_model,
                        messages=messages,
                        temperature=self.llm_temperature,
                        max_tokens=max_tokens or self.llm_max_tokens
                    )
                    return response.choices[0].message.content
                except Exception as e2:
                    logger.error(f"[{self.display_name}] Fallback failed: {e2}")

            raise

    def _call_llm_fallback(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Fallback если LiteLLM недоступен."""
        try:
            import os
            from openai import OpenAI

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.llm_temperature,
                max_tokens=max_tokens or self.llm_max_tokens
            )
            return response.choices[0].message.content
        except ImportError:
            raise RuntimeError("Neither LiteLLM nor OpenAI available")

    # =========================================================================
    # BaseAgent Interface
    # =========================================================================

    def execute(
        self,
        action: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute action (BaseAgent interface)."""
        logger.info(f"[{self.display_name}] Executing: {action}")

        # Проверяем capabilities
        capabilities = self.config.get("capabilities", [])
        supported = [cap["name"] for cap in capabilities]

        if action not in supported:
            raise ValueError(
                f"Unknown action: {action}. "
                f"Supported by {self.display_name}: {', '.join(supported)}"
            )

        if self._workflow and LANGGRAPH_AVAILABLE:
            return self._execute_with_langgraph(action, params, context)
        else:
            return self._execute_simple(action, params, context)

    def _execute_with_langgraph(
        self,
        action: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute with LangGraph workflow."""
        initial_state: CreativeState = {
            "action": action,
            "params": params,
            "context": context,
            "phase": "",
            "iteration": 0,
            "understanding": "",
            "draft": "",
            "critique": "",
            "needs_improvement": False,
            "tool_calls": [],
            "tool_results": [],
            "research_data": None,
            "result": None,
            "error": None,
            "llm_calls": 0,
            "tool_calls_count": 0,
            "start_time": time.time()
        }

        final_state = self._workflow.invoke(initial_state)

        if final_state.get("error"):
            raise RuntimeError(final_state["error"])

        return final_state.get("result", {"status": "unknown_error"})

    def _execute_simple(
        self,
        action: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Simple execution without LangGraph."""
        logger.warning(f"[{self.display_name}] Running in simple mode")

        start_time = time.time()

        prompt = self._build_execution_prompt(
            action=action,
            params=params,
            context=context,
            research_data=None,
            previous_critique=None
        )

        draft = self._call_llm(prompt)
        execution_time = time.time() - start_time

        return {
            "action": action,
            "status": "completed",
            "output": {
                "text": draft,
                "word_count": len(draft.split()) if draft else 0,
            },
            "metrics": {
                "llm_calls": 1,
                "iterations": 1,
                "execution_time_seconds": round(execution_time, 2),
                "model": self.llm_model,
                "mode": "simple"
            },
            "agent": {
                "name": self.name,
                "display_name": self.display_name,
                "type": self.agent_type,
            }
        }

    def introduce(self) -> str:
        """Представиться (для "переклички" на совещании)."""
        return (
            f"{self.display_avatar} {self.display_name}\n"
            f"   {self.display_description}\n"
            f"   Роль: {self.role_in_team}"
        )


# =============================================================================
# Concrete Agent Classes
# =============================================================================

class ResearcherAgent(CreativeAgent):
    """Исследователь — собирает информацию."""

    def __init__(self, config_path: str = "config/agents/researcher_agent.yaml"):
        super().__init__(config_path)


class IdeatorAgent(CreativeAgent):
    """Генератор идей — создаёт концепции."""

    def __init__(self, config_path: str = "config/agents/ideator_agent.yaml"):
        super().__init__(config_path)


class CriticAgent(CreativeAgent):
    """Критик — оценивает качество."""

    def __init__(self, config_path: str = "config/agents/critic_agent.yaml"):
        super().__init__(config_path)


class EditorAgent(CreativeAgent):
    """Редактор — улучшает контент."""

    def __init__(self, config_path: str = "config/agents/editor_agent.yaml"):
        super().__init__(config_path)


# =============================================================================
# Team Factory
# =============================================================================

def create_creative_team() -> Dict[str, CreativeAgent]:
    """
    Создать творческую команду AI_TEAM.

    Returns:
        Словарь агентов: {role: agent}
    """
    team = {}

    agent_configs = [
        ("researcher", "config/agents/researcher_agent.yaml", ResearcherAgent),
        ("ideator", "config/agents/ideator_agent.yaml", IdeatorAgent),
        ("critic", "config/agents/critic_agent.yaml", CriticAgent),
        ("editor", "config/agents/editor_agent.yaml", EditorAgent),
    ]

    for role, config_path, agent_class in agent_configs:
        try:
            team[role] = agent_class(config_path)
            logger.info(f"Created {role}: {team[role].display_name}")
        except Exception as e:
            logger.error(f"Failed to create {role}: {e}")

    return team


def team_rollcall(team: Dict[str, CreativeAgent]) -> str:
    """
    "Перекличка" команды — каждый агент представляется.

    Args:
        team: Словарь агентов

    Returns:
        Строка с представлением каждого агента
    """
    lines = ["=" * 50, "🎭 ТВОРЧЕСКАЯ КОМАНДА AI_TEAM", "=" * 50, ""]

    for role, agent in team.items():
        lines.append(agent.introduce())
        lines.append("")

    lines.append("=" * 50)

    return "\n".join(lines)


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    # Демонстрация: создаём команду и проводим перекличку
    print("\n🚀 Создание творческой команды AI_TEAM...\n")

    team = create_creative_team()

    if team:
        print(team_rollcall(team))
    else:
        print("❌ Не удалось создать команду")
