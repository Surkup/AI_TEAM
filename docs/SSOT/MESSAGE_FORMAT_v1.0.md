# MESSAGE FORMAT Specification v1.0

**Статус**: ✅ Утверждено (Final Release v1.0)
**Версия**: 1.0
**Дата**: 2025-12-15
**Совместимость**: MindBus Protocol v1.0, CloudEvents v1.0
**Базируется на**: CNCF CloudEvents v1.0 (AMQP Edition)

---

## TL;DR (Executive Summary)

**MESSAGE FORMAT** — спецификация структуры поля `data` внутри CloudEvents сообщений для системы AI_TEAM.

**Основа**: CloudEvents v1.0 Specification (CNCF стандарт)

**Что определяет**:
- Структура `data` field для 3 типов сообщений: COMMAND, RESULT, EVENT
- Обязательные и опциональные поля
- Pydantic схемы для Python валидации
- Примеры использования

**Что НЕ определяет**:
- CloudEvents envelope (определено в [MindBus Protocol v1.0](mindbus_protocol_v1.md))
- Транспортный уровень (AMQP properties)
- Routing keys и приоритеты

**НЕ изобретаем велосипед**: Используем CloudEvents v1.0 envelope, определяем только содержимое `data` field.

---

## 1. Связь с MindBus Protocol v1.0

### 1.1. Разделение ответственности

**MindBus Protocol v1.0** определяет:
- ✅ CloudEvents envelope (`specversion`, `type`, `source`, `id`, `time`, `subject`)
- ✅ AMQP properties (priority, delivery_mode, expiration, routing_key)
- ✅ Routing patterns и топология RabbitMQ
- ✅ W3C Trace Context integration

**MESSAGE FORMAT v1.0** (этот документ) определяет:
- ✅ Структура поля `data` внутри CloudEvents
- ✅ Конкретные форматы для COMMAND, RESULT, EVENT типов
- ✅ Pydantic схемы для валидации
- ✅ Примеры полных сообщений

### 1.2. Как они работают вместе

```json
{
  // --- CloudEvents Envelope (определено в MindBus Protocol v1.0) ---
  "specversion": "1.0",
  "type": "ai.team.command",      // Тип CloudEvents (MindBus Protocol)
  "source": "orchestrator-core",
  "id": "msg-uuid-1234",
  "time": "2025-12-15T12:00:00Z",
  "subject": "task-555",
  "traceparent": "00-4bf9...-01",

  // --- Data Field (определено в MESSAGE FORMAT v1.0) ---
  "data": {
    "command_type": "generate_article",  // Структура определена здесь
    "target_node": "agent.writer.001",
    "params": {
      "topic": "AI trends 2025",
      "length": 2000
    },
    "timeout_seconds": 300
  }
}
```

**AMQP Properties** (Source of Truth для маршрутизации):
```python
properties = pika.BasicProperties(
    priority=20,                    # Command priority (MindBus Protocol)
    delivery_mode=2,                # Persistent
    content_type='application/json',
    correlation_id='msg-uuid-1234',
    expiration='300000'             # 5 minutes TTL
)

routing_key = 'cmd.writer.any'      # Routing pattern (MindBus Protocol)
```

---

## 2. Типы сообщений (Message Types)

Система использует 3 базовых типа сообщений для MVP:

| CloudEvents Type | Data Structure | Назначение | Пример |
|------------------|----------------|------------|--------|
| `ai.team.command` | `CommandData` | Команда агенту для выполнения задачи | "Сгенерируй статью" |
| `ai.team.result` | `ResultData` | Результат выполнения команды | "Статья готова" |
| `ai.team.event` | `EventData` | Уведомление о событии в системе | "Задача завершена" |

**Дополнительный тип** (из MindBus Protocol):
- `ai.team.control` — управляющие сигналы (STOP, PAUSE, RESUME)

---

## 3. COMMAND — Структура команды

### 3.1. Назначение

COMMAND — это поручение от Оркестратора к Агенту выполнить определённую задачу.

**Примеры команд**:
- `generate_article` — сгенерировать статью
- `review_code` — провести code review
- `analyze_data` — проанализировать данные
- `execute_test` — выполнить тест

