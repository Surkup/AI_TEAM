# MINDBUS Protocol v1.0 (AMQP Edition)

**Статус документа:** ✅ Утверждено (Final Release v1.0)
**Дата:** 15.12.2025
**Технологический стек:** RabbitMQ (AMQP 0-9-1) + CloudEvents (JSON)
**Принцип:** Convention over Configuration

---

# ЧАСТЬ 1. КОНЦЕПТУАЛЬНОЕ ОПИСАНИЕ

## 1.1. Что такое MindBus?

**MindBus** — это «нервная система» проекта AI_TEAM. Это цифровая магистраль, которая соединяет «Мозг» (Оркестратора) с «Руками» (Агентами-исполнителями).

В отличие от обычной очереди задач, MindBus умеет управлять **важностью**. Если Человек (CEO) отправляет команду «СТОП», этот сигнал обгоняет очередь из обычных задач и поступает в обработку **следующим же сообщением**.

## 1.2. Философия: «Не изобретать велосипед»

Мы используем комбинацию зрелых стандартов:

1. **Транспорт:** RabbitMQ (AMQP 0-9-1) — для надежной доставки и приоритизации.
2. **Язык общения:** CloudEvents (JSON) — для совместимости данных.
3. **Наблюдаемость:** W3C Trace Context — для сквозного мониторинга.

**Обоснование выбора**: См. [READY_MADE_FIRST.md](../project/principles/READY_MADE_FIRST.md) — принцип "Готовые решения первичны"

**Альтернативы рассмотренные**: Custom IPv4-inspired protocol, gRPC, NATS, Apache Kafka

**Почему RabbitMQ + AMQP**:
- ✅ Покрывает 95% требований
- ✅ ISO/IEC 19464:2014 (международный стандарт)
- ✅ 15+ лет в production (банки, телеком)
- ✅ Встроенные приоритеты (Priority Queues)
- ✅ Готовые библиотеки для Python/Go
- ✅ Огромное сообщество + коммерческая поддержка (VMware)

## 1.3. Ключевые возможности

* **Управление приоритетами:** Система различает «фоновые задачи» (Low), «обычные команды» (Normal) и «экстренные прерывания» (Emergency).
* **Разделение идентификаторов:** Мы четко разделяем ID технического запроса (Trace) и ID бизнес-задачи (Subject).
* **Справедливое распределение (Fair Dispatch):** Система выдает новую задачу Агенту строго после того, как завершена предыдущая.

---

# ЧАСТЬ 2. ТЕХНИЧЕСКАЯ СПЕЦИФИКАЦИЯ (SSOT)

## 2.1. Топология и Инфраструктура

* **Broker:** RabbitMQ (версия 3.12+).
* **Exchange:** Единый **Topic Exchange** с именем `mindbus.main`.
* **Queues:** Очереди Агентов создаются с обязательным аргументом: `x-max-priority: 255`.

**Пример создания очереди**:
```python
import pika

channel.queue_declare(
    queue='agent.writer.001',
    durable=True,
    arguments={'x-max-priority': 255}
)
```

## 2.2. Адресация (Routing Keys)

Используется 3-х частный ключ: `type.target.id`

| Тип | Шаблон ключа | Пример | Назначение |
|-----|--------------|--------|------------|
| **COMMAND** | `cmd.{role}.{agent_id}` | `cmd.writer.any` | Поручение работы. |
| **EVENT** | `evt.{source}.{status}` | `evt.task.failed` | Событие (Pub/Sub). |
| **CONTROL** | `ctl.{target}.{scope}` | `ctl.all.stop` | Управляющий сигнал. |
| **RESULT** | *(Reply-To Queue)* | *amq.gen-X...* | Адрес возврата (RPC). |

**Допустимые значения `{scope}` для CONTROL:**

* `stop` — немедленная остановка текущей задачи.
* `pause` — приостановка (без сброса контекста).
* `resume` — возобновление.
* `shutdown` — полное выключение агента.
* `config` — запрос на перечитывание конфигурации.

