"""Unified streaming adapter for all providers."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from test_ai.providers.base import (
    CompletionRequest,
    Provider,
    ProviderError,
    ProviderType,
)

logger = logging.getLogger(__name__)


async def stream_completion(
    provider: Provider,
    messages: list[dict[str, str]],
    system_prompt: str | None = None,
    model: str | None = None,
) -> AsyncGenerator[str, None]:
    """Unified streaming interface for any provider.

    Detects provider type and uses the best available streaming method:
    - Anthropic: native messages.stream() via _async_client
    - OpenAI: native chat.completions.create(stream=True)
    - Ollama: native httpx streaming via complete_stream_async()
    - Fallback: complete_async() yielding single chunk

    Yields:
        Text chunks as strings.
    """
    if not provider._initialized:
        provider.initialize()

    # Extract system prompt from messages if not provided
    if system_prompt is None:
        system_parts = []
        for msg in messages:
            if msg.get("role") == "system":
                system_parts.append(msg.get("content", ""))
        if system_parts:
            system_prompt = "\n\n".join(system_parts)

    # Filter out system messages for the message list
    filtered = [m for m in messages if m.get("role") != "system"]

    # Route to best streaming method per provider type
    try:
        if provider.provider_type == ProviderType.ANTHROPIC:
            async for chunk in _stream_anthropic(
                provider, filtered, system_prompt, model
            ):
                yield chunk
        elif provider.provider_type == ProviderType.OPENAI:
            async for chunk in _stream_openai(provider, filtered, system_prompt, model):
                yield chunk
        elif provider.provider_type == ProviderType.OLLAMA:
            async for chunk in _stream_ollama(provider, filtered, system_prompt, model):
                yield chunk
        else:
            async for chunk in _stream_fallback(
                provider, filtered, system_prompt, model
            ):
                yield chunk
    except ProviderError:
        raise
    except Exception as e:
        logger.warning(f"Streaming failed, falling back to non-streaming: {e}")
        async for chunk in _stream_fallback(provider, filtered, system_prompt, model):
            yield chunk


async def _stream_anthropic(
    provider: Provider,
    messages: list[dict[str, str]],
    system_prompt: str | None,
    model: str | None,
) -> AsyncGenerator[str, None]:
    """Stream via Anthropic's native messages.stream() API."""
    client = getattr(provider, "_async_client", None)
    if client is None:
        raise ProviderError("Anthropic async client not available")

    async with client.messages.stream(
        model=model or provider.default_model,
        system=system_prompt or "You are a helpful assistant.",
        messages=messages,
        max_tokens=4096,
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def _stream_openai(
    provider: Provider,
    messages: list[dict[str, str]],
    system_prompt: str | None,
    model: str | None,
) -> AsyncGenerator[str, None]:
    """Stream via OpenAI's native streaming API."""
    client = getattr(provider, "_async_client", None)
    if client is None:
        raise ProviderError("OpenAI async client not available")

    api_messages: list[dict[str, str]] = []
    if system_prompt:
        api_messages.append({"role": "system", "content": system_prompt})
    api_messages.extend(messages)

    stream = await client.chat.completions.create(
        model=model or provider.default_model,
        messages=api_messages,
        max_tokens=4096,
        stream=True,
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def _stream_ollama(
    provider: Provider,
    messages: list[dict[str, str]],
    system_prompt: str | None,
    model: str | None,
) -> AsyncGenerator[str, None]:
    """Stream via Ollama's complete_stream_async (httpx streaming)."""
    request = CompletionRequest(
        prompt=messages[-1].get("content", "") if messages else "",
        system_prompt=system_prompt,
        model=model,
        messages=messages,
    )
    async for chunk in provider.complete_stream_async(request):
        if chunk.content:
            yield chunk.content


async def _stream_fallback(
    provider: Provider,
    messages: list[dict[str, str]],
    system_prompt: str | None,
    model: str | None,
) -> AsyncGenerator[str, None]:
    """Fallback: single async completion yielded as one chunk."""
    request = CompletionRequest(
        prompt=messages[-1].get("content", "") if messages else "",
        system_prompt=system_prompt,
        model=model,
        messages=messages,
    )
    response = await provider.complete_async(request)
    yield response.content