### 3.2. Структура Data Field

```json
{
  "data": {
    "command_type": "string",       // REQUIRED: Тип команды (action)
    "target_node": "string",        // OPTIONAL: Конкретный узел (если нужен)
    "params": {},                   // REQUIRED: Параметры команды
    "timeout_seconds": 300,         // OPTIONAL: Таймаут выполнения
    "context": {},                  // OPTIONAL: Дополнительный контекст
    "retry_policy": {}              // OPTIONAL: Политика повторов
  }
}
```

### 3.3. Поля COMMAND

| Поле | Тип | Обязательность | Описание |
|------|-----|----------------|----------|
| `command_type` | `string` | **REQUIRED** | Тип команды (определяет какое действие выполнить). Примеры: `"generate_article"`, `"review_code"`, `"analyze_data"` |
| `target_node` | `string \| null` | OPTIONAL | ID конкретного узла (если нужна адресация конкретному агенту). Если `null` — маршрутизация по routing key |
| `params` | `object` | **REQUIRED** | Параметры команды (структура зависит от `command_type`). Минимум: `{}` (пустой объект) |
| `timeout_seconds` | `integer \| null` | OPTIONAL | Таймаут выполнения в секундах. Если не указан — используется дефолтное значение из конфига агента |
| `context` | `object \| null` | OPTIONAL | Дополнительный контекст для выполнения (например, предыдущие результаты, ссылки на артефакты) |
| `retry_policy` | `object \| null` | OPTIONAL | Политика повторов. Поля: `max_attempts` (int), `retry_delay_seconds` (int), `backoff_multiplier` (float) |

### 3.4. Примеры COMMAND

#### Пример 1: Простая команда генерации текста

```json
{
  "specversion": "1.0",
  "type": "ai.team.command",
  "source": "orchestrator-core",
  "id": "cmd-uuid-001",
  "time": "2025-12-15T12:00:00Z",
  "subject": "task-article-555",
  "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",

  "data": {
    "command_type": "generate_article",
    "params": {
      "topic": "AI trends 2025",
      "length": 2000,
      "style": "professional",
      "language": "en"
    },
    "timeout_seconds": 300
  }
}
```

**AMQP Properties**:
```python
priority=20,                    # Normal command
routing_key='cmd.writer.any'   # Any writer agent
```

#### Пример 2: Команда с контекстом и retry policy

```json
{
  "specversion": "1.0",
  "type": "ai.team.command",
  "source": "orchestrator-core",
  "id": "cmd-uuid-002",
  "time": "2025-12-15T12:05:00Z",
  "subject": "task-code-review-777",
  "traceparent": "00-7a8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p-11f167bb1ca013c8-01",

  "data": {
    "command_type": "review_code",
    "target_node": "agent.critic.001",
    "params": {
      "code_artifact_id": "artifact-12345",
      "language": "python",
      "focus": ["security", "performance", "readability"]
    },
    "timeout_seconds": 180,
    "context": {
      "previous_review_id": "review-999",
      "project_guidelines_url": "https://internal/guidelines.md"
    },
    "retry_policy": {
      "max_attempts": 3,
      "retry_delay_seconds": 5,
      "backoff_multiplier": 2.0
    }
  }
}
```

**AMQP Properties**:
```python
priority=20,
routing_key='cmd.critic.critic-001'   # Specific agent
```

### 3.5. Pydantic Schema для COMMAND

```python
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class RetryPolicy(BaseModel):
    """Политика повторных попыток"""
    max_attempts: int = Field(ge=1, le=10, description="Максимум попыток")
    retry_delay_seconds: int = Field(ge=1, description="Задержка между попытками")
    backoff_multiplier: float = Field(ge=1.0, le=5.0, default=1.0, description="Множитель для exponential backoff")

class CommandData(BaseModel):
    """Структура data field для COMMAND сообщений"""
    command_type: str = Field(
        min_length=1,
        max_length=100,
        description="Тип команды (action identifier)"
    )
    target_node: Optional[str] = Field(
        None,
        description="ID конкретного узла (если нужна точная адресация)"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Параметры команды (структура зависит от command_type)"
    )
    timeout_seconds: Optional[int] = Field(
        None,
        ge=1,
        le=3600,
        description="Таймаут выполнения в секундах"
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="Дополнительный контекст для выполнения"
    )
    retry_policy: Optional[RetryPolicy] = Field(
        None,
        description="Политика повторов при ошибках"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "command_type": "generate_article",
                    "params": {
                        "topic": "AI trends 2025",
                        "length": 2000
                    },
                    "timeout_seconds": 300
                }
            ]
        }
```