**Примеры routing keys**:
```
cmd.writer.any          # Команда любому writer агенту
cmd.writer.writer-001   # Команда конкретному агенту
evt.orchestrator.started # Событие: оркестратор запустился
evt.task.completed      # Событие: задача завершена
ctl.all.stop            # Управление: СТОП всем агентам
ctl.writer.pause        # Управление: пауза для всех writer
```

## 2.3. Формат Данных (Data Plane)

Используется стандарт **CloudEvents v1.0** (JSON).

```json
{
  "specversion": "1.0",
  "type": "ai.team.command",
  "source": "orchestrator-core",
  "id": "msg-uuid-1234",           // ID конкретного сообщения (Envelope ID)
  "time": "2025-12-15T12:00:00Z",
  "datacontenttype": "application/json",

  // --- Business Context ---
  "subject": "task-business-555",  // ID бизнес-задачи / Процесса (Task ID)

  // --- Extensions (Logs & Debug only) ---
  // ВНИМАНИЕ: Source of Truth для этих полей — заголовки AMQP!
  // Здесь они дублируются ТОЛЬКО для удобства чтения JSON-логов.
  "priority": 63,
  "correlationid": "cmd-uuid-999",

  // --- Observability ---
  "traceparent": "00-4bf9...-01",  // W3C Trace Context (Span ID)

  // --- Payload ---
  "data": {
    "action": "generate_article",
    "params": {
      "topic": "AI trends 2025",
      "length": 2000
    }
  }
}
```

**CloudEvents спецификация**: https://cloudevents.io/

**Обязательные поля**:
- `specversion` — всегда "1.0"
- `type` — тип сообщения CloudEvents (см. 2.3.1)
- `source` — источник сообщения (компонент-отправитель)
- `id` — уникальный ID сообщения (UUID v4)

**Опциональные поля**:
- `time` — timestamp ISO 8601
- `subject` — ID бизнес-сущности (Task ID)
- `datacontenttype` — MIME type payload (обычно "application/json")
- `traceparent` — W3C Trace Context для распределённой трассировки

### 2.3.1. Типы CloudEvents сообщений

| CloudEvents Type | Назначение | Routing Key Pattern |
|------------------|------------|---------------------|
| `ai.team.command` | Команда агенту | `cmd.*.*` |
| `ai.team.result` | Результат выполнения | (reply-to queue) |
| `ai.team.event` | Событие в системе | `evt.*.*` |
| `ai.team.control` | Управляющий сигнал | `ctl.*.*` |

## 2.4. Маппинг на AMQP Properties (Source of Truth)

Клиент **обязан** заполнить заголовки протокола AMQP. Брокер и Агент доверяют **только** этим заголовкам.

| Свойство | AMQP Property | Значение / Правило |
|----------|---------------|-------------------|
| **Приоритет** | `priority` | `0-10`: Events, `20`: Commands, `255`: CONTROL. |
| **Срок жизни** | `expiration` | Время в мс (string). Пример: `"300000"` (5 минут) |
| **Reply To** | `reply_to` | Очередь для ответа. Пример: `amq.gen-xyz` |
| **Correlation**| `correlation_id` | Связь запрос-ответ. UUID строка. |
| **Delivery** | `delivery_mode` | `2` (Persistent - сообщения переживают рестарт брокера). |
| **Content Type** | `content_type` | `"application/json"` (всегда для CloudEvents) |

**Пример публикации сообщения**:

```python
import pika
import json
import uuid
from datetime import datetime

# CloudEvents сообщение
cloud_event = {
    "specversion": "1.0",
    "type": "ai.team.command",
    "source": "orchestrator-core",
    "id": str(uuid.uuid4()),
    "time": datetime.utcnow().isoformat() + "Z",
    "subject": "task-123",
    "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    "data": {
        "action": "generate_article",
        "params": {"topic": "AI trends"}
    }
}

# AMQP Properties (Source of Truth для маршрутизации)
properties = pika.BasicProperties(
    priority=20,                    # COMMAND priority
    delivery_mode=2,                # Persistent
    content_type='application/json',
    correlation_id=str(uuid.uuid4()),
    expiration='300000'             # 5 minutes TTL
)

# Публикация
channel.basic_publish(
    exchange='mindbus.main',
    routing_key='cmd.writer.any',
    body=json.dumps(cloud_event),
    properties=properties
)
```

## 2.5. Механика работы (Behavior & QoS)

### А. Fair Dispatch (Справедливое распределение)

Все Агенты устанавливают: `channel.basic_qos(prefetch_count=1)`.

* **Эффект:** Брокер держит в статусе "In-flight" не более 1 задачи на Агента.
* **Гарантия:** Если агент занят — новая задача пойдёт к другому агенту с той же ролью.

**Пример настройки**:
```python
channel.basic_qos(prefetch_count=1)
```

### Б. Обработка CONTROL (Cooperative Cancellation)

Сообщения с ключом `ctl.*` и приоритетом `255` помещаются в начало очереди.

* **Требование:** Агент должен проверять очередь/флаг отмены даже во время длительных вычислений.
* **Паттерн**: Проверка каждые N итераций/секунд в долгой операции.

**Пример проверки отмены**:
```python
def long_running_task(cancel_flag):
    for i in range(10000):
        if cancel_flag.is_set():
            logger.info("Task cancelled by CONTROL signal")
            return None
        # Работа
        process_item(i)
```

### В. Гарантии (ACK/NACK)

* **Success:** `basic.ack` отправляется после выполнения и отправки RESULT.
* **Failure:** При разрыве соединения задача возвращается в очередь (Re-queue).
* **Explicit NACK**: Агент может отправить `basic.nack(requeue=False)` для перемещения в Dead Letter Queue.

**Пример обработки**:
```python
def callback(ch, method, properties, body):
    try:
        # Обработка сообщения
        result = process_command(body)

        # Отправка результата
        send_result(result)

        # ACK только после успешной обработки
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"Failed to process: {e}")
        # NACK без requeue -> в DLX (Dead Letter Exchange)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
```

### Г. Проверка свежести (Client-side TTL)

RabbitMQ удаляет просроченные сообщения (Dead Lettering), но возможны гонки.

**Правило:** При получении сообщения Агент обязан проверить поле `expiration` (если передано) или `time` из CloudEvents.

* Если `current_time > timestamp + ttl`: Агент отправляет `ACK` (чтобы убрать из очереди), но **не выполняет** задачу, логируя событие `DroppedExpired`.

**Пример проверки TTL**:
```python
from datetime import datetime, timedelta

def callback(ch, method, properties, body):
    cloud_event = json.loads(body)

    # Проверка TTL
    if properties.expiration:
        ttl_ms = int(properties.expiration)
        message_time = datetime.fromisoformat(cloud_event['time'].rstrip('Z'))
        age = (datetime.utcnow() - message_time).total_seconds() * 1000

        if age > ttl_ms:
            logger.warning(f"Message expired: {cloud_event['id']}, age={age}ms")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return  # Не выполняем

    # Обычная обработка
    process_command(cloud_event)
    ch.basic_ack(delivery_tag=method.delivery_tag)
```

---

# ЧАСТЬ 3. ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

## 3.1. Пример: Отправка COMMAND

```python
import pika
import json
import uuid
from datetime import datetime

def send_command(role: str, action: str, params: dict, subject: str = None):
    """Отправить команду агенту с определённой ролью"""

    # CloudEvents сообщение
    cloud_event = {
        "specversion": "1.0",
        "type": "ai.team.command",
        "source": "orchestrator-core",
        "id": str(uuid.uuid4()),
        "time": datetime.utcnow().isoformat() + "Z",
        "datacontenttype": "application/json",
        "subject": subject or f"task-{uuid.uuid4()}",
        "data": {
            "action": action,
            "params": params
        }
    }

    # AMQP Properties
    properties = pika.BasicProperties(
        priority=20,                    # Normal command priority
        delivery_mode=2,                # Persistent
        content_type='application/json',
        correlation_id=cloud_event['id'],
        expiration='300000'             # 5 minutes
    )

    # Routing key для роли
    routing_key = f"cmd.{role}.any"

    # Публикация
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()

    channel.basic_publish(
        exchange='mindbus.main',
        routing_key=routing_key,
        body=json.dumps(cloud_event),
        properties=properties
    )

    connection.close()
    print(f"✅ Command sent: {action} -> {role}")

# Использование
send_command(
    role='writer',
    action='generate_article',
    params={'topic': 'AI trends 2025', 'length': 2000},
    subject='task-article-001'
)
```

