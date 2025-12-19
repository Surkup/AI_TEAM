# Протокол обсуждения: Архитектура хранения данных AI_TEAM

**Дата:** 2025-12-19
**Участники:** Команда AI_TEAM
**Статус:** ЧЕРНОВИК для обсуждения с коллегами
**Контекст:** Этап 5 IMPLEMENTATION_ROADMAP — Storage

---

## 1. Суть вопроса

### 1.1. Что нужно решить

Система AI_TEAM состоит из автономных AI-агентов (Исследователь, Генератор идей, Критик, Редактор, Пушкин), которые:
- Создают артефакты (тексты, исследования, оценки)
- Передают результаты друг другу через MindBus (RabbitMQ)
- Работают в рамках процессов (Process Cards)

**Ключевые вопросы:**
1. Где и как хранить результаты работы агентов?
2. Как агент узнаёт, где лежит нужный артефакт?
3. Нужен ли отдельный сервис-посредник или все обращаются напрямую?
4. Какие технологии использовать (PostgreSQL, SQLite, S3, Redis)?

### 1.2. Текущее состояние

| Компонент | Что есть | Статус |
|-----------|----------|--------|
| Черновик архитектуры | `docs/technical/stack/05_database_storage.md` | Не утверждён |
| Временная реализация | `src/services/storage_service.py` | In-memory (данные теряются) |
| SSOT спецификация | — | **НЕТ** |
| Тесты | 34 теста пройдено | Для in-memory версии |

### 1.3. Требования к решению

**Функциональные:**
- Сохранение артефактов (тексты, JSON, файлы)
- Получение артефакта по ID
- Поиск по метаданным (trace_id, agent, step)
- Версионирование (история изменений)
- Связь артефакта с процессом и шагом

**Нефункциональные:**
- Надёжность (данные не теряются)
- Масштабируемость (от 1 агента до 100)
- Простота (минимум DevOps)
- Соответствие принципам проекта (SSOT, Ready-Made Solutions First)

---

## 2. Анализ архитектурных паттернов

### 2.1. Паттерн: Операционная система (VFS)

**Как работает:**
```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Программа A│  │  Программа B│  │  Программа C│
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────────┼────────────────┘
                        ▼
              ┌─────────────────┐
              │   ОС (VFS)      │ ← Единый интерфейс
              └────────┬────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
     ┌───────┐    ┌───────┐    ┌───────┐
     │  SSD  │    │  HDD  │    │ Флешка│
     └───────┘    └───────┘    └───────┘
```

**Ключевая идея:** Программа не знает физическое расположение файла. Она работает с абстракцией (путь `/home/user/file.txt`), а ОС маршрутизирует запрос к нужному устройству.

**Применимость для AI_TEAM:** ✅ Высокая
- Агенты = программы
- Storage Service = ОС
- Бэкенды (FS, S3, PostgreSQL) = устройства

### 2.2. Паттерн: Kubernetes PersistentVolume

**Как работает:**
```yaml
# Pod запрашивает хранилище декларативно
apiVersion: v1
kind: PersistentVolumeClaim
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 10Gi
  storageClassName: fast-ssd
```

**Ключевая идея:** Потребитель описывает ЧТО ему нужно (10GB, быстрый SSD), система сама решает ГДЕ и КАК это предоставить.

**Применимость для AI_TEAM:** ⚠️ Частичная
- Хорошо для динамического выделения ресурсов
- Overkill для нашего масштаба (мы не Kubernetes)

### 2.3. Паттерн: Microservices — Storage Service

**Как работает:**
```
┌─────────┐  ┌─────────┐  ┌─────────┐
│Service A│  │Service B│  │Service C│
└────┬────┘  └────┬────┘  └────┬────┘
     │           │           │
     └───────────┼───────────┘
                 ▼
         ┌──────────────┐
         │Storage Service│ ← API: save/get/list/delete
         └──────┬───────┘
                │
     ┌──────────┼──────────┐
     ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│  S3    │ │PostgreSQL│ │ Redis │
└────────┘ └────────┘ └────────┘
```

**Ключевая идея:** Единый сервис-посредник с унифицированным API. Сервисы не знают про бэкенды.

**Применимость для AI_TEAM:** ✅ Высокая
- Соответствует нашей архитектуре (всё через MindBus)
- Storage Service = ещё один участник шины

---

