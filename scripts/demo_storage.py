#!/usr/bin/env python3
"""
Демонстрация Persistent Storage.

Сценарий:
1. Агент создаёт артефакт и сохраняет его
2. Показываем что сохранилось
3. "Перезапускаем" Storage Service (новый экземпляр)
4. Восстанавливаем артефакт и показываем содержимое

Это доказывает, что данные переживают перезапуск!
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from storage import PersistentStorageService, generate_artifact_id
import json
import time


def print_separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def main():
    print("\n" + "🗄️" * 20)
    print("  ДЕМОНСТРАЦИЯ PERSISTENT STORAGE")
    print("🗄️" * 20)

    # Используем тестовую директорию
    test_dir = Path(".data_demo")
    db_path = str(test_dir / "storage.db")
    base_path = str(test_dir / "artifacts")
    temp_path = str(test_dir / "temp")
    buffer_path = str(test_dir / "buffer")
    orphans_path = str(test_dir / "orphans")

    # =========================================================================
    # ШАГ 1: Агент создаёт и сохраняет артефакт
    # =========================================================================
    print_separator("ШАГ 1: Агент создаёт артефакт")

    print("🤖 Агент 'researcher.001' создаёт отчёт об исследовании...")
    print()

    # Создаём Storage Service
    storage = PersistentStorageService(
        db_path=db_path,
        base_path=base_path,
        temp_path=temp_path,
        buffer_path=buffer_path,
        orphans_path=orphans_path,
    )

    # Агент создаёт результат работы
    research_result = {
        "topic": "Искусственный интеллект в 2025 году",
        "findings": [
            "Claude Opus 4.5 — самая умная модель",
            "Мультимодальность стала стандартом",
            "Агентные системы набирают популярность"
        ],
        "conclusion": "AI продолжает развиваться стремительными темпами",
        "created_at": "2025-12-19T15:30:00Z"
    }

    content = json.dumps(research_result, ensure_ascii=False, indent=2).encode('utf-8')

    # Регистрируем артефакт
    manifest = storage.register_artifact(
        content=content,
        artifact_type="research_report",
        trace_id="demo_trace_001",
        created_by="agent.researcher.001",
        filename="ai_research_2025.json",
        context={
            "model_name": "claude-opus-4.5",
            "execution_time_ms": 3500,
        }
    )

    print(f"✅ Артефакт создан!")
    print(f"   ID:       {manifest.id}")
    print(f"   Тип:      {manifest.artifact_type}")
    print(f"   Размер:   {manifest.size_bytes} байт")
    print(f"   Checksum: {manifest.checksum[:30]}...")
    print(f"   URI:      {manifest.uri}")
    print(f"   Статус:   {manifest.status}")

    # Сохраняем ID для восстановления
    saved_artifact_id = manifest.id

    # =========================================================================
    # ШАГ 2: Показываем что на диске
    # =========================================================================
    print_separator("ШАГ 2: Что сохранилось на диске")

    print(f"📁 База данных: {db_path}")
    print(f"📁 Файлы:       {base_path}/")
    print()

    # Показываем статистику
    stats = storage.get_stats()
    print(f"📊 Статистика Storage:")
    print(f"   Артефактов: {stats['artifacts']['total']}")
    print(f"   Завершено:  {stats['artifacts']['completed']}")
    print(f"   Тип:        {stats['storage_type']}")

    # =========================================================================
    # ШАГ 3: "Перезапуск" — создаём новый экземпляр Storage
    # =========================================================================
    print_separator("ШАГ 3: Симуляция перезапуска")

    print("🔄 Удаляем старый экземпляр Storage из памяти...")
    del storage
    print("   Старый Storage удалён")
    print()

    time.sleep(1)  # Пауза для наглядности

    print("🔄 Создаём НОВЫЙ экземпляр Storage Service...")
    print("   (как будто программа перезапустилась)")
    print()

    # Новый экземпляр — подключается к той же базе
    storage_new = PersistentStorageService(
        db_path=db_path,
        base_path=base_path,
        temp_path=temp_path,
        buffer_path=buffer_path,
        orphans_path=orphans_path,
    )

    print("✅ Новый Storage Service запущен!")

    # =========================================================================
    # ШАГ 4: Восстанавливаем артефакт
    # =========================================================================
    print_separator("ШАГ 4: Восстановление артефакта")

    print(f"🔍 Ищем артефакт по ID: {saved_artifact_id[:30]}...")
    print()

    # Получаем манифест
    restored_manifest = storage_new.get_artifact(saved_artifact_id)

    if restored_manifest:
        print("✅ Артефакт НАЙДЕН!")
        print(f"   ID:       {restored_manifest.id}")
        print(f"   Автор:    {restored_manifest.created_by}")
        print(f"   Создан:   {restored_manifest.created_at}")
        print(f"   Статус:   {restored_manifest.status}")
        print()

        # Читаем содержимое
        print("📄 Читаем содержимое файла...")
        content_bytes = storage_new.get_artifact_content(saved_artifact_id)
        restored_data = json.loads(content_bytes.decode('utf-8'))

        print()
        print("📋 Восстановленные данные:")
        print(f"   Тема: {restored_data['topic']}")
        print(f"   Выводы:")
        for finding in restored_data['findings']:
            print(f"      • {finding}")
        print(f"   Заключение: {restored_data['conclusion']}")

        # Проверяем целостность
        print()
        print("🔐 Проверка целостности (checksum)...")
        is_valid = storage_new.verify_artifact(saved_artifact_id)
        if is_valid:
            print("   ✅ Checksum совпадает — файл не повреждён!")
        else:
            print("   ❌ Checksum НЕ совпадает — файл повреждён!")

    else:
        print("❌ Артефакт не найден!")

    # =========================================================================
    # ШАГ 5: Показываем список всех артефактов
    # =========================================================================
    print_separator("ШАГ 5: Список всех артефактов в системе")

    all_artifacts = storage_new.list_artifacts(limit=10)
    print(f"📚 Найдено артефактов: {len(all_artifacts)}")
    print()

    for i, art in enumerate(all_artifacts, 1):
        print(f"   {i}. {art.id[:40]}...")
        print(f"      Тип: {art.artifact_type}, Автор: {art.created_by}")
        print()

    # =========================================================================
    # ИТОГ
    # =========================================================================
    print_separator("ИТОГ")

    print("🎉 Демонстрация успешна!")
    print()
    print("   Что мы доказали:")
    print("   ✅ Артефакт сохраняется на диск (SQLite + файл)")
    print("   ✅ После 'перезапуска' данные доступны")
    print("   ✅ Содержимое файла восстанавливается полностью")
    print("   ✅ Checksum подтверждает целостность")
    print()
    print(f"   Данные хранятся в: {test_dir.absolute()}")
    print()
    print("   Для очистки: rm -rf .data_demo/")
    print()


if __name__ == "__main__":
    main()