## 3.2. Пример: Получение COMMAND агентом

```python
import pika
import json

def process_command(cloud_event: dict):
    """Обработка команды"""
    action = cloud_event['data']['action']
    params = cloud_event['data']['params']

    print(f"📥 Processing: {action}")
    print(f"   Params: {params}")

    # Ваша бизнес-логика здесь
    result = f"Article about {params.get('topic')} generated!"

    return result

def callback(ch, method, properties, body):
    """Callback для обработки сообщений"""
    try:
        cloud_event = json.loads(body)

        # Проверка TTL (см. секцию 2.5.Г)
        if is_expired(cloud_event, properties):
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # Обработка
        result = process_command(cloud_event)

        # TODO: Отправка RESULT обратно (см. 3.3)

        # ACK
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"❌ Error: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

# Настройка агента
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# Создание очереди с приоритетами
channel.queue_declare(
    queue='agent.writer.001',
    durable=True,
    arguments={'x-max-priority': 255}
)

# Bind к routing key
channel.queue_bind(
    queue='agent.writer.001',
    exchange='mindbus.main',
    routing_key='cmd.writer.*'  # Получаем все команды для writer
)

# Fair Dispatch
channel.basic_qos(prefetch_count=1)

# Подписка
channel.basic_consume(
    queue='agent.writer.001',
    on_message_callback=callback
)

print('🤖 Writer Agent started. Waiting for commands...')
channel.start_consuming()
```

## 3.3. Пример: Отправка EVENT

```python
def send_event(source: str, status: str, event_data: dict):
    """Публикация события в систему"""

    cloud_event = {
        "specversion": "1.0",
        "type": "ai.team.event",
        "source": source,
        "id": str(uuid.uuid4()),
        "time": datetime.utcnow().isoformat() + "Z",
        "data": event_data
    }

    properties = pika.BasicProperties(
        priority=10,                    # Low priority for events
        delivery_mode=2,
        content_type='application/json'
    )

    routing_key = f"evt.{source}.{status}"

    channel.basic_publish(
        exchange='mindbus.main',
        routing_key=routing_key,
        body=json.dumps(cloud_event),
        properties=properties
    )

# Использование
send_event(
    source='orchestrator',
    status='task_completed',
    event_data={'task_id': 'task-123', 'duration': 45}
)
```

---

# ЧАСТЬ 4. ПРИМЕЧАНИЯ (RISK MANAGEMENT)

## В1: Зачем `subject`, `traceparent` и `id`? Не много ли ID?

* **ID (`id`):** Уникален для каждого пакета (технический). Для дедупликации и логов.
* **Traceparent (`traceparent`):** Сквозной ID для Jaeger/Grafana (технический, трассировка). Связывает распределённые операции.
* **Subject (`subject`):** ID бизнес-сущности (Задачи/Процесса). Позволяет Агенту понять, "над каким проектом я работаю".

**Пример**:
```
ID: msg-001, msg-002, msg-003          # Три разных сообщения
Traceparent: trace-ABC                  # Все три части одной трассировки
Subject: task-555                       # Все три про одну задачу
```

## В2: JSON vs Binary

* **Текущий статус:** JSON для MVP.
* **План на будущее:** Переход на Protobuf в поле `data` внутри CloudEvents, если потребуется сжать трафик.
* **Обоснование JSON**: Читабельность логов, простота отладки, совместимость с ELK/Logstash.

## В3: Дублирование данных в JSON и Headers

* **Риск:** Рассинхрон между AMQP headers и CloudEvents extensions.
* **Решение:** Закреплено правило: **AMQP Headers = Source of Truth** для маршрутизации и приоритетов. JSON Extensions (`priority`, `correlationid`) = только для ELK/Logstash и отладки.

