# AGENT ARCHITECTURE — Draft v0.4

**Статус**: ⚠️ АРХИВНЫЙ ЧЕРНОВИК — перенесено в SSOT
**Дата**: 2025-12-17
**Версия**: 0.4

> **ВАЖНО**: Этот документ был основой для создания официальной спецификации.
> Актуальная версия: **[docs/SSOT/AGENT_SPEC_v1.0.md](../SSOT/AGENT_SPEC_v1.0.md)**

---

**Цель документа**: Исторический черновик с идеями и концепциями

---

## 1. Что такое Агент в AI_TEAM

**Агент** — это автономный AI-сотрудник, который:
- Получает задачи от Orchestrator
- Самостоятельно решает КАК их выполнить
- Использует свои инструменты и знания
- Возвращает результат

**Метафора**: Агент = Сотрудник компании
- Orchestrator говорит "подготовь отчёт по продажам"
- Агент сам решает: открыть Excel, сделать запрос в базу, построить графики

---

## 2. Анатомия агента

```
┌─────────────────────────────────────────────────────────────┐
│                         АГЕНТ                                │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                    МОЗГ (Brain)                         │ │
│  │                                                         │ │
│  │  LLM: GPT-4 / Claude / Llama / Mistral                 │ │
│  │                                                         │ │
│  │  Отвечает за:                                          │ │
│  │  • Понимание задачи                                    │ │
│  │  • Планирование действий                               │ │
│  │  • Выбор инструментов                                  │ │
│  │  • Генерация результата                                │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │               ИНСТРУМЕНТЫ (Tools)                       │ │
│  │                                                         │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │ │
│  │  │Web Search│ │File I/O  │ │Code Exec │ │ API Call │  │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │ │
│  │  │Calculator│ │ Database │ │  Email   │ │  Custom  │  │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │ │
│  │                                                         │ │
│  │  Агент САМ выбирает какой инструмент использовать      │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                  ПАМЯТЬ (Memory)                        │ │
│  │                                                         │ │
│  │  ┌─────────────────────┐  ┌─────────────────────────┐  │ │
│  │  │   КРАТКОСРОЧНАЯ     │  │     ДОЛГОСРОЧНАЯ        │  │ │
│  │  │                     │  │                         │  │ │
│  │  │ • Контекст задачи   │  │ • Опыт прошлых задач    │  │ │
│  │  │ • История диалога   │  │ • Знания о проекте      │  │ │
│  │  │ • Промежуточные     │  │ • Предпочтения стиля    │  │ │
│  │  │   результаты        │  │ • Паттерны решений      │  │ │
│  │  │                     │  │                         │  │ │
│  │  │ Реализация:         │  │ Реализация:             │  │ │
│  │  │ Контекст LLM        │  │ Vector DB (Chroma)      │  │ │
│  │  └─────────────────────┘  └─────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              УМЕНИЯ (Capabilities)                      │ │
│  │                                                         │ │
│  │  Мозг + Инструменты + Память = Умения                  │ │
│  │                                                         │ │
│  │  Примеры:                                              │ │
│  │  • write_article (написать статью)                     │ │
│  │  • research_topic (исследовать тему)                   │ │
│  │  • review_code (проверить код)                         │ │
│  │  • analyze_data (проанализировать данные)              │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Типы агентов

### 3.1. Специализированные агенты (основной тип)

Как врачи-специалисты — глубокая экспертиза в узкой области.

| Агент | Специализация | Инструменты | Умения |
|-------|---------------|-------------|--------|
| **WriterAgent** | Создание текстов | — | write_article, write_post, improve_text |
| **ResearcherAgent** | Исследования | Web Search, Database | research_topic, find_sources, summarize |
| **DeveloperAgent** | Код | Code Exec, File I/O | write_code, review_code, fix_bugs |
| **AnalystAgent** | Анализ данных | Database, Calculator | analyze_data, build_report, find_insights |
| **CriticAgent** | Оценка качества | — | review_text, score_quality, give_feedback |
| **DesignerAgent** | Визуал | Image Gen API | create_image, design_layout |

### 3.2. Универсальный агент (терапевт)

Знает понемногу обо всём. Используется когда:
- Задача не требует глубокой экспертизы
- Нужен быстрый ответ на простой вопрос
- Специализированный агент недоступен

| Агент | Специализация | Инструменты |
|-------|---------------|-------------|
| **GeneralAgent** | Всё понемногу | Web Search, Calculator |

---

## 4. Компоненты агента (детально)

### 4.1. Мозг (Brain)

**Что это**: LLM который "думает" за агента.

**Конфигурация**:
```yaml
brain:
  provider: "openai"           # openai, anthropic, local
  model: "gpt-4o"              # Конкретная модель
  temperature: 0.7             # Креативность (0.0 - 1.0)
  max_tokens: 4000             # Лимит ответа

  # System prompt — "личность" агента
  system_prompt: |
    Ты — профессиональный копирайтер с 10-летним опытом.
    Твой стиль: ясный, убедительный, без воды.
    Всегда структурируй текст с заголовками.
