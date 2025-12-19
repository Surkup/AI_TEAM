# AGENT Specification v1.0

**Статус**: ✅ Утверждено (Final Release)
**Версия**: 1.0.3
**Дата**: 2025-12-18
**Совместимость**: MindBus Protocol v1.0, MESSAGE_FORMAT v1.1.4, NODE_PASSPORT v1.0

---

## TL;DR (Executive Summary)

**AGENT** — спецификация AI-агента в системе AI_TEAM.

**Основа**: Ready-Made First (LangGraph + LiteLLM + LangChain Tools)

**Ключевые компоненты**:
- **Brain** — LLM для "мышления" (выбор действий, генерация)
- **Tools** — инструменты для взаимодействия с миром (web_search, file_ops, etc.)
- **Memory** — краткосрочная и долгосрочная память
- **Capabilities** — умения агента (Brain + Tools + Memory)

**НЕ изобретаем велосипед**: Используем LangGraph для Agent Loop, LiteLLM для LLM calls, LangChain Tools для инструментов.

---

## 1. Что такое Агент

### 1.1. Определение

**Агент** — автономный AI-компонент системы AI_TEAM, который:
- Получает задачи от Orchestrator (COMMAND)
- Самостоятельно решает КАК их выполнить
- Использует свои инструменты (Tools) и память (Memory)
- Возвращает результат (RESULT) или ошибку (ERROR)

**Метафора**: Агент = Сотрудник компании
- Orchestrator говорит "подготовь отчёт по продажам" (ЧТО)
- Агент сам решает: открыть Excel, сделать запрос в базу, построить графики (КАК)

### 1.2. Принцип разделения ответственности

| Компонент | Отвечает за | Пример |
|-----------|-------------|--------|
| **Orchestrator** | ЧТО делать | "Напиши статью про AI" |
| **Agent** | КАК делать | Выбор tools, планирование шагов, генерация |

---

## 2. Анатомия агента

```
┌─────────────────────────────────────────────────────────────┐
│                         AGENT                                │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                    BRAIN (Мозг)                         │ │
│  │                                                         │ │
│  │  LLM: GPT-4o / Claude / Llama / Mistral                │ │
│  │  System Prompt: "Ты профессиональный копирайтер..."    │ │
│  │                                                         │ │
│  │  Отвечает за:                                          │ │
│  │  • Понимание задачи (UNDERSTAND)                       │ │
│  │  • Планирование действий (PLAN)                        │ │
│  │  • Выбор инструментов (TOOL_CALL)                      │ │
│  │  • Генерация результата (EXECUTE)                      │ │
│  │  • Самокритика (CRITIQUE)                              │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   TOOLS (Инструменты)                   │ │
│  │                                                         │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │ │
│  │  │web_search│ │file_read │ │file_write│ │ api_call │  │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │ │
│  │                                                         │ │
│  │  Агент САМ выбирает какой инструмент использовать      │ │
│  │  через LLM Function Calling / Tool Use                 │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   MEMORY (Память)                       │ │
│  │                                                         │ │
│  │  ┌─────────────────────┐  ┌─────────────────────────┐  │ │
│  │  │   SHORT-TERM        │  │     LONG-TERM           │  │ │
│  │  │   (Краткосрочная)   │  │     (Долгосрочная)      │  │ │
│  │  │                     │  │                         │  │ │
│  │  │ • Контекст задачи   │  │ • Опыт прошлых задач    │  │ │
│  │  │ • История шагов     │  │ • Знания о проекте      │  │ │
│  │  │ • Промежуточные     │  │ • Паттерны решений      │  │ │
│  │  │   результаты        │  │                         │  │ │
│  │  │                     │  │ Реализация:             │  │ │
│  │  │ Реализация:         │  │ Vector DB (Chroma)      │  │ │
│  │  │ State в LangGraph   │  │ (опционально для MVP)   │  │ │
│  │  └─────────────────────┘  └─────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │               CAPABILITIES (Умения)                     │ │
│  │                                                         │ │
│  │  Capability = Brain + Tools + Memory + Prompt          │ │
│  │                                                         │ │
│  │  Примеры:                                              │ │
│  │  • write_article (написать статью)                     │ │
│  │  • research_topic (исследовать тему)                   │ │
│  │  • review_code (проверить код)                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Brain (Мозг)

### 3.1. Назначение

Brain — это LLM, который "думает" за агента: понимает задачу, планирует действия, выбирает инструменты, генерирует результат.

### 3.2. Конфигурация

```yaml
brain:
  # LLM Provider (через LiteLLM)
  provider: "openai"              # openai | anthropic | ollama | azure
  model: "gpt-4o"                 # Конкретная модель

  # Параметры генерации
  temperature: 0.7                # Креативность (0.0 - 1.0)
  max_tokens: 4000                # Лимит ответа

  # System Prompt — "личность" агента
  system_prompt: |
    Ты — профессиональный копирайтер с 10-летним опытом.
    Твой стиль: ясный, убедительный, без воды.
    Всегда структурируй текст с заголовками.

  # Fallback при ошибках
  fallback:
    enabled: true
    model: "gpt-4o-mini"          # Альтернативная модель
