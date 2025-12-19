#!/usr/bin/env python3
"""
WriterAgent "Пушкин" — Специализированный агент для создания текстового контента.

Первый специализированный агент AI_TEAM (Этап 4).
Использует Ready-Made First подход:
- LiteLLM — унифицированный интерфейс для LLM
- LangGraph — Agent Loop с StateGraph
- Tools Framework — web_search, memory_* (AGENT_SPEC v1.0)

Capabilities:
- write_article: Написать статью на заданную тему
- improve_text: Улучшить существующий текст
- generate_outline: Создать структуру/план статьи

Usage:
    ./venv/bin/python -m src.agents.writer_agent

Environment variables:
    OPENAI_API_KEY - для OpenAI provider
    ANTHROPIC_API_KEY - для Anthropic provider

See:
- docs/SSOT/AGENT_SPEC_v1.0.md
- docs/project/IMPLEMENTATION_ROADMAP.md Этап 4
"""

import logging
import os
import time
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict

from dotenv import load_dotenv

# Ready-Made First: LiteLLM для унифицированного LLM интерфейса
try:
    from litellm import completion
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    logging.warning("LiteLLM not installed. Run: pip install litellm")

# Ready-Made First: LangGraph для Agent Loop
try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logging.warning("LangGraph not installed. Run: pip install langgraph")

from .base_agent import BaseAgent

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# LangGraph State Definition
# =============================================================================

class AgentPhase(str, Enum):
    """Фазы работы агента (LangGraph nodes)."""
    UNDERSTAND = "understand"    # Понимание задачи
    PLAN = "plan"               # Планирование (для сложных задач)
    EXECUTE = "execute"         # Выполнение основной работы
    CRITIQUE = "critique"       # Самопроверка результата
    FINISH = "finish"           # Финализация


class WriterState(TypedDict):
    """
    Состояние агента для LangGraph StateGraph.

    Based on AGENT_SPEC_v1.0.md Section 5.1 (Short-Term Memory).
    """
    # Input from COMMAND
    action: str
    params: Dict[str, Any]
    context: Optional[Dict[str, Any]]

    # Working state
    phase: str
    iteration: int
    understanding: str          # Понимание задачи
    plan: Optional[List[str]]   # План (для write_article)
    draft: str                  # Черновик результата
    critique: str               # Самокритика
    needs_improvement: bool     # Нужно ли улучшить

    # Tools state (AGENT_SPEC Section 4)
    tool_calls: List[Dict[str, Any]]    # История вызовов tools
    tool_results: List[Dict[str, Any]]  # Результаты tools
    research_data: Optional[str]         # Данные исследования (web_search)

    # Output
    result: Optional[Dict[str, Any]]
    error: Optional[str]

    # Metrics
    llm_calls: int
    tool_calls_count: int
    tokens_used: int
    start_time: float


# =============================================================================
# WriterAgent Class
# =============================================================================