```

**Вопрос для обсуждения**:
- Один LLM на всех агентов или разные модели для разных задач?
- GPT-4 для сложных задач, GPT-4o-mini для простых?

---

### 4.2. Инструменты (Tools)

**Что это**: Функции которые агент может вызывать для взаимодействия с миром.

**Стандартные инструменты**:

| Инструмент | Описание | Пример использования |
|------------|----------|---------------------|
| `web_search` | Поиск в интернете | Найти последние новости |
| `web_fetch` | Загрузить страницу | Прочитать статью по URL |
| `file_read` | Прочитать файл | Загрузить данные |
| `file_write` | Записать файл | Сохранить результат |
| `code_execute` | Выполнить код | Запустить Python скрипт |
| `database_query` | Запрос к БД | SELECT * FROM ... |
| `api_call` | HTTP запрос | Вызвать внешний API |
| `calculator` | Вычисления | Посчитать статистику |

**Как агент выбирает инструмент**:
```
Задача: "Найди последние новости про Tesla и сделай резюме"

Агент думает (Chain of Thought):
1. Мне нужны свежие новости → инструмент web_search
2. Вызываю: web_search("Tesla news December 2025")
3. Получил 10 результатов
4. Теперь генерирую резюме на основе найденного
```

**Технология**: OpenAI Function Calling / Anthropic Tool Use

**Вопросы для обсуждения**:
- Какие инструменты обязательны для всех агентов?
- Как ограничить опасные инструменты (delete_file, api_call)?

---

### 4.3. Память (Memory)

#### Краткосрочная память

**Что хранит**: Контекст текущей задачи
**Время жизни**: Пока задача выполняется
**Реализация**: Контекст LLM (messages)

```python
# Пример краткосрочной памяти
context = {
    "task": "Написать статью про AI",
    "step": 2,
    "previous_results": {
        "research": "Найдено 5 источников...",
        "outline": "1. Введение, 2. Тренды..."
    }
}
```

#### Долгосрочная память

**Что хранит**: Опыт, знания, паттерны
**Время жизни**: Постоянно
**Реализация**: Vector Database (Chroma, Pinecone)

**Как работает**:
```
1. Агент выполнил задачу
2. Результат + контекст сохраняется в Vector DB
3. При новой похожей задаче — агент "вспоминает" как делал раньше
4. Использует прошлый опыт для улучшения результата
```

**Что сохранять в долгосрочную память**:
- Успешные решения задач
- Обратная связь от пользователя
- Стиль и предпочтения
- Ошибки (чтобы не повторять)

**Вопросы для обсуждения**:
- Общая память на всех агентов или у каждого своя?
- Как "забывать" устаревшую информацию?
- MVP без долгосрочной памяти — ок?

---

### 4.4. Умения (Capabilities)

**Что это**: Действия которые агент умеет выполнять.

**Capability = Мозг + Инструменты + Промпт**

**Пример для WriterAgent**:

```yaml
capabilities:
  - name: "write_article"
    description: "Написать статью на заданную тему"
    parameters:
      topic: string          # О чём писать
      style: string          # Стиль (formal, casual, technical)
      length: integer        # Количество слов
      audience: string       # Целевая аудитория
    tools_used:
      - web_search           # Для исследования темы (опционально)
    output:
      type: "text"
      format: "markdown"

  - name: "improve_text"
    description: "Улучшить существующий текст"
    parameters:
      text: string           # Исходный текст
      feedback: string       # Что улучшить
    output:
      type: "text"

  - name: "review_text"
    description: "Проверить текст и дать оценку"
    parameters:
      text: string
      criteria: array        # По каким критериям оценивать
    output:
      type: "object"
      schema:
        score: integer       # 1-10
        feedback: string
        suggestions: array
