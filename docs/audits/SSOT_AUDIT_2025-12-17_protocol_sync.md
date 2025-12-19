# SSOT Audit Report: Protocol Synchronization

**Дата**: 2025-12-17
**Аудитор**: Claude Opus 4.5
**Статус**: ✅ Завершён, все исправления внесены

---

## 1. Контекст аудита

После обновления MindBus Protocol до версии v1.0.1 с изменениями:
- Единый exchange `mindbus.main` (вместо множества exchanges)
- EVENT routing keys: `evt.{topic}.{event_type}` (описывает "о чём", а не "от кого")
- RESULT/ERROR: RPC reply-to pattern (отправка напрямую в очередь через default exchange)
- Регистрация узлов: etcd/Consul API (не через MindBus events)

Требовалось проверить согласованность всей документации с новым SSOT (mindbus_protocol_v1.md).

---

## 2. Найденные расхождения

### 2.1. MESSAGE_FORMAT_v1.1.md

| Строка | Было | Стало | Причина |
|--------|------|-------|---------|
| 601 | `routing_key='orchestrator.errors'` | RPC reply-to pattern с `exchange=''` | ERROR отправляется напрямую в reply_to очередь |
| 788 | `evt.orchestrator.task_completed` | `evt.task.completed` | EVENT routing key описывает topic, не source |
| 821 | `evt.agent.error` | `evt.node.error` | Унификация: topic = "node", event = "error" |
| 1375 | `evt.orchestrator.task_completed` | `evt.task.completed` | Аналогично строке 788 |

### 2.2. NODE_PASSPORT_SPEC_v1.0.md

| Строка | Было | Стало | Причина |
|--------|------|-------|---------|
| 291 | `"exchangeName": "mindbus.tasks"` | `"mindbus.main"` | Единый exchange |
| 576 | `MindBus Exchange: "mindbus.registry"` | HTTP/gRPC API или etcd/Consul | Регистрация через API, не events |
| 620 | `Exchange: mindbus.registry` | `mindbus.main` + пометка о рекомендуемом варианте | Единый exchange |
| 714-727 | `mindbus.registry` + старые routing keys | `mindbus.main` + `evt.registry.*` формат | Единый exchange + новый формат routing keys |

### 2.3. docs/technical/stack/02_mindbus.md

| Строка | Было | Стало | Причина |
|--------|------|-------|---------|
| 210 | `evt.{source}.{status}` | `evt.{topic}.{event_type}` | EVENT routing key описывает topic |

---

## 3. Архитектурное обоснование изменений

### 3.1. EVENT routing keys: `evt.{topic}.{event_type}`

**Философия**: Routing key описывает **"о чём"** событие, а не **"от кого"**.

**Пример**:
- `evt.task.completed` — событие о завершении задачи
- `evt.node.error` — событие об ошибке узла
- `evt.node.heartbeat` — событие heartbeat

**Кто отправил** указывается в CloudEvents поле `source`:
```json
{
  "type": "ai.team.event",
  "source": "agent.writer.001",  // ← WHO sent
  "data": {
    "event_type": "task.completed"  // ← WHAT happened
  }
}
```

### 3.2. RESULT/ERROR: RPC reply-to pattern

**Философия**: RESULT и ERROR — это ответы на конкретный COMMAND, не публичные события.

**Паттерн**:
```python
# Отправка через default exchange напрямую в очередь
channel.basic_publish(
    exchange='',                    # Default exchange
    routing_key=reply_to_queue,     # Очередь из COMMAND.reply_to
    body=result_json,
    properties=BasicProperties(
        correlation_id=command_id   # Связь с исходным COMMAND
    )
)
```

**Преимущества**:
- Меньше нагрузки на Topic Exchange
- Изоляция: только инициатор получает ответ
- Стандартный паттерн RabbitMQ RPC

### 3.3. Единый exchange `mindbus.main`

**Философия**: Простота > сложность. Один Topic Exchange покрывает все паттерны.

**Было**: `mindbus.tasks`, `mindbus.registry`, `mindbus.events`
**Стало**: `mindbus.main` (Topic Exchange)

**Routing keys разделяют типы**:
- `cmd.*` — команды
- `evt.*` — события
- `ctl.*` — управляющие сигналы

---

## 4. Файлы изменены

1. ✅ `docs/SSOT/MESSAGE_FORMAT_v1.1.md` — 4 исправления
2. ✅ `docs/SSOT/NODE_PASSPORT_SPEC_v1.0.md` — 4 исправления
3. ✅ `docs/technical/stack/02_mindbus.md` — 1 исправление

---

## 5. Рекомендации

1. **Версионирование**: Рассмотреть bump версии MESSAGE_FORMAT до v1.1.3 после этих изменений
2. **Код**: Убедиться, что `src/mindbus/core.py` соответствует документации (проверено ранее)
3. **Тесты**: Запустить `tests/test_comprehensive_mindbus.py` для валидации

---

**Аудит завершён**: 2025-12-17
**Все расхождения исправлены**: ✅
