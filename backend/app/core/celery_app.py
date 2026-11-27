import logging
from celery import Celery
from kombu import Exchange, Queue
from app.core.config import settings

logger = logging.getLogger("cargopulse.celery")

# Initialize Celery app
celery_app = Celery(
    "cargopulse",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Exchanges & Dead-Letter Configuration
default_exchange = Exchange("default", type="direct")
dlx_exchange = Exchange("dlx", type="direct")

celery_app.conf.update(
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,        # 5 minutes hard limit
    task_soft_time_limit=240,   # 4 minutes soft limit
    # Queue Architecture & Routing
    task_queues=(
        Queue("default", default_exchange, routing_key="default"),
        Queue("telemetry", default_exchange, routing_key="telemetry"),
        Queue("notifications", default_exchange, routing_key="notifications"),
        Queue("reconciliation", default_exchange, routing_key="reconciliation"),
        Queue("dead_letter", dlx_exchange, routing_key="dead_letter"),
    ),
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
    # Dead-Letter routing upon max retry exhaustion
    task_reject_on_worker_lost=True,
    task_acks_late=True,
    # Scheduled background tasks (Celery Beat)
    beat_schedule={
        "worker-health-heartbeat-5m": {
            "task": "healthcheck.ping",
            "schedule": 300.0,
            "options": {"queue": "default"},
        },
    },
)


@celery_app.task(bind=True, name="healthcheck.ping")
def ping_task(self):
    """
    Diagnostic Celery worker verification task.
    """
    return {"status": "pong", "worker_id": self.request.id}
