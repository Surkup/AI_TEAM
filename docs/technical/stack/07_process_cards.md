# Process Cards: Декларативные процессы

**Статус:** ✅ УТВЕРЖДЕНО
**Последнее обновление:** 2025-12-15

---

## Что такое Process Cards?

**Process Card** — это YAML-файл, который описывает **ЧТО** нужно сделать для выполнения задачи.

**Аналогия:**
- **Process Card** = рецепт блюда («возьмите 2 яйца, смешайте с молоком...»)
- **Orchestrator** = повар (знает ГДЕ взять яйца, КАК смешивать, КОГДА готово)

**Философия: "Dumb Card, Smart Orchestrator"**

---

## Философия: Готовые решения первичны

Мы **НЕ изобретаем** DSL для workflow. Используем проверенный синтаксис:

✅ **YAML** — стандартный формат для конфигураций
✅ **GitHub Actions-подобный** синтаксис — знакомый миллионам разработчиков
✅ **Kubernetes Jobs/CronJobs** паттерны — steps, conditions, variables

**Полная техническая спецификация**: [PROCESS_CARD_SPEC_v1.0.md](../../SSOT/PROCESS_CARD_SPEC_v1.0.md)

---

## Пример Process Card

```yaml
# process_cards/article_creation.yaml
apiVersion: ai-team.dev/v1
kind: ProcessCard

metadata:
  id: "550e8400-e29b-41d4-a716-446655440000"
  name: "article_creation"
  version: "1.0"
  description: "Создание высококачественной статьи с итерациями"

spec:
  # Входные параметры
  variables:
    topic: ""
    quality_threshold: 8.0
    research_data: null
    draft: ""
    critique: {}
    iteration: 0

  # Шаги выполнения
  steps:
    # Шаг 1: Исследование темы
    - id: "step_research"
      action: "research_topic"
      params:
        topic: ${input.topic}
      output: research_data

    # Шаг 2: Написание черновика
    - id: "step_write"
      action: "write_article"
      params:
        topic: ${input.topic}
        research: ${research_data}
        previous_feedback: ${critique.suggestions}
      output: draft

    # Шаг 3: Критическая оценка
    - id: "step_critique"
      action: "critique_article"
      params:
        draft: ${draft}
      output: critique

    # Шаг 4: Проверка качества
    - id: "step_quality_check"
      condition: "${critique.score} >= ${quality_threshold}"
      then: "step_publish"
      else: "step_improve"

    # Шаг 5a: Улучшение (если качество низкое)
    - id: "step_improve"
      condition: "${iteration} < 10"
      then: "step_write"  # Повторяем написание
      else: "step_publish"  # Лимит итераций → публикуем как есть

    # Шаг 5b: Финальная правка
    - id: "step_publish"
      action: "edit_article"
      params:
        draft: ${draft}
      output: final_article
```

---

## Ключевые концепции

### 1. Декларативность

**Process Card описывает ТОЛЬКО ЧТО делать:**
- ✅ `action: "write_article"` — ЧТО (какую capability использовать)
- ✅ `params: {topic: "..."}` — ЧТО передать

**НЕ описывает HOW (как это сделать):**
- ❌ Какой агент (Orchestrator найдёт по capability)
- ❌ Какую модель LLM (агент решает сам)
- ❌ Сколько retry (Orchestrator управляет)

### 2. Variables + Expression Language

**Переменные:**
```yaml
variables:
  topic: ""  # Входной параметр
  draft: ""  # Промежуточный результат
  critique: {}  # Результат шага
```

**Expression Language:**
```yaml
# ${variable_name} — подстановка переменной
params:
  topic: ${input.topic}

# ${object.field} — доступ к полям
params:
  feedback: ${critique.suggestions}

# Сравнения
condition: "${critique.score} >= 8.0"
condition: "${iteration} < 10"
```

**Простой и понятный** синтаксис — похож на GitHub Actions.

