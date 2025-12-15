# Agent Framework: Hybrid подход (LangGraph → Custom)

---

## ✅ УТВЕРЖДЕНО

**Решение: Hybrid - готовый фреймворк для MVP, постепенная замена на кастомный**

**Изменение от первоначального плана:**
- ❌ **НЕ пишем** Custom фреймворк с нуля для MVP
- ✅ **Начинаем** с LangGraph/CrewAI для быстрого старта
- ✅ **Постепенно заменяем** компоненты на кастомные

**Причина изменения:**
Писать фреймворк с нуля = месяцы работы. Для вайб-кодинга лучше использовать готовое, затем кастомизировать под killer features.

---

## Эволюционный путь

### Фаза 1: MVP (1-2 недели) - LangGraph

**Используем LangGraph для быстрого прототипа:**

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator

class AgentState(TypedDict):
    """Состояние между агентами"""
    topic: str
    draft: str
    critique: dict
    quality_score: float
    iteration: int

# Определяем граф агентов
workflow = StateGraph(AgentState)

# Добавляем узлы (агенты)
workflow.add_node("writer", writer_agent)
workflow.add_node("critic", critic_agent)
workflow.add_node("editor", editor_agent)

# Логика переходов - ПОДДЕРЖИВАЕТ ДИНАМИЧЕСКИЕ ИТЕРАЦИИ!
def should_continue(state: AgentState):
    if state["quality_score"] >= 8.0:
        return "editor"  # Качество достигнуто → финальная правка
    elif state["iteration"] >= 10:
        return "editor"  # Лимит итераций → заканчиваем
    else:
        return "writer"  # Качество низкое → улучшаем

# Killer Feature #1: Динамические итерации до качества ✅
workflow.add_conditional_edges(
    "critic",
    should_continue,
    {
        "writer": "writer",
        "editor": "editor"
    }
)

# Компилируем
app = workflow.compile()

# Выполнение
result = app.invoke({
    "topic": "AI trends",
    "quality_score": 0,
    "iteration": 0
})
```

**Преимущества LangGraph:**
- ✅ Поддерживает динамические workflows (conditional edges)
- ✅ State persistence из коробки
- ✅ Визуализация графа
- ✅ Интеграция с LangChain utilities

---

### Фаза 2: Ранние пользователи (1-3 месяца) - Hybrid

**Добавляем кастомные компоненты для killer features:**

```python
from langgraph.graph import StateGraph
from temporal import workflow  # Temporal интеграция

# Killer Feature #2: Мета-оркестратор (внешние API)
class ExternalAPIAgent:
    """Кастомный агент для вызова внешних сервисов"""

    async def execute(self, task: dict) -> dict:
        if task["type"] == "marketing_copy":
            # Вызываем Jasper API как субподрядчика
            return await jasper_api.generate(task)
        elif task["type"] == "research":
            # Вызываем Perplexity API
            return await perplexity_api.search(task)
        else:
            # Используем внутреннего агента (LangGraph)
            return await internal_agent.execute(task)

# Добавляем в LangGraph workflow
workflow.add_node("external_api", ExternalAPIAgent())

# Killer Feature #3: Адаптивные сценарии ✅
def route_based_on_critique(state: AgentState):
    """Динамически добавляем fact-checker если нужно"""
    critique = state["critique"]

    if "факты сомнительные" in critique.get("weaknesses", []):
        return "fact_checker"  # Добавляем новый узел в runtime
    else:
        return "editor"

workflow.add_conditional_edges("critic", route_based_on_critique)
```

**Что делаем:**
- ✅ LangGraph для базовых workflows
- ✅ Кастомные агенты для внешних API
- ✅ Кастомная логика для адаптивных сценариев
- ✅ Temporal Activities для долгоживущих задач

---

### Фаза 3: Production (6+ месяцев) - Fully Custom

**Полностью кастомный фреймворк когда вырастем:**

```python
from abc import ABC, abstractmethod
from temporal import activity

