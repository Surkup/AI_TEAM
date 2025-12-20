# Orchestrator: Temporal + LangGraph

**Статус**: ✅ УТВЕРЖДЕНО (ADR-001)
**Последнее обновление**: 2025-12-20
**Версия**: 2.1

---

## TL;DR

**Orchestrator v2.1 использует двухслойную архитектуру:**

| Слой | Технология | Назначение |
|------|------------|------------|
| **Execution Layer** | Temporal | Durable execution, event sourcing, retry, subprocess |
| **Intelligence Layer** | LangGraph | AI-планирование, Meeting Protocol, Quality Loop |

**Ключевой принцип:**
> LangGraph ВНУТРИ Temporal Activity (не наоборот!)

**Документы:**
- [ADR-001: Temporal + LangGraph](../../concepts/ADR-001_TEMPORAL_LANGGRAPH.md) — обоснование решения
- [ORCHESTRATOR_SPEC_v2.1](../../SSOT/ORCHESTRATOR_SPEC_v2.1.md) — полная спецификация

---

## Что такое Temporal?

**Temporal = workflow engine для долгоживущих процессов**

**Ключевые концепции:**
- **Workflow** = бизнес-процесс (может длиться часы/дни/месяцы)
- **Activity** = отдельный шаг процесса (вызов агента, API, etc.)
- **Event History** = автоматическое сохранение всех действий
- **Automatic retry** = повторы при ошибках с backoff

**Простыми словами:**
> Temporal помнит где остановился workflow, даже если сервер упал. Автоматически повторяет неудавшиеся шаги. Визуализирует выполнение.

---

## Что такое LangGraph?

**LangGraph = фреймворк для создания AI-агентов и multi-agent систем**

**Ключевые концепции:**
- **StateGraph** = граф состояний с переходами
- **Conditional Edges** = динамическая маршрутизация
- **Cycles** = поддержка циклов (quality loops)

**Для Orchestrator используем:**
- **Meeting Protocol** — коллаборативное планирование агентов
- **Quality Loop** — циклы улучшения качества
- **Conflict Resolution** — разрешение конфликтов между агентами

---

## Архитектура Orchestrator v2.1

```
Process Card (YAML)
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│              Temporal Workflow (ProcessCardWorkflow)        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   Activity: parse_process_card()                            │
│       │                                                      │
│       ▼                                                      │
│   Activity: collaborative_planning()  ← LangGraph (Phase 2) │
│       │                                                      │
│       └── Meeting Protocol Graph                            │
│       │                                                      │
│       ▼                                                      │
│   Activity: execute_step()                                  │
│       │                                                      │
│       └── MindBus → Agent → Result                         │
│       │                                                      │
│       ▼                                                      │
│   Activity: quality_check()           ← LangGraph (Phase 2) │
│       │                                                      │
│       └── Quality Loop Graph                                │
│       │                                                      │
│       ▼                                                      │
│   Child Workflow (subprocess)         ← Temporal Native     │
│       │                                                      │
│       ▼                                                      │
│   Activity: finalize()                                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Что даёт Temporal

### 1. Durable Execution

```python
# Если Temporal Worker упадёт в середине workflow...
# После перезапуска workflow продолжится с того же места!
# Не нужно писать логику сохранения/восстановления состояния

@workflow.defn
class ProcessCardWorkflow:
    @workflow.run
    async def run(self, request: ProcessCardRequest) -> ProcessResult:
        # Temporal автоматически сохраняет состояние после каждого Activity
        card = await workflow.execute_activity(parse_process_card, ...)

        # Если сервер упадёт ЗДЕСЬ, Temporal восстановит workflow
        # и НЕ будет повторять parse_process_card (already completed)

        plan = await workflow.execute_activity(collaborative_planning, ...)
        # ... и т.д.
```

### 2. Automatic Retry с Backoff

```python
# Retry Policy — автоматические повторы при ошибках
retry_policy = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=3,
    non_retryable_error_types=["ValidationError"],
)