```

---

## 5. Жизненный цикл агента

```
┌─────────────────────────────────────────────────────────────┐
│                    ЖИЗНЕННЫЙ ЦИКЛ                            │
│                                                              │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐            │
│  │  INIT    │ ──► │ REGISTER │ ──► │  READY   │◄─────┐     │
│  │          │     │          │     │          │      │     │
│  │Load      │     │Send      │     │Wait for  │      │     │
│  │config    │     │passport  │     │commands  │      │     │
│  │Init LLM  │     │to        │     │          │      │     │
│  │Load tools│     │Registry  │     │          │      │     │
│  └──────────┘     └──────────┘     └────┬─────┘      │     │
│                                         │            │     │
│                                         ▼            │     │
│                                    ┌──────────┐      │     │
│                                    │ WORKING  │      │     │
│                                    │          │      │     │
│                                    │Execute   │      │     │
│                                    │task      │──────┘     │
│                                    │Send      │            │
│                                    │result    │            │
│                                    └──────────┘            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Взаимодействие с Orchestrator

```
Orchestrator                              Agent
     │                                      │
     │  COMMAND: write_article              │
     │  params: {topic: "AI trends"}        │
     │ ─────────────────────────────────►   │
     │                                      │
     │                            ┌─────────┴─────────┐
     │                            │ 1. Понять задачу  │
     │                            │ 2. Нужен поиск?   │
     │                            │    → web_search() │
     │                            │ 3. Генерировать   │
     │                            │    текст          │
     │                            └─────────┬─────────┘
     │                                      │
     │  RESULT: {text: "...", score: 8}     │
     │ ◄─────────────────────────────────   │
     │                                      │
```

**Принцип разделения**:
- **Orchestrator**: ЧТО делать (write_article)
- **Agent**: КАК делать (выбор инструментов, планирование шагов)

---

## 7. Конфигурация агента

```yaml
# config/agents/writer_agent.yaml

writer_agent:
  name: "writer_agent"
  type: "specialist"
  version: "1.0.0"

  # Мозг
  brain:
    provider: "openai"
    model: "gpt-4o"
    temperature: 0.7
    max_tokens: 4000
    system_prompt: |
      Ты — профессиональный копирайтер.
      Пишешь ясно, убедительно, структурированно.

  # Инструменты
  tools:
    - web_search        # Поиск информации
    - web_fetch         # Загрузка страниц

  # Умения
  capabilities:
    - write_article
    - write_post
    - improve_text
    - review_text

  # Память
  memory:
    short_term:
      enabled: true
      max_context_tokens: 8000
    long_term:
      enabled: false     # MVP: отключено
      provider: "chroma"
      collection: "writer_memory"

  # Лимиты
  limits:
    max_tool_calls: 10          # Макс вызовов инструментов за задачу
    max_execution_time: 300     # 5 минут на задачу
    max_retries: 3

  # Регистрация в Registry
  registry:
    enabled: true
    heartbeat_interval_seconds: 10
```

---

## 8. Эволюционный план

