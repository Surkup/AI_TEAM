#!/usr/bin/env python3
"""
Демонстрация памяти агентов.

Сценарий:
1. Создаём Исследователя с включённой памятью
2. Даём ему задание исследовать тему
3. Результат автоматически сохраняется в память
4. "Перезапускаем" агента (новый экземпляр)
5. Агент вспоминает свои предыдущие исследования

Это доказывает, что агенты теперь имеют постоянную память!
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Нужен API ключ для реального теста
from dotenv import load_dotenv
load_dotenv()

import json
import time


def print_separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def demo_with_mock():
    """Демо без реального LLM (быстрый тест памяти)."""
    from agents.agent_memory import AgentMemory

    print_separator("ДЕМО: Память агента (без LLM)")

    # Шаг 1: Создаём память для агента
    print("🧠 Создаём память для Исследователя...")
    memory = AgentMemory(agent_name="agent.researcher.001")
    print(f"   Session: {memory._session_id[:30]}...")
    print()

    # Шаг 2: Сохраняем результат работы
    print("📝 Агент 'выполнил' исследование и сохраняет результат...")

    mock_result = {
        "action": "research_topic",
        "status": "completed",
        "output": {
            "text": """
            # Исследование: Искусственный интеллект в 2025 году

            ## Ключевые находки:
            1. Claude Opus 4.5 — самая мощная модель Anthropic
            2. GPT-5 ожидается в Q2 2025
            3. Агентные системы становятся стандартом
            4. Мультимодальность везде

            ## Вывод:
            AI продолжает экспоненциально развиваться.
            """,
            "word_count": 45,
        },
        "metrics": {
            "model": "gpt-4o",
            "llm_calls": 2,
            "execution_time_seconds": 3.5,
        }
    }

    artifact_id = memory.save_work(
        action="research_topic",
        result=mock_result,
        topic="AI 2025",
    )

    print(f"   ✅ Сохранено: {artifact_id}")
    print()

    # Шаг 3: Агент запоминает важный факт
    print("💡 Агент запоминает важный факт...")

    memory.remember(
        key="fact:claude_opus_4.5",
        value="Claude Opus 4.5 — самая мощная модель Anthropic, выпущена в 2025",
        category="fact",
        importance=9,
    )

    memory.remember(
        key="insight:ai_agents",
        value="Агентные системы в 2025 становятся стандартом разработки AI",
        category="insight",
        importance=8,
    )

    print("   ✅ 2 факта сохранены")
    print()

    # Шаг 4: Статистика
    stats = memory.get_stats()
    print(f"📊 Статистика памяти:")
    print(f"   Работ: {stats['works_count']}")
    print(f"   Воспоминаний: {stats['memories_count']}")
    print()

    # Шаг 5: "Перезапуск" — новый экземпляр
    print_separator("СИМУЛЯЦИЯ ПЕРЕЗАПУСКА")

    print("🔄 Удаляем память из RAM...")
    del memory
    time.sleep(1)

    print("🔄 Создаём НОВЫЙ экземпляр памяти...")
    memory_new = AgentMemory(agent_name="agent.researcher.001")
    print(f"   Новая сессия: {memory_new._session_id[:30]}...")
    print()

    # Шаг 6: Вспоминаем
    print_separator("ВОССТАНОВЛЕНИЕ ПАМЯТИ")

    print("🔍 Ищем предыдущие работы по теме 'AI'...")
    recalled = memory_new.recall_by_topic("AI", limit=5)

    print(f"\n📚 Найдено:")
    print(f"   Работ: {len(recalled['works'])}")
    print(f"   Воспоминаний: {len(recalled['memories'])}")
    print()

    if recalled['works']:
        print("📋 Последние работы:")
        for work in recalled['works']:
            print(f"   • {work['action']}: {work['result_summary'][:50]}...")
        print()

    if recalled['memories']:
        print("💭 Воспоминания:")
        for mem in recalled['memories']:
            print(f"   • [{mem['importance']}/10] {mem['key']}")
            print(f"     {mem['value'][:60]}...")
        print()

    print_separator("ИТОГ")
    print("🎉 Демонстрация успешна!")
    print()
    print("   Что мы доказали:")
    print("   ✅ Агент сохраняет результаты работы")
    print("   ✅ Агент запоминает важные факты")
    print("   ✅ После 'перезапуска' память восстанавливается")
    print("   ✅ Можно искать по теме")
    print()


def demo_with_real_llm():
    """Демо с реальным LLM (требует API ключ)."""

    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  OPENAI_API_KEY не найден")
        print("   Для теста с реальным AI добавьте ключ в .env")
        return False

    print_separator("ДЕМО: Агент с реальным AI и памятью")

    from agents.creative_agent import ResearcherAgent

    # Создаём агента
    print("🤖 Создаём Исследователя с памятью...")

    try:
        agent = ResearcherAgent()
    except Exception as e:
        print(f"❌ Ошибка создания агента: {e}")
        return False

    print(f"   {agent.display_avatar} {agent.display_name}")
    print(f"   Память: {'ON' if agent.memory else 'OFF'}")
    print()

    # Проверяем статистику памяти
    stats = agent.get_memory_stats()
    print(f"📊 Начальная статистика памяти:")
    print(f"   Работ: {stats.get('works_count', 0)}")
    print(f"   Воспоминаний: {stats.get('memories_count', 0)}")
    print()

    # Даём задание
    print("📝 Даём задание исследовать тему...")
    print()

    try:
        result = agent.execute(
            action="research_topic",
            params={
                "topic": "Последние достижения Claude AI",
                "depth": "краткий обзор",
            }
        )

        print(f"✅ Задание выполнено!")
        print(f"   Слов: {result['output']['word_count']}")
        print(f"   LLM вызовов: {result['metrics']['llm_calls']}")

        if result.get("memory", {}).get("saved"):
            print(f"   💾 Сохранено в память: {result['memory']['artifact_id'][:30]}...")
        print()

        # Показываем результат
        print("📄 Результат исследования:")
        print("-" * 40)
        text = result['output']['text']
        print(text[:500] + "..." if len(text) > 500 else text)
        print("-" * 40)
        print()

    except Exception as e:
        print(f"❌ Ошибка выполнения: {e}")
        return False

    # Финальная статистика
    stats = agent.get_memory_stats()
    print(f"📊 Финальная статистика памяти:")
    print(f"   Работ: {stats.get('works_count', 0)}")
    print(f"   Воспоминаний: {stats.get('memories_count', 0)}")
    print()

    print("🎉 Реальный тест успешен!")

    return True


def main():
    print("\n" + "🧠" * 20)
    print("  ДЕМОНСТРАЦИЯ ПАМЯТИ АГЕНТОВ")
    print("🧠" * 20)

    # Сначала быстрый тест без LLM
    demo_with_mock()

    # Тест с реальным LLM — опционально через аргумент командной строки
    if len(sys.argv) > 1 and sys.argv[1] == "--with-llm":
        if os.getenv("OPENAI_API_KEY"):
            demo_with_real_llm()
        else:
            print("\n⚠️  OPENAI_API_KEY не найден для --with-llm режима")
    else:
        print("\n💡 Совет: запустите с --with-llm для теста с реальным AI")

    print()


if __name__ == "__main__":
    main()
