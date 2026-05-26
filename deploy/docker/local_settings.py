import os

FRONTEND_HOST = os.getenv('FRONTEND_HOST', 'http://localhost')
PORTAL_NAME = os.getenv('PORTAL_NAME', 'MediaCMS')
REDIS_LOCATION = os.getenv('REDIS_LOCATION', 'redis://redis:6379/1')

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv('POSTGRES_NAME', 'mediacms'),
        "HOST": os.getenv('POSTGRES_HOST', 'db'),
        "PORT": os.getenv('POSTGRES_PORT', '5432'),
        "USER": os.getenv('POSTGRES_USER', 'mediacms'),
        "PASSWORD": os.getenv('POSTGRES_PASSWORD', 'mediacms'),
        "OPTIONS": {'pool': True},
    }
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_LOCATION,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# CELERY STUFF
BROKER_URL = REDIS_LOCATION
CELERY_RESULT_BACKEND = BROKER_URL

MP4HLS_COMMAND = "/home/mediacms.io/bento4/bin/mp4hls"

DEBUG = os.getenv('DEBUG', 'False') == 'True'

USE_WHISPER_TRANSCRIBE = os.getenv('USE_WHISPER_TRANSCRIBE', 'True') == 'True'
WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'medium')
WHISPER_BIN = os.getenv('WHISPER_BIN', '/home/mediacms.io/bin/whisper')
DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY', '')
APPROVAL_REVIEWER = os.getenv('APPROVAL_REVIEWER', 'admin')
IP_WHITELIST = [ip.strip() for ip in os.getenv('IP_WHITELIST', '').split(',') if ip.strip()]
