from pathlib import Path
from decouple import config, Csv  # <--- IMPORT ADDED

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


# --- CLOUDFLARE VE GÜVENLİK AYARLARI (EKLENDİ) ---

# Django 4.0+ için zorunlu: Admin panelindeki 403 hatasını çözer.
# Cloudflare üzerinden gelen https isteklerini güvenilir kabul eder.
CSRF_TRUSTED_ORIGINS = [
    'https://yenisozcukler.com',
]

# Cloudflare ile SSL (HTTPS) iletişimini Django'ya bildirir.
# Bu ayar olmadan Django, isteğin güvenli olduğunu anlamayıp işlemi reddedebilir.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

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
]
# Geliştirme için yerel bellek cache'i yeterlidir.
# İleride Redis'e geçilebilir.
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
    'core.middleware.CloudflareSecurityMiddleware', # Senin özel middleware'in
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

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
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]

# Internationalization
LANGUAGE_CODE = 'tr-tr' # Türkçe karakterler ve formatlar için tr-tr yapıldı
TIME_ZONE = 'Europe/Istanbul' # Saat dilimi düzeltildi
USE_I18N = True
USE_TZ = True

# --- STATIC FILES (CSS, JavaScript, Images) AYARLARI ---

STATIC_URL = '/static/'

# 1. Geliştirme ortamında statik dosyaların nerede aranacağı:
# Django, 'core/static' klasörüne bakması gerektiğini buradan anlayacak.
STATICFILES_DIRS = [
    BASE_DIR  / "static",
]

# 2. collectstatic komutu çalıştırıldığında tüm dosyaların toplanacağı yer:
STATIC_ROOT = BASE_DIR / 'staticfiles'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST FRAMEWORK AYARLARI
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        # Public API olduğu için boş bırakıldı, view bazlı kontrol var.
    ]
}

STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'



if DEBUG:
    # Geliştirme (Localhost) ortamında HTTPS zorlamasını kapatıyoruz
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    # 1. HTTP -> HTTPS Yönlendirmesi
    
else:
    # Bu ayarlar SADECE canlı ortamda (Production) çalışmalı
    SECURE_SSL_REDIRECT = True

    # 2. Çerez Güvenliği
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # 3. HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 Yıl
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True