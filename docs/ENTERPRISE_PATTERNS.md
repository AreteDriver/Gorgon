# Enterprise Deployment Patterns

This guide covers deployment patterns for Gorgon in enterprise environments, from small teams to large organizations.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Enterprise Gorgon Deployment                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   Team A     │    │   Team B     │    │   Team C     │          │
│  │  Workflows   │    │  Workflows   │    │  Workflows   │          │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │
│         │                   │                   │                   │
│         └───────────────────┼───────────────────┘                   │
│                             │                                        │
│                    ┌────────▼────────┐                              │
│                    │  Gorgon Core    │                              │
│                    │  Orchestrator   │                              │
│                    └────────┬────────┘                              │
│                             │                                        │
│         ┌───────────────────┼───────────────────┐                   │
│         │                   │                   │                   │
│  ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐            │
│  │   Claude    │    │   OpenAI    │    │   Custom    │            │
│  │   Agents    │    │   Agents    │    │   Agents    │            │
│  └─────────────┘    └─────────────┘    └─────────────┘            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Deployment Tiers

### Tier 1: Single Team (1-5 developers)

**Use Case**: Small team automating development workflows

**Architecture**:
- Single Gorgon instance
- Local SQLite for metrics
- Shared workflow definitions in git

**Resources**:
- 1 CPU, 2GB RAM
- 10GB storage

```yaml
# docker-compose.yml
version: '3.8'
services:
  gorgon:
    image: gorgon:latest
    environment:
      - GORGON_ENV=development
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./workflows:/app/workflows
      - ./data:/app/data
    ports:
      - "8501:8501"
```

### Tier 2: Department (5-20 developers)

**Use Case**: Multiple teams sharing infrastructure

**Architecture**:
- Gorgon with PostgreSQL backend
- Redis for caching and job queues
- Centralized workflow registry
- Team-based access control

**Resources**:
- 2-4 CPU, 4-8GB RAM
- 50GB storage
- Managed PostgreSQL

```yaml
version: '3.8'
services:
  gorgon:
    image: gorgon:latest
    environment:
      - GORGON_ENV=production
      - DATABASE_URL=postgresql://...
      - REDIS_URL=redis://redis:6379
    deploy:
      replicas: 2

  redis:
    image: redis:7-alpine

  postgres:
    image: postgres:15
    volumes:
      - pgdata:/var/lib/postgresql/data
```

### Tier 3: Enterprise (20+ developers, multiple departments)

**Use Case**: Organization-wide AI workflow platform

**Architecture**:
- Kubernetes deployment
- Multi-tenant isolation
- SSO integration (SAML/OIDC)
- Audit logging
- Rate limiting per team

**Resources**:
- Kubernetes cluster
- Managed database (RDS/Cloud SQL)
- Redis cluster
- S3/GCS for artifacts

---

## Security Patterns

### API Key Management

```python
# config/secrets.py
from pydantic_settings import BaseSettings

class SecureSettings(BaseSettings):
    """Secure configuration with validation."""

    anthropic_api_key: str
    openai_api_key: str | None = None

    # Rotation support
    anthropic_api_key_secondary: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

**Best Practices**:
1. Use environment variables, never hardcode
2. Rotate keys quarterly
3. Use separate keys per environment (dev/staging/prod)
4. Implement key rotation without downtime

### Network Security

```yaml
# kubernetes/network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: gorgon-network-policy
spec:
  podSelector:
    matchLabels:
      app: gorgon
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: allowed-namespace
  egress:
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
      ports:
        - port: 443
          protocol: TCP
```

### Audit Logging

```python
# All workflow executions are logged
{
    "timestamp": "2025-01-18T10:30:00Z",
    "event": "workflow_execution",
    "workflow_id": "code_review",
    "user": "developer@company.com",
    "team": "platform",
    "duration_ms": 4523,
    "tokens_used": 1250,
    "status": "success"
}
```

---

## Multi-Tenancy

### Namespace Isolation

Each team gets an isolated namespace:

```
/workflows/
├── team-a/
│   ├── code-review.json
│   └── deploy-pipeline.json
├── team-b/
│   └── data-pipeline.json
└── shared/
    └── common-transforms.json
```

### Resource Quotas

```yaml
# kubernetes/resource-quota.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-a-quota
  namespace: gorgon-team-a
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
```

### Token Budget Management

```python
# Per-team token budgets
TEAM_BUDGETS = {
    "team-a": {
        "daily_limit": 100000,
        "monthly_limit": 2000000,
        "alert_threshold": 0.8,
    },
    "team-b": {
        "daily_limit": 50000,
        "monthly_limit": 1000000,
        "alert_threshold": 0.8,
    },
}
```

---

## High Availability

### Load Balancing

```yaml
# kubernetes/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: gorgon-ingress
  annotations:
    nginx.ingress.kubernetes.io/upstream-hash-by: "$request_uri"