---

## 4. RESULT — Структура результата

### 4.1. Назначение

RESULT — это ответ Агента Оркестратору после выполнения команды.

**Типы результатов**:
- `SUCCESS` — команда выполнена успешно
- `FAILURE` — команда завершилась ошибкой
- `TIMEOUT` — превышен таймаут выполнения
- `CANCELLED` — команда отменена по CONTROL сигналу

### 4.2. Структура Data Field

```json
{
  "data": {
    "status": "string",             // REQUIRED: SUCCESS | FAILURE | TIMEOUT | CANCELLED
    "result": {},                   // OPTIONAL: Результат выполнения (при SUCCESS)
    "error": {},                    // OPTIONAL: Информация об ошибке (при FAILURE)
    "execution_time_ms": 1234,      // REQUIRED: Время выполнения в миллисекундах
    "metadata": {}                  // OPTIONAL: Метаданные выполнения
  }
}
```

### 4.3. Поля RESULT

| Поле | Тип | Обязательность | Описание |
|------|-----|----------------|----------|
| `status` | `enum` | **REQUIRED** | Статус выполнения: `"SUCCESS"`, `"FAILURE"`, `"TIMEOUT"`, `"CANCELLED"` |
| `result` | `object \| null` | OPTIONAL | Результат выполнения (только при `status=SUCCESS`). Структура зависит от `command_type` |
| `error` | `object \| null` | OPTIONAL | Информация об ошибке (только при `status=FAILURE`). Поля: `code` (string), `message` (string), `details` (object) |
| `execution_time_ms` | `integer` | **REQUIRED** | Фактическое время выполнения в миллисекундах |
| `metadata` | `object \| null` | OPTIONAL | Метаданные выполнения (model, tokens, cost, etc.) |

### 4.4. Примеры RESULT

#### Пример 1: Успешное выполнение

```json
{
  "specversion": "1.0",
  "type": "ai.team.result",
  "source": "agent.writer.001",
  "id": "result-uuid-001",
  "time": "2025-12-15T12:05:23Z",
  "subject": "task-article-555",
  "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-22f267cc2db024d9-01",

  "data": {
    "status": "SUCCESS",
    "result": {
      "article": "The landscape of AI in 2025 has evolved dramatically...",
      "word_count": 2047,
      "artifact_id": "artifact-67890"
    },
    "execution_time_ms": 12450,
    "metadata": {
      "model": "gpt-4",
      "tokens_used": 3500,
      "estimated_cost_usd": 0.105
    }
  }
}
```

**AMQP Properties**:
```python
priority=20,
correlation_id='cmd-uuid-001',      # Связь с исходной командой
reply_to='orchestrator.results'     # Очередь для ответов
```

#### Пример 2: Ошибка выполнения

```json
{
  "specversion": "1.0",
  "type": "ai.team.result",
  "source": "agent.critic.001",
  "id": "result-uuid-002",
  "time": "2025-12-15T12:06:15Z",
  "subject": "task-code-review-777",
  "traceparent": "00-7a8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p-33f367dd3ec035e0-01",

  "data": {
    "status": "FAILURE",
    "error": {
      "code": "ARTIFACT_NOT_FOUND",
      "message": "Artifact artifact-12345 not found in storage",
      "details": {
        "artifact_id": "artifact-12345",
        "storage_checked": ["s3://ai-team-artifacts", "postgres://artifacts"]
      }
    },
    "execution_time_ms": 1250,
    "metadata": {
      "retry_attempt": 2,
      "max_attempts": 3
    }
  }
}
```

#### Пример 3: Таймаут

