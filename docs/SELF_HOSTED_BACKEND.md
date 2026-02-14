# Gorgon Self-Hosted LLM Backend — Claude Code Build Guide

## Mission
Build a pluggable LLM backend abstraction layer for Gorgon that enables the framework to run entirely self-hosted on local hardware with no external API dependencies. One config switch swaps between cloud API providers and local inference via Ollama. This is the architectural piece that makes Gorgon deployable in air-gapped, on-prem, and regulated enterprise environments.

## Why This Matters
Gorgon's target customers — defense, financial services, regulated enterprise — cannot send agent orchestration traffic to external APIs. A Forward Deployed Engineer at Palantir deploys Foundry into customer environments. Gorgon needs the same capability. The sentence we want to say in interviews: "I deployed my multi-agent orchestration framework on local hardware with zero external API dependencies, running a 70B parameter model for agent reasoning."

---

## Architecture Overview

```
gorgon/
├── llm/                          # NEW: LLM Backend Abstraction Layer
│   ├── __init__.py
│   ├── base.py                   # Abstract base class — LLMProvider
│   ├── config.py                 # Provider configuration & model registry
│   ├── router.py                 # Intelligent model routing per agent/task
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── anthropic.py          # Claude API provider
│   │   ├── openai.py             # OpenAI API provider  
│   │   ├── ollama.py             # Local inference via Ollama
│   │   └── mock.py               # Testing provider (deterministic responses)
│   ├── budget.py                 # Token budget integration (existing budget manager)
│   └── hardware.py               # Local hardware detection & model recommendations
├── agents/                       # EXISTING — agents consume LLMProvider interface
├── state/                        # EXISTING — SQLite checkpoint/resume
├── budget/                       # EXISTING — token budget management
├── skills/                       # EXISTING — skill library
└── workflow/                     # EXISTING — YAML workflow engine
```

---

## Core Interface: LLMProvider

This is the contract that every provider implements. Agents never call a provider directly — they call through this interface.

### File: `gorgon/llm/base.py`

```python
"""
LLM Provider abstraction for Gorgon.

Every LLM backend (API or local) implements this interface.
Agents interact with LLMs exclusively through this contract.
The router selects which provider handles each request based on
task complexity, agent role, budget, and hardware constraints.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Optional


class ModelTier(Enum):
    """Model capability tiers for routing decisions.
    
    The router uses these tiers to match agent needs to available models.
    Not every provider supports every tier.
    """
    REASONING = "reasoning"       # Complex planning, Triumvirate consensus
    STANDARD = "standard"         # General agent tasks, code generation
    FAST = "fast"                 # Simple operations, file ops, formatting
    EMBEDDING = "embedding"       # Vector embeddings for memory/search


@dataclass
class LLMRequest:
    """Standardized request to any LLM provider."""
    messages: list[dict]                    # [{"role": "user", "content": "..."}]
    system_prompt: str = ""                 # System instructions
    model_tier: ModelTier = ModelTier.STANDARD
    max_tokens: int = 4096
    temperature: float = 0.7
    stop_sequences: list[str] = field(default_factory=list)
    
    # Gorgon-specific metadata
    agent_id: str = ""                      # Which agent is making this call
    workflow_id: str = ""                    # Which workflow this belongs to
    consensus_context: bool = False         # True if this is a Triumvirate vote
    
    # Budget tracking
    budget_remaining_tokens: Optional[int] = None  # From budget manager


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    content: str                            # The generated text
    model: str                              # Actual model used (e.g., "llama3.1:70b")
    provider: str                           # Provider name (e.g., "ollama", "anthropic")
    
    # Token accounting
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    
    # Performance
    latency_ms: float = 0.0
    
    # Metadata
    finish_reason: str = ""                 # "stop", "length", "budget_exceeded"
    raw_response: Optional[dict] = None     # Provider-specific raw response


class LLMProvider(ABC):
    """Abstract base class for all LLM providers.
    
    Implement this to add a new LLM backend (cloud API, local inference,
    or custom solution). The router will handle selecting the right
    provider for each request.
    """
    
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a completion. Core method every provider must implement."""
        ...

    @abstractmethod
    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream a completion token by token. For real-time UI feedback."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider is available and responding."""
        ...

    @abstractmethod
    def available_models(self) -> list[dict]:
        """Return list of available models with their capabilities.
        
        Each dict should contain:
        - name: str (model identifier)
        - tier: ModelTier
        - context_window: int
        - supports_streaming: bool
        """
        ...

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for budget tracking. 
        Doesn't need to be exact — ballpark for budget governor."""
        ...
```

