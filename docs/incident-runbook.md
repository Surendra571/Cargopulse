# Incident Runbook

## 1. Readiness Probe Failing (`HTTP 503` on `/api/v1/healthz/ready`)

**Symptoms**: Load balancer marks backend unhealthy; `/api/v1/healthz/ready` returns `database: false` or `redis: false`.

**Triage**:
1. Inspect structured JSON logs:
   ```bash
   docker logs cargopulse_prod_backend --tail 100
   ```
2. Verify PostgreSQL connectivity & pool saturation:
   - Check `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` vs. managed Postgres `max_connections`.
   - Verify SSL parameters (`ssl=require`) in `DATABASE_URL`.
3. Verify Redis connectivity:
   - Confirm Redis instance health and TLS URI (`rediss://`) in `REDIS_URL`.

## 2. High Dead-Letter Queue (DLQ) Volume / Webhook Failures

**Symptoms**: Carrier webhooks failing delivery; items accumulating in `/integrations/dlq`.

**Triage**:
1. Check `cargopulse_prod_worker` logs for target carrier endpoint timeouts or 4xx/5xx responses.
2. Open **Integrations -> Dead-Letter Queue** in the UI or call `GET /api/v1/integrations/dlq`.
3. Replay individual or batch failed deliveries after confirming carrier endpoint recovery.

## 3. Celery Worker / Beat Stall

**Symptoms**: Scheduled tasks or async notifications stop processing.

**Triage**:
1. Ping workers:
   ```bash
   docker exec cargopulse_prod_worker celery -A app.core.celery_app.celery_app inspect ping
   ```
2. Check active/reserved queues:
   ```bash
   docker exec cargopulse_prod_worker celery -A app.core.celery_app.celery_app inspect active
   ```
3. Restart worker or beat container cleanly (`SIGTERM` allows `task_acks_late=True` to requeue unacked tasks):
   ```bash
   docker compose -f docker-compose.prod.yml restart celery_worker celery_beat
   ```

## 4. Database Corruption or Accidental Data Loss

**Action**: Immediately halt mutating workers (`celery_worker`, `celery_beat`), verify latest verified backup in `S3_BACKUP_BUCKET` or `./backups`, and execute `./scripts/restore-db.sh <backup.dump>` followed by `alembic current` and `/api/v1/healthz/ready`.