### 3. Conditional Logic

**Разветвления:**
```yaml
- id: "step_decision"
  condition: "${quality_score} >= 8.0"
  then: "step_publish"  # Если качество достигнуто
  else: "step_improve"  # Иначе улучшаем
```

**Динамические итерации:**
```yaml
- id: "step_retry"
  condition: "${iteration} < 10"
  then: "step_write"  # Повторяем
  else: "step_final"  # Лимит → заканчиваем
```

**Orchestrator интерпретирует условия** и определяет следующий шаг.

---

## "Dumb Card, Smart Orchestrator"

### Process Card (Декларация) — "Глупая"

**Карточка НЕ знает:**
- ❌ Какие агенты зарегистрированы в системе
- ❌ Как найти узел с нужной capability
- ❌ Как обработать ошибку если узел недоступен
- ❌ Сколько раз повторить при временном сбое
- ❌ Как балансировать нагрузку между агентами

**Карточка ТОЛЬКО описывает:**
- ✅ ЧТО нужно сделать (`action: "write_article"`)
- ✅ Какие параметры передать (`params: {topic: "..."}`)
- ✅ Условия перехода (`condition: "${score} >= 8.0"`)

### Orchestrator (Интерпретатор) — "Умный"

**Orchestrator решает:**
- ✅ **WHO**: Находит узел с capability `write_article` в Node Registry
- ✅ **HOW**: Создаёт CloudEvents сообщение, отправляет через MindBus
- ✅ **WHEN**: Управляет таймаутами, retry, fallback
- ✅ **WHERE**: Load balancing между несколькими узлами
- ✅ **IF ERROR**: Обработка ошибок, выбор альтернативного узла

**Аналогия:**
- **Process Card** = SQL запрос (`SELECT * FROM users WHERE age > 18`)
- **Orchestrator** = база данных (query optimizer, execution plan, index selection)

SQL запрос **не знает** как база данных выполнит запрос, он только **описывает ЧТО** нужно получить.

---

## Интеграция с остальной системой

### Process Card → Orchestrator → Node Registry → MindBus

```
1. Process Card                    2. Orchestrator
   ┌────────────────┐                 ┌──────────────────┐
   │ action:        │  →читает→      │ Ищет в Registry: │
   │  write_article │                 │ capability=      │
   │                │                 │  write_article   │
   └────────────────┘                 └──────────────────┘
                                               │
                                               ▼
3. Node Registry                     4. MindBus
   ┌──────────────────┐                 ┌────────────────┐
   │ Найден узел:     │  →возврат→     │ Отправка:      │
   │ writer-001       │                 │ cmd.writer.any │
   │ queue:           │                 │ (CloudEvents)  │
   │  agent.writer... │                 └────────────────┘
   └──────────────────┘
```

**Пошагово:**
1. Orchestrator читает Process Card, видит `action: "write_article"`
2. Запрашивает Node Registry: «Кто умеет `write_article`?»
3. Registry возвращает список узлов с этой capability
4. Orchestrator выбирает узел (load balancing)
5. Создаёт CloudEvents сообщение
6. Отправляет через MindBus в очередь узла
7. Ждёт результат
8. Переходит к следующему шагу Process Card

---

## Примеры кода

### Загрузка Process Card

```python
import yaml
from pydantic import BaseModel

class ProcessCard(BaseModel):
    """SSOT модель Process Card"""
    metadata: dict
    spec: dict

# Загрузка
with open('process_cards/article_creation.yaml') as f:
    card_data = yaml.safe_load(f)

card = ProcessCard(**card_data)
print(f"Loaded: {card.metadata['name']} v{card.metadata['version']}")
```

### Выполнение Process Card (Orchestrator)