```

### 3.3. LLM Interface (LiteLLM)

**Почему LiteLLM**: Ready-Made First — единый интерфейс для всех LLM провайдеров.

```python
from litellm import completion

response = completion(
    model="gpt-4o",           # или "claude-3-opus" или "ollama/llama3"
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task_prompt}
    ],
    temperature=0.7,
    max_tokens=4000
)
```

**Преимущества**:
- ✅ OpenAI, Anthropic, Google, Ollama — один API
- ✅ Автоматический retry и fallback
- ✅ Подсчёт стоимости из коробки

---

## 4. Tools (Инструменты)

### 4.1. Назначение

Tools — функции, которые агент может вызывать для взаимодействия с внешним миром.

### 4.2. Стандартные Tools

| Tool | Описание | Уровень риска | MVP |
|------|----------|---------------|-----|
| `web_search` | Поиск в интернете | Низкий | ✅ |
| `web_fetch` | Загрузить страницу по URL | Низкий | ✅ |
| `file_read` | Прочитать файл | Средний | ✅ |
| `file_write` | Записать файл | Высокий | ⚠️ |
| `memory_read` | Прочитать из памяти | Низкий | ✅ |
| `memory_write` | Записать в память | Низкий | ✅ |
| `api_call` | HTTP запрос к API | Высокий | ❌ |
| `code_execute` | Выполнить код | Критический | ❌ |

### 4.3. Tool Schema (JSON Schema)

Каждый Tool описывается по стандарту OpenAI Function Calling:

```json
{
  "type": "function",
  "function": {
    "name": "web_search",
    "description": "Search the internet for information on a given query",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "The search query"
        },
        "max_results": {
          "type": "integer",
          "description": "Maximum number of results to return",
          "default": 5
        }
      },
      "required": ["query"]
    }
  }
}
```

### 4.4. Tool Interface

```python
from abc import ABC, abstractmethod
from typing import Any, Dict
from pydantic import BaseModel

class ToolResult(BaseModel):
    """Результат выполнения Tool."""
    success: bool
    data: Any = None
    error: str | None = None

class BaseTool(ABC):
    """Базовый класс для всех Tools."""

    name: str                    # Имя tool (для LLM)
    description: str             # Описание (для LLM)
    parameters_schema: dict      # JSON Schema параметров

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Выполнить tool с заданными параметрами."""
        pass

    def to_openai_schema(self) -> dict:
        """Конвертировать в формат OpenAI Function Calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema
            }
        }
```

### 4.5. Безопасность Tools

**Уровни доступа**:

| Уровень | Tools | Требуется |
|---------|-------|-----------|
| **safe** | web_search, web_fetch, memory_* | Ничего |
| **moderate** | file_read | Whitelist директорий |
| **restricted** | file_write, api_call | Явное разрешение в конфиге |
| **critical** | code_execute, shell | Human-in-the-loop |

**Конфигурация безопасности**:

```yaml
tools:
  security:
    allowed_tools:
      - web_search
      - web_fetch
      - file_read
      - memory_read
      - memory_write

    file_read:
      allowed_paths:
        - "/workspace/**"
        - "/data/**"
      denied_paths:
        - "**/.env"
        - "**/secrets/**"

    file_write:
      enabled: false              # Отключено по умолчанию
      requires_approval: true     # Требует подтверждения
```

---

## 5. Memory (Память)

### 5.1. Short-Term Memory (Краткосрочная)

**Назначение**: Хранение контекста текущей задачи.

**Время жизни**: Пока выполняется задача.

**Реализация**: State в LangGraph.

```python
class AgentState(TypedDict):
    """Состояние агента (краткосрочная память)."""

    # Входные данные (из COMMAND)
    action: str
    params: Dict[str, Any]
    context: Dict[str, Any] | None

    # Рабочее состояние
    phase: str                    # Текущая фаза (UNDERSTAND, PLAN, etc.)
    iteration: int                # Номер итерации
    understanding: str            # Понимание задачи
    plan: List[str] | None        # План действий

    # Промежуточные результаты
    tool_calls: List[Dict]        # История вызовов tools
    tool_results: List[Dict]      # Результаты tools
    draft: str                    # Черновик результата
    critique: str                 # Самокритика

    # Результат
    result: Dict[str, Any] | None
    error: str | None

    # Метрики
    llm_calls: int
    start_time: float
```

### 5.2. Long-Term Memory (Долгосрочная)

**Назначение**: Хранение опыта между задачами.

**Время жизни**: Постоянно (персистентное).

**Реализация**: Vector Database (Chroma для MVP).

**Что хранить**:
- Успешные решения задач
- Обратная связь от пользователя
- Контекст проекта
- Паттерны и best practices

**Interface**:

```python
class LongTermMemory(ABC):
    """Интерфейс долгосрочной памяти."""

    @abstractmethod
    def store(self, content: str, metadata: dict) -> str:
        """Сохранить в память. Возвращает ID записи."""
        pass

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[dict]:
        """Семантический поиск по памяти."""
        pass

    @abstractmethod
    def get(self, memory_id: str) -> dict | None:
        """Получить запись по ID."""
        pass
