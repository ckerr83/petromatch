from celery import Celery
from ..core.config import settings

celery_app = Celery(
    "petromatch",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['app.workers.scrape_worker', 'app.workers.match_worker', 'app.workers.cv_worker']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    beat_schedule={
        # Email notifications temporarily disabled
    },
)