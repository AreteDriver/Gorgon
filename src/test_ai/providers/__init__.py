"""Multi-Provider AI Support.

Provides a unified interface for multiple AI providers (OpenAI, Anthropic, Azure,
AWS Bedrock, Google Vertex AI, Ollama) with automatic fallback, streaming support,
and provider-agnostic operations.
"""

from .base import (
    Provider,
    ProviderConfig,
    ProviderType,
    CompletionRequest,
    CompletionResponse,
    StreamChunk,
    ProviderError,
    ProviderNotConfiguredError,
    RateLimitError,
)
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .azure_openai_provider import AzureOpenAIProvider
from .bedrock_provider import BedrockProvider
from .vertex_provider import VertexProvider
from .ollama_provider import OllamaProvider
from .manager import (
    ProviderManager,
    get_provider,
    get_manager,
    list_providers,
    reset_manager,
)

__all__ = [
    # Base classes
    "Provider",
    "ProviderConfig",
    "ProviderType",
    "CompletionRequest",
    "CompletionResponse",
    "StreamChunk",
    "ProviderError",
    "ProviderNotConfiguredError",
    "RateLimitError",
    # Implementations
    "OpenAIProvider",
    "AnthropicProvider",
    "AzureOpenAIProvider",
    "BedrockProvider",
    "VertexProvider",
    "OllamaProvider",
    # Manager
    "ProviderManager",
    "get_provider",
    "get_manager",
    "list_providers",
    "reset_manager",
]