```json
{
  "specversion": "1.0",
  "type": "ai.team.result",
  "source": "agent.researcher.003",
  "id": "result-uuid-003",
  "time": "2025-12-15T12:10:00Z",
  "subject": "task-research-888",
  "traceparent": "00-8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p3q-44f468ee4fd046f1-01",

  "data": {
    "status": "TIMEOUT",
    "error": {
      "code": "EXECUTION_TIMEOUT",
      "message": "Task execution exceeded timeout limit of 180 seconds",
      "details": {
        "timeout_seconds": 180,
        "elapsed_seconds": 180
      }
    },
    "execution_time_ms": 180000,
    "metadata": {
      "partial_results": "Research completed 60% before timeout"
    }
  }
}
```

### 4.5. Pydantic Schema для RESULT

```python
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Literal

class ErrorInfo(BaseModel):
    """Информация об ошибке"""
    code: str = Field(
        min_length=1,
        max_length=100,
        description="Код ошибки (например, ARTIFACT_NOT_FOUND)"
    )
    message: str = Field(
        min_length=1,
        description="Человекочитаемое описание ошибки"
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Дополнительные детали ошибки"
    )

class ResultData(BaseModel):
    """Структура data field для RESULT сообщений"""
    status: Literal["SUCCESS", "FAILURE", "TIMEOUT", "CANCELLED"] = Field(
        description="Статус выполнения команды"
    )
    result: Optional[Dict[str, Any]] = Field(
        None,
        description="Результат выполнения (только при SUCCESS)"
    )
    error: Optional[ErrorInfo] = Field(
        None,
        description="Информация об ошибке (только при FAILURE/TIMEOUT)"
    )
    execution_time_ms: int = Field(
        ge=0,
        description="Фактическое время выполнения в миллисекундах"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Метаданные выполнения (model, tokens, cost, etc.)"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "status": "SUCCESS",
                    "result": {
                        "article": "Generated content...",
                        "word_count": 2000
                    },
                    "execution_time_ms": 12450,
                    "metadata": {
                        "model": "gpt-4",
                        "tokens_used": 3500
                    }
                }
            ]
        }
```

---

## 5. EVENT — Структура события

### 5.1. Назначение

EVENT — это уведомление о событии в системе (Pub/Sub pattern).

**Примеры событий**:
- `task.created` — создана новая задача
- `task.completed` — задача завершена
- `node.registered` — узел зарегистрирован
- `node.heartbeat` — heartbeat от узла
- `system.error` — системная ошибка

### 5.2. Структура Data Field

```json
{
  "data": {
    "event_type": "string",         // REQUIRED: Тип события
    "event_data": {},               // REQUIRED: Данные события
    "severity": "string",           // OPTIONAL: INFO | WARNING | ERROR | CRITICAL
    "tags": []                      // OPTIONAL: Теги для фильтрации
  }
}
```

### 5.3. Поля EVENT

| Поле | Тип | Обязательность | Описание |
|------|-----|----------------|----------|
| `event_type` | `string` | **REQUIRED** | Тип события (обычно формат: `{source}.{action}`). Примеры: `"task.created"`, `"node.registered"` |
| `event_data` | `object` | **REQUIRED** | Данные события (структура зависит от `event_type`) |
| `severity` | `enum \| null` | OPTIONAL | Уровень важности: `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"`. По умолчанию: `"INFO"` |
| `tags` | `array[string] \| null` | OPTIONAL | Теги для фильтрации и категоризации |

### 5.4. Примеры EVENT

#### Пример 1: Событие завершения задачи

```json
{
  "specversion": "1.0",
  "type": "ai.team.event",
  "source": "orchestrator-core",
  "id": "event-uuid-001",
  "time": "2025-12-15T12:05:25Z",
  "subject": "task-article-555",
  "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-55f569ff5ge057g2-01",

  "data": {
    "event_type": "task.completed",
    "event_data": {
      "task_id": "task-article-555",
      "status": "SUCCESS",
      "duration_seconds": 325,
      "assigned_agent": "agent.writer.001",
      "artifact_id": "artifact-67890"
    },
    "severity": "INFO",
    "tags": ["task", "completion", "success"]
  }
}
```

**AMQP Properties**:
```python
priority=10,                        # Low priority for events
routing_key='evt.orchestrator.task_completed'
```

#### Пример 2: Событие ошибки системы

