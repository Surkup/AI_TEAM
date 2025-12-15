# API Framework: FastAPI


---

# ⚠️ ЧЕРНОВИК — ТРЕБУЕТ ПРОВЕРКИ ⚠️

**Этот документ НЕ является финальным решением!**

Требуется детальный анализ, критика и проверка перед принятием решений.

---
## Решение

**Выбран: FastAPI**

---

## Почему FastAPI?

### 1. Async-first (критично для AI_TEAM)

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class TaskRequest(BaseModel):
    topic: str
    quality_threshold: float = 8.0

@app.post("/tasks")
async def create_task(request: TaskRequest):
    """Создать задачу для AI Team"""
    # Async вызов orchestrator
    result = await orchestrator.execute_task(
        task_config={
            "type": "write_article",
            "topic": request.topic,
            "quality_threshold": request.quality_threshold
        },
        trace_id=str(uuid.uuid4())
    )
    return result
```

**Преимущества:**
- ✅ Async/await из коробки
- ✅ Высокая производительность (как Node.js)
- ✅ Идеально для I/O-bound (LLM calls)

---

### 2. Pydantic валидация = SSOT

```python
from pydantic import BaseModel, Field
from typing import Literal

class Message(BaseModel):
    """SSOT для MindBus message"""
    id: str
    type: Literal["COMMAND", "RESULT", "EVENT"]
    from_agent: str
    to_agent: str
    trace_id: str
    payload: dict

@app.post("/messages")
async def send_message(message: Message):
    """FastAPI автоматически валидирует через Pydantic"""
    mindbus.publish(message)
    return {"status": "sent"}
```

**Преимущества:**
- ✅ Автоматическая валидация
- ✅ Автоматическая документация (OpenAPI)
- ✅ Type safety

---

### 3. Автоматическая документация

**FastAPI генерирует OpenAPI/Swagger UI автоматически:**

```
http://localhost:8000/docs  # Swagger UI
http://localhost:8000/redoc  # ReDoc
```

**Без дополнительного кода!**

---

### 4. Производительность

**Benchmark (requests/sec):**
- FastAPI: ~20,000 req/sec
- Flask: ~2,000 req/sec
- Django: ~1,000 req/sec

**Для AI_TEAM:**
- Узкое место = LLM вызовы (секунды), не API (миллисекунды)
- FastAPI избыточно быстр для наших нужд

---

## API Structure

```python
from fastapi import FastAPI, HTTPException, BackgroundTasks
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle: startup/shutdown"""
    # Startup
    await db_service.connect()
    await mindbus.connect()
    print("API started")

    yield

    # Shutdown
    await db_service.close()
    print("API stopped")

app = FastAPI(
    title="AI_TEAM API",
    version="0.1.0",
    lifespan=lifespan
)

# ============================================
# Tasks API
# ============================================

@app.post("/api/v1/tasks", response_model=TaskResponse)
async def create_task(request: TaskRequest, background_tasks: BackgroundTasks):
    """Создать новую задачу"""
    trace_id = str(uuid.uuid4())

    # Создаем в БД
    task_id = await db.create_task(trace_id, request.dict())

    # Запускаем в фоне
    background_tasks.add_task(
        orchestrator.execute_task,
        request.dict(),
        trace_id
    )

    return {
        "task_id": task_id,
        "trace_id": trace_id,
        "status": "pending"
    }

@app.get("/api/v1/tasks/{trace_id}")
async def get_task(trace_id: str):
    """Получить статус задачи"""
    task = await db.get_task(trace_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

# ============================================
# Artifacts API
# ============================================

@app.get("/api/v1/artifacts/{trace_id}/result")
async def get_result(trace_id: str):
    """Получить финальный результат"""
    task = await db.get_task(trace_id)
    if not task or not task["result_artifact_url"]:
        raise HTTPException(status_code=404)

    # Получаем из MinIO
    artifact_data = storage.get_artifact(task["result_artifact_url"])

    return {
        "trace_id": trace_id,
        "content": artifact_data.decode('utf-8'),
        "metadata": task["metadata"]
    }

# ============================================
# Health & Metrics
# ============================================

@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy"}

@app.get("/metrics")
async def metrics():
    """Prometheus metrics"""
    # TODO: Prometheus integration
    return {"tasks_total": 0}
```

---

## Альтернативы и почему НЕТ

### Flask
**Почему НЕТ:**
- ❌ Sync-first (async сложнее)
- ❌ Нет автоматической валидации
- ❌ Медленнее vs FastAPI

### Django + DRF
**Почему НЕТ:**
- ❌ Тяжелый фреймворк (ORM, admin, etc.)
- ❌ Overkill для API-only
- ❌ Медленнее

### Starlette (базовый)
**Почему НЕТ:**
- ❌ FastAPI = Starlette + Pydantic
- ❌ Придется писать валидацию вручную

---

## Итоговое решение

**FastAPI — идеальный выбор:**

1. ✅ Async-first
2. ✅ Pydantic валидация
3. ✅ Автодокументация
4. ✅ Высокая производительность
5. ✅ Простота использования

---

**Статус:** ✅ УТВЕРЖДЕНО
**Последнее обновление:** 2025-12-15
