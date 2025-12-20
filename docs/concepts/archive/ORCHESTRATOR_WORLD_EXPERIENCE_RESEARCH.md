# Исследование: Мировой опыт в оркестрации процессов

**Дата**: 2025-12-20
**Цель**: Найти готовые решения для Orchestrator v2.0, чтобы не изобретать велосипед
**Статус**: Исследование завершено

---

## Резюме для принятия решения

### Рекомендуемый стек технологий для AI_TEAM

| Компонент | Рекомендация | Альтернатива | Почему |
|-----------|--------------|--------------|--------|
| **Workflow Engine** | **Temporal** | Prefect | Durable execution, multi-language, exactly-once |
| **AI Agent Framework** | **LangGraph** | CrewAI | Graph-based, stateful, production-ready |
| **State Pattern** | **Event Sourcing + Saga** | CQRS | Идеально для recovery, audit, compensating transactions |
| **Message Format** | **CloudEvents** | - | Уже используем (SSOT) |
| **Message Broker** | **RabbitMQ/AMQP** | NATS | Уже используем (MindBus) |

### Что можно НЕ писать с нуля

| Функция в ORCHESTRATOR_SPEC v2.0 | Готовое решение | Экономия |
|----------------------------------|-----------------|----------|
| State Machine + Recovery | Temporal Workflow | 6-8 недель |
| Subprocess Management | Temporal Child Workflows | 3-4 недели |
| Quality Loop + Retry | Temporal Activities + Retry Policy | 2-3 недели |
| Meeting Protocol | CrewAI Crew / LangGraph Graph | 2-3 недели |
| Dynamic Card Execution | LangGraph State Machine | 2-3 недели |
| **ИТОГО** | | **15-21 неделя** |

---

## 1. Workflow Orchestration Engines

### 1.1. Temporal (рекомендуется)

