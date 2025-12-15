# AI_TEAM Project Rules

## 0. Meta-принцип: Готовые решения первичны (Ready-Made Solutions First)

**КРИТИЧЕСКОЕ ПРАВИЛО**: Перед проектированием ЛЮБОГО компонента или архитектурного решения — ОБЯЗАТЕЛЬНО искать существующие мировые стандарты и готовые реализации.

**Порядок работы при проектировании**:
1. ✅ Формулируем требования к компоненту/решению
2. ✅ Ищем существующие стандарты (IETF RFC, ISO, CNCF, W3C, IEEE, OASIS)
3. ✅ Ищем готовые реализации (RabbitMQ, Redis, PostgreSQL, gRPC, Kafka, etc.)
4. ✅ Анализируем: покрывают ли ≥80% требований?
5. ✅ Если ДА → используем готовое решение
6. ✅ Если НЕТ → обосновываем custom разработку в архитектурном документе

**Критерии "готового решения"**:
- ✅ Есть техническая документация (RFC/спецификация/стандарт)
- ✅ Есть открытый код ИЛИ стабильная коммерческая версия
- ✅ Есть библиотеки для Python/Go (обязательно)
- ✅ Используется в production >3 лет (примеры компаний)
- ✅ Активное сообщество (commits за последние 3-6 месяцев)

**ЗАПРЕЩЕНО**:
- ❌ Писать "собственный протокол вдохновлённый X" — вместо этого ИСПОЛЬЗОВАТЬ X
- ❌ Писать "свой формат данных похожий на Y" — вместо этого ИСПОЛЬЗОВАТЬ Y
- ❌ Говорить "готовое решение не подходит" без детального сравнительного анализа

**Что делать если готовое решение "почти подходит"**:
- ✅ Адаптировать наши требования под готовое решение (95% случаев)
- ✅ Использовать готовое решение + тонкая обёртка (4% случаев)
- ✅ Разработать с нуля ТОЛЬКО если критичный gap (1% случаев)

**Пример применения**:

Задача: Разработать протокол MindBus для AI_TEAM

❌ **НЕПРАВИЛЬНЫЙ подход**:
1. Придумали "IPv4-inspired binary protocol"
2. Спроектировали 20-byte header
3. Написали парсер Protobuf
→ Результат: 7-10 недель разработки, новый протокол требует поддержки

✅ **ПРАВИЛЬНЫЙ подход**:
1. Проанализировали существующие: AMQP, MQTT, gRPC, NATS
2. Выбрали AMQP (RabbitMQ) — покрывает 95% требований
3. Добавили CloudEvents для стандартизации формата данных
→ Результат: 1-2 недели интеграции, industry-proven решение

**Архитектурное решение ДОЛЖНО быть зафиксировано**:
- В `docs/concepts/COMPONENT_NAME_decision.md` — обоснование выбора технологии
- В `docs/SSOT/COMPONENT_SPEC.md` — техническая спецификация использования

**ТРИГГЕРЫ для проверки этого принципа**:

Если видишь задачу типа:
- "Разработай протокол..."
- "Спроектируй формат данных..."
- "Создай систему для..."
- "Придумай архитектуру..."

→ СТОП! ОБЯЗАТЕЛЬНО:
1. Спросить: "Проанализировал ли ты существующие стандарты и готовые решения?"
2. Предложить: "Давай сначала найдём, что уже существует в мире"
3. Создать таблицу сравнения готовых решений (минимум 3 варианта)
4. ТОЛЬКО ПОСЛЕ ЭТОГО предлагать custom разработку (если готовые не подходят)

See: README.md section "🏛️ Опора на проверенные архитектуры"
See: PROJECT_OVERVIEW.md section "Методология поиска готовых решений"

---

## 1. SSOT - NEVER modify without specification first

**CRITICAL**: Specification-Driven Development is mandatory

- `docs/SSOT/` contains canonical data schemas - **NEVER modify without team approval**
- **NEVER write code before SSOT specification is created and approved**
- **ALWAYS validate code against SSOT schemas before implementation**
- **ALWAYS ask before creating or modifying any file in `docs/SSOT/`**

**SSOT vs Config** - NEVER mix:
- **SSOT** defines "system language" (data structures, message formats, schemas)
- **Config** defines "runtime environment" (timeouts, ports, limits, credentials)
- Example: Field name `trace_id` → SSOT. Timeout value `30s` → Config.

See: README.md section "Разработка по спецификациям (Specification-Driven Development)"

---

## 2. Security - NEVER commit credentials

