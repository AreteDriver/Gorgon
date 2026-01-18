# Gorgon Deployment Templates

Pre-configured deployment templates for different team sizes and infrastructure.

## Quick Start

Choose the template that matches your team size:

| Template | Team Size | Infrastructure | Features |
|----------|-----------|----------------|----------|
| [small-team](./templates/small-team/) | 1-5 devs | Docker Compose | Single instance, SQLite |
| [medium-team](./templates/medium-team/) | 5-20 devs | Docker Compose | PostgreSQL, Redis, Monitoring |
| [enterprise](./templates/enterprise/) | 20+ devs | Kubernetes | HA, Multi-tenant, Full observability |

## Small Team (1-5 developers)

```bash
cd templates/small-team
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY
docker compose up -d
```

Access: http://localhost:8501

## Medium Team (5-20 developers)

```bash
cd templates/medium-team
cp .env.example .env
# Edit .env with all required values
docker compose up -d
```

Services:
- Dashboard: http://localhost:8501
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

## Enterprise (20+ developers)

```bash
cd templates/enterprise

# Create secrets
kubectl create secret generic gorgon-secrets \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-xxx \
  --from-literal=DATABASE_URL=postgresql://... \
  --from-literal=REDIS_URL=redis://... \
  -n gorgon

# Deploy
kubectl apply -k .
```

## Documentation

- [Deployment Guide](../docs/DEPLOYMENT_GUIDE.md) - Step-by-step deployment instructions
- [Enterprise Patterns](../docs/ENTERPRISE_PATTERNS.md) - Multi-tenant and HA patterns

## Directory Structure

```
deploy/
├── README.md                    # This file
└── templates/
    ├── small-team/
    │   ├── docker-compose.yml   # Single instance setup
    │   └── .env.example         # Environment template
    ├── medium-team/
    │   ├── docker-compose.yml   # Multi-service setup
    │   ├── .env.example         # Environment template
    │   ├── init-db.sql          # PostgreSQL schema
    │   └── prometheus.yml       # Monitoring config
    └── enterprise/
        ├── kustomization.yaml   # Kustomize config
        ├── namespace.yaml       # Namespace definition
        ├── deployment.yaml      # Main deployment
        ├── service.yaml         # Service definition
        ├── ingress.yaml         # Ingress rules
        ├── hpa.yaml             # Autoscaling config
        ├── network-policy.yaml  # Network security
        ├── service-account.yaml # RBAC config
        ├── configmap.yaml       # Configuration
        └── secrets.yaml         # Secrets template
```
