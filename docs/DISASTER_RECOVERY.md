# Gorgon Disaster Recovery Runbook

> **Purpose**: Step-by-step procedures for recovering Gorgon services after failures.
> Keep this document bookmarked. It is designed to be followed under pressure.

---

## 1. Overview

This runbook covers recovery procedures for the Gorgon multi-agent orchestration platform, including the FastAPI backend, Streamlit dashboard, PostgreSQL database, Redis cache, and external integrations (OpenAI, Anthropic, GitHub, Notion, Gmail).

### Recovery Targets

| Metric | Target | Notes |
|--------|--------|-------|
| **RTO** (Recovery Time Objective) | 1 hour | Time to restore service |
| **RPO** (Recovery Point Objective) | 24 hours | Maximum acceptable data loss |
| **Backup frequency** | Daily (automated) + pre-deployment (manual) | See Section 2 |

### Deployment Tiers

Recovery steps vary by deployment model. Know which one you are running:

| Tier | Infrastructure | Database |
|------|---------------|----------|
| Small team | Docker Compose (single instance) | SQLite |
| Medium team | Docker Compose (multi-service) | PostgreSQL + Redis |
| Enterprise | Kubernetes (HA) | PostgreSQL + Redis |

---

## 2. Backup Procedures

All database backups use `deploy/backup.sh`. This script handles PostgreSQL backup, restore, listing, and verification.

### Automated Daily Backups

Add to crontab on the host or a dedicated backup node:

```bash
# Daily at 02:00 UTC
0 2 * * * DATABASE_URL="postgresql://user:pass@host:5432/gorgon" /path/to/Gorgon/deploy/backup.sh backup
```

Backups are stored in `BACKUP_DIR` (default: `/var/backups/gorgon`). Retention is controlled by `BACKUP_RETAIN` (default: 30 days).

### Pre-Deployment Manual Backup

Run before every production deployment:

```bash
./deploy/backup.sh backup
```

### Verifying Backups

```bash
# List available backups
./deploy/backup.sh list

# Verify a specific backup is readable
./deploy/backup.sh verify gorgon_backup_YYYYMMDD_HHMMSS.dump
```

### Off-Site Backup (Recommended)

Copy backups to a separate location (S3, GCS, or another host) after each run:

```bash
aws s3 cp /var/backups/gorgon/gorgon_backup_*.dump s3://your-bucket/gorgon-backups/
```

---

## 3. Failure Scenarios & Recovery Procedures

### 3.1 Application Crash / Container Restart

**Symptoms**: Dashboard unreachable, API returns 502/503, container in restart loop.

**Diagnosis**:

```bash
# Docker Compose
docker ps | grep gorgon
docker logs gorgon --tail=200

# Kubernetes
kubectl get pods -n gorgon
kubectl logs -l app=gorgon -n gorgon --tail=200
kubectl describe pod -l app=gorgon -n gorgon
```

**Recovery**:

```bash
# Docker Compose - restart the service
docker compose -f deploy/templates/medium-team/docker-compose.yml restart gorgon

# If restart loop, check for bad config:
docker compose -f deploy/templates/medium-team/docker-compose.yml config
docker exec gorgon env | grep -E 'API_KEY|DATABASE_URL|REDIS_URL'

# Kubernetes - pods should auto-restart; if stuck:
kubectl rollout restart deployment gorgon -n gorgon
kubectl rollout status deployment gorgon -n gorgon
```

**If the crash is caused by a bad deployment**, see Section 3.5 (Failed Deployment Rollback).

---

### 3.2 Database Corruption / Loss

**Symptoms**: Application errors referencing database, 500 errors on all endpoints, `pg_isready` fails.

**Diagnosis**:

```bash
# Check PostgreSQL is running
docker exec gorgon-postgres pg_isready

# Kubernetes
kubectl get pods -l app=postgres -n gorgon
kubectl logs -l app=postgres -n gorgon --tail=100
```

**Recovery**:

1. **Stop the application** to prevent further writes:

   ```bash
   # Docker
   docker compose stop gorgon

   # Kubernetes
   kubectl scale deployment gorgon --replicas=0 -n gorgon
   ```

2. **If PostgreSQL is down**, restart it:

   ```bash
   docker compose restart postgres
   ```

3. **If data is corrupt or lost**, restore from backup:

   ```bash
   # List available backups
   ./deploy/backup.sh list

   # Restore the most recent verified backup
   ./deploy/backup.sh restore gorgon_backup_YYYYMMDD_HHMMSS.dump --yes
   ```

4. **Restart the application**:

   ```bash
   # Docker
   docker compose start gorgon

   # Kubernetes
   kubectl scale deployment gorgon --replicas=3 -n gorgon
   ```

5. **Verify** (see Section 4).

---

### 3.3 Full Infrastructure Failure

**Symptoms**: All services unreachable. Host or cluster is down.

**Recovery**:

1. **Provision new infrastructure** using the appropriate deployment template:

   ```bash
   # Medium team
   cd deploy/templates/medium-team
   cp .env.example .env
   # Fill in .env with production values from your secrets manager

   # Enterprise (new cluster)
   kubectl apply -k deploy/templates/enterprise/
   ```

2. **Restore secrets**:

   ```bash
   # Kubernetes
   kubectl create secret generic gorgon-secrets \
     --from-literal=ANTHROPIC_API_KEY=sk-ant-xxx \
     --from-literal=OPENAI_API_KEY=sk-xxx \
     --from-literal=DATABASE_URL=postgresql://... \
     --from-literal=REDIS_URL=redis://... \
     -n gorgon
   ```

