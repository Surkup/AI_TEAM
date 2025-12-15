# Язык программирования: Python 3.11+

**Статус:** ✅ УТВЕРЖДЕНО
**Последнее обновление:** 2025-12-15

---

## Решение

**Выбран: Python 3.11+**

---

## Почему Python?

### 1. Стандарт для AI/ML (AI/ML Standard)

**Факт:** 99% LLM SDK написаны для Python в первую очередь.

**Библиотеки, которые нам нужны:**
- ✅ `openai` — OpenAI API
- ✅ `anthropic` — Claude API
- ✅ `langchain` — утилиты для промптов, парсинг
- ✅ `litellm` — unified LLM interface
- ✅ `transformers` — HuggingFace models (если локальные)

**Все эти библиотеки:**
- Python = first-class support
- Node.js = второй сорт или нет вообще
- Go/Rust = почти нет

**Простыми словами:**
> Писать AI-систему не на Python — это как строить дом без молотка. Технически возможно, но зачем усложнять?

---

### 2. Быстрая разработка MVP (Rapid Development)

**Мы на этапе MVP** → скорость итераций критична.

**Python позволяет:**
```python
# Пример: создать агента за 10 строк
from litellm import completion

class WriterAgent:
    def write(self, topic):
        response = completion(
            model="gpt-4",
            messages=[{"role": "user", "content": f"Write about {topic}"}]
        )
        return response.choices[0].message.content

# Готово! Работает.
```

**На Go это было бы 50+ строк** (структуры, error handling, etc.)

**Преимущество:**
- Быстрее тестировать идеи
- Легче менять архитектуру
- Меньше boilerplate кода

---

### 3. Type Hints + Pydantic = SSOT в коде

**С Python 3.11+ есть строгая типизация:**

```python
from pydantic import BaseModel, Field
from typing import Literal

class Message(BaseModel):
    """SSOT definition for MindBus message"""
    id: str
    type: Literal["COMMAND", "RESULT", "EVENT"]
    from_agent: str = Field(alias="from")
    to_agent: str = Field(alias="to")
    trace_id: str
    payload: dict

# Pydantic автоматически валидирует
message = Message(
    id="msg-123",
    type="COMMAND",  # Если написать "CMD" — ошибка!
    from_agent="orchestrator",
    to_agent="writer",
    trace_id="task-456",
    payload={"action": "write"}
)
```

**Это идеально для нашего принципа Specification-Driven Development:**
- SSOT определяется в Pydantic моделях
- Код не может нарушить спецификацию
- Автоматическая валидация

---

### 4. Async Support (Python 3.11+)

**Нам нужна асинхронность** для:
- Параллельные вызовы LLM (несколько агентов одновременно)
- WebSocket для real-time Monitor UI
- Обработка множества сообщений в MindBus

**Python 3.11+ async/await:**
```python
import asyncio

async def execute_agents_parallel():
    # Запускаем 3 агента одновременно
    writer_task = writer_agent.write("AI trends")
    critic_task = critic_agent.critique("AI trends")
    researcher_task = researcher_agent.research("AI trends")

    # Ждем все вместе
    results = await asyncio.gather(
        writer_task,
        critic_task,
        researcher_task
    )
    return results
```

**Производительность:**
- Python async близко к Node.js по скорости
- Для I/O-bound задач (вызовы API) — идеально
- FastAPI построен на async (самый быстрый Python web framework)

---

### 5. Огромное сообщество

**Статистика:**
- Python = #1 язык для AI/ML (Stack Overflow Survey 2024)
- 15+ миллионов разработчиков
- Любой вопрос найдет ответ на Stack Overflow за минуты

**Это критично для MVP:**
- Быстрее решать проблемы
- Больше готовых примеров
- Легче нанять разработчиков (если потребуется)

---

## Альтернативы и почему НЕТ

### Node.js / TypeScript

**Плюсы:**
- Async из коробки
- JSON-native (удобно для API)
- Быстрый для веб-приложений

**Почему НЕТ:**
- ❌ Слабая AI/ML экосистема
  - Нет LangChain (есть LangChain.js но хуже)
  - OpenAI SDK хороший, но Anthropic, Google — слабее
  - Нет Transformers, нет локальных моделей
- ❌ Async сложнее отлаживать (callback hell даже с async/await)
- ❌ Меньше примеров AI-систем на Node.js

**Вердикт:** Node.js отличен для веб, но не для AI orchestration.

---

### Go

**Плюсы:**
- Очень быстрый
- Простой concurrency (goroutines)
- Статическая типизация
- Хорош для инфраструктуры (Kubernetes написан на Go)

**Почему НЕТ:**
- ❌ Почти нет AI/ML библиотек
  - Нет LangChain
  - Нет нормальных LLM SDK (только REST API вручную)
  - Нет Pydantic-like валидации
