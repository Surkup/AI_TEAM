# ORCHESTRATOR Specification v2.0 DRAFT

**Статус**: **ЧЕРНОВИК** для обсуждения и доработки
**Версия**: 2.0-draft
**Дата начала**: 2025-12-19
**Основа**: ORCHESTRATOR_SPEC_v1.0 + все концептуальные черновики + новое видение

---

## ВАЖНО: Это рабочий документ

Этот документ объединяет:
- ✅ Текущую спецификацию ORCHESTRATOR_SPEC_v1.0
- ✅ Черновики: Cognitive Stack, Brain Dynamics, Concept v0.2, Process Card Interpreter
- ✅ Открытые вопросы из QUESTIONS.md (раздел 1: Orchestrator)
- ✅ **НОВОЕ**: Коллаборативное планирование с командой агентов
- ✅ **НОВОЕ**: Динамическое создание и вложенность Process Cards

**Цель документа**: Создать полное ТЗ на "умного оркестратора", который станет сердцем системы AI_TEAM.

---

## Содержание

1. [Философия и видение](#1-философия-и-видение)
2. [Ключевые отличия от v1.0](#2-ключевые-отличия-от-v10)
3. [Коллаборативное планирование](#3-коллаборативное-планирование)
4. [Динамическое создание Process Cards](#4-динамическое-создание-process-cards)
5. [Иерархия процессов (вложенность)](#5-иерархия-процессов-вложенность)
6. [Когнитивный стек управления](#6-когнитивный-стек-управления)
7. [Рекурсивная декомпозиция задач](#7-рекурсивная-декомпозиция-задач)
8. [Quality Loop (петля качества)](#8-quality-loop-петля-качества)
9. [Интерпретатор Process Cards](#9-интерпретатор-process-cards)
10. [9 этапов оркестрирования проекта](#10-9-этапов-оркестрирования-проекта)
11. [Защитные механизмы](#11-защитные-механизмы)
12. [Интеграция с существующими компонентами](#12-интеграция-с-существующими-компонентами)
13. [Открытые вопросы для обсуждения](#13-открытые-вопросы-для-обсуждения)
14. [План разработки](#14-план-разработки)

---

## 1. Философия и видение

### 1.1. Главная идея

> **Orchestrator = умный координатор, работающий С командой, а не НАД командой**

Orchestrator не диктует — он **модерирует обсуждение**, **синтезирует предложения**, **формирует консенсус** и **создаёт план действий** вместе с агентами.

### 1.2. Каноническая метафора (обновлённая)

| Компонент | Роль | Метафора |
|-----------|------|----------|
| **MindBus** | Передача информации | Нервная система |
| **Orchestrator** | Координация и планирование | **Совет директоров** (CEO + советники) |
| **Agents** | Экспертиза и исполнение | Специалисты отделов |
| **Process Cards** | Планы и инструкции | Протоколы совещаний, приказы |
| **Storage** | Долговременная память | Архив, библиотека |

### 1.3. Принцип "Коллективного разума"

```
Человек (CEO): "Напиши книгу про AI"
                   │
                   ▼
    ┌─────────────────────────────────────┐
    │         ORCHESTRATOR                 │
    │  "Ребята, поступила задача.          │
    │   Давайте обсудим план!"             │
    └────────────────┬────────────────────┘
                     │
    ┌────────────────┼────────────────┐
    ▼                ▼                ▼
┌─────────┐    ┌─────────┐    ┌─────────┐
│Researcher│    │ Writer  │    │ Editor  │
│"Изучить │    │"Создать │    │"Сделать │
│ тренды" │    │ план"   │    │ ревью"  │
└─────────┘    └─────────┘    └─────────┘
                     │
                     ▼
    ┌─────────────────────────────────────┐
    │  ORCHESTRATOR синтезирует план:      │
    │  1. Исследование → 2. Оглавление →   │
    │  3. Написание глав → 4. Редактура    │
    └─────────────────────────────────────┘
```

### 1.4. Что умеет "умный Orchestrator" (полный список возможностей)

| Возможность | Описание | Источник идеи |
|-------------|----------|---------------|
| **Знает агентов в системе** | Видит Node Registry, понимает capabilities | v1.0 |
| **Знает кому поручить** | Capability matching, выбор исполнителя | v1.0 |
| **Понимает язык карточек** | YAML/JSON интерпретатор Process Cards | Process Card Interpreter |
| **Находит ошибки в карточках** | Валидация, проверка зависимостей | Process Card Interpreter |
| **Понимает невыполнимость** | Нет исполнителей → escalation | v1.0, QUESTIONS.md 1.7 |
| **Создаёт карточки динамически** | LLM генерирует план из запроса | **НОВОЕ**, Brain Dynamics |
| **Создаёт подпроцессы** | Вложенные карточки, иерархия | **НОВОЕ**, QUESTIONS.md 1.7 |
| **Проваливается в подуровни** | Рекурсивная декомпозиция | **НОВОЕ**, Brain Dynamics |
| **Координирует обсуждение** | Агенты предлагают, Orchestrator синтезирует | **НОВОЕ** |
| **Оценивает качество** | Quality Loop, критика, улучшения | Cognitive Stack |
| **Самоанализ** | Причинно-следственные связи, post-mortem | Brain Dynamics |

---

## 2. Ключевые отличия от v1.0

### 2.1. Сравнительная таблица

| Аспект | v1.0 | v2.0 DRAFT |
|--------|------|------------|
| **Планирование** | LLM Planner решает сам | **Коллаборативное** — команда обсуждает |
| **Process Cards** | Статичные (YAML загружается) | **Динамические** — создаются в процессе |
| **Иерархия** | Плоская (один уровень) | **Вложенная** — карточки вызывают карточки |
| **Декомпозиция** | Однократная | **Рекурсивная** — пока команда не скажет "хватит" |
| **Кто решает глубину?** | Policy (max_steps) | **Команда + Policy** |
| **Quality Loop** | Упоминается | **Полностью описан** |
| **Self-reflection** | Нет | **Есть** — анализ причин, post-mortem |

### 2.2. Эволюция архитектуры

```
v1.0: Policy-Governed Hybrid (LLM + Policy Layer)
           │
           ▼
v2.0: Collaborative Policy-Governed Hybrid
      ┌────────────────────────────────────────────┐
      │               ORCHESTRATOR                  │
      │  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
      │  │ Meeting  │  │   LLM    │  │  Policy  │ │
      │  │Moderator │◄─│ Planner  │─►│  Layer   │ │
      │  └──────────┘  └──────────┘  └──────────┘ │
      │       │              │             │       │
      │       └──────────────┼─────────────┘       │
      │                      ▼                     │
      │            ┌──────────────────┐           │
      │            │ Execution Engine │           │
      │            └──────────────────┘           │
      └────────────────────────────────────────────┘
```

---

## 3. Коллаборативное планирование

### 3.1. Концепция "Совещания"

Когда поступает новая задача, Orchestrator не решает сам — он **созывает совещание** с агентами.

### 3.2. Протокол совещания

```yaml
# Шаг 1: Orchestrator объявляет тему
meeting:
  id: "meeting-001"
  topic: "Новая задача: написать книгу про AI"
  participants:
    - researcher
    - writer
    - editor
    - critic
  goal: "Определить план реализации"
  initiated_at: "2025-12-19T10:00:00Z"

# Шаг 2: Каждый агент отвечает proposal-ом
proposals:
  - from: researcher
    proposal:
      action: "research_topic"
      description: "Изучить тренды AI 2025, популярных авторов, конкурентов"
      why: "Чтобы книга была актуальной и уникальной"
      estimated_effort: "medium"
      dependencies: []

  - from: writer
    proposal:
      action: "create_outline"
      description: "Создать структуру книги: оглавление, главы, подглавы"
      why: "Без структуры писать бессмысленно"
      estimated_effort: "low"
      dependencies: ["research_topic"]

  - from: editor
    proposal:
      action: "define_style_guide"
      description: "Определить стиль, tone of voice, целевую аудиторию"
      why: "Единообразие текста с самого начала"
      estimated_effort: "low"
      dependencies: []

# Шаг 3: Orchestrator синтезирует план
synthesis:
  method: "llm_synthesis"  # или "voting" или "orchestrator_decision"
  result:
    steps:
      - id: "step-1"
        action: "research_topic"
        assignee_requirements: ["web_search", "summarization"]

      - id: "step-2"
        action: "define_style_guide"
        assignee_requirements: ["text_analysis"]
        parallel_with: "step-1"  # Можно параллельно

      - id: "step-3"
        action: "create_outline"
        assignee_requirements: ["text_generation"]
        depends_on: ["step-1", "step-2"]
```

### 3.3. Режимы принятия решений

```yaml
# В Process Card или глобально:
decision_mode:
  type: "orchestrator_synthesis"  # По умолчанию

  # Альтернативы:
  # type: "voting"              # Голосование агентов
  # type: "consensus"           # Требуется согласие всех
  # type: "human_approval"      # Человек утверждает план

  # Параметры для synthesis:
  synthesis:
    model: "gpt-4"
    consider_all_proposals: true
    explain_rejections: true
```

### 3.4. Когда НЕ нужно совещание

Orchestrator может пропустить совещание если:
- Задача простая (1-2 шага)
- Есть готовый шаблон Process Card
- Человек явно запретил ("просто сделай, не обсуждай")

```yaml
meeting_policy:
  skip_if:
    - task_complexity: "trivial"
    - template_exists: true
    - human_override: "skip_meeting"
```

---

## 4. Динамическое создание Process Cards

### 4.1. Проблема статических карточек

**v1.0**: Process Card = заранее написанный YAML файл.

**Проблема**: Для каждой новой задачи нужно вручную писать YAML.

### 4.2. Решение: LLM генерирует карточки

```
Человек: "Напиши книгу про AI"
              │
              ▼
┌─────────────────────────────────────────┐
│  Orchestrator + LLM Planner:            │
│  "Сгенерирую Process Card для этой      │
│   задачи на основе обсуждения"          │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  Новая Process Card (runtime):          │
│  - id: process-book-ai-001              │
│  - steps: [research, outline, ...]      │
│  - generated_by: llm_planner            │
│  - approved_by: human (опционально)     │
└─────────────────────────────────────────┘
```

### 4.3. Схема генерации Process Card

```python
class GeneratedProcessCard(BaseModel):
    """Process Card созданная динамически"""

    # Источник
    generation_source: Literal["llm", "template", "meeting_synthesis"]
    generation_context: Dict[str, Any]  # Что было на входе

    # Стандартные поля
    metadata: ProcessCardMetadata
    spec: ProcessCardSpec

    # Аудит
    generated_at: datetime
    generated_by: str  # ID LLM или шаблона

    # Опциональное одобрение
    approval_required: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
```

### 4.4. Шаблоны как основа генерации

Orchestrator может использовать шаблоны для ускорения:

```yaml
# templates/book_creation.yaml
template:
  id: "template-book-creation"
  name: "Создание книги"

  # Параметры шаблона (заполняются)
  parameters:
    topic: {type: string, required: true}
    genre: {type: string, default: "non-fiction"}
    target_pages: {type: integer, default: 200}

  # Шаблон карточки
  spec:
    variables:
      topic: "{{ params.topic }}"
      genre: "{{ params.genre }}"

    steps:
      - id: research
        action: research_topic
        params:
          topic: "{{ variables.topic }}"

      - id: outline
        action: create_outline
        params:
          style: "{{ variables.genre }}"
        depends_on: [research]

      # ... остальные шаги
```

---

## 5. Иерархия процессов (вложенность)

### 5.1. Проблема плоских процессов

**v1.0**: Все шаги на одном уровне.

**Проблема**: Сложные задачи требуют декомпозиции на подзадачи, которые сами состоят из шагов.

### 5.2. Решение: Вложенные Process Cards

```
Главный процесс: "Написать книгу"
│
├── Подпроцесс: "Этап 1: Исследование"
│   ├── Шаг: Найти источники
│   ├── Шаг: Изучить конкурентов
│   └── Шаг: Составить отчёт
│
├── Подпроцесс: "Этап 2: Структура"
│   ├── Шаг: Определить главы
│   └── Шаг: Написать тезисы
│
├── Подпроцесс: "Этап 3: Написание" (ЦИКЛ x10 глав)
│   └── Под-подпроцесс: "Написать главу N"
│       ├── Шаг: Исследование для главы
│       ├── Шаг: Черновик
│       ├── Шаг: Редактура
│       └── Шаг: Финализация
│
└── Подпроцесс: "Этап 4: Публикация"
    └── ...
```

### 5.3. Синтаксис вложенности в Process Card

```yaml
# Вариант A: Inline подпроцесс
steps:
  - id: research-phase
    type: subprocess  # Не action, а subprocess!
    subprocess:
      id: research-subprocess
      steps:
        - id: find-sources
          action: web_search
        - id: analyze-competitors
          action: text_analysis
        - id: create-report
          action: summarize

  - id: write-chapters
    type: subprocess_loop  # Цикл подпроцессов
    loop:
      count: 10  # или from_variable: "chapter_count"
    subprocess:
      id: write-chapter-{{ loop.index }}
      steps:
        - id: research-chapter
          action: research_topic
          params:
            topic: "{{ parent.outline.chapters[loop.index].title }}"
        - id: write-draft
          action: text_generation
        - id: review
          action: text_review
```

```yaml
# Вариант B: Ссылка на внешний подпроцесс
steps:
  - id: research-phase
    type: subprocess_ref
    ref: "templates/research-phase.yaml"
    inputs:
      topic: "{{ variables.book_topic }}"
    outputs:
      report: research_report

  - id: write-chapters
    type: subprocess_loop
    loop:
      count: "{{ variables.chapter_count }}"
    subprocess_ref: "templates/write-chapter.yaml"
    inputs:
      chapter_number: "{{ loop.index }}"
      chapter_title: "{{ variables.outline.chapters[loop.index].title }}"
```

### 5.4. Модель состояния иерархического процесса

```python
class HierarchicalProcessState(BaseModel):
    """Состояние процесса с иерархией"""

    # Идентификация в иерархии
    process_id: str
    parent_process_id: Optional[str] = None  # None = корневой
    root_process_id: str  # Всегда указывает на корень
    depth: int = 0  # Уровень вложенности (0 = корень)

    # Путь в дереве
    path: List[str] = []  # ["root-001", "research-001", "find-sources-001"]

    # Стандартные поля из v1.0
    phase: ProcessPhase
    current_step_id: Optional[str]
    steps: Dict[str, StepState]
    variables: Dict[str, Any]

    # Дочерние процессы
    children: Dict[str, "HierarchicalProcessState"] = {}

    # Бюджет (наследуется от родителя)
    budget: ProcessBudget
    budget_spent: BudgetUsage
```

### 5.5. Лимиты вложенности

```yaml
# config/orchestrator.yaml
hierarchy:
  max_depth: 10              # Максимальная глубина вложенности
  max_total_steps: 1000      # Всего шагов во всех уровнях
  max_children_per_process: 50  # Максимум подпроцессов

  # Защита от циклов
  cycle_detection: true
  visited_cards_cache_ttl: 3600  # Кэш для обнаружения циклов
```

---

## 6. Когнитивный стек управления

### 6.1. Концепция (из ORCHESTRATOR_COGNITIVE_STACK_v0.1)

Orchestrator управляет задачами как **когнитивный процесс** с состояниями.

### 6.2. State Machine для задач

```
┌─────────────┐
│   PENDING   │ ─── Задача поступила, ждёт планирования
└──────┬──────┘
       │ start_planning()
       ▼
┌─────────────┐
│ RESEARCHING │ ─── Сбор информации, анализ требований
└──────┬──────┘
       │ research_complete()
       ▼
┌─────────────┐
│  PLANNING   │ ─── Формирование плана (совещание с агентами)
└──────┬──────┘
       │ plan_approved()
       ▼
┌─────────────┐
│  EXECUTING  │ ─── Выполнение шагов
└──────┬──────┘
       │
       ├─── step_failed() ───► RETRY
       │                          │
       │                          │ retry_limit_reached()
       │                          ▼
       │                    ┌─────────────┐
       │                    │ ESCALATED   │
       │                    └─────────────┘
       │
       │ step_completed() + needs_critique()
       ▼
┌─────────────┐
│  CRITIQUE   │ ─── Оценка качества результата
└──────┬──────┘
       │
       ├─── quality_low() ───► REFACTORING
       │                          │
       │                          │ refactored()
       │                          ▼
       │                       EXECUTING (повтор)
       │
       │ quality_ok()
       ▼
┌─────────────┐
│ FINALIZING  │ ─── Финальная сборка результата
└──────┬──────┘
       │ finalize()
       ▼
┌─────────────┐
│  COMPLETED  │ ─── Задача выполнена успешно
└─────────────┘
```

### 6.3. Internal Economy (бюджеты)

```yaml
# Бюджет задачи
budget:
  # Ресурсные ограничения
  max_iterations: 10        # Циклов улучшения
  max_llm_calls: 100        # Вызовов LLM
  max_cost_usd: 5.00        # Денежный лимит
  max_time_minutes: 120     # Временной лимит

  # Распределение между под-задачами
  distribution_strategy: "proportional"  # или "fixed", "dynamic"

  # Что делать при исчерпании
  on_budget_exhausted: "escalate"  # или "stop", "request_extension"
```

### 6.4. Triangle of Quality (три агента)

Для критичных задач используется схема:

```
┌──────────────┐
│  EXECUTOR    │ ─── Выполняет задачу
│  (Writer)    │
└──────┬───────┘
       │ result
       ▼
┌──────────────┐
│   CRITIC     │ ─── Оценивает качество
│  (Reviewer)  │
└──────┬───────┘
       │ feedback
       ├─── PASS ───► Финализация
       │
       │ FAIL
       ▼
┌──────────────┐
│  ARBITRATOR  │ ─── Разрешает споры (опционально)
│ (Senior/LLM) │
└──────┬───────┘
       │ decision
       ▼
    EXECUTOR (повтор) или ESCALATE
```

---

## 7. Рекурсивная декомпозиция задач

### 7.1. Концепция (из ORCHESTRATOR_BRAIN_DYNAMICS_v0.1)

**Top-Down декомпозиция**: Большая задача раскрывается на подзадачи, каждая из которых может раскрыться ещё глубже.

### 7.2. Алгоритм рекурсивной декомпозиции

```python
def decompose_recursively(task: Task, depth: int = 0) -> HierarchicalProcess:
    """
    Рекурсивная декомпозиция задачи.

    Останавливается когда:
    1. Задача атомарная (один агент, один шаг)
    2. Команда решила "хватит дробить"
    3. Достигнут max_depth
    4. Исчерпан бюджет на планирование
    """

    # Проверка лимитов
    if depth >= config.max_depth:
        return create_atomic_process(task)

    # Спрашиваем команду: нужно ли дробить?
    meeting_result = convene_planning_meeting(
        topic=f"Как выполнить: {task.description}",
        question="Это атомарная задача или нужна декомпозиция?"
    )

    if meeting_result.decision == "atomic":
        # Команда решила: задача атомарная
        return create_atomic_process(task)

    # Декомпозиция
    subtasks = meeting_result.proposed_subtasks

    # Рекурсивно обрабатываем каждую подзадачу
    subprocesses = []
    for subtask in subtasks:
        subprocess = decompose_recursively(subtask, depth + 1)
        subprocesses.append(subprocess)

    return create_composite_process(task, subprocesses)
```

### 7.3. Критерии "атомарности" задачи

Задача считается атомарной если:

```yaml
atomicity_criteria:
  # Любое из условий = задача атомарная
  any_of:
    - single_agent: true       # Один агент может выполнить
    - single_action: true      # Одно действие
    - estimated_time: "<30m"   # Быстро выполняется
    - team_consensus: "atomic" # Команда так решила

  # Исключения (даже если одно условие выше = true)
  except_if:
    - complexity_score: ">8"   # Слишком сложно
    - requires_research: true  # Нужно изучение
```

### 7.4. Контекст между уровнями

При "проваливании" на нижний уровень передаётся контекст:

```yaml
context_propagation:
  # Что наследуется от родителя
  inherit:
    - trace_id           # Для связи логов
    - root_process_id    # Знать корень
    - budget_remaining   # Остаток бюджета
    - quality_criteria   # Критерии качества
    - variables          # Переменные (копия или ссылка)

  # Что НЕ наследуется
  isolate:
    - step_history       # Своя история
    - retry_counts       # Свои счётчики
```

---

## 8. Quality Loop (петля качества)

### 8.1. Концепция (из ORCHESTRATOR_BRAIN_DYNAMICS_v0.1)

**Quality Loop** — цикл проверки и улучшения результата.

### 8.2. Алгоритм Quality Loop

```
┌─────────────────────────────────────────────────────────┐
│                    QUALITY LOOP                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   1. DISPATCH ──────────────────────────────────────┐   │
│      Отправить задачу исполнителю                   │   │
│                                                      │   │
│                                                      ▼   │
│   2. INGEST ◄───────────────────────────────────────    │
│      Получить результат                              │   │
│                                                      │   │
│                                                      ▼   │
│   3. EVALUATE ──────────────────────────────────────    │
│      Оценить качество (Critic агент или LLM)        │   │
│                                                      │   │
│      ┌────────────────┬────────────────┐            │   │
│      ▼                ▼                ▼            │   │
│   ┌──────┐       ┌──────────┐     ┌──────────┐     │   │
│   │ PASS │       │ MARGINAL │     │   FAIL   │     │   │
│   │ ≥90% │       │  70-90%  │     │   <70%   │     │   │
│   └──┬───┘       └────┬─────┘     └────┬─────┘     │   │
│      │                │                 │           │   │
│      ▼                ▼                 ▼           │   │
│   ACCEPT         IMPROVE?           RETRY?          │   │
│   → Done         (ask team)        (check budget)   │   │
│                      │                 │            │   │
│                      ▼                 ▼            │   │
│              ┌─────────────────────────────┐       │   │
│              │  4. DECISION TREE           │       │   │
│              │                             │       │   │
│              │  IF budget_ok AND          │       │   │
│              │     attempts < max:         │       │   │
│              │       → RETRY with feedback │       │   │
│              │                             │       │   │
│              │  ELSE:                      │       │   │
│              │       → ESCALATE to human   │       │   │
│              └─────────────────────────────┘       │   │
│                                                     │   │
└─────────────────────────────────────────────────────────┘
```

### 8.3. Критерии качества

```yaml
# В Process Card или step
quality:
  criteria:
    - name: "completeness"
      description: "Все ли аспекты темы раскрыты?"
      weight: 0.3

    - name: "accuracy"
      description: "Фактическая точность"
      weight: 0.4

    - name: "style"
      description: "Соответствие стилю"
      weight: 0.2

    - name: "originality"
      description: "Оригинальность, не плагиат"
      weight: 0.1

  thresholds:
    pass: 0.9
    marginal: 0.7
    fail: 0.0

  evaluator:
    type: "critic_agent"  # или "llm", "human"
    agent_requirements: ["text_review", "fact_checking"]
```

### 8.4. Feedback для улучшения

При RETRY Orchestrator формирует feedback:

```json
{
  "attempt": 2,
  "previous_score": 0.65,
  "feedback": {
    "completeness": {
      "score": 0.5,
      "issues": ["Не раскрыта тема X", "Пропущен раздел Y"]
    },
    "accuracy": {
      "score": 0.8,
      "issues": ["Устаревшая статистика в параграфе 3"]
    }
  },
  "suggestions": [
    "Добавить раздел про X",
    "Обновить статистику",
    "Расширить заключение"
  ]
}
```

---

## 9. Интерпретатор Process Cards

### 9.1. Концепция (из PROCESS_CARD_INTERPRETER_v0.2)

**Метафора**: Orchestrator = процессор + система команд (ISA)

- **Process Card** = "программа" (декларативное описание)
- **Orchestrator** = "процессор" (читает, валидирует, выполняет)

### 9.2. Пайплайн интерпретации

```
┌─────────────────────────────────────────────────────────┐
│              PROCESS CARD INTERPRETER                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. PARSE ───────────────────────────────────────────►  │
│     YAML/JSON → Internal AST                             │
│                                                          │
│  2. VALIDATE ────────────────────────────────────────►  │
│     JSON Schema, циклы, зависимости                      │
│                                                          │
│  3. COMPILE ─────────────────────────────────────────►  │
│     AST → Execution Graph (DAG)                          │
│                                                          │
│  4. OPTIMIZE ────────────────────────────────────────►  │
│     Параллелизация, топологическая сортировка            │
│                                                          │
│  5. EXECUTE ─────────────────────────────────────────►  │
│     Step-by-step execution engine                        │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 9.3. Валидация Process Card

```python
class ProcessCardValidator:
    """Валидатор Process Cards"""

    def validate(self, card: ProcessCard) -> ValidationResult:
        errors = []
        warnings = []

        # 1. Schema validation
        errors.extend(self.validate_schema(card))

        # 2. Step references check
        errors.extend(self.validate_step_references(card))

        # 3. Cycle detection
        if self.has_cycles(card):
            errors.append(ValidationError(
                code="CYCLE_DETECTED",
                message="Circular dependency in steps",
                location=self.find_cycle(card)
            ))

        # 4. Variable resolution
        errors.extend(self.validate_variables(card))

        # 5. Capability availability (warning, not error)
        warnings.extend(self.check_capability_availability(card))

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
```

### 9.4. Семантика типов шагов

```yaml
step_types:
  # Action step — вызов агента
  action:
    executor: "agent"
    requires: ["action", "params"]
    produces: "output"

  # Condition step — ветвление
  condition:
    executor: "interpreter"  # Не агент, а сам Orchestrator
    requires: ["condition", "then"]
    optional: ["else"]

  # Subprocess step — вложенный процесс
  subprocess:
    executor: "orchestrator"  # Рекурсия
    requires: ["subprocess"]

  # Subprocess loop — цикл подпроцессов
  subprocess_loop:
    executor: "orchestrator"
    requires: ["loop", "subprocess"]

  # Wait step — ожидание
  wait:
    executor: "scheduler"
    requires: ["wait_for"]  # "duration", "event", "human_input"

  # Complete step — завершение
  complete:
    executor: "interpreter"
    optional: ["output"]
```

---

## 10. 9 этапов оркестрирования проекта

### 10.1. Концепция (из ORCHESTRATOR_CONCEPT_v0.2)

Большой проект проходит 9 этапов от идеи до результата.

### 10.2. Полная схема этапов

```
┌────────────────────────────────────────────────────────────┐
│           9 ЭТАПОВ ОРКЕСТРИРОВАНИЯ ПРОЕКТА                 │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ╔══════════════════════════════════════════════════════╗  │
│  ║  ЭТАП 1: ИНИЦИАЦИЯ                                    ║  │
│  ║  • Получение задачи от человека                       ║  │
│  ║  • Создание Project Card                              ║  │
│  ║  • Определение типа: проект/задача/вопрос             ║  │
│  ╚══════════════════════════════════════════════════════╝  │
│                          │                                  │
│                          ▼                                  │
│  ╔══════════════════════════════════════════════════════╗  │
│  ║  ЭТАП 2: ОПРЕДЕЛЕНИЕ ПРАВИЛ РАБОТЫ                    ║  │
│  ║  • Режим автономности: A/B/C                          ║  │
│  ║    A = полная автономия                               ║  │
│  ║    B = автономия с учётом пожеланий                   ║  │
│  ║    C = полный диалог, человек в курсе                 ║  │
│  ║  • Контрольные точки (quality gates)                  ║  │
│  ║  • Эскалационные правила                              ║  │
│  ╚══════════════════════════════════════════════════════╝  │
│                          │                                  │
│                          ▼                                  │
│  ╔══════════════════════════════════════════════════════╗  │
│  ║  ЭТАП 3: УКРУПНЁННАЯ КОНЦЕПЦИЯ                        ║  │
│  ║  • Назначение, ценность, эффект                       ║  │
│  ║  • Критерии успеха (KPI)                              ║  │
│  ║  • Ограничения (время, бюджет, стиль)                 ║  │
│  ║  • Целевая аудитория                                  ║  │
│  ╚══════════════════════════════════════════════════════╝  │
│                          │                                  │
│                          ▼                                  │
│  ╔══════════════════════════════════════════════════════╗  │
│  ║  ЭТАП 4: АНАЛИТИКА И СБОР ДАННЫХ                      ║  │
│  ║  • Исследование предметной области                    ║  │
│  ║  • Анализ конкурентов/аналогов                        ║  │
│  ║  • Изучение best practices                            ║  │
│  ║  • Принцип: "Не изобретать велосипед"                 ║  │
│  ╚══════════════════════════════════════════════════════╝  │
│                          │                                  │
│                          ▼                                  │
│  ╔══════════════════════════════════════════════════════╗  │
│  ║  ЭТАП 5: ПОЛНАЯ ТЕХНИЧЕСКАЯ ДОКУМЕНТАЦИЯ              ║  │
│  ║  • Детальное ТЗ (убрать все "белые пятна")            ║  │
│  ║  • Структура результата                               ║  │
│  ║  • Спецификации компонентов                           ║  │
│  ╚══════════════════════════════════════════════════════╝  │
│                          │                                  │
│                          ▼                                  │
│  ╔══════════════════════════════════════════════════════╗  │
│  ║  ЭТАП 6: ПЛАН РЕАЛИЗАЦИИ                              ║  │
│  ║  • WBS (Work Breakdown Structure)                     ║  │
│  ║  • Декомпозиция на подзадачи                          ║  │
│  ║  • Определение зависимостей                           ║  │
│  ║  • Распределение по агентам                           ║  │
│  ╚══════════════════════════════════════════════════════╝  │
│                          │                                  │
│                          ▼                                  │
│  ╔══════════════════════════════════════════════════════╗  │
│  ║  ЭТАП 7: ПОДБОР КОМАНДЫ                               ║  │
│  ║  • Capability matching                                ║  │
│  ║  • Проверка доступности агентов                       ║  │
│  ║  • Распределение нагрузки                             ║  │
│  ╚══════════════════════════════════════════════════════╝  │
│                          │                                  │
│                          ▼                                  │
│  ╔══════════════════════════════════════════════════════╗  │
│  ║  ЭТАП 8: ИСПОЛНЕНИЕ С ЦИКЛОМ КАЧЕСТВА                 ║  │
│  ║  • Выполнение шагов                                   ║  │
│  ║  • Quality Loop: проверка → критика → улучшение       ║  │
│  ║  • Обработка ошибок, retry                            ║  │
│  ║  • Сохранение артефактов                              ║  │
│  ╚══════════════════════════════════════════════════════╝  │
│                          │                                  │
│                          ▼                                  │
│  ╔══════════════════════════════════════════════════════╗  │
│  ║  ЭТАП 9: ЛОГИРОВАНИЕ И УЛУЧШЕНИЕ                      ║  │
│  ║  • Post-mortem анализ                                 ║  │
│  ║  • Ретроспектива: что сработало, что нет              ║  │
│  ║  • Улучшение карточек процессов                       ║  │
│  ║  • Сохранение learned lessons                         ║  │
│  ╚══════════════════════════════════════════════════════╝  │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### 10.3. Режимы автономности (из Этапа 2)

```yaml
autonomy_modes:
  A:  # Полная автономия
    description: "Orchestrator действует самостоятельно"
    human_involvement: "minimal"
    checkpoints: ["final_result_only"]
    escalation: "only_on_critical_error"

  B:  # Автономия с учётом пожеланий
    description: "Orchestrator учитывает предпочтения человека"
    human_involvement: "preferences"
    checkpoints: ["major_decisions", "final_result"]
    escalation: "on_significant_decisions"

  C:  # Полный диалог
    description: "Человек в курсе всех шагов"
    human_involvement: "full"
    checkpoints: ["every_phase", "every_major_step"]
    escalation: "on_any_uncertainty"
```

---

## 11. Защитные механизмы

### 11.1. Защита от бесконечной вложенности

```yaml
# Из QUESTIONS.md 1.7
nesting_protection:
  # Жёсткие лимиты
  max_subprocess_depth: 10
  max_total_steps: 1000
  max_total_processes: 100

  # Обнаружение циклов
  cycle_detection:
    enabled: true
    method: "visited_set"  # или "tarjan_scc"

  # Бюджет распределяется по уровням
  budget_inheritance:
    method: "proportional"  # Подпроцесс получает долю бюджета
    reserve_for_parent: 0.1  # 10% оставляем родителю
```

### 11.2. Circuit Breaker для нестабильных агентов

```yaml
# Из QUESTIONS.md 1.9
circuit_breaker:
  failure_threshold: 3        # После 3 ошибок подряд
  recovery_timeout_seconds: 60
  max_recovery_timeout: 3600  # Максимум 1 час
  backoff_multiplier: 2.0

  states:
    closed: "Агент работает нормально"
    open: "Агент временно отключён"
    half_open: "Пробуем восстановить"
```

### 11.3. Rate Limiting

```yaml
rate_limiting:
  # Глобальные лимиты
  global:
    max_commands_per_second: 100
    max_processes_per_minute: 10

  # Лимиты на процесс
  per_process:
    max_steps_per_minute: 60
    max_subprocess_spawns_per_minute: 10
```

### 11.4. Kill Switch

```yaml
kill_switch:
  # Человек может остановить всё
  enabled: true

  # Типы остановки
  stop_types:
    graceful:
      description: "Дождаться текущих шагов, потом остановить"
      timeout_seconds: 300

    immediate:
      description: "Остановить немедленно"
      cancel_in_flight: true

    emergency:
      description: "Аварийная остановка всей системы"
      shutdown_all_components: true
```

---

## 12. Интеграция с существующими компонентами

### 12.1. Совместимость с v1.0

**Orchestrator v2.0 MUST быть обратно совместим с v1.0**:

- ✅ Читать и исполнять старые Process Cards
- ✅ Использовать существующий MESSAGE_FORMAT
- ✅ Работать с Node Registry и Node Passport
- ✅ Интегрироваться с MindBus Protocol

### 12.2. Новые сообщения для MindBus

```yaml
# Дополнительные типы событий для v2.0
new_event_types:
  # Совещания
  - type: "ai.team.event.meeting.started"
    routing_key: "evt.meeting.started"

  - type: "ai.team.event.meeting.proposal"
    routing_key: "evt.meeting.proposal"

  - type: "ai.team.event.meeting.concluded"
    routing_key: "evt.meeting.concluded"

  # Иерархия процессов
  - type: "ai.team.event.subprocess.spawned"
    routing_key: "evt.process.subprocess_spawned"

  - type: "ai.team.event.subprocess.completed"
    routing_key: "evt.process.subprocess_completed"

  # Quality Loop
  - type: "ai.team.event.quality.evaluated"
    routing_key: "evt.quality.evaluated"

  - type: "ai.team.event.quality.improvement_requested"
    routing_key: "evt.quality.improvement_requested"
```

### 12.3. Расширение Storage

```yaml
# Новые типы артефактов для v2.0
new_artifact_types:
  - "process_card_generated"    # Динамически созданные карточки
  - "meeting_transcript"        # Протоколы совещаний
  - "quality_report"            # Отчёты о качестве
  - "post_mortem"               # Ретроспективы
```

---

## 13. Открытые вопросы для обсуждения

### 13.1. Критические вопросы (требуют решения)

| # | Вопрос | Варианты | Рекомендация |
|---|--------|----------|--------------|
| 1 | Как синтезировать план из предложений агентов? | LLM synthesis / Voting / Human approval | LLM synthesis |
| 2 | Кто решает "хватит дробить"? | Команда / Orchestrator / Policy | Команда + Policy |
| 3 | Как распределять бюджет между подпроцессами? | Proportional / Fixed / Dynamic | Proportional |
| 4 | Нужно ли человеку одобрять динамические карточки? | Always / Never / Critical only | Critical only |
| 5 | Как агенты "помнят" контекст совещаний? | Memory / Message / Orchestrator stores | Orchestrator stores |

### 13.2. Вопросы для обсуждения позже

| # | Вопрос | Когда обсуждать |
|---|--------|-----------------|
| 6 | Multi-Orchestrator для HA | После MVP |
| 7 | A/B тестирование процессов | После MVP |
| 8 | Маркетплейс карточек | v2.0+ |
| 9 | Визуальный редактор карточек | v2.0+ |

---

## 14. План разработки

### 14.1. Фазы разработки

```
Фаза 1: Обсуждение и доработка ТЗ (текущая)
├── Ревью этого документа
├── Обсуждение открытых вопросов
├── Консолидация решений
└── Утверждение финальной спецификации

Фаза 2: Минимальная реализация (MVP)
├── Базовый интерпретатор Process Cards (уже есть в v1.0)
├── Добавить поддержку subprocess
├── Добавить базовый Quality Loop
└── Тесты

Фаза 3: Коллаборативное планирование
├── Meeting Protocol
├── Proposal сбор от агентов
├── LLM Synthesis
└── Тесты

Фаза 4: Динамические карточки
├── LLM генерация карточек
├── Шаблоны
├── Валидация
└── Тесты

Фаза 5: Полный когнитивный стек
├── 9 этапов оркестрирования
├── Режимы автономности
├── Self-reflection
└── Post-mortem
```

### 14.2. Критерии готовности MVP v2.0

```yaml
mvp_criteria:
  must_have:
    - "Вложенные подпроцессы работают"
    - "Quality Loop с Critic агентом"
    - "Защита от бесконечной вложенности"
    - "Circuit Breaker"

  should_have:
    - "Базовое коллаборативное планирование"
    - "Динамическое создание простых карточек"

  nice_to_have:
    - "9 этапов оркестрирования"
    - "Self-reflection"
```

---

## Заключение

**ORCHESTRATOR_SPEC v2.0 DRAFT** — это эволюция от "умного исполнителя" к "умному координатору":

| Аспект | v1.0 | v2.0 |
|--------|------|------|
| Роль | Исполнитель карточек | **Координатор команды** |
| Планирование | Одинокий LLM | **Коллаборативное** |
| Process Cards | Статические | **Динамические** |
| Структура | Плоская | **Иерархическая** |
| Качество | Упоминается | **Quality Loop** |
| Обучение | Нет | **Post-mortem, Self-reflection** |

**Следующий шаг**: Обсуждение и доработка этого документа.

---

**Версия**: 2.0-draft
**Дата**: 2025-12-19
**Авторы**: User + Claude Opus 4.5
**Статус**: **ЧЕРНОВИК** — требует обсуждения и доработки