class WriterAgent(BaseAgent):
    """
    WriterAgent "Пушкин" — специализированный агент для создания контента.

    Display Name: Пушкин (для Monitor)

    Supported actions:
        - write_article: Написать статью на заданную тему
        - improve_text: Улучшить существующий текст по обратной связи
        - generate_outline: Создать структуру/план статьи

    Architecture:
        - LiteLLM for LLM calls (Ready-Made First)
        - LangGraph for Agent Loop (Ready-Made First)
        - BaseAgent for MindBus integration
    """

    def __init__(self, config_path: str = "config/agents/writer_agent.yaml"):
        super().__init__(config_path)

        # Display Identity (для Monitor)
        display_config = self.config.get("display", {})
        self.display_name = display_config.get("name", "Writer")
        self.display_description = display_config.get("description", "")

        # LLM Configuration
        llm_config = self.config.get("llm", {})
        self.llm_provider = llm_config.get("provider", "openai")
        self.llm_model = llm_config.get("model", "gpt-4o")
        self.llm_temperature = llm_config.get("temperature", 0.7)
        self.llm_max_tokens = llm_config.get("max_tokens", 4000)
        self.system_prompt = llm_config.get("system_prompt", "You are a professional writer.")

        # Fallback LLM
        fallback_config = self.config.get("llm_fallback", {})
        self.fallback_enabled = fallback_config.get("enabled", False)
        self.fallback_model = fallback_config.get("model", "gpt-4o-mini")

        # Agent Loop settings
        loop_config = self.config.get("agent_loop", {})
        self.max_iterations = loop_config.get("max_iterations", 5)
        self.enable_self_critique = loop_config.get("enable_self_critique", True)

        # Tools settings (AGENT_SPEC Section 4)
        tools_config = self.config.get("tools", {})
        self.enable_research = tools_config.get("enable_research", True)
        self.max_tool_calls = tools_config.get("max_tool_calls", 10)

        # Build LangGraph workflow
        self._workflow = self._build_workflow() if LANGGRAPH_AVAILABLE else None

        # Log initialized tools
        tools_list = list(self.tool_registry._tools.keys())
        logger.info(
            f"WriterAgent '{self.display_name}' initialized: "
            f"model={self.llm_model}, tools={tools_list}"
        )

    def _build_workflow(self) -> Optional[Any]:
        """
        Build LangGraph StateGraph for agent loop.

        Pattern: understand → research → plan → execute → critique → finish

        Based on AGENT_SPEC_v1.0.md Section 7.
        """
        if not LANGGRAPH_AVAILABLE:
            return None

        workflow = StateGraph(WriterState)

        # Add nodes (including research for tools)
        workflow.add_node("understand", self._node_understand)
        workflow.add_node("research", self._node_research)  # NEW: Tool calls
        workflow.add_node("plan", self._node_plan)
        workflow.add_node("execute", self._node_execute)
        workflow.add_node("critique", self._node_critique)
        workflow.add_node("finish", self._node_finish)

        # Set entry point
        workflow.set_entry_point("understand")

        # Add edges with conditional routing
        # understand → research (if enabled) or plan
        workflow.add_conditional_edges(
            "understand",
            self._should_research,
            {
                "research": "research",
                "plan": "plan"
            }
        )

        # After research, go to plan
        workflow.add_edge("research", "plan")

        # After planning, execute
        workflow.add_edge("plan", "execute")

        # After execute, optionally critique
        workflow.add_conditional_edges(
            "execute",
            self._should_critique,
            {
                "critique": "critique",
                "finish": "finish"
            }
        )

        # After critique, either improve or finish
        workflow.add_conditional_edges(
            "critique",
            self._should_improve,
            {
                "execute": "execute",
                "finish": "finish"
            }
        )

        workflow.add_edge("finish", END)

        return workflow.compile()

    # =========================================================================
    # LangGraph Nodes
    # =========================================================================

    def _node_understand(self, state: WriterState) -> WriterState:
        """Node: Понимание задачи."""
        logger.info(f"[{self.display_name}] Phase: UNDERSTAND")

        action = state["action"]
        params = state["params"]

        # Формируем понимание задачи
        if action == "write_article":
            topic = params.get("topic", "")
            style = params.get("style", "formal")
            length = params.get("length")  # None если не указано явно
            language = params.get("language", "ru")

            # Формируем understanding БЕЗ навязывания дефолтной длины
            # Если пользователь указал требования к объёму в теме - они имеют приоритет
            understanding = f"Задача: написать статью на тему '{topic}'\n"
            understanding += f"Стиль: {style}\n"
            if length is not None:
                understanding += f"Примерный объём: {length} слов\n"
            # Если length не указан - не добавляем, чтобы не конфликтовать с указаниями в теме
            understanding += f"Язык: {language}"

        elif action == "improve_text":
            text_preview = params.get("text", "")[:200]
            feedback = params.get("feedback", "")

            understanding = (
                f"Задача: улучшить текст по обратной связи\n"
                f"Текст (начало): {text_preview}...\n"
                f"Обратная связь: {feedback}"
            )

        elif action == "generate_outline":
            topic = params.get("topic", "")
            sections = params.get("sections_count", 5)

            understanding = (
                f"Задача: создать структуру статьи на тему '{topic}'\n"
                f"Количество разделов: {sections}"
            )

        else:
            understanding = f"Неизвестное действие: {action}"

        state["understanding"] = understanding
        state["phase"] = AgentPhase.UNDERSTAND.value

        logger.info(f"[{self.display_name}] Understanding: {understanding[:100]}...")

        return state

    def _node_research(self, state: WriterState) -> WriterState:
        """
        Node: Research using tools (web_search, memory).

        Uses Tools Framework from BaseAgent (AGENT_SPEC Section 4).
        """
        logger.info(f"[{self.display_name}] Phase: RESEARCH (using tools)")

        action = state["action"]
        params = state["params"]
        tool_results = state.get("tool_results", [])
        tool_calls = state.get("tool_calls", [])

        research_data = ""

        # Only research for write_article action
        if action == "write_article":
            topic = params.get("topic", "")

            # 1. Check memory for previous research on this topic
            memory_key = f"research:{topic[:50]}"
            memory_result = self.execute_tool("memory_read", key=memory_key)

            if memory_result.get("success") and memory_result.get("data", {}).get("found"):
                # Found cached research
                cached = memory_result["data"]["value"]
                research_data = f"[Из памяти]: {cached.get('summary', '')}\n"
                logger.info(f"[{self.display_name}] Found cached research for topic")
                tool_results.append({"tool": "memory_read", "result": "cache_hit"})
                tool_calls.append({"tool": "memory_read", "params": {"key": memory_key}})

            else:
                # 2. Search the web for information
                if "web_search" in self.tool_registry:
                    search_result = self.execute_tool(
                        "web_search",
                        query=f"{topic} обзор информация",
                        max_results=3
                    )

                    tool_calls.append({
                        "tool": "web_search",
                        "params": {"query": topic, "max_results": 3}
                    })

                    if search_result.get("success"):
                        results = search_result.get("data", [])
                        research_data = "Результаты поиска:\n"
                        for i, r in enumerate(results, 1):
                            research_data += f"{i}. {r.get('title', '')}\n"
                            research_data += f"   {r.get('snippet', '')[:200]}\n"
                            research_data += f"   URL: {r.get('url', '')}\n\n"

                        tool_results.append({
                            "tool": "web_search",
                            "result": f"found {len(results)} results"
                        })

                        # 3. Save research to memory for future use
                        self.execute_tool(
                            "memory_write",
                            key=memory_key,
                            value={
                                "topic": topic,
                                "summary": research_data[:500],
                                "results_count": len(results)
                            }
                        )
                        logger.info(f"[{self.display_name}] Saved research to memory")

                    else:
                        research_data = "[Поиск не удался, продолжаем без дополнительных данных]\n"
                        tool_results.append({
                            "tool": "web_search",
                            "result": "failed",
                            "error": search_result.get("error")
                        })

        state["research_data"] = research_data if research_data else None
        state["tool_results"] = tool_results
        state["tool_calls"] = tool_calls
        state["tool_calls_count"] = state.get("tool_calls_count", 0) + len(tool_calls)
        state["phase"] = "research"

        logger.info(
            f"[{self.display_name}] Research complete: "
            f"{len(tool_calls)} tool calls, {len(research_data)} chars data"
        )

        return state

    def _node_plan(self, state: WriterState) -> WriterState:
        """Node: Планирование (для write_article)."""
        logger.info(f"[{self.display_name}] Phase: PLAN")

        action = state["action"]

        # Планирование нужно только для write_article
        if action == "write_article":
            params = state["params"]
            topic = params.get("topic", "")
            sections = params.get("sections_count", 5)

            # Запрашиваем у LLM план статьи
            plan_prompt = f"""
Создай план статьи на тему: "{topic}"

Требования:
- {sections} основных разделов
- Каждый раздел с кратким описанием (1 предложение)
- Логичная структура от введения к выводам

Формат ответа:
1. [Название раздела]: [краткое описание]
2. [Название раздела]: [краткое описание]
...
"""
            plan_response = self._call_llm(plan_prompt, max_tokens=500)
            state["plan"] = plan_response.split("\n") if plan_response else []
            state["llm_calls"] = state.get("llm_calls", 0) + 1

            logger.info(f"[{self.display_name}] Plan created with {len(state['plan'])} items")

        else:
            state["plan"] = None

        state["phase"] = AgentPhase.PLAN.value

        return state

    def _node_execute(self, state: WriterState) -> WriterState:
        """Node: Выполнение основной работы."""
        logger.info(f"[{self.display_name}] Phase: EXECUTE (iteration {state.get('iteration', 0) + 1})")

        action = state["action"]
        params = state["params"]

        state["iteration"] = state.get("iteration", 0) + 1

        if action == "write_article":
            # Pass research_data from tools (AGENT_SPEC Section 4)
            draft = self._execute_write_article(
                params,
                state.get("plan"),
                state.get("critique"),
                state.get("research_data")
            )

        elif action == "improve_text":
            draft = self._execute_improve_text(params, state.get("critique"))

        elif action == "generate_outline":
            draft = self._execute_generate_outline(params)

        else:
            draft = f"Ошибка: неизвестное действие '{action}'"
            state["error"] = draft

        state["draft"] = draft
        state["llm_calls"] = state.get("llm_calls", 0) + 1
        state["phase"] = AgentPhase.EXECUTE.value

        return state

    def _node_critique(self, state: WriterState) -> WriterState:
        """Node: Самокритика результата."""
        logger.info(f"[{self.display_name}] Phase: CRITIQUE")

        draft = state.get("draft", "")
        action = state["action"]
        params = state["params"]

        # Запрашиваем у LLM оценку
        critique_prompt = f"""
Оцени следующий текст как профессиональный редактор.

Задача была: {state.get('understanding', '')}

Текст для оценки:
---
{draft[:3000]}
---

Ответь в формате:
ОЦЕНКА: [1-10]
СИЛЬНЫЕ СТОРОНЫ: [список]
СЛАБЫЕ СТОРОНЫ: [список]
НУЖНО УЛУЧШИТЬ: [ДА/НЕТ]
РЕКОМЕНДАЦИИ: [если нужно улучшить]
"""

        critique_response = self._call_llm(critique_prompt, max_tokens=500)
        state["critique"] = critique_response
        state["llm_calls"] = state.get("llm_calls", 0) + 1

        # Определяем, нужно ли улучшение
        needs_improvement = "НУЖНО УЛУЧШИТЬ: ДА" in critique_response.upper()

        # Ограничиваем количество итераций
        if state.get("iteration", 0) >= self.max_iterations:
            needs_improvement = False
            logger.info(f"[{self.display_name}] Max iterations reached, finishing")

        state["needs_improvement"] = needs_improvement
        state["phase"] = AgentPhase.CRITIQUE.value

        logger.info(f"[{self.display_name}] Critique: needs_improvement={needs_improvement}")

        return state

    def _node_finish(self, state: WriterState) -> WriterState:
        """Node: Финализация результата."""
        logger.info(f"[{self.display_name}] Phase: FINISH")

        action = state["action"]
        draft = state.get("draft", "")

        # Подсчёт метрик
        execution_time = time.time() - state.get("start_time", time.time())
        word_count = len(draft.split()) if draft else 0

        # Формируем результат согласно MESSAGE_FORMAT SSOT
        result = {
            "action": action,
            "status": "completed",
            "output": {
                "text": draft,
                "word_count": word_count,
            },
            "metrics": {
                "llm_calls": state.get("llm_calls", 0),
                "tool_calls": state.get("tool_calls_count", 0),
                "iterations": state.get("iteration", 1),
                "execution_time_seconds": round(execution_time, 2),
                "model": self.llm_model,
                "self_critique_enabled": self.enable_self_critique,
                "research_enabled": self.enable_research,
            },
            "agent": {
                "name": self.name,
                "display_name": self.display_name,
                "version": self.config.get("version", "1.0.0"),
                "tools": list(self.tool_registry._tools.keys()),
            }
        }

        # Добавляем план для write_article
        if action == "write_article" and state.get("plan"):
            result["output"]["outline"] = state["plan"]

        # Добавляем информацию о tool calls (AGENT_SPEC Section 4)
        if state.get("tool_calls"):
            result["tool_calls"] = state["tool_calls"]

        state["result"] = result
        state["phase"] = AgentPhase.FINISH.value

        logger.info(
            f"[{self.display_name}] Finished: {word_count} words, "
            f"{state.get('llm_calls', 0)} LLM calls, "
            f"{state.get('tool_calls_count', 0)} tool calls, "
            f"{execution_time:.2f}s"
        )

        return state

    # =========================================================================
    # LangGraph Routing Functions
    # =========================================================================

    def _should_research(self, state: WriterState) -> str:
        """Определяет, нужно ли исследование (tool calls)."""
        action = state["action"]
        # Research only for write_article and if enabled
        if action == "write_article" and self.enable_research:
            # Check if we have web_search tool
            if "web_search" in self.tool_registry:
                return "research"
        return "plan"

    def _should_critique(self, state: WriterState) -> str:
        """Определяет, нужна ли самокритика."""
        if self.enable_self_critique and not state.get("error"):
            return "critique"
        return "finish"

    def _should_improve(self, state: WriterState) -> str:
        """Определяет, нужно ли улучшение после критики."""
        if state.get("needs_improvement", False):
            return "execute"
        return "finish"

    # =========================================================================
    # Action Implementations
    # =========================================================================

    def _execute_write_article(
        self,
        params: Dict[str, Any],
        plan: Optional[List[str]],
        previous_critique: Optional[str],
        research_data: Optional[str] = None
    ) -> str:
        """Выполнить написание статьи."""
        topic = params.get("topic", "")
        style = params.get("style", "formal")
        length = params.get("length")  # None если не указано явно
        language = params.get("language", "ru")

        # Формируем промпт
        style_instructions = {
            "formal": "официальный, профессиональный стиль",
            "casual": "разговорный, дружелюбный стиль",
            "technical": "технический, с терминологией",
            "creative": "творческий, образный стиль"
        }

        # Базовые требования
        prompt = f"""
Напиши статью на тему: "{topic}"

Требования:
- Стиль: {style_instructions.get(style, style)}"""

        # Добавляем объём только если указан явно (не конфликтуем с указаниями в теме)
        if length is not None:
            prompt += f"\n- Примерный объём: {length} слов"

        prompt += f"""
- Язык: {'русский' if language == 'ru' else language}
- Формат: Markdown с заголовками H2 и H3
"""

        # Add research data from tools (AGENT_SPEC Section 4)
        if research_data:
            prompt += f"\n\nИспользуй следующую информацию из исследования:\n{research_data}\n"

        if plan:
            prompt += f"\nСледуй плану:\n" + "\n".join(plan)

        if previous_critique:
            prompt += f"\n\nУчти предыдущие замечания:\n{previous_critique}"

        return self._call_llm(prompt, max_tokens=self.llm_max_tokens)

    def _execute_improve_text(
        self,
        params: Dict[str, Any],
        previous_critique: Optional[str]
    ) -> str:
        """Выполнить улучшение текста."""
        text = params.get("text", "")
        feedback = params.get("feedback", "")
        preserve_style = params.get("preserve_style", True)

        prompt = f"""
Улучши следующий текст согласно обратной связи.

Исходный текст:
---
{text}
---

Обратная связь: {feedback}

{"Сохрани оригинальный стиль автора." if preserve_style else "Можешь изменить стиль при необходимости."}
"""

        if previous_critique:
            prompt += f"\n\nДополнительные замечания:\n{previous_critique}"

        return self._call_llm(prompt, max_tokens=self.llm_max_tokens)

    def _execute_generate_outline(self, params: Dict[str, Any]) -> str:
        """Выполнить создание структуры статьи."""
        topic = params.get("topic", "")
        sections_count = params.get("sections_count", 5)

        prompt = f"""
Создай детальную структуру статьи на тему: "{topic}"

Требования:
- {sections_count} основных разделов
- Для каждого раздела: название, ключевые пункты, примерный объём
- Логичная структура от введения к выводам

Формат ответа (Markdown):
## Структура статьи: "{topic}"

### 1. [Название раздела]
- Ключевые пункты: ...
- Примерный объём: X слов

### 2. [Название раздела]
...
"""

        return self._call_llm(prompt, max_tokens=1500)

    # =========================================================================
    # LLM Interface (LiteLLM)
    # =========================================================================

    def _call_llm(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """
        Вызов LLM через LiteLLM (Ready-Made First).

        Args:
            prompt: Текст запроса
            max_tokens: Максимум токенов ответа

        Returns:
            Текст ответа от LLM
        """
        if not LITELLM_AVAILABLE:
            # Fallback на прямой вызов OpenAI если LiteLLM недоступен
            return self._call_llm_direct(prompt, max_tokens)

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
            logger.error(f"[{self.display_name}] LLM call failed: {e}")

            # Попробуем fallback модель
            if self.fallback_enabled:
                logger.info(f"[{self.display_name}] Trying fallback model: {self.fallback_model}")
                try:
                    response = completion(
                        model=self.fallback_model,
                        messages=messages,
                        temperature=self.llm_temperature,
                        max_tokens=max_tokens or self.llm_max_tokens
                    )
                    return response.choices[0].message.content
                except Exception as e2:
                    logger.error(f"[{self.display_name}] Fallback also failed: {e2}")

            raise

    def _call_llm_direct(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Прямой вызов OpenAI API (если LiteLLM недоступен)."""
        try:
            from openai import OpenAI

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")

            client = OpenAI(api_key=api_key)

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
            raise RuntimeError("Neither LiteLLM nor OpenAI library available")

    # =========================================================================
    # BaseAgent Interface
    # =========================================================================

    def execute(
        self,
        action: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute the given action (BaseAgent interface).

        Args:
            action: The action to perform (write_article, improve_text, generate_outline)
            params: Action parameters
            context: Optional execution context

        Returns:
            Result dictionary (SSOT MESSAGE_FORMAT compliant)
        """
        logger.info(f"[{self.display_name}] Executing action: {action}")

        # Проверяем поддерживаемые действия
        supported_actions = ["write_article", "improve_text", "generate_outline"]
        if action not in supported_actions:
            raise ValueError(
                f"Unknown action: {action}. "
                f"Supported: {', '.join(supported_actions)}"
            )

        # Используем LangGraph если доступен
        if self._workflow and LANGGRAPH_AVAILABLE:
            return self._execute_with_langgraph(action, params, context)
        else:
            # Простой fallback без LangGraph
            return self._execute_simple(action, params, context)

    def _execute_with_langgraph(
        self,
        action: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute action using LangGraph workflow."""
        # Инициализируем состояние (AGENT_SPEC Section 5.1)
        initial_state: WriterState = {
            "action": action,
            "params": params,
            "context": context,
            "phase": "",
            "iteration": 0,
            "understanding": "",
            "plan": None,
            "draft": "",
            "critique": "",
            "needs_improvement": False,
            # Tools state (AGENT_SPEC Section 4)
            "tool_calls": [],
            "tool_results": [],
            "research_data": None,
            # Output
            "result": None,
            "error": None,
            # Metrics
            "llm_calls": 0,
            "tool_calls_count": 0,
            "tokens_used": 0,
            "start_time": time.time()
        }

        # Запускаем workflow
        final_state = self._workflow.invoke(initial_state)

        # Проверяем на ошибки
        if final_state.get("error"):
            raise RuntimeError(final_state["error"])

        return final_state.get("result", {"status": "unknown_error"})

    def _execute_simple(
        self,
        action: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Simple execution without LangGraph (fallback)."""
        logger.warning(f"[{self.display_name}] Running in simple mode (LangGraph not available)")

        start_time = time.time()

        if action == "write_article":
            draft = self._execute_write_article(params, None, None)
        elif action == "improve_text":
            draft = self._execute_improve_text(params, None)
        elif action == "generate_outline":
            draft = self._execute_generate_outline(params)
        else:
            raise ValueError(f"Unknown action: {action}")

        execution_time = time.time() - start_time
        word_count = len(draft.split()) if draft else 0

        return {
            "action": action,
            "status": "completed",
            "output": {
                "text": draft,
                "word_count": word_count,
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
                "version": self.config.get("version", "1.0.0"),
            }
        }


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Run WriterAgent 'Пушкин'."""
    agent = WriterAgent()
    print(f"\n   Display Name: {agent.display_name}")
    agent.start()


if __name__ == "__main__":
    main()
