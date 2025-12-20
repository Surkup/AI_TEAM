# ADR-001: Выбор Temporal + LangGraph для Orchestrator

**Статус**: Принято
**Дата**: 2025-12-20
**Авторы**: AI_TEAM Core Team
**Влияет на**: ORCHESTRATOR_SPEC, IMPLEMENTATION_ROADMAP

---

## Контекст

Для реализации Orchestrator v2.0 мы должны решить:
1. Писать workflow engine с нуля или использовать готовое решение?
2. Как совместить надёжность инфраструктуры с интеллектом AI-агентов?

### Текущая ситуация

- ORCHESTRATOR_SPEC v1.0 описывает Policy-Governed Hybrid архитектуру
- ORCHESTRATOR_SPEC v2.0 DRAFT добавляет: subprocesses, meetings, dynamic cards, quality loop
- Исследование мирового опыта показало: 15-21 неделя экономии при использовании готовых решений

---

## Решение

### Принимаем двухслойную архитектуру:

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR v2.1                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ВЕРХНИЙ СЛОЙ: "Умный" (LangGraph)                         │
│   ══════════════════════════════════════════════════════    │
│   • Коллаборативное планирование (Meeting Protocol)         │
│   • Оценка качества (Quality Loop)                          │
│   • Динамическая генерация планов                           │
│   • Разрешение конфликтов между агентами                    │
│                                                              │
│                          ▼                                   │
│                                                              │
│   НИЖНИЙ СЛОЙ: "Надёжный" (Temporal)                        │
│   ══════════════════════════════════════════════════════    │
│   • Durable Execution (переживает рестарты)                 │
│   • Event Sourcing (полный audit trail)                     │
│   • Child Workflows (subprocesses)                          │
│   • Retry + Compensation (Saga pattern)                     │
│   • Exactly-once semantics                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Почему Temporal

### Требования из ORCHESTRATOR_SPEC v2.0

| Требование | Temporal покрывает? |
|------------|---------------------|
| State Contract (хранение состояния) | ✅ Event History |
| Recovery after crash | ✅ Auto-replay |
| Subprocess Manager | ✅ Child Workflows |
| Idempotency | ✅ Workflow ID |
| Optimistic locking | ✅ Workflow versioning |
| Saga / Compensation | ✅ Native support |
| Retry + Backoff | ✅ Activity Retry Policy |
| Long-running processes | ✅ Durable execution (дни, недели) |

### Альтернативы (отвергнуты)

| Технология | Почему НЕ подходит |
|------------|-------------------|
| Apache Airflow | Для batch ETL, не для event-driven |
| Netflix Conductor | Менее активное community |
| Camunda/Zeebe | Enterprise licensing, избыточен для MVP |
| Написать с нуля | 15-21 неделя работы, риски |

### Риски Temporal

| Риск | Mitigation |
|------|------------|
| "Чёрный ящик" | Принять философию Temporal целиком |
| Операционный overhead | Temporal Cloud или self-hosted |
| Vendor lock-in | Temporal open-source (MIT) |

---

## Почему LangGraph

### Требования из ORCHESTRATOR_SPEC v2.0

| Требование | LangGraph покрывает? |
|------------|---------------------|
| Meeting Protocol | ✅ Multi-agent graph |
| Conflict Resolution | ✅ Conditional edges |
| Quality Loop (cycles) | ✅ Cyclical graphs |
| Dynamic planning | ✅ LLM nodes |
| State management | ✅ MemorySaver |

### Альтернативы (отвергнуты)

| Технология | Почему НЕ подходит |
|------------|-------------------|
| CrewAI | Менее гибкий, для прототипирования |
| AutoGen | Conversation-first, не graph-first |
| OpenAI Swarm | Experimental, не production |

### Риски LangGraph

| Риск | Mitigation |
|------|------------|
| Не production-hardened | LangGraph ВНУТРИ Temporal Activity |
| Versioning слабее | Temporal обеспечивает durability |

---

## Критическое правило архитектуры

> **LangGraph ДОЛЖЕН быть ВНУТРИ Temporal Activity, а не наоборот**

```python
# ПРАВИЛЬНО:
@activity.defn
async def collaborative_planning(topic: str) -> Plan:
    """Temporal Activity вызывает LangGraph"""
    graph = build_meeting_graph()
    result = await graph.ainvoke({"topic": topic})
    return result["final_plan"]

@workflow.defn
class ProcessCardWorkflow:
    @workflow.run
    async def run(self, request: ProcessRequest) -> Result:
        # Temporal обеспечивает durability
        plan = await workflow.execute_activity(
            collaborative_planning,
            request.topic,
            start_to_close_timeout=timedelta(minutes=10)
        )
        # ... выполнение плана
```

```python
# НЕПРАВИЛЬНО:
# LangGraph как верхний уровень — теряем durability!
```