**Правило обработки**:
```python
# ✅ ПРАВИЛЬНО: Читаем приоритет из AMQP
priority = properties.priority

# ❌ НЕПРАВИЛЬНО: Читаем приоритет из CloudEvents JSON
# priority = cloud_event.get('priority')  # Только для логов!
```

## В4: Безопасность

**Текущая версия (MVP)**: Базовая безопасность RabbitMQ (user/password).

**Будущие улучшения**:
- TLS для шифрования трафика
- ACL (Access Control Lists) для ограничения доступа агентов к определённым routing keys
- Подпись сообщений (HMAC/JWT) для гарантии целостности

---

# ЧАСТЬ 5. КОНФИГУРАЦИЯ

## 5.1. Конфигурация RabbitMQ

```yaml
# config/rabbitmq.yaml
rabbitmq:
  host: localhost
  port: 5672
  vhost: /ai_team
  username: ${RABBITMQ_USER}    # Из environment
  password: ${RABBITMQ_PASS}

  exchange:
    name: mindbus.main
    type: topic
    durable: true

  priorities:
    event: 10
    command: 20
    control: 255

  ttl:
    default_ms: 300000           # 5 минут
    max_ms: 3600000              # 1 час (защита от бесконечных TTL)
```

## 5.2. Конфигурация компонентов

```yaml
# config/orchestrator.yaml
orchestrator:
  component_id: orchestrator-core
  queue_name: orchestrator.commands

  publishing:
    default_ttl_ms: 300000
    default_priority: 20

  consuming:
    prefetch_count: 1
    auto_ack: false
```

```yaml
# config/agent_writer.yaml
agent:
  role: writer
  instance_id: writer-001
  queue_name: agent.writer.001

  consuming:
    routing_keys:
      - cmd.writer.*
      - ctl.writer.*
      - ctl.all.*
    prefetch_count: 1

  publishing:
    default_priority: 20
```

---

# ЧАСТЬ 6. РАЗВЁРТЫВАНИЕ

## 6.1. Docker Compose для разработки

```yaml
# docker-compose.yaml
version: '3.8'

services:
  rabbitmq:
    image: rabbitmq:3.12-management
    container_name: ai_team_rabbitmq
    ports:
      - "5672:5672"      # AMQP
      - "15672:15672"    # Management UI
    environment:
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: secret
      RABBITMQ_DEFAULT_VHOST: /ai_team
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq

volumes:
  rabbitmq_data:
```

**Запуск**:
```bash
docker-compose up -d
```

**Management UI**: http://localhost:15672 (admin/secret)

## 6.2. Инициализация топологии

```python
# scripts/init_mindbus.py
import pika

connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host='localhost',
        virtual_host='/ai_team',
        credentials=pika.PlainCredentials('admin', 'secret')
    )
)
channel = connection.channel()

# Создание exchange
channel.exchange_declare(
    exchange='mindbus.main',
    exchange_type='topic',
    durable=True
)

print("✅ MindBus topology initialized")
connection.close()
```

---

# ЧАСТЬ 7. МИГРАЦИЯ И ВЕРСИОНИРОВАНИЕ

## 7.1. Версионирование протокола

**Текущая версия**: `v1.0` (AMQP + CloudEvents)

**Стратегия версионирования**:
- Мажорная версия (v2.0): Breaking changes (несовместимые изменения)
- Минорная версия (v1.1): Обратно совместимые добавления
- Патч версия (v1.0.1): Bugfixes

**Версия фиксируется в**:
- CloudEvents `specversion`: "1.0"
- Routing key может содержать версию: `cmd.v1.writer.any` (для будущего)

## 7.2. План миграции (если потребуется v2.0)

1. Dual-mode period: Брокер поддерживает v1 и v2 одновременно
2. Постепенное обновление компонентов
3. Мониторинг: когда последнее v1 сообщение?
4. Отключение v1 после grace period

---

## 9. Quick Start для разработчиков (SDK Implementation)

### 9.1. Структура MindBus SDK

**Рекомендуемая структура проекта** для разработки SDK:

