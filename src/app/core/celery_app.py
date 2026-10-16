# app/core/celery_app.py 
from celery import Celery

from app.core.config import settings

celery_app = Celery("shion_ai", broker=settings.CELERY_BROKER_URL,include=["app.tasks.document_tasks"])
celery_app.conf.task_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.update(
    broker_connection_timeout=3,
    broker_transport_options={"socket_connect_timeout": 3, "socket_timeout": 3},
    task_publish_retry=False,
    worker_prefetch_multiplier=1,
    beat_schedule={"recover-documents": {
        "task": "recover_documents", "schedule": settings.DOCUMENT_RECOVERY_SECONDS,
    }},
)
