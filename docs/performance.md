# Performance Tuning

## Rate Limiting

Gorgon provides two rate limiting algorithms:

**Token Bucket** — Allows burst traffic up to bucket capacity, then throttles to steady rate. Best for APIs with burst tolerance.

**Sliding Window** — Accurate per-minute/hour limits with better fairness. Used for strict compliance with provider limits.

### Configuration

```bash
# .env
RATELIMIT_OPENAI_RPM=60       # OpenAI: 60 req/min
RATELIMIT_OPENAI_TPM=90000    # OpenAI: 90K tokens/min
RATELIMIT_ANTHROPIC_RPM=60    # Claude: 60 req/min
RATELIMIT_GITHUB_RPM=30       # GitHub: 30 req/min
RATELIMIT_NOTION_RPM=30       # Notion: 30 req/min
```

## Caching

### In-Memory Cache (Default)

Zero-dependency TTL cache with FIFO eviction:

```python
from test_ai.cache import cached, async_cached

@cached(ttl=60, prefix="user")
def get_user(user_id: str): ...

@async_cached(ttl=300, prefix="api")
async def fetch_data(endpoint: str): ...
```

Default: 1000 entries max, cleanup every 100 operations.

### Redis Cache (Multi-Process)

For deployments with multiple workers:

```bash
REDIS_URL=redis://localhost:6379/0
```

Auto-detected — if `REDIS_URL` is set, the cache backend switches to Redis.

## Bulkhead Isolation

Limits concurrent requests per provider to prevent resource exhaustion:

```bash
BULKHEAD_OPENAI_CONCURRENT=10
BULKHEAD_ANTHROPIC_CONCURRENT=10
BULKHEAD_DEFAULT_TIMEOUT=30.0    # seconds
```

## Circuit Breaker

Prevents cascading failures when external APIs are down:
- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Failures exceeded threshold, requests rejected immediately
- **HALF_OPEN**: Recovery probe — single request allowed to test if service is back

## Parallel Execution

Gorgon supports fan-out/fan-in patterns for parallel agent execution. Configure via workflow YAML:

```yaml
steps:
  - id: fan_out
    type: fan_out
    params:
      items_from: "{{data_list}}"
      step_template:
        type: claude_code
        params:
          role: analyst
          prompt: "Analyze: {{item}}"
  - id: fan_in
    type: fan_in
    params:
      aggregate_as: results
    depends_on: fan_out
```

## Monitoring

Track performance via the dashboard **Metrics** page or programmatically:

```python
from test_ai.ratelimit import get_limiter_stats
from test_ai.cache import get_cache

# Rate limiter stats
stats = get_limiter_stats()

# Cache hit rate
cache = get_cache()
print(cache.stats.hit_rate)
```
