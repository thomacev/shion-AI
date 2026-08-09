# app/core/celery_app.py 
from celery import Celery
from app.core.config import settings

celery_app = Celery("shion_ai", broker=settings.CELERY_BROKER_URL,include=["app.tasks.document_tasks"])
celery_app.conf.task_serializer = "json"
celery_app.conf.accept_content = ["json"]