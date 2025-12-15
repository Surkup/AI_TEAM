# LLM Integration: LiteLLM


---

# ⚠️ ЧЕРНОВИК — ТРЕБУЕТ ПРОВЕРКИ ⚠️

**Этот документ НЕ является финальным решением!**

Требуется детальный анализ, критика и проверка перед принятием решений.

---
## Решение

**Выбран: LiteLLM (unified interface)**

---

## Почему LiteLLM?

### 1. Единый интерфейс для всех LLM

**Проблема:** Каждый LLM провайдер имеет свой API:
- OpenAI → `openai.ChatCompletion.create()`
- Anthropic → `anthropic.messages.create()`
- Google → `google.generativeai.generate_content()`
- Cohere → `cohere.generate()`

**Решение LiteLLM:** Один интерфейс для всех

```python
from litellm import completion, acompletion

# OpenAI
response = completion(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)

# Anthropic (тот же код!)
response = completion(
    model="claude-3-opus-20240229",
    messages=[{"role": "user", "content": "Hello"}]
)

# Google (тот же код!)
response = completion(
    model="gemini-pro",
    messages=[{"role": "user", "content": "Hello"}]
)

# Cohere (тот же код!)
response = completion(
    model="command-r-plus",
    messages=[{"role": "user", "content": "Hello"}]
)
```

**Преимущество для AI_TEAM:**
- ✅ Меняем модель = меняем 1 строку в конфиге
- ✅ A/B тестирование разных моделей = легко
- ✅ Fallback (если GPT-4 недоступен → Claude) = встроено

---

### 2. Automatic Retry + Fallback

**LiteLLM встроенная устойчивость:**

```python
# Загружаем конфиг из config/llm.yaml
config = load_config("llm.yaml")

# Автоматический retry при ошибках (параметры из конфига)
response = completion(
    model=config["default_model"],
    messages=[{"role": "user", "content": "Hello"}],
    num_retries=config["num_retries"],  # Из конфига
    timeout=config["timeout"]  # Из конфига
)

# Fallback на другую модель (список из конфига)
response = completion(
    model=config["default_model"],
    messages=[{"role": "user", "content": "Hello"}],
    fallbacks=config["fallback_models"]  # Из конфига
)
# Если default_model недоступен → попробует модели из fallback_models
```

**Для AI_TEAM это критично:**
- Агенты не должны падать из-за временных проблем API
- Пользователь не должен ждать если один LLM медленный

---

### 3. Cost Tracking встроен

**LiteLLM автоматически считает стоимость:**

```python
import litellm

# Включаем tracking
litellm.success_callback = ["cost_tracking"]

response = completion(
    model="gpt-4",
    messages=[{"role": "user", "content": "Write an article"}]
)

# Получить стоимость вызова
cost = response._hidden_params.get("response_cost")
print(f"Cost: ${cost:.4f}")

# Статистика по всем вызовам
print(litellm.cost_tracker.get_total_cost())
# {'gpt-4': 0.35, 'claude-3-opus': 0.12}
```

**Преимущество:**
- ✅ Знаем сколько стоит каждая задача
- ✅ Можем показать пользователю стоимость
- ✅ Бюджетный контроль (остановить если превышен лимит)

---

### 4. Caching из коробки

**LiteLLM поддерживает кеш:**

```python
import litellm

# Загружаем конфиг Redis из config/redis.yaml
redis_config = load_config("redis.yaml")
llm_config = load_config("llm.yaml")

# Настраиваем Redis для кеша (параметры из конфига)
litellm.cache = litellm.Cache(
    type="redis",
    host=redis_config["host"],
    port=redis_config["port"],
    ttl=llm_config["cache_ttl"]  # Из конфига
)

# Первый вызов — реальный запрос к API
response1 = completion(
    model=llm_config["default_model"],
    messages=[{"role": "user", "content": "What is AI?"}],
    cache={"ttl": llm_config["cache_ttl"]}
)

# Второй вызов с тем же запросом — из кеша (бесплатно!)
response2 = completion(
    model=llm_config["default_model"],
    messages=[{"role": "user", "content": "What is AI?"}],
    cache={"ttl": llm_config["cache_ttl"]}
)

print(response2._hidden_params.get("cache_hit"))  # True
```

