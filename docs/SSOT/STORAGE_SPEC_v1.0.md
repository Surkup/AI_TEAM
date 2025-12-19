# STORAGE Specification v1.0

**Статус**: ✅ Утверждено (Final Release)
**Версия**: 1.0.0
**Дата**: 2025-12-19
**Совместимость**: MindBus Protocol v1.0, MESSAGE_FORMAT v1.1, NODE_PASSPORT v1.0
**Базируется на**: STORAGE_ARCHITECTURE_DISCUSSION_2025-12-19 (8.8/10 экспертная оценка)

---

## TL;DR (Executive Summary)

**STORAGE** — спецификация системы хранения данных для AI_TEAM.

**Основа**: Ready-Made First (fsspec + SQLAlchemy + LangGraph Checkpointer)

**Ключевые компоненты**:
- **Storage Service** — единый сервис-посредник для артефактов
- **Artifact Manifest** — стандартизированные метаданные артефактов
- **Трёхуровневая архитектура** — Agent State / Process State / Artifacts

**Паттерны**:
- **"Pointer, not Payload"** — через MindBus только метаданные, не файлы
- **Commit Point** — артефакт существует IFF запись в БД committed
- **Immutability** — манифесты неизменяемы после создания

**НЕ изобретаем велосипед**: Используем fsspec для файлов, SQLAlchemy для метаданных, LangGraph Checkpointer для состояния агентов.

---

## 1. Архитектурные инварианты

### 1.1. КРИТИЧЕСКИЕ ПРАВИЛА (MUST)

Эти правила являются **незыблемыми** и **обязательными** для всех компонентов системы.

#### Инвариант 1: Artifact Commit Point

```yaml
invariant:
  name: "Artifact Commit Point"
  definition: "Artifact exists IFF manifest record in SQLite is committed"
  consequence: "File without manifest = orphan (подлежит GC)"
  enforcement: "Storage Service validation before INSERT"
```

**Пояснение**: Артефакт считается существующим в системе **только после** успешной записи манифеста в БД. Файл на диске без записи — это "мусор".

#### Инвариант 2: Artifact Immutability

```yaml
invariant:
  name: "Artifact Immutability"
  definition: "Manifest fields immutable after creation (except status)"
  exception: "status: uploading → completed (one-way transition)"
  consequence: "For corrections → create new version with supersedes"
  enforcement: "Storage Service UPDATE validation"
```

**Пояснение**: Мы не правим артефакты. Мы создаём новые версии.

#### Инвариант 3: Pointer, not Payload

```yaml
invariant:
  name: "Pointer not Payload"
  definition: "MindBus carries only metadata and URIs, never file content"
  consequence: "Files uploaded directly to storage, only URI registered via MindBus"
  enforcement: "Message size validation, Code review"
```

**Пояснение**: RabbitMQ оптимизирован для сообщений (KB), не для файлов (MB).

#### Инвариант 4: Single Writer Pattern

```yaml
invariant:
  name: "Single Writer Pattern"
  definition: "Only Storage Service writes to SQLite. Agents NEVER access DB directly."
  reason: "SQLite single-writer limitation + separation of concerns"
  enforcement: "Code review, no DB credentials for agents"
```

#### Инвариант 5: ACL Enforcement Point

```yaml
invariant:
  name: "ACL Enforcement Point"
  definition: "Storage Service is the ONLY place where visibility/ACL is checked"
  enforcement: "All reads go through get_artifact() with requester context"
```

#### Инвариант 6: Uniform Degradation Policy

```yaml
invariant:
  name: "Uniform Degradation Policy"
  definition: "All agents follow same retry/buffer/continue behavior when Storage Service is down"
  enforcement: "Shared library (src/common/storage_client.py), not per-agent implementation"
```

---

## 2. Трёхуровневая архитектура хранения