3. **Restore database** from off-site backup:

   ```bash
   # Copy backup from off-site storage
   aws s3 cp s3://your-bucket/gorgon-backups/gorgon_backup_YYYYMMDD_HHMMSS.dump /var/backups/gorgon/

   # Restore
   ./deploy/backup.sh restore /var/backups/gorgon/gorgon_backup_YYYYMMDD_HHMMSS.dump --yes
   ```

4. **Start all services**:

   ```bash
   docker compose up -d
   ```

5. **Update DNS** if the new infrastructure has different IP addresses.

6. **Verify** (see Section 4).

---

### 3.4 Compromised API Keys

**Symptoms**: Unexpected API usage, billing alerts, unauthorized access in audit logs.

**Immediate actions (do all of these, in order)**:

1. **Rotate all compromised keys immediately** at the provider:
   - Anthropic: https://console.anthropic.com/
   - OpenAI: https://platform.openai.com/api-keys
   - GitHub: https://github.com/settings/tokens
   - Notion: https://www.notion.so/my-integrations

2. **Update secrets in the running environment**:

   ```bash
   # Docker - update .env file, then:
   docker compose down && docker compose up -d

   # Kubernetes
   kubectl delete secret gorgon-secrets -n gorgon
   kubectl create secret generic gorgon-secrets \
     --from-literal=ANTHROPIC_API_KEY=<NEW_KEY> \
     --from-literal=OPENAI_API_KEY=<NEW_KEY> \
     --from-literal=GITHUB_TOKEN=<NEW_KEY> \
     --from-literal=NOTION_TOKEN=<NEW_KEY> \
     -n gorgon
   kubectl rollout restart deployment gorgon -n gorgon
   ```

3. **Audit the damage**:
   - Review API provider usage dashboards for unauthorized calls.
   - Check GitHub for unauthorized commits or repository access.
   - Review application logs for unusual activity.

4. **Investigate the root cause**: How were the keys exposed? Check for keys in git history, logs, error messages, or third-party services.

5. **Update secrets in your secrets manager** and CI/CD pipelines.

---

### 3.5 Failed Deployment Rollback

**Symptoms**: New deployment causes errors, crashes, or degraded performance.

**Recovery**:

```bash
# Docker Compose - revert to previous image tag
docker compose down
git checkout <last-known-good-commit>
docker compose up -d --build

# Kubernetes - automatic rollback
kubectl rollout undo deployment gorgon -n gorgon

# Kubernetes - rollback to a specific revision
kubectl rollout history deployment gorgon -n gorgon
kubectl rollout undo deployment gorgon --to-revision=<N> -n gorgon

# Verify rollback
kubectl rollout status deployment gorgon -n gorgon
```

If the failed deployment included database migrations, you may also need to restore from the pre-deployment backup (see Section 3.2).

---

## 4. Verification Checklist

After any recovery, confirm all of the following before declaring the incident resolved:

```
[ ] Application container(s) running and stable (no restart loops)
[ ] Health endpoint responds:       curl http://localhost:8501/healthz
[ ] API endpoint responds:          curl http://localhost:8000/docs
[ ] Dashboard loads in browser:     http://localhost:8501
[ ] Database connection works:      docker exec gorgon-postgres pg_isready
[ ] Recent data is present (check workflows, job history)
[ ] Redis connection works (if applicable)
[ ] Prometheus scraping metrics (if applicable): http://localhost:9090/targets
[ ] Grafana dashboards loading (if applicable): http://localhost:3000
[ ] Run smoke test:                 pytest tests/ -x -q --timeout=30
[ ] External integrations functional (GitHub, Notion - test one operation)
```

---

## 5. Contacts & Escalation

Fill in with your team's contacts. Keep this updated.

| Role | Name | Phone | Email | Escalate After |
|------|------|-------|-------|----------------|
| On-call engineer | ___________ | ___________ | ___________ | First responder |
| Backend lead | ___________ | ___________ | ___________ | 15 min |
| Infrastructure lead | ___________ | ___________ | ___________ | 30 min |
| Engineering manager | ___________ | ___________ | ___________ | 1 hour |
| VP Engineering | ___________ | ___________ | ___________ | 2 hours |

### External Contacts

| Service | Support URL | Account ID |
|---------|-----------|------------|
| Anthropic | https://support.anthropic.com | ___________ |
| OpenAI | https://help.openai.com | ___________ |
| Cloud provider | ___________ | ___________ |

---

## 6. Regular Testing

Disaster recovery procedures must be tested regularly to remain trustworthy.

| Drill | Frequency | Scope |
|-------|-----------|-------|
| Backup restore test | Monthly | Restore latest backup to a staging database, verify data integrity |
| Application failover | Quarterly | Kill application containers, confirm auto-restart and recovery |
| Full DR simulation | Twice yearly | Rebuild from scratch using off-site backups on fresh infrastructure |
| Key rotation drill | Quarterly | Rotate all API keys and secrets, confirm services recover |

### After Each Drill

1. Document what happened and how long recovery took.
2. Compare against RTO/RPO targets.
3. Update this runbook with any corrections or improvements.
4. File issues for any gaps discovered.

---

## Appendix: Quick Reference Commands

```bash
# Backup
./deploy/backup.sh backup

# List backups
./deploy/backup.sh list

# Verify backup
./deploy/backup.sh verify <file>

# Restore backup
./deploy/backup.sh restore <file> --yes

# Restart (Docker)
docker compose -f deploy/templates/medium-team/docker-compose.yml restart

# Restart (Kubernetes)
kubectl rollout restart deployment gorgon -n gorgon

# Rollback (Kubernetes)
kubectl rollout undo deployment gorgon -n gorgon

# Check logs (Docker)
docker logs gorgon --tail=200

# Check logs (Kubernetes)
kubectl logs -l app=gorgon -n gorgon --tail=200
```