## 3. Анализ технологий

### 3.1. MLflow

**Что это:** Платформа для управления ML-экспериментами от Databricks.

**Модель данных:**
```
Experiment (эксперимент)
  └── Run (запуск)
       ├── Parameters (гиперпараметры)
       ├── Metrics (метрики)
       └── Artifacts (файлы)
```

**Плюсы:**
- ✅ Готовое решение, широко используется в ML
- ✅ Поддержка S3, GCS, Azure, локальной ФС
- ✅ REST API + Python SDK
- ✅ Версионирование моделей
- ✅ UI для просмотра экспериментов

**Минусы:**
- ❌ Требует отдельного сервера (`mlflow server`)
- ❌ Иерархия Experiment → Run не соответствует нашей Process → Step
- ❌ Заточен под ML (train/evaluate/deploy), не под агентные системы
- ❌ Ручное логирование (`mlflow.log_artifact()`)
- ❌ Высокая сложность настройки (50+ часов по отзывам)
- ❌ Не интегрируется с MindBus (REST, не AMQP)

**Источники:**
- [MLflow Artifact Store](https://mlflow.org/docs/3.5.1/self-hosting/architecture/artifact-store/)
- [ZenML: MLflow Alternatives](https://www.zenml.io/blog/mlflow-alternatives)
- [Neptune: Best MLflow Alternatives](https://neptune.ai/blog/best-mlflow-alternatives)

**Вердикт:** ❌ НЕ ПОДХОДИТ — решает другую задачу, overkill для нас

---

### 3.2. LangGraph Checkpointer

**Что это:** Встроенная система persistence в LangGraph (мы уже используем LangGraph для Agent Loop).

**Модель данных:**
```
Thread (поток выполнения)
  └── Checkpoint (контрольная точка)
       └── State (состояние графа, JSON)
```

**Реализации:**
- `InMemorySaver` — для разработки
- `SqliteSaver` — для локальной работы
- `PostgresSaver` — для production

**Плюсы:**
- ✅ Уже интегрирован в LangGraph (мы используем)
- ✅ Автоматическое сохранение после каждого шага
- ✅ Zero config для SQLite
- ✅ Поддержка time-travel (откат к предыдущему состоянию)
- ✅ Human-in-the-loop (пауза и продолжение)

**Минусы:**
- ⚠️ Хранит только состояние графа (JSON), не большие файлы
- ⚠️ Нет версионирования артефактов
- ⚠️ Нет поиска по метаданным

**Источники:**
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [langgraph-checkpoint PyPI](https://pypi.org/project/langgraph-checkpoint/)

**Вердикт:** ✅ ПОДХОДИТ для состояния агентов, но НЕ ЗАМЕНЯЕТ Storage Service

---

### 3.3. PostgreSQL + MinIO (из черновика)

**Что предлагалось:**
- PostgreSQL — метаданные, статусы, метрики
- MinIO — файлы и артефакты (S3-совместимый)

**Плюсы:**
- ✅ Battle-tested технологии
- ✅ PostgreSQL JSONB для гибких метаданных
- ✅ MinIO — self-hosted S3
- ✅ Разделение metadata/files

**Минусы:**
- ❌ Два сервиса для поддержки
- ❌ PostgreSQL требует настройки и администрирования
- ❌ Overkill для MVP (один разработчик, одна машина)
- ❌ Не определено поведение при деградации

**Вердикт:** ⚠️ Хорошо для production, но ИЗБЫТОЧНО для MVP

---

### 3.4. SQLite + Локальная ФС

**Что это:** Минималистичный стек для MVP.

**Плюсы:**
- ✅ Zero config (SQLite встроен в Python)
- ✅ Нет внешних зависимостей
- ✅ ACID транзакции
- ✅ Через SQLAlchemy → легко мигрировать на PostgreSQL

**Минусы:**
- ⚠️ Один writer (проблема при параллельной записи)
- ⚠️ Не масштабируется горизонтально
- ⚠️ Файлы не реплицируются

**Смягчение рисков:**
- Storage Service — единственный writer (агенты не пишут напрямую)
- Для production → PostgreSQL + MinIO

**Вердикт:** ✅ ПОДХОДИТ для MVP

---

### 3.5. fsspec — абстракция файловых систем

**Что это:** Python библиотека для унифицированного доступа к разным файловым системам.

**Поддерживаемые бэкенды:**
- Локальная ФС
- S3 (AWS, MinIO)
- GCS (Google Cloud)
- Azure Blob
- SFTP, FTP
- HTTP/HTTPS
- Memory

**Пример кода:**
```python
import fsspec

# Локальный файл
with fsspec.open('/tmp/file.txt', 'w') as f:
    f.write('hello')

# S3 (тот же код!)
with fsspec.open('s3://bucket/file.txt', 'w') as f:
    f.write('hello')
```

**Плюсы:**
- ✅ Один API для всех бэкендов
- ✅ Смена бэкенда без изменения кода
- ✅ Широко используется (pandas, dask, xarray)
- ✅ Ready-Made Solution

**Минусы:**
- ⚠️ Нужны дополнительные пакеты для каждого бэкенда (s3fs, gcsfs)

**Вердикт:** ✅ ИСПОЛЬЗОВАТЬ для файлового хранилища

---

### 3.6. Redis

**Что это:** In-memory key-value хранилище.

**Плюсы:**
- ✅ Очень быстрый (микросекунды)
- ✅ Простой API (GET/SET)
- ✅ Поддержка TTL (автоудаление)

**Минусы:**
- ❌ Данные в памяти (потеря при перезапуске без persistence)
- ❌ Дополнительный сервис для поддержки
- ❌ Не нужен для нашей задачи (агенты "думают" секундами, не микросекундами)

**Вердикт:** ❌ НЕ НУЖЕН для MVP

---

## 4. Критические замечания коллег

### 4.1. "Не гонять большие данные через RabbitMQ"

**Проблема:** Первоначально предлагалось передавать контент артефактов через MindBus:
```python
# ❌ НЕПРАВИЛЬНО
self.bus.send_command(
    action="store_artifact",
    params={"content": big_article}  # 10MB текста через шину!
)
```

**Почему это плохо:**
- RabbitMQ оптимизирован для сообщений (KB), не для файлов (MB)
- Рост очередей, задержки, ретраи
- Невозможность гарантировать SLA

**Правильный паттерн: "Pointer, not Payload"**
```python
# ✅ ПРАВИЛЬНО
# Шаг 1: Агент кладёт файл напрямую в хранилище
artifact_uri = storage.upload(content)  # → "file:///artifacts/abc.txt"

# Шаг 2: Через шину — только указатель
self.bus.send_command(
    action="register_artifact",
    params={
        "artifact_id": "research-001",
        "uri": artifact_uri,  # Указатель, не контент!
        "size_bytes": 15000,
        "checksum": "sha256:abc..."
    }
)
```

**Решение:** Два канала:
- MindBus — метаданные и команды управления
- Прямой доступ к хранилищу — для файлов (или presigned URLs)

### 4.2. "Нужен стандарт Artifact Manifest"

**Проблема:** Без стандарта каждый агент будет именовать артефакты по-своему:
- `{trace_id}/research_result`
- `output_{agent}_{timestamp}.txt`
- `result.json`

**Решение: Artifact Manifest v0.1**
```yaml
artifact:
  # Идентификация
  id: "art_abc123"
  version: 1

  # Связь с процессом
  trace_id: "trace_xyz"
  step_id: "research"
  created_by: "agent.researcher.001"
  created_at: "2025-12-19T10:00:00Z"

  # Типизация
  artifact_type: "research_report"  # research_report, idea, critique, draft, final
  content_type: "application/json"

  # Расположение
  uri: "file:///artifacts/trace_xyz/research_v1.json"
  size_bytes: 15234
  checksum: "sha256:abc123..."

  # Жизненный цикл
  status: "completed"  # uploading, completed, failed
  retention: "30d"
  supersedes: null  # ID предыдущей версии

  # Безопасность
  owner: "agent.researcher.001"
  visibility: "trace"  # trace (видно всем в процессе), private, public
```

### 4.3. "SQLite — спорно из-за конкуренции"

**Проблема:** Если несколько агентов параллельно пишут → блокировки SQLite.

**Ответ:** Storage Service — единственный writer. Агенты не пишут в БД напрямую, они отправляют команды, которые Storage Service обрабатывает последовательно.

**Но:** Если Storage Service станет узким местом → переход на PostgreSQL.

### 4.4. "Storage Service — Single Point of Failure"

**Проблема:** Если Storage Service упал — вся система блокируется.

**Решение:**
1. Healthcheck и автоматический перезапуск
2. Агенты буферизуют результаты локально при недоступности
3. Retry с exponential backoff
4. Graceful degradation: процесс продолжается, результаты сохраняются позже

### 4.5. "Нужна базовая Security/ACL"

**Проблема:** Кто может читать/писать артефакты?

**Минимальная модель для MVP:**
- `owner` — кто создал артефакт
- `visibility: trace` — видно всем участникам того же trace_id
- `visibility: private` — видно только владельцу
- `visibility: public` — видно всем

---

## 5. Итоговое решение

### 5.1. Трёхуровневая архитектура хранения

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

### 5.2. Архитектурная диаграмма

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Researcher  │  │   Critic     │  │  Orchestrator│
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       │ 1. Сохранить    │                 │
       │    файл         │                 │
       ▼                 │                 │
┌──────────────┐         │                 │
│ File Storage │ ←───────┼─────────────────┤
│   (fsspec)   │         │                 │
└──────┬───────┘         │                 │
       │ uri             │                 │
       ▼                 ▼                 ▼
┌─────────────────────────────────────────────────┐
│                    MindBus                       │
│      (только метаданные и указатели!)            │
└─────────────────────────┬───────────────────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Storage Service │
                 │  (Metadata)     │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │     SQLite      │
                 │  (Artifact      │
                 │   Manifests)    │
                 └─────────────────┘
```

### 5.3. Выбранные технологии

| Компонент | MVP | Production | Почему |
|-----------|-----|------------|--------|
| Agent State | LangGraph SqliteSaver | LangGraph PostgresSaver | Уже интегрирован |
| Process State | SQLite + SQLAlchemy | PostgreSQL + SQLAlchemy | Zero-config → масштабируемость |
| File Storage | Локальная ФС через fsspec | MinIO через fsspec | Один API, смена бэкенда без кода |
| Metadata | SQLite + SQLAlchemy | PostgreSQL + SQLAlchemy | ACID, миграция одной строкой |
| API | MindBus (AMQP) | MindBus (AMQP) | Единообразие с остальной системой |

### 5.4. Что НЕ используем и почему

| Технология | Причина отказа |
|------------|----------------|
| MLflow | Overkill, другая модель данных (ML vs Agents), требует отдельного сервера |
| Redis | Не нужен (агенты не требуют микросекундных задержек) |
| MongoDB | PostgreSQL JSONB даёт ту же гибкость |
| Прямой SQL в агентах | Нарушает изоляцию, связывает агентов с бэкендом |

---

## 6. План реализации

### 6.1. Что нужно сделать

1. **Написать STORAGE_SPEC_v1.0.md** (SSOT)
   - Artifact Manifest схема (Pydantic)
   - API Storage Service (actions, params, results)
   - Интеграция с MESSAGE_FORMAT
   - Поведение при деградации

2. **Интегрировать LangGraph Checkpointer**
   - Добавить SqliteSaver в CreativeAgent
   - Настроить thread_id = trace_id

3. **Реализовать Storage Service**
   - Модели SQLAlchemy для Artifact Manifest
   - fsspec интеграция для файлов
   - Handlers для MindBus команд

4. **Обновить агентов**
   - Использовать fsspec для сохранения файлов
   - Отправлять register_artifact через MindBus

### 6.2. Оценка трудозатрат

| Задача | Оценка |
|--------|--------|
| STORAGE_SPEC_v1.0.md | 2-3 часа |
| LangGraph Checkpointer интеграция | 1-2 часа |
| Storage Service (SQLAlchemy + fsspec) | 4-6 часов |
| Обновление агентов | 2-3 часа |
| Тесты | 3-4 часа |
| **Итого** | **12-18 часов** |

---

## 7. Оценка по критериям проекта

| Критерий | Оценка | Обоснование |
|----------|--------|-------------|
| **Соответствие принципам** | 9/10 | SSOT (Artifact Manifest), Zero Hardcoding (конфиг бэкенда), Ready-Made (LangGraph, fsspec, SQLAlchemy) |
| **Гармония с архитектурой** | 9/10 | Storage Service как участник MindBus, три уровня хранения с чётким разделением |
| **Простота и надёжность** | 8/10 | SQLite = zero-config, fsspec = абстракция, LangGraph = встроенный checkpointing |
| **Эффективность** | 8/10 | Pointer not payload, файлы не через шину, локальный SQLite быстрый |
| **Ready-Made Solutions** | 9/10 | langgraph-checkpoint, fsspec, SQLAlchemy — всё готовое |
| **Общая оценка** | **8.6/10** | ✅ Готово к реализации |

---

## 8. Открытые вопросы для обсуждения

1. **Presigned URLs или прямой доступ к файлам?**
   - Presigned URLs: агент получает временную ссылку через MindBus, загружает напрямую
   - Прямой доступ: агент сам пишет через fsspec
   - Рекомендация: прямой доступ для MVP (проще)

2. **Где хранить SQLite файл?**
   - `data/storage.db` — рядом с кодом
   - Или в конфиге?

3. **Retention policy?**
   - Как долго хранить артефакты?
   - Автоматическое удаление или ручное?

4. **Нужен ли Vector Storage для semantic search?**
   - Для MVP: нет (поиск по метаданным достаточен)
   - Для future: ChromaDB или FAISS

---

## 9. Источники

### Документация
- [MLflow Artifact Store](https://mlflow.org/docs/3.5.1/self-hosting/architecture/artifact-store/)
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [langgraph-checkpoint PyPI](https://pypi.org/project/langgraph-checkpoint/)
- [fsspec Documentation](https://filesystem-spec.readthedocs.io/)

### Сравнительные обзоры
- [ZenML: MLflow Alternatives](https://www.zenml.io/blog/mlflow-alternatives)
- [Neptune: Best MLflow Alternatives](https://neptune.ai/blog/best-mlflow-alternatives)

### Стандарты
- [OCI Artifact Manifest](https://github.com/oras-project/artifacts-spec/blob/main/artifact-manifest.md)
- [ML Metadata (TensorFlow)](https://www.tensorflow.org/tfx/guide/mlmd)

---

## 10. Обратная связь коллег (Раунд 2)

После первоначального обсуждения коллеги предоставили дополнительные критические замечания.

### 10.1. Коллега 1: Транзакционность и контракты

**Проблема 1: Два "источника правды" без строгого контракта**
> "Файловое хранилище и метаданные могут разойтись. Если файл записался, а метаданные нет — система в inconsistent state."

**Решение:** Транзакционный протокол с чётким "commit point":
```
1. Agent → upload(file) → Storage (файл ещё НЕ видим)
2. Agent → register(artifact_manifest) → Storage Service
3. Storage Service: validate(file_exists + checksum_match)
4. Storage Service: INSERT INTO artifacts → COMMIT POINT
5. Storage Service → "artifact_registered" → Agent

Если шаг 3 или 4 падает → файл удаляется, агенту возвращается ошибка
```

**Проблема 2: Нужны правила retry**
> "Что делать если register упал? Повторять upload? Только register?"

**Решение:** Idempotency by artifact_id + checksum:
- Если артефакт с таким ID и checksum уже есть → "already_exists" (OK)
- Если ID есть, но checksum другой → ошибка "conflict"
- Если ID нет → нормальная регистрация

**Проблема 3: SQLite single-writer — архитектурный инвариант**
> "Если это ограничение, оно должно быть явно задокументировано как архитектурное решение."

**Решение:** Добавить в STORAGE_SPEC:
```yaml
architectural_invariants:
  - name: "Single Writer Pattern"
    description: "Only Storage Service writes to SQLite. Agents NEVER access DB directly."
    reason: "SQLite single-writer limitation + separation of concerns"
    enforcement: "Code review, no DB credentials for agents"
```

**Проблема 4: Artifact Manifest должен быть immutable-first**
> "Запретить изменение metadata после создания. Для 'исправлений' — новая версия."

**Решение:**
- `status`: может измениться `uploading → completed` (один раз)
- Все остальные поля: immutable
- Для изменений: создать новую версию с `supersedes: old_id`

**Проблема 5: Где проверять ACL?**
> "visibility: trace — кто проверяет? Storage Service или каждый агент?"

**Решение:** Storage Service — единственное место проверки ACL:
```python
def get_artifact(artifact_id, requester_id, requester_trace_id):
    artifact = db.get(artifact_id)

    if artifact.visibility == "private":
        assert requester_id == artifact.owner
    elif artifact.visibility == "trace":
        assert requester_trace_id == artifact.trace_id
    # public — всегда OK
```

**Проблема 6: Прямой fsspec доступ vs presigned URLs**
> "Для MVP ОК, но отметить что это временное решение. В production — presigned URLs для security."

**Решение:** Добавить в документ:
```yaml
mvp_limitations:
  - "Direct fsspec access (no presigned URLs)"
  - "File-level ACL not enforced at storage layer"
  - "Production: switch to presigned URLs with expiration"
```

### 10.2. Коллега 2: Метаданные и Garbage Collection

**Проблема 1: Нужно поле `context` для AI-специфичных метаданных**
> "Артефакт создан LLM — важно знать prompt_version, model_name, temperature, etc."

**Решение:** Добавить в Artifact Manifest:
```yaml
artifact:
  # ... existing fields ...

  context:  # NEW
    prompt_version: "1.2.0"
    model_name: "gpt-4o-mini"
    model_params:
      temperature: 0.7
      max_tokens: 4000
    input_artifacts:
      - "art_research_001"  # зависимости
    execution_time_ms: 3500
```

**Проблема 2: Где хранить SQLite?**
> "Рекомендую `.data/storage.db` — не в корне, не в `data/`, а в `.data/` (скрытая папка, не попадает в git случайно)."

**Решение:** Принято. Добавить в конфиг:
```yaml
storage_service:
  database:
    path: ".data/storage.db"
    # легко переопределить через env: STORAGE_DB_PATH
```

**Проблема 3: Retention policy для MVP**
> "Для MVP: infinite (не удалять). Явно задокументировать что GC не реализован."

**Решение:**
```yaml
retention:
  mvp: "infinite"  # No auto-deletion
  future: "configurable per artifact_type"

garbage_collection:
  mvp: "manual only"
  future: "background job"
```

**Проблема 4: Нужна sequence diagram для error handling**
> "Покажи что происходит когда Storage Service недоступен."

**Решение:** Добавить диаграмму:
```
Agent                   Storage           Storage Service
  |                       |                      |
  |--1. upload(file)----->|                      |
  |<--OK + uri------------|                      |
  |                       |                      |
  |--2. register(uri)-------------------------->|
  |                       |                      X (SERVICE DOWN)
  |<--ERROR: service_unavailable----------------|
  |                       |                      |
  |--3. RETRY (exp backoff)-------------------->|
  |                       |                      |
  |                       |                      ✓ (SERVICE UP)
  |<--OK: artifact_registered-------------------|

После N retries:
  - Agent сохраняет артефакт в local buffer
  - Продолжает работу (graceful degradation)
  - Retry регистрации при следующем heartbeat
```

**Проблема 5: Garbage Collection для orphaned файлов**
> "Файл загружен, но register не вызван → orphan. Нужен механизм очистки."

**Решение:**
```yaml
garbage_collection:
  orphan_detection:
    - "Files older than 24h without manifest entry"
    - "Run daily (cron or background job)"
    - "MVP: manual script, not automated"

  orphan_handling:
    - "Move to .data/orphans/ (not delete immediately)"
    - "Keep for 7 days, then delete"
    - "Log for debugging"
```

---

## 11. Обновлённый Artifact Manifest v0.2

С учётом обратной связи:

```yaml
artifact:
  # === Идентификация ===
  id: "art_abc123"                    # Уникальный ID
  version: 1                          # Версия артефакта
  supersedes: null                    # ID предыдущей версии (для изменений)

  # === Связь с процессом ===
  trace_id: "trace_xyz"
  step_id: "research"
  created_by: "agent.researcher.001"
  created_at: "2025-12-19T10:00:00Z"

  # === Типизация ===
  artifact_type: "research_report"
  content_type: "application/json"

  # === Расположение ===
  uri: "file:///.data/artifacts/trace_xyz/research_v1.json"
  size_bytes: 15234
  checksum: "sha256:abc123..."

  # === Жизненный цикл ===
  status: "completed"                 # uploading → completed (one-way)
  retention: "infinite"               # MVP: no auto-deletion

  # === Безопасность ===
  owner: "agent.researcher.001"
  visibility: "trace"                 # trace | private | public

  # === AI Context (NEW) ===
  context:
    prompt_version: "1.2.0"
    model_name: "gpt-4o-mini"
    model_params:
      temperature: 0.7
      max_tokens: 4000
    input_artifacts:                  # Dependencies
      - "art_previous_001"
    execution_time_ms: 3500
```

**Правила immutability:**
- `status`: можно изменить `uploading → completed` (один раз)
- Все остальные поля: **IMMUTABLE после создания**
- Для "исправления" артефакта: создать новый с `supersedes: old_id`

---

## 12. Обновлённые требования для STORAGE_SPEC

После обсуждения добавить в спецификацию:

### 12.1. Транзакционный протокол

```yaml
storage_operations:
  upload_and_register:
    steps:
      1: "upload(file) → temporary storage"
      2: "register(manifest) → Storage Service"
      3: "Storage Service: validate(file_exists, checksum_match)"
      4: "Storage Service: INSERT manifest → COMMIT"
      5: "move file from temp → permanent location"
      6: "return: artifact_registered"

    on_failure:
      step_3_4: "delete temp file, return error"
      step_5: "rollback INSERT, delete temp file, return error"
```

### 12.2. Idempotency

```yaml
idempotency:
  by: "artifact_id + checksum"

  scenarios:
    same_id_same_checksum: "return: already_exists (OK)"
    same_id_diff_checksum: "return: conflict_error"
    new_id: "normal registration"
```

### 12.3. Degradation Behavior

```yaml
degradation:
  storage_service_down:
    agent_behavior:
      - "Retry with exponential backoff (max 3 attempts)"
      - "Buffer artifact locally (.data/buffer/)"
      - "Continue execution (graceful degradation)"
      - "Retry registration on next heartbeat"

    orchestrator_behavior:
      - "Mark step as 'pending_storage'"
      - "Don't block process if non-critical"
      - "Alert if critical artifact missing"
```

### 12.4. Архитектурные инварианты

```yaml
architectural_invariants:
  single_writer:
    description: "Only Storage Service writes to SQLite"
    enforcement: "Code review, no DB credentials for agents"

  acl_enforcement:
    description: "Storage Service is the ONLY ACL checkpoint"
    enforcement: "All reads go through get_artifact()"

  immutable_manifests:
    description: "Artifact metadata immutable after creation"
    exception: "status: uploading → completed"
```

### 12.5. MVP Limitations

```yaml
mvp_limitations:
  documented:
    - "Direct fsspec access (no presigned URLs)"
    - "File-level ACL not enforced at storage layer"
    - "No automated garbage collection"
    - "SQLite single-writer constraint"
    - "Infinite retention (no auto-deletion)"

  production_upgrade:
    - "Presigned URLs with expiration"
    - "PostgreSQL for metadata"
    - "MinIO for files"
    - "Automated GC with configurable retention"
```

---

## 13. Итоговая оценка (обновлённая)

| Критерий | Оценка | Изменение | Обоснование |
|----------|--------|-----------|-------------|
| **Соответствие принципам** | 9/10 | — | SSOT (Artifact Manifest v0.2), Zero Hardcoding, Ready-Made |
| **Гармония с архитектурой** | 9/10 | — | Storage Service как участник MindBus |
| **Простота и надёжность** | 9/10 | ↑ | Транзакционный протокол, idempotency, degradation rules |
| **Эффективность** | 8/10 | — | Pointer not payload, локальный SQLite |
| **Ready-Made Solutions** | 9/10 | — | langgraph-checkpoint, fsspec, SQLAlchemy |
| **Общая оценка** | **8.8/10** | ↑ | Учтены все критические замечания |

---

## 14. Финальная экспертная оценка (Раунд 3)

### 14.1. Вердикт экспертов

> **"Это уже не 'поиск идей', а почти готовый дизайн для SSOT-спеки."**

Архитектура признана **зрелой и готовой к реализации**. Оценка: **8.5–9/10**.

### 14.2. Подтверждённые сильные стороны

| Решение | Почему правильно |
|---------|------------------|
| **Storage Service как участник MindBus** | Убирает связанность агентов с БД/ФС, позволяет менять бэкенды |
| **"Pointer, not Payload"** | Избежали будущего краша системы от перегрузки RabbitMQ |
| **Трёхуровневая модель** | Разделение по природе данных, а не "одна БД на всё" |
| **Artifact Manifest + immutability** | Воспроизводимость, дебаг, time-travel |
| **Честные MVP-ограничения** | Признак зрелости: документируем, не маскируем |

### 14.3. Ключевые точки для STORAGE_SPEC

Эксперты выделили три **обязательных инварианта** для спецификации:

#### 1. Транзакционный протокол как SSOT-инвариант

> **"В какой момент артефакт считается сохранённым?"**

Ответ: **Commit Point = INSERT в SQLite после валидации файла**.

```yaml
# MUST be in STORAGE_SPEC_v1.0.md
invariant:
  name: "Artifact Commit Point"
  definition: "Artifact exists IFF manifest record in SQLite is committed"
  consequence: "File without manifest = orphan (GC candidate)"
```

#### 2. Immutability как обязательное правило

```yaml
invariant:
  name: "Artifact Immutability"
  definition: "Manifest fields immutable after creation (except status)"
  consequence: "For corrections → create new version with supersedes"
```

#### 3. Единая политика деградации

> **"Поведение при деградации должно быть одинаковым у всех агентов"**

```yaml
invariant:
  name: "Uniform Degradation Policy"
  definition: "All agents follow same retry/buffer/continue behavior"
  enforcement: "Shared library, not per-agent implementation"
```

### 14.4. Ценность поля `context`

Эксперты особо отметили добавление AI-контекста:

| Поле | Ценность |
|------|----------|
| `prompt_version` | Понять, почему агент стал работать хуже после обновления |
| `model_name` | Считать стоимость, сравнивать качество между LLM |
| `execution_time_ms` | Искать "узкие места" (Performance Bottlenecks) |
| `input_artifacts` | Граф зависимостей для воспроизводимости |

### 14.5. Graceful Degradation — страховка инвестиций

> **"ИИ-агенты работают долго. Будет катастрофой, если агент потратил 3 минуты и 5$ на токены, а потом всё удалил из-за моргнувшей БД."**

Локальный буфер (`.data/buffer/`) — страховка инвестиций в токены.

### 14.6. Визуализация итоговой иерархии

```
┌─────────────────────────────────────────────────────────────┐
│                    ИЕРАРХИЯ ХРАНЕНИЯ                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  AGENT STATE (LangGraph)                                    │
│  └── Внутренние мысли агента (Memory)                       │
│      • Итерации самокритики                                 │
│      • Промежуточные состояния графа                        │
│                                                             │
│  PROCESS STATE (SQLAlchemy)                                 │
│  └── План работ (To-Do List)                                │
│      • Какой шаг выполнен                                   │
│      • Статус процесса                                      │
│                                                             │
│  ARTIFACTS (fsspec + SQLite)                                │
│  └── Результаты работы (Portfolio)                          │
│      • Исследования, идеи, тексты                           │
│      • Версионирование через supersedes                     │
│      • AI-контекст для воспроизводимости                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 15. Заключение

### 15.1. Статус документа

| Аспект | Статус |
|--------|--------|
| Архитектурное решение | ✅ **УТВЕРЖДЕНО** |
| Технологии | ✅ **ВЫБРАНЫ** (LangGraph, fsspec, SQLAlchemy) |
| Паттерны | ✅ **ОПРЕДЕЛЕНЫ** (Pointer not Payload, Commit Point, Immutability) |
| Инварианты | ✅ **СФОРМУЛИРОВАНЫ** |
| MVP-ограничения | ✅ **ЗАДОКУМЕНТИРОВАНЫ** |

### 15.2. Финальная оценка

| Критерий | Оценка |
|----------|--------|
| Соответствие принципам проекта | 9/10 |
| Гармония с архитектурой | 9/10 |
| Простота и надёжность | 9/10 |
| Эффективность | 8/10 |
| Ready-Made Solutions | 9/10 |
| **Общая оценка** | **8.8/10** |

### 15.3. Следующие шаги

1. **STORAGE_SPEC_v1.0.md** — формальная SSOT-спецификация
   - Pydantic-схемы для Artifact Manifest v0.2
   - SQLAlchemy-модель для таблицы `artifacts`
   - API Storage Service (actions, params, results)
   - Retry-логика (tenacity)

2. **Реализация** — согласно плану из §6

---

**Статус:** ✅ АРХИТЕКТУРА УТВЕРЖДЕНА
**Следующий шаг:** Создание STORAGE_SPEC_v1.0.md

---

*Документ подготовлен: 2025-12-19*
*Автор: Claude Code (Opus 4.5)*
*Финальное обновление: 2025-12-19 (Экспертная оценка, Раунд 3)*