```

### 5.3. Memory Configuration

```yaml
memory:
  short_term:
    enabled: true
    max_context_tokens: 8000      # Лимит контекста LLM

  long_term:
    enabled: false                # MVP: отключено
    provider: "chroma"            # chroma | pinecone | faiss
    collection: "agent_memory"
    embedding_model: "text-embedding-3-small"
```

---

## 6. Capabilities (Умения)

### 6.1. Определение

**Capability** = Brain + Tools + Memory + Специфичный Prompt

Capability — это конкретное умение агента, которое он может выполнять.

### 6.2. Capability Schema

```yaml
capabilities:
  - name: "write_article"
    version: "1.0"
    description: "Написать статью на заданную тему"

    # Входные параметры
    input_schema:
      type: object
      properties:
        topic:
          type: string
          description: "Тема статьи"
        style:
          type: string
          enum: ["formal", "casual", "technical", "creative"]
          default: "formal"
        length:
          type: integer
          description: "Примерное количество слов"
          default: 1000
      required: ["topic"]

    # Выходной формат
    output_schema:
      type: object
      properties:
        text:
          type: string
          description: "Текст статьи"
        word_count:
          type: integer
        outline:
          type: array
          items:
            type: string

    # Какие tools использует
    tools_required:
      - web_search       # Опционально, для исследования

    # Специфичный промпт для capability
    prompt_template: |
      Напиши статью на тему: "{topic}"
      Стиль: {style}
      Примерный объём: {length} слов
```

### 6.3. Связь с NODE_PASSPORT

Capabilities агента объявляются в NODE_PASSPORT при регистрации:

```json
{
  "spec": {
    "capabilities": [
      {
        "name": "write_article",
        "version": "1.0",
        "parameters": {
          "styles": ["formal", "casual", "technical"],
          "max_length": 5000,
          "languages": ["ru", "en"]
        }
      },
      {
        "name": "improve_text",
        "version": "1.0"
      }
    ]
  }
}
```

**Связь**: Orchestrator ищет агентов по capabilities через NODE_REGISTRY.

---

## 7. Agent Loop (LangGraph)

### 7.1. Стандартные фазы

```
UNDERSTAND → PLAN → EXECUTE → CRITIQUE → FINISH
     │         │        │         │
     │         │        │         └──► если needs_improvement=True
     │         │        │                    └──► возврат к EXECUTE
     │         │        │
     │         │        └──► TOOL_CALL (при необходимости)
     │         │
     │         └──► для сложных задач (write_article)
     │
     └──► всегда первая фаза
```

### 7.2. Описание фаз

| Фаза | Назначение | Выход |
|------|------------|-------|
| **UNDERSTAND** | Понять задачу, извлечь ключевые требования | `understanding: str` |
| **PLAN** | Создать план выполнения (для сложных задач) | `plan: List[str]` |
| **EXECUTE** | Выполнить основную работу | `draft: str` |
| **TOOL_CALL** | Вызвать tool (при необходимости) | `tool_result: dict` |
| **CRITIQUE** | Оценить результат, найти недостатки | `critique: str`, `needs_improvement: bool` |
| **FINISH** | Сформировать финальный результат | `result: dict` |

### 7.3. LangGraph Implementation

```python
from langgraph.graph import StateGraph, END

def build_agent_workflow() -> StateGraph:
    """Построить стандартный Agent Loop."""

    workflow = StateGraph(AgentState)

    # Добавляем узлы
    workflow.add_node("understand", node_understand)
    workflow.add_node("plan", node_plan)
    workflow.add_node("execute", node_execute)
    workflow.add_node("tool_call", node_tool_call)
    workflow.add_node("critique", node_critique)
    workflow.add_node("finish", node_finish)

    # Entry point
    workflow.set_entry_point("understand")

    # Edges
    workflow.add_edge("understand", "plan")
    workflow.add_edge("plan", "execute")

    # Conditional: после execute — tool_call или critique
    workflow.add_conditional_edges(
        "execute",
        should_call_tool,
        {
            "tool_call": "tool_call",
            "critique": "critique"
        }
    )

    workflow.add_edge("tool_call", "execute")

    # Conditional: после critique — improve или finish
    workflow.add_conditional_edges(
        "critique",
        should_improve,
        {
            "execute": "execute",
            "finish": "finish"
        }
    )

    workflow.add_edge("finish", END)

    return workflow.compile()
```

### 7.4. Лимиты итераций

```yaml
agent_loop:
  max_iterations: 5               # Максимум итераций execute-critique
  max_tool_calls: 10              # Максимум вызовов tools за задачу
  enable_self_critique: true      # Включить фазу CRITIQUE
```

---

## 8. Конфигурация агента

### 8.1. Полная схема YAML

```yaml
# config/agents/{agent_name}.yaml

