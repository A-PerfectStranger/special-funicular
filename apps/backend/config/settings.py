import os
from typing import Any

from django.core.exceptions import ImproperlyConfigured

APP_ENV = os.environ.get("APP_ENV", "local")
if APP_ENV not in {"local", "test", "staging", "production"}:
    raise ImproperlyConfigured("APP_ENV invalido")
IS_LOCAL = APP_ENV in {"local", "test"}
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "synthetic-local-only-key-never-use-outside-local")
if not IS_LOCAL and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith("synthetic-")):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY seguro requerido")
DEBUG = False
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
if not IS_LOCAL and ("*" in ALLOWED_HOSTS or not os.environ.get("DJANGO_ALLOWED_HOSTS")):
    raise ImproperlyConfigured("Configurar hosts explicitos")
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
INSTALLED_APPS = ["django.contrib.sessions", "core"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.NoStoreMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    }
]
DATABASES: dict[str, Any] = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "NAME": os.environ.get("DB_NAME", "retiro_synthetic"),
        "USER": os.environ.get("DB_USER", "app_runtime"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "synthetic-runtime" if IS_LOCAL else ""),
        "CONN_MAX_AGE": 0,
        "OPTIONS": {
            "connect_timeout": 3,
            "sslmode": os.environ.get("DB_SSLMODE", "disable" if IS_LOCAL else "verify-full"),
        },
        "TEST": {"NAME": "test_retiro_synthetic"},
    }
}
if not IS_LOCAL:
    required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DJANGO_ALLOWED_HOSTS")
    if any(not os.environ.get(key) for key in required):
        raise ImproperlyConfigured("Falta configuracion de servicio")
    if DATABASES["default"]["OPTIONS"]["sslmode"] != "verify-full":
        raise ImproperlyConfigured("PostgreSQL requiere verify-full")
LANGUAGE_CODE = "es"
TIME_ZONE = "UTC"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not IS_LOCAL
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 900
CSRF_COOKIE_SECURE = not IS_LOCAL
SECURE_SSL_REDIRECT = not IS_LOCAL
SECURE_HSTS_SECONDS = 31536000 if not IS_LOCAL else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not IS_LOCAL
SECURE_HSTS_PRELOAD = not IS_LOCAL
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
# No confiar en X-Forwarded-Proto hasta configurar un proxy confiable.
RELEASE_SHA = os.environ.get("RELEASE_SHA", "local")
# E0 nunca implementa ni habilita el flujo de retiro.
PICKUP_ENABLED = False
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    # No registrar cuerpos, query strings ni excepciones con configuracion sensible.
    "loggers": {"django.request": {"handlers": ["null"], "propagate": False}},
}