result = await workflow.execute_activity(
    execute_step,
    request,
    retry_policy=retry_policy,
    start_to_close_timeout=timedelta(minutes=5),
)
```

### 3. Child Workflows (Subprocesses)

```python
# Subprocess = Child Workflow в Temporal
result = await workflow.execute_child_workflow(
    ProcessCardWorkflow.run,
    ProcessCardRequest(
        card_yaml=step.subprocess_ref,
        context=ChildContext(
            parent_process_id=self.state.process_id,
            inputs={"topic": self.state.variables.get("topic")},
        ),
    ),
    execution_timeout=timedelta(minutes=10),
)
```

### 4. Signals & Queries

```python
@workflow.defn
class ProcessCardWorkflow:
    @workflow.signal
    async def cancel_workflow(self, reason: str):
        """Внешний сигнал для отмены workflow"""
        self.state.status = "cancelled"
        self.state.cancel_reason = reason

    @workflow.query
    def get_progress(self) -> dict:
        """Запрос текущего состояния без изменения"""
        return {
            "current_step": self.state.current_step,
            "completed_steps": self.state.completed_steps,
            "status": self.state.status,
        }
```

### 5. Temporal UI (Web Dashboard)

```
http://localhost:8080  # Temporal Web UI

Показывает:
- Все запущенные workflows
- Текущий шаг выполнения
- Полная история activities
- Ошибки и retry attempts
- Latency каждого шага
- Time-travel debugging
```

---

## Что даёт LangGraph

### Meeting Protocol (Collaborative Planning)

```python
from langgraph.graph import StateGraph, END

class MeetingState(TypedDict):
    topic: str
    participants: list[str]
    proposals: list[dict]
    conflicts: list[dict]
    final_plan: Optional[dict]

def build_meeting_graph() -> StateGraph:
    workflow = StateGraph(MeetingState)

    workflow.add_node("collect_proposals", collect_proposals)
    workflow.add_node("detect_conflicts", detect_conflicts)
    workflow.add_node("resolve_conflicts", resolve_conflicts)
    workflow.add_node("finalize_plan", finalize_plan)

    workflow.add_edge("collect_proposals", "detect_conflicts")
    workflow.add_conditional_edges(
        "detect_conflicts",
        has_conflicts,
        {True: "resolve_conflicts", False: "finalize_plan"}
    )
    workflow.add_edge("resolve_conflicts", "detect_conflicts")  # Cycle!
    workflow.add_edge("finalize_plan", END)

    workflow.set_entry_point("collect_proposals")
    return workflow.compile()
```

### Quality Loop

```python
class QualityState(TypedDict):
    result: str
    score: float
    feedback: str
    iteration: int

def build_quality_graph() -> StateGraph:
    workflow = StateGraph(QualityState)

    workflow.add_node("evaluate", evaluate_quality)
    workflow.add_node("improve", improve_result)

    workflow.add_conditional_edges(
        "evaluate",
        lambda s: s["score"] >= 8.0 or s["iteration"] >= 3,
        {True: END, False: "improve"}
    )
    workflow.add_edge("improve", "evaluate")  # Cycle!

    workflow.set_entry_point("evaluate")
    return workflow.compile()
```

---

## Интеграция Temporal + LangGraph

**Критическое правило:** LangGraph вызывается ВНУТРИ Temporal Activity

```python
# ✅ ПРАВИЛЬНО: LangGraph внутри Activity
@activity.defn
async def collaborative_planning(request: PlanningRequest) -> Plan:
    """Temporal Activity вызывает LangGraph"""
    graph = build_meeting_graph()

    # Heartbeat для долгих LLM операций
    async def heartbeat_loop():
        while True:
            activity.heartbeat({"status": "processing"})
            await asyncio.sleep(30)

    heartbeat_task = asyncio.create_task(heartbeat_loop())

    try:
        result = await graph.ainvoke({
            "topic": request.topic,
            "participants": request.participants,
        })
        return result["final_plan"]
    finally:
        heartbeat_task.cancel()


@workflow.defn
class ProcessCardWorkflow:
    @workflow.run
    async def run(self, request: ProcessCardRequest) -> ProcessResult:
        # Temporal обеспечивает durability
        plan = await workflow.execute_activity(
            collaborative_planning,
            PlanningRequest(topic=request.topic),
            start_to_close_timeout=timedelta(minutes=10),
            heartbeat_timeout=timedelta(seconds=60),
        )
