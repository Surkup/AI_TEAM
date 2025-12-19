# NODE PASSPORT Specification v1.0

**Статус**: ✅ Утверждено (Final Release)
**Версия**: 1.0
**Дата**: 2025-12-15
**Совместимость**: MindBus Protocol v1.0, CloudEvents v1.0

---

## TL;DR (Executive Summary)

**NODE PASSPORT** — спецификация паспорта узла (агента/оркестратора/компонента) в системе AI_TEAM.

**Основа**: Kubernetes API Object Model (metadata/spec/status pattern)

**Ключевые возможности**:
- Самоописание узла (кто я, что умею, где нахожусь)
- Динамическое обнаружение (Service Discovery)
- Capability-based routing (маршрутизация по возможностям)
- Health monitoring (контроль работоспособности)
- Lease mechanism (легковесный heartbeat)

**НЕ изобретаем велосипед**: Используем проверенные паттерны Kubernetes (15+ лет production в миллионах узлов).

---

## 1. Зачем нужен NODE PASSPORT

### Проблемы без паспорта

**Проблема 1**: Оркестратор не знает какие агенты доступны
```
Orchestrator: "Нужен AI-агент для генерации кода"
??? → Как найти агента с capability "code_generation"?
```

**Проблема 2**: Невозможно понять статус узла
```
Agent отправил сообщение 5 минут назад.
Он ещё жив? Обрабатывает задачу? Завис?
```

**Проблема 3**: Невозможно маршрутизировать по возможностям
```
Задача требует: Python + OpenAI GPT-4 + >8GB RAM
Какой агент из 50 узлов подходит?
```

### ✅ Решение: NODE PASSPORT

```yaml
Каждый узел регистрирует свой паспорт:
- metadata: Кто я (ID, имя, тип)
- spec: Что умею (capabilities, resources)
- status: Моё состояние (ready/not_ready, conditions, lease)

Оркестратор может:
1. Найти все узлы с нужными capabilities (selector matching)
2. Проверить статус узла (conditions, lease)
3. Маршрутизировать задачи на подходящие узлы
```

---

## 2. Архитектурный паттерн (Kubernetes API Object)

### 2.1. Почему Kubernetes API Object Model?

**Проверенная архитектура**:
- ✅ Используется в production 15+ лет
- ✅ Управляет миллионами узлов одновременно
- ✅ Полная спецификация: https://kubernetes.io/docs/concepts/overview/working-with-objects/
- ✅ Множество готовых библиотек (Python, Go, etc.)

**Паттерны из Kubernetes**:
1. **metadata/spec/status** — разделение "что это" / "что хочу" / "что есть"
2. **Labels/Selectors** — мощная система фильтрации
3. **Conditions** — детальное описание состояния
4. **Lease** — легковесный heartbeat для больших кластеров

### 2.2. Структура паспорта (3 секции)

```yaml
metadata:   # КТО Я (идентификация)
  uid: "uuid"
  name: "human-readable-name"
  labels: {"key": "value"}  # для селекторов

spec:       # ЧТО УМЕЮ (желаемое состояние, capabilities)
  nodeType: "agent" | "orchestrator" | "storage"
  capabilities: [...]
  resources: {...}

status:     # МОЁ СОСТОЯНИЕ (фактическое состояние)
  conditions: [...]  # детали статуса
  lease: {...}       # heartbeat
```

**Принцип разделения**:
- `metadata` — неизменяемое (или редко меняется)
- `spec` — декларация возможностей (меняется при обновлении узла)
- `status` — динамическое (обновляется постоянно)

---

## 3. Полная схема NODE PASSPORT

### 3.1. Metadata (Идентификация узла)

```json
{
  "metadata": {
    "uid": "550e8400-e29b-41d4-a716-446655440000",
    "name": "ai-agent-coder-01",
    "nodeType": "agent",
    "labels": {
      "team": "ai_team",
      "role": "developer",
      "capability.code_generation": "true",
      "capability.python": "true",
      "capability.model.gpt-4": "true",
      "zone": "eu-west-1"
    },
    "annotations": {
      "description": "AI agent для генерации Python кода с использованием GPT-4",
      "owner": "team-backend",
      "created_at": "2025-12-15T10:00:00Z"
    },
    "creationTimestamp": "2025-12-15T10:00:00Z",
    "version": "1.2.5"
  }
}
```