---

## Provider Implementations

### File: `gorgon/llm/providers/ollama.py`

This is the critical provider for self-hosted deployment.

```python
"""
Ollama provider for local LLM inference.

Connects to a local Ollama instance (default: http://localhost:11434).
Supports model pulling, health monitoring, and hardware-aware model selection.

Requirements:
- Ollama installed and running: https://ollama.ai
- At least one model pulled: ollama pull llama3.1:8b
"""

import asyncio
import httpx
from typing import AsyncIterator, Optional

from gorgon.llm.base import LLMProvider, LLMRequest, LLMResponse, ModelTier


# Model tier mapping — which Ollama models serve which tier
# User can override in gorgon.yaml config
DEFAULT_TIER_MODELS = {
    ModelTier.REASONING: [
        "qwen2.5:72b",         # Best reasoning at 72B, needs ~48GB RAM
        "llama3.1:70b",        # Strong reasoning, needs ~48GB RAM
        "deepseek-r1:32b",     # Good reasoning at smaller size, needs ~20GB
        "qwen2.5:32b",         # Solid mid-range, needs ~20GB
    ],
    ModelTier.STANDARD: [
        "qwen2.5:14b",         # Good general purpose, needs ~10GB
        "llama3.1:8b",         # Fast and capable, needs ~6GB
        "mistral:7b",          # Efficient, needs ~5GB
    ],
    ModelTier.FAST: [
        "qwen2.5:3b",          # Very fast, minimal tasks, needs ~2GB
        "llama3.2:3b",         # Lightweight, needs ~2GB
        "phi3:mini",           # Microsoft's small model, needs ~2GB
    ],
    ModelTier.EMBEDDING: [
        "nomic-embed-text",    # Best open embedding model
        "all-minilm",          # Lightweight alternative
    ],
}


class OllamaProvider(LLMProvider):
    """Local LLM inference via Ollama."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        tier_models: Optional[dict] = None,
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.tier_models = tier_models or DEFAULT_TIER_MODELS
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, connect=10.0),
        )
        self._available_models_cache: Optional[list[str]] = None
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate completion via Ollama API."""
        import time
        
        model = await self._select_model(request.model_tier)
        
        # Build Ollama-format messages
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(request.messages)
        
        start = time.monotonic()
        
        response = await self._client.post(
            "/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens,
                    "stop": request.stop_sequences or None,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        
        latency = (time.monotonic() - start) * 1000
        
        return LLMResponse(
            content=data["message"]["content"],
            model=model,
            provider="ollama",
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            total_tokens=data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            latency_ms=latency,
            finish_reason="stop",
            raw_response=data,
        )
    
    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream completion tokens from Ollama."""
        model = await self._select_model(request.model_tier)
        
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(request.messages)
        
        async with self._client.stream(
            "POST",
            "/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens,
                },
            },
        ) as response:
            import json as json_mod
            async for line in response.aiter_lines():
                if line:
                    chunk = json_mod.loads(line)
                    if not chunk.get("done", False):
                        yield chunk["message"]["content"]
    
    async def health_check(self) -> bool:
        """Check if Ollama is running and responsive."""
        try:
            response = await self._client.get("/api/tags")
            return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False
    
    def available_models(self) -> list[dict]:
        """Return cached list of available models."""
        # This needs the async version to be called first
        # In practice, call refresh_models() on startup
        return []
    
    async def refresh_models(self) -> list[str]:
        """Fetch currently pulled models from Ollama."""
        response = await self._client.get("/api/tags")
        response.raise_for_status()
        data = response.json()
        self._available_models_cache = [
            m["name"] for m in data.get("models", [])
        ]
        return self._available_models_cache
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate: ~4 chars per token for English."""
        return len(text) // 4
    
    async def _select_model(self, tier: ModelTier) -> str:
        """Select the best available model for the requested tier.
        
        Strategy: Walk the preference list for the tier.
        Use the first model that's actually pulled locally.
        If nothing matches the tier, fall back to any available model.
        """
        if self._available_models_cache is None:
            await self.refresh_models()
        
        available = set(self._available_models_cache or [])
        
        # Try preferred models for this tier
        for model in self.tier_models.get(tier, []):
            if model in available:
                return model
        
        # Fallback: try any model from any tier
        for tier_models in self.tier_models.values():
            for model in tier_models:
                if model in available:
                    return model
        
        raise RuntimeError(
            f"No models available for tier {tier.value}. "
            f"Available models: {available}. "
            f"Pull a model with: ollama pull llama3.1:8b"
        )
    
    async def pull_model(self, model: str) -> None:
        """Pull a model from Ollama registry. Long-running operation."""
        await self._client.post(
            "/api/pull",
            json={"name": model, "stream": False},
            timeout=httpx.Timeout(3600.0),  # Models can be large
        )
        await self.refresh_models()
    
    async def close(self):
        """Clean up HTTP client."""
        await self._client.aclose()
```

