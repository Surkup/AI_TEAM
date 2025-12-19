# ORCHESTRATOR Specification v1.0

**Статус**: ✅ Утверждено (Final Release)
**Версия**: 1.0
**Дата**: 2025-12-17
**Совместимость**: MindBus Protocol v1.0, NODE_PASSPORT v1.0, NODE_REGISTRY v1.0, MESSAGE_FORMAT v1.1, PROCESS_CARD v1.0

---

## TL;DR (Executive Summary)

**ORCHESTRATOR** — центральный интеллектуальный узел системы AI_TEAM, который управляет выполнением процессов, координирует агентов и обеспечивает качество результатов.

**Каноническая метафора**:
- **MindBus** — ТЕЛО системы (нервная система, передача сигналов)
- **Orchestrator** — СОЗНАНИЕ системы (мозг, принятие решений)
- **Agents** — ОРГАНЫ системы (исполнители, специалисты)

**Архитектура**: Policy-Governed Hybrid (Variant C)
- **LLM Planner** — гибкое планирование и адаптация
- **Policy Layer** — детерминистические guardrails и безопасность

**Философия**: "Dumb Card, Smart Orchestrator"
- Process Card описывает ЧТО делать
- Orchestrator решает КАК, ГДЕ и КОГДА выполнять

**НЕ изобретаем велосипед**:
- Kubernetes patterns (metadata/spec/status, controllers, reconciliation)
- gRPC error model (google.rpc.Code)
- W3C Trace Context (observability)

---

## 1. Введение

### 1.1. Что такое Orchestrator

**Orchestrator** — это центральный компонент AI_TEAM, который:

1. **Понимает цели** — принимает задачи от пользователя (CEO)
2. **Планирует выполнение** — выбирает/создаёт Process Card
3. **Координирует агентов** — находит подходящие узлы, распределяет задачи
4. **Управляет качеством** — контролирует результаты, запускает улучшения
5. **Обеспечивает устойчивость** — обрабатывает ошибки, retry, fallback
6. **Гарантирует прозрачность** — логирует все решения, публикует события

### 1.2. Место в архитектуре

```
ЧЕЛОВЕК (CEO)
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                          │
│  ┌──────────────┐         ┌──────────────┐              │
│  │ Policy Layer │ ◄─────► │ LLM Planner  │              │
│  │ (Guardrails) │         │ (Flexible)   │              │
│  └──────────────┘         └──────────────┘              │
│         │                        │                       │
│         └────────┬───────────────┘                       │
│                  ▼                                       │
│         ┌──────────────────────┐                        │
│         │  Execution Engine    │                        │
│         │  (State Machine)     │                        │
│         └──────────────────────┘                        │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
              ┌──────────────┐
              │   MindBus    │
              │   (AMQP)     │
              └──────────────┘
                      │
     ┌────────────────┼────────────────┐
     ▼                ▼                ▼
┌─────────┐    ┌─────────┐    ┌─────────┐
│ Agent 1 │    │ Agent 2 │    │ Agent N │
└─────────┘    └─────────┘    └─────────┘
```

### 1.3. Связь с другими SSOT спецификациями

| Спецификация | Связь с Orchestrator |
|--------------|---------------------|
| **MindBus Protocol v1.0** | Транспорт: Orchestrator отправляет/получает CloudEvents через AMQP |
| **NODE_REGISTRY v1.0** | Discovery: Orchestrator ищет узлы по capabilities |
| **NODE_PASSPORT v1.0** | Capabilities: Orchestrator читает возможности узлов |
| **MESSAGE_FORMAT v1.1** | Messages: Orchestrator создаёт COMMAND, обрабатывает RESULT/ERROR |
| **PROCESS_CARD v1.0** | Workflows: Orchestrator интерпретирует и исполняет карточки процессов |

---

## 2. Архитектурные принципы

### 2.1. Принцип 1: Stateless Orchestrator

**Состояние процессов хранится в Process State Store (PostgreSQL), НЕ в памяти Orchestrator.**

```
┌─────────────────┐         ┌─────────────────┐
│   Orchestrator  │ ◄─────► │ Process State   │
│   (Stateless)   │         │ Store (DB)      │
└─────────────────┘         └─────────────────┘
```

**Преимущества**:
- ✅ Устранение Single Point of Failure
- ✅ Hot-swap (замена без остановки системы)
- ✅ Horizontal scaling (несколько инстансов)
- ✅ Recovery после сбоев (процессы продолжаются с того же места)

**Реализация (MVP)**:
- v0.1-v0.2: In-memory state (простота)
- v0.3+: PostgreSQL/etcd persistence

### 2.2. Принцип 2: Event-Driven Model

**Orchestrator НЕ ждёт синхронно ответа от агента.**

```
1. Отправил COMMAND
2. Сохранил state в БД
3. Переключился на обработку других событий
4. Получил RESULT/ERROR → реакция
```

**Преимущества**:
- ✅ Отсутствие блокировок
- ✅ Параллельное управление множеством процессов
- ✅ Устойчивость к медленным агентам

### 2.3. Принцип 3: Контракты важнее интеллекта

**Даже если Orchestrator LLM-based — его свобода заканчивается на границах контрактов.**

**Orchestrator НИКОГДА не имеет права**:
- ❌ Нарушать MESSAGE_FORMAT (5 типов сообщений)
- ❌ Игнорировать Process Card
- ❌ "Догадываться" вместо соблюдения протоколов
- ❌ Обходить Policy Layer
- ❌ Отправлять forbidden actions

**Это обеспечивает**:
- ✅ Предсказуемость поведения
- ✅ Возможность отладки
- ✅ Доверие к системе

### 2.4. Принцип 4: "Dumb Card, Smart Orchestrator"

