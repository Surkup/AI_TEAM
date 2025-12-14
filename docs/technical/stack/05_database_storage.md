# Database & Storage: PostgreSQL + MinIO


---

# ⚠️ ЧЕРНОВИК — ТРЕБУЕТ ПРОВЕРКИ ⚠️

**Этот документ НЕ является финальным решением!**

Требуется детальный анализ, критика и проверка перед принятием решений.

---
## Решение

**Выбрано:**
- **PostgreSQL** — для structured data (задачи, состояния, метрики)
- **MinIO** — для artifacts (тексты, файлы, результаты работы агентов)

---

## PostgreSQL: State & Metadata

### Почему PostgreSQL?

**1. Battle-tested реляционная БД**
- ✅ 30+ лет в production
- ✅ ACID транзакции
- ✅ Богатые типы данных (JSONB, Arrays, UUID)
- ✅ Отличная производительность

**2. JSONB для гибкости**
```sql
-- Таблица tasks с JSONB payload
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id TEXT NOT NULL,
    status TEXT NOT NULL,  -- pending, in_progress, completed, failed
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    config JSONB NOT NULL,  -- Конфигурация задачи
    metadata JSONB,  -- Произвольные метаданные
    result_artifact_url TEXT  -- Ссылка на MinIO
);

-- Индексы для быстрого поиска
CREATE INDEX idx_tasks_trace_id ON tasks(trace_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created_at ON tasks(created_at DESC);

-- JSONB индексы для поиска по метаданным
CREATE INDEX idx_tasks_metadata ON tasks USING gin(metadata);
```

**3. Сложные запросы**
```sql
-- Найти все задачи с quality_score > 8
SELECT * FROM tasks
WHERE metadata->>'quality_score' > '8'
AND status = 'completed';

-- Статистика по агентам
SELECT
    config->>'agent' as agent_name,
    COUNT(*) as total_tasks,
    AVG((metadata->>'quality_score')::float) as avg_quality
FROM tasks
WHERE status = 'completed'
GROUP BY agent_name;
```

---

### Схема базы данных (MVP)

```sql
-- Задачи
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id TEXT NOT NULL,
    user_id TEXT,  -- Кто создал задачу
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    config JSONB NOT NULL,  -- { "type": "write_article", "topic": "...", ... }
    metadata JSONB,  -- { "quality_score": 8.5, "iterations": 3, "cost": 0.12 }
    result_artifact_url TEXT,  -- minio://artifacts/task-123/result.txt
    error_message TEXT
);

-- Сообщения (для истории, опционально)
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id TEXT NOT NULL,
    message_type TEXT NOT NULL,  -- COMMAND, RESULT, EVENT
    from_agent TEXT NOT NULL,
    to_agent TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL
);

-- Артефакты (метаданные)
CREATE TABLE artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    artifact_type TEXT NOT NULL,  -- article, critique, image, etc.
    storage_url TEXT NOT NULL,  -- minio://artifacts/...
    size_bytes BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB
);

-- Метрики агентов
CREATE TABLE agent_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL,
    metric_name TEXT NOT NULL,  -- llm_calls, tokens_used, avg_latency, etc.
    value FLOAT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    labels JSONB  -- { "model": "gpt-4", "trace_id": "..." }
);

-- Индексы
CREATE INDEX idx_messages_trace_id ON messages(trace_id);
CREATE INDEX idx_artifacts_trace_id ON artifacts(trace_id);
CREATE INDEX idx_agent_metrics_name_time ON agent_metrics(agent_name, timestamp DESC);
```

---

## MinIO: Artifact Storage

### Почему MinIO?

**1. S3-compatible object storage**
- ✅ Полная совместимость с AWS S3 API
- ✅ Self-hosted (не зависим от AWS)
- ✅ Легкий и быстрый

**2. Простой deployment**
```bash
# Docker Compose
docker run -p 9000:9000 -p 9001:9001 \
  -e "MINIO_ROOT_USER=admin" \
  -e "MINIO_ROOT_PASSWORD=password" \
  minio/minio server /data --console-address ":9001"
```

**3. Bucket structure**
```
minio://
  └── ai-team-artifacts/
      ├── tasks/
      │   └── task-{trace_id}/
      │       ├── input.json
      │       ├── draft_v1.txt
      │       ├── critique_v1.json
      │       ├── draft_v2.txt
      │       └── final_result.txt
      └── agent-outputs/
          ├── writer/
          ├── critic/
          └── editor/
```

---

### Код для работы с MinIO

```python
from minio import Minio
from typing import BinaryIO, Optional
import json

class ArtifactStorage:
    """Сервис для работы с артефактами в MinIO"""

    def __init__(self, endpoint: str, access_key: str, secret_key: str):
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=False  # True для production с HTTPS
        )
        self.bucket = "ai-team-artifacts"

        # Создаем bucket если не существует
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def save_artifact(
        self,
        trace_id: str,
        artifact_name: str,
        content: str | bytes | BinaryIO,
        content_type: str = "text/plain"
    ) -> str:
        """
        Сохраняет артефакт.

        Returns: URL артефакта
        """
        object_name = f"tasks/{trace_id}/{artifact_name}"

        # Конвертируем строку в bytes если нужно
        if isinstance(content, str):
            content = content.encode('utf-8')
            length = len(content)
            from io import BytesIO
            content = BytesIO(content)
        elif isinstance(content, bytes):
            length = len(content)
            from io import BytesIO
            content = BytesIO(content)
        else:
            # Файл
            content.seek(0, 2)  # Конец файла
            length = content.tell()
            content.seek(0)  # Начало файла

        # Сохраняем
        self.client.put_object(
            bucket_name=self.bucket,
            object_name=object_name,
            data=content,
            length=length,
            content_type=content_type
        )

        return f"minio://{self.bucket}/{object_name}"

    def get_artifact(self, url: str) -> bytes:
        """Получает артефакт по URL"""
        # url = "minio://ai-team-artifacts/tasks/trace-123/result.txt"
        parts = url.replace("minio://", "").split("/", 1)
        bucket = parts[0]
        object_name = parts[1]

        response = self.client.get_object(bucket, object_name)
        data = response.read()
        response.close()
        response.release_conn()

        return data

    def save_json_artifact(self, trace_id: str, name: str, data: dict) -> str:
        """Сохраняет JSON артефакт"""
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        return self.save_artifact(
            trace_id=trace_id,
            artifact_name=name,
            content=json_str,
            content_type="application/json"
        )

    def get_json_artifact(self, url: str) -> dict:
        """Получает JSON артефакт"""
        data = self.get_artifact(url)
        return json.loads(data.decode('utf-8'))
```

