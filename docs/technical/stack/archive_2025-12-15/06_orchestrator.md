# Workflow Engine: Temporal с первого дня

---

## ✅ УТВЕРЖДЕНО

**Решение: Temporal для orchestration с MVP**

**Изменение от первоначального плана:**
- ❌ **НЕ пишем** Custom Orchestrator для MVP
- ✅ **Используем** Temporal с первого дня
- ✅ **LangGraph агенты** = Temporal Activities

**Причина изменения:**
Custom Orchestrator = reinventing Temporal (state persistence, retry, versioning). Temporal НЕ сложнее чем Custom, но намного мощнее. Избегаем двойной работы (Custom → потом миграция на Temporal).

---

## Что такое Temporal?

**Temporal = workflow engine для долгоживущих процессов**

**Ключевые концепции:**
- **Workflow** = бизнес-процесс (может длиться часы/дни/месяцы)
- **Activity** = отдельный шаг процесса (вызов агента, API, etc.)
- **State persistence** = автоматическое сохранение состояния
- **Automatic retry** = повторы при ошибках

**Простыми словами:**
> Temporal помнит где остановился workflow, даже если сервер упал. Автоматически повторяет неудавшиеся шаги. Визуализирует выполнение.

---

## Temporal для AI_TEAM

### Killer Feature #1: Динамические итерации до качества

```python
from temporalio import workflow, activity
from datetime import timedelta

@workflow.defn
class ArticleWorkflow:
    @workflow.run
    async def run(self, topic: str, quality_threshold: float = 8.0) -> dict:
        """Создаёт статью с итерациями до достижения качества"""

        quality_score = 0.0
        iteration = 0
        # ⚙️ Параметры из конфига (загружаются из config/workflows.yaml)
        max_iterations = 10  # TODO: load from config

        # Динамические итерации - Temporal поддерживает!
        while quality_score < quality_threshold and iteration < max_iterations:
            iteration += 1

            # Activity = вызов Writer агента
            # ⚙️ Timeouts из конфига (config/workflows.yaml)
            draft = await workflow.execute_activity(
                write_article,
                args=[topic, iteration],
                start_to_close_timeout=timedelta(minutes=5)  # TODO: load from config
            )

            # Activity = вызов Critic агента
            critique = await workflow.execute_activity(
                critique_article,
                args=[draft],
                start_to_close_timeout=timedelta(minutes=3)
            )

            quality_score = critique["score"]

            # Killer Feature #3: Адаптивные сценарии
            if "факты сомнительные" in critique.get("weaknesses", []):
                # Динамически добавляем fact-checking
                await workflow.execute_activity(
                    fact_check_article,
                    args=[draft],
                    start_to_close_timeout=timedelta(minutes=5)
                )

        # Финальная правка
        final_article = await workflow.execute_activity(
            edit_article,
            args=[draft],
            start_to_close_timeout=timedelta(minutes=3)
        )

        return {"article": final_article, "iterations": iteration, "score": quality_score}
```

**Что Temporal даёт автоматически:**
- ✅ State persistence (workflow может восстановиться после сбоя)
- ✅ History (вся история выполнения сохраняется)
- ✅ Retry logic (неудавшиеся activities повторяются)
- ✅ Timeout handling (если activity зависла)
- ✅ Визуализация (Web UI показывает progress)

**⚙️ Zero Hardcoding:**
В production коде все параметры (`max_iterations`, timeouts) загружаются из `config/workflows.yaml`:
```yaml
article_workflow:
  max_iterations: 10
  quality_threshold: 8.0
  timeouts:
    write_article_minutes: 5
    critique_article_minutes: 3
    fact_check_minutes: 5
    edit_article_minutes: 3
```

---

### Activities = Агенты

```python
from temporalio import activity
from langgraph.graph import StateGraph

# Activity #1: Writer Agent (LangGraph)
@activity.defn
async def write_article(topic: str, iteration: int) -> str:
    """Пишет статью через LangGraph"""
    # LangGraph workflow для Writer
    writer_workflow = StateGraph(AgentState)
    # ... настройка writer графа

    result = writer_workflow.invoke({"topic": topic, "iteration": iteration})
    return result["draft"]

# Activity #2: Critic Agent
@activity.defn
async def critique_article(draft: str) -> dict:
    """Критикует статью"""
    critic_workflow = StateGraph(CriticState)
    # ... настройка critic графа

    result = critic_workflow.invoke({"draft": draft})
    return {
        "score": result["quality_score"],
        "strengths": result["strengths"],
        "weaknesses": result["weaknesses"],
        "suggestions": result["suggestions"]
    }

# Activity #3: Fact Checker (кастомный агент)
@activity.defn
async def fact_check_article(draft: str) -> dict:
    """Проверяет факты через внешний API"""
    # Killer Feature #2: Мета-оркестратор
    fact_checker = ExternalAPIAgent("perplexity")
    return await fact_checker.verify_facts(draft)

# Activity #4: Editor Agent
@activity.defn
async def edit_article(draft: str) -> str:
    """Финальная правка"""
    editor_workflow = StateGraph(EditorState)
    result = editor_workflow.invoke({"draft": draft})
    return result["final_article"]
```