class Agent(ABC):
    """Базовый класс для всех агентов"""

    @abstractmethod
    async def execute(self, task: dict, context: dict) -> dict:
        """Выполнить задачу агента"""
        pass

    @abstractmethod
    def validate_result(self, result: dict) -> tuple[bool, float]:
        """Валидировать результат (is_valid, quality_score)"""
        pass

# Каждый агент = Temporal Activity
@activity.defn
async def writer_activity(task: dict) -> dict:
    agent = WriterAgent(config)
    return await agent.execute(task)

@activity.defn
async def critic_activity(draft: dict) -> dict:
    agent = CriticAgent(config)
    return await agent.execute(draft)
```

**Когда переходить:**
- LangGraph ограничения мешают killer features
- Нужен полный контроль над архитектурой
- Есть ресурсы на поддержку кастомного кода

---

## Почему Hybrid, а не сразу Custom?

### ✅ Преимущества Hybrid подхода

**Для вайб-кодинга:**
1. **Быстрый старт** - LangGraph работает за 1-2 дня
2. **Proof of concept** - проверяем идеи быстро
3. **Меньше кода** - не пишем базовую инфраструктуру
4. **Постепенная миграция** - заменяем что нужно, когда нужно

**Риски минимальны:**
- LangGraph гибче чем CrewAI/AutoGen
- Можно заменять компоненты по одному
- Не locked-in (можно мигрировать)

---

## LangGraph vs Альтернативы

### LangGraph ✅ Выбран для MVP

**Почему ДА:**
- ✅ Поддерживает conditional edges (динамические workflows)
- ✅ State persistence
- ✅ Визуализация
- ✅ Интеграция с LangChain utilities
- ✅ Можно кастомизировать постепенно

**Что поддерживает из killer features:**
- ✅ Killer Feature #1: Динамические итерации (conditional edges)
- ⚠️ Killer Feature #2: Мета-оркестратор (добавляем кастомными узлами)
- ✅ Killer Feature #3: Адаптивные сценарии (conditional routing)

### CrewAI - для сравнения

**Почему НЕТ как основной:**
- ❌ Фиксированные workflows (Sequential/Hierarchical)
- ❌ Сложнее кастомизация

**НО:** 🔄 **LEGO-принцип**: Можно использовать CrewAI агенты в LangGraph графе.

### AutoGen - для сравнения

**Почему НЕТ:**
- ❌ Conversation-based (не event-driven)
- ❌ Сложнее интеграция с Temporal

---

## Интеграция с Temporal

**LangGraph агенты как Temporal Activities:**

```python
from temporalio import workflow, activity
from langgraph.graph import StateGraph

# LangGraph workflow
langchain_workflow = StateGraph(AgentState)
# ... настройка графа

# Обёртка как Temporal Activity
@activity.defn
async def langgraph_agent_activity(task: dict) -> dict:
    """Запускаем LangGraph граф как Temporal Activity"""
    result = langchain_workflow.invoke(task)
    return result

# Temporal Workflow использует LangGraph
@workflow.defn
class ArticleWorkflow:
    @workflow.run
    async def run(self, topic: str) -> dict:
        # Вызываем LangGraph через Temporal
        result = await workflow.execute_activity(
            langgraph_agent_activity,
            {"topic": topic},
            start_to_close_timeout=timedelta(minutes=10)
        )
        return result
```

**Преимущества:**
- ✅ LangGraph для логики агентов
- ✅ Temporal для orchestration и state persistence
- ✅ Лучшее из двух миров

---

## 🔄 LEGO-модульность

**Легко заменить LangGraph на:**

### CrewAI
```python
# Было: LangGraph
from langgraph.graph import StateGraph
workflow = StateGraph(AgentState)

