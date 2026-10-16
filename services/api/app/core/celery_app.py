from celery import Celery
from celery.signals import beat_init, worker_process_init
from kombu import Queue

from app.core.config import settings

celery_app = Celery(
    "leadsgen",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.search_jobs",
        "app.workers.enrichment_jobs",
        "app.workers.campaign_jobs",
        "app.workers.reply_jobs",
        "app.workers.platform_email_jobs",
        "app.workers.inbound_jobs",
        "app.workers.ops_jobs",
        "app.workers.privacy_jobs",
        "app.workers.outbound_webhook_jobs",
        "app.workers.billing_jobs",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Reliability: a task is only acknowledged after it finishes, and is re-queued if the
    # worker dies mid-task. Every task must therefore be idempotent.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=300,
    task_soft_time_limit=240,
    broker_connection_retry_on_startup=True,
    result_expires=86_400,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=settings.celery_task_always_eager,
    task_default_queue="default",
    task_queues=(
        Queue("default"),
        Queue("sending"),
        Queue("inbound"),
        Queue("enrichment"),
    ),
    task_routes={
        "campaign.*": {"queue": "sending"},
        "sending.*": {"queue": "sending"},
        "enrichment.*": {"queue": "enrichment"},
        "inbound.*": {"queue": "inbound"},
        "webhooks.*": {"queue": "inbound"},
        "replies.*": {"queue": "inbound"},
        "inbox.*": {"queue": "inbound"},
    },
    beat_schedule={
        "dispatch-sends": {
            "task": "sending.dispatch",
            "schedule": 60.0,
        },
        "reap-stuck-sends": {
            "task": "sending.reap",
            "schedule": 300.0,
        },
        "advance-sequences": {
            "task": "sequences.advance",
            "schedule": 300.0,
        },
        "poll-inboxes": {
            "task": "inbox.poll",
            "schedule": 300.0,
        },
        "retry-webhooks": {
            "task": "webhooks.retry_failed",
            "schedule": 600.0,
        },
        "worker-heartbeat": {
            "task": "ops.heartbeat",
            "schedule": 60.0,
        },
        "purge-audit-logs": {
            "task": "ops.purge_audit_logs",
            "schedule": 86400.0,
        },
        "apply-retention": {
            "task": "privacy.apply_retention",
            "schedule": 86400.0,
        },
        "retry-outbound-webhooks": {
            "task": "outbound_webhooks.retry_due",
            "schedule": 60.0,
        },
        "billing-daily": {
            "task": "billing.daily",
            "schedule": 3600.0,
        },
    },
)


@worker_process_init.connect
def _init_worker_observability(**_kwargs: object) -> None:
    """Error reporting and tracing inside each worker process (beat included)."""
    from app.core.observability import init_sentry
    from app.core.tracing import init_tracing

    init_sentry("worker")
    init_tracing("worker")


@beat_init.connect
def _init_beat_observability(**_kwargs: object) -> None:
    from app.core.observability import init_sentry

    init_sentry("beat")
