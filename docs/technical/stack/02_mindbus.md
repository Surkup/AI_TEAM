# MindBus: RabbitMQ + AMQP 0-9-1 + CloudEvents

**Статус:** ✅ УТВЕРЖДЕНО
**Последнее обновление:** 2025-12-18

---

## Что такое MindBus?

**MindBus** — это «нервная система» AI_TEAM. Цифровая магистраль, которая соединяет «Мозг» (Оркестратор) с «Руками» (Агентами-исполнителями).

**Ключевое отличие от обычной очереди задач**: MindBus умеет управлять **важностью**. Если Человек (CEO) отправляет команду «СТОП», этот сигнал обгоняет очередь из обычных задач и поступает в обработку следующим же сообщением.

---

## Философия: Готовые решения первичны

Мы **НЕ изобретаем велосипед**. Используем комбинацию зрелых стандартов:

1. **Транспорт:** RabbitMQ (AMQP 0-9-1) — ISO/IEC 19464:2014
2. **Формат сообщений:** CloudEvents v1.0 (JSON) — CNCF стандарт
3. **Трассировка:** W3C Trace Context — сквозной мониторинг

**Обоснование выбора**: См. [docs/principles/READY_MADE_FIRST.md](../../principles/READY_MADE_FIRST.md)

**Полная техническая спецификация**: См. [docs/concepts/mindbus_protocol_v1.md](../../concepts/mindbus_protocol_v1.md)

---

## Почему RabbitMQ + AMQP?

### ✅ Покрывает 95% требований

**Что нам нужно от MindBus:**
- ✅ Надёжная доставка сообщений
- ✅ Управление приоритетами (Emergency > Normal > Low)
- ✅ Pub/Sub для событий
- ✅ Request/Reply для команд
- ✅ Fair dispatch (агенты не перегружаются)

**RabbitMQ предоставляет всё это из коробки.**

### ✅ ISO/IEC 19464:2014 (международный стандарт)

AMQP 0-9-1 — это **не просто протокол**, это **международный стандарт**, принятый ISO/IEC.

**Это означает:**
- Формальная спецификация
- Гарантированная совместимость
- Долгосрочная поддержка

### ✅ 15+ лет в production

**RabbitMQ используют:**
- Банки (миллионы финансовых транзакций)
- Телекоммуникационные компании (критичные системы)
- E-commerce платформы (высокие нагрузки)

**Для AI_TEAM это значит:** надёжность проверена временем и масштабом.

### ✅ Встроенные Priority Queues

```python
# Создаём очередь с поддержкой приоритетов
channel.queue_declare(
    queue='agent.writer.001',
    durable=True,
    arguments={'x-max-priority': 255}
)

# Отправляем сообщение с приоритетом
channel.basic_publish(
    exchange='mindbus.main',
    routing_key='cmd.writer.any',
    body=message_json,
    properties=pika.BasicProperties(
        priority=200  # Emergency (STOP команда)
    )
)
```

**Результат:** Команда «STOP» с приоритетом 200 обгоняет обычные задачи (приоритет 100).

### ✅ Готовые библиотеки для Python

```python
# Установка
pip install pika  # Официальная библиотека RabbitMQ для Python

# Использование
import pika

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost')
)
channel = connection.channel()

# Всё остальное — стандартный AMQP
```

**Никакой custom реализации протокола** — используем готовые, протестированные библиотеки.

---

### ⚠️ ВАЖНО: Thread Safety (pika.BlockingConnection)

> *Добавлено 2025-12-18 по результатам отладки*

**`pika.BlockingConnection` НЕ является потокобезопасной!**

**Проблема**: Если один поток слушает сообщения (`start_consuming`), а другой поток отправляет сообщения через то же соединение — возникает race condition:

```
ERROR: IndexError: pop from an empty deque
ERROR: StreamLostError: Transport indicated EOF
```

**Решение**: Для операций из разных потоков создавать **ОТДЕЛЬНЫЕ соединения**:

```python
# ❌ НЕПРАВИЛЬНО — одно соединение на два потока
self.bus = MindBus()
self.bus.connect()

# Поток 1: слушает сообщения
threading.Thread(target=self.bus.start_consuming).start()

# Поток 2: отправляет heartbeat (CRASH!)
self.bus.send_event("heartbeat", ...)


# ✅ ПРАВИЛЬНО — отдельное соединение для каждого потока
self.bus = MindBus()           # Основной поток
self.bus.connect()

self.heartbeat_bus = MindBus()  # Фоновый поток
self.heartbeat_bus.connect()

# Поток 1: слушает через основное соединение
threading.Thread(target=self.bus.start_consuming).start()

# Поток 2: отправляет через своё соединение
self.heartbeat_bus.send_event("heartbeat", ...)
```