# Стало: CrewAI
from crewai import Crew, Agent, Task
crew = Crew(agents=[writer, critic], tasks=[write_task, review_task])
```

### Custom Framework
```python
# Постепенная замена узлов LangGraph на кастомные
workflow.add_node("writer", CustomWriterAgent())  # Кастомный
workflow.add_node("critic", critic_langchain_agent)  # Ещё LangChain
```

**Интерфейс Activity остаётся тот же** → Temporal Workflow не меняется → LEGO-принцип работает ✅

---

## LangChain Utilities (используем всегда)

**Что берём из LangChain независимо от фреймворка:**

### 1. Prompt Templates
```python
from langchain.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a {role}. {instructions}"),
    ("human", "{task}")
])
```

### 2. Output Parsers
```python
from langchain.output_parsers import PydanticOutputParser

parser = PydanticOutputParser(pydantic_object=CriticReview)
```

### 3. Memory
```python
from langchain.memory import ConversationBufferMemory

memory = ConversationBufferMemory(return_messages=True)
```

**Эти утилиты работают с любым фреймворком** ✅

---

## Примеры кода

### MVP: LangGraph Agent

```python
from langgraph.graph import StateGraph, END
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from litellm import acompletion

# Pydantic модели (SSOT)
class CriticReview(BaseModel):
    score: float
    strengths: list[str]
    weaknesses: list[str]
    suggestions: list[str]

# Writer Agent
async def writer_agent(state: AgentState) -> AgentState:
    """Пишет статью"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a professional writer"),
        ("human", "Write about: {topic}\n\nFeedback: {feedback}")
    ])

    messages = prompt.format_messages(
        topic=state["topic"],
        feedback=state.get("critique", {}).get("suggestions", "")
    )

    response = await acompletion(
        model="gpt-4",
        messages=[{"role": m.type, "content": m.content} for m in messages]
    )

    state["draft"] = response.choices[0].message.content
    state["iteration"] += 1
    return state

# Critic Agent
async def critic_agent(state: AgentState) -> AgentState:
    """Оценивает статью"""
    parser = PydanticOutputParser(pydantic_object=CriticReview)

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a critical reviewer"),
        ("human", "Review:\n{draft}\n\n{format_instructions}")
    ])

    messages = prompt.format_messages(
        draft=state["draft"],
        format_instructions=parser.get_format_instructions()
    )

    response = await acompletion(model="gpt-4", messages=[...])
    review = parser.parse(response.choices[0].message.content)

    state["critique"] = review.dict()
    state["quality_score"] = review.score
    return state

# Собираем граф
workflow = StateGraph(AgentState)
workflow.add_node("writer", writer_agent)
workflow.add_node("critic", critic_agent)
workflow.add_node("editor", editor_agent)

workflow.set_entry_point("writer")
workflow.add_edge("writer", "critic")

# Динамические итерации
def should_continue(state):
    return "writer" if state["quality_score"] < 8.0 and state["iteration"] < 10 else "editor"

workflow.add_conditional_edges("critic", should_continue, {"writer": "writer", "editor": "editor"})
workflow.add_edge("editor", END)

app = workflow.compile()
```

---

## Итоговое решение

**Hybrid подход (LangGraph → Custom) — правильный выбор для AI_TEAM:**

1. ✅ **MVP (1-2 недели)**: LangGraph для быстрого старта
2. ✅ **Early Users (1-3 мес)**: Hybrid (LangGraph + кастомные компоненты)
3. ✅ **Production (6+ мес)**: Полностью кастомный при необходимости

**Killer Features поддерживаются:**
- ✅ Динамические итерации (LangGraph conditional edges)
- ✅ Мета-оркестратор (кастомные узлы)
- ✅ Адаптивные сценарии (conditional routing)

**Модульность:**
- 🔄 Можно заменить LangGraph на CrewAI/AutoGen/Custom
- 🔄 Можно заменять узлы по одному
- 🔄 LangChain utilities работают с любым фреймворком

**Интеграция:**
- ✅ LangGraph агенты = Temporal Activities
- ✅ Temporal обеспечивает orchestration
- ✅ Redis для кеширования LLM вызовов

**Для вайб-кодинга:**
- ✅ Работающий прототип за 1-2 дня
- ✅ Proof of concept быстро
- ✅ Постепенная кастомизация без rewrite

---

**Статус:** ✅ УТВЕРЖДЕНО
**Последнее обновление:** 2025-12-13