### File: `gorgon/llm/providers/anthropic.py`

```python
"""
Anthropic Claude API provider.

For cloud deployment or hybrid setups where some agents use API
and others use local inference.

Requires: ANTHROPIC_API_KEY environment variable
"""

import os
import time
from typing import AsyncIterator, Optional

from gorgon.llm.base import LLMProvider, LLMRequest, LLMResponse, ModelTier

# Lazy import — don't require anthropic SDK if using only local
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


TIER_MODELS = {
    ModelTier.REASONING: "claude-opus-4-5-20250929",
    ModelTier.STANDARD: "claude-sonnet-4-5-20250929",
    ModelTier.FAST: "claude-haiku-4-5-20251001",
}


class AnthropicProvider(LLMProvider):
    """Claude API provider for cloud deployment."""
    
    def __init__(self, api_key: Optional[str] = None):
        if not HAS_ANTHROPIC:
            raise ImportError(
                "anthropic package required: pip install anthropic"
            )
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        model = TIER_MODELS.get(request.model_tier, TIER_MODELS[ModelTier.STANDARD])
        
        start = time.monotonic()
        
        response = await self._client.messages.create(
            model=model,
            max_tokens=request.max_tokens,
            system=request.system_prompt or anthropic.NOT_GIVEN,
            messages=request.messages,
            temperature=request.temperature,
            stop_sequences=request.stop_sequences or anthropic.NOT_GIVEN,
        )
        
        latency = (time.monotonic() - start) * 1000
        
        return LLMResponse(
            content=response.content[0].text,
            model=model,
            provider="anthropic",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            latency_ms=latency,
            finish_reason=response.stop_reason or "stop",
            raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
        )
    
    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        model = TIER_MODELS.get(request.model_tier, TIER_MODELS[ModelTier.STANDARD])
        
        async with self._client.messages.stream(
            model=model,
            max_tokens=request.max_tokens,
            system=request.system_prompt or anthropic.NOT_GIVEN,
            messages=request.messages,
            temperature=request.temperature,
        ) as stream:
            async for text in stream.text_stream:
                yield text
    
    async def health_check(self) -> bool:
        try:
            # Minimal request to verify API key and connectivity
            response = await self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:
            return False
    
    def available_models(self) -> list[dict]:
        return [
            {"name": v, "tier": k, "context_window": 200000, "supports_streaming": True}
            for k, v in TIER_MODELS.items()
        ]
    
    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4
```

---

## Model Router

### File: `gorgon/llm/router.py`

