# Parallel Agent Execution

Gorgon supports parallel execution of AI agent tasks with intelligent rate limiting to prevent API throttling.

## Overview

When running workflows with multiple AI steps, Gorgon can execute them in parallel while:
- Respecting per-provider concurrency limits
- Adapting to rate limit (429) errors
- Coordinating across multiple processes

## Quick Start

```python
from test_ai.workflow import create_rate_limited_executor, ParallelTask

# Create executor with defaults
executor = create_rate_limited_executor()

# Define tasks
tasks = [
    ParallelTask(
        id="task1",
        step_id="task1",
        handler=my_async_handler,
        kwargs={"provider": "anthropic"},
    ),
    ParallelTask(
        id="task2",
        step_id="task2",
        handler=my_async_handler,
        kwargs={"provider": "openai"},
    ),
]

# Execute with rate limiting
result = executor.execute_parallel(tasks)
```

## Rate Limiting Layers

Gorgon implements three complementary rate limiting strategies:

### 1. Per-Provider Concurrency (Semaphores)

Limits concurrent requests per provider to prevent bursts:

```python
executor = RateLimitedParallelExecutor(
    provider_limits={
        "anthropic": 5,   # Max 5 concurrent Anthropic calls
        "openai": 8,      # Max 8 concurrent OpenAI calls
        "default": 10,    # Default for other providers
    }
)
```

### 2. Adaptive Rate Limiting

Automatically adjusts limits based on API responses:

- **On 429 error**: Reduces limit by `backoff_factor` (default 0.5)
- **On consecutive successes**: Recovers toward base limit
- **Cooldown**: Minimum time between adjustments

```python
from test_ai.workflow import AdaptiveRateLimitConfig

config = AdaptiveRateLimitConfig(
    min_concurrent=1,        # Never go below 1
    backoff_factor=0.5,      # Halve limit on 429
    recovery_factor=1.2,     # Increase by 20% on recovery
    recovery_threshold=10,   # Recover after 10 successes
    cooldown_seconds=30.0,   # Wait 30s between adjustments
)

executor = RateLimitedParallelExecutor(
    adaptive=True,
    adaptive_config=config,
)
```

### 3. Cross-Process Distributed Limiting

For multi-process or multi-instance deployments, use distributed rate limiting:

```python
executor = create_rate_limited_executor(
    distributed=True,
    anthropic_rpm=60,    # 60 requests per minute
    openai_rpm=90,       # 90 requests per minute
)
```

**Backends:**
- **Redis** (recommended for production): Set `REDIS_URL` environment variable
- **SQLite** (single-machine fallback): Automatic file-based coordination

## Workflow YAML Configuration

Configure parallel steps in workflow YAML:

```yaml
name: parallel-analysis
version: "1.0.0"
description: Analyze from multiple perspectives

steps:
  - id: parallel_analysis
    type: parallel
    params:
      max_workers: 4
      strategy: asyncio
      steps:
        - id: claude_analysis
          type: claude_code
          params:
            role: analyst
            prompt: "Analyze the security implications..."

        - id: openai_analysis
          type: openai
          params:
            prompt: "Analyze the performance aspects..."
```

## Monitoring

Get current rate limit stats:

```python
stats = executor.get_provider_stats()
# {
#     "anthropic": {
#         "base_limit": 5,
#         "current_limit": 3,        # Reduced due to 429s
#         "consecutive_successes": 5,
#         "total_429s": 2,
#         "is_throttled": True,
#         "distributed_enabled": True,
#         "distributed_rpm": 60,
#     },
#     ...
# }
```

Reset adaptive state:

```python
# Reset specific provider
executor.reset_adaptive_state("anthropic")

# Reset all providers
executor.reset_adaptive_state()
```

## Provider Detection

Tasks are automatically routed to the correct rate limit pool based on:

1. Explicit `provider` kwarg: `kwargs={"provider": "anthropic"}`
2. Step type: `step_type="claude_code"` -> anthropic
3. Handler name: `def call_claude_api()` -> anthropic
4. Default: Falls back to "default" pool

## Best Practices

### 1. Start Conservative

Begin with lower concurrency limits and increase after observing behavior:

```python
executor = create_rate_limited_executor(
    anthropic_concurrent=3,  # Start low
    openai_concurrent=5,
)
```

### 2. Enable Adaptive by Default

Adaptive rate limiting handles transient issues automatically:

```python
executor = create_rate_limited_executor(adaptive=True)  # Default
```

### 3. Use Distributed for Multiple Workers

If running multiple API instances or workers:

```python
executor = create_rate_limited_executor(
    distributed=True,
    anthropic_rpm=50,  # Leave headroom
)
```

### 4. Monitor 429 Rates

Track `total_429s` in stats to tune limits:

```python
stats = executor.get_provider_stats()
if stats["anthropic"]["total_429s"] > 10:
    logger.warning("Consider reducing anthropic_concurrent")
```

## API Reference

### RateLimitedParallelExecutor

```python
RateLimitedParallelExecutor(
    strategy: ParallelStrategy = ParallelStrategy.ASYNCIO,
    max_workers: int = 4,
    timeout: float = 300.0,
    provider_limits: dict[str, int] | None = None,
    adaptive: bool = True,
    adaptive_config: AdaptiveRateLimitConfig | None = None,
    distributed: bool = False,
    distributed_window: int = 60,
    distributed_rpm: dict[str, int] | None = None,
)
```

### create_rate_limited_executor

```python
create_rate_limited_executor(
    max_workers: int = 4,
    anthropic_concurrent: int = 5,
    openai_concurrent: int = 8,
    timeout: float = 300.0,
    adaptive: bool = True,
    backoff_factor: float = 0.5,
    recovery_threshold: int = 10,
    distributed: bool = False,
    distributed_window: int = 60,
    anthropic_rpm: int = 60,
    openai_rpm: int = 90,
) -> RateLimitedParallelExecutor
```

### Distributed Rate Limiters

```python
# Auto-detect (Redis if REDIS_URL set, else SQLite)
from test_ai.workflow import get_rate_limiter
limiter = get_rate_limiter()

# Explicit SQLite
from test_ai.workflow import SQLiteRateLimiter
limiter = SQLiteRateLimiter(db_path="/path/to/rate_limits.db")

# Explicit Redis
from test_ai.workflow import RedisRateLimiter
limiter = RedisRateLimiter(url="redis://localhost:6379/0")
```

## Troubleshooting

### Tasks Timing Out

Increase timeout or reduce concurrent tasks:

```python
executor = create_rate_limited_executor(
    timeout=600.0,      # 10 minutes
    max_workers=2,      # Reduce parallelism
)
```

### Frequent 429 Errors

1. Check current limits vs actual API quotas
2. Enable adaptive rate limiting
3. Consider distributed limiting for multiple processes

### Distributed Limiter Not Working

1. Verify `REDIS_URL` is set correctly
2. Check Redis connectivity
3. For SQLite, ensure write permissions to `~/.gorgon/`
