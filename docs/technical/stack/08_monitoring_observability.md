# Monitoring & Observability: OpenTelemetry + Prometheus + Grafana


---

# ⚠️ ЧЕРНОВИК — ТРЕБУЕТ ПРОВЕРКИ ⚠️

**Этот документ НЕ является финальным решением!**

Требуется детальный анализ, критика и проверка перед принятием решений.

---
## Решение

**Выбрано:**
- **OpenTelemetry** — unified observability (traces, metrics, logs)
- **Prometheus** — metrics storage & alerting
- **Grafana** — visualization

---

## Почему это важно для AI_TEAM?

### Принцип: Observability-first

**Каждое сообщение имеет trace_id:**
```python
message = Message(
    id="msg-123",
    type="COMMAND",
    from_agent="orchestrator",
    to_agent="writer",
    trace_id="task-456",  # ← Сквозной ID
    payload={}
)
```

**trace_id проходит через:**
1. MindBus message
2. LLM call
3. Database запись
4. Artifact storage
5. Все логи

**Результат:** Можем проследить всю историю задачи.

---

## OpenTelemetry: Unified Observability

### Что такое OpenTelemetry?

**3 типа данных:**
1. **Traces** — путь запроса через систему
2. **Metrics** — числовые показатели (latency, tokens, cost)
3. **Logs** — текстовые события

**OpenTelemetry = vendor-neutral стандарт.**

---

### Tracing пример

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Инициализация
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# В Orchestrator
class Orchestrator:
    async def execute_task(self, task_config: dict, trace_id: str):
        # Создаем span для всей задачи
        with tracer.start_as_current_span(
            "execute_task",
            attributes={
                "trace_id": trace_id,
                "task_type": task_config["type"]
            }
        ) as span:

            # Writer agent
            with tracer.start_as_current_span("writer_agent"):
                draft = await self.call_agent("writer", task_config, trace_id)

            # Critic agent
            with tracer.start_as_current_span("critic_agent"):
                critique = await self.call_agent("critic", draft, trace_id)

            span.set_attribute("quality_score", critique["quality_score"])

            return draft
```

**Visualize в Grafana/Jaeger:**
```
Task execution (10.5s)
  ├─ writer_agent (7.2s)
  │   ├─ llm_call (6.8s)
  │   └─ save_artifact (0.4s)
  └─ critic_agent (3.3s)
      └─ llm_call (3.1s)
```

---

## Prometheus: Metrics

### Ключевые метрики для AI_TEAM

```python
from prometheus_client import Counter, Histogram, Gauge

# Счетчики
tasks_total = Counter(
    'ai_team_tasks_total',
    'Total tasks processed',
    ['status']  # pending, completed, failed
)

llm_calls_total = Counter(
    'ai_team_llm_calls_total',
    'Total LLM calls',
    ['model', 'agent']
)

# Гистограммы (для latency)
task_duration = Histogram(
    'ai_team_task_duration_seconds',
    'Task execution duration',
    ['task_type']
)

llm_latency = Histogram(
    'ai_team_llm_latency_seconds',
    'LLM call latency',
    ['model']
)

# Gauge (текущее значение)
tasks_in_progress = Gauge(
    'ai_team_tasks_in_progress',
    'Tasks currently executing'
)

quality_score = Histogram(
    'ai_team_quality_score',
    'Quality score distribution',
    buckets=[0, 2, 4, 6, 8, 10]
)

llm_cost = Counter(
    'ai_team_llm_cost_dollars',
    'Total LLM cost in USD',
    ['model']
)
```

### Использование

```python
class Orchestrator:
    async def execute_task(self, task_config, trace_id):
        tasks_in_progress.inc()
        tasks_total.labels(status='pending').inc()

        start_time = time.time()

        try:
            result = await self._execute(task_config, trace_id)

            # Метрики успеха
            tasks_total.labels(status='completed').inc()
            quality_score.observe(result["quality_score"])

        except Exception as e:
            tasks_total.labels(status='failed').inc()
            raise

        finally:
            duration = time.time() - start_time
            task_duration.labels(task_type=task_config["type"]).observe(duration)
            tasks_in_progress.dec()
```

---

## Grafana: Visualization

### Dashboards для AI_TEAM

**Dashboard 1: Task Overview**
- Total tasks (по статусам)
- Tasks in progress
- Average task duration
- Quality score distribution

**Dashboard 2: LLM Metrics**
- LLM calls по моделям
- Average latency по моделям
- Total cost (по моделям)
- Token usage

**Dashboard 3: Agent Performance**
- Вызовов каждого агента
- Success rate
- Average quality score

---

## Полный стек observability

```yaml
# docker-compose.yml
version: '3.8'

services:
  # OpenTelemetry Collector
  otel-collector:
    image: otel/opentelemetry-collector:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317"  # OTLP gRPC
      - "4318:4318"  # OTLP HTTP

  # Prometheus
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  # Grafana
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana

volumes:
  grafana-data:
```

---

## Итоговое решение

**OpenTelemetry + Prometheus + Grafana:**

1. ✅ Industry standard (vendor-neutral)
2. ✅ trace_id сквозная трассировка
3. ✅ Метрики для всех компонентов
4. ✅ Visualization из коробки
5. ✅ Простая интеграция с Python

---

**Статус:** ✅ УТВЕРЖДЕНО
**Последнее обновление:** 2025-12-15
