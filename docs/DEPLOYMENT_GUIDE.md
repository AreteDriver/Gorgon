# Gorgon Deployment Guide

This guide covers deploying Gorgon across different environments and infrastructure.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (Docker)](#quick-start-docker)
3. [Production Docker](#production-docker)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Cloud Deployments](#cloud-deployments)
6. [Configuration Reference](#configuration-reference)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required
- Docker 20.10+ and Docker Compose 2.0+
- API keys for AI providers (Anthropic, OpenAI)

### Recommended
- PostgreSQL 14+ (for production)
- Redis 6+ (for caching/queues)
- Kubernetes 1.25+ (for enterprise)

---

## Quick Start (Docker)

Get Gorgon running in under 5 minutes.

```bash
# Clone the repository
git clone https://github.com/AreteDriver/Gorgon.git
cd Gorgon

# Copy configuration template
cp deploy/templates/small-team/.env.example .env

# Edit .env and add your API key
# ANTHROPIC_API_KEY=sk-ant-...

# Start Gorgon
docker compose -f deploy/templates/small-team/docker-compose.yml up -d

# Access the dashboard
open http://localhost:8501
```

### Verify Installation

```bash
# Check container status
docker ps | grep gorgon

# View logs
docker logs gorgon -f

# Test health endpoint
curl http://localhost:8501/healthz
```

---

## Production Docker

For teams needing PostgreSQL, Redis, and monitoring.

### Setup

```bash
cd deploy/templates/medium-team

# Configure environment
cp .env.example .env
# Edit .env with your values:
# - ANTHROPIC_API_KEY
# - POSTGRES_PASSWORD
# - GRAFANA_PASSWORD

# Start all services
docker compose up -d

# Verify all services are running
docker compose ps
```

### Services

| Service | Port | Purpose |
|---------|------|---------|
| Gorgon | 8501 | Main application |
| PostgreSQL | 5432 | Persistent storage |
| Redis | 6379 | Caching & queues |
| Prometheus | 9090 | Metrics collection |
| Grafana | 3000 | Dashboards |

### Accessing Services

```bash
# Dashboard
open http://localhost:8501

# Grafana (admin/your-password)
open http://localhost:3000

# Prometheus
open http://localhost:9090
```

### Backup & Restore

```bash
# Backup PostgreSQL
docker exec gorgon-postgres pg_dump -U gorgon gorgon > backup.sql

# Restore PostgreSQL
docker exec -i gorgon-postgres psql -U gorgon gorgon < backup.sql
```

---

## Kubernetes Deployment

For enterprise deployments with high availability.

### Prerequisites

- Kubernetes cluster (1.25+)
- kubectl configured
- Ingress controller (nginx recommended)
- cert-manager (for TLS)

### Deploy with Kustomize

```bash
cd deploy/templates/enterprise

# Create namespace
kubectl create namespace gorgon

# Create secrets (replace with your values)
kubectl create secret generic gorgon-secrets \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-xxx \
  --from-literal=DATABASE_URL=postgresql://gorgon:pass@postgres:5432/gorgon \
  --from-literal=REDIS_URL=redis://redis:6379 \
  -n gorgon

# Apply manifests
kubectl apply -k .

# Verify deployment
kubectl get pods -n gorgon
kubectl get svc -n gorgon
```

### Configure Ingress

Edit `ingress.yaml` to set your domain:

```yaml
spec:
  rules:
    - host: gorgon.your-domain.com
```

Apply changes:
```bash
kubectl apply -f ingress.yaml
```

### Scaling

```bash
# Manual scaling
kubectl scale deployment gorgon --replicas=5 -n gorgon

# HPA is configured automatically - check status
kubectl get hpa -n gorgon
```

### Monitoring

```bash
# Port-forward Prometheus
kubectl port-forward svc/prometheus 9090:9090 -n monitoring

# Port-forward Grafana
kubectl port-forward svc/grafana 3000:3000 -n monitoring
```

---

## Cloud Deployments

### AWS (EKS)

```bash
# Create EKS cluster
eksctl create cluster \
  --name gorgon-cluster \
  --region us-west-2 \
  --nodegroup-name workers \
  --node-type t3.medium \
  --nodes 3

# Install AWS Load Balancer Controller
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=gorgon-cluster

# Deploy Gorgon
kubectl apply -k deploy/templates/enterprise/

# Create RDS PostgreSQL (recommended)
aws rds create-db-instance \
  --db-instance-identifier gorgon-db \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --master-username gorgon \
  --master-user-password YOUR_PASSWORD \
  --allocated-storage 20
```

### GCP (GKE)

```bash
# Create GKE cluster
gcloud container clusters create gorgon-cluster \
  --zone us-central1-a \
  --num-nodes 3 \
  --machine-type e2-medium

# Get credentials
gcloud container clusters get-credentials gorgon-cluster

# Deploy Gorgon
kubectl apply -k deploy/templates/enterprise/

# Create Cloud SQL PostgreSQL
gcloud sql instances create gorgon-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1
```

### Azure (AKS)

```bash
# Create resource group
az group create --name gorgon-rg --location eastus

# Create AKS cluster
az aks create \
  --resource-group gorgon-rg \
  --name gorgon-cluster \
  --node-count 3 \
  --node-vm-size Standard_B2s \
  --generate-ssh-keys

# Get credentials
az aks get-credentials --resource-group gorgon-rg --name gorgon-cluster

# Deploy Gorgon
kubectl apply -k deploy/templates/enterprise/
```

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | - | Anthropic API key |
| `OPENAI_API_KEY` | No | - | OpenAI API key |
| `GORGON_ENV` | No | development | Environment (development/staging/production) |
| `LOG_LEVEL` | No | INFO | Log level (DEBUG/INFO/WARNING/ERROR) |
| `DATABASE_URL` | No | sqlite | PostgreSQL connection URL |
| `REDIS_URL` | No | - | Redis connection URL |
| `METRICS_ENABLED` | No | true | Enable Prometheus metrics |

### Resource Requirements

| Tier | CPU | Memory | Storage |
|------|-----|--------|---------|
| Small | 1 core | 2 GB | 10 GB |
| Medium | 2-4 cores | 4-8 GB | 50 GB |
| Enterprise | 4+ cores | 8+ GB | 100+ GB |

---

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs gorgon

# Common issues:
# - Missing API key: Add ANTHROPIC_API_KEY to .env
# - Port conflict: Change DASHBOARD_PORT in .env
```

### Database connection failed

```bash
# Verify PostgreSQL is running
docker exec gorgon-postgres pg_isready

# Check connection string
docker exec gorgon env | grep DATABASE_URL
```

### Kubernetes pods not ready

```bash
# Check pod status
kubectl describe pod -l app=gorgon -n gorgon

# Check logs
kubectl logs -l app=gorgon -n gorgon --tail=100

# Common issues:
# - Secret not found: Verify secrets exist
# - Resource limits: Check node capacity
```

### High memory usage

```bash
# Check current usage
docker stats gorgon

# Increase limits in docker-compose.yml:
# deploy:
#   resources:
#     limits:
#       memory: 8G
```

### API rate limiting

If you're hitting rate limits:

1. Implement request queuing with Redis
2. Use exponential backoff
3. Consider higher tier API plans

```python
# Example backoff configuration
RATE_LIMIT_CONFIG = {
    "max_retries": 3,
    "base_delay": 1.0,
    "max_delay": 60.0,
}
```

---

## Next Steps

- Configure [Enterprise Patterns](./ENTERPRISE_PATTERNS.md) for multi-tenant setup
- Set up [monitoring alerts](./ENTERPRISE_PATTERNS.md#monitoring--observability)
- Review [security best practices](./ENTERPRISE_PATTERNS.md#security-patterns)