---

## Почему Temporal, а не Custom?

### ✅ Temporal даёт из коробки:

**1. State Persistence**
```python
# Если Temporal Worker упадёт в середине workflow...
# После перезапуска workflow продолжится с того же места!
# Не нужно писать логику сохранения/восстановления состояния
```

**2. Automatic Retry**
```python
@activity.defn(retry_policy=RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=3
))
async def write_article(...):
    # Если LLM API упадёт, Temporal автоматически повторит
    pass
```

**3. Versioning**
```python
# Можно обновить логику workflow без breaking changes
# Старые запущенные workflows продолжат работать со старой версией
# Новые запустятся с новой версией
```

**4. Distributed Execution**
```python
# Несколько Temporal Workers могут обрабатывать activities параллельно
# Автоматический load balancing
# Horizontal scaling
```

**5. Визуализация**
```
http://localhost:8080  # Temporal Web UI

Видно:
- Какие workflows запущены
- Текущий шаг выполнения
- История всех activities
- Ошибки и retry attempts
- Latency каждого шага
```

---

## Custom Orchestrator vs Temporal

| Функция | Custom | Temporal |
|---------|--------|----------|
| **Код для MVP** | 500+ строк | 100-200 строк |
| **State persistence** | Писать вручную (Redis/PostgreSQL) | Автоматически ✅ |
| **Retry logic** | Писать вручную | Автоматически ✅ |
| **Distributed execution** | Писать вручную | Автоматически ✅ |
| **Визуализация** | Писать вручную | Web UI из коробки ✅ |
| **Версионирование** | Писать вручную | Автоматически ✅ |
| **Timeout handling** | Писать вручную | Автоматически ✅ |
| **Отладка** | Сложно (логи) | Легко (Web UI + history) ✅ |
| **Learning curve** | 1 день (простой Python) | 2-3 дня (новые концепции) |

**Вывод:** Temporal сложнее на 1-2 дня изучения, но экономит недели разработки.

---

## Интеграция с остальным стеком

### Temporal + LangGraph

```python
# LangGraph агенты = Temporal Activities
@activity.defn
async def langgraph_writer_activity(task: dict) -> dict:
    """Обёртка LangGraph как Temporal Activity"""
    workflow = StateGraph(WriterState)
    # ... настройка LangGraph
    return workflow.invoke(task)

# Temporal Workflow вызывает LangGraph
@workflow.defn
class TaskWorkflow:
    @workflow.run
    async def run(self, task: dict) -> dict:
        result = await workflow.execute_activity(
            langgraph_writer_activity,
            args=[task],
            start_to_close_timeout=timedelta(minutes=10)
        )
        return result
```

### Temporal + LiteLLM (через Activities)

```python
@activity.defn
async def llm_call_activity(prompt: str, model: str = "gpt-4") -> str:
    """LLM вызов как Activity с автоматическим retry"""
    # LiteLLM с Redis cache
    response = await acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        cache={"ttl": 3600}
    )
    return response.choices[0].message.content
```

### Temporal + PostgreSQL

```python
@activity.defn
async def save_task_activity(trace_id: str, result: dict):
    """Сохранение результата в БД как Activity"""
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE tasks SET status = 'completed', result = $1 WHERE trace_id = $2",
            json.dumps(result), trace_id
        )
```

---

## Архитектура с Temporal

```
┌────────────────────────────────────────────┐
│         FastAPI (API Gateway)              │
│  - Создаёт задачу                          │
│  - Запускает Temporal Workflow             │
└──────────────────┬─────────────────────────┘
                   │ start_workflow()
                   ▼
┌────────────────────────────────────────────┐
│         Temporal Server                     │
│  - Управляет workflows                      │
│  - State persistence                        │
│  - Task queue                               │
└──────────────────┬─────────────────────────┘
                   │ assigns activities
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
┌─────────┐  ┌─────────┐  ┌─────────┐
│ Worker 1│  │ Worker 2│  │ Worker 3│
│         │  │         │  │         │
│Activities│  │Activities│  │Activities│
│(Agents) │  │(Agents) │  │(Agents) │
└─────────┘  └─────────┘  └─────────┘
     │            │            │
     └────────────┴────────────┘
                  │
     ┌────────────┴────────────┐
     │                         │
     ▼                         ▼
┌─────────┐              ┌─────────┐
│ Redis   │              │PostgreSQL│
│ (cache) │              │  (state) │
└─────────┘              └─────────┘
```