| Версия | Что реализуем | Память | Инструменты |
|--------|--------------|--------|-------------|
| **v0.1 MVP** | WriterAgent с базовыми capabilities | Только краткосрочная | Нет (только LLM) |
| **v0.2** | + CriticAgent, + Tool Use | Краткосрочная | web_search |
| **v0.3** | + Долгосрочная память | + Vector DB (Chroma) | + file_read/write |
| **v0.4** | + ResearcherAgent, AnalystAgent | Полная | + database_query |
| **v1.0** | Полноценная система агентов | RAG + эпизодическая | Полный набор |

---

## 9. Вопросы для обсуждения

### 9.1. Архитектурные вопросы

1. **Автономность агента**: Насколько агент должен быть самостоятельным?
   - Вариант A: Агент полностью автономен (сам планирует, сам выбирает инструменты)
   - Вариант B: Orchestrator даёт hints какие инструменты использовать
   - **Предложение**: Вариант A — агент автономен в рамках своих capabilities

2. **Память**: Общая или раздельная?
   - Вариант A: У каждого агента своя память
   - Вариант B: Общая память на всех (shared knowledge)
   - **Предложение**: Гибридный подход — личная + общая

3. **Мультимодальность**: Нужны ли агенты для картинок/видео?
   - MVP: только текст
   - v1.0+: DesignerAgent с image generation

### 9.2. Технические вопросы

4. **Какой Vector DB использовать для долгосрочной памяти?**
   - Chroma — простой, open-source, хорош для MVP
   - Pinecone — managed, масштабируемый
   - FAISS — быстрый, но требует self-hosting
   - **Предложение**: Chroma для MVP

5. **Как реализовать Tool Use?**
   - OpenAI Function Calling — проверенный стандарт
   - LangChain Tools — больше абстракций
   - Custom implementation — полный контроль
   - **Предложение**: OpenAI Function Calling (или Anthropic Tool Use)

6. **Fallback при недоступности LLM?**
   - Retry с exponential backoff
   - Fallback на альтернативную модель (GPT-4 → Claude)
   - **Предложение**: Retry + optional fallback

### 9.3. Бизнес-вопросы

7. **Какие агенты нужны в первую очередь?**
   - WriterAgent — генерация контента
   - CriticAgent — оценка качества
   - ResearcherAgent — поиск информации
   - **Предложение**: WriterAgent → CriticAgent → ResearcherAgent

8. **Как измерять качество работы агента?**
   - Оценка от CriticAgent
   - Обратная связь от пользователя
   - Метрики: время выполнения, количество retry
   - **Предложение**: Все три + агрегация в метриках

---

## 10. Связь с существующими SSOT

| SSOT | Связь с агентами |
|------|------------------|
| **NODE_PASSPORT** | Агент создаёт свой паспорт с capabilities |
| **NODE_REGISTRY** | Orchestrator ищет агентов по capabilities |
| **MESSAGE_FORMAT** | Агент получает COMMAND, отправляет RESULT/ERROR |
| **PROCESS_CARD** | Определяет какие capabilities нужны для шагов |
| **ORCHESTRATOR_SPEC** | Orchestrator выбирает агента и отправляет задачи |

---

## 11. SSOT Compliance — Явные контракты

> **Принцип**: Агент НЕ изобретает собственные форматы данных. Агент ИСПОЛЬЗУЕТ существующие SSOT.

### 11.1. Контракт с MESSAGE_FORMAT_v1.1

**Агент получает**: CloudEvents сообщение типа `ai.team.command`
```json
{
  "specversion": "1.0",
  "type": "ai.team.command",
  "source": "orchestrator-core",
  "id": "cmd-uuid-123",
  "time": "2025-12-17T12:00:00Z",
  "subject": "task-uuid-456",
  "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",

  "data": {
    "action": "write_article",
    "params": {
      "topic": "AI trends",
      "style": "formal"
    },
    "timeout_seconds": 300
  }
}
```