**Экономия для AI_TEAM:**
- ✅ Одинаковые запросы не тратят деньги
- ✅ Быстрее ответы (из кеша мгновенно)
- ✅ Меньше нагрузка на LLM API

---

### 5. Observability: Callbacks

**LiteLLM callbacks для логирования:**

```python
import litellm

def custom_callback(kwargs, completion_response, start_time, end_time):
    """Логируем каждый вызов LLM"""
    model = kwargs["model"]
    latency = end_time - start_time
    tokens = completion_response.usage.total_tokens
    cost = completion_response._hidden_params.get("response_cost", 0)

    print(f"[LLM] {model} | {tokens} tokens | {latency:.2f}s | ${cost:.4f}")

    # Отправляем в Prometheus/OpenTelemetry
    metrics.record_llm_call(model, tokens, latency, cost)

# Регистрируем callback
litellm.success_callback = [custom_callback]

# Все вызовы будут логироваться
response = completion(model="gpt-4", messages=[...])
```

**Для AI_TEAM observability:**
- ✅ Видим все LLM вызовы
- ✅ Можем трейсить через trace_id
- ✅ Метрики для мониторинга

---

## Альтернативы и почему НЕТ

### Прямые SDK (OpenAI, Anthropic, etc.)

**Плюсы:**
- Официальные библиотеки
- Полный feature set

**Почему НЕТ:**
- ❌ Разные API для каждого провайдера
- ❌ Нужно писать abstraction layer самим
- ❌ Нет unified retry/fallback
- ❌ Нет cost tracking из коробки

**Пример проблемы:**
```python
# OpenAI
from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)

# Anthropic (ДРУГОЙ API!)
from anthropic import Anthropic
client = Anthropic()
response = client.messages.create(
    model="claude-3-opus-20240229",
    messages=[{"role": "user", "content": "Hello"}],
    max_tokens=1024  # Обязательный параметр!
)

# Разные response formats, разные error handling, разная логика
```

**Вердикт:** Прямые SDK — если нужна только одна модель. Для multi-model — overkill.

---

### LangChain LLM Wrappers

**Плюсы:**
- Unified interface
- Много интеграций

**Почему НЕТ:**
- ❌ Тяжелая абстракция (BaseLanguageModel, BaseChatModel)
- ❌ Сложнее для простых вызовов
- ❌ Нет cost tracking из коробки
- ❌ Нет automatic fallback

**Пример LangChain:**
```python
from langchain.chat_models import ChatOpenAI, ChatAnthropic

# OpenAI
llm_openai = ChatOpenAI(model="gpt-4")
response = llm_openai.predict("Hello")

# Anthropic (нужно создавать другой объект!)
llm_anthropic = ChatAnthropic(model="claude-3-opus-20240229")
response = llm_anthropic.predict("Hello")

# Сложнее переключаться между моделями динамически
```

**Вердикт:** LangChain wrappers хороши для chains/agents, но для простых вызовов — overkill.

---

### Haystack LLM Integration

**Плюсы:**
- Unified interface
- Document-focused

**Почему НЕТ:**
- ❌ Фокус на RAG/документы (не наш use case)
- ❌ Меньше поддержки моделей vs LiteLLM
- ❌ Heavier framework

**Вердикт:** Haystack для RAG систем, не для multi-agent orchestration.

---

## Архитектура использования

### LLM Service Layer

```
┌─────────────────────────────────────────────────────────┐
│                    Agents Layer                          │
│  WriterAgent | CriticAgent | EditorAgent | ...          │
└────────────────────────┬────────────────────────────────┘
                         │
                         │ calls
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  LLM Service                             │
│                  (LiteLLM wrapper)                       │
│                                                          │
│  - completion(model, messages, **kwargs)                │
│  - acompletion (async version)                          │
│  - retry logic                                          │
│  - fallback logic                                       │
│  - cost tracking                                        │
│  - caching (Redis)                                      │
│  - observability (callbacks)                            │
└────────────────────────┬────────────────────────────────┘
                         │
                         │ uses
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   LiteLLM                                │
│  Unified interface to all LLM providers                 │
└────────────────────────┬────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
  ┌─────────┐      ┌─────────┐      ┌─────────┐
  │ OpenAI  │      │Anthropic│      │ Google  │
  │   API   │      │   API   │      │   API   │
  └─────────┘      └─────────┘      └─────────┘
```