**Process Card** — "глупый" рецепт (описывает ЧТО делать)
**Orchestrator** — "умный" повар (решает КАК и ГДЕ выполнять)

```yaml
# Process Card говорит:
steps:
  - action: "code_generation"
    params:
      language: "python"

# Orchestrator решает:
# 1. Какой агент подходит? → Node Registry query
# 2. Агент offline? → Выбрать другого / ждать / escalate
# 3. Timeout? → Retry на другом узле
# 4. Результат плохой? → Вернуться к предыдущему шагу
```

---

## 3. Архитектура: Policy-Governed Hybrid (Variant C)

### 3.1. Почему Variant C

**Сравнение вариантов**:

| Вариант | Determinism | Safety | Speed | Quality | Score |
|---------|-------------|--------|-------|---------|-------|
| **A: Workflow Engine** | 10/10 | 9/10 | 6/10 | 8/10 | 43/50 (86%) |
| **B: LLM-Director** | 3/10 | 4/10 | 10/10 | 8/10 | 30/50 (60%) |
| **C: Policy-Governed** | 7/10 | 9/10 | 8/10 | 9/10 | 41/50 (82%) |

**Variant C выбран** как лучший баланс для MVP → Production:
- ✅ Гибкость LLM для адаптации
- ✅ Policy Layer для безопасности
- ✅ Можно начать просто, усложнять постепенно

### 3.2. Компоненты архитектуры

#### 3.2.1. Policy Layer (Guardrails)

**Назначение**: Детерминистические проверки безопасности и ограничений.

**Policies для MVP**:

```yaml
policies:
  # Budget Policy (защита от зацикливания)
  - type: budget
    max_steps: 100
    max_agents: 10
    timeout: 3600  # 1 час

  # Capability Policy (выбор правильного агента)
  - type: capability_matching
    strict: true  # требовать точное совпадение

  # Retry Policy (обработка ошибок)
  - type: retry
    max_retries_per_step: 3
    backoff: exponential
    initial_delay_seconds: 5

  # Timeout Policy (защита от hang)
  - type: timeout
    step_timeout_seconds: 300
    process_timeout_seconds: 3600
```

**Policies для Production (v0.4+)**:

```yaml
policies:
  # Safety Policy (запрещённые действия)
  - type: safety
    forbidden_actions:
      - delete_data
      - external_api_call_unverified

  # Approval Policy (human-in-the-loop)
  - type: approval
    require_human_approval:
      - action: publish
      - action: send_email
```

#### 3.2.2. LLM Planner (Flexible)

**Назначение**: Интеллектуальное планирование и адаптация.

**Функции LLM Planner**:
1. **Goal Decomposition** — разбиение цели на подзадачи
2. **Agent Selection** — выбор лучшего агента с учётом контекста
3. **Error Recovery** — адаптивное восстановление после ошибок
4. **Quality Assessment** — оценка качества результатов

**Промпт для LLM Planner**:

```
You are Orchestrator LLM. Your goal: {goal from Process Card}

Available agents in Node Registry:
- agent-1: capabilities [web_search, summarization], status=ready, load=2
- agent-2: capabilities [text_generation], status=ready, load=5

Current process state:
- Step: {current_step}
- Variables: {process_variables}
- Previous outputs: {outputs from previous steps}

Policies enforced:
- Budget: {current_step}/{max_steps}
- Retry: {retry_count}/{max_retries}
- Forbidden actions: {forbidden_actions}

Decide next action:
1. Which agent to call?
2. What COMMAND to send?
3. What inputs to provide?

Respond in JSON:
{
  "reasoning": "...",
  "next_action": {
    "agent_id": "agent-1",
    "command": {
      "action": "...",
      "params": {...}
    }
  }
}
```

#### 3.2.3. Execution Engine (State Machine)

**Назначение**: Детерминистическое исполнение шагов Process Card.

**Состояния процесса**:

```
┌─────────┐
│ PENDING │ ──── Процесс создан, ждёт запуска
└────┬────┘
     │ start()
     ▼
┌─────────┐
│ RUNNING │ ──── Процесс выполняется
└────┬────┘
     │
     ├──── step_completed() ────► [следующий шаг]
     │
     ├──── error() ────► RETRY / FAILED
     │
     ├──── pause() ────► PAUSED
     │
     └──── complete() ────► COMPLETED

┌─────────┐
│ PAUSED  │ ──── Процесс приостановлен
└────┬────┘
     │ resume()
     ▼
┌─────────┐
│ RUNNING │
└─────────┘

┌─────────┐
│ FAILED  │ ──── Процесс завершился с ошибкой
└─────────┘

┌───────────┐
│ COMPLETED │ ──── Процесс успешно завершён
└───────────┘
```

**Состояния шага**:

```
PENDING → IN_PROGRESS → COMPLETED
                     → FAILED → RETRY → IN_PROGRESS
                              → ESCALATED
```

---

## 4. Функциональные требования

### 4.1. Приоритизация функций

| Приоритет | Описание | Версия |
|-----------|----------|--------|
| 🔴 **КРИТИЧНО** | Без этого система не работает | v0.1 MVP |
| 🟡 **ВАЖНО** | Нужно быстро, но не блокирует | v0.2-v0.3 |
| 🟢 **СТРАТЕГИЧЕСКИ** | Долгосрочное развитие | v1.0+ |

### 4.2. Функции v0.1 (MVP Skeleton)

#### 4.2.1. Подключение к MindBus 🔴

**Orchestrator MUST**:
- Публиковать COMMAND messages
- Подписываться на RESULT / ERROR
- Использовать W3C Trace Context (traceparent)

**Pydantic Schema**:

```python
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

class OrchestratorCommandRequest(BaseModel):
    """Запрос на отправку команды агенту"""
    action: str = Field(description="Действие для выполнения")
    params: Dict[str, Any] = Field(default_factory=dict)
    requirements: Optional[Dict[str, Any]] = Field(
        None,
        description="Требования к узлу (capabilities, constraints)"
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="Контекст процесса (process_id, step)"
    )
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    idempotency_key: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
```

#### 4.2.2. Работа с Node Registry 🔴

**Orchestrator MUST**:
- Получать список узлов с нужными capabilities
- Фильтровать по статусу (ready / offline)
- Понимать типы узлов (agent / storage / tool)

**Capability Matching**:

```python
# Поиск узлов для выполнения action
def find_suitable_nodes(action: str, registry: NodeRegistry) -> List[NodePassport]:
    selector = {
        "matchLabels": {
            f"capability.{action}": "true"
        },
        "matchExpressions": [
            {"key": "status.phase", "operator": "Eq", "values": ["Running"]},
            {"key": "status.conditions.Ready", "operator": "Eq", "values": ["True"]}
        ]
    }
    return registry.query(selector)
```

#### 4.2.3. Чтение Process Card 🔴

**Orchestrator MUST**:
- Загружать и парсить YAML/JSON
- Валидировать структуру (metadata, spec, steps)
- Проверять на циклические зависимости

**Process Card Loader**:

```python
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ProcessCardMetadata(BaseModel):
    id: str
    name: str
    version: str
    description: Optional[str] = None

class ProcessStep(BaseModel):
    id: str
    action: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    output: Optional[str] = None
    condition: Optional[str] = None
    then: Optional[str] = None
    else_: Optional[str] = Field(None, alias="else")
    retry: Optional[Dict[str, Any]] = None
    next: Optional[str] = None
    type: Optional[str] = None  # complete, human_checkpoint, wait

class ProcessCardSpec(BaseModel):
    variables: Dict[str, Any] = Field(default_factory=dict)
    steps: List[ProcessStep]

class ProcessCard(BaseModel):
    metadata: ProcessCardMetadata
    spec: ProcessCardSpec
```

#### 4.2.4. Формирование COMMAND 🔴

**Orchestrator создаёт CloudEvents COMMAND согласно MESSAGE_FORMAT v1.1**:

```json
{
  "specversion": "1.0",
  "type": "ai.team.command",
  "source": "orchestrator-main",
  "id": "cmd-uuid-001",
  "time": "2025-12-17T12:00:00Z",
  "subject": "process-book-001/step-research",
  "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",

  "data": {
    "action": "research",
    "params": {
      "topic": "AI trends 2025",
      "depth": "comprehensive"
    },
    "requirements": {
      "capabilities": ["web_search", "summarization"]
    },
    "context": {
      "process_id": "process-book-001",
      "step": "step-research"
    },
    "timeout_seconds": 300,
    "idempotency_key": "idem-001"
  }
}
```

#### 4.2.5. Выбор исполнителя 🔴

**Алгоритм для MVP (детерминистический)**:

```python
def select_executor(action: str, registry: NodeRegistry) -> Optional[str]:
    """Выбор исполнителя для действия (MVP: первый подходящий)"""

    candidates = find_suitable_nodes(action, registry)

    if not candidates:
        return None  # Нет подходящих узлов

    # MVP: Выбираем первый ready узел с минимальной нагрузкой
    ready_nodes = [n for n in candidates if n.status.phase == "Running"]

    if not ready_nodes:
        return None

    # Сортируем по загрузке (currentTasks)
    ready_nodes.sort(key=lambda n: n.status.currentTasks or 0)

    return ready_nodes[0].metadata.uid
```

#### 4.2.6. Приём RESULT 🔴

**Orchestrator обрабатывает успешные результаты**:

```python
def handle_result(result_event: CloudEvent, process_state: ProcessState):
    """Обработка успешного результата"""

    # 1. Сопоставление с COMMAND по correlation_id
    command_id = result_event.correlation_id
    pending_command = process_state.get_pending_command(command_id)

    if not pending_command:
        logger.warning(f"Unknown correlation_id: {command_id}")
        return

    # 2. Извлечение output
    result_data = result_event.data
    output = result_data.get("output", {})

    # 3. Сохранение в переменные процесса
    if pending_command.output_variable:
        process_state.variables[pending_command.output_variable] = output

    # 4. Переход к следующему шагу
    next_step = get_next_step(pending_command.step_id, process_state)
    process_state.current_step = next_step

    # 5. Логирование
    logger.info(f"Step {pending_command.step_id} completed successfully")
```

#### 4.2.7. Обработка ERROR 🔴

**Orchestrator обрабатывает ошибки согласно google.rpc.Code**:

