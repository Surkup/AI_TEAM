# SSOT Specifications

This directory contains canonical data schemas (Single Source of Truth).

All code MUST follow these specifications.

## Structure

**Утверждённые спецификации**:
- ✅ **[mindbus_protocol_v1.md](mindbus_protocol_v1.md)** — спецификация протокола MindBus (AMQP + CloudEvents envelope)
- ✅ **[MESSAGE_FORMAT_v1.1.md](MESSAGE_FORMAT_v1.1.md)** — спецификация формата сообщений v1.1.1 (структура data field, ERROR type, AsyncAPI) — **оценка 95/100** 🏆
- ✅ **[NODE_PASSPORT_SPEC_v1.0.md](NODE_PASSPORT_SPEC_v1.0.md)** — спецификация паспорта узла (agent/orchestrator/component)
- ✅ **[NODE_REGISTRY_SPEC_v1.0.md](NODE_REGISTRY_SPEC_v1.0.md)** — спецификация реестра узлов (Node Registry)
- ✅ **[PROCESS_CARD_SPEC_v1.0.md](PROCESS_CARD_SPEC_v1.0.md)** — спецификация карточек процессов (Process Cards)

**Архивные версии**:
- 📦 **[MESSAGE_FORMAT_v1.0.md](MESSAGE_FORMAT_v1.0.md)** — v1.0 (superseded by v1.1)

**Планируемые спецификации**:
- `task_format.md` — Task structure (интеграция с Process Cards)

## Rules

- NEVER modify without team approval
- ALWAYS update version when changing
- ALWAYS document breaking changes
