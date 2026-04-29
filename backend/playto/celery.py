import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "playto.settings")

app = Celery("playto")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "pickup-pending-payouts": {
        "task": "payouts.tasks.pickup_pending_payouts",
        "schedule": 5.0,
    },
    "retry-stuck-payouts": {
        "task": "payouts.tasks.check_and_retry_stuck_payouts",
        "schedule": 10.0,
    },
}
