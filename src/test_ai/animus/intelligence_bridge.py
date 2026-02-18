"""Animus IntelligenceProvider implementation wrapping Gorgon's agent providers.

Conforms to the IntelligenceProvider protocol defined in animus/protocols/intelligence.py:
    generate(prompt, system) -> str
    generate_stream(prompt, system) -> AsyncIterator[str]
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from .config import AnimusBridgeConfig

logger = logging.getLogger(__name__)


class GorgonIntelligenceProvider:
    """IntelligenceProvider protocol implementation using Gorgon's provider layer.

    Wraps Gorgon's AgentProvider to satisfy Animus's IntelligenceProvider
    structural protocol. Supports both synchronous generation and
    async streaming.
    """

    def __init__(
        self,
        provider_type: str = "anthropic",
        config: AnimusBridgeConfig | None = None,
    ):
        self._provider_type = provider_type
        self._config = config or AnimusBridgeConfig()
        self._provider = None

    def _get_provider(self):
        """Lazy-initialize the underlying Gorgon AgentProvider."""
        if self._provider is None:
            from test_ai.agents.provider_wrapper import create_agent_provider

            self._provider = create_agent_provider(self._provider_type)
        return self._provider

    def generate(self, prompt: str, system: str | None = None) -> str:
        """Generate a completion synchronously.

        Satisfies IntelligenceProvider.generate().
        """
        import asyncio

        provider = self._get_provider()
        messages = self._build_messages(prompt, system)

        # Run async completion synchronously
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in an async context — create a new thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    asyncio.run, provider.complete(messages)
                ).result()
            return result
        else:
            return asyncio.run(provider.complete(messages))

    async def generate_stream(
        self, prompt: str, system: str | None = None
    ) -> AsyncIterator[str]:
        """Stream a completion response.

        Satisfies IntelligenceProvider.generate_stream().
        """
        provider = self._get_provider()
        messages = self._build_messages(prompt, system)

        async for chunk in provider.stream_completion(messages):
            yield chunk

    def _build_messages(
        self, prompt: str, system: str | None
    ) -> list[dict[str, str]]:
        """Build the messages list for the provider."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages
