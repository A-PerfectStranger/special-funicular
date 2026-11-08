"""Environment configuration; E1/E2 are gated independently and pickups remain disabled."""

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
INSTALLED_APPS = [
    "core",
    "django.contrib.sessions",
    "identity",
    "school_roster",
    "evidence",
    "authorization",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.SafeResponsesMiddleware",
    "core.middleware.LivenessMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
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
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
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
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 12 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
DATA_UPLOAD_MAX_MEMORY_SIZE = 450000
E1_IDENTITY_ENABLED = os.environ.get("E1_IDENTITY_ENABLED", "false") == "true"
E1_OIDC = {
    key: os.environ.get(variable, "")
    for key, variable in {
        "issuer": "OIDC_ISSUER",
        "web_client": "OIDC_WEB_CLIENT_ID",
        "mobile_client": "OIDC_MOBILE_CLIENT_ID",
        "web_redirect": "OIDC_WEB_REDIRECT_URI",
        "mobile_redirect": "OIDC_MOBILE_REDIRECT_URI",
        "mfa_policy": "OIDC_MFA_POLICY",
        "pool_id": "OIDC_COGNITO_POOL_ID",
        "region": "AWS_REGION",
    }.items()
}
if E1_IDENTITY_ENABLED and (
    not all(E1_OIDC.values())
    or not (os.environ.get("SYSTEM_READ_DATABASE_URL") or os.environ.get("SYSTEM_READ_PASSWORD"))
):
    raise ImproperlyConfigured("E1 requires configured OIDC and an isolated system reader")
if E1_IDENTITY_ENABLED and APP_ENV == "production":
    raise ImproperlyConfigured("E1 production commissioning is not configured")
# Only set for the ECS ALB boundary: task ingress must be restricted to its managed SG.
TRUSTED_INGRESS = os.environ.get("TRUSTED_INGRESS", "")
if TRUSTED_INGRESS not in {"", "ecs-express"}:
    raise ImproperlyConfigured("Unknown ingress boundary")
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https") if TRUSTED_INGRESS == "ecs-express" else None
)
# ALB liveness arrives over the private target-group connection, without XFP.
SECURE_REDIRECT_EXEMPT = [r"^health/live$"]
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "loggers": {"django.request": {"handlers": ["null"], "propagate": False}},
}

E2_FAMILY_ENABLED = os.environ.get("E2_FAMILY_ENABLED", "false") == "true"
if E2_FAMILY_ENABLED and not E1_IDENTITY_ENABLED:
    raise ImproperlyConfigured("E2 requires E1 identity")