spec:
  rules:
    - host: gorgon.company.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: gorgon
                port:
                  number: 8501
```

### Database Replication

```yaml
# PostgreSQL with read replicas
primary:
  host: gorgon-db-primary.region.rds.amazonaws.com

replicas:
  - host: gorgon-db-replica-1.region.rds.amazonaws.com
  - host: gorgon-db-replica-2.region.rds.amazonaws.com
```

### Failover Strategy

1. **Active-Passive**: Secondary instance on standby
2. **Active-Active**: Multiple regions with data sync
3. **Circuit Breaker**: Graceful degradation when AI providers fail

```python
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60)
def call_claude_api(prompt: str) -> str:
    """API call with circuit breaker protection."""
    return client.complete(prompt)
```

---

## Monitoring & Observability

### Metrics Collection

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram

workflow_executions = Counter(
    'gorgon_workflow_executions_total',
    'Total workflow executions',
    ['workflow_id', 'status', 'team']
)

execution_duration = Histogram(
    'gorgon_execution_duration_seconds',
    'Workflow execution duration',
    ['workflow_id']
)
```

### Alerting Rules

```yaml
# prometheus/alerts.yaml
groups:
  - name: gorgon
    rules:
      - alert: HighFailureRate
        expr: |
          rate(gorgon_workflow_executions_total{status="failed"}[5m])
          / rate(gorgon_workflow_executions_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High workflow failure rate"

      - alert: TokenBudgetExceeded
        expr: gorgon_tokens_used_daily > gorgon_token_budget_daily * 0.9
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Team approaching token budget limit"
```

### Dashboard Queries

```promql
# Workflow success rate
sum(rate(gorgon_workflow_executions_total{status="success"}[1h]))
/ sum(rate(gorgon_workflow_executions_total[1h]))

# P99 execution latency
histogram_quantile(0.99,
  rate(gorgon_execution_duration_seconds_bucket[5m])
)

# Token usage by team
sum by (team) (increase(gorgon_tokens_used_total[24h]))
```

---

## Disaster Recovery

### Backup Strategy

| Component | Frequency | Retention | Method |
|-----------|-----------|-----------|--------|
| Workflows | Continuous | Git history | Git push |
| Metrics DB | Hourly | 30 days | pg_dump |
| Execution logs | Daily | 90 days | S3 lifecycle |
| Configurations | On change | Versioned | Git/Vault |

### Recovery Procedures

1. **Workflow Recovery**: Clone from git repository
2. **Database Recovery**: Restore from latest backup
3. **Full Recovery**: Terraform/Pulumi infrastructure rebuild

```bash
# Restore from backup
pg_restore -d gorgon_metrics backup_2025-01-18.dump

# Verify integrity
python -m gorgon.cli verify-db
```

---

## Cost Management

### Token Usage Optimization

1. **Prompt Caching**: Cache repeated prompts
2. **Model Selection**: Use appropriate model per task
3. **Batching**: Combine similar requests

```python
# Model selection by task complexity
MODEL_SELECTION = {
    "simple_transform": "claude-3-haiku",
    "code_review": "claude-3-sonnet",
    "architecture_planning": "claude-3-opus",
}
```

### Cost Allocation

```python
# Tag all API calls with team/project
def track_cost(team: str, project: str, tokens: int):
    cost = tokens * COST_PER_TOKEN
    metrics.record_cost(team, project, cost)
```

---

## Migration Guide

### From Single Instance to Multi-Tenant

1. **Export existing workflows**:
   ```bash
   gorgon export --all --output workflows-backup/
   ```

2. **Deploy new infrastructure**:
   ```bash
   terraform apply -var-file=enterprise.tfvars
   ```

3. **Import with namespace mapping**:
   ```bash
   gorgon import --source workflows-backup/ --namespace team-a
   ```

4. **Verify and cutover**:
   ```bash
   gorgon verify --namespace team-a
   gorgon dns-cutover --confirm
   ```

---

## Support Matrix

| Feature | Tier 1 | Tier 2 | Tier 3 |
|---------|--------|--------|--------|
| Workflows | ✅ | ✅ | ✅ |
| Dashboard | ✅ | ✅ | ✅ |
| Multi-tenant | ❌ | ✅ | ✅ |
| SSO | ❌ | Optional | ✅ |
| Audit logs | Basic | Full | Full |
| SLA | Best effort | 99.5% | 99.9% |
| Support | Community | Email | Dedicated |
