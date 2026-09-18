from decouple import config

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ]
}

RATELIMIT_IP_META_KEY = 'common.http.get_client_ip'
RATELIMIT_ENABLE = config('RATELIMIT_ENABLE', default=True, cast=bool)