```
mindbus_sdk/
├── __init__.py
├── config.py          # Чтение env (MINDBUS_URL, credentials)
├── connection.py      # pika.BlockingConnection wrapper
├── publisher.py       # send_command / send_event / send_control
├── consumer.py        # listen(), ACK/NACK
├── envelope.py        # CloudEvents creation helpers
├── routing.py         # routing key generation
├── constants.py       # priority enums, message scopes
└── exceptions.py      # MindBus exceptions
```

**Принцип**: Минимальная обёртка (~300-500 строк), вся логика в RabbitMQ + CloudEvents SDK.

---

### 9.2. Пример: Publisher (отправка команды)

```python
# publisher.py
from cloudevents.http import CloudEvent, to_structured
import pika
from uuid import uuid4
from datetime import datetime

class MindBusPublisher:
    def __init__(self, connection):
        self.channel = connection.channel()

    def send_command(self, target_role, payload, priority=20, ttl_ms=300000):
        """Отправить команду агенту

        Args:
            target_role: роль агента (writer, coder, researcher)
            payload: dict с данными задачи
            priority: приоритет 0-255 (20=normal, 100=high, 255=critical)
            ttl_ms: время жизни сообщения в миллисекундах
        """
        event = CloudEvent(
            attributes={
                "type": "ai.team.command",
                "source": "orchestrator",
                "id": str(uuid4()),
                "time": datetime.utcnow().isoformat() + "Z",
                "subject": payload.get("task_id"),
                "datacontenttype": "application/json"
            },
            data=payload
        )

        routing_key = f"cmd.{target_role}.any"

        self.channel.basic_publish(
            exchange="mindbus.main",
            routing_key=routing_key,
            body=to_structured(event)[1],
            properties=pika.BasicProperties(
                priority=priority,
                delivery_mode=2,  # persistent
                expiration=str(ttl_ms)
            )
        )
```

---

### 9.3. Пример: Consumer (обработка сообщений)

```python
# consumer.py
from cloudevents.http import from_structured
import pika

class MindBusConsumer:
    def __init__(self, connection, queue_name):
        self.channel = connection.channel()
        self.queue_name = queue_name

    def start(self, callback):
        """Начать слушать очередь

        Args:
            callback: функция обработки (принимает CloudEvent)
        """
        # Объявление очереди с приоритетами
        self.channel.queue_declare(
            queue=self.queue_name,
            durable=True,
            arguments={"x-max-priority": 255}
        )

        # QoS: обрабатывать по 1 сообщению
        self.channel.basic_qos(prefetch_count=1)

        def on_message(ch, method, props, body):
            try:
                # Парсинг CloudEvent
                event = from_structured(body)

                # Обработка задачи
                callback(event)

                # ACK (подтверждение обработки)
                ch.basic_ack(method.delivery_tag)
            except Exception as e:
                print(f"Error processing message: {e}")
                # NACK без requeue (сообщение в DLQ)
                ch.basic_nack(method.delivery_tag, requeue=False)

        self.channel.basic_consume(
            queue=self.queue_name,
            on_message_callback=on_message
        )

        print(f"Listening on queue: {self.queue_name}")
        self.channel.start_consuming()
```

---

### 9.4. Пример: Agent (полный цикл)

```python
# example_agent.py
from mindbus_sdk import MindBusConsumer, MindBusPublisher
import pika
import os

def main():
    # 1. Подключение к RabbitMQ
    connection = pika.BlockingConnection(
        pika.URLParameters(os.getenv("MINDBUS_URL"))
    )

    # 2. Consumer для получения задач
    consumer = MindBusConsumer(connection, "agent.writer.tasks")

    # 3. Publisher для отправки результатов
    publisher = MindBusPublisher(connection)

    # 4. Обработчик задач
    def handle_task(event):
        task = event.data
        print(f"Received task: {task['task_id']}")

        # Выполнить задачу (здесь ваша бизнес-логика)
        result = execute_writing_task(task)

        # Отправить результат обратно Оркестратору
        publisher.send_result(
            task_id=task["task_id"],
            result=result,
            priority=20
        )

    # 5. Запуск (блокирующий вызов)
    consumer.start(handle_task)

if __name__ == "__main__":
    main()
```