```python
"""
Intelligent model routing for Gorgon agents.

The router decides which provider and model handles each LLM request
based on: agent role, task complexity, budget remaining, hardware
constraints, and provider availability.

This is where the Resource Governor (Triumvirate) interfaces with
the LLM layer — the governor sets constraints, the router honors them.
"""

from typing import Optional
from gorgon.llm.base import LLMProvider, LLMRequest, LLMResponse, ModelTier


class LLMRouter:
    """Routes LLM requests to the best available provider.
    
    Routing strategy:
    1. If only one provider is configured, use it for everything.
    2. If multiple providers available, route by tier:
       - REASONING → prefer cloud API (better quality), fall back to local
       - STANDARD → prefer local (save money), fall back to API
       - FAST → always local (speed + cost)
       - EMBEDDING → always local (no reason to pay for embeddings)
    3. Budget governor can force local-only mode mid-workflow.
    4. Health check failures trigger automatic failover.
    """
    
    def __init__(self):
        self._providers: dict[str, LLMProvider] = {}
        self._primary: Optional[str] = None
        self._fallback: Optional[str] = None
        self._force_local: bool = False
    
    def register_provider(
        self,
        name: str,
        provider: LLMProvider,
        is_primary: bool = False,
        is_fallback: bool = False,
    ):
        """Register an LLM provider with the router."""
        self._providers[name] = provider
        if is_primary:
            self._primary = name
        if is_fallback:
            self._fallback = name
    
    def force_local_only(self, enabled: bool = True):
        """Budget governor or air-gap mode: restrict to local providers only.
        
        Called by the Triumvirate resource governor when:
        - Token budget is running low
        - Network is unavailable  
        - Air-gapped deployment mode
        """
        self._force_local = enabled
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Route a request to the best available provider."""
        provider_name = await self._select_provider(request)
        provider = self._providers[provider_name]
        
        try:
            response = await provider.generate(request)
            return response
        except Exception as e:
            # Failover to fallback provider
            if self._fallback and self._fallback != provider_name:
                fallback = self._providers[self._fallback]
                return await fallback.generate(request)
            raise
    
    async def _select_provider(self, request: LLMRequest) -> str:
        """Select provider based on routing strategy."""
        
        # Air-gapped / budget-constrained: local only
        if self._force_local:
            for name, provider in self._providers.items():
                if name in ("ollama", "local", "mock"):
                    if await provider.health_check():
                        return name
            raise RuntimeError("No local provider available in force_local mode")
        
        # Tier-based routing when multiple providers exist
        if len(self._providers) > 1:
            if request.model_tier == ModelTier.FAST:
                # Always prefer local for fast/cheap tasks
                if "ollama" in self._providers:
                    return "ollama"
            
            if request.model_tier == ModelTier.EMBEDDING:
                # Always local for embeddings
                if "ollama" in self._providers:
                    return "ollama"
            
            if request.model_tier == ModelTier.REASONING:
                # Prefer cloud API for reasoning quality
                # Unless budget is tight (checked via budget_remaining_tokens)
                if request.budget_remaining_tokens and request.budget_remaining_tokens < 10000:
                    if "ollama" in self._providers:
                        return "ollama"
                for name in ("anthropic", "openai"):
                    if name in self._providers:
                        return name
        
        # Default: primary provider
        if self._primary and self._primary in self._providers:
            return self._primary
        
        # Last resort: first available
        return next(iter(self._providers))
```

---

## Hardware Detection

### File: `gorgon/llm/hardware.py`

