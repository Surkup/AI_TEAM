"""
AI_TEAM Services Module.

Contains infrastructure services that register as nodes in the system:
- StorageService: File and artifact storage
- (future) StateService: State management
- (future) SchedulerService: Task scheduling
"""

from .base_service import BaseService
from .storage_service import StorageService

__all__ = ["BaseService", "StorageService"]
