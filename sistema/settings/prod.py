"""Configuración de producción.

Se activa con DJANGO_SETTINGS_MODULE=sistema.settings.prod, que es lo que hace
docker-compose.prod.yml. Nunca uses este módulo con el .env de desarrollo.
"""
from .base import *  # noqa: F401,F403
from .base import BASE_DIR, SECRET_KEY, env  # noqa: F401

DEBUG = False

# Sin valor por defecto a propósito: si falta, la app no arranca.
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# Por defecto, https:// de cada host permitido. Se puede sobrescribir por entorno.
CSRF_TRUSTED_ORIGINS = env(
    "CSRF_TRUSTED_ORIGINS",
    default=[f"https://{host}" for host in ALLOWED_HOSTS if host not in ("*", "")],
)

# Una clave de relleno o demasiado corta no puede llegar a producción.
_MARCADORES = ("insecure-", "cambia", "changeme", "secret-key", "django-insecure")
if len(SECRET_KEY) < 50 or any(m in SECRET_KEY.lower() for m in _MARCADORES):
    raise RuntimeError(
        "SECRET_KEY no es válida para producción (es un marcador de posición o es "
        "demasiado corta). Genera una y ponla en el .env del servidor:\n"
        "  python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    )

# --- HTTPS ------------------------------------------------------------------
# Caddy termina el TLS y habla con Django por HTTP dentro de la red de Docker,
# así que Django reconoce la petición como segura por esta cabecera.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)

SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False  # HTMX lee el token del DOM, no de la cookie.
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
USE_X_FORWARDED_HOST = True

# --- Estáticos --------------------------------------------------------------
# WhiteNoise con manifiesto: nombres con hash y cabeceras de caché largas.
# Exige haber pasado collectstatic; deploy.sh lo hace en cada despliegue.
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
}
WHITENOISE_MAX_AGE = 60 * 60 * 24 * 365

# --- Base de datos ----------------------------------------------------------
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)  # noqa: F405
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405

# --- Logs -------------------------------------------------------------------
# Nada de DEBUG en las librerías HTTP: el modo depuración del SDK de Anthropic
# y de httpx escribe cabeceras, y ahí viaja la clave de la API.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "anthropic": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "httpx": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "httpcore": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

# Django ya oculta en los informes de error cualquier ajuste cuyo nombre contenga
# API, KEY, SECRET, TOKEN, PASS o SIGNATURE. ANTHROPIC_API_KEY encaja, así que no
# aparece en los trazados. Aun así: nunca pongas ANTHROPIC_LOG=debug en el VPS.
