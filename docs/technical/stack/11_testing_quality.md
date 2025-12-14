# Testing & Quality: pytest + coverage


---

# ⚠️ ЧЕРНОВИК — ТРЕБУЕТ ПРОВЕРКИ ⚠️

**Этот документ НЕ является финальным решением!**

Требуется детальный анализ, критика и проверка перед принятием решений.

---
## Решение

**Выбрано:**
- **pytest** — testing framework
- **pytest-asyncio** — async tests
- **pytest-cov** — coverage reports
- **Ruff** — linting & formatting
- **mypy** — type checking

---

## pytest для тестирования

### Структура тестов

```
tests/
├── unit/
│   ├── test_agents.py
│   ├── test_mindbus.py
│   ├── test_llm_service.py
│   └── test_storage.py
├── integration/
│   ├── test_orchestrator.py
│   ├── test_api.py
│   └── test_workflows.py
└── e2e/
    └── test_full_task.py
```

### Примеры тестов

```python
# tests/unit/test_agents.py
import pytest
from agents.writer import WriterAgent
from config.models import AgentConfig

@pytest.fixture
def writer_agent():
    config = AgentConfig(
        name="writer",
        role="writer",
        llm_model="gpt-4",
        temperature=0.7,
        max_tokens=2000,
        prompt_template="prompts/writer.txt"
    )
    return WriterAgent(config)

@pytest.mark.asyncio
async def test_writer_execute(writer_agent):
    """Test Writer agent execution"""
    task = {"topic": "AI trends", "style": "professional"}
    result = await writer_agent.execute(task, context={}, trace_id="test-123")

    assert "article" in result
    assert len(result["article"]) > 100
    assert result["metadata"]["model"] == "gpt-4"

def test_writer_validation(writer_agent):
    """Test Writer result validation"""
    result = {"article": "Short"}
    is_valid, score = writer_agent.validate_result(result)

    assert not is_valid  # Слишком короткая статья
    assert score == 0.0
```

---

## Coverage requirements

```bash
# pytest.ini
[tool.pytest.ini_options]
minversion = "7.0"
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
addopts = """
    --cov=src
    --cov-report=html
    --cov-report=term
    --cov-fail-under=80
"""
```

**Цель: 80%+ coverage для критических компонентов**

---

## Ruff для качества кода

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "F",   # pyflakes
    "I",   # isort
    "N",   # pep8-naming
    "UP",  # pyupgrade
    "B",   # flake8-bugbear
]
ignore = []

[tool.ruff.format]
quote-style = "double"
```

---

## mypy для type checking

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

---

## CI/CD Pipeline

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install poetry
          poetry install

      - name: Lint with Ruff
        run: poetry run ruff check .

      - name: Type check with mypy
        run: poetry run mypy src/

      - name: Run tests
        run: poetry run pytest

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Итоговое решение

**pytest + Ruff + mypy:**

1. ✅ Async testing (pytest-asyncio)
2. ✅ Coverage tracking
3. ✅ Fast linting (Ruff)
4. ✅ Type safety (mypy)
5. ✅ CI/CD integration

---

**Статус:** 📝 ЧЕРНОВИК (требует проверки и утверждения)
**Последнее обновление:** 2025-12-13
