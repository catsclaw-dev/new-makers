from pathlib import Path

import environ

from django.utils.translation import gettext_lazy as _

from config.telemetry import build_sentry_config, initialize_sentry

BASE_DIR = Path(__file__).resolve().parent.parent


env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    DJANGO_SECURE_SSL_REDIRECT=(bool, False),
    DJANGO_SESSION_COOKIE_SECURE=(bool, False),
    DJANGO_CSRF_COOKIE_SECURE=(bool, False),
    DJANGO_SECURE_HSTS_SECONDS=(int, 0),
    DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=(bool, False),
    DJANGO_SECURE_HSTS_PRELOAD=(bool, False),
    DJANGO_SILK_ENABLED=(bool, True),
    DJANGO_SILK_AUTHENTICATION=(bool, True),
    DJANGO_SILK_AUTHORISATION=(bool, True),
    DJANGO_SILK_PYTHON_PROFILER=(bool, False),
    EMAIL_PORT=(int, 587),
    EMAIL_USE_TLS=(bool, True),
    SENTRY_PROFILES_SAMPLE_RATE=(float, 0.0),
    SENTRY_SEND_DEFAULT_PII=(bool, False),
    SENTRY_TRACES_SAMPLE_RATE=(float, 0.0),
)

environ.Env.read_env(BASE_DIR / ".env")

# old key in commits not actual :3
SECRET_KEY = env("DJANGO_SECRET_KEY")

DEBUG = env("DJANGO_DEBUG")

ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=["127.0.0.1", "localhost"],
)

CSRF_TRUSTED_ORIGINS = env.list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=[],
)


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "import_export",
    "simple_history",
    "apps.api.apps.ApiConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.directories.apps.DirectoriesConfig",
    "apps.specialists.apps.SpecialistsConfig",
    "apps.projects.apps.ProjectsConfig",
    "apps.interactions.apps.InteractionsConfig",
    "apps.reviews.apps.ReviewsConfig",
]

if DEBUG:
    INSTALLED_APPS += [
        "debug_toolbar",
    ]

    INTERNAL_IPS = [
        "127.0.0.1",
        "::1",
    ]

SILK_ENABLED = DEBUG and env.bool("DJANGO_SILK_ENABLED", default=True)

if SILK_ENABLED:
    INSTALLED_APPS += [
        "silk",
    ]
    SILKY_AUTHENTICATION = env.bool("DJANGO_SILK_AUTHENTICATION", default=True)
    SILKY_AUTHORISATION = env.bool("DJANGO_SILK_AUTHORISATION", default=True)
    SILKY_PYTHON_PROFILER = env.bool("DJANGO_SILK_PYTHON_PROFILER", default=False)

    SILKY_MAX_REQUEST_BODY_SIZE = 1024
    SILKY_MAX_RESPONSE_BODY_SIZE = 1024

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if DEBUG:
    MIDDLEWARE.insert(1, "debug_toolbar.middleware.DebugToolbarMiddleware")

if SILK_ENABLED:
    MIDDLEWARE.insert(0, "silk.middleware.SilkyMiddleware")

ROOT_URLCONF = "config.urls"


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.interactions.context_processors.notification_counts",
            ],
        },
    },
]


WSGI_APPLICATION = "config.wsgi.application"


DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "ru"

TIME_ZONE = "Europe/Moscow"

USE_I18N = True

USE_TZ = True

LANGUAGES = [
    ("ru", _("Русский")),
    ("en", _("English")),
]

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

AUTH_USER_MODEL = "accounts.User"


MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"


STATIC_URL = "static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATIC_ROOT = BASE_DIR / "staticfiles"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}


LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:profile"
LOGOUT_REDIRECT_URL = "projects:home"


EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    default="MeetService <noreply@meetservice.local>",
)


SECURE_SSL_REDIRECT = env.bool(
    "DJANGO_SECURE_SSL_REDIRECT",
    default=False,
)
SESSION_COOKIE_SECURE = env.bool(
    "DJANGO_SESSION_COOKIE_SECURE",
    default=False,
)
CSRF_COOKIE_SECURE = env.bool(
    "DJANGO_CSRF_COOKIE_SECURE",
    default=False,
)

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = env.bool(
    "DJANGO_CSRF_COOKIE_HTTPONLY",
    default=False,
)

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

SECURE_HSTS_SECONDS = env.int(
    "DJANGO_SECURE_HSTS_SECONDS",
    default=0,
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=False,
)
SECURE_HSTS_PRELOAD = env.bool(
    "DJANGO_SECURE_HSTS_PRELOAD",
    default=False,
)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "meetservice-cache",
    }
}

CACHE_TIMEOUT = 60 * 5


SENTRY_CONFIG = build_sentry_config(
    dsn=env("SENTRY_DSN", default=""),
    environment=env("SENTRY_ENVIRONMENT", default="development"),
    traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
    profiles_sample_rate=env.float("SENTRY_PROFILES_SAMPLE_RATE", default=0.0),
    send_default_pii=env.bool("SENTRY_SEND_DEFAULT_PII", default=False),
    release=env("SENTRY_RELEASE", default=""),
)
SENTRY_ENABLED = initialize_sentry(SENTRY_CONFIG)