```
┌─────────────────────────────────────────────────────────────┐
│                    УРОВНИ ХРАНЕНИЯ                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  УРОВЕНЬ 1: AGENT STATE                                     │
│  ─────────────────────                                      │
│  Что: Состояние агента между итерациями самокритики        │
│  Технология: LangGraph Checkpointer (SqliteSaver)          │
│  Готовое решение: ✅ langgraph-checkpoint                   │
│  Свой код: 0 строк                                          │
│                                                             │
│  УРОВЕНЬ 2: PROCESS STATE                                   │
│  ────────────────────────                                   │
│  Что: Статус процесса, какой шаг выполнен                  │
│  Технология: SQLite через SQLAlchemy                        │
│  Готовое решение: ✅ SQLAlchemy                             │
│  Свой код: ~100 строк (модели + CRUD)                       │
│                                                             │
│  УРОВЕНЬ 3: ARTIFACTS                                       │
│  ────────────────────                                       │
│  Что: Результаты работы агентов (тексты, файлы)            │
│  Технология: fsspec (файлы) + SQLite (метаданные)          │
│  Готовое решение: ✅ fsspec, ✅ SQLAlchemy                  │
│  Свой код: ~300 строк (Storage Service handlers)            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Artifact Manifest v1.0

### 3.1. Полная схема

```yaml
artifact:
  # === Идентификация ===
  id: "art_abc123"                    # REQUIRED: Уникальный ID (формат: art_{uuid})
  version: 1                          # REQUIRED: Версия артефакта (integer, starts at 1)
  supersedes: null                    # OPTIONAL: ID предыдущей версии (для изменений)

  # === Связь с процессом ===
  trace_id: "trace_xyz"               # REQUIRED: ID процесса (из COMMAND.traceparent)
  step_id: "research"                 # OPTIONAL: ID шага процесса
  created_by: "agent.researcher.001"  # REQUIRED: ID создателя (node_id)
  created_at: "2025-12-19T10:00:00Z"  # REQUIRED: Время создания (ISO 8601)

  # === Типизация ===
  artifact_type: "research_report"    # REQUIRED: Тип артефакта (см. 3.2)
  content_type: "application/json"    # REQUIRED: MIME type

  # === Расположение ===
  uri: "file:///.data/artifacts/trace_xyz/research_v1.json"  # REQUIRED: URI файла
  size_bytes: 15234                   # REQUIRED: Размер в байтах
  checksum: "sha256:abc123..."        # REQUIRED: Контрольная сумма

  # === Жизненный цикл ===
  status: "completed"                 # REQUIRED: uploading | completed | failed
  retention: "infinite"               # OPTIONAL: Политика хранения (MVP: infinite)

  # === Безопасность ===
  owner: "agent.researcher.001"       # REQUIRED: Владелец артефакта
  visibility: "trace"                 # REQUIRED: trace | private | public

  # === AI Context ===
  context:                            # OPTIONAL: Контекст создания (для воспроизводимости)
    prompt_version: "1.2.0"           # Версия промпта агента
    model_name: "gpt-4o-mini"         # Модель LLM
    model_params:                     # Параметры генерации
      temperature: 0.7
      max_tokens: 4000
    input_artifacts:                  # Зависимости (input artifacts)
      - "art_previous_001"
    execution_time_ms: 3500           # Время выполнения
```

### 3.2. Стандартные artifact_type

| artifact_type | Описание | Создаётся |
|---------------|----------|-----------|
| `research_report` | Результат исследования | Researcher Agent |
| `idea` | Сгенерированная идея | Ideator Agent |
| `critique` | Критический анализ | Critic Agent |
| `draft` | Черновик текста | Writer Agent |
| `edited_draft` | Отредактированный черновик | Editor Agent |
| `final` | Финальный результат | Any Agent |
| `log` | Лог выполнения | Any Agent |
| `intermediate` | Промежуточный результат | Any Agent |

### 3.3. Pydantic Schema

```python
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Literal
from datetime import datetime

class ModelParams(BaseModel):
    """Параметры LLM модели"""
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)

