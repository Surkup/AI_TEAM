# ORCHESTRATOR Specification v2.1

**Статус**: ✅ APPROVED (SSOT v2.1)
**Версия**: 2.1.0
**Дата утверждения**: 2025-12-20
**Основа**: ORCHESTRATOR_SPEC v1.0 + v2.0 DRAFT + ADR-001 (Temporal + LangGraph)
**Архитектурное решение**: [ADR-001](../concepts/ADR-001_TEMPORAL_LANGGRAPH.md) (неотъемлемая часть)

---

## TL;DR (Executive Summary)

**ORCHESTRATOR v2.1** — это эволюция Orchestrator с использованием **production-ready** технологий:

| Слой | Технология | Назначение |
|------|------------|------------|
| **Execution Layer** | Temporal | Надёжное выполнение, recovery, subprocesses |
| **Intelligence Layer** | LangGraph | AI-логика: planning, meetings, quality |
| **Transport Layer** | MindBus (AMQP) | Коммуникация с агентами |

**Ключевой принцип**:
> "Тупой" надёжный фундамент (Temporal) + "умная" надстройка (LangGraph)

**Главное правило**:
> LangGraph ВНУТРИ Temporal Activity, не наоборот

---

## 1. Философия v2.1

### 1.1. Мировой опыт

Исследование показало (см. [ORCHESTRATOR_WORLD_EXPERIENCE_RESEARCH](ORCHESTRATOR_WORLD_EXPERIENCE_RESEARCH.md)):

> **Process Management = State Machine + Event Log + Orchestration Engine**

Успешные системы (Uber, Netflix, Stripe) пришли к выводу:
- Orchestrator должен быть **детерминированным и надёжным**
- Интеллект (AI) — это **плагины**, не ядро
- Event Sourcing обеспечивает recovery и audit

### 1.2. Двухслойная архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR v2.1                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ╔═══════════════════════════════════════════════════════════╗  │
│   ║           INTELLIGENCE LAYER (LangGraph)                   ║  │
│   ║                                                             ║  │
│   ║   ┌─────────────────┐   ┌─────────────────────────────┐   ║  │
│   ║   │ Meeting Protocol│   │ Quality Loop               │   ║  │
│   ║   │ (multi-agent)   │   │ (evaluate → improve)       │   ║  │
│   ║   └─────────────────┘   └─────────────────────────────┘   ║  │
│   ║   ┌─────────────────┐   ┌─────────────────────────────┐   ║  │
│   ║   │ Dynamic Planning│   │ Conflict Resolution        │   ║  │
│   ║   │ (LLM-based)     │   │ (conditional routing)      │   ║  │
│   ║   └─────────────────┘   └─────────────────────────────┘   ║  │
│   ╚═══════════════════════════════════════════════════════════╝  │
│                               │                                   │
│                               │ Activities                        │
│                               ▼                                   │
│   ╔═══════════════════════════════════════════════════════════╗  │
│   ║            EXECUTION LAYER (Temporal)                      ║  │
│   ║                                                             ║  │
│   ║   ┌─────────────────┐   ┌─────────────────────────────┐   ║  │
│   ║   │ Workflow Engine │   │ Event History               │   ║  │
│   ║   │ (state machine) │   │ (audit trail)               │   ║  │
│   ║   └─────────────────┘   └─────────────────────────────┘   ║  │
│   ║   ┌─────────────────┐   ┌─────────────────────────────┐   ║  │
│   ║   │ Child Workflows │   │ Retry + Compensation        │   ║  │
│   ║   │ (subprocesses)  │   │ (Saga pattern)              │   ║  │
│   ║   └─────────────────┘   └─────────────────────────────┘   ║  │
│   ╚═══════════════════════════════════════════════════════════╝  │
│                               │                                   │
│                               │ COMMAND / RESULT                  │
│                               ▼                                   │
│   ┌───────────────────────────────────────────────────────────┐  │
│   │                    MindBus (AMQP)                          │  │
│   │                    CloudEvents                             │  │
│   └───────────────────────────────────────────────────────────┘  │
│                               │                                   │
│              ┌────────────────┼────────────────┐                  │
│              ▼                ▼                ▼                  │
│         ┌─────────┐    ┌─────────┐    ┌─────────┐               │
│         │ Agent 1 │    │ Agent 2 │    │ Agent N │               │
│         └─────────┘    └─────────┘    └─────────┘               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3. Отличие от n8n и классических workflow engines

| Аспект | n8n / Airflow | AI_TEAM Orchestrator v2.1 |
|--------|---------------|---------------------------|
| **Планирование** | Человек рисует workflow | **AI генерирует** план |
| **Адаптация** | Жёсткий алгоритм | **Динамическая** адаптация |
| **При ошибке** | Стоп или retry | **AI решает** что делать |
| **Качество** | Нет проверки | **Quality Loop** с критикой |
| **Команда** | Один исполнитель | **Совещание** агентов |

---

## 2. Компоненты системы

### 2.1. Temporal (Execution Layer)

**Назначение**: Надёжное выполнение workflows с гарантиями.

**Что даёт Temporal**:

| Функция | Описание |
|---------|----------|
| **Durable Execution** | Workflow переживает рестарты, сбои, deployments |
| **Event History** | Полная история всех действий (audit trail) |
| **Exactly-once (Workflow)** | Логическая гарантия однократного выполнения *на уровне workflow state* |
| **At-least-once (Activity)** | Activities могут выполняться повторно — **требуется идемпотентность!** |
| **Child Workflows** | Вложенные процессы (наши subprocesses) |
| **Activity Retry** | Автоматический retry с backoff |
| **Saga Pattern** | Compensating transactions |
| **Signals** | Внешние события в workflow |
| **Queries** | Получение состояния без изменения |