---

### Использование в Agent

```python
class WriterAgent(Agent):
    def __init__(
        self,
        config: AgentConfig,
        mindbus: MindBus,
        llm_service: LLMService,
        storage: ArtifactStorage,
        db: DatabaseService
    ):
        super().__init__(config, mindbus)
        self.llm_service = llm_service
        self.storage = storage
        self.db = db

    async def execute(self, task: dict, context: dict, trace_id: str) -> dict:
        # Генерируем статью
        result = await self.llm_service.complete(
            messages=[...],
            trace_id=trace_id
        )

        article = result["content"]

        # Сохраняем артефакт в MinIO
        artifact_url = self.storage.save_artifact(
            trace_id=trace_id,
            artifact_name=f"draft_{context.get('iteration', 1)}.txt",
            content=article,
            content_type="text/plain"
        )

        # Сохраняем метаданные в PostgreSQL
        await self.db.save_artifact_metadata(
            trace_id=trace_id,
            agent_name=self.config.name,
            artifact_type="article_draft",
            storage_url=artifact_url,
            size_bytes=len(article.encode('utf-8')),
            metadata={
                "iteration": context.get("iteration", 1),
                "model": result["model"],
                "tokens": result["tokens"],
                "cost": result["cost"]
            }
        )

        return {
            "artifact_url": artifact_url,
            "metadata": result["metadata"]
        }
```

---

## Почему НЕ другие варианты?

### MongoDB
**Почему НЕТ:**
- ❌ Нам не нужна schema-less (у нас есть Pydantic для SSOT)
- ❌ PostgreSQL JSONB дает ту же гибкость
- ❌ PostgreSQL лучше для аналитических запросов
- ❌ Еще одна база данных (PostgreSQL уже выбран)

### MySQL
**Почему НЕТ:**
- ❌ Слабее JSONB support vs PostgreSQL
- ❌ Меньше advanced типов данных
- ❌ PostgreSQL более feature-rich

### AWS S3 (вместо MinIO)
**Почему НЕТ для MVP:**
- ❌ Зависимость от AWS
- ❌ Стоимость (egress fees)
- ✅ **Но**: MinIO S3-compatible → легко мигрировать позже

---

## Database Service (Python wrapper)

```python
from typing import Optional, Dict, Any
import asyncpg
from uuid import UUID
import json

class DatabaseService:
    """Сервис для работы с PostgreSQL"""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Создает connection pool"""
        self.pool = await asyncpg.create_pool(self.connection_string)

    async def create_task(
        self,
        trace_id: str,
        config: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> UUID:
        """Создает новую задачу"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO tasks (trace_id, user_id, status, config)
                VALUES ($1, $2, 'pending', $3)
                RETURNING id
                """,
                trace_id,
                user_id,
                json.dumps(config)
            )
            return row['id']

    async def update_task_status(
        self,
        trace_id: str,
        status: str,
        metadata: Optional[Dict] = None,
        result_url: Optional[str] = None
    ):
        """Обновляет статус задачи"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE tasks
                SET status = $2,
                    metadata = COALESCE($3, metadata),
                    result_artifact_url = COALESCE($4, result_artifact_url),
                    updated_at = NOW()
                WHERE trace_id = $1
                """,
                trace_id,
                status,
                json.dumps(metadata) if metadata else None,
                result_url
            )

    async def get_task(self, trace_id: str) -> Optional[Dict]:
        """Получает задачу по trace_id"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM tasks WHERE trace_id = $1",
                trace_id
            )
            if row:
                return dict(row)
            return None

    async def save_artifact_metadata(
        self,
        trace_id: str,
        agent_name: str,
        artifact_type: str,
        storage_url: str,
        size_bytes: int,
        metadata: Optional[Dict] = None
    ):
        """Сохраняет метаданные артефакта"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO artifacts (trace_id, agent_name, artifact_type, storage_url, size_bytes, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                trace_id,
                agent_name,
                artifact_type,
                storage_url,
                size_bytes,
                json.dumps(metadata) if metadata else None
            )
```

---

## Итоговое решение

**PostgreSQL + MinIO — правильный выбор потому что:**

**PostgreSQL:**
1. ✅ Battle-tested для structured data
2. ✅ JSONB для гибкости
3. ✅ Отличная производительность для аналитики
4. ✅ ACID транзакции

**MinIO:**
1. ✅ S3-compatible (легко мигрировать на AWS S3)
2. ✅ Self-hosted (контроль данных)
3. ✅ Простой deployment
4. ✅ Идеален для больших файлов

**Разделение ответственности:**
- PostgreSQL = metadata, состояния, метрики
- MinIO = артефакты (тексты, файлы)

---

**Статус:** 📝 ЧЕРНОВИК (требует проверки и утверждения)
**Последнее обновление:** 2025-12-13