**Агент отправляет**: CloudEvents сообщение типа `ai.team.result` (успех) или `ai.team.error` (ошибка)
```json
{
  "specversion": "1.0",
  "type": "ai.team.result",
  "source": "agent.writer.001",
  "id": "result-uuid-789",
  "time": "2025-12-17T12:05:00Z",
  "subject": "task-uuid-456",

  "data": {
    "status": "SUCCESS",
    "output": { "text": "...", "word_count": 2000 },
    "metrics": {
      "llm_calls": 1,
      "execution_time_ms": 3500,
      "tokens_used": 4500
    }
  }
}
```

**ВАЖНО**: Типы сообщений строго по SSOT!
- `ai.team.command` — команда (НЕ `ai_team.command.execute`)
- `ai.team.result` — успешный результат
- `ai.team.error` — ошибка (отдельный тип, не в RESULT!)
- `ai.team.event` — событие
- `ai.team.control` — управление (STOP/PAUSE)

**Ссылка**: [MESSAGE_FORMAT_v1.1.md](../SSOT/MESSAGE_FORMAT_v1.1.md)

---

### 11.2. Контракт с NODE_PASSPORT_SPEC_v1.0

**Агент ОБЯЗАН** создать Node Passport при старте (Kubernetes API Object pattern):

```json
{
  "metadata": {
    "uid": "550e8400-e29b-41d4-a716-446655440000",
    "name": "agent-writer-001",
    "nodeType": "agent",
    "labels": {
      "team": "ai_team",
      "role": "writer",
      "capability.write_article": "true",
      "capability.improve_text": "true"
    },
    "creationTimestamp": "2025-12-17T10:00:00Z",
    "version": "1.0.0"
  },

  "spec": {
    "capabilities": [
      {
        "name": "write_article",
        "version": "1.0.0",
        "inputSchema": {
          "type": "object",
          "properties": {
            "topic": { "type": "string" },
            "style": { "type": "string", "enum": ["formal", "casual"] }
          }
        },
        "outputSchema": {
          "type": "object",
          "properties": {
            "text": { "type": "string" },
            "word_count": { "type": "integer" }
          }
        }
      }
    ],
    "resources": {
      "llmProvider": "openai",
      "llmModel": "gpt-4o",
      "maxConcurrentTasks": 1
    }
  },

  "status": {
    "phase": "Running",
    "conditions": [
      {
        "type": "Ready",
        "status": "True",
        "lastTransitionTime": "2025-12-17T10:00:00Z"
      }
    ],
    "lease": {
      "holderIdentity": "agent-writer-001",
      "renewTime": "2025-12-17T10:05:00Z",
      "leaseDurationSeconds": 30
    }
  }
}
```

**ВАЖНО**: Структура паспорта строго по Kubernetes pattern!
- `metadata.uid` — НЕ `uuid` (Kubernetes naming)
- `status.phase` — НЕ `status.state` (Kubernetes naming)
- `status.conditions` — детальное состояние
- `status.lease` — heartbeat механизм

**Ссылка**: [NODE_PASSPORT_SPEC_v1.0.md](../SSOT/NODE_PASSPORT_SPEC_v1.0.md)

---

### 11.3. Контракт с NODE_REGISTRY_SPEC_v1.0

**Агент ОБЯЗАН** зарегистрироваться в Registry при старте.

#### Способ регистрации: API (не Events!)

**ВАЖНО**: Регистрация выполняется через **прямой API вызов** к etcd/Consul, а НЕ через MindBus Events.

**Причины выбора API**:
- ✅ **Синхронность**: Агент получает подтверждение "я зарегистрирован" или ошибку
- ✅ **Надёжность**: API даёт гарантию записи в Registry
- ✅ **Heartbeat**: etcd имеет встроенный TTL/Lease механизм
- ✅ **Ready-Made First**: Используем etcd/Consul как задумано их создателями

