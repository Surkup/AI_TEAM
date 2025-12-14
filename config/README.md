# Configuration Files

## 📋 Принцип: Zero Hardcoding

**Все параметры системы хранятся в YAML конфигах, НЕ в коде.**

Этот каталог содержит эталонные конфигурационные файлы для AI_TEAM проекта.

---

## 📁 Структура

```
config/
├── README.md              # Этот файл
├── redis.yaml             # Конфигурация Redis (кеш + rate limiting)
├── llm.yaml               # Конфигурация LLM (модели, параметры, бюджеты)
├── workflows.yaml         # Конфигурация Temporal workflows
├── api.yaml               # Конфигурация API Gateway (FastAPI)
└── agents/
    └── dummy_agent.yaml   # Конфигурация для DummyAgent
```

---

## 🔐 Секреты и переменные окружения

**НИКОГДА не храните секреты в YAML файлах!**

API ключи и пароли загружаются из переменных окружения:

```bash
# .env файл (НЕ коммитить в git!)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
REDIS_PASSWORD=your_password_here
```

В конфигах используйте плейсхолдеры:

```yaml
redis:
  password: "${REDIS_PASSWORD}"  # Загрузится из .env
```

---

## 🎯 Примеры использования

### Python

```python
import yaml
from pathlib import Path

def load_config(config_name: str) -> dict:
    """Загружает конфиг из config/{config_name}"""
    config_path = Path("config") / config_name
    with open(config_path) as f:
        return yaml.safe_load(f)

# Использование
llm_config = load_config("llm.yaml")
model = llm_config["llm"]["default_model"]  # "gpt-4"
```

### С Pydantic (рекомендуется)

```python
from pydantic import BaseModel
from typing import List
import yaml

class LLMConfig(BaseModel):
    default_model: str
    fallback_models: List[str]
    temperature: float
    # ... остальные поля

# Загрузка и валидация
with open("config/llm.yaml") as f:
    config_dict = yaml.safe_load(f)
    llm_config = LLMConfig(**config_dict["llm"])

# Все поля валидированы Pydantic!
```

---

## 🔧 Окружения (Environments)

Для разных окружений используйте разные конфиги:

```
config/
├── dev/
│   ├── llm.yaml        # Дешевые модели для разработки
│   └── redis.yaml      # localhost
├── staging/
│   ├── llm.yaml        # Тестовые модели
│   └── redis.yaml      # staging redis
└── production/
    ├── llm.yaml        # Production модели
    └── redis.yaml      # Production redis (с паролем)
```

Переключение через переменную окружения:

```python
import os

env = os.getenv("AI_TEAM_ENV", "dev")  # по умолчанию dev
config_path = Path("config") / env / "llm.yaml"
```

---

## ✅ Чек-лист перед коммитом

- [ ] Все параметры вынесены в конфиги (нет hardcoded значений в коде)
- [ ] Нет API ключей и паролей в YAML файлах
- [ ] Секреты используют плейсхолдеры `"${VAR_NAME}"`
- [ ] `.env` файл добавлен в `.gitignore`
- [ ] Есть `.env.example` с примером структуры (без реальных ключей)

---

## 📚 Связанные документы

- [CLAUDE.md](../CLAUDE.md) - Правила проекта (включая Zero Hardcoding)
- [README.md](../README.md) - Принципы системы
- [docs/technical/stack/10_configuration_management.md](../docs/technical/stack/10_configuration_management.md) - Детальная спецификация

---

**Помните**: Изменяя конфиг, вы меняете поведение системы БЕЗ изменения кода.
Это и есть Zero Hardcoding!
