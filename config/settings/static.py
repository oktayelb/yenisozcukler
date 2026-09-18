from .base import BASE_DIR


STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR  / "static",
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