agent:
  # Идентификация
  name: "agent.writer.001"        # Уникальное имя (для MindBus routing)
  type: "writer"                  # Тип агента
  version: "1.0.0"                # Версия

  # Display Identity (для Monitor)
  display:
    name: "Пушкин"                # Человекочитаемое имя
    description: "Мастер художественного слова"
    avatar: "quill"               # Иконка

  # Brain (LLM)
  brain:
    provider: "openai"
    model: "gpt-4o"
    temperature: 0.7
    max_tokens: 4000
    system_prompt: |
      Ты — профессиональный копирайтер.
      Пишешь ясно, убедительно, структурированно.
    fallback:
      enabled: true
      model: "gpt-4o-mini"

  # Tools
  tools:
    enabled:
      - web_search
      - memory_read
      - memory_write
    security:
      file_read:
        allowed_paths: ["/workspace/**"]

  # Memory
  memory:
    short_term:
      enabled: true
      max_context_tokens: 8000
    long_term:
      enabled: false

  # Capabilities
  capabilities:
    - name: "write_article"
      version: "1.0"
    - name: "improve_text"
      version: "1.0"
    - name: "generate_outline"
      version: "1.0"

  # Agent Loop
  agent_loop:
    max_iterations: 5
    max_tool_calls: 10
    enable_self_critique: true

  # Limits
  limits:
    max_execution_time_seconds: 300   # 5 минут на задачу
    max_retries: 3

  # Registry
  registry:
    enabled: true
    heartbeat_interval_seconds: 10
```

---

## 9. Интеграция с SSOT

### 9.1. MESSAGE_FORMAT v1.1

**Агент получает**: `ai.team.command`
```json
{
  "type": "ai.team.command",
  "data": {
    "action": "write_article",
    "params": {"topic": "AI trends", "style": "formal"},
    "timeout_seconds": 300
  }
}
```

**Агент отправляет**: `ai.team.result` (успех) или `ai.team.error` (ошибка)
```json
{
  "type": "ai.team.result",
  "data": {
    "status": "SUCCESS",
    "output": {"text": "...", "word_count": 2000},
    "execution_time_ms": 45000,
    "metrics": {"llm_calls": 5, "tool_calls": 2}
  }
}
```

**Ссылка**: [MESSAGE_FORMAT_v1.1.md](MESSAGE_FORMAT_v1.1.md)

### 9.2. NODE_PASSPORT v1.0

Агент создаёт NODE_PASSPORT при старте:

```json
{
  "metadata": {
    "uid": "uuid-here",
    "name": "agent.writer.001",
    "nodeType": "agent",
    "labels": {
      "capability.write_article": "true",
      "capability.improve_text": "true"
    }
  },
  "spec": {
    "capabilities": [...],
    "endpoint": {
      "protocol": "amqp",
      "queue": "cmd.agent_writer_001.*"
    }
  },
  "status": {
    "phase": "Running",
    "conditions": [{"type": "Ready", "status": "True"}],
    "lease": {...}
  }
}
```

**Ссылка**: [NODE_PASSPORT_SPEC_v1.0.md](NODE_PASSPORT_SPEC_v1.0.md)

### 9.3. MindBus Protocol v1.0

**Подписки агента**:
- `cmd.{agent_name}.*` — личные команды
- `cmd.{agent_type}.*` — команды по типу (broadcast)
- `ctl.all.*` — CONTROL сигналы для всех
- `ctl.{agent_type}.*` — CONTROL для типа

**Отправка RESULT**: через `reply_to` (RPC pattern)

**Ссылка**: [mindbus_protocol_v1.md](mindbus_protocol_v1.md)

---

## 10. Типы агентов

### 10.1. Специализированные агенты

| Агент | Тип | Capabilities | Tools |
|-------|-----|--------------|-------|
| **WriterAgent** | writer | write_article, improve_text | web_search |
| **CriticAgent** | critic | review_text, score_quality | — |
| **ResearcherAgent** | researcher | research_topic, summarize | web_search, web_fetch |
| **DeveloperAgent** | developer | write_code, review_code | file_read, file_write |

### 10.2. Эволюционный план

| Версия | Что реализуем | Tools | Memory |
|--------|--------------|-------|--------|
| **v0.1** | WriterAgent (базовый) | — | Short-term only |
| **v0.2** | + Tools Framework | web_search | Short-term |
| **v0.3** | + CriticAgent | — | Short-term |
| **v0.4** | + Long-term Memory | web_search, file_* | + Chroma |
| **v1.0** | Полная система | Полный набор | Full RAG |

---

## 11. Реализация (структура кода)

```
src/agents/
├── __init__.py
├── base_agent.py           # Базовый класс (уже есть)
│
├── tools/                  # Tools Framework
│   ├── __init__.py
│   ├── base_tool.py        # BaseTool ABC
│   ├── web_search.py       # WebSearchTool
│   ├── web_fetch.py        # WebFetchTool
│   ├── file_ops.py         # FileReadTool, FileWriteTool
│   └── memory_tools.py     # MemoryReadTool, MemoryWriteTool
│
├── memory/                 # Memory Framework
│   ├── __init__.py
│   ├── short_term.py       # ShortTermMemory (state)
│   └── long_term.py        # LongTermMemory (Chroma)
│
├── workflow/               # Agent Loop (LangGraph)
│   ├── __init__.py
│   ├── phases.py           # Node functions (understand, plan, etc.)
│   └── builder.py          # WorkflowBuilder
│
└── specialized/            # Специализированные агенты
    ├── writer_agent.py     # WriterAgent "Пушкин"
    ├── critic_agent.py     # CriticAgent
    └── researcher_agent.py # ResearcherAgent