**Правило**: Один поток = одно соединение MindBus.

**Подробнее**: См. [AGENT_SPEC v1.0.2, раздел 14.4](../../SSOT/AGENT_SPEC_v1.0.md#144-архитектура-соединений-mindbus-thread-safety)

---

## CloudEvents v1.0 — формат сообщений

**CloudEvents** — это CNCF стандарт для описания событий в облачных системах.

**Почему CloudEvents:**
- ✅ Vendor-neutral (не привязан к конкретной платформе)
- ✅ JSON формат (human-readable)
- ✅ Стандартные поля: `id`, `source`, `type`, `subject`, `data`
- ✅ Расширяемость через `datacontenttype` и custom attributes

**Пример CloudEvents сообщения:**

```json
{
  "specversion": "1.0",
  "type": "ai.team.command",
  "source": "orchestrator",
  "id": "msg-550e8400-e29b-41d4-a716-446655440000",
  "subject": "task-123",
  "time": "2025-12-15T10:30:00Z",
  "datacontenttype": "application/json",
  "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
  "data": {
    "action": "write_article",
    "params": {
      "topic": "AI trends 2025",
      "style": "professional"
    }
  }
}
```

**Ключевые поля:**
- `id` — уникальный ID сообщения (технический)
- `subject` — ID бизнес-задачи (для группировки)
- `traceparent` — W3C Trace Context (сквозная трассировка)
- `type` — тип сообщения (`ai.team.command`, `ai.team.event`, `ai.team.control`)

---

## W3C Trace Context — сквозная трассировка

**Проблема:** Как проследить путь одной задачи через десятки компонентов?

**Решение:** W3C Trace Context — стандарт для распределённой трассировки.

**Формат `traceparent`:**
```
00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
│   │                                │                  │
│   └─ Trace ID (128 bit)            └─ Parent ID      └─ Flags
└─ Version
```

**Как это работает:**

1. **Оркестратор** создаёт задачу → генерирует `trace_id`
2. Отправляет команду Writer → включает `traceparent` в CloudEvents
3. **Writer** обрабатывает → логирует с тем же `trace_id`
4. Writer вызывает LLM → включает `trace_id` в метаданные
5. Writer отправляет результат Critic → передаёт `trace_id`
6. **Critic** обрабатывает → логирует с тем же `trace_id`

**Результат:** Все логи, метрики, события связаны одним `trace_id` → можно проследить **всю историю задачи** от начала до конца.

**Визуализация в Grafana/Jaeger:**
```
Task execution (trace_id: 4bf92f3577b34da6a3ce929d0e0e4736)
  ├─ orchestrator: create_task (0.5s)
  ├─ writer: write_article (7.2s)
  │   └─ llm_service: gpt-4_call (6.8s)
  ├─ critic: critique_article (3.3s)
  │   └─ llm_service: claude_call (3.1s)
  └─ orchestrator: finalize_task (0.2s)
```

---

## Топология MindBus

### Topic Exchange

```
┌─────────────────────────────────────┐
│     mindbus.main (Topic Exchange)   │
│                                     │
│  Routing:                           │
│  - cmd.writer.any  → writer queues  │
│  - cmd.critic.any  → critic queues  │
│  - evt.task.*      → all listeners  │
│  - ctl.all.stop    → all agents     │
└─────────────────────────────────────┘
          │
    ┌─────┼─────┐
    │     │     │
    ▼     ▼     ▼
┌────────┐ ┌────────┐ ┌────────┐
│ writer │ │ critic │ │ editor │
│ queue  │ │ queue  │ │ queue  │
│ P:255  │ │ P:255  │ │ P:255  │
└────────┘ └────────┘ └────────┘
```

**Routing Keys:**
- `cmd.{role}.{agent_id}` — команда для агента (например: `cmd.writer.any`)
- `evt.{topic}.{event_type}` — событие (например: `evt.task.completed`, `evt.node.heartbeat`)
- `ctl.{target}.{scope}` — управляющий сигнал (например: `ctl.all.stop`)

### Priority Queues

Каждая очередь создаётся с `x-max-priority: 255`:

```python
channel.queue_declare(
    queue='agent.writer.001',
    durable=True,
    arguments={'x-max-priority': 255}
)
```

**Уровни приоритетов:**
- `200-255` — **Emergency** (STOP, SHUTDOWN)
- `150-199` — **High** (срочные задачи от пользователя)
- `100-149` — **Normal** (обычные команды)
- `50-99` — **Low** (фоновые задачи, мониторинг)

---

## Примеры кода

### Отправка команды (Orchestrator → Agent)

```python
import pika
import json
from datetime import datetime

# Подключение к RabbitMQ
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost')
)
channel = connection.channel()

# CloudEvents сообщение
message = {
    "specversion": "1.0",
    "type": "ai.team.command",
    "source": "orchestrator",
    "id": "msg-550e8400",
    "subject": "task-123",
    "time": datetime.utcnow().isoformat() + "Z",
    "datacontenttype": "application/json",
    "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    "data": {
        "action": "write_article",
        "params": {"topic": "AI trends 2025"}
    }
}

# Отправка
channel.basic_publish(
    exchange='mindbus.main',
    routing_key='cmd.writer.any',  # Любой writer агент
    body=json.dumps(message),
    properties=pika.BasicProperties(
        priority=100,  # Normal priority
        content_type='application/cloudevents+json',
        delivery_mode=2  # Persistent
    )
)

print(f"Sent command to writer agents (trace_id: {message['traceparent']})")
connection.close()
```

### Получение команды (Agent)

```python
import pika
import json

def callback(ch, method, properties, body):
    """Обработчик входящих сообщений"""
    # Парсим CloudEvents
    message = json.loads(body)

    trace_id = message.get('traceparent', 'unknown')
    action = message['data']['action']

    print(f"[{trace_id}] Received command: {action}")

    # Обработка команды...
    # (здесь логика агента)

    # Подтверждение обработки
    ch.basic_ack(delivery_tag=method.delivery_tag)

# Подключение
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost')
)
channel = connection.channel()

# Создаём очередь с приоритетами
channel.queue_declare(
    queue='agent.writer.001',
    durable=True,
    arguments={'x-max-priority': 255}
)

# Привязка к exchange
channel.queue_bind(
    exchange='mindbus.main',
    queue='agent.writer.001',
    routing_key='cmd.writer.#'  # Все команды для writer
)

# Fair dispatch (агент обрабатывает по 1 задаче)
channel.basic_qos(prefetch_count=1)

# Слушаем очередь
channel.basic_consume(
    queue='agent.writer.001',
    on_message_callback=callback
)

print('Writer agent waiting for commands...')
channel.start_consuming()
```

### Публикация события (Agent → Все слушатели)

```python
# Событие: задача завершена
event = {
    "specversion": "1.0",
    "type": "ai.team.event",
    "source": "agent.writer.001",
    "id": "evt-550e8400",
    "subject": "task-123",
    "time": datetime.utcnow().isoformat() + "Z",
    "datacontenttype": "application/json",
    "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    "data": {
        "status": "completed",
        "result_url": "minio://artifacts/task-123/article.txt"
    }
}

# Публикуем событие
channel.basic_publish(
    exchange='mindbus.main',
    routing_key='evt.task.completed',
    body=json.dumps(event),
    properties=pika.BasicProperties(
        content_type='application/cloudevents+json',
        delivery_mode=2
    )
)
```

---

## Альтернативы и почему НЕТ

### Redis Streams
**Почему НЕТ:**
- ❌ Нет встроенных Priority Queues (критично для STOP команд)
- ❌ Менее зрелый для enterprise messaging
- ❌ Меньше гарантий доставки vs RabbitMQ

**НО:** 🔄 **LEGO-принцип** позволяет заменить RabbitMQ на Redis Streams если требования изменятся.

### Apache Kafka
**Почему НЕТ для MVP:**
- ❌ Overkill для наших нагрузок
- ❌ Сложнее в настройке и эксплуатации
- ❌ Фокус на streaming (мы делаем messaging)

**НО:** 🔄 Можно мигрировать на Kafka если понадобится масштабирование до миллионов сообщений/сек.

### NATS
**Почему НЕТ для MVP:**
- ❌ Меньше production опыта vs RabbitMQ
- ❌ Меньше функций из коробки (Priority Queues требуют JetStream)

**НО:** 🔄 NATS — хороший кандидат для замены если нужна максимальная скорость.

### gRPC
**Почему НЕТ:**
- ❌ Request-Response паттерн (не Pub/Sub)
- ❌ Нет очередей и persistence
- ❌ Тесная связь клиент-сервер (не подходит для async messaging)

**Вердикт:** gRPC отлично для синхронных API, но не для async message bus.

### Custom протокол
**Почему НЕТ:**
- ❌ Reinventing wheel (7-10 недель разработки)
- ❌ Нет гарантий надёжности
- ❌ Нужна команда для поддержки

**RabbitMQ покрывает 95% требований** → нет причин писать с нуля.

---

## Интеграция с остальным стеком

### MindBus + Node Registry

```python
# Agent регистрируется в Registry
registry.register_node({
    "metadata": {
        "name": "writer-001",
        "namespace": "ai-team"
    },
    "spec": {
        "capabilities": ["write_article", "edit_text"],
        "mindbus_queue": "agent.writer.001",  # ← MindBus queue
        "mindbus_routing_key": "cmd.writer.#"
    }
})

# Orchestrator находит агента по capability
nodes = registry.find_by_capability("write_article")
target_queue = nodes[0]['spec']['mindbus_queue']

# Отправляет команду через MindBus
mindbus.send_command(
    queue=target_queue,
    action="write_article",
    params={...}
)
```

### MindBus + Process Cards

```yaml
# Process Card описывает WHAT (что делать)
steps:
  - id: "step_write"
    action: "write_article"
    params:
      topic: ${input.topic}
    output: draft

# Orchestrator переводит в MindBus сообщение (HOW)
{
  "type": "ai.team.command",
  "source": "orchestrator",
  "data": {
    "action": "write_article",
    "params": {"topic": "AI trends"}
  }
}
```

**Разделение ответственности:**
- **Process Card** — декларативное описание (WHAT)
- **Orchestrator** — находит узлы, создаёт MindBus сообщения (HOW)
- **MindBus** — доставляет сообщения (WHERE)

---

## Мониторинг MindBus

### RabbitMQ Management UI

```bash
# Доступ к веб-интерфейсу
http://localhost:15672

# Login: guest / guest (по умолчанию)
```

**Что можно увидеть:**
- Количество сообщений в очередях
- Скорость обработки (msg/sec)
- Неподтверждённые сообщения
- Подключённые consumers

### Prometheus метрики

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'rabbitmq'
    static_configs:
      - targets: ['localhost:15692']
```

**Ключевые метрики:**
- `rabbitmq_queue_messages` — количество сообщений в очереди
- `rabbitmq_queue_messages_ready` — ожидающие обработки
- `rabbitmq_queue_messages_unacknowledged` — в процессе обработки

### OpenTelemetry трассировка

```python
# При отправке сообщения
with tracer.start_as_current_span("mindbus.send_command") as span:
    span.set_attribute("routing_key", "cmd.writer.any")
    span.set_attribute("trace_id", trace_id)

    channel.basic_publish(...)
```

---

## Docker Compose для MVP

```yaml
version: '3.8'

services:
  # RabbitMQ
  rabbitmq:
    image: rabbitmq:3.12-management
    ports:
      - "5672:5672"    # AMQP
      - "15672:15672"  # Management UI
      - "15692:15692"  # Prometheus metrics
    environment:
      - RABBITMQ_DEFAULT_USER=admin
      - RABBITMQ_DEFAULT_PASS=password
    volumes:
      - rabbitmq-data:/var/lib/rabbitmq

volumes:
  rabbitmq-data:
```

**Запуск:**
```bash
docker-compose up -d rabbitmq

# Проверка
curl http://localhost:15672
```

---

## Итоговое решение

**RabbitMQ + AMQP 0-9-1 + CloudEvents — правильный выбор для MindBus:**

1. ✅ **ISO/IEC стандарт** с 15+ годами production опыта
2. ✅ **Priority Queues** для управления важностью (STOP > обычные команды)
3. ✅ **CloudEvents** для vendor-neutral формата сообщений
4. ✅ **W3C Trace Context** для сквозной трассировки
5. ✅ **Готовые библиотеки** (pika для Python)
6. ✅ **Battle-tested** (банки, телеком, e-commerce)
7. 🔄 **LEGO-модульность** — можно заменить на NATS/Kafka/Redis при необходимости

**Что НЕ делаем:**
- ❌ НЕ изобретаем custom протокол
- ❌ НЕ используем Redis Streams (нет Priority Queues)
- ❌ НЕ используем Kafka (overkill для MVP)

**Разделение ответственности:**
- **MindBus** — доставка сообщений между компонентами
- **Node Registry** — поиск узлов по capabilities
- **Process Cards** — декларативное описание процессов
- **Orchestrator** — координация выполнения

**MindBus = нервная система AI_TEAM** ✅

---

**Статус:** ✅ УТВЕРЖДЕНО
**Техническая спецификация:** [docs/concepts/mindbus_protocol_v1.md](../../concepts/mindbus_protocol_v1.md)
**Последнее обновление**: 2025-12-15