class ArtifactContext(BaseModel):
    """AI-контекст создания артефакта (для воспроизводимости)"""
    prompt_version: Optional[str] = Field(None, description="Версия промпта агента")
    model_name: Optional[str] = Field(None, description="Имя LLM модели")
    model_params: Optional[ModelParams] = Field(None, description="Параметры генерации")
    input_artifacts: Optional[List[str]] = Field(
        default_factory=list,
        description="ID входных артефактов (зависимости)"
    )
    execution_time_ms: Optional[int] = Field(None, ge=0, description="Время выполнения в мс")

class ArtifactManifest(BaseModel):
    """Artifact Manifest v1.0 — SSOT для метаданных артефактов"""

    # Идентификация
    id: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^art_[a-zA-Z0-9_-]+$",
        description="Уникальный ID артефакта"
    )
    version: int = Field(ge=1, description="Версия артефакта")
    supersedes: Optional[str] = Field(None, description="ID предыдущей версии")

    # Связь с процессом
    trace_id: str = Field(min_length=1, description="ID процесса (trace)")
    step_id: Optional[str] = Field(None, description="ID шага процесса")
    created_by: str = Field(min_length=1, description="ID создателя (node_id)")
    created_at: datetime = Field(description="Время создания")

    # Типизация
    artifact_type: str = Field(min_length=1, description="Тип артефакта")
    content_type: str = Field(
        default="application/json",
        description="MIME type содержимого"
    )

    # Расположение
    uri: str = Field(min_length=1, description="URI файла")
    size_bytes: int = Field(ge=0, description="Размер в байтах")
    checksum: str = Field(
        min_length=1,
        pattern=r"^sha256:[a-f0-9]{64}$",
        description="Контрольная сумма SHA256"
    )

    # Жизненный цикл
    status: Literal["uploading", "completed", "failed"] = Field(
        description="Статус артефакта"
    )
    retention: str = Field(default="infinite", description="Политика хранения")

    # Безопасность
    owner: str = Field(min_length=1, description="Владелец артефакта")
    visibility: Literal["trace", "private", "public"] = Field(
        default="trace",
        description="Видимость артефакта"
    )

    # AI Context
    context: Optional[ArtifactContext] = Field(
        None,
        description="Контекст создания для воспроизводимости"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "id": "art_research_001",
                    "version": 1,
                    "trace_id": "trace_xyz",
                    "step_id": "research",
                    "created_by": "agent.researcher.001",
                    "created_at": "2025-12-19T10:00:00Z",
                    "artifact_type": "research_report",
                    "content_type": "application/json",
                    "uri": "file:///.data/artifacts/trace_xyz/research_v1.json",
                    "size_bytes": 15234,
                    "checksum": "sha256:abc123def456...",
                    "status": "completed",
                    "retention": "infinite",
                    "owner": "agent.researcher.001",
                    "visibility": "trace",
                    "context": {
                        "model_name": "gpt-4o-mini",
                        "execution_time_ms": 3500
                    }
                }
            ]
        }
```

---

## 4. Storage Service API

### 4.1. Интеграция с MindBus

Storage Service — участник MindBus с `nodeType: storage`.

**Node Passport**:
```yaml
metadata:
  uid: "storage-001"
  name: "storage-primary"
  nodeType: "storage"
  labels:
    role: "storage"
    capability.file_storage: "true"
    capability.artifact_storage: "true"

spec:
  capabilities:
    - "file_storage"
    - "artifact_storage"