```python
from enum import Enum

class ErrorHandling(Enum):
    RETRY = "retry"         # Повторить операцию
    ESCALATE = "escalate"   # Эскалировать человеку
    ABORT = "abort"         # Прервать процесс
    FALLBACK = "fallback"   # Использовать альтернативу

# Таблица решений по кодам ошибок
ERROR_HANDLING_TABLE = {
    "DEADLINE_EXCEEDED": ErrorHandling.RETRY,      # Retryable
    "RESOURCE_EXHAUSTED": ErrorHandling.RETRY,     # Retryable после ожидания
    "UNAVAILABLE": ErrorHandling.RETRY,            # Retryable
    "ABORTED": ErrorHandling.RETRY,                # Retryable
    "INVALID_ARGUMENT": ErrorHandling.ABORT,       # Не retryable
    "NOT_FOUND": ErrorHandling.ABORT,              # Не retryable
    "PERMISSION_DENIED": ErrorHandling.ESCALATE,   # Требует вмешательства
    "INTERNAL": ErrorHandling.RETRY,               # Retry 1-2 раза
    "UNIMPLEMENTED": ErrorHandling.FALLBACK,       # Выбрать другого агента
}

def handle_error(error_event: CloudEvent, process_state: ProcessState):
    """Обработка ошибки выполнения"""

    error_data = error_event.data.get("error", {})
    error_code = error_data.get("code", "UNKNOWN")
    retryable = error_data.get("retryable", False)

    handling = ERROR_HANDLING_TABLE.get(error_code, ErrorHandling.ESCALATE)

    if handling == ErrorHandling.RETRY and retryable:
        retry_command(process_state)
    elif handling == ErrorHandling.FALLBACK:
        try_fallback_agent(process_state)
    elif handling == ErrorHandling.ESCALATE:
        escalate_to_human(process_state, error_data)
    else:
        abort_process(process_state, error_data)
```

#### 4.2.8. Трассировка и логирование 🔴

**Orchestrator публикует EVENT о своих решениях**:

```json
{
  "specversion": "1.0",
  "type": "ai.team.event",
  "source": "orchestrator-main",
  "id": "evt-uuid-001",
  "time": "2025-12-17T12:00:05Z",
  "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-11f167bb1ca013c8-01",

  "data": {
    "event_type": "orchestrator.agent_selected",
    "event_data": {
      "process_id": "process-book-001",
      "step": "step-research",
      "action": "research",
      "selected_agent": "agent-researcher-01",
      "reason": "best_match_capabilities",
      "alternatives_considered": ["agent-researcher-02"]
    },
    "severity": "INFO"
  }
}
```

### 4.3. Функции v0.2 (Basic Resilience)

#### 4.3.1. State Persistence 🟡

```python
class ProcessStateStore:
    """Персистентное хранилище состояния процессов"""

    async def save_state(self, process_id: str, state: ProcessState):
        """Сохранить состояние процесса"""
        pass

    async def load_state(self, process_id: str) -> Optional[ProcessState]:
        """Загрузить состояние процесса"""
        pass

    async def list_active_processes(self) -> List[str]:
        """Список активных процессов для recovery"""
        pass
```

#### 4.3.2. Retry & Backoff 🟡

```python
class RetryPolicy(BaseModel):
    max_attempts: int = Field(default=3, ge=1, le=10)
    initial_delay_seconds: float = Field(default=5.0)
    backoff_multiplier: float = Field(default=2.0)
    max_delay_seconds: float = Field(default=300.0)

def calculate_retry_delay(attempt: int, policy: RetryPolicy) -> float:
    """Exponential backoff с ограничением"""
    delay = policy.initial_delay_seconds * (policy.backoff_multiplier ** (attempt - 1))
    return min(delay, policy.max_delay_seconds)
```

#### 4.3.3. Fallback Agent Selection 🟡

```python
def select_fallback_agent(
    original_agent: str,
    action: str,
    registry: NodeRegistry
) -> Optional[str]:
    """Выбрать альтернативного агента при ошибке"""

    candidates = find_suitable_nodes(action, registry)

    # Исключаем оригинального агента
    alternatives = [n for n in candidates if n.metadata.uid != original_agent]

    if not alternatives:
        return None

    # Выбираем с минимальной нагрузкой
    alternatives.sort(key=lambda n: n.status.currentTasks or 0)
    return alternatives[0].metadata.uid
```

### 4.4. Функции v0.3 (Observability & Control)

#### 4.4.1. CONTROL Messages 🟡

**Orchestrator обрабатывает управляющие сигналы**:

```python
def handle_control(control_event: CloudEvent, process_state: ProcessState):
    """Обработка CONTROL сообщения"""

    control_type = control_event.data.get("control_type")
    target = control_event.data.get("target", {})
    process_id = target.get("process_id")

    if control_type == "stop":
        stop_process(process_id, reason="Manual stop by operator")
    elif control_type == "pause":
        pause_process(process_id)
    elif control_type == "resume":
        resume_process(process_id)
    elif control_type == "shutdown":
        graceful_shutdown()
```

#### 4.4.2. Priority Management 🟡

```python
class ProcessPriority(BaseModel):
    """Приоритет процесса (0-9, где 9 = highest)"""
    value: int = Field(default=5, ge=0, le=9)

    def to_amqp_priority(self) -> int:
        """Конвертация в AMQP priority (0-255)"""
        # Mapping: process priority 0-9 → AMQP 0-90
        return self.value * 10
```

### 4.5. Функции v0.4 (Security & Policies)

#### 4.5.1. Policy Layer 🟡

```python
from abc import ABC, abstractmethod
from typing import Tuple

class Policy(ABC):
    """Базовый класс политики"""

    @abstractmethod
    def check(self, action: str, context: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Проверка политики. Возвращает (allowed, reason)"""
        pass

class ForbiddenActionsPolicy(Policy):
    """Политика запрещённых действий"""

    def __init__(self, forbidden_actions: List[str]):
        self.forbidden_actions = set(forbidden_actions)

    def check(self, action: str, context: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if action in self.forbidden_actions:
            return False, f"Action '{action}' is forbidden by safety policy"
        return True, None

class BudgetPolicy(Policy):
    """Политика бюджета"""

    def __init__(self, max_steps: int, max_agents: int):
        self.max_steps = max_steps
        self.max_agents = max_agents

    def check(self, action: str, context: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        current_step = context.get("current_step", 0)
        if current_step >= self.max_steps:
            return False, f"Budget exceeded: {current_step}/{self.max_steps} steps"
        return True, None

class PolicyEngine:
    """Движок проверки политик"""

    def __init__(self, policies: List[Policy]):
        self.policies = policies

    def check_all(self, action: str, context: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Проверить все политики"""
        violations = []
        for policy in self.policies:
            allowed, reason = policy.check(action, context)
            if not allowed:
                violations.append(reason)
        return len(violations) == 0, violations
```

