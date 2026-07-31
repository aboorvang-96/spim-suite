from pathlib import Path
from decouple import config
import dj_database_url
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# -------------------------------------------------------------------
# SECURITY
# -------------------------------------------------------------------

SECRET_KEY = config(
    'SECRET_KEY',
    default='django-production-secret-key-spim-suite'
)

DEBUG = config('DEBUG', cast=bool, default=False)

ALLOWED_HOSTS = ['*']

# Required when DEBUG=False
CSRF_TRUSTED_ORIGINS = [
    'https://spim-suite-production.up.railway.app',
    'https://spim-lite.vercel.app',
]

# Security settings for production
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# -------------------------------------------------------------------
# INSTALLED APPS
# -------------------------------------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Project Apps
    'accounts',
    'dashboard',
    'finance',
    'projects',
    'clients',
    'invoices',
    'employees',
    'reports',
    'branches',
    'categories',
    'income',
    'transactions',
    'attendance',
    'material_stock',
    'api',

    # Third Party Apps
    'whitenoise.runserver_nostatic',
    'widget_tweaks',
    'corsheaders',
]

# -------------------------------------------------------------------
# MIDDLEWARE
# -------------------------------------------------------------------

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',

    # WhiteNoise
    'whitenoise.middleware.WhiteNoiseMiddleware',

    # CORS
    'corsheaders.middleware.CorsMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# -------------------------------------------------------------------
# CORS
# -------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = [
    'http://localhost:8081',
    'http://127.0.0.1:8081',
    'http://localhost:19006',
    'http://127.0.0.1:19006',
    'https://spim-suite.railway.app',
    'https://spim-lite.vercel.app',
]

CORS_ALLOW_CREDENTIALS = False

CORS_URLS_REGEX = r'^/api/.*$'

# -------------------------------------------------------------------
# URLS & AUTH
# -------------------------------------------------------------------

ROOT_URLCONF = 'config.urls'

WSGI_APPLICATION = 'config.wsgi.application'

AUTH_USER_MODEL = 'accounts.User'

LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/auth/login/'

# -------------------------------------------------------------------
# TEMPLATES
# -------------------------------------------------------------------

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# -------------------------------------------------------------------
# DATABASE — uses os.environ directly so Railway vars are always read
# -------------------------------------------------------------------

DATABASES = {
    'default': dj_database_url.parse(
        os.environ['DATABASE_URL'],
        conn_max_age=600,
        ssl_require=True,
    )
}

# -------------------------------------------------------------------
# INTERNATIONALIZATION
# -------------------------------------------------------------------

LANGUAGE_CODE = 'en-in'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True
USE_TZ = True

# -------------------------------------------------------------------
# CURRENCY SETTINGS
# -------------------------------------------------------------------

CURRENCY_SYMBOL = '₹'
CURRENCY_CODE = 'INR'

# -------------------------------------------------------------------
# SPIM LITE APP VERSION GATE
# -------------------------------------------------------------------
# Single source of truth for the SPIM Lite (mobile APK) version policy.
# Bumping either value here is the ONLY change needed to shift the gate;
# all API-side checks read from these constants via api.version_check.
#
#   CURRENT_APP_VERSION        — latest APK build published to users.
#   MINIMUM_SUPPORTED_VERSION  — oldest APK still allowed to hit the API.
#                                Anything older is force-updated (HTTP 426).
SPIM_LITE_CURRENT_APP_VERSION       = "2.0.0"
SPIM_LITE_MINIMUM_SUPPORTED_VERSION = "2.0.0"

# Master switch for the App-Version gate. Version 2.0.0 is the sole
# supported SPIM Lite release; every older APK is now permanently blocked
# with HTTP 426 by the existing decorator + helper module.
SPIM_LITE_ENFORCE_VERSION_GATE = True

# -------------------------------------------------------------------
# STATIC FILES
# -------------------------------------------------------------------

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static'
]

STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# -------------------------------------------------------------------
# MEDIA FILES
# -------------------------------------------------------------------

MEDIA_URL = '/media/'

MEDIA_ROOT = BASE_DIR / 'media'

# -------------------------------------------------------------------
# DEFAULT AUTO FIELD
# -------------------------------------------------------------------

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'