"""Provider wrapper for agents with streaming support."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, AsyncGenerator

if TYPE_CHECKING:
    from test_ai.providers.base import Provider

logger = logging.getLogger(__name__)


class AgentProvider:
    """Wrapper around Provider with async and streaming support."""

    def __init__(self, provider: "Provider"):
        """Initialize with a provider.

        Args:
            provider: The underlying AI provider.
        """
        self.provider = provider
        if not self.provider._initialized:
            self.provider.initialize()

    async def complete(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
    ) -> str:
        """Complete a conversation.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            max_tokens: Maximum tokens in the response.

        Returns:
            The assistant's response.
        """
        from test_ai.providers.base import CompletionRequest

        # Extract system prompt from messages
        system_prompt = None
        filtered_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                if system_prompt is None:
                    system_prompt = msg.get("content", "")
                else:
                    system_prompt += "\n\n" + msg.get("content", "")
            else:
                filtered_messages.append(msg)

        request = CompletionRequest(
            prompt=filtered_messages[-1].get("content", "")
            if filtered_messages
            else "",
            system_prompt=system_prompt or "You are a helpful assistant.",
            messages=filtered_messages,
            temperature=0.7,
            max_tokens=max_tokens,
        )

        response = await self.provider.complete_async(request)
        return response.content

    async def stream_completion(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Stream a completion response.

        Args:
            messages: List of message dicts with 'role' and 'content'.

        Yields:
            Text chunks as they're generated.
        """
        # Check if provider has native streaming
        if hasattr(self.provider, "_async_client") and self.provider._async_client:
            try:
                async for chunk in self._stream_anthropic(messages):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"Streaming failed, falling back to non-streaming: {e}")

        # Fall back to non-streaming
        response = await self.complete(messages)
        yield response

    async def _stream_anthropic(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Stream using Anthropic's native streaming API.

        Args:
            messages: List of message dicts.

        Yields:
            Text chunks.
        """
        # Extract system prompt
        system_prompt = None
        filtered_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                if system_prompt is None:
                    system_prompt = msg.get("content", "")
                else:
                    system_prompt += "\n\n" + msg.get("content", "")
            else:
                filtered_messages.append(msg)

        try:
            async with self.provider._async_client.messages.stream(
                model=self.provider.default_model,
                system=system_prompt or "You are a helpful assistant.",
                messages=filtered_messages,
                max_tokens=4096,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Anthropic streaming error: {e}")
            raise


def create_agent_provider(provider_type: str = "anthropic") -> AgentProvider:
    """Create an agent provider.

    Args:
        provider_type: Type of provider ('anthropic', 'openai', or 'ollama').

    Returns:
        Configured AgentProvider.
    """
    if provider_type == "anthropic":
        from test_ai.providers.anthropic_provider import AnthropicProvider
        from test_ai.config import get_settings

        settings = get_settings()
        provider = AnthropicProvider(api_key=settings.anthropic_api_key)
        return AgentProvider(provider)

    elif provider_type == "openai":
        from test_ai.providers.openai_provider import OpenAIProvider
        from test_ai.config import get_settings

        settings = get_settings()
        provider = OpenAIProvider(api_key=settings.openai_api_key)
        return AgentProvider(provider)

    elif provider_type == "ollama":
        from test_ai.providers.ollama_provider import OllamaProvider
        from test_ai.config import get_settings

        settings = get_settings()
        provider = OllamaProvider(
            host=settings.ollama_base_url,
            model=settings.ollama_default_model,
        )
        return AgentProvider(provider)

    else:
        raise ValueError(f"Unknown provider type: {provider_type}")