### 4.6. Функции v0.5 (LLM Integration)

#### 4.6.1. LLM Planner Interface 🟢

```python
from abc import ABC, abstractmethod

class LLMPlanner(ABC):
    """Интерфейс LLM Planner"""

    @abstractmethod
    async def decompose_goal(self, goal: str, context: Dict[str, Any]) -> List[ProcessStep]:
        """Разбить цель на шаги"""
        pass

    @abstractmethod
    async def select_agent(
        self,
        action: str,
        candidates: List[NodePassport],
        context: Dict[str, Any]
    ) -> Tuple[str, str]:
        """Выбрать агента с объяснением. Returns (agent_id, reasoning)"""
        pass

    @abstractmethod
    async def handle_error(
        self,
        error: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ErrorHandling:
        """Решить как обработать ошибку"""
        pass

class SimpleLLMPlanner(LLMPlanner):
    """Простая реализация LLM Planner через API"""

    def __init__(self, llm_client, model: str = "gpt-4"):
        self.llm_client = llm_client
        self.model = model

    async def select_agent(
        self,
        action: str,
        candidates: List[NodePassport],
        context: Dict[str, Any]
    ) -> Tuple[str, str]:
        prompt = self._build_agent_selection_prompt(action, candidates, context)
        response = await self.llm_client.complete(prompt, model=self.model)
        return self._parse_agent_selection(response)
```

### 4.7. Функции v1.0 (Production-Ready)

#### 4.7.1. Budget Management 🟢

```python
class ProcessBudget(BaseModel):
    """Бюджет выполнения процесса"""
    max_cost_usd: Optional[float] = None
    max_tokens: Optional[int] = None
    max_time_seconds: Optional[int] = None

class BudgetTracker:
    """Трекер расходов процесса"""

    def __init__(self, budget: ProcessBudget):
        self.budget = budget
        self.spent_usd = 0.0
        self.spent_tokens = 0
        self.start_time = datetime.utcnow()

    def record_usage(self, cost_usd: float, tokens: int):
        self.spent_usd += cost_usd
        self.spent_tokens += tokens

    def is_exceeded(self) -> Tuple[bool, Optional[str]]:
        if self.budget.max_cost_usd and self.spent_usd >= self.budget.max_cost_usd:
            return True, f"Cost budget exceeded: ${self.spent_usd:.2f}/${self.budget.max_cost_usd:.2f}"
        if self.budget.max_tokens and self.spent_tokens >= self.budget.max_tokens:
            return True, f"Token budget exceeded: {self.spent_tokens}/{self.budget.max_tokens}"
        # ... time check
        return False, None
```

#### 4.7.2. Self-Analysis 🟢

```python
class OrchestratorMetrics:
    """Метрики производительности Orchestrator"""

    # Counters
    processes_total: int = 0
    processes_succeeded: int = 0
    processes_failed: int = 0
    commands_sent: int = 0
    errors_received: int = 0

    # Histograms
    process_duration_seconds: List[float] = []
    step_duration_seconds: List[float] = []

    # Agent statistics
    agent_success_rates: Dict[str, float] = {}
    agent_avg_latency: Dict[str, float] = {}

    def success_rate(self) -> float:
        if self.processes_total == 0:
            return 0.0
        return self.processes_succeeded / self.processes_total
```

---

## 5. API спецификация

### 5.1. CloudEvents Types (Отправляемые)

| Type | Описание | Priority |
|------|----------|----------|
| `ai.team.command` | Команда агенту | 20 |
| `ai.team.event` | Событие Orchestrator | 10 |
| `ai.team.control` | Управление агентами | 255 |

### 5.2. CloudEvents Types (Принимаемые)

| Type | Описание | Обработчик |
|------|----------|------------|
| `ai.team.result` | Успешный результат от агента | `handle_result()` |
| `ai.team.error` | Ошибка выполнения | `handle_error()` |
| `ai.team.event` | События от других узлов | `handle_external_event()` |
| `ai.team.control` | Управляющие сигналы | `handle_control()` |

### 5.3. Routing Keys

**Per MindBus Protocol v1.0.1**:

**Orchestrator подписывается на**:
- `evt.{topic}.#` — события системы (подписка по темам, не по источникам!)
- `ctl.orchestrator.#` — управление Orchestrator
- `ctl.all.#` — глобальные управляющие сигналы

**Orchestrator публикует в**:
- `cmd.{role}.{node_id}` — команда конкретному узлу
- `cmd.{role}.any` — команда любому узлу с ролью
- `evt.{topic}.{event_type}` — события от Orchestrator (topic=тема, source в CloudEvents=orchestrator-core)

**RESULT и ERROR** (RPC pattern):
- Агенты отправляют RESULT/ERROR **напрямую** в очередь `reply_to`, указанную в COMMAND
- Orchestrator НЕ подписывается на routing keys для RESULT/ERROR
- Это стандартный AMQP RPC паттерн: публикация в default exchange ("") с routing_key = queue_name

**Философия routing keys** (из MindBus Protocol):
- Routing key описывает **"о чём"** сообщение (тема), а НЕ "от кого" (источник)
- Поле `source` в CloudEvents указывает отправителя
- Примеры EVENT routing keys:
  - `evt.task.completed` — о завершении задачи
  - `evt.process.started` — о запуске процесса
  - `evt.registry.node_registered` — о регистрации узла

### 5.4. Queues