---

## Что это меняет в архитектуре

### Process Card Execution

```
Process Card (YAML)
       │
       ▼
Temporal Workflow
       │
       ├── Activity: parse_card()
       │
       ├── Activity: collaborative_planning()  ← LangGraph здесь
       │        │
       │        └── Meeting Protocol (graph)
       │
       ├── Child Workflow: step_1             ← Subprocess
       │        │
       │        └── Activity: execute_action()
       │
       ├── Activity: quality_check()           ← LangGraph здесь
       │        │
       │        └── Quality Loop (graph)
       │
       └── Activity: finalize()
```

### Mapping концепций

| AI_TEAM Concept | Temporal Implementation |
|-----------------|------------------------|
| Process Card | Workflow Definition |
| Step | Activity |
| Subprocess | Child Workflow |
| State Contract | Event History |
| Recovery | Replay from Event Log |
| Variables | Workflow State |
| Budget tracking | Workflow metadata + signals |
| Meeting Protocol | Activity с LangGraph |
| Quality Loop | Activity с LangGraph |

---

## Совместимость с существующими SSOT

### Что НЕ меняется

| SSOT | Статус |
|------|--------|
| CloudEvents | ✅ Остаётся форматом сообщений |
| MindBus (AMQP) | ✅ Остаётся транспортом к агентам |
| Process Card | ✅ Остаётся DSL |
| Node Passport | ✅ Остаётся контрактом агентов |
| Node Registry | ✅ Остаётся discovery механизмом |
| MESSAGE_FORMAT | ✅ Остаётся для COMMAND/RESULT |

### Что меняется

| Компонент | Было | Стало |
|-----------|------|-------|
| State Store | PostgreSQL (custom) | Temporal Event History |
| Execution Engine | Custom State Machine | Temporal Workflow |
| Subprocess Manager | Custom | Temporal Child Workflows |
| Retry Logic | Custom | Temporal Retry Policy |

---

## Экономия ресурсов

| Функция | Без Temporal | С Temporal |
|---------|--------------|------------|
| State Management | 6-8 недель | 0 (встроено) |
| Recovery | 3-4 недели | 0 (встроено) |
| Subprocess | 3-4 недели | 0 (Child Workflows) |
| Retry + Saga | 2-3 недели | 0 (встроено) |
| **ИТОГО** | 15-21 неделя | ~2 недели интеграции |

---

## План внедрения

### Phase 1: Temporal Core (2 недели)
- [ ] Установка Temporal (Docker / Cloud)
- [ ] Базовый Workflow для Process Card
- [ ] Activity для отправки COMMAND через MindBus
- [ ] Интеграция с Node Registry

### Phase 2: LangGraph Integration (2 недели)
- [ ] Activity для Meeting Protocol
- [ ] Activity для Quality Loop
- [ ] Тесты multi-agent scenarios

### Phase 3: Migration (1 неделя)
- [ ] Миграция ORCHESTRATOR_SPEC v2.0 → v2.1
- [ ] Обновление IMPLEMENTATION_ROADMAP
- [ ] Документация

---

## Последствия решения

### Положительные

1. **Надёжность** — Temporal проверен в Uber, Stripe, Netflix
2. **Скорость разработки** — экономия 15-21 недели
3. **Масштабируемость** — Temporal поддерживает миллионы workflows
4. **Audit trail** — полная история из коробки
5. **Time-travel debugging** — можно "отмотать" любой момент

### Отрицательные

1. **Новая зависимость** — Temporal сервер нужно поддерживать
2. **Обучение команды** — новый инструмент
3. **Vendor philosophy** — нужно принять модель Temporal

### Нейтральные

1. **Open source** — MIT лицензия, нет vendor lock-in
2. **Python SDK** — поддерживается, хотя Go/Java сильнее

---

## Связанные документы

- [ORCHESTRATOR_SPEC_v2.1](../SSOT/ORCHESTRATOR_SPEC_v2.1.md) — **текущая спецификация (SSOT)**
- [ORCHESTRATOR_SPEC_v1.0](../SSOT/archive/ORCHESTRATOR_SPEC_v1.0.md) — предыдущая версия (архив)
- [ORCHESTRATOR_SPEC_v2.0_DRAFT](../SSOT/archive/ORCHESTRATOR_SPEC_v2.0_DRAFT.md) — концептуальный черновик (архив)
- [ORCHESTRATOR_WORLD_EXPERIENCE_RESEARCH](archive/ORCHESTRATOR_WORLD_EXPERIENCE_RESEARCH.md) — исследование (архив)
- [Temporal Documentation](https://docs.temporal.io/)
- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)

---

**Решение принято**: 2025-12-20
**Следующий шаг**: ✅ ВЫПОЛНЕНО — ORCHESTRATOR_SPEC v2.1 создан и утверждён как SSOT