```python
"""
Hardware detection for local model recommendations.

Detects available compute resources and recommends which models
can run effectively. The Resource Governor uses this data to set
agent caps and model tier limits.

Supports: macOS (Apple Silicon), Linux (NVIDIA GPU), generic (CPU only)
"""

import platform
import subprocess
import shutil
from dataclasses import dataclass
from typing import Optional


@dataclass
class HardwareProfile:
    """Detected hardware capabilities for LLM inference."""
    platform: str                           # "macos_arm64", "linux_nvidia", "linux_cpu"
    total_memory_gb: float                  # Total system RAM
    available_memory_gb: float              # Currently available RAM
    gpu_name: Optional[str] = None          # GPU model name
    gpu_vram_gb: Optional[float] = None     # GPU VRAM (NVIDIA only)
    unified_memory: bool = False            # Apple Silicon unified memory
    cpu_cores: int = 0
    
    # Recommendations
    max_model_params_b: float = 0.0         # Largest model (in billions) that fits
    recommended_tier: str = ""              # "reasoning", "standard", "fast"
    recommended_models: list[str] = None
    
    def __post_init__(self):
        if self.recommended_models is None:
            self.recommended_models = []


def detect_hardware() -> HardwareProfile:
    """Detect local hardware and compute model recommendations.
    
    Call this on Gorgon startup. The Resource Governor uses the
    profile to set agent limits and model routing preferences.
    """
    import os
    import psutil
    
    system = platform.system()
    machine = platform.machine()
    
    total_mem = psutil.virtual_memory().total / (1024**3)
    avail_mem = psutil.virtual_memory().available / (1024**3)
    cores = os.cpu_count() or 1
    
    profile = HardwareProfile(
        platform=f"{system.lower()}_{machine}",
        total_memory_gb=round(total_mem, 1),
        available_memory_gb=round(avail_mem, 1),
        cpu_cores=cores,
    )
    
    # Apple Silicon detection
    if system == "Darwin" and machine == "arm64":
        profile.unified_memory = True
        profile.platform = "macos_arm64"
        # On Apple Silicon, unified memory is shared between CPU and GPU
        # Models can use nearly all of it for inference
        _recommend_apple_silicon(profile)
    
    # NVIDIA GPU detection
    elif shutil.which("nvidia-smi"):
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(", ")
                profile.gpu_name = parts[0]
                profile.gpu_vram_gb = round(float(parts[1]) / 1024, 1)
                profile.platform = "linux_nvidia"
                _recommend_nvidia(profile)
        except (subprocess.TimeoutExpired, ValueError, IndexError):
            _recommend_cpu_only(profile)
    
    else:
        _recommend_cpu_only(profile)
    
    return profile


def _recommend_apple_silicon(profile: HardwareProfile):
    """Recommendations for Apple Silicon Macs.
    
    Key insight: unified memory means the full RAM pool is available
    for model weights. A Mac Studio with 192GB can run 70B+ models.
    Rule of thumb: ~1.2GB per billion parameters (Q4 quantized).
    """
    usable_gb = profile.total_memory_gb * 0.75  # Leave 25% for system
    profile.max_model_params_b = round(usable_gb / 1.2, 0)
    
    if profile.total_memory_gb >= 128:
        profile.recommended_tier = "reasoning"
        profile.recommended_models = [
            "qwen2.5:72b", "llama3.1:70b", "deepseek-r1:70b",
            "qwen2.5:32b", "llama3.1:8b",
        ]
    elif profile.total_memory_gb >= 64:
        profile.recommended_tier = "reasoning"
        profile.recommended_models = [
            "qwen2.5:32b", "deepseek-r1:32b",
            "qwen2.5:14b", "llama3.1:8b",
        ]
    elif profile.total_memory_gb >= 32:
        profile.recommended_tier = "standard"
        profile.recommended_models = [
            "qwen2.5:14b", "llama3.1:8b", "mistral:7b",
        ]
    elif profile.total_memory_gb >= 16:
        profile.recommended_tier = "standard"
        profile.recommended_models = [
            "llama3.1:8b", "mistral:7b", "phi3:mini",
        ]
    else:
        profile.recommended_tier = "fast"
        profile.recommended_models = ["phi3:mini", "qwen2.5:3b"]


def _recommend_nvidia(profile: HardwareProfile):
    """Recommendations for NVIDIA GPU systems.
    
    VRAM is the constraint — model must fit entirely in GPU memory
    for good performance. System RAM used for overflow but much slower.
    """
    vram = profile.gpu_vram_gb or 0
    profile.max_model_params_b = round(vram / 1.2, 0)
    
    if vram >= 48:  # A100, A6000, etc.
        profile.recommended_tier = "reasoning"
        profile.recommended_models = [
            "qwen2.5:72b", "llama3.1:70b",
            "qwen2.5:32b", "llama3.1:8b",
        ]
    elif vram >= 24:  # RTX 4090, A5000
        profile.recommended_tier = "standard"
        profile.recommended_models = [
            "qwen2.5:14b", "llama3.1:8b", "mistral:7b",
        ]
    elif vram >= 12:  # RTX 4070, etc.
        profile.recommended_tier = "standard"
        profile.recommended_models = [
            "llama3.1:8b", "mistral:7b", "phi3:mini",
        ]
    elif vram >= 8:
        profile.recommended_tier = "fast"
        profile.recommended_models = ["phi3:mini", "qwen2.5:3b"]
    else:
        _recommend_cpu_only(profile)


def _recommend_cpu_only(profile: HardwareProfile):
    """CPU-only inference. Slow but functional for small models."""
    profile.recommended_tier = "fast"
    profile.max_model_params_b = 3
    profile.recommended_models = ["phi3:mini", "qwen2.5:3b"]
```

---

## Configuration

### File: `gorgon/llm/config.py`

The user configures providers in `gorgon.yaml` at the project root:

