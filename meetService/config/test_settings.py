from __future__ import annotations

import os

os.environ["DJANGO_DEBUG"] = "False"
os.environ["DJANGO_SILK_ENABLED"] = "False"
os.environ["SENTRY_DSN"] = ""

from .settings import *

DEBUG = False
SILK_ENABLED = False

INSTALLED_APPS += [
    "debug_toolbar",
    "silk",
]

MIDDLEWARE = [
    "silk.middleware.SilkyMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    *MIDDLEWARE,
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
EMAIL_NOTIFICATIONS_ENABLED = True
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
CELERY_TASK_ALWAYS_EAGER = True
STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
