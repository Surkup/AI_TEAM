"""
AgentMemory — Persistent memory for AI_TEAM agents.

Интегрирует агентов с PersistentStorageService для:
- Сохранения результатов работы (artifact_type="agent_work")
- Запоминания важной информации (artifact_type="agent_memory")
- Восстановления контекста после перезапуска

Based on:
- STORAGE_SPEC_v1.1.md
- CONTEXT_MEMORY_ARCHITECTURE_v1.2.md

Ready-Made Solutions:
- PersistentStorageService для хранения
- JSON для сериализации
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.storage import PersistentStorageService, generate_artifact_id

logger = logging.getLogger(__name__)


class AgentMemory:
    """
    Persistent memory для агента.

    Позволяет агенту:
    - Сохранять результаты работы
    - Запоминать важную информацию
    - Вспоминать предыдущие работы по теме
    - Сохранять context между сессиями

    Структура хранения:
    - artifact_type="agent_work" — результаты выполнения задач
    - artifact_type="agent_memory" — заметки, факты, выводы
    - artifact_type="agent_context" — сохранённый контекст сессии
    """

    def __init__(
        self,
        agent_name: str,
        storage: Optional[PersistentStorageService] = None,
        db_path: str = ".data/storage.db",
    ):
        """
        Инициализация памяти агента.

        Args:
            agent_name: Имя агента (node_id)
            storage: Существующий Storage Service (опционально)
            db_path: Путь к базе данных (если storage не передан)
        """
        self.agent_name = agent_name

        if storage:
            self.storage = storage
        else:
            self.storage = PersistentStorageService(db_path=db_path)

        self._session_id = generate_artifact_id().replace("art_", "session_")

        logger.info(f"AgentMemory initialized for {agent_name}, session={self._session_id[:20]}...")

    # =========================================================================
    # Сохранение результатов работы
    # =========================================================================

    def save_work(
        self,
        action: str,
        result: Dict[str, Any],
        topic: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        """
        Сохранить результат работы агента.

        Args:
            action: Какое действие выполнялось
            result: Результат выполнения
            topic: Тема работы (для поиска)
            trace_id: ID процесса (опционально)

        Returns:
            artifact_id сохранённого результата
        """
        work_data = {
            "action": action,
            "result": result,
            "topic": topic,
            "agent": self.agent_name,
            "session": self._session_id,
            "saved_at": datetime.utcnow().isoformat(),
        }

        content = json.dumps(work_data, ensure_ascii=False, indent=2).encode("utf-8")

        manifest = self.storage.register_artifact(
            content=content,
            artifact_type="agent_work",
            trace_id=trace_id or self._session_id,
            created_by=self.agent_name,
            filename=f"{action}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
            context={
                "model_name": result.get("metrics", {}).get("model", "unknown"),
                "execution_time_ms": int(result.get("metrics", {}).get("execution_time_seconds", 0) * 1000),
            }
        )

        logger.info(f"[{self.agent_name}] Saved work: {action} -> {manifest.id[:30]}...")

        return manifest.id

    # =========================================================================
    # Запоминание информации
    # =========================================================================

    def remember(
        self,
        key: str,
        value: Any,
        category: str = "general",
        importance: int = 5,
    ) -> str:
        """
        Запомнить информацию.

        Args:
            key: Ключ для поиска (например, "topic:AI", "fact:claude_release_date")
            value: Что запомнить
            category: Категория (general, fact, insight, decision)
            importance: Важность 1-10 (влияет на приоритет при recall)

        Returns:
            artifact_id
        """
        memory_data = {
            "key": key,
            "value": value,
            "category": category,
            "importance": importance,
            "agent": self.agent_name,
            "remembered_at": datetime.utcnow().isoformat(),
        }

        content = json.dumps(memory_data, ensure_ascii=False, indent=2).encode("utf-8")

        manifest = self.storage.register_artifact(
            content=content,
            artifact_type="agent_memory",
            trace_id=f"memory_{self.agent_name}",
            created_by=self.agent_name,
            filename=f"memory_{key.replace(':', '_').replace(' ', '_')[:30]}.json",
        )

        logger.info(f"[{self.agent_name}] Remembered: {key} (importance={importance})")

        return manifest.id

    # =========================================================================
    # Вспоминание
    # =========================================================================

    def recall_works(
        self,
        action: Optional[str] = None,
        topic: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Вспомнить предыдущие работы.

        Args:
            action: Фильтр по действию
            topic: Фильтр по теме (поиск в содержимом)
            limit: Максимум результатов

        Returns:
            Список предыдущих работ
        """
        # Получаем все работы агента
        artifacts = self.storage.list_artifacts(
            created_by=self.agent_name,
            artifact_type="agent_work",
            limit=limit * 3,  # Берём больше, потом фильтруем
        )

        results = []

        for art in artifacts:
            try:
                content = self.storage.get_artifact_content(art.id)
                work_data = json.loads(content.decode("utf-8"))

                # Фильтруем
                if action and work_data.get("action") != action:
                    continue
                if topic and topic.lower() not in json.dumps(work_data).lower():
                    continue

                results.append({
                    "id": art.id,
                    "action": work_data.get("action"),
                    "topic": work_data.get("topic"),
                    "result_summary": self._summarize_result(work_data.get("result", {})),
                    "saved_at": work_data.get("saved_at"),
                })

                if len(results) >= limit:
                    break

            except Exception as e:
                logger.warning(f"Failed to read work {art.id}: {e}")

        logger.info(f"[{self.agent_name}] Recalled {len(results)} works (action={action}, topic={topic})")

        return results

    def recall_memory(
        self,
        key: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Вспомнить сохранённую информацию.

        Args:
            key: Поиск по ключу (частичное совпадение)
            category: Фильтр по категории
            limit: Максимум результатов

        Returns:
            Список воспоминаний
        """
        artifacts = self.storage.list_artifacts(
            created_by=self.agent_name,
            artifact_type="agent_memory",
            limit=limit * 3,
        )

        results = []

        for art in artifacts:
            try:
                content = self.storage.get_artifact_content(art.id)
                memory_data = json.loads(content.decode("utf-8"))

                # Фильтруем
                if key and key.lower() not in memory_data.get("key", "").lower():
                    continue
                if category and memory_data.get("category") != category:
                    continue

                results.append({
                    "id": art.id,
                    "key": memory_data.get("key"),
                    "value": memory_data.get("value"),
                    "category": memory_data.get("category"),
                    "importance": memory_data.get("importance"),
                    "remembered_at": memory_data.get("remembered_at"),
                })

                if len(results) >= limit:
                    break

            except Exception as e:
                logger.warning(f"Failed to read memory {art.id}: {e}")

        # Сортируем по важности
        results.sort(key=lambda x: x.get("importance", 0), reverse=True)

        logger.info(f"[{self.agent_name}] Recalled {len(results)} memories")

        return results

    def recall_by_topic(self, topic: str, limit: int = 5) -> Dict[str, Any]:
        """
        Вспомнить всё по теме — и работы, и заметки.

        Args:
            topic: Тема для поиска
            limit: Максимум результатов каждого типа

        Returns:
            {"works": [...], "memories": [...]}
        """
        works = self.recall_works(topic=topic, limit=limit)
        memories = self.recall_memory(key=topic, limit=limit)

        return {
            "works": works,
            "memories": memories,
            "total": len(works) + len(memories),
        }

    # =========================================================================
    # Контекст сессии
    # =========================================================================

    def save_context(self, context: Dict[str, Any]) -> str:
        """
        Сохранить контекст текущей сессии.

        Полезно для восстановления после перезапуска.
        """
        context_data = {
            "context": context,
            "agent": self.agent_name,
            "session": self._session_id,
            "saved_at": datetime.utcnow().isoformat(),
        }

        content = json.dumps(context_data, ensure_ascii=False, indent=2).encode("utf-8")

        manifest = self.storage.register_artifact(
            content=content,
            artifact_type="agent_context",
            trace_id=f"context_{self.agent_name}",
            created_by=self.agent_name,
            filename=f"context_{self._session_id[:20]}.json",
        )

        return manifest.id

    def load_latest_context(self) -> Optional[Dict[str, Any]]:
        """
        Загрузить последний сохранённый контекст.
        """
        artifacts = self.storage.list_artifacts(
            created_by=self.agent_name,
            artifact_type="agent_context",
            limit=1,
        )

        if not artifacts:
            return None

        try:
            content = self.storage.get_artifact_content(artifacts[0].id)
            context_data = json.loads(content.decode("utf-8"))
            return context_data.get("context")
        except Exception as e:
            logger.warning(f"Failed to load context: {e}")
            return None

    # =========================================================================
    # Статистика
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику памяти агента."""
        works = self.storage.list_artifacts(
            created_by=self.agent_name,
            artifact_type="agent_work",
            limit=1000,
        )

        memories = self.storage.list_artifacts(
            created_by=self.agent_name,
            artifact_type="agent_memory",
            limit=1000,
        )

        return {
            "agent": self.agent_name,
            "session": self._session_id,
            "works_count": len(works),
            "memories_count": len(memories),
            "total_artifacts": len(works) + len(memories),
        }

    # =========================================================================
    # Helpers
    # =========================================================================

    def _summarize_result(self, result: Dict[str, Any]) -> str:
        """Создать краткое summary результата."""
        output = result.get("output", {})
        text = output.get("text", "")

        if text:
            # Первые 100 символов
            summary = text[:100].replace("\n", " ")
            if len(text) > 100:
                summary += "..."
            return summary

        return str(result)[:100]
