# OpenAI Integration

Gorgon wraps the OpenAI API with rate limiting, retry logic, and both sync/async support.

## Setup

```bash
# .env
OPENAI_API_KEY=sk-...
```

## Usage

```python
from test_ai.api_clients import OpenAIClient

client = OpenAIClient()

# Text completion
result = client.generate_completion(
    "Explain microservices",
    model="gpt-4o-mini",
    temperature=0.7,
    system_prompt="You are a software architect."
)

# Summarization
summary = client.summarize_text("Long article...", max_length=500)

# SOP generation
sop = client.generate_sop("employee onboarding process")
```

### Async

```python
result = await client.generate_completion_async("Explain microservices")
summary = await client.summarize_text_async("Long article...")
```

## Methods

| Method | Description |
|--------|-------------|
| `generate_completion(prompt, model, temperature, max_tokens, system_prompt)` | Chat completion |
| `summarize_text(text, max_length)` | Summarize text |
| `generate_sop(task_description)` | Generate Standard Operating Procedure |

All methods have `_async` variants.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `RATELIMIT_OPENAI_RPM` | 60 | Requests per minute |
| `RATELIMIT_OPENAI_TPM` | 90000 | Tokens per minute |
| `BULKHEAD_OPENAI_CONCURRENT` | 10 | Max concurrent requests |

## Resilience

- **Retry**: 3 attempts with exponential backoff (1s-30s)
- **Rate limiting**: Token bucket per provider
- **Bulkhead**: Concurrent request isolation
- **Circuit breaker**: Prevents cascading failures