---

## Примеры кода для AI_TEAM

### LLM Service Wrapper

```python
from typing import Optional, List, Dict, Any
from litellm import acompletion, completion
import litellm
from pydantic import BaseModel

class LLMConfig(BaseModel):
    """Конфигурация LLM из config/llm.yaml

    ⚠️ БЕЗ ДЕФОЛТНЫХ ЗНАЧЕНИЙ!
    Все параметры загружаются из YAML конфига.
    """
    default_model: str
    fallback_models: List[str]
    temperature: float
    max_tokens: int
    timeout: int
    num_retries: int
    cache_ttl: int

class LLMService:
    """Сервис для работы с LLM через LiteLLM"""

    def __init__(self, config: LLMConfig, redis_config: dict):
        """
        Args:
            config: LLMConfig загруженный из config/llm.yaml
            redis_config: dict загруженный из config/redis.yaml
        """
        self.config = config

        # Настраиваем кеш (параметры из redis_config)
        litellm.cache = litellm.Cache(
            type="redis",
            host=redis_config["host"],
            port=redis_config["port"],
            ttl=config.cache_ttl
        )

        # Включаем callbacks для observability
        litellm.success_callback = [self._log_success]
        litellm.failure_callback = [self._log_failure]

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        trace_id: Optional[str] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Асинхронный вызов LLM.

        Returns:
            {
                "content": "..response text..",
                "model": "gpt-4",
                "tokens": 150,
                "cost": 0.0045,
                "cached": False
            }
        """
        model = model or self.config.default_model
        temperature = temperature or self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens

        # Метаданные для observability
        metadata = {"trace_id": trace_id} if trace_id else {}

        try:
            response = await acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=self.config.timeout,
                num_retries=self.config.num_retries,
                fallbacks=self.config.fallback_models,
                cache={"ttl": self.config.cache_ttl} if use_cache else None,
                metadata=metadata
            )

            return {
                "content": response.choices[0].message.content,
                "model": response.model,
                "tokens": response.usage.total_tokens,
                "cost": response._hidden_params.get("response_cost", 0),
                "cached": response._hidden_params.get("cache_hit", False)
            }

        except Exception as e:
            # Логируем ошибку
            print(f"[LLM Error] {e}")
            raise

    def _log_success(self, kwargs, completion_response, start_time, end_time):
        """Callback при успешном вызове"""
        latency = end_time - start_time
        model = kwargs.get("model")
        tokens = completion_response.usage.total_tokens
        cost = completion_response._hidden_params.get("response_cost", 0)
        trace_id = kwargs.get("metadata", {}).get("trace_id")

        print(f"[LLM Success] trace_id={trace_id} model={model} tokens={tokens} latency={latency:.2f}s cost=${cost:.4f}")

        # TODO: Send to OpenTelemetry/Prometheus

    def _log_failure(self, kwargs, completion_response, start_time, end_time):
        """Callback при ошибке"""
        model = kwargs.get("model")
        error = completion_response
        trace_id = kwargs.get("metadata", {}).get("trace_id")

        print(f"[LLM Failure] trace_id={trace_id} model={model} error={error}")

        # TODO: Send to error tracking
```

### Использование в Agent

```python
class WriterAgent(Agent):
    def __init__(self, config: AgentConfig, mindbus: MindBus, llm_service: LLMService):
        super().__init__(config, mindbus)
        self.llm_service = llm_service

    async def execute(self, task: dict, context: dict, trace_id: str) -> dict:
        """Выполняет задачу написания"""

        messages = [
            {"role": "system", "content": f"You are a professional writer."},
            {"role": "user", "content": f"Write about: {task['topic']}"}
        ]

        # Вызываем LLM через сервис
        result = await self.llm_service.complete(
            messages=messages,
            model=self.config.llm_model,  # Может быть gpt-4, claude, etc.
            temperature=self.config.temperature,
            trace_id=trace_id
        )

        return {
            "article": result["content"],
            "metadata": {
                "model": result["model"],
                "tokens": result["tokens"],
                "cost": result["cost"],
                "cached": result["cached"]
            }
        }
```

