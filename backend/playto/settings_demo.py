"""
Demo settings: SQLite + Celery ALWAYS_EAGER (tasks run synchronously inline).
Used when PostgreSQL/Redis are not available — shows full UI working.
DO NOT use in production.
"""
from .settings import *  # noqa: F401, F403
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Switch to SQLite — no external DB needed
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "demo.sqlite3",
    }
}

# Run Celery tasks inline (synchronously) instead of needing a broker.
# Payouts are processed immediately on creation, simulating the worker.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# No Redis needed
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

CORS_ALLOW_ALL_ORIGINS = True
DEBUG = True