```yaml
# Очереди Orchestrator (per MindBus Protocol v1.0.1)
queues:
  # Очередь для RPC ответов (RESULT/ERROR от агентов)
  # Агенты публикуют напрямую сюда через default exchange
  - name: orchestrator.responses
    durable: true
    arguments:
      x-max-priority: 255

  # Очередь для EVENT подписок (Pub/Sub)
  - name: orchestrator.events
    bindings:
      - exchange: mindbus.main
        routing_key: "evt.task.#"        # События о задачах
      - exchange: mindbus.main
        routing_key: "evt.process.#"     # События о процессах
      - exchange: mindbus.main
        routing_key: "evt.registry.#"    # События реестра

  # Очередь для CONTROL сигналов
  - name: orchestrator.control
    bindings:
      - exchange: mindbus.main
        routing_key: "ctl.orchestrator.#"
      - exchange: mindbus.main
        routing_key: "ctl.all.#"
```

**Примечание**: При отправке COMMAND, Orchestrator указывает `reply_to: "orchestrator.responses"`
в AMQP properties. Агент использует это значение для отправки RESULT/ERROR.

---

## 6. Модель данных

### 6.1. Process State

```python
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

class ProcessPhase(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"

class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class StepState(BaseModel):
    step_id: str
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    last_error: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None

class ProcessState(BaseModel):
    """Состояние выполняемого процесса"""

    # Identity
    process_id: str = Field(description="Уникальный ID процесса")
    process_card_id: str = Field(description="ID Process Card")

    # Phase
    phase: ProcessPhase = ProcessPhase.PENDING

    # Progress
    current_step_id: Optional[str] = None
    steps: Dict[str, StepState] = Field(default_factory=dict)

    # Variables
    variables: Dict[str, Any] = Field(default_factory=dict)

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Tracing
    trace_id: str = Field(description="W3C Trace ID для процесса")

    # Result
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
```

### 6.2. Orchestrator Node Passport

```json
{
  "metadata": {
    "uid": "orchestrator-main-001",
    "name": "orchestrator-main",
    "nodeType": "orchestrator",
    "labels": {
      "role": "orchestrator",
      "capability.task_orchestration": "true",
      "capability.process_management": "true",
      "capability.agent_coordination": "true"
    },
    "creationTimestamp": "2025-12-17T10:00:00Z",
    "version": "1.0.0"
  },
  "spec": {
    "nodeType": "orchestrator",
    "capabilities": [
      {
        "name": "task_orchestration",
        "version": "1.0",
        "parameters": {
          "max_parallel_processes": 100,
          "max_agents_managed": 500,
          "supported_process_card_versions": ["1.0"]
        }
      },
      {
        "name": "llm_planning",
        "version": "1.0",
        "parameters": {
          "supported_models": ["gpt-4", "claude-3"]
        }
      }
    ],
    "resources": {
      "limits": {
        "memory": "4Gi",
        "cpu": "2000m",
        "concurrent_processes": 100
      }
    },
    "endpoint": {
      "protocol": "amqp",
      "queue": "orchestrator.commands.incoming"
    }
  },
  "status": {
    "phase": "Running",
    "conditions": [
      {
        "type": "Ready",
        "status": "True",
        "lastTransitionTime": "2025-12-17T10:00:30Z",
        "reason": "OrchestratorHealthy",
        "message": "Orchestrator is ready to accept tasks"
      },
      {
        "type": "MindBusConnected",
        "status": "True",
        "lastTransitionTime": "2025-12-17T10:00:05Z"
      },
      {
        "type": "RegistryConnected",
        "status": "True",
        "lastTransitionTime": "2025-12-17T10:00:10Z"
      }
    ],
    "lease": {
      "holderIdentity": "orchestrator-main",
      "renewTime": "2025-12-17T12:00:00Z",
      "leaseDurationSeconds": 30
    },
    "activeProcesses": 15,
    "totalProcessesCompleted": 1547
  }
}
```

---

## 7. Конфигурация

### 7.1. Orchestrator Config (Zero Hardcoding)

```yaml
# config/orchestrator.yaml
orchestrator:
  # Identity
  node_id: "orchestrator-main"
  version: "1.0.0"

  # MindBus connection
  mindbus:
    host: ${RABBITMQ_HOST:-localhost}
    port: ${RABBITMQ_PORT:-5672}
    username: ${RABBITMQ_USER:-guest}
    password: ${RABBITMQ_PASSWORD:-guest}
    vhost: ${RABBITMQ_VHOST:-/}

  # State persistence
  state_store:
    type: "postgres"  # или "memory" для MVP
    connection_string: ${DATABASE_URL}

  # Process limits
  limits:
    max_parallel_processes: 100
    max_steps_per_process: 100
    default_step_timeout_seconds: 300
    max_step_timeout_seconds: 3600
    default_process_timeout_seconds: 3600
    max_retries_per_step: 3

  # Policies
  policies:
    budget:
      enabled: true
      max_steps: 100

    retry:
      enabled: true
      max_attempts: 3
      initial_delay_seconds: 5
      backoff_multiplier: 2.0

    safety:
      enabled: false  # Включить в v0.4
      forbidden_actions: []

  # LLM Planner (v0.5+)
  llm_planner:
    enabled: false
    provider: "openai"
    model: "gpt-4"
    api_key: ${OPENAI_API_KEY}

  # Observability
  observability:
    logging:
      level: "INFO"
      format: "json"

    tracing:
      enabled: true
      exporter: "jaeger"
      endpoint: ${JAEGER_ENDPOINT:-http://localhost:14268/api/traces}

    metrics:
      enabled: true
      port: 9090
```

---

## 8. Версионирование

### 8.1. Эволюционный путь