```

---

## 12. Безопасность

### 12.1. Принципы

1. **Least Privilege**: Агент имеет только необходимые tools
2. **Whitelist**: Разрешённые tools явно указываются в конфиге
3. **Sandboxing**: Опасные tools требуют явного разрешения
4. **Audit**: Все tool calls логируются

### 12.2. Уровни доступа

| Уровень | Описание | Пример |
|---------|----------|--------|
| **open** | Доступно всем агентам | web_search, memory_read |
| **restricted** | Требует явного разрешения | file_write |
| **critical** | Требует human-in-the-loop | code_execute, shell |

### 12.3. Конфигурация безопасности

```yaml
security:
  # Глобальные лимиты
  global_limits:
    max_tool_calls_per_task: 20
    max_api_calls_per_minute: 60

  # Per-tool настройки
  tools:
    file_write:
      requires_approval: true
      allowed_paths: ["/workspace/output/**"]

    api_call:
      enabled: false
```

---

## 13. Связь с другими спецификациями

| SSOT | Что агент БЕРЁТ | Что агент ДАЁТ |
|------|-----------------|----------------|
| **MESSAGE_FORMAT** | Структура COMMAND | Структура RESULT/ERROR |
| **NODE_PASSPORT** | Схема паспорта | Свой паспорт с capabilities |
| **NODE_REGISTRY** | API регистрации | Регистрация + heartbeat |
| **MindBus** | Протокол подключения | Сообщения по протоколу |
| **PROCESS_CARD** | — | Capabilities для шагов |

---

## 14. Уточнения (по результатам ревью)

### 14.1. Idempotency Storage

> *Idempotency storage backend is implementation-defined.*

Агент может хранить idempotency keys (для предотвращения повторной обработки команд) в:
- In-memory (для MVP)
- Redis (для production)
- Файловая система (для простых случаев)

Время жизни ключей: 24 часа (настраивается).

### 14.2. Routing Key vs Target Node

**Разделение ответственности**:

| Поле | Назначение | Пример |
|------|------------|--------|
| **routing_key** | Транспортная адресация (AMQP) | `cmd.writer.agent_001` |
| **target_node** | Логическая фильтрация (в payload) | `agent.writer.001` |

Агент проверяет `target_node` в data payload и игнорирует сообщения, адресованные другим агентам.

### 14.3. Resource Limits Enforcement

> *Runtime resource enforcement is delegated to execution environment.*

Агент **декларирует** лимиты в NODE_PASSPORT, но **не enforce** их сам:
- CPU/Memory limits → Docker/Kubernetes
- API rate limits → LiteLLM / API Gateway
- Execution time → Orchestrator timeout

Агент только **отслеживает** собственные метрики и **сообщает** о превышении.

### 14.4. Архитектура соединений MindBus (Thread Safety)

> *Добавлено в v1.0.2 (2025-12-18) по результатам отладки.*

**КРИТИЧЕСКИ ВАЖНО**: Библиотека `pika.BlockingConnection` НЕ является потокобезопасной.

**Проблема**: Если агент одновременно:
1. Слушает команды в основном потоке (`start_consuming`)
2. Отправляет heartbeat из фонового потока

...то возникает race condition и соединение падает с ошибкой `IndexError: pop from an empty deque`.

**Решение**: Агент использует **ДВА отдельных MindBus соединения**:

```
┌─────────────────────────────────────────────────────────────┐
│                         AGENT                                │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │               Основное соединение (bus)                 │ │
│  │                                                         │ │
│  │  • Приём команд (start_consuming)                      │ │
│  │  • Отправка RESULT/ERROR                               │ │
│  │  • Работает в ОСНОВНОМ потоке                          │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │            Heartbeat соединение (_heartbeat_bus)        │ │
│  │                                                         │ │
│  │  • Только отправка heartbeat                           │ │
│  │  • Работает в ФОНОВОМ потоке                           │ │
│  │  • Изолировано от основного соединения                 │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Правило для разработчиков**:

> ⚠️ При добавлении новой функциональности, которая отправляет сообщения из отдельного потока — ОБЯЗАТЕЛЬНО создавать для неё отдельное MindBus соединение.

**Примеры когда нужно отдельное соединение**:
- ✅ Heartbeat из фонового потока → `_heartbeat_bus`
- ✅ Периодическая отправка метрик → отдельное соединение
- ✅ Асинхронные уведомления → отдельное соединение

**Когда НЕ нужно отдельное соединение**:
- ❌ Отправка RESULT после обработки команды (тот же поток)
- ❌ Любые операции в callback обработчика сообщений

**Реализация в коде** (BaseAgent):