```python
class Orchestrator:
    def execute_process_card(self, card: ProcessCard, input_params: dict):
        """Выполняет Process Card"""
        # Инициализация переменных
        variables = card.spec['variables'].copy()
        variables.update({'input': input_params})

        # Выполнение шагов
        for step in card.spec['steps']:
            # Проверка условия (если есть)
            if 'condition' in step:
                if not self._eval_condition(step['condition'], variables):
                    continue  # Пропускаем шаг

            # Выполнение action
            if 'action' in step:
                result = self._execute_action(
                    action=step['action'],
                    params=self._substitute_variables(step['params'], variables)
                )

                # Сохранение результата в переменные
                if 'output' in step:
                    variables[step['output']] = result

            # Переходы (then/else)
            if 'then' in step or 'else' in step:
                next_step_id = self._eval_branch(step, variables)
                # Переход к указанному шагу...

        return variables

    def _execute_action(self, action: str, params: dict):
        """Находит узел и выполняет action"""
        # 1. Поиск в Registry
        nodes = self.registry.find_by_capability(action)
        if not nodes:
            raise NoCapableNodesError(f"No nodes with capability: {action}")

        # 2. Load balancing
        target = self._select_best_node(nodes)

        # 3. Отправка через MindBus
        result = self.mindbus.send_command(
            queue=target.mindbus_queue,
            action=action,
            params=params,
            timeout=60
        )

        return result
```

---

## Docker Compose для Process Cards

```yaml
version: '3.8'

services:
  orchestrator:
    build: ./orchestrator
    environment:
      - ETCD_HOST=etcd
      - RABBITMQ_HOST=rabbitmq
    volumes:
      - ./process_cards:/app/process_cards  # ← Process Cards монтируются
    depends_on:
      - etcd
      - rabbitmq
```

**Process Cards загружаются из файловой системы** — можно изменять без перезапуска Orchestrator (hot reload).

---

## Альтернативы

### Temporal Workflows (Python code)
**Почему НЕТ:**
- ❌ Хардкод логики в коде (не декларативно)
- ❌ Нельзя изменить без перезапуска
- ❌ Требует знания Python для создания процесса

**Process Cards:**
- ✅ Декларативные (YAML)
- ✅ Hot reload (изменили файл → новая логика)
- ✅ Может создать непрограммист

### BPMN (Business Process Model and Notation)
**Почему НЕТ для MVP:**
- ❌ Overkill (слишком сложная нотация)
- ❌ XML-based (менее human-readable)
- ❌ Требует специальных редакторов

**Process Cards:**
- ✅ Простой YAML
- ✅ Редактируется в любом текстовом редакторе

### Apache Airflow DAGs
**Почему НЕТ:**
- ❌ Python code (не декларативно)
- ❌ Фокус на batch processing (не real-time)

---

## Итоговое решение

**Process Cards (YAML DSL) — правильный выбор:**

1. ✅ **Декларативность** — описывают ЧТО, а не КАК
2. ✅ **"Dumb Card, Smart Orchestrator"** — разделение ответственности
3. ✅ **GitHub Actions-like** синтаксис — знакомый и простой
4. ✅ **Hot reload** — изменения без перезапуска
5. ✅ **Expression Language** — variables, conditions, branches
6. ✅ **Capability-based** — не привязаны к конкретным агентам
7. 🔄 **LEGO-модульность** — процессы независимы от исполнения

**Разделение ответственности:**
- **Process Card** — WHAT (какие действия, в каком порядке)
- **Orchestrator** — WHO/HOW/WHERE (какой узел, как выполнить, обработка ошибок)
- **Node Registry** — WHERE найти узлы
- **MindBus** — HOW доставить команды

**Process Cards = рецепты для AI_TEAM** ✅

---

**Статус:** ✅ УТВЕРЖДЕНО
**Техническая спецификация:** [PROCESS_CARD_SPEC_v1.0.md](../../SSOT/PROCESS_CARD_SPEC_v1.0.md)
**Последнее обновление**: 2025-12-15