> ⚠️ **КРИТИЧЕСКИ ВАЖНО**: Temporal гарантирует exactly-once только на уровне *workflow state*.
> Activities выполняются **at-least-once**. Каждое взаимодействие с агентом и storage
> **ОБЯЗАНО быть идемпотентным** по `idempotency_key` / `correlation_id`.
> Любые I/O операции — **только в Activities**, никогда в Workflow code.

**Mapping на наши концепции**:

| AI_TEAM Concept | Temporal Concept |
|-----------------|------------------|
| Process Card | Workflow Definition |
| Process Instance | Workflow Execution |
| Step | Activity |
| Subprocess | Child Workflow |
| State Contract | Workflow State + Event History |
| Recovery | Replay from Event History |
| Idempotency | Workflow ID + Idempotency Key |
| Variables | Workflow State |
| Budget | Workflow Metadata + Signals |

### 2.2. LangGraph (Intelligence Layer)

**Назначение**: AI-логика для принятия решений.

**Что даёт LangGraph**:

| Функция | Описание |
|---------|----------|
| **Graph-based flows** | Nodes, edges, conditional routing |
| **Cyclical graphs** | Loops для Quality Loop |
| **State management** | In-thread и cross-thread memory |
| **Multi-agent** | Координация нескольких агентов |
| **Conditional routing** | Ветвление по условиям |

**Где используется LangGraph**:

| Компонент | Описание |
|-----------|----------|
| **Meeting Protocol** | Совещание агентов для планирования |
| **Quality Loop** | Оценка → критика → улучшение |
| **Conflict Resolution** | Разрешение конфликтов между агентами |
| **Dynamic Planning** | Генерация плана с помощью LLM |

**КРИТИЧЕСКОЕ ПРАВИЛО**:
> LangGraph вызывается ВНУТРИ Temporal Activity.
> Temporal обеспечивает durability, LangGraph — логику.

### 2.3. MindBus (Transport Layer)

**Без изменений** относительно v1.0:
- AMQP (RabbitMQ)
- CloudEvents format
- MESSAGE_FORMAT v1.1 (COMMAND, RESULT, ERROR, EVENT, CONTROL)

---

## 3. Process Card Execution Flow

### 3.1. Общая схема

```
Process Card (YAML)
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Temporal Workflow                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. PARSE ─────────────────────────────────────────────────►│
│     Activity: parse_process_card()                           │
│     • Загрузка YAML                                          │
│     • Валидация структуры                                    │
│     • Проверка зависимостей                                  │
│                                                              │
│  2. PLAN (optional) ───────────────────────────────────────►│
│     Activity: collaborative_planning()  ← LangGraph          │
│     • Meeting Protocol                                       │
│     • Сбор proposals от агентов                              │
│     • Разрешение конфликтов                                  │
│     • Генерация/уточнение плана                              │
│                                                              │
│  3. EXECUTE ───────────────────────────────────────────────►│
│     for each step in plan:                                   │
│         │                                                    │
│         ├── Simple Step? ─► Activity: execute_step()         │
│         │   • Отправка COMMAND через MindBus                 │
│         │   • Ожидание RESULT/ERROR                          │
│         │   • Сохранение output                              │
│         │                                                    │
│         └── Subprocess? ─► Child Workflow                    │
│             • Рекурсивное выполнение                         │
│             • Изоляция состояния                             │
│             • Boundary Artifacts                             │
│                                                              │
│  4. QUALITY CHECK (optional) ──────────────────────────────►│
│     Activity: quality_loop()  ← LangGraph                    │
│     • Оценка результата                                      │
│     • PASS → продолжаем                                      │
│     • FAIL → retry с feedback                                │
│                                                              │
│  5. FINALIZE ──────────────────────────────────────────────►│
│     Activity: finalize_process()                             │
│     • Сборка результата                                      │
│     • Сохранение артефактов                                  │
│     • Публикация EVENT о завершении                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.2. Код: Main Workflow

```python
from datetime import timedelta
from temporalio import workflow, activity
from temporalio.common import RetryPolicy

