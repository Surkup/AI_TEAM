# AI_TEAM Project Rules

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
- Modifying `docs/IMPLEMENTATION_ROADMAP.md`
- Modifying `docs/MINDBUS_README.md`
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
- `docs/MINDBUS_README.md` - MindBus architecture concept
- `docs/IMPLEMENTATION_ROADMAP.md` - Development plan (current)
- `docs/PRELIMINARY_PLAN.md` - Initial planning (reference only)

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
- Development plan → Check `docs/IMPLEMENTATION_ROADMAP.md`
- Open questions → Check `QUESTIONS.md`

**ALWAYS ask before**:
- Making structural changes
- Modifying SSOT files
- Deleting anything
- Committing config files

---

**Last updated**: 2025-12-12
**Version**: 1.0