```yaml
# gorgon.yaml — LLM Configuration

llm:
  # Deployment mode: "cloud", "local", "hybrid"
  # cloud: API providers only
  # local: Ollama only (air-gapped safe)
  # hybrid: route by tier — reasoning via API, everything else local
  mode: hybrid

  providers:
    ollama:
      enabled: true
      base_url: "http://localhost:11434"
      # Override default tier→model mapping
      tier_models:
        reasoning: ["qwen2.5:72b", "deepseek-r1:32b"]
        standard: ["llama3.1:8b"]
        fast: ["qwen2.5:3b"]
        embedding: ["nomic-embed-text"]
    
    anthropic:
      enabled: true
      # API key from environment: ANTHROPIC_API_KEY
      tier_models:
        reasoning: "claude-opus-4-5-20250929"
        standard: "claude-sonnet-4-5-20250929"
        fast: "claude-haiku-4-5-20251001"
    
    openai:
      enabled: false
  
  # Resource constraints (feeds into Triumvirate Resource Governor)
  budget:
    max_tokens_per_workflow: 500000
    max_tokens_per_agent: 50000
    api_cost_limit_daily_usd: 10.00
    prefer_local_under_tokens: 10000  # Use local if budget below this
  
  # Hardware overrides (auto-detected if not specified)
  hardware:
    max_memory_percent: 75      # Don't use more than 75% of RAM for models
    max_concurrent_models: 2    # Ollama can run multiple, but at memory cost
```

---

## Integration with Triumvirate Resource Governor

The Resource Governor (which the Zorya trio consults) gets a new data source:

```python
# In the existing resource governor, add hardware awareness:

async def evaluate_agent_spawn(self, request: AgentSpawnRequest) -> GovernorDecision:
    """Zorya consult: can we spawn this agent given current resources?"""
    
    # Existing checks: CPU, memory, agent count
    cpu_ok = self.metrics.cpu_percent < self.caps.cpu_max
    mem_ok = self.metrics.memory_percent < self.caps.memory_max
    agents_ok = self.metrics.active_agents < self.caps.max_agents
    
    # NEW: LLM budget check
    budget_ok = self.budget_manager.can_afford(
        agent_type=request.agent_type,
        estimated_tokens=request.estimated_tokens,
    )
    
    # NEW: Hardware can support the model tier this agent needs
    hardware_ok = self.hardware_profile.max_model_params_b >= _min_params_for_tier(
        request.model_tier
    )
    
    # If budget is low, force local-only mode
    if not budget_ok and self.llm_router:
        self.llm_router.force_local_only(True)
        # Re-check: can we afford local inference? (free)
        budget_ok = True  # Local inference has no token cost
    
    return GovernorDecision(
        approved=all([cpu_ok, mem_ok, agents_ok, budget_ok, hardware_ok]),
        constraints={
            "model_tier": request.model_tier if hardware_ok else ModelTier.FAST,
            "force_local": self.llm_router._force_local,
        },
    )
```

---

## Target Hardware Profiles

| Machine | Memory | GPU | Max Model | Gorgon Capability |
|---------|--------|-----|-----------|-------------------|
| **Mac Studio M4 Ultra 192GB** | 192GB unified | Integrated | 70B+ Q4 | Full reasoning tier. Run Triumvirate + 8 agents on 70B. Demo machine. |
| **Mac Studio M4 Ultra 128GB** | 128GB unified | Integrated | 70B Q4 (tight) | Full reasoning tier. 32B comfortable, 70B with less headroom. |
| **Mac Studio M4 Max 64GB** | 64GB unified | Integrated | 32B Q4 | Standard tier with 32B reasoning. Good development machine. |
| **ASUS (RTX 4090)** | 32-64GB + 24GB VRAM | RTX 4090 | 14B in VRAM | Standard tier. 8B-14B fast in VRAM, 32B+ spills to system RAM (slow). |
| **Linux server (A100 80GB)** | 256GB+ | A100 80GB | 70B+ | Enterprise deployment. Full reasoning tier in GPU. |
| **Laptop / basic desktop** | 16GB | None | 8B Q4 | Fast tier only. Functional for demos and light workflows. |