@workflow.defn
class ProcessCardWorkflow:
    """Главный workflow для выполнения Process Card"""

    def __init__(self):
        self.state = ProcessState()

    @workflow.run
    async def run(self, request: ProcessCardRequest) -> ProcessResult:
        # 1. Parse Process Card
        card = await workflow.execute_activity(
            parse_process_card,
            request.card_yaml,
            start_to_close_timeout=timedelta(seconds=30),
        )

        # 2. Collaborative Planning (if complex task)
        if self.needs_planning(card):
            plan = await workflow.execute_activity(
                collaborative_planning,
                PlanningRequest(card=card, context=request.context),
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            card = self.apply_plan(card, plan)

        # 3. Execute steps
        for step in card.spec.steps:
            if step.type == "subprocess":
                # Child Workflow для subprocess
                result = await workflow.execute_child_workflow(
                    ProcessCardWorkflow.run,
                    ProcessCardRequest(
                        card_yaml=step.subprocess_ref,
                        context=self.create_child_context(step),
                        budget=self.allocate_budget(step),
                    ),
                )
            else:
                # Activity для обычного шага
                result = await workflow.execute_activity(
                    execute_step,
                    ExecuteStepRequest(step=step, state=self.state),
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=self.get_retry_policy(step),
                )

            # Сохраняем результат
            self.state.variables[step.output] = result.output

            # 4. Quality Check (if configured)
            if step.quality_check:
                quality = await workflow.execute_activity(
                    quality_loop,
                    QualityRequest(step=step, result=result, state=self.state),
                    start_to_close_timeout=timedelta(minutes=5),
                )
                if quality.verdict == "FAIL":
                    # Retry с feedback
                    continue  # Loop back

        # 5. Finalize
        return await workflow.execute_activity(
            finalize_process,
            FinalizeRequest(state=self.state),
            start_to_close_timeout=timedelta(seconds=30),
        )
```

### 3.3. Код: Execute Step Activity

```python
@activity.defn
async def execute_step(request: ExecuteStepRequest) -> StepResult:
    """
    Activity для выполнения одного шага Process Card.
    Отправляет COMMAND через MindBus, ждёт RESULT.
    """
    step = request.step
    state = request.state

    # 1. Найти подходящего агента
    agent = await node_registry.find_agent(
        capabilities=step.requirements.get("capabilities", []),
        status="ready",
    )

    if not agent:
        raise ApplicationError(
            "No suitable agent found",
            type="UNAVAILABLE",
            non_retryable=False,  # Можно retry
        )

    # 2. Подготовить COMMAND
    command = CloudEvent(
        type="ai.team.command",
        source="orchestrator",
        data={
            "action": step.action,
            "params": resolve_variables(step.params, state.variables),
            "context": {
                "process_id": state.process_id,
                "step_id": step.id,
            },
            "timeout_seconds": step.timeout or 300,
            "idempotency_key": f"{state.process_id}:{step.id}:{state.attempt}",
        },
    )

    # 3. Отправить через MindBus и ждать ответ
    result = await mindbus.send_and_wait(
        command=command,
        target_agent=agent.uid,
        timeout=timedelta(seconds=step.timeout or 300),
    )

    # 4. Обработать результат
    if result.type == "ai.team.error":
        error_data = result.data.get("error", {})
        raise ApplicationError(
            error_data.get("message", "Unknown error"),
            type=error_data.get("code", "INTERNAL"),
            non_retryable=not error_data.get("retryable", True),
        )

    return StepResult(
        step_id=step.id,
        output=result.data.get("output", {}),
        agent_id=agent.uid,
    )
```

---

## 4. Intelligence Layer: LangGraph Components

### 4.1. Meeting Protocol (Activity)

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional

class MeetingState(TypedDict):
    """Состояние совещания агентов"""
    topic: str
    participants: List[str]
    proposals: List[Proposal]
    conflicts: List[Conflict]
    final_plan: Optional[Plan]

def build_meeting_graph() -> StateGraph:
    """Строит граф для Meeting Protocol"""

    graph = StateGraph(MeetingState)

    # Nodes
    graph.add_node("invite_agents", invite_agents)
    graph.add_node("collect_proposals", collect_proposals)
    graph.add_node("detect_conflicts", detect_conflicts)
    graph.add_node("resolve_conflicts", resolve_conflicts)
    graph.add_node("synthesize_plan", synthesize_plan)
    graph.add_node("validate_plan", validate_plan)

    # Edges
    graph.set_entry_point("invite_agents")
    graph.add_edge("invite_agents", "collect_proposals")
    graph.add_edge("collect_proposals", "detect_conflicts")

    # Conditional: есть конфликты?
    graph.add_conditional_edges(
        "detect_conflicts",
        lambda s: "resolve" if s["conflicts"] else "synthesize",
        {
            "resolve": "resolve_conflicts",
            "synthesize": "synthesize_plan",
        }
    )

    graph.add_edge("resolve_conflicts", "synthesize_plan")
    graph.add_edge("synthesize_plan", "validate_plan")
    graph.add_edge("validate_plan", END)

    return graph.compile()


@activity.defn
async def collaborative_planning(request: PlanningRequest) -> Plan:
    """
    Temporal Activity: Коллаборативное планирование.
    Использует LangGraph для координации агентов.
    """
    graph = build_meeting_graph()

    result = await graph.ainvoke({
        "topic": request.card.metadata.name,
        "participants": find_relevant_agents(request.card),
        "proposals": [],
        "conflicts": [],
        "final_plan": None,
    })

    return result["final_plan"]
```

### 4.2. Quality Loop (Activity)

```python
class QualityState(TypedDict):
    """Состояние Quality Loop"""
    result: Any
    criteria: List[QualityCriterion]
    evaluation: Optional[Evaluation]
    feedback: Optional[Feedback]
    verdict: str  # PASS, MARGINAL, FAIL
    iteration: int

def build_quality_graph() -> StateGraph:
    """Строит граф для Quality Loop"""

    graph = StateGraph(QualityState)

    # Nodes
    graph.add_node("evaluate", evaluate_result)
    graph.add_node("decide", decide_action)
    graph.add_node("generate_feedback", generate_feedback)

    # Entry
    graph.set_entry_point("evaluate")

    # Edges
    graph.add_edge("evaluate", "decide")

    # Conditional: что делать?
    graph.add_conditional_edges(
        "decide",
        lambda s: s["verdict"],
        {
            "PASS": END,
            "MARGINAL": "generate_feedback",
            "FAIL": "generate_feedback",
        }
    )

    # Feedback возвращается caller'у для retry
    graph.add_edge("generate_feedback", END)

    return graph.compile()


@activity.defn
async def quality_loop(request: QualityRequest) -> QualityResult:
    """
    Temporal Activity: Оценка качества результата.
    Использует LangGraph для цикла критики.
    """
    graph = build_quality_graph()

    result = await graph.ainvoke({
        "result": request.result.output,
        "criteria": request.step.quality_criteria or default_criteria(),
        "evaluation": None,
        "feedback": None,
        "verdict": "PENDING",
        "iteration": request.state.quality_iterations,
    })

    return QualityResult(
        verdict=result["verdict"],
        score=result["evaluation"].score if result["evaluation"] else 0,
        feedback=result["feedback"],
    )
```

---

## 5. State Management

### 5.1. Temporal Event History = State Contract

**В v2.0 DRAFT мы описывали State Contract вручную. Temporal делает это автоматически.**

```
Event History (автоматически):
┌─────────────────────────────────────────────────────────────┐
│ WorkflowExecutionStarted                                     │
│ ActivityTaskScheduled (parse_process_card)                   │
│ ActivityTaskStarted                                          │
│ ActivityTaskCompleted (result: {...})                        │
│ ActivityTaskScheduled (execute_step: step-1)                 │
│ ActivityTaskStarted                                          │
│ ActivityTaskCompleted (result: {...})                        │
│ ChildWorkflowExecutionStarted (subprocess-1)                 │
│ ChildWorkflowExecutionCompleted (result: {...})              │
│ ActivityTaskScheduled (quality_loop)                         │
│ ...                                                          │
│ WorkflowExecutionCompleted                                   │
└─────────────────────────────────────────────────────────────┘
```

**Что это даёт**:
- ✅ Полный audit trail
- ✅ Recovery: при рестарте Temporal replay'ит события
- ✅ Time-travel: можно посмотреть состояние в любой момент
- ✅ Debugging: видно каждый шаг

### 5.2. Workflow State

```python
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime

class ProcessState(BaseModel):
    """Состояние процесса (хранится в Temporal Workflow)"""

    # Identity
    process_id: str
    process_card_id: str
    trace_id: str

    # Progress
    current_step_id: Optional[str] = None
    completed_steps: List[str] = []
    failed_steps: List[str] = []

    # Variables (outputs from steps)
    variables: Dict[str, Any] = {}

    # Budget tracking
    budget_allocated: ProcessBudget
    budget_spent: BudgetUsage = BudgetUsage()

    # Quality iterations
    quality_iterations: int = 0

    # For retry
    attempt: int = 1

    # Timing
    started_at: datetime
    deadline: Optional[datetime] = None
```

### 5.3. Recovery

**Temporal автоматически восстанавливает процессы после сбоя:**

```python
# При рестарте Temporal:
# 1. Загружает Event History
# 2. Replay'ит события (Activity results кэшированы)
# 3. Продолжает с того места, где остановился

# Нам НЕ нужно писать recovery логику!
```

---

## 6. Subprocess (Child Workflows)

### 6.1. Изоляция подпроцессов

**КРИТИЧЕСКОЕ ПРАВИЛО: Child Workflow НЕ имеет доступа к переменным родителя.**

Это фундаментальный принцип изоляции, предотвращающий побочные эффекты.

```python
# В главном workflow:
result = await workflow.execute_child_workflow(
    ProcessCardWorkflow.run,
    ProcessCardRequest(
        card_yaml=step.subprocess_ref,
        context=ChildContext(
            parent_process_id=self.state.process_id,
            root_process_id=self.state.root_process_id or self.state.process_id,
            # Boundary Artifacts: ТОЛЬКО явные inputs
            inputs={
                "topic": self.state.variables.get("topic"),
                "constraints": self.state.variables.get("constraints"),
            },
        ),
        budget=Budget(
            max_cost_usd=self.state.budget_allocated.max_cost_usd * 0.2,  # 20%
            max_time_seconds=step.timeout or 600,
        ),
    ),
    # Child Workflow имеет свой timeout
    execution_timeout=timedelta(seconds=step.timeout or 600),
)

# Child Workflow НЕ видит все переменные родителя — только inputs
# Это Boundary Artifacts из v2.0 DRAFT
```

### 6.1.1. Правила изоляции Subprocess (INVARIANTS)

| Инвариант | Описание |
|-----------|----------|
| **INV-SUB-1** | Child Workflow получает ТОЛЬКО те данные, которые явно переданы в `inputs` |
| **INV-SUB-2** | Child Workflow НЕ может читать `self.state.variables` родителя |
| **INV-SUB-3** | Child Workflow НЕ может модифицировать состояние родителя |
| **INV-SUB-4** | Результат Child Workflow возвращается как единый объект (Boundary Artifact) |
| **INV-SUB-5** | Budget Child Workflow <= Budget родителя (аллоцированная часть) |

**Пример нарушения (ЗАПРЕЩЕНО)**:

```python
# ❌ НЕПРАВИЛЬНО: передача всего state
result = await workflow.execute_child_workflow(
    ProcessCardWorkflow.run,
    ProcessCardRequest(
        card_yaml=step.subprocess_ref,
        context=ChildContext(
            inputs=self.state.variables,  # ❌ Передаём ВСЁ — нарушение изоляции!
        ),
    ),
)
```

**Правильный подход**:

```python
# ✅ ПРАВИЛЬНО: явный allowlist
ALLOWED_INPUTS_FOR_SUBPROCESS = ["topic", "constraints", "style_guide"]

result = await workflow.execute_child_workflow(
    ProcessCardWorkflow.run,
    ProcessCardRequest(
        card_yaml=step.subprocess_ref,
        context=ChildContext(
            inputs={
                key: self.state.variables.get(key)
                for key in step.subprocess_inputs  # Явно указано в Process Card
                if key in ALLOWED_INPUTS_FOR_SUBPROCESS
            },
        ),
    ),
)
```

**Process Card: объявление subprocess inputs**:

```yaml
steps:
  - id: "detailed_research"
    type: "subprocess"
    subprocess_ref: "research_deep_dive.yaml"
    subprocess_inputs:  # Явный allowlist
      - "topic"
      - "constraints"
    output: "research_result"
```

### 6.1.2. Boundary Artifact Contract

**Формальный контракт** для данных, передаваемых между parent и child workflows.

```python
from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime

class BoundaryArtifact(BaseModel):
    """
    Контракт для данных на границе subprocess.
    Используется как для inputs, так и для outputs.
    """
    # Identity
    artifact_id: str              # Уникальный ID: "ba_{uuid4}"
    process_id: str               # ID процесса-владельца
    direction: str                # "input" | "output"

    # Content
    schema_ref: Optional[str]     # Ссылка на JSON Schema (если есть)
    content_type: str             # MIME type: "application/json", "text/plain"
    payload: Optional[Any]        # Inline данные (для маленьких объектов)
    uri: Optional[str]            # URI в Storage (для больших объектов)

    # Metadata
    created_at: datetime
    created_by: str               # Кто создал: parent process_id или child process_id

    class Config:
        # Валидация: либо payload, либо uri
        @validator('uri', always=True)
        def payload_or_uri(cls, v, values):
            if not v and not values.get('payload'):
                raise ValueError("Either payload or uri must be set")
            return v
```

**Правило размера**:

| Размер данных | Где хранить |
|---------------|-------------|
| < 64 KB | `payload` (inline) |
| >= 64 KB | `uri` (Storage) |

**Пример использования**:

```python
# Parent → Child: создаём input artifact
input_artifact = BoundaryArtifact(
    artifact_id=f"ba_{workflow.uuid4()}",
    process_id=self.state.process_id,
    direction="input",
    content_type="application/json",
    payload={"topic": "AI Agents", "constraints": ["max 5 pages"]},
    created_at=workflow.now(),
    created_by=self.state.process_id,
)

# Child → Parent: возвращаем output artifact
output_artifact = BoundaryArtifact(
    artifact_id=f"ba_{workflow.uuid4()}",
    process_id=child_process_id,
    direction="output",
    content_type="application/json",
    uri="storage://artifacts/research_result_001.json",  # Большой документ
    created_at=workflow.now(),
    created_by=child_process_id,
)
```

### 6.2. Лимиты вложенности

```python
# Temporal не имеет встроенного лимита, но мы добавляем:
MAX_SUBPROCESS_DEPTH = 10

@workflow.defn
class ProcessCardWorkflow:
    @workflow.run
    async def run(self, request: ProcessCardRequest) -> ProcessResult:
        # Проверка глубины
        depth = request.context.get("depth", 0)
        if depth >= MAX_SUBPROCESS_DEPTH:
            raise ApplicationError(
                f"Max subprocess depth ({MAX_SUBPROCESS_DEPTH}) exceeded",
                type="RESOURCE_EXHAUSTED",
                non_retryable=True,
            )

        # При создании child workflow — передаём depth + 1
        child_request = ProcessCardRequest(
            ...,
            context={**request.context, "depth": depth + 1},
        )
```

---

## 7. Error Handling

### 7.1. Temporal Retry Policy

```python
# Retry с exponential backoff
retry_policy = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=3,
    non_retryable_error_types=[
        "INVALID_ARGUMENT",
        "NOT_FOUND",
        "PERMISSION_DENIED",
    ],
)

result = await workflow.execute_activity(
    execute_step,
    request,
    start_to_close_timeout=timedelta(minutes=5),
    retry_policy=retry_policy,
)
```

### 7.2. Saga / Compensation

```python
@workflow.defn
class BookWritingWorkflow:
    @workflow.run
    async def run(self, request: BookRequest) -> Book:
        compensations = []

        try:
            # Step 1: Research
            research = await workflow.execute_activity(
                research_topic, request.topic
            )
            compensations.append(lambda: cleanup_research(research.id))

            # Step 2: Outline
            outline = await workflow.execute_activity(
                create_outline, research
            )
            compensations.append(lambda: archive_outline(outline.id))

            # Step 3: Write chapters
            chapters = []
            for i in range(request.chapter_count):
                chapter = await workflow.execute_activity(
                    write_chapter, outline, i
                )
                chapters.append(chapter)
                compensations.append(lambda c=chapter: delete_draft(c.id))

            return Book(chapters=chapters)

        except Exception as e:
            # Compensate in reverse order
            for compensate in reversed(compensations):
                try:
                    await workflow.execute_activity(compensate)
                except Exception:
                    pass  # Best effort
            raise
```

### 7.3. Activity Heartbeat для долгих LLM-задач

**Проблема**: LangGraph Activities (collaborative_planning, quality_loop) могут выполняться долго (минуты). Temporal может посчитать Activity "мёртвой" и сделать retry.

**Решение**: Использовать Heartbeat для сигнализации о прогрессе.

```python
from temporalio import activity
from temporalio.exceptions import CancelledError
import asyncio

@activity.defn
async def collaborative_planning(request: PlanningRequest) -> Plan:
    """
    Long-running Activity с Heartbeat.
    Temporal знает, что Activity жива, даже если LLM думает долго.
    """
    graph = build_meeting_graph()

    # Heartbeat task — сигнализирует каждые 30 сек
    async def heartbeat_loop():
        while True:
            try:
                activity.heartbeat({"status": "processing", "step": "llm_call"})
                await asyncio.sleep(30)
            except CancelledError:
                break

    heartbeat_task = asyncio.create_task(heartbeat_loop())

    try:
        result = await graph.ainvoke({
            "topic": request.card.metadata.name,
            "participants": find_relevant_agents(request.card),
            "proposals": [],
            "conflicts": [],
            "final_plan": None,
        })
        return result["final_plan"]
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except CancelledError:
            pass


# В Workflow — настройка heartbeat_timeout
plan = await workflow.execute_activity(
    collaborative_planning,
    PlanningRequest(card=card, context=request.context),
    start_to_close_timeout=timedelta(minutes=10),
    heartbeat_timeout=timedelta(seconds=60),  # Если нет heartbeat 60 сек — retry
    retry_policy=RetryPolicy(maximum_attempts=2),
)
```

**Конфигурация**:

```yaml
# config/orchestrator.yaml
orchestrator:
  temporal:
    activities:
      # LLM Activities требуют длинных таймаутов
      collaborative_planning:
        start_to_close_timeout_seconds: 600  # 10 минут
        heartbeat_timeout_seconds: 60         # Heartbeat каждые 60 сек
        heartbeat_interval_seconds: 30        # Отправляем каждые 30 сек

      quality_loop:
        start_to_close_timeout_seconds: 300   # 5 минут
        heartbeat_timeout_seconds: 60
        heartbeat_interval_seconds: 30

      execute_step:
        start_to_close_timeout_seconds: 300
        # Для обычных шагов heartbeat не нужен
```

---

## 7.4. Workflow Versioning (Determinism)

**Проблема**: Temporal требует детерминизма. Если изменить код Workflow (порядок шагов, условия), старые запущенные процессы могут упасть при Replay.

**Решение**: Использовать `workflow.patched()` для поддержки версий.

```python
@workflow.defn
class ProcessCardWorkflow:
    @workflow.run
    async def run(self, request: ProcessCardRequest) -> ProcessResult:
        # Version 1: Исходная логика
        # Version 2: Добавили обязательный quality check

        card = await workflow.execute_activity(
            parse_process_card,
            request.card_yaml,
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Пример версионирования: добавили новый шаг
        if workflow.patched("add-mandatory-quality-check"):
            # Новая логика (для новых workflow)
            plan = await workflow.execute_activity(
                collaborative_planning,
                PlanningRequest(card=card, context=request.context),
                start_to_close_timeout=timedelta(minutes=10),
            )
        else:
            # Старая логика (для уже запущенных workflow)
            plan = self.simple_planning(card)

        # ... остальной код
```

**Правила версионирования**:

| Правило | Описание |
|---------|----------|
| **Добавление шага** | Использовать `workflow.patched("feature-name")` |
| **Удаление шага** | Использовать `workflow.deprecate_patch("feature-name")` |
| **Изменение порядка** | Новая версия Workflow Definition (v2, v3...) |
| **Изменение Activity** | Activity можно менять свободно (не детерминистичны) |

**Запрещённые операции в Workflow** (нарушают детерминизм):

```python
# ❌ ЗАПРЕЩЕНО в Workflow:
import random
random.choice([...])  # Недетерминистично!

import datetime
datetime.now()  # Используйте workflow.now() вместо этого

import uuid
uuid.uuid4()  # Используйте workflow.uuid4()

await asyncio.sleep(10)  # Используйте workflow.sleep()

# ✅ ПРАВИЛЬНО:
from temporalio import workflow

workflow.now()      # Детерминистичное время
workflow.uuid4()    # Детерминистичный UUID
await workflow.sleep(timedelta(seconds=10))  # Детерминистичный sleep
```

---

## 8. Integration with Existing SSOT

### 8.1. MindBus RPC Contract

**КРИТИЧЕСКИ ВАЖНО**: Контракт для Request-Reply паттерна через MindBus.

#### 8.1.1. Correlation Rules

| Поле | Назначение | Формат |
|------|------------|--------|
| `correlation_id` | Связывает COMMAND и RESULT | `{process_id}:{step_id}:{attempt}` |
| `idempotency_key` | Дедупликация на стороне агента | `{process_id}:{step_id}:{attempt}` |
| `reply_to` | Очередь для ответа | `orchestrator.responses.{node_id}` |
| `traceparent` | W3C Trace Context | Из parent workflow |

#### 8.1.2. Timeout Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│  Activity start_to_close_timeout (самый внешний)            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  MindBus RPC timeout (должен быть МЕНЬШЕ!)          │    │
│  │  ┌─────────────────────────────────────────────┐    │    │
│  │  │  step.timeout (указан в Process Card)       │    │    │
│  │  └─────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘

ПРАВИЛО: mindbus_timeout <= activity_timeout - buffer (30 сек)
```

#### 8.1.3. Late Reply Handling

```python
async def handle_response(response: CloudEvent) -> None:
    """Обработка ответов от агентов"""
    correlation_id = response.get("correlation_id")

    # Проверяем, ждём ли мы ещё этот ответ
    pending = await pending_requests.get(correlation_id)

    if pending is None:
        # Late reply — шаг уже завершён (timeout или retry succeeded)
        logger.warning(
            f"Late reply ignored: correlation_id={correlation_id}",
            extra={"response_id": response.id}
        )
        # НЕ обрабатываем, просто логируем и отбрасываем
        return

    # Валидный ответ — доставляем
    await pending.future.set_result(response)
```

#### 8.1.4. Idempotency на стороне агента

```python
# Агент ОБЯЗАН проверять idempotency_key
async def handle_command(command: CloudEvent) -> CloudEvent:
    idempotency_key = command.data.get("idempotency_key")

    # Проверяем, выполняли ли уже
    cached_result = await idempotency_cache.get(idempotency_key)
    if cached_result:
        logger.info(f"Returning cached result for {idempotency_key}")
        return cached_result

    # Выполняем команду
    result = await execute_action(command)

    # Кэшируем результат (TTL = 24 часа)
    await idempotency_cache.set(idempotency_key, result, ttl=86400)

    return result
```

### 8.2. MindBus Integration (Code)

```python
# Activity для отправки COMMAND через MindBus
@activity.defn
async def execute_step(request: ExecuteStepRequest) -> StepResult:
    """Отправляет COMMAND через MindBus, ждёт RESULT"""

    # Генерируем correlation_id для связи request/response
    correlation_id = f"{request.state.process_id}:{request.step.id}:{request.state.attempt}"

    # CloudEvent по MESSAGE_FORMAT v1.1
    command = CloudEvent(
        specversion="1.0",
        type="ai.team.command",
        source="orchestrator",
        id=str(uuid.uuid4()),
        time=datetime.utcnow().isoformat(),
        traceparent=request.state.trace_id,
        data={
            "action": request.step.action,
            "params": request.step.params,
            "requirements": request.step.requirements,
            "context": {
                "process_id": request.state.process_id,
                "step": request.step.id,
            },
            "timeout_seconds": request.step.timeout or 300,
            "idempotency_key": correlation_id,  # Используем тот же ключ
        },
    )

    # AMQP routing по MindBus Protocol v1.0
    routing_key = f"cmd.{request.agent.role}.{request.agent.uid}"

    # Рассчитываем timeout для MindBus (меньше чем Activity timeout)
    mindbus_timeout = min(
        request.step.timeout or 300,
        activity.info().start_to_close_timeout.total_seconds() - 30  # Buffer
    )

    # Отправка и ожидание (RPC pattern)
    result = await mindbus.publish_and_wait(
        exchange="mindbus.main",
        routing_key=routing_key,
        message=command,
        reply_to=f"orchestrator.responses.{ORCHESTRATOR_NODE_ID}",
        correlation_id=correlation_id,
        timeout=timedelta(seconds=mindbus_timeout),
    )

    return parse_result(result)
```

### 8.3. Node Registry Integration

```python
# Activity для поиска агентов
@activity.defn
async def find_suitable_agents(requirements: Dict) -> List[NodePassport]:
    """Поиск агентов через Node Registry"""

    selector = {
        "matchLabels": {
            f"capability.{cap}": "true"
            for cap in requirements.get("capabilities", [])
        },
        "matchExpressions": [
            {"key": "status.phase", "operator": "Eq", "values": ["Running"]},
            {"key": "status.conditions.Ready", "operator": "Eq", "values": ["True"]},
        ],
    }

    return await node_registry.query(selector)
```

### 8.4. Process Card Compatibility

**Важное разъяснение версий**:

| Версия | Описание |
|--------|----------|
| **ORCHESTRATOR_SPEC v2.1** | Версия спецификации *оркестратора* (этот документ) |
| **Process Card spec_version** | Версия формата *карточки процесса* (1.0, 2.0) |

Это **разные версии**. Orchestrator v2.1 поддерживает Process Card версий 1.0 и 2.0.

```python
# Парсинг Process Card v1.0 и v2.0
@activity.defn
async def parse_process_card(card_yaml: str) -> ProcessCard:
    """Парсинг и валидация Process Card"""

    card = yaml.safe_load(card_yaml)

    # Определяем версию Process Card (НЕ версию Orchestrator!)
    spec_version = card.get("metadata", {}).get("spec_version", "1.0")

    if spec_version == "1.0":
        return ProcessCard_v1.parse_obj(card)
    elif spec_version == "2.0":
        return ProcessCard_v2.parse_obj(card)
    else:
        raise ValueError(f"Unknown Process Card spec_version: {spec_version}. Supported: 1.0, 2.0")
```

---

## 9. Конфигурация

### 9.1. Temporal Configuration

```yaml
# config/orchestrator.yaml
orchestrator:
  # Identity
  node_id: "orchestrator-main"
  version: "2.1.0"

  # Temporal connection
  temporal:
    host: ${TEMPORAL_HOST:-localhost}
    port: ${TEMPORAL_PORT:-7233}
    namespace: ${TEMPORAL_NAMESPACE:-ai-team}
    task_queue: "orchestrator-tasks"

    # Worker settings
    worker:
      max_concurrent_activities: 100
      max_concurrent_workflows: 50

    # Retry defaults
    default_retry_policy:
      initial_interval_seconds: 5
      backoff_coefficient: 2.0
      maximum_interval_seconds: 300
      maximum_attempts: 3

  # MindBus connection (без изменений)
  mindbus:
    host: ${RABBITMQ_HOST:-localhost}
    port: ${RABBITMQ_PORT:-5672}

  # LangGraph settings
  langgraph:
    # Meeting Protocol
    meeting:
      proposal_timeout_seconds: 60
      min_proposals: 1
      max_rounds: 3

    # Quality Loop
    quality:
      max_iterations: 3
      pass_threshold: 0.9

  # Limits
  limits:
    max_subprocess_depth: 10
    max_total_steps: 1000
    default_step_timeout_seconds: 300

  # LLM for Intelligence Layer
  llm:
    provider: "anthropic"
    model: "claude-3-sonnet"
    api_key: ${ANTHROPIC_API_KEY}

    # Timeouts (важно для Temporal!)
    timeout_seconds: 120  # LLM может быть медленным
```

### 9.2. Temporal Server (Docker)

```yaml
# docker-compose.temporal.yaml
version: '3.8'
services:
  temporal:
    image: temporalio/auto-setup:1.22
    ports:
      - "7233:7233"
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_USER=temporal
      - POSTGRES_PWD=temporal
      - POSTGRES_SEEDS=postgres

  temporal-ui:
    image: temporalio/ui:2.21
    ports:
      - "8080:8080"
    environment:
      - TEMPORAL_ADDRESS=temporal:7233

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_USER=temporal
      - POSTGRES_PASSWORD=temporal
```

---

## 10. Observability

### 10.1. Temporal UI

Temporal предоставляет UI из коробки:
- Список workflows
- История событий
- Состояние каждого workflow
- Retry, cancel, terminate

### 10.2. Tracing

```python
# Temporal интегрируется с OpenTelemetry
from temporalio.contrib.opentelemetry import TracingInterceptor

client = await Client.connect(
    "localhost:7233",
    interceptors=[TracingInterceptor()],
)

# Все workflows и activities автоматически трассируются
```

### 10.3. Metrics

```python
# Temporal экспортирует Prometheus метрики
# Доступны на :9090/metrics

# Ключевые метрики:
# - temporal_workflow_completed_total
# - temporal_workflow_failed_total
# - temporal_activity_execution_latency
# - temporal_workflow_task_queue_poll_latency
```

---

## 11. MVP Subset (Phase 1 Scope)

**КРИТИЧНО**: Чтобы избежать scope creep, фиксируем строгий минимум для Phase 1.

### 11.1. Что ВХОДИТ в MVP

| Компонент | Описание | Приоритет |
|-----------|----------|-----------|
| **ProcessCardWorkflow** | Основной workflow для Process Card | P0 |
| **parse_process_card** | Activity для парсинга YAML | P0 |
| **execute_step** | Activity для выполнения шага через MindBus | P0 |
| **Retry Policy** | Базовые ретраи с backoff | P0 |
| **Child Workflows** | Поддержка subprocess | P1 |
| **Temporal UI** | Мониторинг из коробки | P0 |

### 11.2. Что НЕ ВХОДИТ в MVP (Phase 2+)

| Компонент | Причина отложения | Фаза |
|-----------|-------------------|------|
| **collaborative_planning** | Требует LangGraph интеграции | Phase 2 |
| **quality_loop** | Требует LangGraph интеграции | Phase 2 |
| **Meeting Protocol** | Сложная multi-agent логика | Phase 2 |
| **Dynamic Process Cards** | Высокий риск, требует sandbox | Phase 3 |
| **Saga / Compensation** | Можно добавить позже | Phase 2 |
| **OpenTelemetry** | Production hardening | Phase 3 |

### 11.3. MVP Acceptance Criteria

**Phase 1 считается завершённой когда**:

```
✅ Temporal Server запущен (Docker)
✅ ProcessCardWorkflow выполняет простую Process Card (3-5 шагов)
✅ execute_step отправляет COMMAND через MindBus и получает RESULT
✅ Retry работает при transient ошибках
✅ Child Workflow работает для subprocess
✅ Temporal UI показывает workflow history
✅ 10+ E2E тестов проходят
```

### 11.4. MVP Process Card для тестирования

```yaml
# examples/process_cards/mvp_test_card.yaml
apiVersion: ai.team/v1
kind: ProcessCard
metadata:
  name: "mvp-test-card"
  version: "1.0.0"
  spec_version: "2.0"  # Версия формата Process Card (НЕ Orchestrator!)
spec:
  variables:
    topic: "Test topic"
  steps:
    - id: "step-1"
      action: "generate_text"
      params:
        prompt: "Write a haiku about ${topic}"
      output: "haiku"
      timeout: 60

    - id: "step-2"
      action: "generate_text"
      params:
        prompt: "Translate this haiku to Spanish: ${haiku}"
      output: "translated"
      timeout: 60

    - id: "step-3"
      action: "generate_text"
      params:
        prompt: "Rate this translation 1-10: ${translated}"
      output: "rating"
      timeout: 60
```

### 11.5. MVP Architecture Diagram

```
MVP Phase 1 (simplified):

┌─────────────────────────────────────────────────────────┐
│                  Temporal Workflow                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  parse_process_card ──► execute_step ──► execute_step   │
│        (Activity)         (Activity)      (Activity)     │
│                               │                │         │
│                               ▼                ▼         │
│                          MindBus          MindBus        │
│                               │                │         │
│                               ▼                ▼         │
│                          Agent 1          Agent 2        │
│                                                          │
└─────────────────────────────────────────────────────────┘

НЕТ в MVP:
  ✗ collaborative_planning (LangGraph)
  ✗ quality_loop (LangGraph)
  ✗ Dynamic Cards
  ✗ Saga compensation
```

---

## 12. Migration from v1.0

### 12.1. Что меняется

| Компонент | v1.0 | v2.1 |
|-----------|------|------|
| State Store | PostgreSQL (custom) | Temporal Event History |
| Execution Engine | Custom State Machine | Temporal Workflow |
| Retry Logic | Custom | Temporal Retry Policy |
| Subprocess | Не было | Temporal Child Workflows |
| Recovery | Custom | Temporal auto-replay |

### 12.2. Что НЕ меняется

| Компонент | Статус |
|-----------|--------|
| MindBus (AMQP) | Без изменений |
| CloudEvents | Без изменений |
| MESSAGE_FORMAT | Без изменений |
| Process Card format | Без изменений (+ новые поля v2.0) |
| Node Passport | Без изменений |
| Node Registry | Без изменений |

### 12.3. План миграции

1. **Установить Temporal** (Docker / Cloud)
2. **Создать Workflow для Process Card** (заменяет custom state machine)
3. **Создать Activities** (execute_step, quality_loop, etc.)
4. **Интегрировать LangGraph** (как activities)
5. **Тестирование** с существующими Process Cards
6. **Deprecate** custom state management

---

## 13. Roadmap

### Phase 1: Temporal Core (2 недели)
- [ ] Установка Temporal
- [ ] ProcessCardWorkflow
- [ ] execute_step Activity
- [ ] Интеграция с MindBus
- [ ] Тесты

### Phase 2: LangGraph Integration (2 недели)
- [ ] collaborative_planning Activity
- [ ] quality_loop Activity
- [ ] conflict_resolution
- [ ] Тесты multi-agent

### Phase 3: Production Hardening (1 неделя)
- [ ] Monitoring + Alerting
- [ ] Temporal UI customization
- [ ] Documentation
- [ ] Performance testing

---

## 14. Связанные документы

- [ADR-001: Temporal + LangGraph](../concepts/ADR-001_TEMPORAL_LANGGRAPH.md) — обоснование решения
- [ORCHESTRATOR_SPEC v1.0](archive/ORCHESTRATOR_SPEC_v1.0.md) — предыдущая версия (архив)
- [ORCHESTRATOR_SPEC v2.0 DRAFT](../concepts/drafts/ORCHESTRATOR_SPEC_v2.0_DRAFT.md) — концептуальный черновик
- [ORCHESTRATOR_WORLD_EXPERIENCE_RESEARCH](../concepts/drafts/ORCHESTRATOR_WORLD_EXPERIENCE_RESEARCH.md) — исследование
- [MindBus Protocol v1.0](mindbus_protocol_v1.md)
- [MESSAGE_FORMAT v1.1](MESSAGE_FORMAT_v1.1.md)
- [PROCESS_CARD v1.0](PROCESS_CARD_SPEC_v1.0.md)

---

---

**Версия**: 2.1.0
**Дата утверждения**: 2025-12-20
**Авторы**: AI_TEAM Core Team
**Статус**: ✅ APPROVED (SSOT v2.1)

**История ревизий**:
| Версия | Дата | Изменения |
|--------|------|-----------|
| 2.1-draft | 2025-12-20 | Первоначальная версия на базе Temporal + LangGraph |
| 2.1-draft-rev2 | 2025-12-20 | Heartbeat, Versioning, Subprocess Isolation, MVP Scope |
| 2.1-draft-rev3 | 2025-12-20 | MindBus RPC Contract, At-least-once гарантии, Boundary Artifact Contract |
| **2.1.0** | **2025-12-20** | **APPROVED — финальная SSOT версия** |

**Экспертное утверждение**: Документ прошёл архитектурный review и признан production-ready.
