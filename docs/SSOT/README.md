# SSOT Specifications

This directory contains canonical data schemas (Single Source of Truth).

All code MUST follow these specifications.

## Structure

**Утверждённые спецификации**:
- ✅ **[NODE_PASSPORT_SPEC_v1.0.md](NODE_PASSPORT_SPEC_v1.0.md)** — спецификация паспорта узла (agent/orchestrator/component)
- ✅ **[NODE_REGISTRY_SPEC_v1.0.md](NODE_REGISTRY_SPEC_v1.0.md)** — спецификация реестра узлов (Node Registry)
- ✅ **[PROCESS_CARD_SPEC_v1.0.md](PROCESS_CARD_SPEC_v1.0.md)** — спецификация карточек процессов (Process Cards)

**Планируемые спецификации**:
- `message_format.md` — MindBus message format (дополнительно к [mindbus_protocol_v1.md](./mindbus_protocol_v1.md))
- `task_format.md` — Task structure (интеграция с Process Cards)

## Rules

- NEVER modify without team approval
- ALWAYS update version when changing
- ALWAYS document breaking changes