**Recommendation for portfolio demos:** Mac Studio M4 Ultra 192GB is the sweet spot. Run `qwen2.5:72b` for Triumvirate reasoning, `llama3.1:8b` for standard agents, `qwen2.5:3b` for fast ops — all simultaneously, all local, zero API cost. That's a Palantir-ready demo.

---

## Build Order

Execute these in sequence. Each step is independently testable.

### Step 1: Base Interface + Mock Provider
```bash
# Create the module structure
mkdir -p gorgon/llm/providers
touch gorgon/llm/__init__.py
touch gorgon/llm/providers/__init__.py

# Implement:
# 1. gorgon/llm/base.py (LLMProvider, LLMRequest, LLMResponse, ModelTier)
# 2. gorgon/llm/providers/mock.py (returns deterministic responses for testing)

# Test:
pytest tests/llm/test_base.py -v
```

**Prompt for Claude Code:**
```
Read GORGON_SELF_HOSTED_BACKEND.md. Implement Step 1: base.py with 
LLMProvider ABC, LLMRequest, LLMResponse, ModelTier dataclasses. 
Then implement mock.py provider that returns configurable deterministic 
responses. Write tests in tests/llm/test_base.py covering all dataclass 
creation and mock provider generate/stream/health_check.
```

### Step 2: Ollama Provider
```bash
# Implement gorgon/llm/providers/ollama.py
# Requires: pip install httpx
# Requires: Ollama running locally with at least one model

# Test (integration — needs running Ollama):
pytest tests/llm/test_ollama.py -v

# Test (unit — mocked HTTP):
pytest tests/llm/test_ollama_unit.py -v
```

**Prompt for Claude Code:**
```
Read GORGON_SELF_HOSTED_BACKEND.md. Implement Step 2: Ollama provider 
in gorgon/llm/providers/ollama.py. Use httpx async client. Implement 
generate, stream, health_check, refresh_models, pull_model, and 
_select_model (tier-based model selection with fallback). Write both 
unit tests (mocked HTTP with respx or similar) and integration test 
markers for live Ollama testing.
```

### Step 3: Anthropic Provider
```bash
# Implement gorgon/llm/providers/anthropic.py
# Requires: pip install anthropic

# Test:
pytest tests/llm/test_anthropic.py -v
```

**Prompt for Claude Code:**
```
Read GORGON_SELF_HOSTED_BACKEND.md. Implement Step 3: Anthropic provider 
in gorgon/llm/providers/anthropic.py. Lazy import anthropic SDK. Map 
ModelTier to Claude model names. Implement generate and stream using 
the async Anthropic client. Write unit tests with mocked API responses.
```

### Step 4: Router
```bash
# Implement gorgon/llm/router.py
# No new dependencies

# Test:
pytest tests/llm/test_router.py -v
```

**Prompt for Claude Code:**
```
Read GORGON_SELF_HOSTED_BACKEND.md. Implement Step 4: LLMRouter in 
gorgon/llm/router.py. Register multiple providers, route by tier 
(reasoning→API, fast→local, standard→configurable), support 
force_local_only mode for budget governor, implement failover on 
provider errors. Write tests covering all routing scenarios: 
single provider, multi-provider tier routing, force_local, failover, 
budget-triggered local switch.
```

### Step 5: Hardware Detection
```bash
# Implement gorgon/llm/hardware.py
# Requires: pip install psutil

# Test:
pytest tests/llm/test_hardware.py -v
```

**Prompt for Claude Code:**
```
Read GORGON_SELF_HOSTED_BACKEND.md. Implement Step 5: hardware.py 
with detect_hardware() that identifies Apple Silicon (unified memory), 
NVIDIA GPU (nvidia-smi), or CPU-only. Generate model recommendations 
based on available memory/VRAM. Write tests that mock platform detection 
for each hardware profile.
```

### Step 6: Config Loader + Integration
```bash
# Implement gorgon/llm/config.py
# Reads gorgon.yaml, instantiates providers, wires up router
# Requires: pip install pyyaml

# Integration test:
pytest tests/llm/test_integration.py -v
```

**Prompt for Claude Code:**
```
Read GORGON_SELF_HOSTED_BACKEND.md. Implement Step 6: config.py that 
loads the llm section from gorgon.yaml, instantiates the configured 
providers, registers them with the router, and applies budget/hardware 
constraints. Create a factory function create_llm_router(config_path) 
that returns a fully configured LLMRouter. Write integration tests 
that verify the full chain: config → providers → router → generate.
```

