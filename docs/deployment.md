# Production Deployment Guide

## Prerequisites

- Docker & Docker Compose v2 (or container orchestrator such as ECS / Kubernetes / Cloud Run)
- Managed **PostgreSQL 16+** with SSL enabled (`ssl=require`)
- Managed **Redis 7+** with TLS (`rediss://`)
- **S3-compatible Object Storage** bucket for e-POD documents and signatures
- TLS termination (Cloud Load Balancer, Cloudflare, or Certbot/Traefik in front of Nginx)

## 1. Environment Configuration

Copy `.env.production.example` to `.env.production` and populate secrets from your secrets manager (AWS Secrets Manager, GCP Secret Manager, or HashiCorp Vault):

```bash
cp .env.production.example .env.production
openssl rand -hex 32  # Use output for SECRET_KEY
```

Verify that:
- `ENVIRONMENT=production` and `DEBUG=false`
- `COOKIE_SECURE=true`
- `ALLOWED_ORIGINS` lists only your HTTPS domain(s)
- `SECRET_KEY` and `POSTGRES_PASSWORD` do not use any development defaults (the API refuses to start in production if defaults are present)

## 2. Database Migrations

Run Alembic migrations against the managed PostgreSQL instance before routing traffic:

```bash
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

## 3. Launch Production Stack

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Services started:
- `cargopulse_prod_backend` (FastAPI + 4 Uvicorn workers on port `8000`)
- `cargopulse_prod_worker` (Celery worker consuming `default,telemetry,notifications,reconciliation`)
- `cargopulse_prod_beat` (Celery Beat periodic task scheduler)
- `cargopulse_prod_frontend` (Nginx serving static SPA + `/api/` proxy on port `80`)

## 4. Health & Verification

```bash
curl -fsS http://localhost:8000/api/v1/healthz/live
curl -fsS http://localhost:8000/api/v1/healthz/ready
curl -fsS http://localhost/nginx-health
```

## 5. Backups & Restores

- **Automated Backup**: `./scripts/backup-db.sh /var/backups/cargopulse` (supports `S3_BACKUP_BUCKET` for encrypted S3 off-site storage and 14-day retention pruning).
- **Restore Procedure**: `./scripts/restore-db.sh /var/backups/cargopulse/cargopulse_<timestamp>.dump` (validates Alembic schema version after restore).
