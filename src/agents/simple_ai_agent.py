#!/usr/bin/env python3
"""
SimpleAIAgent — Agent that uses real LLM (OpenAI/Anthropic) to generate text.

This agent demonstrates integration with real AI models through MindBus.
It receives COMMAND messages with prompts and returns RESULT with generated text.

Usage:
    ./venv/bin/python -m src.agents.simple_ai_agent

Environment variables required:
    OPENAI_API_KEY - for OpenAI provider
    ANTHROPIC_API_KEY - for Anthropic provider

See: docs/project/IMPLEMENTATION_ROADMAP.md Step 1.6
"""

import logging
import os
import time
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from .base_agent import BaseAgent

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleAIAgent(BaseAgent):
    """
    Agent that uses real LLM to generate text.

    Supported actions:
        - generate_text: Generate text based on prompt

    Configuration (config/agents/simple_ai_agent.yaml):
        llm.provider: "openai" or "anthropic"
        llm.model: Model name (e.g., "gpt-4o-mini", "claude-3-haiku-20240307")
        llm.temperature: Creativity level (0.0-1.0)
        llm.max_tokens: Maximum response length
    """

    def __init__(self, config_path: str = "config/agents/simple_ai_agent.yaml"):
        super().__init__(config_path)

        # LLM configuration
        llm_config = self.config.get("llm", {})
        self.provider = llm_config.get("provider", "openai")
        self.model = llm_config.get("model", "gpt-4o-mini")
        self.temperature = llm_config.get("temperature", 0.7)
        self.max_tokens = llm_config.get("max_tokens", 500)

        # Initialize LLM client
        self._client = None
        self._init_client()

        logger.info(
            f"SimpleAIAgent initialized: provider={self.provider}, "
            f"model={self.model}, temperature={self.temperature}"
        )

    def _init_client(self) -> None:
        """Initialize the LLM client based on provider."""
        if self.provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")

            from openai import OpenAI
            self._client = OpenAI(api_key=api_key)
            logger.info("OpenAI client initialized")

        elif self.provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")

            from anthropic import Anthropic
            self._client = Anthropic(api_key=api_key)
            logger.info("Anthropic client initialized")

        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

    def execute(
        self,
        action: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute an action using the LLM.

        Args:
            action: The action to perform (e.g., "generate_text")
            params: Action parameters (must include "prompt" for generate_text)
            context: Optional execution context

        Returns:
            Result dictionary with generated text and metrics
        """
        logger.info(f"Executing action: {action}")
        logger.info(f"  params: {params}")

        if action == "generate_text":
            return self._generate_text(params)
        else:
            raise ValueError(f"Unknown action: {action}. Supported: generate_text")

    def _generate_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate text using the configured LLM."""
        prompt = params.get("prompt")
        if not prompt:
            raise ValueError("Missing required parameter: prompt")

        # Override defaults with params if provided
        temperature = params.get("temperature", self.temperature)
        max_tokens = params.get("max_tokens", self.max_tokens)

        logger.info(f"  Generating text with {self.provider}/{self.model}...")

        start_time = time.time()

        if self.provider == "openai":
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )

            text = response.choices[0].message.content
            usage = response.usage

            metrics = {
                "model": self.model,
                "provider": self.provider,
                "tokens_prompt": usage.prompt_tokens,
                "tokens_completion": usage.completion_tokens,
                "tokens_total": usage.total_tokens,
                "cost_usd": self._estimate_cost_openai(
                    usage.prompt_tokens,
                    usage.completion_tokens
                )
            }

        elif self.provider == "anthropic":
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            text = response.content[0].text
            usage = response.usage

            metrics = {
                "model": self.model,
                "provider": self.provider,
                "tokens_prompt": usage.input_tokens,
                "tokens_completion": usage.output_tokens,
                "tokens_total": usage.input_tokens + usage.output_tokens,
                "cost_usd": self._estimate_cost_anthropic(
                    usage.input_tokens,
                    usage.output_tokens
                )
            }

        generation_time = time.time() - start_time
        metrics["generation_time_seconds"] = round(generation_time, 2)

        logger.info(f"  Generated {metrics['tokens_completion']} tokens in {generation_time:.2f}s")
        logger.info(f"  Estimated cost: ${metrics['cost_usd']:.4f}")

        return {
            "action": "generate_text",
            "status": "completed",
            "text": text,
            "prompt_echo": prompt[:100] + "..." if len(prompt) > 100 else prompt,
            "metrics": metrics,
            "message": f"Generated {metrics['tokens_completion']} tokens with {self.model}"
        }

    def _estimate_cost_openai(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost for OpenAI API call (approximate prices)."""
        # Prices as of 2024 (per 1M tokens)
        prices = {
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "gpt-4-turbo": {"input": 10.00, "output": 30.00},
            "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        }

        model_prices = prices.get(self.model, {"input": 1.0, "output": 3.0})
        cost = (
            (prompt_tokens / 1_000_000) * model_prices["input"] +
            (completion_tokens / 1_000_000) * model_prices["output"]
        )
        return round(cost, 6)

    def _estimate_cost_anthropic(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for Anthropic API call (approximate prices)."""
        # Prices as of 2024 (per 1M tokens)
        prices = {
            "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
            "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
            "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
        }

        model_prices = prices.get(self.model, {"input": 3.0, "output": 15.0})
        cost = (
            (input_tokens / 1_000_000) * model_prices["input"] +
            (output_tokens / 1_000_000) * model_prices["output"]
        )
        return round(cost, 6)


def main():
    """Run the SimpleAIAgent."""
    agent = SimpleAIAgent()
    agent.start()


if __name__ == "__main__":
    main()
