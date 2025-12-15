# Redis: Кеш & Rate Limiting

---

## ✅ УТВЕРЖДЕНО

**Решение: Redis для кеширования и очередей**

**Изменение от первоначального плана:**
- ❌ **НЕ используем** Redis Streams как отдельный MindBus
- ✅ **Используем** Temporal для коммуникации между агентами
- ✅ **Используем** Redis для кеширования LLM вызовов и rate limiting

**Причина изменения:**
Temporal уже обеспечивает messaging, state persistence, retry logic. Отдельный MindBus на Redis Streams = дублирование функций.

---

## Роль Redis в AI_TEAM

### 1. Кеширование LLM вызовов = экономия денег

**Проблема:**
LLM вызовы дорогие (GPT-4 ~$0.03 за запрос). Одинаковые запросы не должны стоить денег дважды.

**Решение: LiteLLM + Redis Cache**

```python
import litellm

# Загружаем конфиг из config/redis.yaml и config/llm.yaml
redis_config = load_config("redis.yaml")
llm_config = load_config("llm.yaml")

# Настраиваем Redis для кеша (параметры из конфига)
litellm.cache = litellm.Cache(
    type="redis",
    host=redis_config["host"],
    port=redis_config["port"],
    ttl=llm_config["cache_ttl"]
)

# Первый вызов — реальный запрос к LLM
response1 = completion(
    model=llm_config["default_model"],
    messages=[{"role": "user", "content": "What is AI?"}],
    cache={"ttl": llm_config["cache_ttl"]}
)
# Cost: зависит от модели

# Второй вызов с тем же запросом — из кеша
response2 = completion(
    model=llm_config["default_model"],
    messages=[{"role": "user", "content": "What is AI?"}],
    cache={"ttl": llm_config["cache_ttl"]}
)
# Cost: $0 (кеш!) ✅
```

**Экономия:**
- Типичная задача = 10-20 LLM вызовов
- 30-50% вызовов повторяются (промпты, критерии оценки)
- Redis cache = экономия 30-50% на LLM затратах

---

### 2. Rate Limiting для API

**Проблема:**
Нужно ограничить количество запросов от пользователя (защита от злоупотребления).

**Решение: Redis для rate limiting**

```python
import redis
from fastapi import HTTPException

# Загружаем конфиг Redis из config/redis.yaml
redis_config = load_config("redis.yaml")

redis_client = redis.Redis(
    host=redis_config["host"],
    port=redis_config["port"]
)

async def check_rate_limit(user_id: str, limit: int, window: int):
    """
    Проверяет rate limit для пользователя.

    Args:
        limit: максимум запросов (из конфига)
        window: временное окно в секундах (из конфига)
    """
    key = f"rate_limit:{user_id}"

    # Инкрементируем счётчик
    current = redis_client.incr(key)

    # Устанавливаем TTL при первом запросе
    if current == 1:
        redis_client.expire(key, window)

    # Проверяем лимит
    if current > limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {limit} requests per {window} seconds"
        )

    return current

# Загружаем конфиг rate limiting
rate_limit_config = load_config("api.yaml")["rate_limit"]

# В FastAPI endpoint
@app.post("/api/v1/tasks")
async def create_task(request: TaskRequest, user_id: str):
    await check_rate_limit(
        user_id,
        limit=rate_limit_config["requests_per_window"],
        window=rate_limit_config["window_seconds"]
    )
    # ... создание задачи
```

---

### 3. Session Storage (опционально)

**Если понадобится хранить сессии пользователей:**

```python
# Сохранить сессию
redis_client.setex(
    f"session:{session_id}",
    3600,  # TTL 1 час
    json.dumps({"user_id": "123", "preferences": {...}})
)

# Получить сессию
session_data = redis_client.get(f"session:{session_id}")
```

---

## Почему Redis?

### ✅ Преимущества

1. **Быстрый** - in-memory, микросекундная латентность
2. **Простой** - одна Docker команда для запуска
3. **Надёжный** - используется Twitter, GitHub, Stack Overflow
4. **Персистентность** - опционально (RDB snapshots, AOF)
5. **Популярный** - все знают Redis, легко найти помощь

### Benchmark производительности

```
Redis GET: ~10,000-50,000 ops/sec (один instance)
Redis SET: ~10,000-50,000 ops/sec

AI_TEAM потребности: ~100 ops/sec (кеш lookup)
Запас: 100x-500x ✅
```

---

## Альтернативы и почему НЕТ для MVP

### Memcached
**Почему НЕТ:**
- ❌ Нет персистентности (Redis опционально умеет)
- ❌ Более ограниченные структуры данных
- ❌ Менее популярен в Python экосистеме

**НО:** 🔄 **LEGO-принцип**: Можно заменить Redis на Memcached одной строкой в конфиге если нужна только кеширование.

### Valkey (Redis fork)
**Почему НЕТ для MVP:**
- ❌ Очень новый (2024), меньше production опыта
- ❌ Меньше поддержки в библиотеках

**НО:** 🔄 **LEGO-принцип**: Valkey полностью совместим с Redis, можно переключиться без изменения кода.

### In-Memory Cache (Python dict)
**Почему НЕТ для production:**
- ❌ Не персистентный (перезапуск = потеря кеша)
- ❌ Не работает для distributed setup (несколько workers)