```json
{
  "specversion": "1.0",
  "type": "ai.team.event",
  "source": "agent.writer.001",
  "id": "event-uuid-002",
  "time": "2025-12-15T12:07:30Z",
  "subject": null,
  "traceparent": "00-9c0d1e2f3g4h5i6j7k8l9m0n1o2p3q4r-66f670gg6hf068h3-01",

  "data": {
    "event_type": "node.error",
    "event_data": {
      "node_id": "agent.writer.001",
      "error_code": "LLM_API_QUOTA_EXCEEDED",
      "error_message": "OpenAI API rate limit exceeded",
      "recovery_action": "Switched to fallback model (claude-3-sonnet)",
      "impact": "Temporary degradation in response quality"
    },
    "severity": "WARNING",
    "tags": ["node", "error", "llm", "fallback"]
  }
}
```

**AMQP Properties**:
```python
priority=10,
routing_key='evt.agent.error'
```

#### Пример 3: Heartbeat события

```json
{
  "specversion": "1.0",
  "type": "ai.team.event",
  "source": "agent.critic.002",
  "id": "event-uuid-003",
  "time": "2025-12-15T12:08:00Z",
  "subject": null,

  "data": {
    "event_type": "node.heartbeat",
    "event_data": {
      "node_id": "agent.critic.002",
      "status": "READY",
      "active_tasks": 1,
      "queue_length": 3,
      "uptime_seconds": 86400,
      "resource_usage": {
        "cpu_percent": 45.2,
        "memory_mb": 512
      }
    },
    "severity": "INFO",
    "tags": ["heartbeat", "monitoring"]
  }
}
```

**AMQP Properties**:
```python
priority=5,                         # Very low priority for heartbeats
routing_key='evt.agent.heartbeat'
```

### 5.5. Pydantic Schema для EVENT

```python
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Literal, List

class EventData(BaseModel):
    """Структура data field для EVENT сообщений"""
    event_type: str = Field(
        min_length=1,
        max_length=100,
        description="Тип события (формат: source.action)"
    )
    event_data: Dict[str, Any] = Field(
        description="Данные события (структура зависит от event_type)"
    )
    severity: Optional[Literal["INFO", "WARNING", "ERROR", "CRITICAL"]] = Field(
        "INFO",
        description="Уровень важности события"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Теги для фильтрации и категоризации"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "event_type": "task.completed",
                    "event_data": {
                        "task_id": "task-555",
                        "status": "SUCCESS"
                    },
                    "severity": "INFO",
                    "tags": ["task", "completion"]
                }
            ]
        }
```

---

## 6. CONTROL — Управляющие сигналы

### 6.1. Назначение

CONTROL — экстренные управляющие сигналы для остановки/паузы/возобновления работы.