| Версия | Название | Фокус | Ключевые функции |
|--------|----------|-------|------------------|
| **v0.1** | MVP Skeleton | Минимальный рабочий цикл | MindBus + Registry + COMMAND/RESULT |
| **v0.2** | Resilient Runtime | Устойчивость | Retry, Fallback, State persistence |
| **v0.3** | Observable Runtime | Наблюдаемость | CONTROL, Events, Tracing |
| **v0.4** | Policy Manager | Безопасность | Policy Layer, Forbidden actions |
| **v0.5** | Intelligent Planner | LLM-помощник | Goal decomposition, Smart selection |
| **v1.0** | Strategic Leader | Production | Budgets, Self-analysis, Hot-swap |

### 8.2. Архитектурная эволюция

| Версия | Архитектурный вариант |
|--------|-----------------------|
| v0.1-v0.3 | **Deterministic** (простой workflow engine) |
| v0.4 | **Transition** (добавляется Policy Layer) |
| v0.5+ | **Policy-Governed Hybrid** (LLM + Policies) |
| v1.0+ | **Full Hybrid** + optional pure LLM mode |

---

## 9. Метрики и мониторинг

### 9.1. Prometheus Metrics

```python
# Orchestrator metrics
orchestrator_processes_total = Counter(
    "orchestrator_processes_total",
    "Total number of processes started",
    ["status"]  # pending, running, completed, failed
)

orchestrator_commands_sent_total = Counter(
    "orchestrator_commands_sent_total",
    "Total number of commands sent to agents",
    ["action", "agent_role"]
)

orchestrator_errors_received_total = Counter(
    "orchestrator_errors_received_total",
    "Total errors received from agents",
    ["error_code"]
)

orchestrator_process_duration_seconds = Histogram(
    "orchestrator_process_duration_seconds",
    "Process execution duration",
    buckets=[10, 30, 60, 120, 300, 600, 1800, 3600]
)

orchestrator_step_duration_seconds = Histogram(
    "orchestrator_step_duration_seconds",
    "Step execution duration",
    ["action"],
    buckets=[1, 5, 10, 30, 60, 120, 300]
)

orchestrator_active_processes = Gauge(
    "orchestrator_active_processes",
    "Number of currently active processes"
)

orchestrator_policy_violations_total = Counter(
    "orchestrator_policy_violations_total",
    "Policy violations detected",
    ["policy_type"]
)
```

### 9.2. Health Check

```python
class OrchestratorHealth(BaseModel):
    """Health check response"""
    status: Literal["healthy", "degraded", "unhealthy"]
    mindbus_connected: bool
    registry_connected: bool
    state_store_connected: bool
    active_processes: int
    uptime_seconds: int
    version: str

@app.get("/health")
async def health_check() -> OrchestratorHealth:
    return OrchestratorHealth(
        status="healthy",
        mindbus_connected=mindbus.is_connected(),
        registry_connected=registry.is_connected(),
        state_store_connected=state_store.is_connected(),
        active_processes=len(active_processes),
        uptime_seconds=get_uptime(),
        version="1.0.0"
    )
```

---

## 10. Граничные случаи

### 10.1. Все агенты offline

**Проблема**: Нет подходящих узлов для выполнения шага.

**Решение**:
1. v0.1: ERROR "UNAVAILABLE: No agents available"
2. v0.2+: Exponential backoff retry (1s, 2s, 4s...)
3. v0.3+: Публикация EVENT "waiting_for_agents", escalation

### 10.2. Агент упал во время выполнения

**Проблема**: COMMAND отправлен, агент не ответил.

**Решение**:
1. Timeout → ERROR "DEADLINE_EXCEEDED"
2. Retry на другом агенте (fallback)
3. Node Registry heartbeat отмечает узел как offline

### 10.3. Бесконечный цикл в Process Card

**Проблема**: Циклическая зависимость шагов.

**Решение**:
1. Валидация при загрузке карточки (DAG check)
2. Budget policy (max_steps) как защита runtime
3. ERROR "INVALID_ARGUMENT: Circular dependency detected"

### 10.4. Orchestrator crash recovery

**Проблема**: Orchestrator перезапустился во время процесса.

**Решение**:
1. v0.2+: Загрузка активных процессов из State Store
2. Продолжение с текущего шага
3. Re-send команды для IN_PROGRESS шагов (idempotency_key защищает)

---

## 11. Безопасность

### 11.1. Принципы безопасности

1. **Minimal Privilege**: Orchestrator не имеет прямого доступа к данным агентов
2. **Policy Enforcement**: Все действия проходят через Policy Layer
3. **Audit Trail**: Все решения логируются с reasoning
4. **Input Validation**: Все входящие сообщения валидируются против SSOT

### 11.2. Forbidden Actions (v0.4+)

```yaml
safety:
  forbidden_actions:
    - delete_data
    - drop_database
    - rm_rf
    - format_disk
    - send_email_external
    - api_call_unverified
```

### 11.3. Human Approval (v0.4+)

```yaml
approval:
  require_human_approval:
    - action: publish_external
    - action: payment_process
    - action: user_data_export
```

---

## 12. Связанные документы

- **[MindBus Protocol v1.0](mindbus_protocol_v1.md)** — транспорт и CloudEvents
- **[MESSAGE_FORMAT v1.1](MESSAGE_FORMAT_v1.1.md)** — структура сообщений
- **[NODE_REGISTRY v1.0](NODE_REGISTRY_SPEC_v1.0.md)** — реестр узлов
- **[NODE_PASSPORT v1.0](NODE_PASSPORT_SPEC_v1.0.md)** — паспорта узлов
- **[PROCESS_CARD v1.0](PROCESS_CARD_SPEC_v1.0.md)** — карточки процессов
- **[orchestrator_architectures.md](../concepts/orchestrator_architectures.md)** — исходный анализ архитектур
- **[ORCHESTRATOR_FUNCTIONAL_REQUIREMENTS.md](../concepts/ORCHESTRATOR_FUNCTIONAL_REQUIREMENTS.md)** — полные функциональные требования