```python
import etcd3
import json

class AgentRegistration:
    def __init__(self, etcd_host: str = "localhost", etcd_port: int = 2379):
        self.etcd = etcd3.client(host=etcd_host, port=etcd_port)
        self.lease_id = None

    async def register(self, passport: dict, ttl_seconds: int = 30):
        """Регистрация агента в Registry через etcd API"""

        # 1. Создаём Lease с TTL (etcd встроенный heartbeat)
        self.lease_id = self.etcd.lease(ttl=ttl_seconds)

        # 2. Записываем паспорт с привязкой к Lease
        node_uid = passport["metadata"]["uid"]
        self.etcd.put(
            key=f"/ai_team/registry/nodes/{node_uid}",
            value=json.dumps(passport),
            lease=self.lease_id
        )

        # 3. Запускаем фоновое продление Lease
        self._start_lease_keepalive()

        return True  # Синхронное подтверждение!

    def _start_lease_keepalive(self):
        """etcd автоматически продлевает Lease"""
        # etcd3 library делает это автоматически при использовании lease
        pass
```

#### Уведомление через MindBus (опционально)

**После** успешной регистрации через API, агент **может** опубликовать событие для мониторинга:

```python
# ПОСЛЕ успешной регистрации в etcd — уведомляем систему
channel.basic_publish(
    exchange='mindbus.main',
    routing_key='evt.registry.node_registered',  # О ЧЁМ событие (тема)
    body=json.dumps({
        "specversion": "1.0",
        "type": "ai.team.event",
        "source": f"agent.{self.role}.{self.uid}",  # КТО отправил
        "data": {
            "node_uid": self.uid,
            "node_type": "agent",
            "capabilities": ["write_article", "improve_text"]
        }
    })
)
```

**Orchestrator находит агента через etcd API**:
```python
# Orchestrator запрашивает Registry напрямую через etcd
import etcd3

etcd = etcd3.client()
nodes = etcd.get_prefix("/ai_team/registry/nodes/")

# Фильтрация по capability
for value, metadata in nodes:
    passport = json.loads(value)
    if "write_article" in [c["name"] for c in passport["spec"]["capabilities"]]:
        if passport["status"]["phase"] == "Running":
            candidates.append(passport)
```

**Разделение ответственности**:
- **etcd API** → регистрация, heartbeat, поиск узлов (control plane)
- **MindBus Events** → уведомления для мониторинга (data plane, опционально)

**Ссылка**: [NODE_REGISTRY_SPEC_v1.0.md](../SSOT/NODE_REGISTRY_SPEC_v1.0.md)

---

### 11.4. Контракт с MindBus Protocol

**Exchange**: Единый `mindbus.main` (Topic Exchange) — НЕ создаём отдельные exchanges!

**Агент ОБЯЗАН** подписаться на routing keys согласно SSOT:

```python
# Routing keys из MindBus Protocol v1.0:
# - cmd.{role}.{agent_id} — команды
# - ctl.{target}.{scope} — управление (STOP/PAUSE/RESUME)

# Агент создаёт свою очередь
queue_name = f"agent.{self.role}.{self.uid}"
channel.queue_declare(
    queue=queue_name,
    durable=True,
    arguments={'x-max-priority': 255}  # Поддержка приоритетов!
)

# Подписка на команды для своей роли
channel.queue_bind(
    exchange='mindbus.main',
    queue=queue_name,
    routing_key=f'cmd.{self.role}.{self.uid}'  # Личные команды
)
channel.queue_bind(
    exchange='mindbus.main',
    queue=queue_name,
    routing_key=f'cmd.{self.role}.any'  # Команды любому агенту роли
)

# Подписка на CONTROL сигналы
channel.queue_bind(
    exchange='mindbus.main',
    queue=queue_name,
    routing_key='ctl.all.*'  # STOP/PAUSE для всех
)
channel.queue_bind(
    exchange='mindbus.main',
    queue=queue_name,
    routing_key=f'ctl.{self.role}.*'  # STOP/PAUSE для роли
)
```

**Агент отправляет RESULT через reply-to** (RPC pattern):
```python
# AMQP Properties из входящего COMMAND содержат reply_to
# Отправляем результат НАПРЯМУЮ в reply-to queue, НЕ через routing key!
channel.basic_publish(
    exchange='',  # Default exchange для direct reply
    routing_key=properties.reply_to,  # Queue из COMMAND
    properties=pika.BasicProperties(
        correlation_id=properties.correlation_id  # Связь с COMMAND
    ),
    body=json.dumps(result_message)
)
```