**НО:** ✅ Можно использовать для локальной разработки (упрощение).

---

## Архитектура использования

```
┌──────────────────────────────────────────────┐
│            FastAPI (API Layer)               │
│  - Rate limiting через Redis                 │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│         LiteLLM (LLM Integration)            │
│  - Cache через Redis                         │
│  - Экономия 30-50% на LLM затратах           │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│              Redis Server                     │
│  - Key-Value store                           │
│  - In-memory, быстрый доступ                 │
│  - Опционально: persistence (RDB/AOF)        │
└──────────────────────────────────────────────┘
```

---

## Примеры кода

### Docker Compose

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes  # Включить persistence

volumes:
  redis-data:
```

### Интеграция с LiteLLM

```python
from typing import List, Dict
import litellm
import redis

class LLMService:
    def __init__(self, redis_config: dict, llm_config: dict):
        """
        Args:
            redis_config: dict из config/redis.yaml
            llm_config: dict из config/llm.yaml
        """
        # Формируем Redis URL из конфига
        redis_url = f"redis://{redis_config['host']}:{redis_config['port']}"

        # Настраиваем Redis cache для LiteLLM
        litellm.cache = litellm.Cache(
            type="redis",
            host=redis_config["host"],
            port=redis_config["port"],
            ttl=llm_config["cache_ttl"]
        )

        self.redis_client = redis.from_url(redis_url)

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4",
        use_cache: bool = True
    ):
        """Вызов LLM с кешированием"""
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            cache={"ttl": 3600} if use_cache else None
        )

        # Проверяем был ли cache hit
        cached = response._hidden_params.get("cache_hit", False)

        return {
            "content": response.choices[0].message.content,
            "cached": cached,
            "cost": 0 if cached else response._hidden_params.get("response_cost", 0)
        }
```

### Rate Limiting Middleware для FastAPI

```python
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import redis

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_client: redis.Redis):
        super().__init__(app)
        self.redis = redis_client

    async def dispatch(self, request: Request, call_next):
        # Получаем user_id (из header, token, etc.)
        user_id = request.headers.get("X-User-ID", "anonymous")

        # Проверяем rate limit
        key = f"rate_limit:{user_id}"
        current = self.redis.incr(key)

        if current == 1:
            self.redis.expire(key, 60)  # 60 секунд

        if current > 10:  # Максимум 10 запросов в минуту
            raise HTTPException(status_code=429, detail="Too many requests")

        response = await call_next(request)
        return response

# Добавляем в FastAPI
app.add_middleware(RateLimitMiddleware, redis_client=redis_client)
```

---

## 🔄 LEGO-модульность

**Легко заменить Redis на:**

### Memcached (только кеш)
```python
# Загружаем конфиг из config/memcached.yaml
memcached_config = load_config("memcached.yaml")

# Замена в коде (изменили тип кеша в конфиге)
litellm.cache = litellm.Cache(
    type=memcached_config["type"],  # "memcached"
    host=memcached_config["host"],
    port=memcached_config["port"]
)
```

### Valkey (Redis fork)
```bash
# Замена в docker-compose.yml
services:
  cache:
    image: valkey/valkey:7  # Было: redis:7-alpine
    # ... остальное как у Redis
```

### In-Memory (локальная разработка)
```python
# Замена в коде
litellm.cache = litellm.Cache(type="local")  # В памяти процесса
```

**Интерфейс остаётся тот же** → код агентов не меняется → LEGO-принцип работает ✅

---

## Мониторинг Redis

### Полезные команды

```bash
# Подключиться к Redis CLI
docker exec -it redis redis-cli

# Проверить использование памяти
INFO memory

# Посмотреть все ключи (только для development!)
KEYS *

# Посмотреть статистику кеша
INFO stats

# Проверить количество ключей
DBSIZE
```

### Метрики для мониторинга

```python
import redis

def get_redis_stats(redis_client: redis.Redis) -> dict:
    """Получить статистику Redis"""
    info = redis_client.info()

    return {
        "used_memory_mb": info["used_memory"] / 1024 / 1024,
        "total_keys": redis_client.dbsize(),
        "hit_rate": info["keyspace_hits"] / (info["keyspace_hits"] + info["keyspace_misses"]) if info["keyspace_hits"] + info["keyspace_misses"] > 0 else 0,
        "connected_clients": info["connected_clients"]
    }
```

---

## Итоговое решение

**Redis — правильный выбор для кеширования и rate limiting:**

1. ✅ Кеширование LLM = экономия 30-50% затрат
2. ✅ Rate limiting = защита API
3. ✅ Простая настройка (одна Docker команда)
4. ✅ Быстрый (in-memory)
5. ✅ Надёжный (battle-tested)
6. 🔄 **LEGO-модульность**: Легко заменить на Memcached, Valkey или in-memory

**Что НЕ делаем:**
- ❌ НЕ используем Redis Streams как MindBus
- ❌ НЕ дублируем функции Temporal

**Temporal обеспечивает:**
- ✅ Коммуникацию между агентами
- ✅ State persistence
- ✅ Retry logic

**Redis обеспечивает:**
- ✅ Кеширование (экономия денег)
- ✅ Rate limiting (защита API)

**Разделение ответственности = чистая архитектура** ✅

---

**Статус:** ✅ УТВЕРЖДЕНО
**Последнее обновление:** 2025-12-13