**Источник**: [Temporal Blog](https://temporal.io/blog/saga-pattern-made-easy), [PracData](https://www.pracdata.io/p/state-of-workflow-orchestration-ecosystem-2025)

**Что это**: Workflow orchestration platform от создателей Uber Cadence. Используется в Uber, Netflix, Snap, Stripe.

**Ключевые возможности**:
- ✅ **Durable Execution** — workflow переживает рестарты, падения, сетевые сбои
- ✅ **Event Sourcing** — каждое состояние записывается, можно "отмотать"
- ✅ **Exactly-once semantics** — идемпотентность из коробки
- ✅ **Multi-language SDK** — Go, Java, Python, TypeScript, PHP, .NET
- ✅ **Child Workflows** — вложенные процессы (наш subprocess!)
- ✅ **Activity Retry** — автоматические retry с backoff
- ✅ **Saga Pattern** — compensating transactions из коробки

**Как покрывает наши требования**:

| Наше требование (v2.0) | Temporal feature |
|------------------------|------------------|
| State Contract | Workflow State + Event History |
| Subprocess Manager | Child Workflows |
| Recovery after crash | Automatic replay from Event History |
| Idempotency | Workflow ID + Run ID |
| Optimistic locking | Workflow versioning |
| Quality Loop retry | Activity Retry Policy |
| Budget tracking | Workflow metadata + signals |

**Пример кода** (Python SDK):
```python
from temporalio import workflow, activity

@activity.defn
async def research_topic(topic: str) -> ResearchResult:
    # Это "шаг" нашей Process Card
    return await call_agent("researcher", topic)

@workflow.defn
class BookWritingWorkflow:
    """Это наша Process Card, но как code"""

    @workflow.run
    async def run(self, request: BookRequest) -> Book:
        # Step 1: Research (с автоматическим retry)
        research = await workflow.execute_activity(
            research_topic,
            request.topic,
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        # Step 2: Child workflow для каждой главы (subprocess!)
        chapters = []
        for i in range(request.chapter_count):
            chapter = await workflow.execute_child_workflow(
                WriteChapterWorkflow.run,
                ChapterRequest(number=i, outline=research.outline)
            )
            chapters.append(chapter)

        return Book(chapters=chapters)
```

**Вердикт**: **Покрывает 80-90% нашего State Contract, Subprocess, Recovery**.

---

### 1.2. Prefect

**Источник**: [Prefect vs Airflow](https://www.datacamp.com/tutorial/airflow-vs-prefect-deciding-which-is-right-for-your-data-workflow)

**Что это**: Python-native workflow orchestration, особенно популярен в ML/Data Science.

**Ключевые возможности**:
- ✅ Pythonic API — декораторы `@flow`, `@task`
- ✅ ControlFlow — специальный фреймворк для AI workflows
- ✅ Marvin — LLM-powered assistant
- ✅ Task caching, state handling

**Минусы для нас**:
- ❌ Только Python (мы можем захотеть Go-агентов)
- ❌ Менее mature для long-running workflows
- ❌ Нет built-in Saga pattern

**Вердикт**: Хорош для ML pipelines, но Temporal лучше для mission-critical orchestration.

---

### 1.3. Netflix Conductor

**Источник**: [Medium Comparison](https://medium.com/@chucksanders22/netflix-conductor-v-s-temporal-uber-cadence-v-s-zeebe-vs-airflow-320df0365948)

**Что это**: Microservices orchestration от Netflix, поддерживается Orkes.

**Ключевые возможности**:
- ✅ Visual workflow debugging
- ✅ Language-agnostic (JSON workflow definitions)
- ✅ Low footprint

**Минусы**:
- ❌ Менее активное community чем Temporal
- ❌ JSON workflows менее гибкие чем code

**Вердикт**: Интересен для визуализации, но Temporal мощнее.

---

### 1.4. Apache Airflow

**Источник**: [Airflow 3.0 Release](https://www.zenml.io/blog/orchestration-showdown-dagster-vs-prefect-vs-airflow)

**Что это**: Самый популярный orchestrator (80,000+ организаций). Версия 3.0 вышла в апреле 2025.

**Почему НЕ подходит нам**:
- ❌ Оптимизирован для scheduled batch jobs, не для event-driven
- ❌ Нет durable execution как в Temporal
- ❌ Тяжёлый для real-time workflows

**Вердикт**: Отлично для ETL/Data pipelines, но не для AI agent orchestration.

---

### 1.5. Camunda/Zeebe (BPMN)

**Источник**: [Camunda Blog](https://camunda.com/platform/zeebe/), [Intuit Case Study](https://camunda.com/blog/2024/08/scaling-workflow-engines-intuit-camunda-8-zeebe/)

**Что это**: Enterprise BPMN workflow engine. Zeebe — cloud-native версия.

**Ключевые возможности**:
- ✅ BPMN 2.0 стандарт — визуальное моделирование
- ✅ DMN для decision tables
- ✅ 10x throughput vs традиционные BPMN engines
- ✅ AI features (Camunda Copilot) — генерация BPMN из natural language

**Интересно для нас**:
- Visual Process Designer
- Стандартизированный BPMN формат

**Минусы**:
- ❌ Enterprise licensing (Camunda License 1.0)
- ❌ BPMN может быть overkill для AI workflows

**Вердикт**: Интересен для визуализации, но Temporal проще интегрировать.

---

## 2. AI Agent Orchestration Frameworks

### 2.1. LangGraph (рекомендуется для AI-части)

**Источник**: [Top AI Agent Frameworks 2025](https://www.getmaxim.ai/articles/top-5-ai-agent-frameworks-in-2025-a-practical-guide-for-ai-builders/)

**Что это**: Graph-based state machine для LLM agents. Часть LangChain ecosystem.

**Ключевые возможности**:
- ✅ **Graph-first approach** — nodes, edges, conditional routing
- ✅ **Stateful workflows** — in-thread и cross-thread memory
- ✅ **MemorySaver** — persistence для state
- ✅ **Traceable, debuggable flows**

**Как покрывает наши требования**:

| Наше требование (v2.0) | LangGraph feature |
|------------------------|-------------------|
| Meeting Protocol | Multi-agent graph with conditional edges |
| Dynamic Card Generation | LLM nodes + state updates |
| Quality Loop | Cycles in graph + conditional routing |
| Conflict Resolution | Reducer functions for state merging |

**Пример кода**:
```python
from langgraph.graph import StateGraph, END

class MeetingState(TypedDict):
    topic: str
    proposals: list[Proposal]
    conflicts: list[Conflict]
    final_plan: Optional[Plan]

def collect_proposals(state: MeetingState) -> MeetingState:
    """Каждый агент отправляет proposal"""
    proposals = []
    for agent in ["researcher", "writer", "editor"]:
        proposal = call_agent(agent, state["topic"])
        proposals.append(proposal)
    return {"proposals": proposals}

def detect_conflicts(state: MeetingState) -> MeetingState:
    """Анализ конфликтов между proposals"""
    conflicts = find_conflicts(state["proposals"])
    return {"conflicts": conflicts}

def route_after_conflicts(state: MeetingState) -> str:
    if state["conflicts"]:
        return "resolve_conflicts"
    return "synthesize_plan"

# Граф = наш Meeting Protocol!
graph = StateGraph(MeetingState)
graph.add_node("collect_proposals", collect_proposals)
graph.add_node("detect_conflicts", detect_conflicts)
graph.add_node("resolve_conflicts", resolve_conflicts)
graph.add_node("synthesize_plan", synthesize_plan)

graph.add_edge("collect_proposals", "detect_conflicts")
graph.add_conditional_edges("detect_conflicts", route_after_conflicts)
graph.add_edge("resolve_conflicts", "synthesize_plan")
graph.add_edge("synthesize_plan", END)
```

**Вердикт**: **Идеально для Meeting Protocol и Quality Loop**. Можно комбинировать с Temporal.

---

### 2.2. CrewAI

**Источник**: [CrewAI vs LangGraph](https://www.datagrom.com/data-science-machine-learning-ai-blog/langgraph-vs-autogen-vs-crewai-comparison-agentic-ai-frameworks)

**Что это**: Framework для role-playing AI agents. "Crew" = команда агентов.

**Ключевые возможности**:
- ✅ **Role-based agents** — каждый агент имеет роль и цель
- ✅ **Crews and Flows** — высокоуровневая автономия + низкоуровневый контроль
- ✅ **Built-in memory** — ChromaDB для short-term, SQLite для long-term
- ✅ **Rapid prototyping** — быстрый старт

**Как покрывает наши требования**:

| Наше требование (v2.0) | CrewAI feature |
|------------------------|----------------|
| Коллаборативное планирование | Crew collaboration |
| Agent roles | Native support |
| Memory | Short-term + Long-term + Entity memory |

**Пример**:
```python
from crewai import Agent, Crew, Task

researcher = Agent(
    role="Researcher",
    goal="Find relevant information",
    backstory="Expert in research methodology"
)

writer = Agent(
    role="Writer",
    goal="Create compelling content",
    backstory="Experienced content creator"
)

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.sequential  # или hierarchical
)
```

**Вердикт**: Проще чем LangGraph, но менее гибкий. Хорош для прототипирования.

---

### 2.3. Microsoft AutoGen

**Источник**: [AutoGen Enterprise](https://www.instinctools.com/blog/autogen-vs-langchain-vs-crewai/)

**Что это**: Enterprise-focused multi-agent framework от Microsoft.

**Ключевые возможности**:
- ✅ **Enterprise-grade** — advanced error handling, logging
- ✅ **Human-in-the-loop** — native support
- ✅ **Conversation orchestration** — chat-like collaboration
- ✅ **Production deployment** (используется в Novo Nordisk)

**Минусы**:
- ❌ Более сложный чем CrewAI
- ❌ Conversation-first (не graph-first)

**Вердикт**: Хорош для enterprise, но LangGraph гибче для наших нужд.

---

### 2.4. OpenAI Swarm / Agency Swarm

**Источник**: [OpenAI Swarm Release](https://www.infoq.com/news/2024/10/openai-swarm-orchestration/)

**Что это**: Experimental framework от OpenAI для multi-agent handoffs.

**Статус**: Experimental, не для production.

**Вердикт**: Интересная концепция handoffs, но не production-ready.

---

### 2.5. Anthropic Agent SDK

**Источник**: [VentureBeat - Anthropic Multi-Session](https://venturebeat.com/ai/anthropic-says-it-solved-the-long-running-ai-agent-problem-with-a-new-multi)

**Что это**: Официальный SDK от Anthropic для Claude agents.

**Ключевые возможности**:
- ✅ **Initializer agent + Coding agent** pattern
- ✅ **Subagents** — 90.2% improvement на internal metrics
- ✅ **Modular intelligence** — каждый agent = unit

**Очень релевантно для нас** — мы используем Claude!

---

## 3. Архитектурные паттерны

### 3.1. Saga Pattern (рекомендуется)

**Источник**: [Microsoft Saga Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/saga), [Temporal Saga](https://temporal.io/blog/saga-pattern-made-easy)

**Что это**: Паттерн для distributed transactions с compensating actions.

**Применение к нашему Orchestrator**:
```
Saga для "Написать книгу":

1. Research → SUCCESS → продолжаем
2. Outline → SUCCESS → продолжаем
3. Write Chapter 1 → FAIL!

Compensating transactions:
- Rollback: Delete Chapter 1 draft
- Rollback: Archive Outline (не удаляем, но помечаем)
- Rollback: Mark Research as "unused"
```

**Два подхода**:
- **Orchestration** (центральный координатор) ← **наш подход**
- **Choreography** (события между сервисами)

**Вердикт**: **Saga + State Machine = наш Recovery механизм**.

---

### 3.2. Event Sourcing + CQRS

**Источник**: [Microsoft Event Sourcing](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing), [Confluent CQRS](https://developer.confluent.io/courses/event-sourcing/cqrs/)

**Что это**:
- **Event Sourcing**: Храним не состояние, а последовательность событий
- **CQRS**: Разделяем read и write модели

**Применение к нашему Orchestrator**:

```
Event Store (Write Model):
┌─────────────────────────────────────────┐
│ ProcessCreated(id=001, topic="AI Book") │
│ StepStarted(step=research)              │
│ StepCompleted(step=research, result=..) │
│ StepStarted(step=outline)               │
│ StepFailed(step=outline, error=..)      │
│ StepRetried(step=outline, attempt=2)    │
│ StepCompleted(step=outline, result=..)  │
└─────────────────────────────────────────┘

Read Model (Materialized View):
┌─────────────────────────────────────────┐
│ Process 001:                            │
│   phase: RUNNING                        │
│   current_step: write_chapter_1         │
│   completed: [research, outline]        │
│   variables: {topic: "AI Book", ...}    │
└─────────────────────────────────────────┘
```

**Преимущества**:
- ✅ Полный audit trail
- ✅ Time-travel queries ("что было в 10:00?")
- ✅ Self-healing (replay events = reconstruct state)
- ✅ Идеально для recovery после crash

**Temporal уже использует Event Sourcing** внутри!

---

## 4. Сравнительная таблица

| Критерий | Temporal | LangGraph | CrewAI | Camunda |
|----------|----------|-----------|--------|---------|
| **Durable Execution** | ✅ Native | ❌ | ❌ | ✅ |
| **Multi-Agent** | ❌ | ✅ Native | ✅ Native | ❌ |
| **State Machine** | ✅ | ✅ Graph | ❌ | ✅ BPMN |
| **Recovery** | ✅ Auto | ⚠️ Manual | ⚠️ Manual | ✅ Auto |
| **Saga Pattern** | ✅ Native | ❌ | ❌ | ✅ |
| **Python SDK** | ✅ | ✅ | ✅ | ✅ |
| **LLM Integration** | ⚠️ Manual | ✅ Native | ✅ Native | ⚠️ |
| **Open Source** | ✅ MIT | ✅ MIT | ✅ MIT | ⚠️ Commercial |
| **Production Ready** | ✅ | ✅ | ⚠️ | ✅ |

---

## 5. Рекомендуемая архитектура

### Гибридный подход: Temporal + LangGraph

```
┌─────────────────────────────────────────────────────────────┐
│                    AI_TEAM Orchestrator v2.0                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              TEMPORAL (Workflow Layer)               │   │
│   │                                                      │   │
│   │  • Durable Execution                                │   │
│   │  • Child Workflows (subprocesses)                   │   │
│   │  • Saga + Compensating Transactions                 │   │
│   │  • Event Sourcing (auto)                            │   │
│   │  • Recovery after crash                             │   │
│   └──────────────────────┬──────────────────────────────┘   │
│                          │                                   │
│                          │ Activities                        │
│                          ▼                                   │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              LANGGRAPH (Agent Layer)                 │   │
│   │                                                      │   │
│   │  • Meeting Protocol (graph of agents)               │   │
│   │  • Conflict Resolution (conditional edges)          │   │
│   │  • Quality Loop (cycles in graph)                   │   │
│   │  • Dynamic planning with LLM                        │   │
│   └──────────────────────┬──────────────────────────────┘   │
│                          │                                   │
│                          │ MindBus (AMQP)                    │
│                          ▼                                   │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                    AI Agents                         │   │
│   │  (Researcher, Writer, Editor, Critic, ...)          │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Как это работает

1. **Temporal Workflow** = Process Card execution
   - Каждая Process Card становится Temporal Workflow
   - Subprocess = Child Workflow
   - Recovery = автоматический replay

2. **LangGraph** = AI-специфичная логика
   - Meeting Protocol = LangGraph graph
   - Каждый agent = node в графе
   - Conflict resolution = conditional edges

3. **Temporal Activity** вызывает LangGraph
   ```python
   @activity.defn
   async def collaborative_planning(topic: str) -> Plan:
       """Temporal Activity → LangGraph execution"""
       graph = build_meeting_graph()
       result = await graph.ainvoke({"topic": topic})
       return result["final_plan"]
   ```

---

## 6. Что мы можем взять готовое

### Немедленно использовать

| Технология | Для чего | Усилия на интеграцию |
|------------|----------|---------------------|
| **Temporal** | State management, recovery, subprocesses | 2-3 недели |
| **LangGraph** | Meeting protocol, quality loop | 1-2 недели |
| **CloudEvents** | Message format | Уже используем |
| **RabbitMQ** | Message broker | Уже используем |

### Изучить для будущего

| Технология | Для чего | Когда |
|------------|----------|-------|
| **CrewAI** | Rapid prototyping новых workflows | Phase 3+ |
| **Camunda Copilot** | Visual process designer | v2.5+ |
| **Anthropic Agent SDK** | Subagent patterns | После стабилизации SDK |

---

## 7. Влияние на ORCHESTRATOR_SPEC v2.0

### Что можно упростить

1. **State Contract** → Использовать Temporal Event History
2. **Recovery** → Temporal auto-replay
3. **Idempotency** → Temporal Workflow ID
4. **Subprocess Manager** → Temporal Child Workflows
5. **Saga/Compensation** → Temporal Saga pattern

### Что оставить custom

1. **Process Card format** — наш YAML DSL
2. **MindBus integration** — наш AMQP protocol
3. **Agent capabilities** — наш Node Passport
4. **Meeting Protocol details** — наша бизнес-логика

### Новый раздел для спецификации

Рекомендую добавить раздел "Integration with Workflow Engines":

```yaml
# В ORCHESTRATOR_SPEC v2.0
workflow_engine_integration:
  primary: "temporal"
  version: "1.x"

  mapping:
    process_card: "temporal.Workflow"
    step: "temporal.Activity"
    subprocess: "temporal.ChildWorkflow"
    variables: "temporal.WorkflowState"

  ai_layer:
    framework: "langgraph"
    use_for:
      - "collaborative_planning"
      - "quality_loop"
      - "conflict_resolution"
```

---

## Источники

### Workflow Orchestration
- [State of Workflow Orchestration 2025](https://www.pracdata.io/p/state-of-workflow-orchestration-ecosystem-2025)
- [Workflow Orchestration Platforms Comparison](https://procycons.com/en/blogs/workflow-orchestration-platforms-comparison-2025/)
- [Temporal Saga Pattern](https://temporal.io/blog/saga-pattern-made-easy)
- [Netflix Conductor Comparison](https://medium.com/@chucksanders22/netflix-conductor-v-s-temporal-uber-cadence-v-s-zeebe-vs-airflow-320df0365948)

### AI Agent Frameworks
- [Top AI Agent Frameworks 2025](https://www.getmaxim.ai/articles/top-5-ai-agent-frameworks-in-2025-a-practical-guide-for-ai-builders/)
- [LangGraph vs AutoGen vs CrewAI](https://www.datagrom.com/data-science-machine-learning-ai-blog/langgraph-vs-autogen-vs-crewai-comparison-agentic-ai-frameworks)
- [Anthropic Multi-Agent SDK](https://venturebeat.com/ai/anthropic-says-it-solved-the-long-running-ai-agent-problem-with-a-new-multi)

### Architecture Patterns
- [Microsoft Saga Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/saga)
- [Event Sourcing Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)
- [CQRS Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs)

### BPMN Engines
- [Camunda/Zeebe Platform](https://camunda.com/platform/zeebe/)
- [Scaling Workflow at Intuit](https://camunda.com/blog/2024/08/scaling-workflow-engines-intuit-camunda-8-zeebe/)

---

**Вывод**: Используя **Temporal + LangGraph**, мы можем сократить разработку на **15-21 неделю** и получить production-ready решение вместо "велосипеда".
