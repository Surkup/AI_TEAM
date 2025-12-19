#!/usr/bin/env python3
"""
Восстановление артефактов после РЕАЛЬНОГО перезапуска.

Этот скрипт показывает, что данные сохранились между запусками программы.
Запустите ПОСЛЕ demo_storage.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from storage import PersistentStorageService
import json


def main():
    print("\n" + "🔄" * 20)
    print("  ВОССТАНОВЛЕНИЕ ПОСЛЕ ПЕРЕЗАПУСКА")
    print("🔄" * 20)
    print()

    # Подключаемся к существующей базе
    test_dir = Path(".data_demo")

    if not test_dir.exists():
        print("❌ Папка .data_demo не найдена!")
        print("   Сначала запустите: python3 scripts/demo_storage.py")
        return 1

    storage = PersistentStorageService(
        db_path=str(test_dir / "storage.db"),
        base_path=str(test_dir / "artifacts"),
        temp_path=str(test_dir / "temp"),
        buffer_path=str(test_dir / "buffer"),
        orphans_path=str(test_dir / "orphans"),
    )

    print("✅ Storage Service подключен к существующей базе")
    print()

    # Показываем все артефакты
    artifacts = storage.list_artifacts()

    print(f"📚 Найдено артефактов: {len(artifacts)}")
    print()

    if not artifacts:
        print("   (пусто)")
        return 0

    for art in artifacts:
        print(f"┌─ Артефакт: {art.id}")
        print(f"│  Тип:     {art.artifact_type}")
        print(f"│  Автор:   {art.created_by}")
        print(f"│  Создан:  {art.created_at}")
        print(f"│  Размер:  {art.size_bytes} байт")
        print(f"│")

        # Читаем содержимое
        try:
            content = storage.get_artifact_content(art.id)
            data = json.loads(content.decode('utf-8'))

            if 'topic' in data:
                print(f"│  📄 Тема: {data['topic']}")
            if 'findings' in data:
                print(f"│  📄 Выводы: {len(data['findings'])} пунктов")
            if 'conclusion' in data:
                print(f"│  📄 Заключение: {data['conclusion'][:50]}...")
        except Exception as e:
            print(f"│  ⚠️ Ошибка чтения: {e}")

        # Проверяем целостность
        is_valid = storage.verify_artifact(art.id)
        status = "✅ OK" if is_valid else "❌ ПОВРЕЖДЁН"
        print(f"│")
        print(f"└─ Целостность: {status}")
        print()

    print("=" * 50)
    print("🎉 Данные успешно восстановлены после перезапуска!")
    print("=" * 50)
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
