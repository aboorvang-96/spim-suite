from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = config('SECRET_KEY')
DEBUG      = config('DEBUG', cast=bool, default=True)
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'accounts',
    'finance',
    'projects',
    'clients',
    'invoices',
    'dashboard',
    'reports',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF    = 'core.urls'
AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL       = '/auth/login/'
LOGIN_REDIRECT_URL  = '/dashboard/'
LOGOUT_REDIRECT_URL = '/auth/login/'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        # Injects `today_ist` / `today_ist_iso` into every template so
        # <input type="date"> can render max="{{ today_ist_iso }}" without
        # each view having to plumb the value through its own context.
        'accounts.date_utils.today_ist_context',
    ]},
}]

DATABASES = {'default': {
    'ENGINE':   'django.db.backends.mysql',
    'NAME':     config('DB_NAME'),
    'USER':     config('DB_USER'),
    'PASSWORD': config('DB_PASSWORD'),
    'HOST':     config('DB_HOST', default='localhost'),
    'PORT':     config('DB_PORT', default='3306'),
    'OPTIONS':  {'charset': 'utf8mb4'},
}}

LANGUAGE_CODE = 'en-in'
TIME_ZONE     = 'Asia/Kolkata'
USE_I18N = True
USE_TZ   = True

# Currency Settings for India
CURRENCY_SYMBOL = '₹'
CURRENCY_CODE = 'INR'

STATIC_URL       = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT      = BASE_DIR / 'staticfiles'
MEDIA_URL        = '/media/'
MEDIA_ROOT       = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS — allow SPIM Lite (Vercel) to reach the mobile API on Railway.
# django-cors-headers is already installed (requirements.txt line 15).
CORS_ALLOWED_ORIGINS = [
    'https://spim-lite.vercel.app',
]
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
