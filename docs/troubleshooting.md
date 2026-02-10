# Troubleshooting

## Authentication

| Error | Cause | Fix |
|-------|-------|-----|
| "Invalid token" | Token expired | Re-authenticate via login endpoint |
| "Auth failed" | Wrong credentials | Verify username and password hash |
| "Demo auth disabled" | Production mode | Set `ALLOW_DEMO_AUTH=true` for dev |
| "Bearer token missing" | No auth header | Add `Authorization: Bearer <token>` |

## Configuration

| Error | Cause | Fix |
|-------|-------|-----|
| "Insecure secret key" | Default SECRET_KEY | Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| "SQLite in production" | DATABASE_URL not set | Use PostgreSQL: `postgresql://user:pass@host/db` |
| "Module not found" | PYTHONPATH issue | Use `poetry run python ...` or set `PYTHONPATH=src` |
| "pydantic_settings missing" | Deps not installed | Run `poetry install` or `pip install -e ".[dev]"` |

## Rate Limiting

| Error | Meaning | Fix |
|-------|---------|-----|
| HTTP 429 | Too many requests | Wait for `retry_after` header value |
| "Brute force blocked" | Failed auth attempts | Wait 1min-1hr (exponential backoff) |
| "Token limit exceeded" | Token budget exhausted | Reduce prompt size or increase budget |

## API Integrations

| Error | Cause | Fix |
|-------|-------|-----|
| "OpenAI API error" | Invalid/expired key | Check `OPENAI_API_KEY` in `.env` |
| "GitHub not configured" | No token | Set `GITHUB_TOKEN=ghp_...` |
| "Notion not configured" | No token | Set `NOTION_TOKEN=secret_...` |
| "Gmail auth failed" | OAuth token expired | Delete `token.json`, re-authenticate |

## Dashboard

| Issue | Fix |
|-------|-----|
| Dashboard won't start | Check `streamlit` installed: `pip install streamlit` |
| "No workflows available" | Create workflows in Builder or Workflows page first |
| Pages show errors | Check `.env` has required API keys |

## Tests

| Issue | Fix |
|-------|-----|
| Collection errors | Run `poetry install` to install all deps |
| Tests hang | Check for unmocked external API calls |
| Flaky rate limit tests | Use longer time windows in test config |
| SECRET_KEY warning | Expected in tests — test fixtures use test values |

## Common Commands

```bash
# Check configuration
python -c "from test_ai.config import get_settings; s = get_settings(); print(s.is_production_safe)"

# Verify API keys
python -c "from test_ai.api_clients import OpenAIClient; print(OpenAIClient().generate_completion('hello'))"

# Reset Gmail auth
rm token.json

# Check logs
ls -la logs/workflow_*.json
```