```

```python
# ❌ НЕПРАВИЛЬНО: LangGraph как верхний уровень — теряем durability!
graph = build_workflow_graph()  # LangGraph
result = graph.invoke(...)  # Если упадёт — всё потеряно!
```

---

## Сравнение: Custom vs Temporal

| Функция | Custom | Temporal |
|---------|--------|----------|
| **Код для MVP** | 500+ строк | 100-200 строк |
| **State persistence** | Писать вручную | Автоматически ✅ |
| **Retry logic** | Писать вручную | Автоматически ✅ |
| **Event sourcing** | Писать вручную | Автоматически ✅ |
| **Subprocess** | Писать вручную | Child Workflows ✅ |
| **Визуализация** | Писать вручную | Web UI из коробки ✅ |
| **Версионирование** | Писать вручную | workflow.patched() ✅ |
| **Learning curve** | 1 день | 2-3 дня |

**Экономия:** 15-21 неделя разработки

---

## Docker Compose для MVP

```yaml
version: '3.8'

services:
  # Temporal Server
  temporal:
    image: temporalio/auto-setup:latest
    ports:
      - "7233:7233"  # gRPC
      - "8080:8080"  # Web UI
    environment:
      - DB=sqlite  # SQLite для MVP, PostgreSQL для production

  # Temporal Worker (наш Orchestrator)
  orchestrator:
    build: ./orchestrator
    environment:
      - TEMPORAL_SERVER=temporal:7233
      - MINDBUS_URL=amqp://rabbitmq:5672
    depends_on:
      - temporal
      - rabbitmq

  # RabbitMQ (MindBus)
  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "5672:5672"
      - "15672:15672"
```

---

## MVP Scope (Phase 1)

**Что ВХОДИТ в MVP:**

| Компонент | Описание |
|-----------|----------|
| **ProcessCardWorkflow** | Основной workflow для Process Card |
| **parse_process_card** | Activity для парсинга YAML |
| **execute_step** | Activity для выполнения шага через MindBus |
| **Retry Policy** | Базовые ретраи с backoff |
| **Child Workflows** | Поддержка subprocess |
| **Temporal UI** | Мониторинг из коробки |

**Что НЕ ВХОДИТ в MVP (Phase 2):**

| Компонент | Причина отложения |
|-----------|-------------------|
| **collaborative_planning** | Требует LangGraph |
| **quality_loop** | Требует LangGraph |
| **Meeting Protocol** | Сложная multi-agent логика |
| **Saga / Compensation** | Можно добавить позже |

---

## Альтернативы (отвергнуты)

### ❌ Custom State Machine

**Почему НЕТ:**
- Reinventing Temporal (15-21 неделя работы)
- Нет event sourcing
- Нет автоматического retry
- Нет time-travel debugging

### ❌ Apache Airflow

**Почему НЕТ:**
- Для batch ETL, не для event-driven
- DAG фиксирован, нельзя менять динамически

### ❌ Netflix Conductor

**Почему НЕТ:**
- Менее активное community
- Java-first (Python SDK менее развит)

---

## Компании используют Temporal

- **Uber** — управление заказами
- **Netflix** — media processing
- **Stripe** — платёжные workflows
- **Coinbase** — финансовые транзакции
- **HashiCorp** — infrastructure provisioning

---

## Связанные документы

- [ADR-001: Temporal + LangGraph](../../concepts/ADR-001_TEMPORAL_LANGGRAPH.md)
- [ORCHESTRATOR_SPEC_v2.1](../../SSOT/ORCHESTRATOR_SPEC_v2.1.md)
- [IMPLEMENTATION_ROADMAP — Этап 5.5](../../project/IMPLEMENTATION_ROADMAP.md)
- [MindBus Protocol v1.0](../../SSOT/mindbus_protocol_v1.md)
- [PROCESS_CARD_SPEC v1.0](../../SSOT/PROCESS_CARD_SPEC_v1.0.md)

---

**Статус:** ✅ УТВЕРЖДЕНО
**Последнее обновление:** 2025-12-20