#### Поля `metadata`

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `uid` | string (UUID) | ✅ | Уникальный идентификатор узла (неизменяемый) |
| `name` | string | ✅ | Человеко-читаемое имя (уникальное в системе) |
| `nodeType` | enum | ✅ | Тип узла: `agent`, `orchestrator`, `storage`, `gateway` |
| `labels` | map[string]string | ⚠️ | Метки для селекторов (рекомендуется) |
| `annotations` | map[string]string | ❌ | Произвольные метаданные (не для селекторов) |
| `creationTimestamp` | string (ISO 8601) | ✅ | Время создания узла |
| `version` | string | ✅ | Версия узла (semver: "1.2.5") |

#### Labels Convention (соглашения)

**Стандартные labels**:
```yaml
team: "ai_team"                        # Команда/проект
role: "developer" | "writer" | "qa"    # Роль агента
zone: "eu-west-1"                      # Географическая зона (если важно)
environment: "production" | "staging"  # Окружение
```

**Capability labels** (для селекторов):
```yaml
capability.code_generation: "true"     # Умеет генерировать код
capability.python: "true"              # Умеет Python
capability.model.gpt-4: "true"         # Использует GPT-4
capability.api.openai: "true"          # Имеет доступ к OpenAI API
```

**Правило**: Label ключи должны быть lowercase, разделитель: `.` или `-`. Значения: lowercase string.

---

### 3.2. Spec (Декларация возможностей)

```json
{
  "spec": {
    "nodeType": "agent",
    "capabilities": [
      {
        "name": "code_generation",
        "version": "1.0",
        "parameters": {
          "languages": ["python", "javascript", "go"],
          "max_lines": 1000,
          "models": ["gpt-4", "gpt-4-turbo"]
        }
      },
      {
        "name": "code_review",
        "version": "1.0",
        "parameters": {
          "languages": ["python"],
          "max_files": 10
        }
      }
    ],
    "resources": {
      "requests": {
        "cpu": "500m",
        "memory": "2Gi",
        "api_tokens": {
          "openai": 10000
        }
      },
      "limits": {
        "cpu": "2000m",
        "memory": "8Gi",
        "concurrent_tasks": 5
      }
    },
    "endpoint": {
      "protocol": "amqp",
      "queue": "ai-agent-coder-01.tasks",
      "replyQueue": "ai-agent-coder-01.replies"
    },
    "configuration": {
      "llm_provider": "openai",
      "model": "gpt-4-turbo-preview",
      "temperature": 0.7,
      "max_tokens": 4000
    }
  }
}
```

#### Поля `spec`

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `nodeType` | enum | ✅ | Тип узла (дублируется из metadata для удобства) |
| `capabilities` | array[Capability] | ✅ | Список возможностей узла |
| `resources` | Resources | ⚠️ | Ресурсы узла (requests/limits) |
| `endpoint` | Endpoint | ✅ | Как связаться с узлом |
| `configuration` | map[string]any | ❌ | Конфигурация узла (опционально) |

#### Capability Object

