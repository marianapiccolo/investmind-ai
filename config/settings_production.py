"""Production settings, with an explicit mode for testing locally over HTTP."""

import os

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F403
from .settings import (
    BASE_DIR,
    SECRET_KEY,
    env_bool,
    env_list,
)
from .settings import MIDDLEWARE as base_middleware


DEBUG = False

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")

if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "Set explicit DJANGO_ALLOWED_HOSTS values for production."
    )

if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured(
        "Production requires a new random DJANGO_SECRET_KEY of at least 50 characters."
    )

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

MIDDLEWARE = list(base_middleware)
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "3600"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Enable only behind a trusted proxy that controls this header.
SECURE_PROXY_SSL_HEADER = None
if env_bool("DJANGO_TRUST_PROXY_HEADERS", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# This mode is restricted to loopback hosts for testing before HTTPS is set up.
LOCAL_PRODUCTION_TEST = env_bool("DJANGO_LOCAL_PRODUCTION_TEST", False)

if LOCAL_PRODUCTION_TEST:
    loopback_hosts = {"127.0.0.1", "localhost", "[::1]"}
    if not set(ALLOWED_HOSTS).issubset(loopback_hosts):
        raise ImproperlyConfigured(
            "Local production testing is restricted to loopback hosts."
        )

    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
    SECURE_PROXY_SSL_HEADER = None
