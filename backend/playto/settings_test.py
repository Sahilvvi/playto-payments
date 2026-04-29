"""
Test settings: SQLite with IMMEDIATE isolation level so that concurrent transactions
acquire write locks at BEGIN time (not at first write). This makes SELECT FOR UPDATE
semantics work correctly across threads — the second thread waits for the first to
commit before it reads, preventing overdraft races.
"""
from .settings import *  # noqa: F401, F403
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test.sqlite3",
        "OPTIONS": {
            "timeout": 30,
            "isolation_level": "IMMEDIATE",
        },
    }
}

# Run Celery tasks inline (no broker needed for tests)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

CORS_ALLOW_ALL_ORIGINS = True
DEBUG = False

# Speed up password hashing in tests
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Silence staticfiles warning
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
