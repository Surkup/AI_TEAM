# Configuration Management: YAML + Pydantic


---

# ⚠️ ЧЕРНОВИК — ТРЕБУЕТ ПРОВЕРКИ ⚠️

**Этот документ НЕ является финальным решением!**

Требуется детальный анализ, критика и проверка перед принятием решений.

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
├── agents.yaml          # Конфигурация агентов
├── llm.yaml             # LLM settings
├── mindbus.yaml         # Redis/MindBus settings
├── database.yaml        # PostgreSQL settings
├── storage.yaml         # MinIO settings
└── process_cards/       # Workflow definitions
    ├── article.yaml
    ├── research.yaml
    └── social_media.yaml

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

### config/process_cards/article.yaml
```yaml
process_card:
  name: "article_creation"
  description: "Write high-quality article"

  quality_threshold: 8.0
  max_iterations: 10

  steps:
    - agent: "researcher"
      task: "research_topic"
      timeout: 300

    - agent: "writer"
      task: "write_draft"
      timeout: 300

    - agent: "critic"
      task: "critique"
      timeout: 180

    - agent: "editor"
      task: "final_edit"
      timeout: 180
      condition: "quality_score >= 8.0"
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

**Статус:** 📝 ЧЕРНОВИК (требует проверки и утверждения)
**Последнее обновление:** 2025-12-13
