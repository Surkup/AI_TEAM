# Configuration Management: YAML + Pydantic

**Статус:** ✅ УТВЕРЖДЕНО
**Последнее обновление:** 2025-12-15

**Примечание:** Конфигурация охватывает Node Passports и Process Cards

---

## Решение

**Выбрано: YAML файлы + Pydantic валидация**

---

## Почему YAML + Pydantic?

### Принцип: Zero Hardcoding

**Вся конфигурация в файлах, не в коде:**

```yaml
# config/agents.yaml
agents:
  - name: "writer"
    role: "writer"
    llm_model: "gpt-4"
    temperature: 0.7
    max_tokens: 2000
    prompt_template: "prompts/writer.txt"

  - name: "critic"
    role: "critic"
    llm_model: "claude-3-opus-20240229"
    temperature: 0.3
    max_tokens: 1500
    prompt_template: "prompts/critic.txt"
```

### Pydantic валидация = SSOT

```python
from pydantic import BaseModel, Field
from typing import Literal

class AgentConfig(BaseModel):
    """SSOT для конфигурации агента"""
    name: str
    role: Literal["writer", "critic", "editor", "researcher"]
    llm_model: str
    temperature: float = Field(ge=0.0, le=2.0)
    max_tokens: int = Field(gt=0, le=32000)
    prompt_template: str

# Загрузка и валидация
import yaml

with open("config/agents.yaml") as f:
    config_data = yaml.safe_load(f)

agents = [AgentConfig(**agent) for agent in config_data["agents"]]
# Если конфиг невалиден → Pydantic выдаст ошибку
```

**Преимущества:**
- ✅ Type safety
- ✅ Автоматическая валидация
- ✅ Понятные ошибки
- ✅ IDE autocomplete

---

## Структура конфигов

```
config/
├── llm.yaml             # LLM settings
├── mindbus.yaml         # RabbitMQ/MindBus settings
├── database.yaml        # PostgreSQL settings
├── storage.yaml         # MinIO settings (опционально)
├── registry.yaml        # etcd/Consul settings
└── node_passports/      # Node Passport declarations
    ├── writer-001.yaml
    ├── critic-001.yaml
    └── orchestrator.yaml

process_cards/           # Process Card definitions
├── article_creation.yaml
├── code_generation.yaml
└── research.yaml

prompts/
├── writer.txt
├── critic.txt
└── editor.txt
```

---

## Примеры конфигов

### config/llm.yaml
```yaml
llm:
  default_model: "gpt-4"
  fallback_models:
    - "claude-3-opus-20240229"
    - "gpt-3.5-turbo"
  temperature: 0.7
  max_tokens: 2000
  timeout: 60
  num_retries: 3
  cache_ttl: 3600
  budget:
    max_cost_per_task: 0.50
    max_cost_per_day: 10.00
```

### process_cards/article_creation.yaml (Process Card SSOT)
```yaml
apiVersion: ai-team.dev/v1
kind: ProcessCard

metadata:
  id: "550e8400-e29b-41d4-a716-446655440000"
  name: "article_creation"
  version: "1.0"

spec:
  variables:
    topic: ""
    quality_threshold: 8.0
    draft: ""
    critique: {}

  steps:
    - id: "step_write"
      action: "write_article"  # ← capability name
      params:
        topic: ${input.topic}
      output: draft

    - id: "step_critique"
      action: "critique_article"
      params:
        draft: ${draft}
      output: critique

    - id: "step_decision"
      condition: "${critique.score} >= ${quality_threshold}"
      then: "step_publish"
      else: "step_write"  # Повторяем
```

### config/node_passports/writer-001.yaml (Node Passport SSOT)
```yaml
apiVersion: ai-team.dev/v1
kind: NodePassport

metadata:
  name: "writer-001"
  namespace: "ai-team"
  labels:
    role: "writer"

spec:
  type: "agent"
  capabilities:
    - name: "write_article"
      input_schema:
        topic: string
      output_schema:
        article: string

  communication:
    mindbus_queue: "agent.writer.001"
    mindbus_routing_key: "cmd.writer.#"

  resources:
    llm_model: "gpt-4"
```

---

## Environment Variables

**Секреты через переменные окружения:**

```yaml
# config/llm.yaml
llm:
  api_keys:
    openai: ${OPENAI_API_KEY}
    anthropic: ${ANTHROPIC_API_KEY}
```

```python
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Environment variables"""
    openai_api_key: str
    anthropic_api_key: str
    database_url: str
    redis_url: str

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## Итоговое решение

**YAML + Pydantic:**

1. ✅ Zero hardcoding
2. ✅ Type safety
3. ✅ Human-readable (YAML)
4. ✅ Validation из коробки

---

**Примечание:** Конфигурация охватывает все компоненты системы:
- Process Cards (декларативные процессы)
- Node Passports (паспорта узлов)
- LLM settings, MindBus, Database, etc.

**Статус:** ✅ УТВЕРЖДЕНО
**Последнее обновление:** 2025-12-15