### Step 7: Wire Into Existing Agent Base Class
```bash
# Modify the existing agent base class to use LLMRouter
# instead of direct provider calls.
# This is the only step that touches existing Gorgon code.
```

**Prompt for Claude Code:**
```
Read GORGON_SELF_HOSTED_BACKEND.md. The existing agent base class 
needs to accept an LLMRouter instance and use it for all LLM calls. 
Find the agent base class, add router as a constructor parameter, 
and replace any direct API calls with router.generate(). Ensure 
agent_id and workflow_id are populated on every LLMRequest for 
budget tracking. Do not break existing tests.
```

---

## Testing Strategy

```
tests/llm/
├── test_base.py              # Dataclass creation, enum values
├── test_mock_provider.py     # Mock provider deterministic behavior
├── test_ollama_unit.py       # Ollama provider with mocked HTTP
├── test_ollama_integration.py # Requires running Ollama (marked slow)
├── test_anthropic.py         # Anthropic provider with mocked SDK
├── test_router.py            # All routing scenarios
├── test_hardware.py          # Hardware detection with mocked platform
├── test_config.py            # YAML config loading
└── test_integration.py       # Full chain: config → router → generate
```

Mark integration tests that need real services:
```python
import pytest

@pytest.mark.integration
@pytest.mark.skipif(not ollama_available(), reason="Ollama not running")
async def test_ollama_live_generate():
    ...
```

---

## Dependencies

Add to `pyproject.toml`:
```toml
[project.optional-dependencies]
local = [
    "httpx>=0.25.0",      # Ollama HTTP client
    "psutil>=5.9.0",      # Hardware detection
]
cloud = [
    "anthropic>=0.40.0",  # Claude API
    "openai>=1.0.0",      # OpenAI API (optional)
]
all = [
    "httpx>=0.25.0",
    "psutil>=5.9.0", 
    "anthropic>=0.40.0",
]
```

Install for self-hosted only: `pip install gorgon[local]`
Install for cloud only: `pip install gorgon[cloud]`
Install everything: `pip install gorgon[all]`

---

## The Demo Script

When the backend is built, this is the portfolio demo:

```python
"""demo_self_hosted.py — Gorgon running fully local."""

import asyncio
from gorgon.llm.hardware import detect_hardware
from gorgon.llm.config import create_llm_router

async def main():
    # Detect what we're running on
    hw = detect_hardware()
    print(f"Hardware: {hw.platform}")
    print(f"Memory: {hw.total_memory_gb}GB ({hw.available_memory_gb}GB available)")
    print(f"Max model: {hw.max_model_params_b}B parameters")
    print(f"Recommended models: {hw.recommended_models}")
    print()
    
    # Create router in local-only mode
    router = await create_llm_router("gorgon.yaml")
    router.force_local_only(True)
    
    # Triumvirate reasoning request
    from gorgon.llm.base import LLMRequest, ModelTier
    
    response = await router.generate(LLMRequest(
        messages=[{"role": "user", "content": "Evaluate this plan: ..."}],
        system_prompt="You are Zorya Utrennyaya, the optimistic executor...",
        model_tier=ModelTier.REASONING,
        agent_id="zorya_utrennyaya",
    ))
    
    print(f"Provider: {response.provider}")
    print(f"Model: {response.model}")
    print(f"Tokens: {response.total_tokens}")
    print(f"Latency: {response.latency_ms:.0f}ms")
    print(f"Response: {response.content[:200]}...")

asyncio.run(main())
```

**The interview sentence:** "Gorgon's LLM backend is pluggable — one config switch moves the entire framework from cloud API to local inference. I've run it fully air-gapped on a Mac Studio with a 70B parameter model driving the Triumvirate consensus engine. Zero external dependencies."

---

## What NOT To Do

- Do not hardcode any provider or model name in agent code — always go through the router
- Do not import `anthropic` or `openai` at module level — lazy imports only, so local-only installs don't need cloud SDKs
- Do not assume network availability anywhere in the agent layer
- Do not skip the hardware detection step — it prevents OOM crashes from loading too-large models
- Do not put API keys in config files — environment variables only
- Do not run multiple large models simultaneously via Ollama without checking hardware.max_concurrent_models