---

## Конфигурация моделей (YAML)

```yaml
# config/llm.yaml
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

  # Модели для разных агентов (можем переопределить)
  agent_models:
    writer: "gpt-4"
    critic: "claude-3-opus-20240229"  # Claude лучше для критики
    editor: "gpt-4"
    researcher: "perplexity-online"  # Специализированная модель для research

  # Бюджетный контроль
  budget:
    max_cost_per_task: 0.50  # $0.50 max per task
    max_cost_per_day: 10.00  # $10 max per day
```

### Загрузка конфига

```python
import yaml
from pydantic import BaseModel

class LLMBudget(BaseModel):
    max_cost_per_task: float
    max_cost_per_day: float

class LLMFullConfig(BaseModel):
    default_model: str
    fallback_models: List[str]
    temperature: float
    max_tokens: int
    timeout: int
    num_retries: int
    cache_ttl: int
    agent_models: Dict[str, str]
    budget: LLMBudget

# Загрузка
with open("config/llm.yaml") as f:
    config_dict = yaml.safe_load(f)
    llm_config = LLMFullConfig(**config_dict["llm"])

# Использование
llm_service = LLMService(llm_config)
```

---

## Multi-Model Strategy

**Разные модели для разных задач:**

| Agent | Модель | Почему |
|-------|--------|--------|
| **Writer** | GPT-4 | Лучшее качество генерации |
| **Critic** | Claude 3 Opus | Лучшая критическая оценка |
| **Editor** | GPT-4 | Качественная правка |
| **Researcher** | Perplexity | Встроенный web search |
| **Fact-Checker** | GPT-4 | Высокая точность |

```python
# В конфиге агента указываем предпочтительную модель
agents:
  - name: "writer"
    role: "writer"
    llm_model: "gpt-4"  # ← Переопределяет default

  - name: "critic"
    role: "critic"
    llm_model: "claude-3-opus-20240229"  # ← Claude для критики

  - name: "researcher"
    role: "researcher"
    llm_model: "perplexity-online"  # ← Специализированная модель
```

---

## Cost Optimization

### 1. Кеширование одинаковых запросов
```python
# Первый раз — реальный вызов
result1 = await llm_service.complete(
    messages=[{"role": "user", "content": "What is AI?"}],
    use_cache=True
)
# Cost: $0.002

# Второй раз — из кеша
result2 = await llm_service.complete(
    messages=[{"role": "user", "content": "What is AI?"}],
    use_cache=True
)
# Cost: $0 (кеш!)
```

### 2. Умный fallback (дешевая модель для простых задач)
```python
llm_config = LLMConfig(
    default_model="gpt-4",  # Дорогая, но качественная
    fallback_models=[
        "gpt-3.5-turbo",  # Если gpt-4 недоступен — дешевле
    ]
)
```

### 3. Budget control
```python
class LLMService:
    async def complete(self, messages, **kwargs):
        # Проверяем бюджет
        current_cost = get_today_cost()
        if current_cost >= self.config.budget.max_cost_per_day:
            raise BudgetExceededError("Daily budget exceeded")

        result = await acompletion(...)

        # Обновляем счетчик
        update_cost_tracker(result["cost"])

        return result
```

---

## Итоговое решение

**LiteLLM — идеальный выбор для AI_TEAM потому что:**

1. ✅ Единый интерфейс для всех LLM (OpenAI, Anthropic, Google, Cohere, etc.)
2. ✅ Automatic retry + fallback = надежность
3. ✅ Cost tracking из коробки
4. ✅ Caching = экономия денег + скорость
5. ✅ Observability через callbacks
6. ✅ Простота использования (минимум кода)
7. ✅ Multi-model strategy (разные модели для разных агентов)

**Альтернативы отклонены:**
- Прямые SDK — разные API для каждого провайдера
- LangChain wrappers — тяжелая абстракция
- Haystack — фокус на RAG, не наш use case

**Риски минимальны:**
- LiteLLM battle-tested (используется в production)
- Active development
- Поддержка всех major LLM провайдеров

---

**Статус:** ✅ УТВЕРЖДЕНО
**Последнее обновление:** 2025-12-15