---

### 9.5. Пример: Connection Helper

```python
# connection.py
import pika
import os

def create_connection():
    """Создать подключение к RabbitMQ из env переменных"""
    url = os.getenv("MINDBUS_URL", "amqp://guest:guest@localhost:5672/")

    params = pika.URLParameters(url)
    params.heartbeat = 600  # heartbeat каждые 10 минут
    params.blocked_connection_timeout = 300

    return pika.BlockingConnection(params)
```

---

### 9.6. Checklist для разработчиков

**Перед началом разработки SDK**:

- [ ] ✅ Прочитал секции 1-5 этого документа (спецификация протокола)
- [ ] ✅ Установил зависимости: `pip install pika cloudevents`
- [ ] ✅ Запустил RabbitMQ (см. секцию 8)
- [ ] ✅ Создал структуру проекта (см. секцию 9.1)
- [ ] ✅ НЕ пишу custom AMQP клиент (использую `pika`)
- [ ] ✅ НЕ изобретаю формат сообщений (использую `CloudEvents`)
- [ ] ✅ НЕ реализую retry/reconnect вручную (использую `pika` механизмы)

**Запрещено при разработке**:

- ❌ Писать свой TCP/AMQP клиент
- ❌ Парсить JSON руками (использовать `CloudEvents` SDK)
- ❌ Хардкодить URL, credentials (использовать `config.py` + env)
- ❌ Добавлять кастомные поля в CloudEvent (только стандартные из секции 3)
- ❌ Изменять routing keys без обновления спецификации (секция 4)

---

### 9.7. Dependencies (requirements.txt)

```txt
pika>=1.3.0
cloudevents>=1.9.0
python-dotenv>=1.0.0
```

**Установка**:
```bash
pip install -r requirements.txt
```

---

### 9.8. Environment Configuration

**Пример `.env` файла**:

```bash
# RabbitMQ Connection
MINDBUS_URL=amqp://guest:guest@localhost:5672/

# Agent Configuration
AGENT_ROLE=writer
AGENT_QUEUE=agent.writer.tasks

# Logging
LOG_LEVEL=INFO
```

**⚠️ ВАЖНО**: `.env` файл НЕ коммитить в git (добавить в `.gitignore`).

---

### 9.9. Следующие шаги

После изучения этой секции разработчик готов:

1. ✅ Создать базовый MindBus SDK (~500 строк)
2. ✅ Реализовать первого агента (Writer/Coder/Researcher)
3. ✅ Подключить агента к RabbitMQ
4. ✅ Отправлять/получать сообщения через MindBus

**Время разработки базового SDK**: 1-2 дня

**Полная документация CloudEvents**: https://cloudevents.io/
**Полная документация pika**: https://pika.readthedocs.io/

---

**Документ утверждён. Готов к реализации.**

**Следующие шаги**:
1. Развёртывание RabbitMQ (Docker Compose) — см. секцию 8
2. Создание SDK библиотеки для Python (`mindbus-sdk`) — см. секцию 9
3. Реализация базового Orchestrator
4. Реализация первого агента (Writer)
5. End-to-end тестирование

**Время до MVP**: 1-2 недели

---

**Приложение A: Ссылки на стандарты**

- **AMQP 0-9-1**: https://www.rabbitmq.com/tutorials/amqp-concepts.html
- **ISO/IEC 19464:2014**: AMQP международный стандарт
- **CloudEvents v1.0**: https://cloudevents.io/
- **W3C Trace Context**: https://www.w3.org/TR/trace-context/
- **RabbitMQ Documentation**: https://www.rabbitmq.com/documentation.html

**Приложение B: Связанные документы**

- [READY_MADE_FIRST.md](../project/principles/READY_MADE_FIRST.md) — Обоснование выбора готовых решений
- [MINDBUS_README.md](../MINDBUS_README.md) — Концептуальная архитектура MindBus
- [PROJECT_OVERVIEW.md](../../PROJECT_OVERVIEW.md) — Общая архитектура AI_TEAM
- [CLAUDE.md](../../CLAUDE.md) — Правила разработки проекта