---

## Финальное заключение

**ORCHESTRATOR SPEC v1.0** — это:

✅ **Консолидация** всех концептуальных документов в единую SSOT спецификацию
✅ **Policy-Governed Hybrid** архитектура (Variant C) как выбранный подход
✅ **Эволюционный путь** от MVP (v0.1) до Production (v1.0)
✅ **Интеграция** со всеми существующими SSOT спецификациями
✅ **Zero Hardcoding** — вся конфигурация вынесена
✅ **Pydantic schemas** для валидации
✅ **Prometheus metrics** для observability

**Следующий шаг**: Реализация Orchestrator v0.1 согласно этой спецификации.

---

## 13. Roadmap улучшений (v1.1+)

Данная секция содержит принятые идеи для будущих версий, собранные по результатам ревью спецификации.

### 13.1. Scheduler как под-компонент (v1.1)

**Текущее состояние**: Orchestrator выполняет планирование, выбор агентов и контроль выполнения как единый монолит.

**Предложение**: Выделить Scheduler как отдельный логический модуль внутри Orchestrator.

**Что это даст**:
- Чёткое разделение ответственности (Single Responsibility)
- Возможность заменять стратегию планирования без изменения остального кода
- Упрощение тестирования логики выбора агентов
- Подготовка к reconciliation loop паттерну (как в Kubernetes Controllers)

**Архитектура**:
```
Orchestrator
├── Scheduler (выбор агентов, балансировка нагрузки)
├── Executor (отправка команд, обработка результатов)
└── PolicyEngine (проверка ограничений)
```

**Целевая версия**: v1.1

---

### 13.2. Формализация idempotency_key (v1.2)

**Текущее состояние**: idempotency_key упоминается как опциональное поле в COMMAND.

**Предложение**: Сделать idempotency_key обязательным стандартом в MESSAGE_FORMAT.

**Что это даст**:
- Гарантированная защита от двойного выполнения при retry
- Единообразное поведение всех агентов
- Упрощение логики восстановления после сбоев

**Изменения**:
1. MESSAGE_FORMAT v1.2: idempotency_key становится REQUIRED для COMMAND
2. Агенты MUST хранить обработанные ключи (TTL: 24 часа)
3. Повторный COMMAND с тем же ключом → возврат кэшированного RESULT

**Целевая версия**: v1.2 (требует обновления MESSAGE_FORMAT)

---

### 13.3. Multi-Orchestrator и High Availability (v1.0 Production)

**Текущее состояние**: Один Orchestrator управляет всей системой. При его падении система останавливается.

**Предложение**: Поддержка нескольких Orchestrator'ов для отказоустойчивости.

**Что это даст**:
- High Availability (HA) — система продолжает работать при падении одного Orchestrator
- Horizontal scaling — распределение нагрузки между несколькими инстансами
- Zero-downtime deployments — обновление без остановки системы

**Архитектура**:
```
┌─────────────────┐     ┌─────────────────┐
│ Orchestrator-1  │     │ Orchestrator-2  │
│    (Leader)     │     │   (Standby)     │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
            ┌─────────────────┐
            │  Leader Election │
            │  (etcd / Redis)  │
            └─────────────────┘
```

**Требования**:
1. Orchestrator регистрируется в Node Registry как обычный узел
2. Leader Election через etcd/Redis/Consul
3. Stateless design (уже реализован) позволяет быстрый failover
4. Process State Store (PostgreSQL) как единый источник состояния

**Целевая версия**: v1.0 Production

---

### 13.4. Единая спецификация безопасности (v1.0 Production)

**Текущее состояние**: Информация о безопасности разбросана по разным документам:
- ORCHESTRATOR_SPEC — Policy Layer, forbidden actions, human approval
- MESSAGE_FORMAT — валидация сообщений, reject невалидных данных
- NODE_PASSPORT — аутентификация узлов, lease mechanism
- MindBus Protocol — AMQP security, TLS
- CLAUDE.md — правила работы с credentials

**Предложение**: Когда система вырастет и вопросы безопасности станут критичнее — собрать всё в единый документ `SECURITY_CONTROLS_v1.0.md`.

**Что войдёт в документ**:
- Аутентификация (кто ты?) — как узлы подтверждают свою идентичность
- Авторизация (что тебе можно?) — права доступа, роли
- Шифрование — TLS, управление секретами
- Валидация данных — SSOT schemas, reject policy
- Аудит — кто что делал, логирование решений
- Forbidden actions — запрещённые операции

**Когда делать**: Когда появятся внешние пользователи, аудиторы, или накопится критическая масса security-требований.

**Целевая версия**: v1.0 Production (не блокер для MVP)

---

### 13.5. Связь с другими SSOT

При реализации улучшений потребуется обновление:

| Улучшение | Затрагиваемые SSOT |
|-----------|-------------------|
| Scheduler модуль | Только ORCHESTRATOR_SPEC (внутренний рефакторинг) |
| idempotency_key | MESSAGE_FORMAT v1.2 |
| Multi-Orchestrator | NODE_REGISTRY (HA patterns), ORCHESTRATOR_SPEC |
| Security Controls | Новый документ, консолидация из всех SSOT |

---

**Версия**: 1.0
**Дата**: 2025-12-17
**Авторы**: AI_TEAM Core Team
**Статус**: ✅ Утверждено (Final Release)