**NEVER commit**:
- `.env` files - contain API keys and secrets
- `config/*.json` - may contain sensitive data
- Any files with API keys, tokens, passwords
- Files matching patterns: `*.key`, `*.pem`, `credentials.*`, `secrets.*`

**ALWAYS**:
- Check `git status` before commits
- Ask before committing config files
- Use environment variables for secrets

---

## 3. Configuration - NEVER hardcode parameters

**CRITICAL RULE**: Zero Hardcoding principle

**NEVER hardcode in code**:
- Timeouts, retries, limits
- API keys, URLs, ports, hostnames
- Agent names, component IDs
- File paths, directory paths
- Threshold values
- Any "magic numbers" or constants

**MUST be in config files**:
- All system parameters
- Component settings
- Resource limits
- Connection addresses

See: README.md section "⚙️ Нулевой хардкод (Zero Hardcoding)"

---

## 4. Git workflow

**Main branch**: `main`

**Commit messages**:
- ALWAYS write in Russian
- ALWAYS include: what was done and why
- Format: `<action>: <description>`
- ALWAYS add `Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>` for AI-generated code

**NEVER**:
- Force push to `main` branch
- Commit without descriptive message
- Skip pre-commit hooks

**Git safety**:
- ALWAYS run `git status` before commits
- ALWAYS review `git diff` before committing
- Ask before any destructive git operations

See: docs/IMPLEMENTATION_ROADMAP.md for development stages

---

## 5. Before deleting or major changes - ALWAYS ask

**ALWAYS ask before**:
- Deleting any file
- Modifying files in `docs/SSOT/` directory
- Modifying `README.md`, `QUESTIONS.md`, `CLAUDE.md`
- Modifying `docs/project/IMPLEMENTATION_ROADMAP.md`
- Modifying `docs/SSOT/mindbus_protocol_v1.md`
- Any structural changes to the project

**IMPORTANT**: SSOT changes require team discussion and approval

---

## 6. Project structure

**Critical directories**:
- `docs/SSOT/` - Canonical data schemas (**DO NOT TOUCH without approval**)
- `docs/` - All project documentation
- `config/` - Configuration files (check before commit)

**Key files**:
- `README.md` - Project concept and principles
- `QUESTIONS.md` - Open questions catalog
- `CLAUDE.md` - This file (project rules)
- `docs/SSOT/mindbus_protocol_v1.md` - MindBus Protocol v1.0 (Final)
- `docs/project/IMPLEMENTATION_ROADMAP.md` - Development plan (current)
- `docs/archive_reorganization_2025-12-15/PRELIMINARY_PLAN.md` - Initial planning (archived)

---

## 7. Development workflow - MUST follow

**MANDATORY order**:
1. ✅ Create SSOT specification (in `docs/SSOT/`)
2. ✅ Document in project docs
3. ✅ Get team approval
4. ✅ **ONLY THEN** write code

**NEVER**:
- Code with "temporary" structures ("will fix later")
- Invent data formats on-the-fly
- Use different structures in different components for same entity
- Change data structures without updating SSOT first

See: README.md sections:
- "🎯 Единый источник правды (Single Source of Truth - SSOT)"
- "📋 Разработка по спецификациям (Specification-Driven Development)"

---

## 8. Code quality

**ALWAYS**:
- Follow SSOT schemas strictly
- Validate all inputs and outputs
- Include error handling
- Write clear, self-documenting code
- Add comments only where logic is non-obvious

**NEVER**:
- Skip validation against SSOT
- Assume data structure without checking SSOT
- Write code before specification exists

**Handling invalid data** (CRITICAL for distributed system):
- **IF** message violates SSOT schema → **REJECT immediately**
- **NEVER** try to "fix" or "guess" invalid data
- **ALWAYS** log validation error with details
- **MUST** send ERROR message back to sender (if applicable)
- Component should fail fast, not silently ignore errors

---

## 9. Documentation

**ALWAYS keep updated**:
- SSOT specs when data structures change
- README.md when principles change
- QUESTIONS.md when new questions arise
- Implementation docs when architecture changes

**Documentation is NOT optional** - it must be updated **before or with** code changes

---

## 10. When in doubt

**If unsure about**:
- Data structure → Check `docs/SSOT/` first, ask if not found
- Project rules → Check this file and README.md
- Development plan → Check `docs/project/IMPLEMENTATION_ROADMAP.md`
- Open questions → Check `QUESTIONS.md`

**ALWAYS ask before**:
- Making structural changes
- Modifying SSOT files
- Deleting anything
- Committing config files

---

**Last updated**: 2025-12-15
**Version**: 1.1 (Добавлен мета-принцип "Готовые решения первичны")
