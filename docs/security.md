# Security Best Practices

## Authentication

Gorgon uses token-based authentication with cryptographically secure tokens (`secrets.token_urlsafe(32)`).

```bash
# .env
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(48))">
API_CREDENTIALS=admin:<sha256-hash>
ALLOW_DEMO_AUTH=false
```

Generate password hashes:
```bash
python -c "from hashlib import sha256; print(sha256(b'your_password').hexdigest())"
```

## Field-Level Encryption

Sensitive data (API keys, tokens, PII) can be encrypted at rest using Fernet symmetric encryption with PBKDF2-HMAC-SHA256 key derivation (480,000 iterations).

Encrypted values are prefixed with `enc:` for identification.

## Brute Force Protection

Built-in per-IP rate limiting with exponential backoff:
- **Auth endpoints**: 5 attempts/minute, 20/hour
- **General endpoints**: 60/minute, 300/hour
- **Extended blocks**: 24-hour lockout after 10+ failures

## Request Size Limits

Middleware enforces body size limits by content type:
- JSON: 1 MB
- Form data: 50 MB
- General: 10 MB

## Production Checklist

```
SECRET_KEY          ≥32 characters, not the default
DATABASE_URL        PostgreSQL (not SQLite)
ALLOW_DEMO_AUTH     false
PRODUCTION          true
DEBUG               false
LOG_FORMAT          json
SANITIZE_LOGS       true
```

The `settings.is_production_safe` property validates all of the above. Violations raise errors when `PRODUCTION=true`.

## Log Sanitization

When `SANITIZE_LOGS=true`, sensitive data (API keys, tokens, passwords) is redacted from log output.

## Shell Execution

Workflow shell steps are constrained:
- **Timeout**: 300s default (`SHELL_TIMEOUT_SECONDS`)
- **Output limit**: 10 MB (`SHELL_MAX_OUTPUT_BYTES`)
- **Command whitelist**: Optional (`SHELL_ALLOWED_COMMANDS`)

## Credential Management

- Never commit `.env` files
- Use environment variables for all secrets
- Rotate tokens regularly
- Gmail tokens stored with 600 permissions (user-read only)
- Use HTTPS in production for token transmission
