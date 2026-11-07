"""E0: technical availability only. No identity or pickup routes are enabled."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
APP_ENV = os.environ.get("APP_ENV", "development")
if APP_ENV not in {"development", "test", "staging", "production"}:
    raise ImproperlyConfigured("Invalid APP_ENV")
DEBUG = os.environ.get("DJANGO_DEBUG", "false") == "true"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must contain at least 50 characters")
if APP_ENV in {"staging", "production"} and (DEBUG or SECRET_KEY.startswith("synthetic")):
    raise ImproperlyConfigured("Cloud requires DEBUG=false and a managed secret")
ALLOWED_HOSTS = [x for x in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if x]
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Explicit DJANGO_ALLOWED_HOSTS required")
INSTALLED_APPS = ["core"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.SafeResponsesMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.environ.get("PGHOST", "127.0.0.1"),
        "PORT": os.environ.get("PGPORT", "5432"),
        "NAME": os.environ.get("PGDATABASE", "retiro"),
        "USER": os.environ.get("PGUSER", "retiro_runtime"),
        "PASSWORD": os.environ.get("PGPASSWORD", ""),
        "CONN_MAX_AGE": 0,
        "OPTIONS": {"connect_timeout": 3, "sslmode": os.environ.get("PGSSLMODE", "prefer")},
    }
}
if APP_ENV in {"staging", "production"} and os.environ.get("PGSSLMODE") != "verify-full":
    raise ImproperlyConfigured("Cloud PostgreSQL requires PGSSLMODE=verify-full")
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = APP_ENV in {"staging", "production"}
SECURE_HSTS_SECONDS = 31536000 if SECURE_SSL_REDIRECT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_SSL_REDIRECT
SECURE_HSTS_PRELOAD = SECURE_SSL_REDIRECT
X_FRAME_OPTIONS = "DENY"
# Deliberately no proxy trust header: configure only at a verified ingress boundary.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "loggers": {"django.request": {"handlers": ["null"], "propagate": False}},
}