```

### 4.2. Поддерживаемые actions

| Action | Описание | Params |
|--------|----------|--------|
| `register_artifact` | Зарегистрировать артефакт | `manifest: ArtifactManifest` |
| `get_artifact` | Получить артефакт по ID | `artifact_id: str` |
| `list_artifacts` | Список артефактов | `trace_id?: str, artifact_type?: str, limit?: int` |
| `get_artifact_uri` | Получить URI для загрузки | `artifact_id: str` |
| `delete_artifact` | Удалить артефакт | `artifact_id: str` (admin only) |

### 4.3. COMMAND примеры

#### register_artifact

```json
{
  "specversion": "1.0",
  "type": "ai.team.command",
  "source": "agent.researcher.001",
  "id": "cmd-register-001",
  "time": "2025-12-19T10:00:00Z",
  "subject": "task-555",
  "traceparent": "00-trace-abc-01",

  "data": {
    "action": "register_artifact",
    "target_node": "storage-primary",
    "params": {
      "manifest": {
        "id": "art_research_001",
        "version": 1,
        "trace_id": "trace_xyz",
        "created_by": "agent.researcher.001",
        "created_at": "2025-12-19T10:00:00Z",
        "artifact_type": "research_report",
        "content_type": "application/json",
        "uri": "file:///.data/artifacts/trace_xyz/research_v1.json",
        "size_bytes": 15234,
        "checksum": "sha256:abc123...",
        "status": "completed",
        "owner": "agent.researcher.001",
        "visibility": "trace"
      }
    }
  }
}
```

**AMQP Properties**:
```python
routing_key='cmd.storage.any'
priority=20
```

#### get_artifact

```json
{
  "data": {
    "action": "get_artifact",
    "target_node": "storage-primary",
    "params": {
      "artifact_id": "art_research_001"
    },
    "context": {
      "requester_id": "agent.writer.001",
      "requester_trace_id": "trace_xyz"
    }
  }
}
```

### 4.4. RESULT примеры

#### register_artifact — SUCCESS

```json
{
  "specversion": "1.0",
  "type": "ai.team.result",
  "source": "storage-primary",
  "id": "result-001",
  "time": "2025-12-19T10:00:01Z",
  "subject": "task-555",

  "data": {
    "status": "SUCCESS",
    "output": {
      "artifact_id": "art_research_001",
      "registered": true,
      "uri": "file:///.data/artifacts/trace_xyz/research_v1.json"
    },
    "execution_time_ms": 45
  }
}
```

#### get_artifact — SUCCESS

```json
{
  "data": {
    "status": "SUCCESS",
    "output": {
      "manifest": {
        "id": "art_research_001",
        "version": 1,
        "uri": "file:///.data/artifacts/trace_xyz/research_v1.json",
        "...": "..."
      }
    },
    "execution_time_ms": 12
  }
}
```

### 4.5. ERROR примеры

#### Artifact not found

```json
{
  "type": "ai.team.error",
  "data": {
    "error": {
      "code": "NOT_FOUND",
      "message": "Artifact not found: art_unknown_001",
      "retryable": false,
      "details": {
        "artifact_id": "art_unknown_001"
      }
    }
  }
}
```

#### ACL violation

```json
{
  "type": "ai.team.error",
  "data": {
    "error": {
      "code": "PERMISSION_DENIED",
      "message": "Access denied: artifact visibility is 'private', requester is not owner",
      "retryable": false,
      "details": {
        "artifact_id": "art_private_001",
        "visibility": "private",
        "owner": "agent.researcher.001",
        "requester": "agent.writer.002"
      }
    }
  }
}
```

#### Already exists (idempotency)

```json
{
  "type": "ai.team.result",
  "data": {
    "status": "SUCCESS",
    "output": {
      "artifact_id": "art_research_001",
      "registered": false,
      "already_exists": true,
      "message": "Artifact with same ID and checksum already registered"
    },
    "execution_time_ms": 5
  }
}
```

---

## 5. Транзакционный протокол

### 5.1. Upload and Register Flow

```
Agent                   File Storage        Storage Service        SQLite
  |                         |                      |                  |
  |--1. upload(file)------->|                      |                  |
  |   (direct fsspec)       |                      |                  |
  |<--OK + temp_uri---------|                      |                  |
  |                         |                      |                  |
  |--2. register(manifest)------------------------->|                  |
  |                         |                      |                  |
  |                         |<--3. validate--------|                  |
  |                         |   file_exists?       |                  |
  |                         |   checksum_match?    |                  |
  |                         |--OK----------------->|                  |
  |                         |                      |                  |
  |                         |                      |--4. INSERT------>|
  |                         |                      |   (COMMIT POINT) |
  |                         |                      |<--OK-------------|
  |                         |                      |                  |
  |                         |<--5. move------------|                  |
  |                         |   temp → permanent   |                  |
  |                         |--OK----------------->|                  |
  |                         |                      |                  |
  |<--6. artifact_registered-----------------------|                  |