- ❌ Overkill для MVP
  - Больше boilerplate
  - Медленнее разработка
- ❌ Мало примеров AI-систем на Go

**Вердикт:** Go отличен для infrastructure tools (Redis, Docker), но не для AI orchestration.

---

### Rust

**Плюсы:**
- Максимальная скорость
- Memory safety без garbage collector
- Отличен для performance-critical систем

**Почему НЕТ:**
- ❌ Крутая кривая обучения (сложный язык)
- ❌ Почти нет AI/ML экосистемы
- ❌ Очень медленная разработка (vs Python)
- ❌ Огромный overkill для MVP

**Вердикт:** Rust для системного программирования, не для AI MVP.

---

## Что говорят люди?

### Успешные AI-проекты на Python:

**LangChain:**
> "We chose Python because that's where the AI community is."

**CrewAI:**
> "Python allows us to iterate fast and leverage the entire ML ecosystem."

**OpenAI (ChatGPT backend):**
> Stack includes Python + FastAPI for orchestration

### Проблемы, о которых пишут:

**Проблема 1: Performance**
> "Python медленный для CPU-intensive задач"

**Наш случай:**
- Мы I/O-bound (ждем API ответы)
- Python async достаточно быстрый для I/O
- Узкие места = LLM API, не наш код

**Проблема 2: GIL (Global Interpreter Lock)**
> "Python не может использовать несколько CPU cores"

**Наш случай:**
- Async решает для I/O-bound
- Если нужно CPU — запустим несколько процессов
- Для MVP это не проблема

**Проблема 3: Packaging сложный**
> "Python packaging — это ад (pip, conda, poetry...)"

**Решение:**
- Docker решает проблему окружения
- Poetry для dev зависимостей
- Для пользователя — Docker image, не надо ничего ставить

---

## Версия: Python 3.11+

**Почему 3.11+, а не 3.10 или 3.9?**

**Python 3.11 преимущества:**
- ✅ **10-60% быстрее** чем 3.10 (PEP 659)
- ✅ **Лучшие error messages** (PEP 657)
- ✅ **tomllib** встроен (парсинг TOML)
- ✅ **ExceptionGroup** для множественных ошибок

**Python 3.12 (опционально):**
- Еще быстрее
- f-string improvements
- Но 3.11 уже достаточно stable

**Минимальная версия:** 3.11
**Рекомендуемая:** 3.11 или 3.12

---

## Инструменты разработки

### Poetry (Dependency Management)

**Зачем:**
- Управление зависимостями
- Виртуальные окружения
- Lockfile для воспроизводимости

**Установка:**
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

**Использование:**
```bash
poetry init
poetry add fastapi redis pydantic
poetry install  # Установить все зависимости
poetry run python main.py
```

### Ruff (Linter + Formatter)

**Зачем:**
- Проверка стиля кода
- Автоформатирование
- Находит баги
- **Очень быстрый** (написан на Rust)

**Конфиг:**
```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I"]  # errors, flake8, imports
```

### mypy (Type Checking)

**Зачем:**
- Проверка типов статически
- Ловит ошибки до запуска

**Пример:**
```python
def process(message: Message) -> Result:
    # mypy проверит, что возвращаем Result, не str
    return Result(status="done")
```

---

## Примеры кода для AI_TEAM

### Message Handling
```python
from typing import Literal
from pydantic import BaseModel

class Message(BaseModel):
    id: str
    type: Literal["COMMAND", "RESULT", "EVENT"]
    from_agent: str
    to_agent: str
    trace_id: str
    payload: dict

def handle_message(msg: Message):
    match msg.type:
        case "COMMAND":
            execute_command(msg)
        case "RESULT":
            process_result(msg)
        case "EVENT":
            log_event(msg)
```

### Async Agent Execution
```python
import asyncio
from litellm import acompletion

class Agent:
    async def execute(self, prompt: str) -> str:
        response = await acompletion(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

# Запуск нескольких агентов параллельно
async def orchestrate():
    agents = [WriterAgent(), CriticAgent(), EditorAgent()]
    results = await asyncio.gather(*[agent.execute("task") for agent in agents])
    return results
```

---

## Итоговое решение

**Python 3.11+** — единственный разумный выбор для AI_TEAM потому что:

1. ✅ Стандарт для AI/ML (все библиотеки здесь)
2. ✅ Быстрая разработка MVP
3. ✅ Type hints + Pydantic = SSOT
4. ✅ Async для параллельности
5. ✅ Огромное сообщество

**Альтернативы отклонены:**
- Node.js — нет AI экосистемы
- Go — нет AI библиотек, overkill
- Rust — слишком сложно для MVP

**Риски минимальны:**
- Performance — не проблема для I/O-bound
- GIL — async решает
- Packaging — Docker решает

---

**Статус:** 📝 ЧЕРНОВИК (требует проверки и утверждения)
**Последнее обновление:** 2025-12-13
