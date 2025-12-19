"""
API Gateway for AI_TEAM.

Provides HTTP endpoints for:
- Creating and managing tasks
- Process card execution
- System status
"""

from .gateway import create_app, APIGateway

__all__ = ["create_app", "APIGateway"]