---

## Docker Compose для MVP

```yaml
version: '3.8'

services:
  # Temporal Server (все в одном для MVP)
  temporal:
    image: temporalio/auto-setup:latest
    ports:
      - "7233:7233"  # gRPC
      - "8080:8080"  # Web UI
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_USER=temporal
      - POSTGRES_PWD=temporal
      - POSTGRES_SEEDS=postgres
    depends_on:
      - postgres

  # Temporal Worker (наши агенты)
  worker:
    build: ./worker
    environment:
      - TEMPORAL_SERVER=temporal:7233
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/ai_team
    depends_on:
      - temporal
      - redis
      - postgres

  # FastAPI (API Gateway)
  api:
    build: ./api
    ports:
      - "8000:8000"
    environment:
      - TEMPORAL_SERVER=temporal:7233
    depends_on:
      - temporal

  # PostgreSQL (для задач и Temporal state)
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_PASSWORD=password
      - POSTGRES_USER=postgres
    volumes:
      - postgres-data:/var/lib/postgresql/data

  # Redis (кеш для LLM)
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres-data:
```

**5 контейнеров для полного стека!** ✅

---

## 🔄 LEGO-модульность

**Легко заменить Temporal на:**

### Airflow
```python
# Было: Temporal Workflow
@workflow.defn
class ArticleWorkflow:
    ...

# Стало: Airflow DAG
from airflow import DAG
from airflow.operators.python import PythonOperator

dag = DAG("article_workflow", ...)
write_task = PythonOperator(task_id="write", python_callable=write_article)
```

### Prefect
```python
# Было: Temporal
@workflow.defn
class ArticleWorkflow:
    ...

# Стало: Prefect Flow
from prefect import flow, task

@task
def write_article(...):
    ...

@flow
def article_workflow(...):
    draft = write_article(...)
    ...
```

### Custom (если очень нужно)
```python
# Можно вернуться к Custom если Temporal не подходит
# Но вряд ли понадобится - Temporal очень гибкий
```

**Интерфейс Activity остаётся похожим** → агенты (Activities) не меняются → LEGO-принцип работает ✅

---

## Примеры из реального мира

**Компании используют Temporal:**
- **Uber** - управление заказами (долгоживущие workflows)
- **Netflix** - media processing pipelines
- **Coinbase** - financial transactions
- **HashiCorp** - infrastructure provisioning

**Паттерн:** Долгоживущие процессы с гарантией выполнения.

**AI_TEAM use case:** Создание статьи может занять 10-30 минут (несколько итераций). Temporal гарантирует что процесс завершится, даже если worker упадёт.

---

## Итоговое решение

**Temporal с первого дня — правильный выбор для AI_TEAM:**

1. ✅ **Проще чем Custom** - меньше кода, больше функций
2. ✅ **State persistence** - автоматическое восстановление
3. ✅ **Retry logic** - не теряем задачи при сбоях
4. ✅ **Визуализация** - Web UI для отладки
5. ✅ **Versioning** - обновления без breaking changes
6. ✅ **Distributed** - horizontal scaling из коробки
7. ✅ **Battle-tested** - используется Uber, Netflix, Coinbase

**Интеграция:**
- ✅ LangGraph агенты = Temporal Activities
- ✅ LiteLLM вызовы = Activities с retry
- ✅ PostgreSQL = Activities для persistence

**Модульность:**
- 🔄 Можно заменить на Airflow/Prefect если нужны другие паттерны
- 🔄 Агенты (Activities) остаются независимыми

**Для вайб-кодинга:**
- ✅ Learning curve 2-3 дня (tutorials отличные)
- ✅ Работающий MVP за неделю
- ✅ Не нужно писать инфраструктуру
- ✅ Избегаем reinventing wheel

**Почему НЕ Custom:**
- ❌ Reinventing Temporal = месяцы работы
- ❌ Потом всё равно мигрировали бы на Temporal
- ❌ Temporal НЕ сложнее Custom для наших задач

---

**Статус:** ✅ УТВЕРЖДЕНО
**Последнее обновление:** 2025-12-13