```json
{
  "name": "code_generation",
  "version": "1.0",
  "parameters": {
    "languages": ["python", "javascript"],
    "max_lines": 1000,
    "models": ["gpt-4"]
  }
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `name` | string | Название возможности (например: "code_generation", "text_translation") |
| `version` | string | Версия capability (semver) |
| `parameters` | map[string]any | Параметры возможности (произвольная структура) |

**Стандартные capability names** (предлагаемый список):
- `code_generation` — генерация кода
- `code_review` — ревью кода
- `text_generation` — генерация текста
- `text_translation` — перевод текста
- `image_generation` — генерация изображений
- `data_analysis` — анализ данных
- `task_orchestration` — оркестрация задач

#### Resources Object

```json
{
  "requests": {
    "cpu": "500m",
    "memory": "2Gi",
    "api_tokens": {"openai": 10000}
  },
  "limits": {
    "cpu": "2000m",
    "memory": "8Gi",
    "concurrent_tasks": 5
  }
}
```

**Формат** (аналогично Kubernetes):
- CPU: `"500m"` = 0.5 CPU core, `"2000m"` = 2 CPU cores
- Memory: `"2Gi"` = 2 Гибибайта, `"512Mi"` = 512 Мебибайт
- Custom resources: произвольные поля (API tokens, concurrent tasks, etc.)

#### Endpoint Object

```json
{
  "protocol": "amqp",
  "queue": "ai-agent-coder-01.tasks",
  "replyQueue": "ai-agent-coder-01.replies",
  "exchangeName": "mindbus.main",
  "routingKey": "agent.coder.01"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `protocol` | enum | Протокол: `"amqp"`, `"http"`, `"grpc"` (в AI_TEAM используется `amqp`) |
| `queue` | string | Очередь для входящих задач (AMQP queue name) |
| `replyQueue` | string | Очередь для ответов (опционально, если используется RPC pattern) |
| `exchangeName` | string | Exchange для публикации (опционально) |
| `routingKey` | string | Routing key для маршрутизации (опционально) |

---

### 3.3. Status (Текущее состояние)

```json
{
  "status": {
    "phase": "Running",
    "conditions": [
      {
        "type": "Ready",
        "status": "True",
        "lastTransitionTime": "2025-12-15T10:05:00Z",
        "reason": "AgentHealthy",
        "message": "Agent is ready to accept tasks"
      },
      {
        "type": "APIAvailable",
        "status": "True",
        "lastTransitionTime": "2025-12-15T10:00:30Z",
        "reason": "OpenAIConnected",
        "message": "OpenAI API is accessible, tokens available"
      },
      {
        "type": "ResourceSufficient",
        "status": "True",
        "lastTransitionTime": "2025-12-15T10:00:00Z",
        "reason": "WithinLimits",
        "message": "CPU: 800m/2000m, Memory: 3.2Gi/8Gi, Tasks: 2/5"
      }
    ],
    "lease": {
      "holderIdentity": "ai-agent-coder-01",
      "acquireTime": "2025-12-15T10:00:00Z",
      "renewTime": "2025-12-15T10:15:00Z",
      "leaseDurationSeconds": 30
    },
    "currentTasks": 2,
    "totalTasksProcessed": 1547,
    "lastActivityTime": "2025-12-15T10:14:55Z",
    "uptime": "5d 3h 15m"
  }
}
```

#### Поля `status`

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `phase` | enum | ✅ | Фаза жизненного цикла: `Pending`, `Running`, `Terminating`, `Failed` |
| `conditions` | array[Condition] | ✅ | Детальное описание состояния (паттерн Kubernetes) |
| `lease` | Lease | ✅ | Heartbeat механизм для определения живости узла |
| `currentTasks` | int | ❌ | Количество задач в обработке (опционально) |
| `totalTasksProcessed` | int | ❌ | Всего обработано задач с момента запуска |
| `lastActivityTime` | string (ISO 8601) | ⚠️ | Время последней активности (рекомендуется) |
| `uptime` | string | ❌ | Время работы узла (человеко-читаемое, опционально) |

#### Phase (Фазы жизненного цикла)

| Phase | Описание | Когда переходим |
|-------|----------|------------------|
| `Pending` | Узел регистрируется, ещё не готов | После создания паспорта, до готовности |
| `Running` | Узел работает, принимает задачи | Когда `Ready` condition = True |
| `Terminating` | Узел завершает работу (graceful shutdown) | Получен сигнал остановки |
| `Failed` | Узел в нерабочем состоянии | Критическая ошибка, потеря связи |

#### Condition Object (паттерн Kubernetes)

```json
{
  "type": "Ready",
  "status": "True",
  "lastTransitionTime": "2025-12-15T10:05:00Z",
  "reason": "AgentHealthy",
  "message": "Agent is ready to accept tasks"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `type` | string | Тип условия (например: "Ready", "APIAvailable", "ResourceSufficient") |
| `status` | enum | Состояние: `"True"`, `"False"`, `"Unknown"` |
| `lastTransitionTime` | string (ISO 8601) | Время последнего изменения статуса |
| `reason` | string | Краткая причина (CamelCase, машинно-читаемая) |
| `message` | string | Детальное описание для человека |

**Стандартные Condition Types**:

| Type | Описание | status=True | status=False |
|------|----------|-------------|--------------|
| `Ready` | Узел готов к работе | Принимает задачи | Не может принимать задачи |
| `APIAvailable` | Внешний API доступен | API работает | Нет доступа к API |
| `ResourceSufficient` | Ресурсы в пределах лимитов | В норме | Превышение лимитов |
| `Healthy` | Health check пройден | Здоров | Нездоров |
| `NetworkReachable` | Сеть доступна | Сеть OK | Проблемы с сетью |

**Правило обновления Conditions**:
- Узел ОБЯЗАН обновлять conditions при каждом изменении статуса
- `lastTransitionTime` обновляется ТОЛЬКО при смене `status` (True ↔ False)
- Если status не изменился, `lastTransitionTime` остаётся прежним

#### Lease Object (Heartbeat механизм)

```json
{
  "holderIdentity": "ai-agent-coder-01",
  "acquireTime": "2025-12-15T10:00:00Z",
  "renewTime": "2025-12-15T10:15:00Z",
  "leaseDurationSeconds": 30
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `holderIdentity` | string | ID держателя lease (обычно = metadata.name) |
| `acquireTime` | string (ISO 8601) | Когда lease был получен впервые |
| `renewTime` | string (ISO 8601) | Последнее обновление lease (heartbeat) |
| `leaseDurationSeconds` | int | Срок действия lease в секундах (обычно 15-30s) |

**Логика работы Lease**:

1. **Узел получает lease** при регистрации (`acquireTime`)
2. **Узел обновляет lease** каждые N секунд (`renewTime` обновляется)
3. **Оркестратор проверяет**: `now() - renewTime < leaseDurationSeconds`
   - Если ДА → узел живой
   - Если НЕТ → узел считается мёртвым (убрать из активных)

**Преимущества Lease vs Heartbeat**:
- ✅ Легковесный (только обновление timestamp, без создания новых сообщений)
- ✅ Масштабируемый (в Kubernetes управляет миллионами узлов)
- ✅ Tolerance to clock skew (небольшая погрешность часов не критична)

**Рекомендуемые значения**:
```yaml
leaseDurationSeconds: 30      # Lease действителен 30 секунд
renewIntervalSeconds: 10      # Узел обновляет каждые 10 секунд
                              # → 3x буфер для сбоев сети
```

---

## 4. Capability Matching (Селекторы)

### 4.1. Как Оркестратор находит подходящий узел?

**Задача**: Найти агента с возможностями: `code_generation` + `python` + `gpt-4`

**Селектор** (аналогично Kubernetes Label Selector):

```json
{
  "selector": {
    "matchLabels": {
      "capability.code_generation": "true",
      "capability.python": "true",
      "capability.model.gpt-4": "true"
    },
    "matchExpressions": [
      {
        "key": "zone",
        "operator": "In",
        "values": ["eu-west-1", "eu-central-1"]
      },
      {
        "key": "memory",
        "operator": "Gt",
        "values": ["4Gi"]
      }
    ]
  }
}
```

### 4.2. Selector Syntax

#### matchLabels (Точное совпадение)

```json
"matchLabels": {
  "capability.python": "true",
  "role": "developer"
}
```

**Правило**: ВСЕ labels должны совпадать (AND логика)

#### matchExpressions (Операторы)

```json
"matchExpressions": [
  {
    "key": "zone",
    "operator": "In",
    "values": ["eu-west-1", "us-east-1"]
  }
]
```

**Поддерживаемые операторы**:

| Operator | Описание | Пример |
|----------|----------|--------|
| `In` | Значение в списке | `zone In [eu-west-1, us-east-1]` |
| `NotIn` | Значение НЕ в списке | `zone NotIn [deprecated-zone]` |
| `Exists` | Label существует | `capability.code_generation Exists` |
| `DoesNotExist` | Label НЕ существует | `legacy DoesNotExist` |
| `Gt` | Больше (для чисел) | `memory Gt [4Gi]` |
| `Lt` | Меньше (для чисел) | `cpu Lt [2000m]` |

**Правило**: ВСЕ выражения должны быть истинны (AND логика)

### 4.3. Пример: Поиск узлов

**Запрос Оркестратора**:

```python
# Найти агентов с Python + GPT-4, в EU зонах, с >4Gi памяти
selector = {
    "matchLabels": {
        "capability.python": "true",
        "capability.model.gpt-4": "true"
    },
    "matchExpressions": [
        {"key": "zone", "operator": "In", "values": ["eu-west-1", "eu-central-1"]},
        {"key": "memory", "operator": "Gt", "values": ["4Gi"]},
        {"key": "status.phase", "operator": "In", "values": ["Running"]},
        {"key": "status.conditions.Ready", "operator": "Eq", "values": ["True"]}
    ]
}

matching_nodes = registry.find_nodes(selector)
```

**Результат**:

```json
[
  {
    "metadata": {
      "uid": "550e8400-e29b-41d4-a716-446655440000",
      "name": "ai-agent-coder-01",
      "labels": {
        "capability.python": "true",
        "capability.model.gpt-4": "true",
        "zone": "eu-west-1"
      }
    },
    "spec": {
      "resources": {
        "limits": {"memory": "8Gi"}
      }
    },
    "status": {
      "phase": "Running",
      "conditions": [{"type": "Ready", "status": "True"}]
    }
  }
]
```

---

## 5. Регистрация и обновление паспорта

### 5.1. Процесс регистрации узла (Node Lifecycle)

```
1. [Узел стартует]
   ↓
2. [Создаёт свой NODE PASSPORT]
   ↓
3. [Регистрирует паспорт в Registry]
   → HTTP/gRPC API или etcd/Consul
   → Registry Service сохраняет паспорт
   ↓
4. [Registry сохраняет паспорт]
   → Валидация схемы
   → Сохранение в БД
   → Присвоение UID (если не указан)
   ↓
5. [Registry отправляет подтверждение]
   → CloudEvent: node.registered.ack
   ↓
6. [Узел начинает обновлять Lease]
   → Каждые 10s публикует: node.lease.renewed
   ↓
7. [Узел переходит в phase: Running]
   → Обновляет status.phase
   → Публикует: node.status.updated
   ↓
8. [Узел готов принимать задачи]
```

### 5.2. CloudEvent для регистрации

**Event Type**: `node.registered`

```json
{
  "specversion": "1.0",
  "type": "node.registered",
  "source": "ai-agent-coder-01",
  "id": "uuid-event-id",
  "time": "2025-12-15T10:00:00Z",
  "datacontenttype": "application/json",
  "data": {
    "passport": {
      "metadata": { ... },
      "spec": { ... },
      "status": { ... }
    }
  }
}
```

**Альтернатива через MindBus** (если используется EVENT-based регистрация):
- Exchange: `mindbus.main`
- Routing Key: `evt.registry.node_registered`
- Queue: `registry.events` (подписка Registry Service)

**Рекомендуемый вариант**: Прямая регистрация через HTTP/gRPC API или etcd/Consul (см. NODE_REGISTRY_SPEC)

### 5.3. Обновление паспорта

**Когда обновлять**:

| Что изменилось | Event Type | Частота |
|----------------|------------|---------|
| Lease (heartbeat) | `node.lease.renewed` | Каждые 10s |
| Status (conditions) | `node.status.updated` | При изменении |
| Spec (capabilities) | `node.spec.updated` | Редко (при обновлении узла) |
| Metadata (labels) | `node.metadata.updated` | Очень редко |

**CloudEvent для обновления Lease**:

```json
{
  "specversion": "1.0",
  "type": "node.lease.renewed",
  "source": "ai-agent-coder-01",
  "id": "uuid-event-id",
  "time": "2025-12-15T10:15:00Z",
  "datacontenttype": "application/json",
  "data": {
    "nodeId": "550e8400-e29b-41d4-a716-446655440000",
    "lease": {
      "renewTime": "2025-12-15T10:15:00Z"
    }
  }
}
```

**Оптимизация**: Lease обновления могут идти напрямую в Registry (без MindBus), через HTTP/gRPC для снижения нагрузки.

### 5.4. Удаление узла (Graceful Shutdown)

```
1. [Узел получает сигнал остановки (SIGTERM)]
   ↓
2. [Переходит в phase: Terminating]
   → Публикует: node.status.updated (phase=Terminating)
   ↓
3. [Завершает обработку текущих задач]
   → Отклоняет новые задачи
   → Дожидается завершения активных
   ↓
4. [Публикует финальный event]
   → CloudEvent: node.deregistered
   ↓
5. [Registry удаляет паспорт]
   ↓
6. [Узел останавливается]
```

**CloudEvent для удаления**:

```json
{
  "specversion": "1.0",
  "type": "node.deregistered",
  "source": "ai-agent-coder-01",
  "id": "uuid-event-id",
  "time": "2025-12-15T10:30:00Z",
  "datacontenttype": "application/json",
  "data": {
    "nodeId": "550e8400-e29b-41d4-a716-446655440000",
    "reason": "GracefulShutdown",
    "message": "Node shutting down normally"
  }
}
```

---

## 6. Интеграция с MindBus Protocol

### 6.1. Registry Service (Хранитель паспортов)

**Роль**: Централизованный реестр всех узлов системы

**Функции**:
1. Приём регистраций узлов (node.registered events)
2. Обновление паспортов (node.*.updated events)
3. Обновление Lease (node.lease.renewed events)
4. Мониторинг живости (проверка Lease)
5. Удаление мёртвых узлов (Lease expired)
6. Поиск узлов по селекторам (Capability Matching API)

**Exchanges и Queues** (если используется EVENT-based подход):

```yaml
# Registry получает события (через единый exchange)
Exchange: mindbus.main
Queue: registry.events
Bindings:
  - routing_key: "evt.registry.node_registered"
  - routing_key: "evt.registry.node_updated"
  - routing_key: "evt.registry.node_deregistered"
  - routing_key: "evt.node.heartbeat"

# Registry публикует события (Pub/Sub)
Exchange: mindbus.main
Routing keys:
  - "evt.registry.node_registered_ack"
  - "evt.registry.node_updated_ack"
```

**Рекомендуемый вариант**: Прямая регистрация через etcd/Consul API (см. NODE_REGISTRY_SPEC v1.0.1)

### 6.2. Orchestrator → Registry: Поиск узла

**Сценарий**: Оркестратор получил задачу, ищет подходящий агент

**Запрос** (CloudEvent):

```json
{
  "specversion": "1.0",
  "type": "registry.nodes.query",
  "source": "orchestrator-main",
  "id": "query-uuid",
  "time": "2025-12-15T10:20:00Z",
  "datacontenttype": "application/json",
  "data": {
    "selector": {
      "matchLabels": {
        "capability.code_generation": "true",
        "capability.python": "true"
      },
      "matchExpressions": [
        {"key": "status.phase", "operator": "Eq", "values": ["Running"]},
        {"key": "status.conditions.Ready", "operator": "Eq", "values": ["True"]}
      ]
    },
    "limit": 10,
    "sortBy": "currentTasks"
  }
}
```

**Ответ** (CloudEvent):

```json
{
  "specversion": "1.0",
  "type": "registry.nodes.query.response",
  "source": "registry-service",
  "id": "response-uuid",
  "time": "2025-12-15T10:20:00.050Z",
  "datacontenttype": "application/json",
  "correlationid": "query-uuid",
  "data": {
    "nodes": [
      {
        "metadata": { ... },
        "spec": { ... },
        "status": { ... }
      }
    ],
    "totalMatched": 3,
    "returned": 3
  }
}
```

**Паттерн**: Request-Reply (RabbitMQ RPC)

### 6.3. Agent → Registry: Heartbeat (Lease Update)

**Вариант 1: Через MindBus** (CloudEvent)

```json
{
  "specversion": "1.0",
  "type": "node.lease.renewed",
  "source": "ai-agent-coder-01",
  "id": "lease-uuid",
  "time": "2025-12-15T10:20:15Z",
  "datacontenttype": "application/json",
  "data": {
    "nodeId": "550e8400-e29b-41d4-a716-446655440000",
    "lease": {
      "renewTime": "2025-12-15T10:20:15Z"
    }
  }
}
```

**Вариант 2: Прямой HTTP/gRPC** (легче для Registry)

```http
PATCH /api/v1/nodes/550e8400-e29b-41d4-a716-446655440000/lease
Content-Type: application/json

{
  "renewTime": "2025-12-15T10:20:15Z"
}
```

**Рекомендация**: Используйте HTTP/gRPC для Lease updates (меньше нагрузка на MindBus).

---

## 7. Примеры паспортов для разных типов узлов

### 7.1. AI Agent (Code Generator)

```json
{
  "metadata": {
    "uid": "550e8400-e29b-41d4-a716-446655440000",
    "name": "ai-agent-coder-01",
    "nodeType": "agent",
    "labels": {
      "role": "developer",
      "capability.code_generation": "true",
      "capability.python": "true",
      "capability.model.gpt-4": "true",
      "zone": "eu-west-1"
    },
    "creationTimestamp": "2025-12-15T10:00:00Z",
    "version": "1.2.5"
  },
  "spec": {
    "nodeType": "agent",
    "capabilities": [
      {
        "name": "code_generation",
        "version": "1.0",
        "parameters": {
          "languages": ["python", "javascript"],
          "max_lines": 1000,
          "models": ["gpt-4", "gpt-4-turbo"]
        }
      }
    ],
    "resources": {
      "limits": {
        "memory": "8Gi",
        "concurrent_tasks": 5
      }
    },
    "endpoint": {
      "protocol": "amqp",
      "queue": "ai-agent-coder-01.tasks"
    }
  },
  "status": {
    "phase": "Running",
    "conditions": [
      {"type": "Ready", "status": "True", "lastTransitionTime": "2025-12-15T10:05:00Z"}
    ],
    "lease": {
      "holderIdentity": "ai-agent-coder-01",
      "renewTime": "2025-12-15T10:20:00Z",
      "leaseDurationSeconds": 30
    },
    "currentTasks": 2
  }
}
```

### 7.2. Orchestrator

```json
{
  "metadata": {
    "uid": "orchestrator-main-uuid",
    "name": "orchestrator-main",
    "nodeType": "orchestrator",
    "labels": {
      "role": "orchestrator",
      "capability.task_orchestration": "true",
      "capability.process_management": "true"
    },
    "creationTimestamp": "2025-12-15T09:00:00Z",
    "version": "2.0.0"
  },
  "spec": {
    "nodeType": "orchestrator",
    "capabilities": [
      {
        "name": "task_orchestration",
        "version": "1.0",
        "parameters": {
          "max_parallel_workflows": 100,
          "max_agents_managed": 500
        }
      }
    ],
    "endpoint": {
      "protocol": "amqp",
      "queue": "orchestrator.commands"
    }
  },
  "status": {
    "phase": "Running",
    "conditions": [
      {"type": "Ready", "status": "True", "lastTransitionTime": "2025-12-15T09:00:30Z"}
    ],
    "lease": {
      "holderIdentity": "orchestrator-main",
      "renewTime": "2025-12-15T10:20:00Z",
      "leaseDurationSeconds": 30
    },
    "currentTasks": 47
  }
}
```

### 7.3. Storage Node

```json
{
  "metadata": {
    "uid": "storage-minio-01-uuid",
    "name": "storage-minio-01",
    "nodeType": "storage",
    "labels": {
      "role": "storage",
      "capability.object_storage": "true",
      "capability.s3_api": "true",
      "zone": "eu-west-1"
    },
    "creationTimestamp": "2025-12-15T08:00:00Z",
    "version": "1.0.0"
  },
  "spec": {
    "nodeType": "storage",
    "capabilities": [
      {
        "name": "object_storage",
        "version": "1.0",
        "parameters": {
          "protocols": ["s3"],
          "max_object_size": "5TB",
          "versioning": true
        }
      }
    ],
    "resources": {
      "limits": {
        "storage": "100Ti",
        "iops": 50000
      }
    },
    "endpoint": {
      "protocol": "http",
      "url": "https://minio-01.ai-team.internal:9000"
    }
  },
  "status": {
    "phase": "Running",
    "conditions": [
      {"type": "Ready", "status": "True", "lastTransitionTime": "2025-12-15T08:00:30Z"},
      {"type": "DiskSpace", "status": "True", "lastTransitionTime": "2025-12-15T08:00:30Z", "message": "45Ti / 100Ti used"}
    ],
    "lease": {
      "holderIdentity": "storage-minio-01",
      "renewTime": "2025-12-15T10:20:00Z",
      "leaseDurationSeconds": 30
    }
  }
}
```

---

## 8. Валидация паспорта

### 8.1. Обязательные проверки (Registry Service)

**При получении node.registered**:

1. ✅ **Схема валидна** (JSON Schema для NODE PASSPORT)
2. ✅ **Обязательные поля заполнены**:
   - `metadata.uid`, `metadata.name`, `metadata.nodeType`
   - `spec.nodeType`, `spec.capabilities`, `spec.endpoint`
   - `status.phase`, `status.conditions`, `status.lease`
3. ✅ **UID уникален** (нет дубликатов в реестре)
4. ✅ **Name уникален** (нет дубликатов в реестре)
5. ✅ **Labels корректны** (lowercase, valid characters)
6. ✅ **Lease корректен** (`leaseDurationSeconds > 0`, `renewTime` not too old)

**Если валидация провалена**:
```json
{
  "type": "node.registered.error",
  "data": {
    "nodeId": "550e8400-e29b-41d4-a716-446655440000",
    "error": "ValidationError",
    "details": "Field metadata.uid is required but missing"
  }
}
```

### 8.2. JSON Schema для валидации

(Полная схема будет в отдельном файле `NODE_PASSPORT_SCHEMA.json`)

**Основные правила**:
- `metadata.uid`: UUID v4 формат
- `metadata.name`: lowercase, alphanumeric + `-`, max 63 chars
- `labels`: key/value max 253/63 chars, lowercase
- `phase`: enum ["Pending", "Running", "Terminating", "Failed"]
- `conditions[].status`: enum ["True", "False", "Unknown"]
- `lease.renewTime`: ISO 8601 timestamp, not older than `leaseDurationSeconds * 2`

---

## 9. Мониторинг и Health Checks

### 9.1. Как Registry определяет мёртвые узлы?

**Алгоритм**:

```python
def is_node_alive(node_passport):
    lease = node_passport["status"]["lease"]
    now = datetime.utcnow()
    renew_time = parse_iso8601(lease["renewTime"])
    lease_duration = lease["leaseDurationSeconds"]

    time_since_renew = (now - renew_time).total_seconds()

    if time_since_renew > lease_duration:
        return False  # Node считается мёртвым
    else:
        return True   # Node живой
```

**Действия Registry при обнаружении мёртвого узла**:

1. Изменить `status.phase` → `Failed`
2. Добавить condition: `{"type": "Ready", "status": "False", "reason": "LeaseExpired"}`
3. Опубликовать event: `node.unhealthy`
4. (Опционально) Удалить узел из активных через N минут

### 9.2. Health Check Events

**Event Types**:

| Event Type | Когда публикуется | Кто публикует |
|------------|-------------------|---------------|
| `node.healthy` | Узел прошёл health check | Registry (после проверки Lease) |
| `node.unhealthy` | Lease истёк | Registry |
| `node.recovered` | Узел восстановился после сбоя | Registry (если Lease обновился после unhealthy) |

---

## 10. Расширения и будущие улучшения

### 10.1. Что НЕ вошло в v1.0 (но можно добавить)

**Возможные расширения**:

1. **Node Groups** — группировка узлов (аналог Kubernetes ReplicaSets)
2. **Affinity/Anti-affinity** — правила размещения задач
3. **Taints and Tolerations** — исключение узлов из маршрутизации
4. **Resource Quotas** — лимиты на потребление ресурсов
5. **Priority Classes** — приоритеты узлов
6. **Custom Metrics** — кастомные метрики в status (CPU usage, GPU load, etc.)
7. **Admission Webhooks** — валидация паспортов через внешние сервисы

### 10.2. Backward Compatibility

**Правило**: При добавлении новых полей в паспорт:
- ✅ Новые поля ОПЦИОНАЛЬНЫЕ (не ломают старые узлы)
- ✅ Версия паспорта увеличивается: `v1.0` → `v1.1` (minor)
- ✅ Breaking changes → новая major версия: `v2.0`

**Пример эволюции**:

```
v1.0 → Текущая версия (базовый паспорт)
v1.1 → Добавлены Custom Metrics в status (опционально)
v1.2 → Добавлены Taints в spec (опционально)
v2.0 → Изменена структура capabilities (breaking change)
```

---

## 11. Связь с другими спецификациями

### 11.1. Зависимости

**NODE PASSPORT** базируется на:

1. **MindBus Protocol v1.0** (`docs/SSOT/mindbus_protocol_v1.md`)
   - Использует RabbitMQ (AMQP) для передачи паспортов
   - Использует CloudEvents формат для events

2. **CloudEvents v1.0** (https://github.com/cloudevents/spec)
   - Формат всех events: `node.registered`, `node.*.updated`, etc.

3. **Kubernetes API Conventions** (https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md)
   - Паттерны: metadata/spec/status, labels/selectors, conditions, leases

### 11.2. Связанные документы

- **[READY_MADE_FIRST.md](../project/principles/READY_MADE_FIRST.md)** — принцип "готовые решения первичны"
- **[mindbus_protocol_v1.md](mindbus_protocol_v1.md)** — протокол шины данных (тот же каталог SSOT)
- **[CLAUDE.md](../../CLAUDE.md)** — правила разработки (SSOT, Zero Hardcoding)
- **[PROJECT_OVERVIEW.md](../../PROJECT_OVERVIEW.md)** — концепция проекта

---

## Финальное резюме

**NODE PASSPORT v1.0** — это:

✅ **Проверенная архитектура** (Kubernetes API Object Model, 15+ лет production)
✅ **Полная спецификация** (готова к имплементации)
✅ **SSOT compliant** (будет основой для schemas в `docs/SSOT/`)
✅ **Расширяемая** (легко добавлять новые поля без breaking changes)
✅ **Production-grade** (Lease mechanism используется в миллионах узлов)

**Следующий шаг**: Имплементация Registry Service (Python) с поддержкой NODE PASSPORT v1.0.

---

**Версия**: 1.0
**Дата**: 2025-12-15
**Авторы**: AI_TEAM Core Team
**Статус**: ✅ Утверждено (Final Release)
