#!/usr/bin/env python3
"""
DummyAgent — Test agent that simulates work with configurable delay.

This agent is used for testing the MindBus infrastructure.
It accepts any COMMAND, waits for a configured delay, and returns a mock result.

Usage:
    ./venv/bin/python -m src.agents.dummy_agent

See: docs/project/IMPLEMENTATION_ROADMAP.md Step 1.4
"""

import logging
import time
from typing import Any, Dict, Optional

from .base_agent import BaseAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class DummyAgent(BaseAgent):
    """
    Test agent that simulates work with configurable delay.

    Configuration (config/agents/dummy_agent.yaml):
        mock_delay_seconds: Time to simulate work
        success_rate: Probability of success (1.0 = always success)
    """

    def __init__(self, config_path: str = "config/agents/dummy_agent.yaml"):
        super().__init__(config_path)

        # DummyAgent-specific config
        self.mock_delay_seconds = self.config.get("mock_delay_seconds", 1.0)
        self.success_rate = self.config.get("success_rate", 1.0)

        logger.info(
            f"DummyAgent initialized: delay={self.mock_delay_seconds}s, "
            f"success_rate={self.success_rate}"
        )

    def execute(
        self,
        action: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a mock action.

        The DummyAgent:
        1. Logs the received action and params
        2. Waits for mock_delay_seconds
        3. Returns a mock result

        Args:
            action: The action to perform
            params: Action parameters
            context: Optional execution context

        Returns:
            Mock result dictionary
        """
        logger.info(f"Executing action: {action}")
        logger.info(f"  params: {params}")
        if context:
            logger.info(f"  context: {context}")

        # Simulate work
        logger.info(f"  Simulating work for {self.mock_delay_seconds}s...")
        time.sleep(self.mock_delay_seconds)

        # Check success rate (for testing error handling)
        import random
        if random.random() > self.success_rate:
            raise RuntimeError(f"Simulated failure for action: {action}")

        # Return mock result
        result = {
            "action": action,
            "status": "completed",
            "mock": True,
            "echo_params": params,
            "message": f"DummyAgent successfully processed '{action}'"
        }

        # Add action-specific mock data
        if action == "generate_article":
            result["article"] = f"Mock article about: {params.get('topic', 'unknown topic')}"
            result["word_count"] = params.get("length", 1000)

        elif action == "test.echo":
            result["echo"] = params

        logger.info(f"  Completed: {result.get('message', 'OK')}")

        return result


def main():
    """Run the DummyAgent."""
    agent = DummyAgent()
    agent.start()


if __name__ == "__main__":
    main()
