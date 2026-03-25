import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "BilimAI.settings")

app = Celery("BilimAI")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
