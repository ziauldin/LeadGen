from celery import Celery

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
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    beat_schedule={
        "process-campaign-sends": {
            "task": "campaign.process_sends",
            "schedule": 300.0,
        },
        "sync-replies": {
            "task": "replies.sync",
            "schedule": 900.0,
        },
    },
)