**Ссылка**: [mindbus_protocol_v1.md](../SSOT/mindbus_protocol_v1.md)

---

### 11.5. Таблица соответствия

| SSOT | Что агент БЕРЁТ | Что агент ДАЁТ |
|------|-----------------|----------------|
| **MESSAGE_FORMAT** | Структура COMMAND | Структура RESULT/ERROR |
| **NODE_PASSPORT** | Схема паспорта | Свой паспорт с capabilities |
| **NODE_REGISTRY** | API регистрации | Регистрация + heartbeat |
| **MindBus** | Протокол подключения | Сообщения по протоколу |
| **PROCESS_CARD** | — (не напрямую) | Capabilities для шагов |
| **ORCHESTRATOR_SPEC** | Формат команд | Формат ответов |

> **КРИТИЧНО**: Код агента НЕ содержит собственных определений форматов данных. Все структуры импортируются из SSOT!

---

## 12. Ready-Made First — Готовые фреймворки

> **Принцип**: НЕ пишем собственный Agent Loop с нуля. ИСПОЛЬЗУЕМ проверенные решения.

### 12.1. Выбранный стек для агентов

| Компонент | Технология | Почему |
|-----------|-----------|--------|
| **LLM Calls** | **LiteLLM** | Единый интерфейс для всех провайдеров (уже в стеке) |
| **Agent Loop** | **LangGraph** | Stateful workflows, conditional edges, proven |
| **Team Orchestration** | **CrewAI** (опционально) | Если нужна командная работа агентов |
| **Tools** | **LangChain Tools** | Стандартные инструменты из коробки |
| **Memory** | **LangChain Memory** → **Chroma** | Для долгосрочной памяти |

### 12.2. LiteLLM — LLM Calls (уже утверждено)

```python
from litellm import acompletion

# Единый интерфейс для ВСЕХ провайдеров
response = await acompletion(
    model="gpt-4o",           # или "claude-3-opus" или "ollama/llama3"
    messages=[
        {"role": "system", "content": "You are a writer"},
        {"role": "user", "content": "Write about AI"}
    ],
    temperature=0.7
)
```

**Преимущества**:
- ✅ OpenAI, Anthropic, Google, Local — один API
- ✅ Автоматический retry и fallback
- ✅ Подсчёт стоимости из коробки
- ✅ Кеширование через Redis

**Ссылка**: [04_llm_integration.md](../technical/stack/04_llm_integration.md)

### 12.3. LangGraph — Agent Loop (утверждено для MVP)

**Почему LangGraph**:
- ✅ Conditional edges (динамические workflows)
- ✅ State persistence из коробки
- ✅ Визуализация графа
- ✅ Интеграция с LangChain utilities
- ✅ НЕ пишем собственный ReAct цикл

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class AgentState(TypedDict):
    """Состояние агента"""
    task: dict
    thought: str
    action: str
    observation: str
    result: dict
    iteration: int

# Создаём граф агента
workflow = StateGraph(AgentState)

# Узлы
workflow.add_node("think", think_step)      # LLM думает
workflow.add_node("act", action_step)       # Выполняет действие
workflow.add_node("observe", observe_step)  # Наблюдает результат
workflow.add_node("finish", finish_step)    # Формирует ответ

# Логика переходов (ReAct pattern)
def should_continue(state: AgentState) -> str:
    if state["action"] == "FINISH":
        return "finish"
    elif state["iteration"] >= 10:
        return "finish"
    else:
        return "act"

workflow.add_edge("think", should_continue)
workflow.add_edge("act", "observe")
workflow.add_edge("observe", "think")
workflow.add_edge("finish", END)

# Компилируем
agent_app = workflow.compile()
```

**Ссылка**: [archive_2025-12-15/03_agent_framework.md](../technical/stack/archive_2025-12-15/03_agent_framework.md)

### 12.4. CrewAI — Team Orchestration (опционально)

**Когда использовать CrewAI**:
- Несколько агентов работают над ОДНОЙ задачей
- Нужна передача работы между агентами
- Командная динамика (Writer → Critic → Editor)

```python
from crewai import Agent, Task, Crew

