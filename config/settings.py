from pathlib import Path
from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
# Reads SECRET_KEY from .env
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
# Reads DEBUG from .env, converts "False"/"True" string to boolean
DEBUG = config('DEBUG', default=False, cast=bool)

# Reads ALLOWED_HOSTS from .env, converts comma-separated string to list
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())

# --- CLOUDFLARE VE GÜVENLİK AYARLARI ---

# Django 4.0+ için zorunlu: Admin panelindeki 403 hatasını çözer.
CSRF_TRUSTED_ORIGINS = [
    'https://yenisozcukler.com',
    'https://www.yenisozcukler.com',
]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CONTENT_TYPE_NOSNIFF = True

# Session cookie hardening — applies in all environments
SESSION_COOKIE_HTTPONLY = True   
SESSION_COOKIE_SAMESITE = 'Strict'  

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'core',
    # Challenge özelliği kapatıldı (URL'leri ve arayüzü kaldırıldı) ama uygulama
    # INSTALLED_APPS'te kalmak zorunda: core.Notification.challenge_comment FK'sı
    # ve core migration'ları (0024, 0025) challenge modellerine bağımlı.
    # Kaldırılırsa Django açılışta RuntimeError verir.
    'challenge',
]

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'core.middleware.CloudflareSecurityMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Note for S2: Once you run `pip install django-csp`, uncomment the line below:
    # 'csp.middleware.CSPMiddleware',
]

# --- CSP CONFIGURATION (S2 Fix Preparation) ---
# Requires django-csp. Adjust domains based on your specific external resources.
# CSP_DEFAULT_SRC = ("'self'",)
# CSP_SCRIPT_SRC = ("'self'", "https://challenges.cloudflare.com", "https://fonts.googleapis.com")
# CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com")
# CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com")
# CSP_IMG_SRC = ("'self'", "data:")

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR.parent / 'sozluk.db',
        'OPTIONS': {
            # WAL: yazma işlemi sırasında okuyucular bloklanmaz.
            # IMMEDIATE: transaction.atomic blokları kilit yükseltme
            # deadlock'una düşmeden doğrudan yazma kilidi alır.
            'transaction_mode': 'IMMEDIATE',
            'timeout': 20,
            'init_command': 'PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;',
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]

LANGUAGE_CODE = 'tr-tr' 
TIME_ZONE = 'Europe/Istanbul' 
USE_I18N = True
USE_TZ = True

# --- STATIC FILES (CSS, JavaScript, Images) AYARLARI ---

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR  / "static",
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# --- S1 Fix: Replaced deprecated STATICFILES_STORAGE with STORAGES ---
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# django-ratelimit'in key='ip' anahtarı varsayılan olarak REMOTE_ADDR okur;
# Cloudflare arkasında bu, ziyaretçinin değil CF edge sunucusunun IP'sidir ve
# tüm ziyaretçiler aynı limit kovasını paylaşır. Gerçek IP'yi CF-Connecting-IP
# üzerinden çözen yardımcı fonksiyonu kullan (dev'de REMOTE_ADDR'a düşer).
RATELIMIT_IP_META_KEY = 'core.views.get_client_ip'

# Yük testi için geçici kapatma: .env dosyasına RATELIMIT_ENABLE=FALSE yazıp
# sunucuyu yeniden başlat. Test bitince satırı sil (varsayılan: açık).
RATELIMIT_ENABLE = config('RATELIMIT_ENABLE', default=True, cast=bool)

# REST FRAMEWORK AYARLARI
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    # --- S8 Fix: Changed empty array to IsAuthenticated default ---
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ]
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'core': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

if DEBUG:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
else:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000 
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True