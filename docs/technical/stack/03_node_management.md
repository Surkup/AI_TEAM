# Node Management: Node Passport + Node Registry

**Статус:** ✅ УТВЕРЖДЕНО
**Последнее обновление:** 2025-12-15

---

## Что такое Node Management?

**Node Management** — это система регистрации и поиска узлов (agents, components, services) в AI_TEAM.

**Ключевые компоненты:**
1. **Node Passport** — декларативный паспорт узла (что умеет, как с ним общаться)
2. **Node Registry** — централизованный реестр всех узлов (Service Discovery)

**Философия**: Kubernetes-inspired подход к управлению узлами.

---

## Философия: Готовые решения первичны

Мы **НЕ изобретаем** Service Discovery с нуля. Используем проверенные паттерны:

1. **Node Passport** — формат по образцу Kubernetes API Objects (`metadata` / `spec` / `status`)
2. **Node Registry** — etcd или Consul (проверенные Service Discovery решения)

**Полные технические спецификации:**
- [NODE_PASSPORT_SPEC_v1.0.md](../../SSOT/NODE_PASSPORT_SPEC_v1.0.md)
- [NODE_REGISTRY_SPEC_v1.0.md](../../SSOT/NODE_REGISTRY_SPEC_v1.0.md)

---

## Node Passport — декларативный паспорт узла

**Концепция:** Каждый узел (agent, orchestrator, component) описывает себя через YAML-файл.

**Пример паспорта Writer агента:**

```yaml
# node_passport.yaml
apiVersion: ai-team.dev/v1
kind: NodePassport

metadata:
  name: "writer-001"
  namespace: "ai-team"
  labels:
    role: "writer"
    team: "content"
  annotations:
    description: "Пишет статьи и контент"

spec:
  type: "agent"
  version: "1.0.0"

  capabilities:
    - name: "write_article"
      description: "Написание статей"
      input_schema:
        topic: string
        style: string
      output_schema:
        article: string
        metadata: object

    - name: "edit_text"
      description: "Редактирование текста"
      input_schema:
        text: string
      output_schema:
        edited_text: string

  communication:
    mindbus_queue: "agent.writer.001"
    mindbus_routing_key: "cmd.writer.#"

  resources:
    llm_model: "gpt-4"
    max_concurrent_tasks: 3

status:
  state: "ready"
  registered_at: "2025-12-15T10:00:00Z"
  last_heartbeat: "2025-12-15T10:05:00Z"
```

**Ключевые секции:**
- `metadata` — идентификация узла (name, namespace, labels)
- `spec` — спецификация узла (capabilities, communication, resources)
- `status` — текущее состояние (ready/busy/offline, heartbeat)

**Kubernetes-inspired структура** — проверенный паттерн для описания ресурсов.

---

## Node Registry — Service Discovery

**Концепция:** Центра льный реестр, где все узлы регистрируются и могут быть найдены.

**Технология:** etcd или Consul

### Почему etcd/Consul?

✅ **Battle-tested**: Kubernetes использует etcd для Service Discovery
✅ **Key-Value Store**: Простое хранение паспортов (key = node name, value = passport YAML)
✅ **Watch API**: Автоматическое уведомление при изменениях
✅ **Health Checks**: Встроенный TTL и heartbeat
✅ **Готовые библиотеки**: python-etcd3, python-consul

### Как это работает

```python
# 1. Agent регистрируется в Registry при старте
import etcd3

etcd = etcd3.client(host='localhost', port=2379)

# Загружаем паспорт
with open('node_passport.yaml') as f:
    passport = yaml.safe_load(f)

# Регистрируем в etcd
key = f"/ai-team/nodes/{passport['metadata']['namespace']}/{passport['metadata']['name']}"
etcd.put(key, yaml.dump(passport))

# Устанавливаем TTL (heartbeat)
lease = etcd.lease(ttl=30)  # 30 секунд
etcd.put(key, yaml.dump(passport), lease=lease)

# 2. Orchestrator находит узлы по capability
def find_nodes_by_capability(capability_name):
    """Находит все узлы с нужной capability"""
    nodes = []

    for value, metadata in etcd.get_prefix('/ai-team/nodes/'):
        passport = yaml.safe_load(value.decode('utf-8'))

        # Проверяем capabilities
        for cap in passport['spec'].get('capabilities', []):
            if cap['name'] == capability_name:
                nodes.append(passport)
                break

    return nodes

# Поиск
writers = find_nodes_by_capability('write_article')
print(f"Found {len(writers)} writer nodes")

# 3. Отправка команды найденному узлу
target_node = writers[0]
mindbus_queue = target_node['spec']['communication']['mindbus_queue']

# Отправляем через MindBus
mindbus.send_command(
    queue=mindbus_queue,
    action='write_article',
    params={'topic': 'AI trends 2025'}
)
```

---

## Capability-Based Routing

**Проблема:** Как оркестратору найти подходящий агент для задачи?

**Решение:** Capability-based routing

**Вместо:**
```python
# ❌ Hardcoded agent names
send_command(agent_name='writer-001', action='write_article')
```

**Делаем:**
```python
# ✅ Capability-based search
nodes = registry.find_by_capability('write_article')
target = select_best_node(nodes)  # Load balancing
send_command(queue=target.mindbus_queue, action='write_article')
```