```

### 5.2. Поведение при ошибках

| Шаг | Ошибка | Действие |
|-----|--------|----------|
| 3 | File not found | Return ERROR, агент должен re-upload |
| 3 | Checksum mismatch | Delete temp file, return ERROR |
| 4 | DB error | Delete temp file, return ERROR |
| 5 | Move failed | Rollback INSERT, delete temp, return ERROR |

### 5.3. Idempotency

```yaml
idempotency:
  by: "artifact_id + checksum"

  scenarios:
    same_id_same_checksum: "return SUCCESS with already_exists=true"
    same_id_diff_checksum: "return ERROR code=ALREADY_EXISTS"
    new_id: "normal registration"
```

---

## 6. Degradation Behavior

### 6.1. Когда Storage Service недоступен

```
Agent                   Storage           Storage Service
  |                       |                      |
  |--1. upload(file)----->|                      |
  |<--OK + uri------------|                      |
  |                       |                      |
  |--2. register(uri)-------------------------->|
  |                       |                      X (SERVICE DOWN)
  |<--ERROR: UNAVAILABLE------------------------|
  |                       |                      |
  |--3. RETRY #1 (5s delay)-------------------->|
  |                       |                      X (SERVICE DOWN)
  |<--ERROR: UNAVAILABLE------------------------|
  |                       |                      |
  |--4. RETRY #2 (10s delay)------------------->|
  |                       |                      X (SERVICE DOWN)
  |<--ERROR: UNAVAILABLE------------------------|
  |                       |                      |
  |--5. BUFFER LOCALLY---->|                     |
  |   .data/buffer/       |                      |
  |                       |                      |
  |--6. CONTINUE WORK---->                       |
  |   (graceful degradation)                     |
```

### 6.2. Поведение агентов (ОБЯЗАТЕЛЬНОЕ)

```yaml
agent_degradation_behavior:
  on_storage_unavailable:
    1: "Retry with exponential backoff"
    2: "max_retries: 3"
    3: "backoff: 5s, 10s, 20s"
    4: "After max_retries: buffer artifact locally to .data/buffer/"
    5: "Continue execution (graceful degradation)"
    6: "Retry registration on next heartbeat"

  buffer_location: ".data/buffer/"
  buffer_format: "{artifact_id}.json"  # manifest + content path
```

### 6.3. Orchestrator поведение

```yaml
orchestrator_degradation_behavior:
  on_storage_unavailable:
    - "Mark step as 'pending_storage'"
    - "Don't block process if artifact non-critical"
    - "Alert if critical artifact missing after timeout"
    - "Retry registration when Storage Service recovers"
```

---

## 7. File Storage

### 7.1. fsspec Abstraction

```python
import fsspec
import hashlib

class FileStorage:
    """Абстракция файлового хранилища через fsspec"""

    def __init__(self, base_path: str = ".data/artifacts"):
        self.base_path = base_path
        self.fs = fsspec.filesystem("file")  # MVP: local filesystem

    def upload(self, content: bytes, trace_id: str, filename: str) -> str:
        """Upload file and return URI"""
        path = f"{self.base_path}/{trace_id}/{filename}"
        self.fs.makedirs(f"{self.base_path}/{trace_id}", exist_ok=True)

        with self.fs.open(path, "wb") as f:
            f.write(content)

        return f"file://{path}"

    def compute_checksum(self, content: bytes) -> str:
        """Compute SHA256 checksum"""
        return f"sha256:{hashlib.sha256(content).hexdigest()}"

    def exists(self, uri: str) -> bool:
        """Check if file exists"""
        path = uri.replace("file://", "")
        return self.fs.exists(path)

    def read(self, uri: str) -> bytes:
        """Read file content"""
        path = uri.replace("file://", "")
        with self.fs.open(path, "rb") as f:
            return f.read()
