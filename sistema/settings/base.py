"""Configuracion comun a todos los entornos."""
import mimetypes
from pathlib import Path

import environ

# Algunos sistemas no traen WebP en su tabla de tipos y las imagenes se acaban
# sirviendo como application/octet-stream. Se registra explicitamente.
mimetypes.add_type("image/webp", ".webp", True)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    TIME_ZONE=(str, "Europe/Madrid"),
    ANTHROPIC_API_KEY=(str, ""),
    ANTHROPIC_MODEL=(str, "claude-sonnet-5"),
)

environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="insecure-dev-key-cambiala")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "django_htmx",
]

# Una app por dominio del sistema.
LOCAL_APPS = [
    "core",
    "missions",
    "progression",
    "business",
    "review",
    "wisdom",
    "notebook",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Un solo usuario: toda la instancia queda detras del login salvo /entrar/.
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "sistema.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.navegacion",
            ],
        },
    },
]

WSGI_APPLICATION = "sistema.wsgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://sistema:sistema@db:5432/sistema",
    ),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-es"
TIME_ZONE = env("TIME_ZONE")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/entrar/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/entrar/"

# SDK de Anthropic (revision asistida, redaccion comercial, calibracion).
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL")

# App de Android (APK con Bubblewrap). La huella SHA-256 del certificado con el
# que se firma el APK va en assetlinks.json: sin ella la app se abre con la
# barra de direccion de Chrome arriba. Vacia, el fichero sale vacio.
ANDROID_PACKAGE = env("ANDROID_PACKAGE", default="com.jaumeleveling.app")
ANDROID_SHA256 = env.list("ANDROID_SHA256", default=[])