**Преимущества:**
- ✅ Агенты добавляются/удаляются динамически
- ✅ Автоматический load balancing (выбираем узел с наименьшей нагрузкой)
- ✅ Failover (если узел offline, выбираем другой)
- ✅ Масштабирование (добавили новых writer → автоматически включаются в rotation)

---

## Интеграция с Process Cards

**Process Card описывает ЧТО** делать:

```yaml
# Process Card
steps:
  - id: "step_write"
    action: "write_article"  # ← Capability name
    params:
      topic: ${input.topic}
```

**Orchestrator находит КТО** может это сделать:

```python
# Orchestrator
capability = step['action']  # "write_article"
nodes = registry.find_by_capability(capability)

if not nodes:
    raise NoCapableNodesError(f"No nodes with capability: {capability}")

# Выбираем узел (load balancing)
target = select_least_loaded(nodes)

# Отправляем команду через MindBus
mindbus.send_command(
    queue=target.mindbus_queue,
    action=capability,
    params=step['params']
)
```

**Разделение ответственности:**
- **Process Card** — WHAT (какую задачу)
- **Orchestrator** — WHO (какой узел) + HOW (как выполнить)
- **Node Registry** — WHERE (где найти узлы)

---

## Heartbeat и Health Checks

**Проблема:** Как узнать, что агент alive или crashed?

**Решение:** TTL + Heartbeat

```python
# Agent отправляет heartbeat каждые 10 секунд
import time

lease = etcd.lease(ttl=30)  # Умрёт через 30 сек без обновления

while True:
    # Обновляем status
    passport['status']['last_heartbeat'] = datetime.utcnow().isoformat() + 'Z'
    passport['status']['state'] = 'ready'

    # Обновляем в etcd (с lease)
    etcd.put(key, yaml.dump(passport), lease=lease)

    # Heartbeat раз в 10 секунд
    time.sleep(10)
```

**Orchestrator проверяет health:**

```python
def is_node_healthy(passport):
    """Проверяет живой ли узел"""
    last_heartbeat = datetime.fromisoformat(
        passport['status']['last_heartbeat'].replace('Z', '+00:00')
    )

    age = datetime.now(timezone.utc) - last_heartbeat

    # Мёртв если нет heartbeat > 1 минуты
    return age.total_seconds() < 60

# Фильтруем только здоровые узлы
writers = find_nodes_by_capability('write_article')
healthy_writers = [n for n in writers if is_node_healthy(n)]
```

---

## Docker Compose для MVP

```yaml
version: '3.8'

services:
  # etcd
  etcd:
    image: quay.io/coreos/etcd:v3.5
    environment:
      - ETCD_ADVERTISE_CLIENT_URLS=http://0.0.0.0:2379
      - ETCD_LISTEN_CLIENT_URLS=http://0.0.0.0:2379
    ports:
      - "2379:2379"
    volumes:
      - etcd-data:/etcd-data

  # Agent (example)
  agent-writer:
    build: ./agents/writer
    environment:
      - ETCD_HOST=etcd
      - ETCD_PORT=2379
      - RABBITMQ_HOST=rabbitmq
    depends_on:
      - etcd
      - rabbitmq
    volumes:
      - ./config/node_passports/writer-001.yaml:/app/node_passport.yaml

volumes:
  etcd-data:
```

---

## Альтернативы

### Consul (вместо etcd)
**Можно использовать**, разница минимальна:

```python
# С Consul API почти то же самое
import consul

c = consul.Consul(host='localhost', port=8500)
c.kv.put(key, yaml.dump(passport))
```

**Выбор между etcd/Consul:**
- **etcd** — если планируете Kubernetes (уже используется)
- **Consul** — если нужен встроенный Service Mesh

🔄 **LEGO-принцип**: Легко мигрировать между etcd и Consul.

### Zookeeper
**Почему НЕТ:**
- ❌ Более сложная настройка
- ❌ Java-based (тяжелее для Python проекта)
- ❌ etcd/Consul более популярны в Cloud Native экосистеме

---

## Итоговое решение

**Node Passport + Node Registry (etcd/Consul) — правильный выбор:**

1. ✅ **Kubernetes-inspired** паттерн (metadata/spec/status)
2. ✅ **Capability-based routing** (агенты находятся по "что умеют")
3. ✅ **Battle-tested** Service Discovery (etcd используется в Kubernetes)
4. ✅ **Динамическая регистрация** (узлы добавляются/удаляются на лету)
5. ✅ **Health checks** (TTL + heartbeat)
6. ✅ **Load balancing** (выбор наименее загруженного узла)
7. 🔄 **LEGO-модульность** — легко заменить etcd на Consul или Zookeeper

**Разделение ответственности:**
- **Node Passport** — декларация узла (YAML)
- **Node Registry** — хранилище паспортов (etcd/Consul)
- **Orchestrator** — поиск узлов по capabilities
- **MindBus** — коммуникация с найденными узлами

**Node Management = Service Discovery для AI_TEAM** ✅

---

**Статус:** ✅ УТВЕРЖДЕНО
**Технические спецификации:**
- [NODE_PASSPORT_SPEC_v1.0.md](../../SSOT/NODE_PASSPORT_SPEC_v1.0.md)
- [NODE_REGISTRY_SPEC_v1.0.md](../../SSOT/NODE_REGISTRY_SPEC_v1.0.md)

**Последнее обновление**: 2025-12-15