**Определено в**: [MindBus Protocol v1.0, секция 2.2](mindbus_protocol_v1.md#22-адресация-routing-keys)

**Типы CONTROL** (scope):
- `stop` — немедленная остановка текущей задачи
- `pause` — приостановка без сброса контекста
- `resume` — возобновление работы
- `shutdown` — полное выключение узла
- `config` — перезагрузка конфигурации

**Routing keys**:
- `ctl.all.stop` — остановить все узлы
- `ctl.writer.pause` — пауза для всех writer агентов
- `ctl.agent.001.shutdown` — выключить конкретный узел

**AMQP Priority**: `255` (максимальный приоритет)

### 6.2. Структура Data Field

```json
{
  "data": {
    "control_type": "string",       // REQUIRED: stop | pause | resume | shutdown | config
    "reason": "string",             // OPTIONAL: Причина управляющего сигнала
    "parameters": {}                // OPTIONAL: Дополнительные параметры
  }
}
```

### 6.3. Пример CONTROL

```json
{
  "specversion": "1.0",
  "type": "ai.team.control",
  "source": "human-operator",
  "id": "control-uuid-001",
  "time": "2025-12-15T12:10:00Z",
  "subject": null,

  "data": {
    "control_type": "stop",
    "reason": "Emergency: High priority task requires immediate resources",
    "parameters": {
      "grace_period_seconds": 30,
      "save_state": true
    }
  }
}
```

**AMQP Properties**:
```python
priority=255,                       # CRITICAL priority
routing_key='ctl.all.stop'
```

### 6.4. Pydantic Schema для CONTROL

```python
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Literal

class ControlData(BaseModel):
    """Структура data field для CONTROL сообщений"""
    control_type: Literal["stop", "pause", "resume", "shutdown", "config"] = Field(
        description="Тип управляющего сигнала"
    )
    reason: Optional[str] = Field(
        None,
        description="Причина отправки управляющего сигнала"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        None,
        description="Дополнительные параметры управления"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "control_type": "stop",
                    "reason": "Emergency stop requested by operator",
                    "parameters": {
                        "grace_period_seconds": 30
                    }
                }
            ]
        }
```

---

## 7. Валидация сообщений

### 7.1. Обязательная валидация

**КРИТИЧЕСКИ ВАЖНО**: Все компоненты системы MUST validate входящие сообщения против SSOT схем.

**Правило обработки невалидных данных** (из [CLAUDE.md](../../CLAUDE.md)):
- **IF** message нарушает SSOT схему → **REJECT немедленно**
- **NEVER** пытаться "исправить" или "угадать" невалидные данные
- **ALWAYS** логировать ошибку валидации с деталями
- **MUST** отправить ERROR message обратно отправителю (если применимо)
- Компонент должен **fail fast**, не игнорировать ошибки молча

### 7.2. Пример валидации в Python

```python
from pydantic import ValidationError
import json

def validate_and_process_message(cloud_event: dict, channel, method):
    """Валидация и обработка входящего сообщения"""

    try:
        # 1. Проверка типа CloudEvents
        event_type = cloud_event.get("type")

        if event_type == "ai.team.command":
            # Валидация COMMAND
            command_data = CommandData(**cloud_event["data"])
            process_command(command_data)

        elif event_type == "ai.team.result":
            # Валидация RESULT
            result_data = ResultData(**cloud_event["data"])
            process_result(result_data)

        elif event_type == "ai.team.event":
            # Валидация EVENT
            event_data = EventData(**cloud_event["data"])
            process_event(event_data)

        else:
            raise ValueError(f"Unknown event type: {event_type}")

        # ACK только после успешной валидации и обработки
        channel.basic_ack(delivery_tag=method.delivery_tag)

    except ValidationError as e:
        # КРИТИЧЕСКИ ВАЖНО: Логируем детали ошибки валидации
        logger.error(
            f"SSOT validation failed for message {cloud_event.get('id')}",
            extra={
                "event_type": cloud_event.get("type"),
                "event_id": cloud_event.get("id"),
                "validation_errors": e.errors(),
                "raw_data": cloud_event.get("data")
            }
        )

        # Отправляем ERROR message обратно отправителю
        send_validation_error_response(
            original_message=cloud_event,
            validation_errors=e.errors()
        )

        # NACK без requeue → сообщение в Dead Letter Queue
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception as e:
        logger.error(f"Unexpected error processing message: {e}")
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
```

### 7.3. Пример отправки ERROR response

```python
def send_validation_error_response(original_message: dict, validation_errors: list):
    """Отправить ERROR response при ошибке валидации"""

    error_result = ResultData(
        status="FAILURE",
        error=ErrorInfo(
            code="VALIDATION_ERROR",
            message="Message data does not match SSOT schema",
            details={
                "original_message_id": original_message.get("id"),
                "validation_errors": validation_errors
            }
        ),
        execution_time_ms=0
    )

    error_event = {
        "specversion": "1.0",
        "type": "ai.team.result",
        "source": "agent.validator",
        "id": str(uuid.uuid4()),
        "time": datetime.utcnow().isoformat() + "Z",
        "subject": original_message.get("subject"),
        "traceparent": original_message.get("traceparent"),
        "data": error_result.model_dump()
    }

    # Отправка в MindBus
    publish_message(error_event, priority=20)
```

---

## 8. Конфигурация и Zero Hardcoding

### 8.1. Принцип Zero Hardcoding

**Из [CLAUDE.md](../../CLAUDE.md)**:
- **NEVER** hardcode timeouts, limits, параметры в коде
- **MUST** все параметры выносить в конфигурацию
- **ALWAYS** использовать environment variables для секретов

### 8.2. Пример конфигурации

```yaml
# config/messaging.yaml
messaging:
  # Дефолтные таймауты (НЕ hardcode в коде!)
  default_command_timeout_seconds: 300
  max_command_timeout_seconds: 3600

  # Retry политики
  default_retry_policy:
    max_attempts: 3
    retry_delay_seconds: 5
    backoff_multiplier: 2.0

  # Валидация
  validation:
    strict_mode: true           # Reject на любую ошибку валидации
    log_validation_errors: true
    send_error_responses: true

  # Приоритеты (должны совпадать с MindBus Protocol)
  priorities:
    event: 10
    command: 20
    result: 20
    control: 255
```

### 8.3. Использование конфигурации в коде

```python
import yaml
from pydantic import BaseModel

class MessagingConfig(BaseModel):
    """Конфигурация сообщений (Zero Hardcoding)"""
    default_command_timeout_seconds: int
    max_command_timeout_seconds: int
    # ... остальные поля

# Загрузка из YAML (НЕ hardcode!)
with open("config/messaging.yaml") as f:
    config_data = yaml.safe_load(f)
    messaging_config = MessagingConfig(**config_data["messaging"])

# Использование в коде
def create_command(command_type: str, params: dict) -> CommandData:
    return CommandData(
        command_type=command_type,
        params=params,
        timeout_seconds=messaging_config.default_command_timeout_seconds  # Из конфига!
    )
```

---

## 9. Интеграция с другими SSOT спецификациями

### 9.1. NODE PASSPORT интеграция

Когда узел регистрируется в системе, он отправляет EVENT:

```json
{
  "specversion": "1.0",
  "type": "ai.team.event",
  "source": "agent.writer.001",
  "id": "event-registration-001",
  "time": "2025-12-15T12:00:00Z",

  "data": {
    "event_type": "node.registered",
    "event_data": {
      "node_passport": {
        // Структура из NODE_PASSPORT_SPEC_v1.0.md
        "metadata": {
          "uid": "node-uuid-001",
          "name": "writer-001",
          "labels": {
            "role": "writer",
            "capability": "text_generation"
          }
        },
        "spec": {
          "nodeType": "agent",
          "capabilities": ["generate_article", "generate_story"],
          "resources": {
            "llm_model": "gpt-4",
            "max_tokens": 4096
          }
        },
        "status": {
          "phase": "Ready",
          "conditions": [...]
        }
      }
    },
    "severity": "INFO",
    "tags": ["registration", "agent"]
  }
}
```

### 9.2. PROCESS CARD интеграция

Когда Оркестратор выполняет Process Card, он отправляет COMMAND согласно шагам:

```yaml
# Process Card example (из PROCESS_CARD_SPEC_v1.0.md)
steps:
  - name: generate
    agent_role: writer
    command: generate_article
    params:
      topic: ${{ inputs.topic }}
```

**Оркестратор создаёт COMMAND**:

```json
{
  "data": {
    "command_type": "generate_article",  // Из Process Card: command
    "params": {
      "topic": "AI trends 2025"           // Из Process Card: params
    },
    "timeout_seconds": 300
  }
}
```

---

## 10. Миграция и версионирование

### 10.1. Версия спецификации

**Текущая версия**: v1.0

**Стратегия версионирования**:
- Мажорная версия (v2.0): Breaking changes (несовместимые изменения структуры)
- Минорная версия (v1.1): Обратно совместимые добавления полей
- Патч версия (v1.0.1): Исправления ошибок в документации

### 10.2. Обратная совместимость

**Правила для сохранения совместимости**:

✅ **МОЖНО добавить** (минорная версия):
- Новые OPTIONAL поля в существующие структуры
- Новые типы событий (`event_type`)
- Новые enum значения (если поле OPTIONAL)

❌ **НЕЛЬЗЯ без новой мажорной версии**:
- Удалять или переименовывать REQUIRED поля
- Менять типы данных существующих полей
- Менять семантику существующих полей
- Делать OPTIONAL поля REQUIRED

### 10.3. План миграции на v2.0 (если потребуется)

1. **Dual-mode период**: Система поддерживает v1.0 и v2.0 одновременно
2. **Версия в CloudEvents**: Добавить поле `dataschema` для явного указания версии
3. **Постепенное обновление**: Компоненты обновляются один за другим
4. **Мониторинг**: Отслеживаем когда последнее v1.0 сообщение обработано
5. **Отключение v1.0**: После grace period (например, 30 дней)

---

## Приложение A: Полные примеры

### A.1. Полный цикл COMMAND → RESULT

**1. Оркестратор отправляет COMMAND**:

```json
{
  "specversion": "1.0",
  "type": "ai.team.command",
  "source": "orchestrator-core",
  "id": "cmd-12345",
  "time": "2025-12-15T12:00:00Z",
  "subject": "task-555",
  "traceparent": "00-trace-abc-01",
  "datacontenttype": "application/json",

  "data": {
    "command_type": "generate_article",
    "params": {
      "topic": "AI trends 2025",
      "length": 2000
    },
    "timeout_seconds": 300
  }
}
```

**AMQP**: `routing_key='cmd.writer.any'`, `priority=20`

**2. Агент получает, валидирует, выполняет**

**3. Агент отправляет RESULT**:

```json
{
  "specversion": "1.0",
  "type": "ai.team.result",
  "source": "agent.writer.001",
  "id": "result-67890",
  "time": "2025-12-15T12:05:23Z",
  "subject": "task-555",
  "traceparent": "00-trace-abc-02",
  "datacontenttype": "application/json",

  "data": {
    "status": "SUCCESS",
    "result": {
      "article": "The AI landscape in 2025...",
      "word_count": 2047
    },
    "execution_time_ms": 12450,
    "metadata": {
      "model": "gpt-4",
      "tokens_used": 3500
    }
  }
}
```

**AMQP**: `correlation_id='cmd-12345'`, `reply_to='orchestrator.results'`

**4. Оркестратор публикует EVENT о завершении**:

```json
{
  "specversion": "1.0",
  "type": "ai.team.event",
  "source": "orchestrator-core",
  "id": "event-99999",
  "time": "2025-12-15T12:05:25Z",
  "subject": "task-555",
  "traceparent": "00-trace-abc-03",

  "data": {
    "event_type": "task.completed",
    "event_data": {
      "task_id": "task-555",
      "status": "SUCCESS",
      "duration_seconds": 325
    },
    "severity": "INFO"
  }
}
```

**AMQP**: `routing_key='evt.orchestrator.task_completed'`, `priority=10`

---

## Приложение B: Связанные документы

- **[MindBus Protocol v1.0](mindbus_protocol_v1.md)** — транспортный уровень и CloudEvents envelope
- **[NODE_PASSPORT_SPEC_v1.0.md](NODE_PASSPORT_SPEC_v1.0.md)** — спецификация паспорта узла
- **[NODE_REGISTRY_SPEC_v1.0.md](NODE_REGISTRY_SPEC_v1.0.md)** — спецификация реестра узлов
- **[PROCESS_CARD_SPEC_v1.0.md](PROCESS_CARD_SPEC_v1.0.md)** — спецификация карточек процессов
- **[CLAUDE.md](../../CLAUDE.md)** — правила разработки проекта
- **[PROJECT_OVERVIEW.md](../../PROJECT_OVERVIEW.md)** — общая концепция AI_TEAM

---

## Приложение C: Ссылки на стандарты

- **CloudEvents v1.0**: https://cloudevents.io/
- **CNCF CloudEvents Primer**: https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/primer.md
- **CloudEvents JSON Format**: https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/formats/json-format.md
- **W3C Trace Context**: https://www.w3.org/TR/trace-context/
- **Pydantic Documentation**: https://docs.pydantic.dev/

---

**Документ утверждён. Готов к реализации.**

**Следующие шаги**:
1. Реализация Pydantic моделей в `src/common/schemas/messages.py`
2. Интеграция валидации в MindBus SDK
3. Тестирование всех типов сообщений
4. Переход к Step 1.2: Реализация MindBus Core v0.1

**Статус реализации**: Step 1.1 ✅ ЗАВЕРШЁН

**Последнее обновление**: 2025-12-15
