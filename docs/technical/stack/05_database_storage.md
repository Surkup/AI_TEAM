# Database & Storage: Трёхуровневая архитектура

**Статус:** ✅ УТВЕРЖДЕНО
**Последнее обновление:** 2025-12-19
**SSOT:** [STORAGE_SPEC_v1.0.md](../../SSOT/STORAGE_SPEC_v1.0.md)

---

## TL;DR

**Принцип:** Ready-Made Solutions First

**Выбранный стек:**
- **Agent State** → LangGraph Checkpointer (SqliteSaver)
- **Process State** → SQLite + SQLAlchemy
- **Artifacts** → fsspec (файлы) + SQLite (метаданные)

**MVP → Production путь:**
- SQLite → PostgreSQL (одна строка конфига)
- Local FS → MinIO/S3 (одна строка конфига через fsspec)

---

## Трёхуровневая архитектура хранения

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

## Технологии

### MVP (Zero Config)

| Компонент | Технология | Почему |
|-----------|------------|--------|
| Agent State | LangGraph SqliteSaver | Уже интегрирован в LangGraph |
| Metadata DB | SQLite + SQLAlchemy | Zero-config, файловая БД |
| File Storage | Local FS через fsspec | Zero-config, работает везде |

### Production (Scale)

| Компонент | Технология | Почему |
|-----------|------------|--------|
| Agent State | LangGraph PostgresSaver | Масштабируемость |
| Metadata DB | PostgreSQL + SQLAlchemy | ACID, concurrent writes |
| File Storage | MinIO через fsspec | S3-compatible, self-hosted |

**Переход MVP → Production:**
```python
# MVP
saver = SqliteSaver.from_conn_string(".data/checkpoints.db")
fs = fsspec.filesystem("file")

# Production (меняем 2 строки)
saver = PostgresSaver.from_conn_string(os.environ["DATABASE_URL"])
fs = fsspec.filesystem("s3", endpoint_url=os.environ["MINIO_URL"])
```

---

## Artifact Manifest v1.0

Каждый артефакт имеет стандартизированные метаданные:

```yaml
artifact:
  # Идентификация
  id: "art_abc123"                    # Уникальный ID
  version: 1                          # Версия
  supersedes: null                    # ID предыдущей версии

  # Связь с процессом
  trace_id: "trace_xyz"               # ID процесса
  step_id: "research"                 # ID шага
  created_by: "agent.researcher.001"  # ID создателя
  created_at: "2025-12-19T10:00:00Z"  # Время создания

  # Типизация
  artifact_type: "research_report"    # Тип артефакта
  content_type: "application/json"    # MIME type

  # Расположение
  uri: "file:///.data/artifacts/trace_xyz/research_v1.json"
  size_bytes: 15234
  checksum: "sha256:abc123..."

  # Жизненный цикл
  status: "completed"                 # uploading → completed
  retention: "infinite"               # MVP: no auto-deletion

  # Безопасность
  owner: "agent.researcher.001"
  visibility: "trace"                 # trace | private | public

  # AI Context (для воспроизводимости)
  context:
    prompt_version: "1.2.0"
    model_name: "gpt-4o-mini"
    model_params:
      temperature: 0.7
    input_artifacts: ["art_previous"]
    execution_time_ms: 3500
```

**Полная Pydantic-схема:** см. [STORAGE_SPEC_v1.0.md §3.3](../../SSOT/STORAGE_SPEC_v1.0.md)

---

## Storage Service

Storage Service — участник MindBus (nodeType: storage).

### API (через MindBus COMMAND/RESULT)

| Action | Описание |
|--------|----------|
| `register_artifact` | Зарегистрировать артефакт |
| `get_artifact` | Получить артефакт по ID |
| `list_artifacts` | Список артефактов (фильтры: trace_id, type) |
| `get_artifact_uri` | Получить URI для загрузки |
| `delete_artifact` | Удалить артефакт (admin only) |

### Архитектурные инварианты

```yaml
invariants:
  - name: "Artifact Commit Point"
    rule: "Artifact exists IFF manifest in SQLite is committed"

  - name: "Artifact Immutability"
    rule: "Manifest immutable after creation (except status)"

  - name: "Pointer, not Payload"
    rule: "MindBus carries only metadata/URIs, never file content"

  - name: "Single Writer Pattern"
    rule: "Only Storage Service writes to SQLite"

  - name: "ACL Enforcement Point"
    rule: "Storage Service is the ONLY ACL checkpoint"
```

---

## Структура директорий

```
.data/
├── artifacts/                    # Зарегистрированные артефакты
│   ├── trace_xyz/
│   │   ├── research_v1.json
│   │   └── draft_v2.txt
│   └── trace_abc/
│       └── final_v1.txt
├── buffer/                       # Буфер при недоступности Storage Service
├── temp/                         # Временные файлы (до регистрации)
├── orphans/                      # Orphaned files (для GC)
└── storage.db                    # SQLite база метаданных
```

---

## Почему НЕ другие варианты?

### ❌ MLflow
- Overkill для нашего use case
- Другая модель данных (ML experiments vs Agent artifacts)
- Требует отдельного сервера

### ❌ MongoDB
- PostgreSQL JSONB даёт ту же гибкость
- SQLite проще для MVP
- Нет преимуществ для нашего use case

### ❌ Redis для State
- Не нужен (агенты не требуют микросекундных задержек)
- LangGraph Checkpointer уже решает проблему

### ❌ Прямой SQL в агентах
- Нарушает изоляцию
- Связывает агентов с бэкендом
- Storage Service — единственная точка доступа

---

## Degradation Behavior

### Когда Storage Service недоступен

```yaml
agent_behavior:
  1: "Retry with exponential backoff (5s, 10s, 20s)"
  2: "max_retries: 3"
  3: "After max_retries: buffer artifact to .data/buffer/"
  4: "Continue execution (graceful degradation)"
  5: "Retry registration on next heartbeat"
```

**Почему важно:** ИИ-агенты работают долго (минуты). Потеря 3 минут работы и $5 токенов из-за "моргнувшей БД" — недопустима. Локальный буфер — страховка инвестиций.

---

## Связанные документы

- **[STORAGE_SPEC_v1.0.md](../../SSOT/STORAGE_SPEC_v1.0.md)** — полная SSOT спецификация
- **[STORAGE_ARCHITECTURE_DISCUSSION](../../concepts/drafts/STORAGE_ARCHITECTURE_DISCUSSION_2025-12-19.md)** — протокол обсуждения
- **[AGENT_SPEC_v1.0.md](../../SSOT/AGENT_SPEC_v1.0.md)** — интеграция с агентами

---

## MVP Limitations

```yaml
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

---

**Статус:** ✅ УТВЕРЖДЕНО
**Следующий шаг:** Реализация Storage Service