```python
class BaseAgent:
    def __init__(self, config_path: str):
        self.bus = MindBus()                    # Основное соединение
        self._heartbeat_bus: Optional[MindBus] = None  # Отдельное для heartbeat

    def _start_heartbeat_thread(self) -> None:
        # Создаём ОТДЕЛЬНОЕ соединение для heartbeat потока
        self._heartbeat_bus = MindBus()
        self._heartbeat_bus.connect()

        def heartbeat_loop():
            while not self._stop_heartbeat.wait(timeout=interval):
                self._heartbeat_bus.send_event(...)  # Используем отдельное соединение

        threading.Thread(target=heartbeat_loop, daemon=True).start()
```

### 14.5. Progress Heartbeat (Task Progress Reporting)

> *Добавлено в v1.0.3 (2025-12-18)*

**Проблема**: Когда агент выполняет долгую задачу (например, LLM генерация 3+ минуты), невозможно отличить "работает долго" от "завис".

**Решение**: Агент периодически отправляет `task.progress` events пока работает над задачей.

#### 14.5.1. Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                         AGENT                                │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────┐ │
│  │   Main Thread    │  │ Lifecycle Thread │  │  Progress  │ │
│  │                  │  │                  │  │   Thread   │ │
│  │  self.bus        │  │ _heartbeat_bus   │  │ _progress  │ │
│  │  (MindBus #1)    │  │  (MindBus #2)    │  │    _bus    │ │
│  │                  │  │                  │  │ (MindBus#3)│ │
│  │  • Получение CMD │  │  • node.heartbeat│  │            │ │
│  │  • Отправка      │  │    каждые 10 сек │  │ • task.    │ │
│  │    RESULT/ERROR  │  │                  │  │   progress │ │
│  │  • LLM вызовы    │  │  "Я жив"         │  │   каждые   │ │
│  │    (блокирующие) │  │                  │  │   30 сек   │ │
│  │                  │  │                  │  │            │ │
│  │                  │  │                  │  │ "Работаю   │ │
│  │                  │  │                  │  │  над task" │ │
│  └──────────────────┘  └──────────────────┘  └────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Три MindBus соединения** (thread safety):
1. **Main** — приём команд, отправка результатов
2. **Lifecycle Heartbeat** — "я жив" (node.heartbeat)
3. **Progress Heartbeat** — "я работаю над задачей X" (task.progress)

#### 14.5.2. Конфигурация

```yaml
# config/agents/{agent_name}.yaml

agent:
  # ... другие настройки ...

  # Progress Heartbeat (v1.0.3)
  progress_heartbeat:
    enabled: true
    interval_seconds: 30        # Отправлять каждые 30 секунд
    # Агент считается "зависшим" если пропустил 3 интервала (90 сек)
```

#### 14.5.3. Event Format

См. [MESSAGE_FORMAT v1.1.4, секция 5.4 Пример 4](MESSAGE_FORMAT_v1.1.md)

```json
{
  "type": "ai.team.event",
  "source": "agent.writer.001",
  "data": {
    "event_type": "task.progress",
    "event_data": {
      "task_id": "cmd-uuid-001",
      "state": "working",
      "elapsed_seconds": 45,
      "phase": "generating"
    }
  }
}
```

#### 14.5.4. Реализация в BaseAgent

```python
class BaseAgent:
    def __init__(self, config_path: str):
        self.bus = MindBus()                          # Main thread
        self._heartbeat_bus: Optional[MindBus] = None # Lifecycle heartbeat
        self._progress_bus: Optional[MindBus] = None  # Progress heartbeat (NEW)

        self._current_task_id: Optional[str] = None
        self._task_start_time: Optional[float] = None
        self._working = threading.Event()

    def _start_progress_thread(self) -> None:
        """Progress heartbeat — отдельный поток для отчёта о выполнении задачи."""
        if not self.config.get("progress_heartbeat", {}).get("enabled", True):
            return

        self._progress_bus = MindBus()
        self._progress_bus.connect()

        interval = self.config.get("progress_heartbeat", {}).get("interval_seconds", 30)

        def progress_loop():
            while not self._stop_event.is_set():
                if self._working.is_set() and self._current_task_id:
                    elapsed = int(time.time() - self._task_start_time)
                    self._progress_bus.send_event(
                        event_type="task.progress",
                        data={
                            "task_id": self._current_task_id,
                            "state": "working",
                            "elapsed_seconds": elapsed,
                        },
                        routing_key="evt.task.progress"
                    )
                time.sleep(interval)

        threading.Thread(target=progress_loop, daemon=True).start()

    def handle_command(self, message: dict) -> None:
        """Обработка входящей команды."""
        self._current_task_id = message.get("id")
        self._task_start_time = time.time()
        self._working.set()  # Начали работать

        try:
            result = self._execute(message)  # Блокирующий LLM вызов
            self.bus.send_result(result)
        except Exception as e:
            self.bus.send_error(str(e))
        finally:
            self._working.clear()  # Закончили
            self._current_task_id = None
            self._task_start_time = None
```

#### 14.5.5. Логика на стороне Monitor/Orchestrator

```python
# Хранение времени последнего progress
last_progress: Dict[str, float] = {}  # task_id -> timestamp

def on_task_progress(event: dict):
    """Обработка task.progress событий."""
    task_id = event["data"]["event_data"]["task_id"]
    last_progress[task_id] = time.time()

    # Обновить UI: показать elapsed_seconds
    update_ui_progress(task_id, event["data"]["event_data"])

def check_stuck_tasks():
    """Периодическая проверка зависших задач."""
    grace_period = 90  # 3 пропущенных интервала по 30 сек

    for task_id, last_time in last_progress.items():
        if time.time() - last_time > grace_period:
            # Агент завис!
            mark_task_as_stuck(task_id)
            send_alert(f"Agent stuck on task {task_id}")
```

#### 14.5.6. Важные правила

1. **Progress thread НЕ знает** что делает main thread — он просто проверяет флаг `_working`
2. **Progress отправляется только** когда `_working.is_set()` и есть `_current_task_id`
3. **При завершении задачи** (успех или ошибка) — флаг сбрасывается, progress прекращается
4. **Если агент упал** во время работы — progress прекратится → система обнаружит

### 14.6. Singleton Enforcement (Защита от дублирования экземпляров)

> *Добавлено в v1.0.4 (2025-12-18)*

**Проблема**: При случайном запуске второго экземпляра агента с тем же именем оба экземпляра подписываются на одну очередь. RabbitMQ распределяет сообщения между ними (round-robin), что приводит к:
- Дублированию ответов
- Потере сообщений
- Непредсказуемому поведению системы

**Решение**: Использование RabbitMQ Exclusive Queue как механизма блокировки.

#### 14.6.1. Механизм: RabbitMQ Exclusive Queue

При старте агент ДОЛЖЕН объявить exclusive queue для получения "блокировки":

```python
try:
    queue = channel.queue_declare(
        queue=f"singleton.{agent_name}",
        exclusive=True,      # Только одно соединение может владеть
        auto_delete=True     # Автоудаление при отключении
    )
except pika.exceptions.ChannelClosedByBroker as e:
    if e.reply_code == 405:  # RESOURCE_LOCKED
        # Очередь уже занята другим экземпляром
        raise AgentAlreadyRunningError(agent_name)
    raise
```

**Почему Exclusive Queue**:
- ✅ Встроенная функция RabbitMQ (AMQP 0-9-1)
- ✅ Не требует дополнительных сервисов (Ready-Made First)
- ✅ Автоматическое освобождение при crash/disconnect
- ✅ Гарантированная атомарность на уровне брокера

#### 14.6.2. Поведение при конфликте

Если очередь уже занята другим экземпляром:
- RabbitMQ возвращает ошибку `RESOURCE_LOCKED (405)`
- Агент ДОЛЖЕН завершиться с понятным сообщением об ошибке
- Агент НЕ ДОЛЖЕН молча продолжать работу

#### 14.6.3. Требования к логированию

**КРИТИЧЕСКИ ВАЖНО**: Факт конфликта ДОЛЖЕН быть зафиксирован в логах для диагностики.

**При успешном захвате блокировки** (INFO):
```
INFO:[agent.writer.001] Singleton lock acquired (queue: singleton.agent.writer.001)
```

**При конфликте** (ERROR):
```
ERROR:[agent.writer.001] SINGLETON CONFLICT: Agent 'agent.writer.001' already running!
ERROR:[agent.writer.001] Another instance holds exclusive queue 'singleton.agent.writer.001'
ERROR:[agent.writer.001] Action: Stop the existing instance or use a different agent name
ERROR:[agent.writer.001] Shutting down to prevent duplicate processing
```

**Требования к лог-сообщениям**:
1. Уровень ERROR для конфликтов (легко фильтруется в логах)
2. Включать имя агента в сообщение
3. Включать имя очереди для диагностики
4. Чёткое объяснение причины и рекомендация действий

#### 14.6.4. Освобождение ресурса

Exclusive queue автоматически освобождается при:
- Graceful shutdown (Ctrl+C, SIGTERM) — мгновенно
- Crash агента (соединение разрывается) — мгновенно
- Потере сети — после TCP timeout (~60 сек, настраивается в RabbitMQ)

**При graceful shutdown** (INFO):
```
INFO:[agent.writer.001] Singleton lock released (graceful shutdown)
```

#### 14.6.5. Конфигурация

```yaml
# config/agents/{agent_name}.yaml

agent:
  # ... другие настройки ...

  # Singleton Enforcement (v1.0.4)
  singleton:
    enabled: true                    # По умолчанию включено
    queue_prefix: "singleton"        # Префикс для очереди блокировки
```

#### 14.6.6. Реализация в BaseAgent

```python
class AgentAlreadyRunningError(Exception):
    """Raised when another instance of the agent is already running."""
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        super().__init__(
            f"Agent '{agent_name}' is already running. "
            f"Stop the existing instance before starting a new one."
        )


class BaseAgent:
    def __init__(self, config_path: str):
        # ... existing initialization ...
        self._singleton_enabled = True  # From config
        self._singleton_queue: Optional[str] = None

    def _acquire_singleton_lock(self) -> None:
        """
        Acquire singleton lock via RabbitMQ exclusive queue.

        Raises:
            AgentAlreadyRunningError: If another instance is already running
        """
        if not self._singleton_enabled:
            return

        queue_name = f"singleton.{self.name}"

        try:
            self.bus.channel.queue_declare(
                queue=queue_name,
                exclusive=True,
                auto_delete=True
            )
            self._singleton_queue = queue_name
            logger.info(f"[{self.name}] Singleton lock acquired (queue: {queue_name})")

        except pika.exceptions.ChannelClosedByBroker as e:
            if e.reply_code == 405:  # RESOURCE_LOCKED
                logger.error(f"[{self.name}] SINGLETON CONFLICT: Agent '{self.name}' already running!")
                logger.error(f"[{self.name}] Another instance holds exclusive queue '{queue_name}'")
                logger.error(f"[{self.name}] Action: Stop the existing instance or use a different agent name")
                logger.error(f"[{self.name}] Shutting down to prevent duplicate processing")
                raise AgentAlreadyRunningError(self.name)
            raise

    def start(self) -> None:
        """Start the agent."""
        self.bus.connect()

        # ПЕРВЫМ ДЕЛОМ: захватываем singleton lock
        self._acquire_singleton_lock()

        # Остальная инициализация только после успешного захвата
        self._subscribe_to_commands()
        self._send_registration_event()
        # ...

    def stop(self) -> None:
        """Stop the agent and cleanup."""
        # ... existing cleanup ...

        if self._singleton_queue:
            logger.info(f"[{self.name}] Singleton lock released (graceful shutdown)")

        self.bus.disconnect()
```

#### 14.6.7. Диагностика проблем

**Как найти конфликты в логах**:
```bash
# Поиск всех singleton конфликтов
grep "SINGLETON CONFLICT" /var/log/ai_team/*.log

# Поиск по конкретному агенту
grep "agent.writer.001.*SINGLETON" /var/log/ai_team/*.log
```

**Как проверить, кто держит блокировку**:
```bash
# RabbitMQ Management API
rabbitmqctl list_queues name exclusive owner_pid | grep singleton

# Или через Management UI
# http://localhost:15672/#/queues → найти singleton.{agent_name}
```

---

## 15. Финальное резюме

**AGENT_SPEC v1.0** — это:

✅ **Полная спецификация** AI-агента (Brain, Tools, Memory, Capabilities)
✅ **Ready-Made First** (LangGraph, LiteLLM, LangChain Tools)
✅ **SSOT Compliant** (согласовано с MESSAGE_FORMAT, NODE_PASSPORT, MindBus)
✅ **Безопасность** (уровни доступа, sandboxing, audit)
✅ **Расширяемость** (легко добавлять новые tools и capabilities)

**Следующие шаги**:
1. Реализовать Tools Framework (`src/agents/tools/`)
2. Обновить WriterAgent — добавить tools
3. Создать CriticAgent по этой спецификации

---

**Версия**: 1.0.3
**Дата**: 2025-12-18
**Авторы**: AI_TEAM Core Team
**Статус**: ✅ Утверждено (Final Release)

---

## Changelog

### v1.0.4 (2025-12-18)
- **ДОБАВЛЕНО**: Раздел 14.6 "Singleton Enforcement (Защита от дублирования экземпляров)"
- **ПРОБЛЕМА**: При случайном запуске второго экземпляра агента с тем же именем происходит round-robin распределение сообщений между экземплярами
- **РЕШЕНИЕ**: RabbitMQ Exclusive Queue как механизм блокировки (`singleton.{agent_name}`)
- **ЛОГИРОВАНИЕ**: Детальные ERROR-логи для диагностики конфликтов
- **ИСКЛЮЧЕНИЕ**: `AgentAlreadyRunningError` при попытке запуска дубликата

### v1.0.3 (2025-12-18)
- **ДОБАВЛЕНО**: Раздел 14.5 "Progress Heartbeat (Task Progress Reporting)"
- **ПРОБЛЕМА**: Невозможно отличить "агент работает долго" от "агент завис"
- **РЕШЕНИЕ**: Агент периодически отправляет `task.progress` events (каждые 30 сек)
- **АРХИТЕКТУРА**: Третье MindBus соединение `_progress_bus` для progress thread
- **СВЯЗЬ**: См. MESSAGE_FORMAT v1.1.4 секция "task.progress event type"

### v1.0.2 (2025-12-18)
- **ДОБАВЛЕНО**: Раздел 14.4 "Архитектура соединений MindBus (Thread Safety)"
- **ПРИЧИНА**: pika.BlockingConnection не потокобезопасен, heartbeat из отдельного потока вызывал crash
- **РЕШЕНИЕ**: Агент использует два отдельных MindBus соединения (основное + heartbeat)
- **ИНСТРУКЦИЯ**: При отправке сообщений из отдельного потока — создавать отдельное соединение

### v1.0.1 (2025-12-18)
- Добавлен раздел 14 "Уточнения по результатам ревью"
- Уточнено: Idempotency storage backend is implementation-defined
- Уточнено: Routing key vs target_node разделение
- Уточнено: Resource limits enforcement delegated to execution environment

### v1.0 (2025-12-17)
- Первоначальный релиз