# Создаём агентов
writer = Agent(
    role="Writer",
    goal="Write engaging articles",
    backstory="Experienced content writer"
)

critic = Agent(
    role="Critic",
    goal="Review and improve content",
    backstory="Strict quality reviewer"
)

# Создаём задачи
write_task = Task(
    description="Write article about {topic}",
    agent=writer
)

review_task = Task(
    description="Review the article and provide feedback",
    agent=critic
)

# Собираем команду
crew = Crew(
    agents=[writer, critic],
    tasks=[write_task, review_task],
    process="sequential"  # или "hierarchical"
)

# Запускаем
result = crew.kickoff(inputs={"topic": "AI trends"})
```

**LEGO-принцип**: CrewAI агенты можно использовать внутри LangGraph графа!

### 12.5. Эволюционный путь

| Фаза | Agent Loop | Team Work | LLM Calls |
|------|-----------|-----------|-----------|
| **MVP (v0.1)** | LangGraph (basic) | — | LiteLLM |
| **v0.2-0.3** | LangGraph (full) | — | LiteLLM |
| **v0.4+** | LangGraph | + CrewAI для команд | LiteLLM |
| **v1.0** | Custom (если нужно) | CrewAI или Custom | LiteLLM |

### 12.6. Что НЕ пишем с нуля

| Компонент | НЕ пишем | ИСПОЛЬЗУЕМ |
|-----------|----------|------------|
| ReAct цикл | ❌ Custom loop | ✅ LangGraph StateGraph |
| Tool calling | ❌ Custom parser | ✅ LangChain Tools |
| Memory | ❌ Custom storage | ✅ LangChain Memory + Chroma |
| LLM interface | ❌ Custom clients | ✅ LiteLLM |
| Retry/Fallback | ❌ Custom logic | ✅ LiteLLM built-in |

> **КРИТИЧНО**: Фреймворки дают 80% функциональности. Мы кастомизируем только 20% для killer features!

---

## 13. Следующие шаги

После обсуждения и утверждения концепции:

1. **Создать AGENT_SPEC_v1.0.md** — формальная SSOT спецификация
2. **Реализовать WriterAgent** — первый специализированный агент
3. **Добавить Tool Use** — web_search как первый инструмент
4. **Реализовать CriticAgent** — для цикла улучшения качества

---

**Статус**: Ожидает финального утверждения
**Версия**: 0.4
**Автор**: AI_TEAM
**Дата обновления**: 2025-12-17

**Changelog v0.4** (по результатам исследования существующих стандартов):
- **ИСПРАВЛЕНО**: `status.phase: "Ready"` → `"Running"` (согласно SSOT enum)
- **ИСПРАВЛЕНО**: Registry регистрация через etcd API (не MindBus Events)
- **УТОЧНЕНО**: MindBus Events используются для уведомлений, а не для регистрации
- **УТОЧНЕНО**: Routing key `evt.{topic}.{event_type}` описывает "о чём", source — "от кого"

**Changelog v0.3** (по результатам аудита коллег):
- **ИСПРАВЛЕНО**: Routing keys выровнены с MindBus SSOT (`cmd.{role}.*`, `ctl.*.*`)
- **ИСПРАВЛЕНО**: CloudEvents types (`ai.team.*` вместо `ai_team.*`)
- **ИСПРАВЛЕНО**: Node Passport структура по Kubernetes pattern (`status.phase`, `metadata.uid`)
- **ИСПРАВЛЕНО**: RESULT отправка через reply-to (RPC pattern)

**Changelog v0.2**:
- Добавлен раздел 11 "SSOT Compliance" — явные контракты с существующими SSOT
- Добавлен раздел 12 "Ready-Made First" — выбор LangGraph + LiteLLM + CrewAI
- Учтены рекомендации коллег по предотвращению "изобретения велосипеда"