```

### 7.2. Структура директорий

```
.data/
├── artifacts/                    # Зарегистрированные артефакты
│   ├── trace_xyz/
│   │   ├── research_v1.json
│   │   ├── idea_v1.json
│   │   └── draft_v2.txt
│   └── trace_abc/
│       └── final_v1.txt
├── buffer/                       # Буфер при недоступности Storage Service
│   ├── art_pending_001.json
│   └── art_pending_002.json
├── temp/                         # Временные файлы (до регистрации)
│   └── upload_*.tmp
├── orphans/                      # Orphaned files (для GC)
│   └── orphan_2025-12-19_*.json
└── storage.db                    # SQLite база метаданных
```

### 7.3. .gitignore

```gitignore
# Storage data (MVP: local files)
.data/
```

---

## 8. SQLAlchemy Models

### 8.1. Artifact Table

```python
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Enum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class ArtifactStatus(enum.Enum):
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"

class ArtifactVisibility(enum.Enum):
    TRACE = "trace"
    PRIVATE = "private"
    PUBLIC = "public"

class ArtifactModel(Base):
    """SQLAlchemy model for Artifact Manifest"""
    __tablename__ = "artifacts"

    # Primary key
    id = Column(String(100), primary_key=True)
    version = Column(Integer, nullable=False, default=1)

    # Process link
    trace_id = Column(String(100), nullable=False, index=True)
    step_id = Column(String(100), nullable=True)
    created_by = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Type
    artifact_type = Column(String(50), nullable=False, index=True)
    content_type = Column(String(100), nullable=False, default="application/json")

    # Location
    uri = Column(Text, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    checksum = Column(String(100), nullable=False, unique=True)

    # Lifecycle
    status = Column(Enum(ArtifactStatus), nullable=False, default=ArtifactStatus.UPLOADING)
    retention = Column(String(50), nullable=False, default="infinite")

    # Security
    owner = Column(String(100), nullable=False)
    visibility = Column(Enum(ArtifactVisibility), nullable=False, default=ArtifactVisibility.TRACE)

    # AI Context (JSON field)
    context = Column(JSON, nullable=True)

    # Versioning
    supersedes = Column(String(100), nullable=True)

    # Indexes for common queries
    __table_args__ = (
        # Index for trace + type queries
        # CREATE INDEX idx_trace_type ON artifacts(trace_id, artifact_type)
    )
```

### 8.2. Database Configuration

```yaml
# config/services/storage.yaml
storage_service:
  name: "storage-primary"
  type: "storage"

  database:
    path: ".data/storage.db"
    # Override via env: STORAGE_DB_PATH

  file_storage:
    base_path: ".data/artifacts"
    temp_path: ".data/temp"
    buffer_path: ".data/buffer"
    orphans_path: ".data/orphans"

  limits:
    max_file_size_bytes: 10485760  # 10 MB
    max_artifacts_per_trace: 1000

  retention:
    policy: "infinite"  # MVP: no auto-deletion
    gc_enabled: false   # MVP: manual GC only

  endpoint:
    protocol: "amqp"

  log_level: "INFO"

  registry:
    enabled: true
    heartbeat_interval_seconds: 10
```

---

## 9. ACL (Access Control)

### 9.1. Visibility Model

| Visibility | Кто может читать | Пример |
|------------|------------------|--------|
| `trace` | Все участники того же trace_id | Артефакты внутри одного процесса |
| `private` | Только owner | Черновики, личные заметки |
| `public` | Все | Финальные результаты |

### 9.2. ACL Enforcement (в Storage Service)

```python
def check_access(artifact: ArtifactModel, requester_id: str, requester_trace_id: str) -> bool:
    """Check if requester can access artifact"""

    if artifact.visibility == ArtifactVisibility.PUBLIC:
        return True

    if artifact.visibility == ArtifactVisibility.PRIVATE:
        return artifact.owner == requester_id

    if artifact.visibility == ArtifactVisibility.TRACE:
        return artifact.trace_id == requester_trace_id

    return False
```

---

## 10. MVP Limitations

### 10.1. Задокументированные ограничения

```yaml
mvp_limitations:
  documented:
    - "Direct fsspec access (no presigned URLs)"
    - "File-level ACL not enforced at storage layer"
    - "No automated garbage collection"
    - "SQLite single-writer constraint"
    - "Infinite retention (no auto-deletion)"
    - "Local filesystem only (no S3/MinIO)"

  production_upgrade_path:
    - "Presigned URLs with expiration"
    - "PostgreSQL for metadata"
    - "MinIO for files"
    - "Automated GC with configurable retention"
```

### 10.2. Garbage Collection (MVP)

```yaml
garbage_collection:
  mvp:
    enabled: false
    policy: "manual only"

  orphan_detection:
    description: "Files older than 24h without manifest entry"
    script: "scripts/gc_orphans.py"
    schedule: "manual"

  orphan_handling:
    - "Move to .data/orphans/ (not delete immediately)"
    - "Keep for 7 days, then delete"
    - "Log for debugging"
```

---

## 11. Технологии

### 11.1. Выбранные технологии

| Компонент | MVP | Production | Почему |
|-----------|-----|------------|--------|
| Agent State | LangGraph SqliteSaver | LangGraph PostgresSaver | Уже интегрирован |
| Process State | SQLite + SQLAlchemy | PostgreSQL + SQLAlchemy | Zero-config → масштабируемость |
| File Storage | Локальная ФС через fsspec | MinIO через fsspec | Один API, смена бэкенда без кода |
| Metadata | SQLite + SQLAlchemy | PostgreSQL + SQLAlchemy | ACID, миграция одной строкой |
| API | MindBus (AMQP) | MindBus (AMQP) | Единообразие с остальной системой |

### 11.2. Что НЕ используем и почему

| Технология | Причина отказа |
|------------|----------------|
| MLflow | Overkill, другая модель данных (ML vs Agents), требует отдельного сервера |
| Redis | Не нужен (агенты не требуют микросекундных задержек) |
| MongoDB | PostgreSQL JSONB даёт ту же гибкость |
| Прямой SQL в агентах | Нарушает изоляцию, связывает агентов с бэкендом |

---

## 12. Связанные документы

- **[MindBus Protocol v1.0](mindbus_protocol_v1.md)** — транспортный уровень
- **[MESSAGE_FORMAT v1.1](MESSAGE_FORMAT_v1.1.md)** — формат сообщений
- **[NODE_PASSPORT_SPEC v1.0](NODE_PASSPORT_SPEC_v1.0.md)** — паспорт узла
- **[AGENT_SPEC v1.0](AGENT_SPEC_v1.0.md)** — спецификация агентов
- **[STORAGE_ARCHITECTURE_DISCUSSION](../concepts/drafts/STORAGE_ARCHITECTURE_DISCUSSION_2025-12-19.md)** — протокол обсуждения

---

## 13. Changelog

### v1.0.0 (2025-12-19)

- Initial release
- Artifact Manifest v1.0 с AI Context
- Storage Service API
- Транзакционный протокол
- Degradation behavior
- ACL model
- MVP limitations documented

---

**Статус**: ✅ Утверждено
**Следующий шаг**: Реализация Storage Service

---

*Документ подготовлен: 2025-12-19*
*Автор: Claude Code (Opus 4.5)*
*Основа: STORAGE_ARCHITECTURE_DISCUSSION_2025-12-19 (экспертная оценка 8.8/10)*
